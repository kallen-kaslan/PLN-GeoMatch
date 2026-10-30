"""Durable correction progress, real final validation, and bounded crash recovery."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.correction_progress_schema import upgrade_correction_progress
from app.models.correction import CorrectionCandidateEvidence, CorrectionTarget
from app.models.matching import MatchCandidate, MatchingRun, ReconciliationProcess
from app.modules.corrections import router
from app.modules.corrections.service import selected_run
from app.modules.corrections.writer import SearchWriter
from tests.test_corrections import upload


@pytest.fixture
def pending(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> dict:
    submitted = Mock(
        side_effect=RuntimeError("No worker is needed for incremental processing")
    )
    monkeypatch.setattr(
        router.execute_batch_reconciliation_pipeline, "apply_async", submitted
    )
    upload(
        client, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n002,-6.2,106.8\n003,-6.2,106.8\n"
    )
    pdpj = upload(client, "pdpj", "IDPEL,LAT,LON\n001,-6.2,106.8\n")
    review = client.post("/pdpj/reviews", json={"batch_id": pdpj}).json()
    assert (
        client.post(
            f"/pdpj/reviews/{review['id']}/complete",
            json={"revision": review["revision"], "actor": "Petugas"},
        ).status_code
        == 200
    )
    batch = upload(client, "idpel_kosong", "NAMA,LAT,LON\n" + "Target,-6.2,106.8\n" * 5)
    response = client.post(
        "/corrections/idpel_kosong/checks",
        json={
            "batch_id": batch,
            "pdpj_review_id": review["id"],
            "radius_meters": 10,
            "actor": "Petugas",
            "request_key": "progress_request_1",
            "incremental": True,
        },
    )
    assert response.status_code == 200, response.json()
    assert not submitted.called
    return response.json()


def path(check: dict) -> str:
    return f"/corrections/idpel_kosong/checks/{check['process_id']}"


def advance(client: TestClient, check: dict, run: dict) -> dict:
    response = client.post(
        path(check) + "/advance",
        json={
            "run_id": run["id"],
            "revision": run["processing"]["revision"],
            "chunk_size": 2,
        },
    )
    assert response.status_code == 200, response.json()
    return response.json()


def finish(client: TestClient, check: dict, run: dict) -> dict:
    for _ in range(12):
        if run["status"] == "completed":
            return run
        run = advance(client, check, run)
    pytest.fail("Processing did not finish")


def test_stage_duration_survives_reload_and_pause_without_counting_preparation(
    client: TestClient, pending: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.modules.corrections import engine, progress

    preparation_clock = iter([100.0, 1000.0])
    monkeypatch.setattr(progress, "monotonic", lambda: next(preparation_clock))
    run = advance(client, pending, pending["latest_run"])
    assert run["processing"]["stage"] == "matching"
    assert run["processing"]["elapsed_seconds"] == 900.0
    assert run["processing"]["stage_elapsed_seconds"] == 0.0
    matching_clock = iter([100.0, 110.0, 200.0, 220.0, 300.0, 330.0])
    monkeypatch.setattr(engine, "monotonic", lambda: next(matching_clock))
    monkeypatch.setattr(progress, "monotonic", lambda: 100.0)
    first = advance(client, pending, run)
    assert first["processing"]["stage_elapsed_seconds"] == 10.0
    assert first["processing"]["stage_timed_rows"] == 2
    restored = client.get(path(pending) + "/progress").json()
    assert restored["processing"] == first["processing"]
    paused = client.post(path(pending) + "/pause", json={"run_id": first["id"]}).json()
    assert paused["processing"]["stage_elapsed_seconds"] == 10.0
    resumed = client.post(
        path(pending) + "/resume", json={"run_id": first["id"]}
    ).json()
    second = advance(client, pending, resumed)
    assert second["processing"]["stage_elapsed_seconds"] == 30.0
    third = advance(client, pending, second)
    assert third["processing"]["stage"] == "validating"
    assert third["processing"]["stage_elapsed_seconds"] == 0.0
    assert third["processing"]["stage_timed_rows"] == 0
    assert third["processing"]["elapsed_seconds"] == 960.0
    validation_clock = iter([100.0, 105.0])
    monkeypatch.setattr(progress, "monotonic", lambda: next(validation_clock))
    validated = advance(client, pending, third)
    assert validated["processing"]["stage_elapsed_seconds"] == 5.0
    assert validated["processing"]["validated_rows"] == 2
    assert validated["processing"]["stage_timed_rows"] == 2


def test_existing_checkpoint_only_uses_newly_measured_rows_for_time_estimates(
    client: TestClient,
    db_session: Session,
    pending: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.corrections import engine

    prepared = advance(client, pending, pending["latest_run"])
    first = advance(client, pending, prepared)
    stored = db_session.get(MatchingRun, first["id"])
    old_progress = dict(stored.processing)
    old_progress.pop("stage_elapsed_seconds")
    old_progress.pop("stage_timed_rows")
    stored.processing = old_progress
    db_session.commit()
    matching_clock = iter([100.0, 120.0])
    monkeypatch.setattr(engine, "monotonic", lambda: next(matching_clock))
    second = advance(client, pending, first)
    assert second["processing"]["processed_rows"] == 4
    assert second["processing"]["stage_elapsed_seconds"] == 20.0
    assert second["processing"]["stage_timed_rows"] == 2


def test_saved_progress_pause_resume_and_final_validation_are_real(
    client: TestClient,
    db_session: Session,
    pending: dict,
) -> None:
    run = pending["latest_run"]
    assert run["processing"]["stage"] == "preparing"
    prepared = advance(client, pending, run)
    first = advance(client, pending, prepared)
    assert first["processing"]["processed_rows"] == 2
    assert first["processing"]["validated_rows"] == 0
    assert first["processing"]["last_row_number"] == 3
    with Session(db_session.get_bind()) as other:
        assert other.query(CorrectionTarget).count() == 2
        assert (
            other.query(MatchCandidate).count()
            == other.query(CorrectionCandidateEvidence).count()
            == 4
        )
    original_ids = [item.id for item in db_session.query(MatchCandidate).all()]
    paused = client.post(path(pending) + "/pause", json={"run_id": run["id"]}).json()
    assert paused["processing"]["state"] == "paused"
    assert (
        client.post(
            path(pending) + "/advance",
            json={"run_id": run["id"], "revision": first["processing"]["revision"]},
        ).status_code
        == 409
    )
    resumed = client.post(path(pending) + "/resume", json={"run_id": run["id"]}).json()
    next_part = advance(client, pending, resumed)
    assert next_part["processing"]["processed_rows"] == 4
    matched = advance(client, pending, next_part)
    assert matched["processing"]["stage"] == "validating"
    validated = advance(client, pending, matched)
    assert validated["processing"]["validated_rows"] == 2
    assert client.get(path(pending)).json()["current_generation"] == 0
    validated = advance(client, pending, validated)
    assert validated["processing"]["validated_rows"] == 4
    validated = advance(client, pending, validated)
    assert validated["processing"]["stage"] == "publishing"
    assert validated["processing"]["validated_rows"] == 5
    assert client.get(path(pending)).json()["current_generation"] == 0
    ready = advance(client, pending, validated)
    assert ready["status"] == "completed" and ready["processing"]["state"] == "ready"
    assert client.get(path(pending)).json()["current_generation"] == 1
    assert db_session.query(CorrectionTarget).count() == 5
    assert (
        db_session.query(MatchCandidate).count()
        == db_session.query(CorrectionCandidateEvidence).count()
        == 10
    )
    assert [
        item.id
        for item in db_session.query(MatchCandidate)
        .order_by(MatchCandidate.id)
        .limit(4)
    ] == original_ids


def test_failed_chunk_does_not_erase_previous_saves_or_duplicate_candidates(
    client: TestClient,
    db_session: Session,
    pending: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = advance(client, pending, pending["latest_run"])
    saved = advance(client, pending, prepared)
    original = SearchWriter.flush

    def interrupt(writer: SearchWriter) -> None:
        original(writer)
        raise RuntimeError("Interrupted after inserts but before commit")

    with monkeypatch.context() as patch:
        patch.setattr(SearchWriter, "flush", interrupt)
        failed = client.post(
            path(pending) + "/advance",
            json={
                "run_id": saved["id"],
                "revision": saved["processing"]["revision"],
                "chunk_size": 2,
            },
        )
    assert failed.status_code == 500
    stored = client.get(path(pending)).json()["latest_run"]
    assert stored["processing"]["state"] == "failed"
    assert (
        stored["processing"]["last_source_id"] == saved["processing"]["last_source_id"]
    )
    assert stored["processing"]["processed_rows"] == 2
    assert db_session.query(CorrectionTarget).count() == 2
    assert db_session.query(MatchCandidate).count() == 4
    resumed = client.post(
        path(pending) + "/resume", json={"run_id": saved["id"]}
    ).json()
    ready = finish(client, pending, resumed)
    assert (
        ready["processing"]["processed_rows"]
        == ready["processing"]["validated_rows"]
        == 5
    )
    assert db_session.query(MatchCandidate).count() == 10


def test_validation_detects_missing_candidate_evidence(
    client: TestClient, db_session: Session, pending: dict
) -> None:
    run = pending["latest_run"]
    while run["processing"]["stage"] != "validating":
        run = advance(client, pending, run)
    db_session.delete(db_session.query(CorrectionCandidateEvidence).first())
    db_session.commit()
    response = client.post(
        path(pending) + "/advance",
        json={
            "run_id": run["id"],
            "revision": run["processing"]["revision"],
            "chunk_size": 2,
        },
    )
    assert response.status_code == 500
    info = client.get(path(pending)).json()
    assert info["current_generation"] == 0
    assert info["latest_run"]["processing"]["validated_rows"] == 0
    assert db_session.query(CorrectionTarget).count() == 5


def test_progress_migration_preserves_legacy_runs() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE matching_runs (id INTEGER PRIMARY KEY, generation INTEGER)"
            )
        )
        connection.execute(text("INSERT INTO matching_runs VALUES (1, 3)"))
        upgrade_correction_progress(connection)
        upgrade_correction_progress(connection)
        assert connection.execute(
            text("SELECT generation, processing FROM matching_runs")
        ).one() == (3, None)
    engine.dispose()


@pytest.mark.parametrize("state", ["running", "paused", "failed"])
def test_committed_partial_results_are_readable_but_not_published(
    client: TestClient, db_session: Session, pending: dict, state: str
) -> None:
    prepared = advance(client, pending, pending["latest_run"])
    saved = advance(client, pending, prepared)
    if state == "paused":
        client.post(path(pending) + "/pause", json={"run_id": saved["id"]})
    elif state == "failed":
        from app.models.matching import MatchingRun, ProcessStatus

        run = db_session.get(MatchingRun, saved["id"])
        run.status = ProcessStatus.FAILED
        run.processing = {**run.processing, "state": "failed"}
        db_session.commit()
    scope = {"process_id": pending["process_id"]}
    for version in ({}, {"generation": saved["generation"]}):
        params = {**scope, **version}
        summary = client.get("/corrections/idpel_kosong/summary", params=params)
        assert summary.status_code == 200, summary.json()
        assert summary.json()["matched"] == 2
        assert summary.json()["not_checked"] == 3
        rows = client.get("/corrections/idpel_kosong/records", params=params).json()
        assert [row["search_status"] for row in rows["items"]] == [
            "matched",
            "matched",
            "not_checked",
            "not_checked",
            "not_checked",
        ]
        filtered = client.get(
            "/corrections/idpel_kosong/records",
            params={**params, "status": "not_checked"},
        ).json()
        assert filtered["total"] == 3
        detail = client.get(
            f"/corrections/idpel_kosong/records/{rows['items'][0]['id']}",
            params=params,
        )
        assert detail.status_code == 200, detail.json()
        assert detail.json()["search_status"] == "matched"
        assert detail.json()["candidates_total"] == 2
        assert all(item["observations"] for item in detail.json()["candidates"])
    assert client.get(path(pending)).json()["current_generation"] == 0
    process = db_session.get(ReconciliationProcess, pending["process_id"])
    assert selected_run(db_session, process, None) is None
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as rejected:
        selected_run(db_session, process, saved["generation"])
    assert rejected.value.status_code == 409


def test_partial_retry_uses_its_own_results_and_keeps_completed_history(
    client: TestClient, pending: dict
) -> None:
    completed = finish(client, pending, pending["latest_run"])
    retried = client.post(
        path(pending) + "/retry",
        json={
            "latest_run_id": completed["id"],
            "radius_meters": 10,
            "request_key": "partial_read_retry",
            "actor": "Petugas",
            "incremental": True,
        },
    )
    assert retried.status_code == 200, retried.json()
    prepared = advance(client, pending, retried.json()["latest_run"])
    saved = advance(client, pending, prepared)
    summary_path = "/corrections/idpel_kosong/summary"
    current = client.get(
        summary_path, params={"process_id": pending["process_id"]}
    ).json()
    previous = client.get(
        summary_path, params={"process_id": pending["process_id"], "generation": 1}
    ).json()
    assert current["generation"] == saved["generation"] == 2
    assert current["matched"] == 2 and current["not_checked"] == 3
    assert previous["generation"] == 1
    assert previous["matched"] == 5 and previous["not_checked"] == 0
    assert client.get(path(pending)).json()["current_generation"] == 1
