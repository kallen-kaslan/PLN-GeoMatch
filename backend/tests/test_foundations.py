"""Regression coverage for isolation, source mapping, and retained search history."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.models.master_sisa import MasterSisaRecord
from app.models.matching import MatchCandidate, MatchingRun, ReconciliationProcess
from app.models.upload import BatchStatus, DatasetType, SourceRecord, UploadBatch
from app.modules.spatial.engine import create_matching_run, run_spatial_matching_job
from app.modules.spatial.master_builder import build_combined_master
from app.modules.spatial.pipeline import execute_pipeline, pin_pipeline_sources
from app.modules.spatial.preparation import process_master_sisa_exclusion
from app.modules.upload.normalization import extract_standard_fields, validate_fields


def batch(
    db: Session, kind: DatasetType, rows: list[dict], mapping: dict | None = None
) -> UploadBatch:
    source = UploadBatch(
        filename="fixture.csv",
        dataset_type=kind,
        status=BatchStatus.COMPLETED,
        column_mapping=mapping,
        total_rows=len(rows),
    )
    db.add(source)
    db.flush()
    db.add_all(SourceRecord(batch_id=source.id, data=row) for row in rows)
    db.commit()
    return source


def setup_matching(db: Session) -> tuple[int, int]:
    master = batch(
        db,
        DatasetType.PASCABAYAR,
        [
            {"idpel": "001234567890", "latitude": -6.2, "longitude": 106.8},
            {"idpel": "001234567891", "latitude": -6.2005, "longitude": 106.8},
        ],
    )
    combined = build_combined_master(db, [master.id], [])
    snapshot = process_master_sisa_exclusion(db, combined["master_batch_id"])
    target = batch(
        db, DatasetType.TARGET, [{"nomor_meter": "T1", "lat": -6.2, "lon": 106.8}]
    )
    return snapshot["master_snapshot_id"], target.id


@pytest.mark.parametrize("coordinate", ["NaN", "inf", "-inf", "91", "bad"])
def test_invalid_coordinate_is_reported(coordinate: str) -> None:
    fields = extract_standard_fields({"idpel": "0012", "lat": coordinate, "lon": 106.8})
    # A literal NaN is treated as an empty cell; other malformed values are errors.
    if coordinate == "NaN":
        assert fields["lat"] is None
    else:
        assert {"field": "lat", "code": "koordinat_tidak_valid"} in fields[
            "validation_errors"
        ]


def test_explicit_empty_mapping_does_not_use_unselected_alias() -> None:
    fields = extract_standard_fields(
        {"selected": "", "idpel": "9999", "x": "106,8", "y": "-6,2"},
        {"idpel": "selected"},
    )
    assert fields["idpel"] is None
    assert fields["lat"] == -6.2
    assert fields["lon"] == 106.8
    assert validate_fields(fields, DatasetType.PDPJ)


def test_master_keeps_latest_identity_without_coordinates(db_session: Session) -> None:
    source = batch(
        db_session,
        DatasetType.PASCABAYAR,
        [
            {"idpel": "0012", "lat": -6.2, "lon": 106.8, "periode": "2026-01"},
            {"idpel": "0012", "periode": "2026-02"},
            {"idpel": "0013", "lat": -6.2, "lon": 106.8},
        ],
    )
    result = build_combined_master(db_session, [source.id], [])
    assert result["total_master_clean"] == 2
    assert result["incomplete_coordinates"] == 1
    snapshot = process_master_sisa_exclusion(db_session, result["master_batch_id"])
    retained = (
        db_session.query(MasterSisaRecord)
        .filter(
            MasterSisaRecord.snapshot_id == snapshot["master_snapshot_id"],
            MasterSisaRecord.idpel == "0012",
        )
        .one()
    )
    assert retained.latitude is None and retained.longitude is None
    target = batch(db_session, DatasetType.TARGET, [{"lat": -6.2, "lon": 106.8}])
    run = run_spatial_matching_job(db_session, "incomplete", target.id)
    candidates = (
        db_session.query(MatchCandidate)
        .filter(MatchCandidate.process_id == run["process_id"])
        .all()
    )
    assert [candidate.candidate_idpel for candidate in candidates] == ["0013"]


def test_mapping_validation_preserves_raw_and_counts_real_errors(
    client: TestClient, db_session: Session
) -> None:
    uploaded = client.post(
        "/upload/",
        data={"dataset_type": "pascabayar"},
        files={
            "file": (
                "custom.csv",
                b"CUSTOM,Y_POS,X_POS\n001234567890,,\n001234567891,invalid,106.8\n",
                "text/csv",
            )
        },
    )
    assert uploaded.status_code == 200
    batch_id = uploaded.json()["id"]
    result = client.post(
        "/upload/confirm-mapping",
        json={
            "batch_id": batch_id,
            "column_mapping": {
                "idpel": "CUSTOM",
                "latitude": "Y_POS",
                "longitude": "X_POS",
            },
        },
    )
    assert result.status_code == 200
    assert result.json()["valid_rows"] == 1
    assert result.json()["error_rows"] == 1
    records = (
        db_session.query(SourceRecord)
        .filter(SourceRecord.batch_id == batch_id)
        .order_by(SourceRecord.id)
        .all()
    )
    assert records[0].idpel == "001234567890"
    assert records[0].is_valid
    assert records[0].data["CUSTOM"] == "001234567890"
    assert "idpel" not in records[0].data
    assert records[1].validation_errors == [
        {"field": "lat", "code": "koordinat_tidak_valid"}
    ]
    assert "001234567891" not in str(result.json()["errors"])


def test_unknown_mapping_column_is_rejected(
    client: TestClient, db_session: Session
) -> None:
    source = batch(db_session, DatasetType.PDPJ, [{"idpel": "0012"}])
    response = client.post(
        "/upload/confirm-mapping",
        json={"batch_id": source.id, "column_mapping": {"idpel": "MISSING"}},
    )
    assert response.status_code == 422


def test_pdpj_and_target_custom_mappings_reach_matching(db_session: Session) -> None:
    source = batch(
        db_session,
        DatasetType.PASCABAYAR,
        [
            {"idpel": "0012", "lat": -6.2, "lon": 106.8},
            {"idpel": "0013", "lat": -6.2, "lon": 106.8},
        ],
    )
    combined = build_combined_master(db_session, [source.id], [])
    pdpj = batch(
        db_session,
        DatasetType.PDPJ,
        [{"C": "0012", "V": "true"}],
        {"idpelanggan": "C", "verif": "V"},
    )
    first = process_master_sisa_exclusion(
        db_session, combined["master_batch_id"], pdpj.id
    )
    second = process_master_sisa_exclusion(db_session, combined["master_batch_id"])
    assert first["total_master_sisa"] == 1 and second["total_master_sisa"] == 2
    assert db_session.query(MasterSisaRecord).count() == 3
    target = batch(
        db_session,
        DatasetType.TARGET,
        [{"R": "CUSTOM-TARGET", "A": -6.2, "B": 106.8}],
        {"nomor_meter": "R", "lat": "A", "lon": "B"},
    )
    result = run_spatial_matching_job(
        db_session, "mapped", target.id, master_snapshot_id=first["master_snapshot_id"]
    )
    candidate = (
        db_session.query(MatchCandidate)
        .filter(MatchCandidate.process_id == result["process_id"])
        .one()
    )
    assert (
        candidate.target_ref == "CUSTOM-TARGET" and candidate.candidate_idpel == "0013"
    )


def test_queued_matching_keeps_original_snapshot(db_session: Session) -> None:
    snapshot_id, target_id = setup_matching(db_session)
    process = ReconciliationProcess(
        process_name="pinned", master_snapshot_id=snapshot_id, target_batch_id=target_id
    )
    db_session.add(process)
    db_session.flush()
    run = create_matching_run(db_session, process, 100, 5)
    db_session.commit()
    later_master = batch(
        db_session, DatasetType.MASTER, [{"idpel": "9999", "lat": -6.2, "lon": 106.8}]
    )
    process_master_sisa_exclusion(db_session, later_master.id)
    run_spatial_matching_job(
        db_session, "pinned", target_id, process_id=process.id, run_id=run.id
    )
    assert {c.candidate_idpel for c in db_session.query(MatchCandidate).all()} == {
        "001234567890",
        "001234567891",
    }
    assert process.master_snapshot_id == snapshot_id


def test_rerun_preserves_decisions_and_retry_is_idempotent(db_session: Session) -> None:
    snapshot_id, target_id = setup_matching(db_session)
    first = run_spatial_matching_job(
        db_session, "history", target_id, master_snapshot_id=snapshot_id
    )
    old = (
        db_session.query(MatchCandidate)
        .filter(MatchCandidate.generation == 1)
        .order_by(MatchCandidate.id)
        .first()
    )
    old.is_accepted = 1
    old_id = old.id
    db_session.commit()
    second = run_spatial_matching_job(
        db_session,
        "history",
        target_id,
        process_id=first["process_id"],
        radius_meters=10,
    )
    assert second["generation"] == 2
    assert db_session.query(MatchCandidate).count() == 3
    db_session.refresh(old)
    assert old.id == old_id and old.is_accepted == 1
    retried = run_spatial_matching_job(
        db_session,
        "history",
        target_id,
        process_id=first["process_id"],
        run_id=second["run_id"],
    )
    assert retried == second
    assert db_session.query(MatchCandidate).count() == 3
    assert db_session.query(MatchingRun).count() == 2


def test_missing_and_empty_processes_never_fallback(
    client: TestClient, db_session: Session
) -> None:
    _, target_id = setup_matching(db_session)
    run_spatial_matching_job(db_session, "populated", target_id)
    empty = ReconciliationProcess(process_name="empty")
    db_session.add(empty)
    db_session.commit()
    response = client.get(f"/process/{empty.id}/candidates")
    assert response.status_code == 200
    assert response.json()["items"] == [] and response.json()["process_id"] == empty.id
    summary = client.get(f"/process/{empty.id}/summary").json()
    assert summary["process_id"] == empty.id and summary["total_candidates"] == 0
    for endpoint in ("candidates", "summary", "export", "runs"):
        assert client.get(f"/process/99999/{endpoint}").status_code == 404
    filtered = client.get("/process/1/candidates?idpel_filters=kosong")
    assert filtered.json()["items"] == []


def test_history_api_and_export_stay_in_requested_generation(
    client: TestClient, db_session: Session
) -> None:
    _, target_id = setup_matching(db_session)
    first = run_spatial_matching_job(db_session, "history", target_id)
    old = db_session.query(MatchCandidate).order_by(MatchCandidate.id).first()
    old.is_accepted = 1
    db_session.commit()
    run_spatial_matching_job(
        db_session,
        "history",
        target_id,
        process_id=first["process_id"],
        radius_meters=10,
    )
    process_id = first["process_id"]
    current = client.get(f"/process/{process_id}/candidates").json()
    historic = client.get(f"/process/{process_id}/candidates?generation=1").json()
    assert current["generation"] == 2 and current["total"] == 1
    assert historic["total"] == 2 and historic["items"][0]["is_accepted"] == 1
    assert len(client.get(f"/process/{process_id}/runs").json()) == 2
    assert (
        client.get(f"/process/{process_id}/summary?generation=1").json()[
            "radius_meters"
        ]
        == 100
    )
    assert (
        client.post(
            f"/process/candidates/{old.id}/decision", json={"is_accepted": 0}
        ).status_code
        == 409
    )
    assert (
        client.get(f"/process/{process_id}/candidates?generation=999").status_code
        == 404
    )
    assert len(client.get(f"/process/{process_id}/export").text.splitlines()) == 2
    assert (
        len(client.get(f"/process/{process_id}/export?generation=1").text.splitlines())
        == 3
    )


def test_failed_attempt_keeps_previous_results(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.modules.spatial import engine

    _, target_id = setup_matching(db_session)
    first = run_spatial_matching_job(db_session, "history", target_id)
    monkeypatch.setattr(
        engine,
        "calculate_haversine_distance",
        Mock(side_effect=RuntimeError("failure")),
    )
    with pytest.raises(RuntimeError):
        run_spatial_matching_job(
            db_session, "history", target_id, process_id=first["process_id"]
        )
    db_session.rollback()
    assert (
        db_session.get(ReconciliationProcess, first["process_id"]).current_generation
        == 1
    )
    assert db_session.query(MatchCandidate).count() == 2


def test_pipeline_pins_sources_and_reuses_snapshot(db_session: Session) -> None:
    source = batch(
        db_session,
        DatasetType.PASCABAYAR,
        [{"idpel": "0012", "lat": -6.2, "lon": 106.8}],
    )
    original = batch(db_session, DatasetType.TARGET, [{"lat": -6.2, "lon": 106.8}])
    sources = pin_pipeline_sources(db_session, source.id, None, None, original.id)
    process = ReconciliationProcess(
        process_name="pipeline", source_batches=sources, radius_meters=100
    )
    db_session.add(process)
    db_session.commit()
    batch(db_session, DatasetType.TARGET, [{"lat": -8, "lon": 110}])
    first = execute_pipeline(db_session, process.id)
    snapshot_id = process.master_snapshot_id
    assert process.target_batch_id == original.id
    assert execute_pipeline(db_session, process.id) == first
    assert (
        process.master_snapshot_id == snapshot_id
        and db_session.query(MatchingRun).count() == 1
    )


def test_mapping_cannot_change_after_snapshot_is_used(
    client: TestClient, db_session: Session
) -> None:
    snapshot_id, _ = setup_matching(db_session)
    from app.models.master_sisa import MasterSnapshot

    snapshot = db_session.get(MasterSnapshot, snapshot_id)
    assert (
        client.post(
            "/upload/confirm-mapping",
            json={
                "batch_id": snapshot.master_batch_id,
                "column_mapping": {"idpel": "idpel"},
            },
        ).status_code
        == 409
    )


def test_matching_api_reserves_snapshot_and_rerun_keeps_history(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.modules.spatial import router

    snapshot_id, target_id = setup_matching(db_session)
    monkeypatch.setattr(settings, "ALLOW_SYNC_FALLBACK", True)
    monkeypatch.setattr(
        router.execute_matching_task, "delay", Mock(side_effect=RuntimeError("offline"))
    )
    response = client.post(
        "/process/run-matching",
        json={
            "process_name": "api",
            "target_batch_id": target_id,
            "master_snapshot_id": snapshot_id,
        },
    )
    assert response.status_code == 200 and response.json()["status"] == "completed"
    process_id = response.json()["process_id"]
    again = client.post(f"/process/{process_id}/rerun", json={"radius_meters": 10})
    assert again.status_code == 200 and again.json()["generation"] == 2
    assert db_session.query(MatchCandidate).count() == 3
    assert len(client.get("/process/master-snapshots").json()) == 1


def test_invalid_explicit_sources_are_not_substituted(
    client: TestClient, db_session: Session
) -> None:
    _, target_id = setup_matching(db_session)
    assert (
        client.post(
            "/process/run-matching",
            json={
                "process_name": "bad",
                "target_batch_id": target_id,
                "master_snapshot_id": 999,
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/upload/batch-process", json={"pascabayar_batch_id": 999}
        ).status_code
        == 422
    )
    assert db_session.query(ReconciliationProcess).count() == 0


def test_pipeline_without_pdpj_still_uses_own_snapshot(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.modules.upload import router

    source = batch(
        db_session,
        DatasetType.PASCABAYAR,
        [{"idpel": "0012", "lat": -6.2, "lon": 106.8}],
    )
    target = batch(db_session, DatasetType.TARGET, [{"lat": -6.2, "lon": 106.8}])
    monkeypatch.setattr(settings, "ALLOW_SYNC_FALLBACK", True)
    monkeypatch.setattr(
        router.execute_batch_reconciliation_pipeline,
        "delay",
        Mock(side_effect=RuntimeError("offline")),
    )
    response = client.post(
        "/upload/batch-process",
        json={"pascabayar_batch_id": source.id, "target_batch_id": target.id},
    )
    assert response.status_code == 200
    assert response.json()["matching_summary"]["matched_targets"] == 1
    assert client.post(f"/upload/auto-pipeline?batch_id={target.id}").status_code == 200


@pytest.mark.parametrize(
    "endpoint", ["/history/processes/1", "/history/processes", "/upload/reset"]
)
def test_cleanup_handles_new_relations(
    client: TestClient, db_session: Session, endpoint: str
) -> None:
    _, target_id = setup_matching(db_session)
    run_spatial_matching_job(db_session, "cleanup", target_id)
    response = (
        client.post(endpoint)
        if endpoint == "/upload/reset"
        else client.delete(endpoint)
    )
    assert response.status_code == 200
    assert db_session.query(MatchingRun).count() == 0
    assert db_session.query(MatchCandidate).count() == 0


def test_upload_to_export_flow(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.modules.spatial import router

    def upload(kind: str, content: bytes, mapping: dict) -> int:
        response = client.post(
            "/upload/",
            data={"dataset_type": kind},
            files={"file": ("flow.csv", content, "text/csv")},
        )
        assert response.status_code == 200
        source_id = response.json()["id"]
        checked = client.post(
            "/upload/confirm-mapping",
            json={"batch_id": source_id, "column_mapping": mapping},
        )
        assert checked.status_code == 200 and checked.json()["error_rows"] == 0
        return source_id

    master_id = upload(
        "pascabayar",
        b"C,A,B\n001234567890,-6.2,106.8\n001234567891,,\n",
        {"idpel": "C", "lat": "A", "lon": "B"},
    )
    pdpj_id = upload("pdpj", b"C\n001234567891\n", {"idpelanggan": "C"})
    # An incomplete PDPJ identity now needs an explicit validation decision before
    # it can be used for master exclusion. Its IDPEL remains protected afterwards.
    validation = client.post("/pdpj/reviews", json={"batch_id": pdpj_id}).json()
    row = client.get(f"/pdpj/reviews/{validation['id']}/rows").json()["items"][0]
    decision = client.post(
        f"/pdpj/reviews/{validation['id']}/rows/{row['id']}/decision",
        json={
            "revision": validation["revision"],
            "actor": "Petugas Uji",
            "action": "exception",
            "reason": "Identitas sudah diperiksa; koordinat menunggu survei",
        },
    )
    assert decision.status_code == 200
    assert (
        client.post(
            f"/pdpj/reviews/{validation['id']}/complete",
            json={"revision": decision.json()["revision"], "actor": "Petugas Uji"},
        ).status_code
        == 200
    )
    target_id = upload(
        "target",
        b"R,A,B\nSURVEY-1,-6.2,106.8\n",
        {"nomor_meter": "R", "lat": "A", "lon": "B"},
    )
    built = client.post(
        "/process/build-master",
        json={"pascabayar_batch_ids": [master_id], "prabayar_batch_ids": []},
    )
    assert built.status_code == 200 and built.json()["incomplete_coordinates"] == 1
    prepared = client.post(
        "/process/prepare-master-sisa",
        json={
            "master_batch_id": built.json()["master_batch_id"],
            "pdpj_batch_id": pdpj_id,
        },
    )
    assert (
        prepared.status_code == 200 and prepared.json()["total_excluded_by_pdpj"] == 1
    )
    monkeypatch.setattr(settings, "ALLOW_SYNC_FALLBACK", True)
    monkeypatch.setattr(
        router.execute_matching_task, "delay", Mock(side_effect=RuntimeError("offline"))
    )
    result = client.post(
        "/process/run-matching",
        json={
            "process_name": "end to end",
            "target_batch_id": target_id,
            "master_snapshot_id": prepared.json()["master_snapshot_id"],
        },
    )
    assert result.status_code == 200 and result.json()["status"] == "completed"
    process_id = result.json()["process_id"]
    candidate = client.get(f"/process/{process_id}/candidates").json()["items"][0]
    assert candidate["candidate_idpel"] == "001234567890"
    assert candidate["target_ref"] == "SURVEY-1"
    assert (
        client.post(
            f"/process/candidates/{candidate['id']}/decision", json={"is_accepted": 1}
        ).status_code
        == 200
    )
    assert client.post(f"/process/{process_id}/finalize-review").status_code == 200
    assert client.get(f"/process/{process_id}/summary").json()["valid_count"] == 1
    assert "001234567890" in client.get(f"/process/{process_id}/export").text


def test_queued_pipeline_mapping_is_frozen(
    client: TestClient, db_session: Session
) -> None:
    source = batch(db_session, DatasetType.PASCABAYAR, [{"idpel": "0012"}])
    process = ReconciliationProcess(
        process_name="queued",
        source_batches=pin_pipeline_sources(db_session, source.id, None, None, None),
    )
    db_session.add(process)
    db_session.commit()
    response = client.post(
        "/upload/confirm-mapping",
        json={"batch_id": source.id, "column_mapping": {"idpel": "idpel"}},
    )
    assert response.status_code == 409
