"""Categorized corrections: collisions, complete outcomes, source snapshots, and retry isolation."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.config import settings
from app.correction_schema import upgrade_corrections
from app.models.correction import (
    CorrectionAttempt,
    CorrectionCandidateEvidence,
    CorrectionCheck,
    CorrectionTarget,
)
from app.models.matching import (
    MatchCandidate,
    MatchingRun,
    ProcessStatus,
    ReconciliationProcess,
)
from app.models.pdpj import PdpjRow
from app.models.upload import SourceRecord
from app.modules.corrections import router
from app.modules.spatial.pipeline import execute_pipeline
from app.modules.upload.normalization import with_reference_fields
from app.tasks.spatial_tasks import mark_process_failed


def upload(
    client: TestClient, kind: str, content: str, mapping: dict[str, str] | None = None
) -> int:
    response = client.post(
        "/upload/",
        data={"dataset_type": kind},
        files={"file": (kind + ".csv", content.encode(), "text/csv")},
    )
    assert response.status_code == 200
    batch_id = response.json()["id"]
    checked = client.post(
        "/upload/confirm-mapping",
        json={
            "batch_id": batch_id,
            "column_mapping": mapping
            or (
                {"idpel": "IDPEL"}
                if "IDPEL" in content.splitlines()[0].split(",")
                else {}
            ),
        },
    )
    assert checked.status_code == 200
    return batch_id


@pytest.fixture
def reference(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> int:
    master = "IDPEL,NAMA,LAT,LON,NOMOR_GARDU\n001,PDPJ,-6.2,106.8,G0\n"
    master += "".join(
        f"{number:03},Kandidat {number},-6.2,106.8,G{number}\n"
        for number in range(2, 9)
    )
    master += "009,Tanpa koordinat,,,G9\n010,Koordinat rusak,bad,106.8,G10\n020,Agak jauh,-6.2005,106.8,G20\n"
    upload(client, "dil", master)
    batch_id = upload(
        client,
        "pdpj",
        "IDPEL,NAMA,LAT,LON,NOMOR_METER,NOAGENDA,ID_TITIK\n001,PDPJ,-6.2,106.8,M001,A001,S001\n",
    )
    review = client.post("/pdpj/reviews", json={"batch_id": batch_id}).json()
    assert (
        client.post(
            f"/pdpj/reviews/{review['id']}/complete",
            json={"revision": review["revision"], "actor": "Petugas Uji"},
        ).status_code
        == 200
    )
    monkeypatch.setattr(settings, "ALLOW_SYNC_FALLBACK", True)
    monkeypatch.setattr(
        router.execute_batch_reconciliation_pipeline,
        "apply_async",
        Mock(side_effect=RuntimeError("offline")),
    )
    return review["id"]


def check(
    client: TestClient,
    kind: str,
    batch_id: int,
    review_id: int,
    key: str = "request_key_1",
    radius: float = 10,
) -> dict:
    response = client.post(
        f"/corrections/{kind}/checks",
        json={
            "batch_id": batch_id,
            "pdpj_review_id": review_id,
            "radius_meters": radius,
            "request_key": key,
            "actor": "Petugas Uji",
        },
    )
    assert response.status_code == 200, response.json()
    assert response.json()["status"] == "completed", response.json()
    return response.json()


def test_not_found_category_checks_every_row_and_counts_rows_not_candidates(
    client: TestClient, reference: int, db_session: Session
) -> None:
    kind = "idpel_tidak_ketemu"
    batch_id = upload(
        client,
        kind,
        "IDPEL,NOMOR_METER,LAT,LON\n001,X,-6.2,106.8\n999,M001,-6.2,106.8\n998,M998,-6.2,106.8\n009,M009,-6.2,106.8\n997,M997,-9,110\n996,M996,,\n995,M995,bad,106.8\n,M994,-6.2,106.8\n",
    )
    before = client.get(f"/corrections/{kind}/summary?batch_id={batch_id}").json()
    assert before["total_rows"] == before["not_checked"] == 8
    assert (
        client.get(f"/corrections/{kind}/records?batch_id={batch_id}").json()["total"]
        == 8
    )
    result = check(client, kind, batch_id, reference)
    process_id = result["process_id"]
    params = {"batch_id": batch_id, "process_id": process_id}
    summary = client.get(f"/corrections/{kind}/summary", params=params).json()
    assert summary["total_rows"] == 8 and summary["pdpj_conflicts"] == 2
    assert summary["matched"] == 2 and summary["no_candidates"] == 1
    assert summary["incomplete_coordinates"] == 2 and summary["invalid_data"] == 2
    assert summary["identity_found"] == 2 and summary["not_checked"] == 0
    rows = client.get(
        f"/corrections/{kind}/records", params={**params, "limit": 2, "skip": 2}
    ).json()
    assert rows["total"] == 8 and len(rows["items"]) == 2
    assert all(row["candidate_count"] == 7 for row in rows["items"])
    assert (
        rows["items"][1]["identity_status"] == "found"
        and rows["items"][1]["category"] == kind
    )
    assert (
        db_session.query(MatchCandidate)
        .filter(MatchCandidate.process_id == process_id)
        .count()
        == 14
    )
    assert db_session.query(CorrectionTarget).count() == 8
    for status, expected in (
        ("pdpj_conflict", 2),
        ("matched", 2),
        ("no_candidates", 1),
        ("incomplete_coordinates", 2),
        ("invalid_data", 2),
        ("identity_found", 2),
        ("identity_not_found", 5),
    ):
        assert (
            client.get(
                f"/corrections/{kind}/records", params={**params, "status": status}
            ).json()["total"]
            == expected
        )
    assert (
        client.get(
            f"/corrections/{kind}/records", params={**params, "q": "M998"}
        ).json()["total"]
        == 1
    )
    assert (
        client.get(f"/corrections/{kind}/records", params={**params, "q": "%"}).json()[
            "total"
        ]
        == 0
    )
    assert (
        len(client.get(f"/corrections/{kind}/checks?batch_id={batch_id}").json()) == 1
    )
    assert client.get(f"/corrections/{kind}/batches/{batch_id}").json()["headers"] == [
        "IDPEL",
        "NOMOR_METER",
        "LAT",
        "LON",
    ]


def test_empty_category_compares_typed_references_and_only_warns_on_same_coordinates(
    client: TestClient, reference: int
) -> None:
    kind = "idpel_kosong"
    batch_id = upload(
        client,
        kind,
        "IDPEL,NOMOR_METER,NOAGENDA,ID_TITIK,LAT,LON\n,M001,,,-6.2,106.8\n,,M001,,-6.2,106.8\n,,A001,,-6.2,106.8\n,,,S001,-6.2,106.8\n,,,OTHER,-6.2,106.8\n,,,NO-COORD,,\n998,,,WRONG-KIND,-6.2,106.8\n",
    )
    result = check(client, kind, batch_id, reference)
    rows = client.get(
        f"/corrections/{kind}/records?process_id={result['process_id']}"
    ).json()["items"]
    assert [row["search_status"] for row in rows] == [
        "pdpj_conflict",
        "matched",
        "matched",
        "pdpj_conflict",
        "matched",
        "incomplete_coordinates",
        "invalid_data",
    ]
    assert rows[0]["conflicts"][0]["code"] == "meter_sama_pdpj"
    assert not rows[2]["conflicts"] and rows[2]["candidate_count"] == 7
    assert rows[2]["fields"]["agenda_ref"] == "A001"
    assert rows[3]["conflicts"][0]["code"] == "survey_sama_pdpj"
    assert rows[4]["warnings"][0]["code"] == "koordinat_sama_pdpj"
    assert not rows[4]["conflicts"] and rows[4]["candidate_count"] == 7
    assert rows[6]["errors"][0]["code"] == "kategori_idpel_harus_kosong"


@pytest.mark.parametrize("kind", ["idpel_tidak_ketemu", "idpel_kosong"])
@pytest.mark.parametrize("legacy_mapping", [False, True])
def test_shared_agenda_does_not_block_candidate_search_or_selection(
    client: TestClient, reference: int, kind: str, legacy_mapping: bool
) -> None:
    # Repeated agendas are allowed both across PDPJ and within the correction file.
    ids = ("998", "997") if kind == "idpel_tidak_ketemu" else ("", "")
    mapping = {"idpel": "IDPEL", "target_ref": "NOAGENDA"} if legacy_mapping else None
    batch_id = upload(
        client,
        kind,
        f"IDPEL,NOAGENDA,LAT,LON\n{ids[0]},A001,-6.2,106.8\n{ids[1]},A001,-6.2,106.8\n",
        mapping=mapping,
    )
    checked = check(client, kind, batch_id, reference)
    process = checked["process_id"]
    summary = client.get(
        f"/corrections/{kind}/summary", params={"process_id": process}
    ).json()
    assert summary["pdpj_conflicts"] == 0 and summary["matched"] == 2
    rows = client.get(
        f"/corrections/{kind}/records", params={"process_id": process}
    ).json()["items"]
    assert all(not row["conflicts"] and row["candidate_count"] == 7 for row in rows)
    assert all(row["fields"]["agenda_ref"] == "A001" for row in rows)
    detail = client.get(
        f"/corrections/{kind}/records/{rows[0]['id']}", params={"process_id": process}
    ).json()
    assert all(
        candidate["fields"]["idpel"] != "001" for candidate in detail["candidates"]
    )
    choice = client.post(
        f"/corrections/{kind}/checks/{process}/records/{rows[0]['id']}/choice",
        json={
            "generation": 1,
            "expected_revision": 0,
            "candidate_id": detail["candidates"][0]["id"],
            "actor": "Petugas Uji",
            "reason": "",
            "request_key": "shared_agenda_choice",
        },
    )
    assert choice.status_code == 200, choice.text
    assert choice.json()["current"]["target_fields"]["agenda_ref"] == "A001"


def test_shared_agenda_does_not_waive_idpel_meter_survey_or_coordinate_validation(
    client: TestClient, reference: int
) -> None:
    kind = "idpel_tidak_ketemu"
    batch_id = upload(
        client,
        kind,
        "IDPEL,NOAGENDA,NOMOR_METER,ID_TITIK,LAT,LON\n001,A001,,,-6.2,106.8\n998,A001,M001,,-6.2,106.8\n997,A001,,S001,-6.2,106.8\n996,A001,,,,\n995,A001,,,bad,106.8\n994,A001,,,-9,110\n",
    )
    checked = check(client, kind, batch_id, reference)
    rows = client.get(
        f"/corrections/{kind}/records", params={"process_id": checked["process_id"]}
    ).json()["items"]
    assert [row["search_status"] for row in rows] == [
        "pdpj_conflict",
        "pdpj_conflict",
        "pdpj_conflict",
        "incomplete_coordinates",
        "invalid_data",
        "no_candidates",
    ]
    assert [row["conflicts"][0]["code"] for row in rows[:3]] == [
        "idpel_sama_pdpj",
        "meter_sama_pdpj",
        "survey_sama_pdpj",
    ]
    assert all(
        conflict["code"] != "agenda_sama_pdpj"
        for row in rows
        for conflict in row["conflicts"]
    )


def test_retry_applies_new_agenda_policy_without_rewriting_previous_result(
    client: TestClient, reference: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.modules.corrections.service import REFERENCE_FIELDS

    kind = "idpel_kosong"
    batch_id = upload(client, kind, "NOAGENDA,LAT,LON\nA001,-6.2,106.8\n")
    monkeypatch.setitem(REFERENCE_FIELDS, "agenda", ("agenda_ref",))
    previous = check(client, kind, batch_id, reference)
    process = previous["process_id"]
    record = client.get(
        f"/corrections/{kind}/records", params={"process_id": process}
    ).json()["items"][0]
    assert record["search_status"] == "pdpj_conflict"
    assert record["conflicts"][0]["code"] == "agenda_sama_pdpj"
    monkeypatch.delitem(REFERENCE_FIELDS, "agenda")
    retried = client.post(
        f"/corrections/{kind}/checks/{process}/retry",
        json={
            "latest_run_id": previous["latest_run"]["id"],
            "radius_meters": 10,
            "actor": "Petugas Uji",
            "request_key": "retry_without_agenda_block",
        },
    )
    assert retried.status_code == 200 and retried.json()["current_generation"] == 2
    path = f"/corrections/{kind}/records/{record['id']}"
    latest = client.get(path, params={"process_id": process}).json()
    assert latest["search_status"] == "matched" and latest["candidates_total"] == 7
    assert latest["conflicts"] == [] and latest["fields"]["agenda_ref"] == "A001"
    historical = client.get(
        path, params={"process_id": process, "generation": 1}
    ).json()
    assert (
        historical["search_status"] == "pdpj_conflict"
        and historical["candidates_total"] == 0
    )
    assert historical["conflicts"] == record["conflicts"]


def test_candidate_details_use_saved_evidence_and_keep_zero_candidate_rows(
    client: TestClient, reference: int, db_session: Session
) -> None:
    kind = "idpel_kosong"
    batch_id = upload(
        client, kind, "ID_TITIK,LAT,LON\nNEAR,-6.2,106.8\nFAR,-9,110\nEMPTY,,\n"
    )
    result = check(client, kind, batch_id, reference)
    rows = client.get(
        f"/corrections/{kind}/records?process_id={result['process_id']}"
    ).json()["items"]
    detail_path = f"/corrections/{kind}/records/{rows[0]['id']}"
    detail = client.get(
        detail_path, params={"process_id": result["process_id"], "limit": 2}
    ).json()
    assert detail["candidates_total"] == 7 and len(detail["candidates"]) == 2
    assert detail["candidates"][0]["fields"]["idpel"] == "002"
    assert detail["candidates"][0]["fields"]["kode_gardu"] == "G2"
    assert detail["candidates"][0]["observations"][0]["filename"] == "dil.csv"
    assert detail["candidates"][0]["distance_meters"] == 0
    source_id = detail["candidates"][0]["observations"][0]["record_id"]
    db_session.get(SourceRecord, source_id).data = {
        "IDPEL": "CHANGED",
        "NAMA": "changed after check",
    }
    db_session.commit()
    saved = client.get(
        detail_path, params={"process_id": result["process_id"], "limit": 2}
    ).json()
    assert saved["candidates"] == detail["candidates"]
    for row in rows[1:]:
        empty = client.get(
            f"/corrections/{kind}/records/{row['id']}",
            params={"process_id": result["process_id"]},
        ).json()
        assert empty["candidates_total"] == 0 and empty["candidates"] == []
        assert empty["raw_data"]["ID_TITIK"] in {"FAR", "EMPTY"}
    assert (
        not db_session.query(MatchCandidate)
        .filter(MatchCandidate.candidate_idpel == "001")
        .first()
    )


def test_idempotent_requests_rerun_history_stale_retry_and_late_failure(
    client: TestClient, reference: int, db_session: Session
) -> None:
    kind = "idpel_kosong"
    batch_id = upload(client, kind, "ID_TITIK,LAT,LON\nONE,-6.2,106.8\n")
    first = check(client, kind, batch_id, reference)
    again = check(client, kind, batch_id, reference)
    assert first["requested_run_id"] == again["requested_run_id"]
    process_id = first["process_id"]
    candidate = (
        db_session.query(MatchCandidate)
        .filter(MatchCandidate.process_id == process_id)
        .first()
    )
    candidate.is_accepted = 1
    db_session.commit()
    assert (
        execute_pipeline(db_session, process_id, first["requested_run_id"])["status"]
        == "completed"
    )
    assert db_session.query(MatchCandidate).count() == 7 and candidate.is_accepted == 1
    retry_body = {
        "latest_run_id": first["requested_run_id"],
        "radius_meters": 100,
        "request_key": "retry_key_1",
        "actor": "Petugas Uji",
    }
    second = client.post(
        f"/corrections/{kind}/checks/{process_id}/retry", json=retry_body
    )
    assert second.status_code == 200 and second.json()["current_generation"] == 2
    assert (
        client.post(
            f"/corrections/{kind}/checks/{process_id}/retry", json=retry_body
        ).json()["requested_run_id"]
        == second.json()["requested_run_id"]
    )
    stale = {**retry_body, "request_key": "retry_key_stale"}
    assert (
        client.post(
            f"/corrections/{kind}/checks/{process_id}/retry", json=stale
        ).status_code
        == 409
    )
    assert db_session.query(MatchCandidate).count() == 15
    old = client.get(
        f"/corrections/{kind}/records?process_id={process_id}&generation=1"
    ).json()["items"][0]
    new = client.get(f"/corrections/{kind}/records?process_id={process_id}").json()[
        "items"
    ][0]
    assert old["candidate_count"] == 7 and new["candidate_count"] == 8
    assert candidate.is_accepted == 1
    mark_process_failed(db_session, process_id, first["requested_run_id"])
    assert (
        db_session.get(ReconciliationProcess, process_id).matching_status
        == ProcessStatus.COMPLETED
    )


def test_queued_and_failed_jobs_do_not_publish_results_and_can_retry(
    client: TestClient,
    reference: int,
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    kind = "idpel_kosong"
    batch_id = upload(client, kind, "ID_TITIK,LAT,LON\nONE,-6.2,106.8\n")
    monkeypatch.setattr(
        router.execute_batch_reconciliation_pipeline,
        "apply_async",
        Mock(return_value=object()),
    )
    body = {
        "batch_id": batch_id,
        "pdpj_review_id": reference,
        "radius_meters": 10,
        "request_key": "queued_key_1",
        "actor": "Petugas Uji",
    }
    queued = client.post(f"/corrections/{kind}/checks", json=body).json()
    assert (
        queued["latest_run"]["status"] == "queued" and queued["current_generation"] == 0
    )
    process_id, run_id = queued["process_id"], queued["requested_run_id"]
    assert (
        client.get(f"/corrections/{kind}/summary?process_id={process_id}").json()[
            "not_checked"
        ]
        == 1
    )
    assert (
        client.get(
            f"/corrections/{kind}/records?process_id={process_id}&generation=1"
        ).status_code
        == 409
    )
    retry = {
        "latest_run_id": run_id,
        "radius_meters": 10,
        "request_key": "queued_retry_1",
        "actor": "Petugas Uji",
    }
    assert (
        client.post(
            f"/corrections/{kind}/checks/{process_id}/retry", json=retry
        ).status_code
        == 409
    )
    mark_process_failed(db_session, process_id, run_id)
    monkeypatch.setattr(settings, "ALLOW_SYNC_FALLBACK", False)
    monkeypatch.setattr(
        router.execute_batch_reconciliation_pipeline,
        "apply_async",
        Mock(side_effect=RuntimeError("offline")),
    )
    failed = client.post(
        f"/corrections/{kind}/checks/{process_id}/retry",
        json={**retry, "request_key": "failure_key_1"},
    ).json()
    assert (
        failed["latest_run"]["status"] == "failed" and failed["current_generation"] == 0
    )
    assert failed["execution_mode"] == "worker_unavailable"
    assert failed["latest_run"]["failure_code"] == "worker_unavailable"
    stored = client.get(f"/corrections/{kind}/checks/{process_id}").json()
    assert stored["latest_run"]["failure_code"] == "worker_unavailable"
    monkeypatch.setattr(settings, "ALLOW_SYNC_FALLBACK", True)
    success = client.post(
        f"/corrections/{kind}/checks/{process_id}/retry",
        json={
            **retry,
            "latest_run_id": failed["requested_run_id"],
            "request_key": "success_key_1",
        },
    ).json()
    assert success["status"] == "completed" and success["current_generation"] == 3
    assert success["execution_mode"] == "sync_fallback"
    assert success["latest_run"]["failure_code"] is None
    assert success["runs"][1]["failure_code"] == "worker_unavailable"
    assert db_session.query(CorrectionTarget).count() == 1


def test_scope_validation_pending_mapping_and_completed_pdpj_are_enforced(
    client: TestClient, reference: int
) -> None:
    first = upload(client, "idpel_kosong", "ID_TITIK,LAT,LON\nFIRST,-6.2,106.8\n")
    other = upload(client, "idpel_tidak_ketemu", "IDPEL,LAT,LON\n999,-6.2,106.8\n")
    checked = check(client, "idpel_kosong", first, reference)
    process_id = checked["process_id"]
    own_row = client.get(
        f"/corrections/idpel_kosong/records?process_id={process_id}"
    ).json()["items"][0]["id"]
    assert (
        client.get(f"/corrections/idpel_tidak_ketemu/checks/{process_id}").status_code
        == 404
    )
    assert (
        client.get(f"/corrections/idpel_tidak_ketemu/records/{own_row}").status_code
        == 404
    )
    assert (
        client.get(
            f"/corrections/idpel_tidak_ketemu/records?batch_id={other}&process_id={process_id}"
        ).status_code
        == 404
    )
    assert client.get(f"/corrections/idpel_kosong/batches/{other}").status_code == 404
    assert client.get("/corrections/idpel_kosong/checks/999999").status_code == 404
    assert client.get("/corrections/idpel_kosong/records/999999").status_code == 404
    assert (
        client.get(
            f"/corrections/idpel_kosong/records?process_id={process_id}&generation=99"
        ).status_code
        == 404
    )
    assert (
        client.get("/corrections/idpel_kosong/records?generation=1").status_code == 422
    )
    assert client.get("/corrections/idpel_kosong/records?limit=1000").status_code == 422
    assert (
        client.post("/upload/auto-pipeline", params={"batch_id": first}).status_code
        == 422
    )
    assert (
        client.post(
            "/upload/confirm-mapping",
            json={"batch_id": first, "column_mapping": {"survey_ref": "LAT"}},
        ).status_code
        == 409
    )
    pdpj = upload(client, "pdpj", "IDPEL,LAT,LON\n001,-6.2,106.8\n")
    pending_review = client.post("/pdpj/reviews", json={"batch_id": pdpj}).json()["id"]
    body = {
        "batch_id": first,
        "pdpj_review_id": pending_review,
        "actor": "Petugas Uji",
        "request_key": "pending_review_1",
    }
    assert client.post("/corrections/idpel_kosong/checks", json=body).status_code == 422
    pending = client.post(
        "/upload/",
        data={"dataset_type": "idpel_kosong"},
        files={"file": ("pending.csv", b"CUSTOM\nONE\n", "text/csv")},
    ).json()["id"]
    assert client.get(f"/corrections/idpel_kosong/batches/{pending}").json()[
        "headers"
    ] == ["CUSTOM"]
    assert (
        client.post(
            "/corrections/idpel_kosong/checks",
            json={**body, "batch_id": pending, "pdpj_review_id": reference},
        ).status_code
        == 409
    )


def test_migration_ready_pdpj_legacy_categories_and_reset(
    client: TestClient, reference: int, db_session: Session
) -> None:
    batch_id = upload(client, "idpel_kosong", "ID_TITIK,LAT,LON\nONE,-6.2,106.8\n")
    check(client, "idpel_kosong", batch_id, reference)
    assert client.get("/corrections/ready-pdpj").json()[0]["review_id"] == reference
    upload(client, "target", "ID_TITIK,LAT,LON\nLEGACY,-6.2,106.8\n")
    assert len(client.get("/corrections/idpel_kosong/batches").json()) == 1
    assert client.get("/corrections/idpel_tidak_ketemu/batches").json() == []
    with db_session.get_bind().begin() as connection:
        upgrade_corrections(connection)
        upgrade_corrections(connection)
        assert "correction_targets" in inspect(connection).get_table_names()
    assert client.post("/upload/reset").status_code == 200
    for model in (
        CorrectionCheck,
        CorrectionTarget,
        CorrectionAttempt,
        CorrectionCandidateEvidence,
    ):
        assert db_session.query(model).count() == 0


def test_old_pdpj_reference_upgrade_respects_replaced_generic_reference() -> None:
    old = {"idpel": "001", "target_ref": "NEW"}
    result = with_reference_fields(
        old, {"IDPEL": "001", "NOMOR_METER": "OLD", "NOAGENDA": "OTHER"}, None
    )
    assert result["meter_ref"] == "NEW" and result["agenda_ref"] == "OTHER"
    assert result["survey_ref"] is None and old == {"idpel": "001", "target_ref": "NEW"}


def test_partial_flush_of_many_conflicts_rolls_back_without_losing_published_results(
    client: TestClient,
    reference: int,
    db_session: Session,
) -> None:
    kind = "idpel_tidak_ketemu"
    batch_id = upload(client, kind, "IDPEL,LAT,LON\n" + "001,-6.2,106.8\n" * 205)
    original = check(client, kind, batch_id, reference)
    process_id = original["process_id"]
    flushed = False

    def interrupt_after_outcomes_are_written(session, _):
        nonlocal flushed
        if any(isinstance(row, CorrectionTarget) for row in session.new):
            flushed = True
            raise RuntimeError("Simulated failure after writing outcomes")

    event.listen(db_session, "after_flush", interrupt_after_outcomes_are_written)
    try:
        result = client.post(
            f"/corrections/{kind}/checks/{process_id}/retry",
            json={
                "latest_run_id": original["latest_run"]["id"],
                "actor": "Petugas Uji",
                "radius_meters": 30,
                "request_key": "partial_conflicts_retry",
            },
        ).json()
    finally:
        event.remove(db_session, "after_flush", interrupt_after_outcomes_are_written)
    assert flushed
    assert result["latest_run"]["status"] == "failed"
    assert result["latest_run"]["failure_code"] == "processing_failed"
    assert result["current_generation"] == original["current_generation"]
    assert db_session.query(CorrectionTarget).count() == 205
    summary = client.get(f"/corrections/{kind}/summary?process_id={process_id}").json()
    assert summary["pdpj_conflicts"] == 205 and summary["not_checked"] == 0


def test_reference_zero_placeholders_do_not_block_and_leading_zeroes_remain_distinct(
    client: TestClient,
    reference: int,
    db_session: Session,
) -> None:
    prior = db_session.query(PdpjRow).filter(PdpjRow.review_id == reference).first()
    assert prior is not None
    source = db_session.get(SourceRecord, prior.source_record_id)
    assert source is not None
    review = client.post("/pdpj/reviews", json={"batch_id": source.batch_id}).json()
    row = client.get(f"/pdpj/reviews/{review['id']}/rows").json()["items"][0]
    changed = client.patch(
        f"/pdpj/reviews/{review['id']}/rows/{row['id']}",
        json={
            "revision": review["revision"],
            "actor": "Petugas Uji",
            "reason": "Perbaikan nomor meter",
            "fields": {"meter_ref": "000123", "nomor_meter_prepaid": "0"},
        },
    )
    assert changed.status_code == 200
    assert (
        client.post(
            f"/pdpj/reviews/{review['id']}/complete",
            json={"revision": changed.json()["revision"], "actor": "Petugas Uji"},
        ).status_code
        == 200
    )
    batch_id = upload(
        client,
        "idpel_kosong",
        "NOMOR_METER,LAT,LON\n0,-6.2,106.8\n123,-6.2,106.8\n000123,-6.2,106.8\n",
    )
    checked = check(client, "idpel_kosong", batch_id, review["id"])
    records = client.get(
        f"/corrections/idpel_kosong/records?process_id={checked['process_id']}"
    ).json()["items"]
    assert [row["search_status"] for row in records] == [
        "matched",
        "matched",
        "pdpj_conflict",
    ]


@pytest.mark.parametrize(
    "target_lat,target_lon,master_lat,master_lon,radius",
    [(0, 179.9999, 0, -179.9999, 30), (90, 0, 89.99999, 180, 5)],
)
def test_spatial_bound_preserves_candidates_across_dateline_and_near_poles(
    client: TestClient,
    reference: int,
    target_lat: float,
    target_lon: float,
    master_lat: float,
    master_lon: float,
    radius: float,
) -> None:
    upload(client, "dil", f"IDPEL,LAT,LON\n030,{master_lat},{master_lon}\n")
    pdpj = client.get("/pdpj/batches").json()[0]["id"]
    review = client.post("/pdpj/reviews", json={"batch_id": pdpj}).json()
    assert (
        client.post(
            f"/pdpj/reviews/{review['id']}/complete",
            json={"revision": review["revision"], "actor": "Petugas Uji"},
        ).status_code
        == 200
    )
    batch_id = upload(
        client,
        "idpel_kosong",
        f"ID_TITIK,LAT,LON\nBOUNDARY,{target_lat},{target_lon}\n",
    )
    checked = check(client, "idpel_kosong", batch_id, review["id"], radius=radius)
    record = client.get(
        f"/corrections/idpel_kosong/records?process_id={checked['process_id']}"
    ).json()["items"][0]
    detail = client.get(
        f"/corrections/idpel_kosong/records/{record['id']}?process_id={checked['process_id']}"
    ).json()
    assert (
        detail["candidates_total"] == 1
        and detail["candidates"][0]["fields"]["idpel"] == "030"
    )


def test_correction_worker_failure_is_final_until_explicit_retry(
    client: TestClient,
    reference: int,
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    from app.tasks import spatial_tasks

    batch_id = upload(client, "idpel_kosong", "ID_TITIK,LAT,LON\nONE,-6.2,106.8\n")
    monkeypatch.setattr(
        router.execute_batch_reconciliation_pipeline,
        "apply_async",
        Mock(return_value=object()),
    )
    queued = client.post(
        "/corrections/idpel_kosong/checks",
        json={
            "batch_id": batch_id,
            "pdpj_review_id": reference,
            "actor": "Petugas Uji",
            "request_key": "worker_failure_1",
        },
    ).json()
    monkeypatch.setattr(spatial_tasks, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", Mock())
    monkeypatch.setattr(
        spatial_tasks, "execute_pipeline", Mock(side_effect=RuntimeError("failed"))
    )
    monkeypatch.setattr(
        spatial_tasks.execute_batch_reconciliation_pipeline, "retry", Mock()
    )
    failed = spatial_tasks.execute_batch_reconciliation_pipeline.run(
        process_id=queued["process_id"],
        run_id=queued["requested_run_id"],
        retry_on_failure=False,
    )
    assert failed["status"] == "failed"
    spatial_tasks.execute_batch_reconciliation_pipeline.retry.assert_not_called()
    assert (
        db_session.get(MatchingRun, queued["requested_run_id"]).status
        == ProcessStatus.FAILED
    )
    stored = client.get(
        f"/corrections/idpel_kosong/checks/{queued['process_id']}"
    ).json()
    assert stored["latest_run"]["failure_code"] == "processing_failed"
