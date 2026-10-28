"""Correction map reuse, scoped choices, concurrency guards, and retained audit evidence."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.correction_map_schema import upgrade_correction_map
from app.models.correction_decision import CorrectionDecision
from app.models.matching import MatchCandidate
from app.modules.corrections import router
from app.modules.corrections.writer import SearchWriter
from tests.test_corrections import check, reference, upload  # noqa: F401


@pytest.fixture
def mapped(
    client: TestClient, request: pytest.FixtureRequest
) -> tuple[str, dict, list[dict]]:
    review_id = request.getfixturevalue("reference")
    kind = "idpel_kosong"
    batch = upload(
        client,
        kind,
        "ID_TITIK,NAMA,LAT,LON\nA,Target A,-6.2,106.8\nB,Target B,-6.2,106.8\nC,Tanpa koordinat,,\nD,Bentrok,-6.2,106.8\n",
    )
    checked = check(client, kind, batch, review_id)
    rows = client.get(
        f"/corrections/{kind}/records", params={"process_id": checked["process_id"]}
    ).json()["items"]
    return kind, checked, rows


def details(
    client: TestClient, kind: str, process: int, record: int, **params: float
) -> dict:
    response = client.get(
        f"/corrections/{kind}/records/{record}",
        params={"process_id": process, **params},
    )
    assert response.status_code == 200, response.text
    return response.json()


def body(
    candidate: int | None,
    revision: int = 0,
    generation: int = 1,
    key: str = "choice_request_01",
    reason: str = "",
) -> dict:
    return {
        "candidate_id": candidate,
        "expected_revision": revision,
        "generation": generation,
        "request_key": key,
        "actor": "Petugas Uji",
        "reason": reason,
    }


def test_map_radius_reuses_snapshot_and_never_reads_master(
    client: TestClient, db_session: Session, mapped: tuple
) -> None:
    kind, checked, rows = mapped
    statements: list[str] = []

    def capture(_conn, _cursor, statement, _parameters, _context, _many) -> None:
        statements.append(statement.lower())

    bind = db_session.get_bind()
    event.listen(bind, "before_cursor_execute", capture)
    try:
        result = details(
            client, kind, checked["process_id"], rows[0]["id"], radius_meters=1
        )
    finally:
        event.remove(bind, "before_cursor_execute", capture)
    assert result["candidates_total"] == 7
    assert not any(
        "master_sisa_records" in statement or "cleaned_master_records" in statement
        for statement in statements
    )
    response = client.get(
        f"/corrections/{kind}/records/{rows[0]['id']}",
        params={"process_id": checked["process_id"], "radius_meters": 100},
    )
    assert response.status_code == 409
    assert (
        client.get(
            f"/corrections/{kind}/records/{rows[0]['id']}", params={"radius_meters": 1}
        ).status_code
        == 409
    )
    assert (
        details(client, kind, checked["process_id"], rows[2]["id"], radius_meters=10)[
            "candidates_total"
        ]
        == 0
    )


def test_one_choice_replace_clear_audit_and_idempotency(
    client: TestClient, db_session: Session, mapped: tuple
) -> None:
    kind, checked, rows = mapped
    process, record = checked["process_id"], rows[0]["id"]
    candidates = details(client, kind, process, record)["candidates"]
    url = f"/corrections/{kind}/checks/{process}/records/{record}/choice"
    assert client.get(url).json() == {"revision": 0, "current": None, "history": []}
    request = body(candidates[0]["id"])
    first = client.post(url, json=request)
    assert first.status_code == 200, first.text
    assert first.json()["current"]["candidate"]["fields"]["idpel"] == "002"
    assert client.post(url, json=request).json()["revision"] == 1
    assert (
        client.post(
            url, json=body(candidates[1]["id"], key="choice_request_01")
        ).status_code
        == 409
    )
    assert (
        client.post(
            url, json=body(candidates[1]["id"], key="choice_stale_001")
        ).status_code
        == 409
    )
    assert (
        client.post(
            url, json=body(candidates[1]["id"], revision=1, key="choice_no_reason")
        ).status_code
        == 422
    )
    replaced = client.post(
        url,
        json=body(
            candidates[1]["id"],
            revision=1,
            key="choice_replace_1",
            reason="Bukti meter lebih sesuai",
        ),
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["revision"] == 2
    assert (
        db_session.query(MatchCandidate)
        .filter_by(process_id=process, target_record_id=record, is_accepted=1)
        .count()
        == 1
    )
    assert replaced.json()["history"][1] == first.json()["current"]
    cleared = client.post(
        url,
        json=body(
            None, revision=2, key="choice_clear_001", reason="Perlu verifikasi lapangan"
        ),
    )
    assert cleared.status_code == 200
    assert cleared.json()["current"]["candidate_id"] is None
    assert len(cleared.json()["history"]) == 3
    assert (
        db_session.query(MatchCandidate)
        .filter_by(process_id=process, target_record_id=record, is_accepted=1)
        .count()
        == 0
    )
    assert (
        client.post(
            url, json=body(None, revision=3, key="choice_clear_002", reason="ulang")
        ).status_code
        == 422
    )


def test_choices_are_scoped_and_legacy_writes_cannot_bypass_audit(
    client: TestClient, mapped: tuple
) -> None:
    kind, checked, rows = mapped
    process, record = checked["process_id"], rows[0]["id"]
    candidate = details(client, kind, process, record)["candidates"][0]["id"]
    url = f"/corrections/{kind}/checks/{process}/records/{record}/choice"
    wrong_row = f"/corrections/{kind}/checks/{process}/records/{rows[1]['id']}/choice"
    assert client.post(wrong_row, json=body(candidate)).status_code == 404
    assert client.get(url.replace(kind, "idpel_tidak_ketemu")).status_code == 404
    assert (
        client.post(
            url.replace(kind, "idpel_tidak_ketemu"), json=body(candidate)
        ).status_code
        == 404
    )
    assert (
        client.get(url.replace(f"records/{record}", "records/99999")).status_code == 404
    )
    assert client.post(url, json={**body(candidate), "actor": "  "}).status_code == 422
    assert (
        client.post(
            f"/process/candidates/{candidate}/decision", json={"is_accepted": 1}
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/process/candidates/bulk-decision",
            json={"candidate_ids": [candidate], "is_accepted": 1},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/process/{process}/rerun", json={"radius_meters": 100}
        ).status_code
        == 409
    )
    assert client.post(f"/process/{process}/finalize-review").status_code == 409
    assert client.get(url).json()["revision"] == 0


def test_choice_survives_expansion_historical_versions_read_only(
    client: TestClient, mapped: tuple
) -> None:
    kind, checked, rows = mapped
    process, record = checked["process_id"], rows[0]["id"]
    first_candidate = details(client, kind, process, record)["candidates"][0]["id"]
    url = f"/corrections/{kind}/checks/{process}/records/{record}/choice"
    first = client.post(url, json=body(first_candidate)).json()
    retry = client.post(
        f"/corrections/{kind}/checks/{process}/retry",
        json={
            "latest_run_id": checked["latest_run"]["id"],
            "radius_meters": 100,
            "actor": "Petugas Uji",
            "request_key": "expanded_request_1",
        },
    )
    assert retry.status_code == 200, retry.text
    assert retry.json()["current_generation"] == 2
    assert client.get(url).json() == first
    assert details(client, kind, process, record, generation=1)["candidates_total"] == 7
    expanded = details(client, kind, process, record, radius_meters=100)
    assert expanded["candidates_total"] == 8
    assert (
        details(client, kind, process, record, radius_meters=10)["candidates_total"]
        == 7
    )
    assert (
        client.post(
            url,
            json=body(
                first_candidate, revision=1, reason="ulang", key="choice_old_gen_1"
            ),
        ).status_code
        == 409
    )
    assert (
        client.post(
            url,
            json=body(
                first_candidate,
                revision=1,
                generation=2,
                reason="ulang",
                key="choice_old_cand1",
            ),
        ).status_code
        == 404
    )
    accepted = client.post(
        url,
        json=body(
            expanded["candidates"][-1]["id"],
            revision=1,
            generation=2,
            reason="Kandidat hasil perluasan",
            key="choice_expanded1",
        ),
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["history"][1] == first["current"]
    assert accepted.json()["current"]["candidate"]["distance_meters"] > 50


def test_pending_search_blocks_choice_and_reset_obeys_foreign_keys(
    client: TestClient,
    db_session: Session,
    mapped: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kind, checked, rows = mapped
    process, record = checked["process_id"], rows[0]["id"]
    candidate = details(client, kind, process, record)["candidates"][0]["id"]
    url = f"/corrections/{kind}/checks/{process}/records/{record}/choice"
    assert client.post(url, json=body(candidate)).status_code == 200
    monkeypatch.setattr(
        router.execute_batch_reconciliation_pipeline,
        "apply_async",
        Mock(return_value=object()),
    )
    queued = client.post(
        f"/corrections/{kind}/checks/{process}/retry",
        json={
            "latest_run_id": checked["latest_run"]["id"],
            "radius_meters": 100,
            "actor": "Uji",
            "request_key": "queued_request_1",
        },
    )
    assert queued.json()["latest_run"]["status"] == "queued"
    assert (
        client.post(
            url,
            json=body(candidate, revision=1, key="choice_in_queue1", reason="ganti"),
        ).status_code
        == 409
    )
    assert client.post("/upload/reset").status_code == 200
    assert db_session.query(CorrectionDecision).count() == 0


@pytest.mark.parametrize("kind", ["idpel_kosong", "idpel_tidak_ketemu"])
@pytest.mark.parametrize("state", ["running", "paused", "failed"])
def test_saved_rows_can_be_chosen_before_completion_and_survive_resume(
    client: TestClient,
    db_session: Session,
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    state: str,
) -> None:
    review_id = request.getfixturevalue("reference")
    batch = upload(
        client,
        kind,
        "IDPEL,NAMA,LAT,LON\n"
        + "".join(
            f"{700 + i if kind == 'idpel_tidak_ketemu' else ''},Target {i},-6.2,106.8\n"
            for i in range(5)
        ),
    )
    started = client.post(
        f"/corrections/{kind}/checks",
        json={
            "batch_id": batch,
            "pdpj_review_id": review_id,
            "radius_meters": 10,
            "actor": "Petugas",
            "request_key": "partial_map_start",
            "incremental": True,
        },
    )
    assert started.status_code == 200, started.json()
    check = started.json()
    process = check["process_id"]
    base = f"/corrections/{kind}/checks/{process}"

    def advance(run: dict) -> dict:
        response = client.post(
            base + "/advance",
            json={
                "run_id": run["id"],
                "revision": run["processing"]["revision"],
                "chunk_size": 2,
            },
        )
        assert response.status_code == 200, response.json()
        return response.json()

    prepared = advance(check["latest_run"])
    saved = advance(prepared)
    assert saved["processing"]["processed_rows"] == 2
    if state == "paused":
        assert (
            client.post(base + "/pause", json={"run_id": saved["id"]}).status_code
            == 200
        )
    elif state == "failed":
        with monkeypatch.context() as patch:
            patch.setattr(
                SearchWriter, "flush", Mock(side_effect=RuntimeError("Interrupted"))
            )
            failed = client.post(
                base + "/advance",
                json={
                    "run_id": saved["id"],
                    "revision": saved["processing"]["revision"],
                    "chunk_size": 2,
                },
            )
        assert failed.status_code == 500
    scope = {"process_id": process, "generation": saved["generation"]}
    rows = client.get(
        f"/corrections/{kind}/records", params={**scope, "saved_only": True}
    ).json()
    assert rows["total"] == 2
    assert all(row["search_status"] == "matched" for row in rows["items"])
    assert client.get(f"/corrections/{kind}/records", params=scope).json()["total"] == 5
    record = rows["items"][0]["id"]
    detail = details(client, kind, process, record)
    candidate = detail["candidates"][0]["id"]
    choice_url = base + f"/records/{record}/choice"
    request = body(candidate)
    chosen = client.post(choice_url, json=request)
    assert chosen.status_code == 200, chosen.json()
    assert chosen.json()["current"]["candidate"]["observations"]
    assert client.post(choice_url, json=request).json()["revision"] == 1
    assert (
        client.post(
            choice_url, json=body(candidate, key="partial_stale_choice")
        ).status_code
        == 409
    )
    assert client.get(base).json()["current_generation"] == 0
    resumed = client.post(base + "/resume", json={"run_id": saved["id"]}).json()
    assert resumed["processing"]["processed_rows"] == 2
    run = advance(resumed)
    assert run["processing"]["processed_rows"] == 4
    for _ in range(8):
        if run["status"] == "completed":
            break
        run = advance(run)
    assert run["status"] == "completed"
    assert run["id"] == saved["id"]
    assert client.get(base).json()["current_generation"] == 1
    assert client.get(choice_url).json() == chosen.json()
    assert db_session.get(MatchCandidate, candidate).is_accepted == 1
    assert (
        client.get(
            f"/corrections/{kind}/records", params={**scope, "saved_only": True}
        ).json()["total"]
        == 5
    )


def test_partial_retry_keeps_old_versions_read_only_and_rejects_unsaved_rows(
    client: TestClient, mapped: tuple
) -> None:
    kind, checked, rows = mapped
    process, record = checked["process_id"], rows[0]["id"]
    old = details(client, kind, process, record)["candidates"][0]["id"]
    base = f"/corrections/{kind}/checks/{process}"
    retried = client.post(
        base + "/retry",
        json={
            "latest_run_id": checked["latest_run"]["id"],
            "radius_meters": 100,
            "actor": "Petugas",
            "request_key": "partial_map_retry",
            "incremental": True,
        },
    )
    assert retried.status_code == 200, retried.json()
    run = retried.json()["latest_run"]
    for _ in range(2):
        response = client.post(
            base + "/advance",
            json={
                "run_id": run["id"],
                "revision": run["processing"]["revision"],
                "chunk_size": 1,
            },
        )
        assert response.status_code == 200, response.json()
        run = response.json()
    assert run["processing"]["processed_rows"] == 1
    choice_url = base + f"/records/{record}/choice"
    assert client.post(choice_url, json=body(old)).status_code == 409
    assert client.post(choice_url, json=body(old, generation=2)).status_code == 404
    assert (
        client.post(
            base + f"/records/{rows[1]['id']}/choice", json=body(old, generation=2)
        ).status_code
        == 409
    )
    current = details(client, kind, process, record)["candidates"][0]["id"]
    chosen = client.post(choice_url, json=body(current, generation=2))
    assert chosen.status_code == 200, chosen.json()
    assert chosen.json()["current"]["generation"] == 2


def test_choice_schema_upgrade_is_additive_idempotent(db_session: Session) -> None:
    connection = db_session.connection()
    CorrectionDecision.__table__.drop(connection)
    upgrade_correction_map(connection)
    upgrade_correction_map(connection)
    assert "correction_decisions" in inspect(connection).get_table_names()
