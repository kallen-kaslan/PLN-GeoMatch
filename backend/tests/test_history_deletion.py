"""Foreign-key-safe scoped history removal with rollback and active-work guards."""

import sqlite3
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models.correction import (
    CorrectionAttempt,
    CorrectionCandidateEvidence,
    CorrectionCheck,
    CorrectionTarget,
)
from app.models.correction_decision import CorrectionDecision
from app.models.master_sisa import (
    CorrectionMasterObservation,
    CorrectionObservationCatalog,
    MasterPreparation,
    MasterPreparationExcluded,
    MasterPreparationIdentity,
    MasterSisaRecord,
    MasterSnapshot,
)
from app.models.matching import (
    MatchCandidate,
    MatchingRun,
    ProcessStatus,
    ReconciliationProcess,
)
from app.models.pdpj import PdpjReview, PdpjRow
from app.models.upload import SourceRecord, UploadBatch
from app.processing_activity import activity_lock
from tests.test_corrections import reference, upload  # noqa: F401

SOURCE_MODELS = (
    UploadBatch,
    SourceRecord,
    PdpjReview,
    PdpjRow,
    MasterSnapshot,
    MasterSisaRecord,
    MasterPreparation,
    MasterPreparationIdentity,
    MasterPreparationExcluded,
    CorrectionObservationCatalog,
    CorrectionMasterObservation,
)
HISTORY_MODELS = (
    CorrectionDecision,
    CorrectionCandidateEvidence,
    CorrectionTarget,
    CorrectionAttempt,
    MatchCandidate,
    MatchingRun,
    CorrectionCheck,
    ReconciliationProcess,
)


def counts(db: Session, models: tuple) -> dict[str, int]:
    return {model.__tablename__: db.query(model).count() for model in models}


def finish(client: TestClient, kind: str, check: dict) -> dict:
    run = check["latest_run"]
    for _ in range(20):
        if run["status"] == "completed":
            return run
        response = client.post(
            f"/corrections/{kind}/checks/{check['process_id']}/advance",
            json={
                "run_id": run["id"],
                "revision": run["processing"]["revision"],
                "chunk_size": 2,
            },
        )
        assert response.status_code == 200, response.json()
        run = response.json()
    pytest.fail("Correction processing did not finish")


@pytest.fixture(params=["idpel_kosong", "idpel_tidak_ketemu"])
def histories(client: TestClient, request: pytest.FixtureRequest) -> dict:
    review_id = request.getfixturevalue("reference")
    kind = request.param
    identity = "" if kind == "idpel_kosong" else "999"
    batch = upload(client, kind, f"IDPEL,LAT,LON\n{identity},-6.2,106.8\n")
    checks = []
    for number in (1, 2):
        response = client.post(
            f"/corrections/{kind}/checks",
            json={
                "batch_id": batch,
                "pdpj_review_id": review_id,
                "radius_meters": 10,
                "actor": "Uji Hapus",
                "request_key": f"delete_check_{number}",
                "incremental": True,
            },
        )
        assert response.status_code == 200, response.json()
        check = response.json()
        run = finish(client, kind, check)
        base = f"/corrections/{kind}/checks/{check['process_id']}"
        record = client.get(
            f"/corrections/{kind}/records", params={"process_id": check["process_id"]}
        ).json()["items"][0]
        detail = client.get(
            f"/corrections/{kind}/records/{record['id']}",
            params={"process_id": check["process_id"]},
        ).json()
        response = client.post(
            base + f"/records/{record['id']}/choice",
            json={
                "generation": 1,
                "expected_revision": 0,
                "candidate_id": detail["candidates"][0]["id"],
                "actor": "Uji Hapus",
                "request_key": f"delete_choice_{number}",
            },
        )
        assert response.status_code == 200, response.json()
        if number == 1:
            response = client.post(
                base + "/retry",
                json={
                    "latest_run_id": run["id"],
                    "radius_meters": 100,
                    "actor": "Uji Hapus",
                    "request_key": "delete_second_generation",
                    "incremental": True,
                },
            )
            assert response.status_code == 200, response.json()
            run = finish(client, kind, response.json())
            # The active decision still references a candidate from generation 1.
            assert (
                client.get(base + f"/records/{record['id']}/choice").json()["current"][
                    "generation"
                ]
                == 1
            )
        checks.append({"id": check["process_id"], "run_id": run["id"], "base": base})
    return {"kind": kind, "checks": checks}


def test_delete_one_process_keeps_other_results_and_shared_sources(
    client: TestClient,
    db_session: Session,
    histories: dict,
) -> None:
    selected, other = histories["checks"]
    before_sources = counts(db_session, SOURCE_MODELS)
    other_candidates = (
        db_session.query(MatchCandidate.id).filter_by(process_id=other["id"]).all()
    )
    assert (
        db_session.query(ReconciliationProcess)
        .filter_by(id=selected["id"])
        .one()
        .master_snapshot_id
        == db_session.query(ReconciliationProcess)
        .filter_by(id=other["id"])
        .one()
        .master_snapshot_id
    )
    response = client.delete(f"/history/processes/{selected['id']}")
    assert response.status_code == 200, response.json()
    assert (
        db_session.query(CorrectionDecision)
        .filter_by(process_id=selected["id"])
        .count()
        == 0
    )
    assert (
        db_session.query(CorrectionAttempt).filter_by(process_id=selected["id"]).count()
        == 0
    )
    assert (
        db_session.query(CorrectionCheck).filter_by(process_id=selected["id"]).count()
        == 0
    )
    assert (
        db_session.query(MatchCandidate).filter_by(process_id=selected["id"]).count()
        == 0
    )
    assert (
        db_session.query(MatchingRun).filter_by(process_id=selected["id"]).count() == 0
    )
    assert (
        db_session.query(ReconciliationProcess).filter_by(id=selected["id"]).count()
        == 0
    )
    assert (
        db_session.query(MatchCandidate.id).filter_by(process_id=other["id"]).all()
        == other_candidates
    )
    assert (
        db_session.query(CorrectionDecision).filter_by(process_id=other["id"]).count()
        == 1
    )
    assert counts(db_session, SOURCE_MODELS) == before_sources
    assert db_session.execute(text("PRAGMA foreign_key_check")).all() == []
    assert client.get(other["base"] + "/results").json()["summary"]["chosen_count"] == 1
    assert client.delete(f"/history/processes/{selected['id']}").status_code == 404


def test_clear_all_removes_correction_and_legacy_history_but_not_sources(
    client: TestClient,
    db_session: Session,
    histories: dict,
) -> None:
    legacy = ReconciliationProcess(
        process_name="Legacy", matching_status=ProcessStatus.COMPLETED
    )
    db_session.add(legacy)
    db_session.flush()
    db_session.add(
        MatchingRun(
            process_id=legacy.id,
            generation=1,
            radius_meters=10,
            status=ProcessStatus.COMPLETED,
        )
    )
    db_session.add(
        MatchCandidate(
            process_id=legacy.id,
            generation=1,
            target_ref="Legacy",
            target_lat=-6.2,
            target_lon=106.8,
            candidate_idpel="002",
            candidate_lat=-6.2,
            candidate_lon=106.8,
            distance_meters=0,
        )
    )
    db_session.commit()
    before = counts(db_session, SOURCE_MODELS)
    response = client.delete("/history/processes")
    assert response.status_code == 200, response.json()
    assert not any(counts(db_session, HISTORY_MODELS).values())
    assert counts(db_session, SOURCE_MODELS) == before
    assert client.get("/history/processes").json() == []
    assert client.delete("/history/processes").status_code == 200


@pytest.mark.parametrize("all_history", [False, True])
def test_database_failure_rolls_back_every_deletion(
    client: TestClient,
    db_session: Session,
    histories: dict,
    all_history: bool,
) -> None:
    before = counts(db_session, HISTORY_MODELS + SOURCE_MODELS)

    def fail_after_deleting_candidates(
        _connection: Any,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        _context: Any,
        _many: bool,
    ) -> None:
        if statement.startswith("DELETE FROM match_candidates"):
            raise OperationalError(
                statement, {}, sqlite3.IntegrityError("Simulated failure")
            )

    event.listen(
        db_session.get_bind(), "after_cursor_execute", fail_after_deleting_candidates
    )
    try:
        endpoint = (
            "/history/processes"
            if all_history
            else f"/history/processes/{histories['checks'][0]['id']}"
        )
        response = client.delete(endpoint)
    finally:
        event.remove(
            db_session.get_bind(),
            "after_cursor_execute",
            fail_after_deleting_candidates,
        )
    assert response.status_code == 500
    assert "DELETE FROM" not in response.json()["detail"]
    assert counts(db_session, HISTORY_MODELS + SOURCE_MODELS) == before


@pytest.mark.parametrize("status", [ProcessStatus.QUEUED, ProcessStatus.RUNNING])
def test_active_history_blocks_clear_all_before_any_deletions(
    client: TestClient,
    db_session: Session,
    histories: dict,
    status: ProcessStatus,
) -> None:
    selected, other = histories["checks"]
    busy = db_session.get(MatchingRun, other["run_id"])
    assert busy is not None
    busy.status = status
    busy.processing = {**(busy.processing or {}), "state": "running"}
    db_session.commit()
    before = counts(db_session, HISTORY_MODELS)
    response = client.delete("/history/processes")
    assert response.status_code == 409, response.json()
    assert counts(db_session, HISTORY_MODELS) == before
    assert client.delete(f"/history/processes/{other['id']}").status_code == 409
    # Work in another process does not prevent deleting the selected idle one.
    assert client.delete(f"/history/processes/{selected['id']}").status_code == 200


@pytest.mark.parametrize("scope", ["correction", "correction:pause"])
def test_active_request_lock_blocks_deletion_even_when_saved_status_is_complete(
    client: TestClient,
    db_session: Session,
    histories: dict,
    scope: str,
) -> None:
    selected = histories["checks"][0]
    before = counts(db_session, HISTORY_MODELS)
    with activity_lock(
        db_session,
        scope,
        selected["run_id"],
        "pausing" if scope.endswith(":pause") else "matching",
    ):
        response = client.delete(f"/history/processes/{selected['id']}")
        assert response.status_code == 409, response.json()
        assert counts(db_session, HISTORY_MODELS) == before
    assert client.delete(f"/history/processes/{selected['id']}").status_code == 200


def test_paused_checkpoint_can_be_deleted_after_active_work_has_finished(
    client: TestClient,
    db_session: Session,
    histories: dict,
) -> None:
    selected = histories["checks"][0]
    run = db_session.get(MatchingRun, selected["run_id"])
    assert run is not None
    run.status = ProcessStatus.RUNNING
    run.processing = {**(run.processing or {}), "state": "paused"}
    db_session.commit()
    assert client.delete(f"/history/processes/{selected['id']}").status_code == 200
