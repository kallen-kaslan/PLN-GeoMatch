"""Bounded preparation, cache reuse, source fidelity, and crash-safe checkpoints."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session

from app.master_preparation_schema import upgrade_master_preparation
from app.models.master_sisa import (
    MasterPreparation,
    MasterPreparationIdentity,
    MasterSisaRecord,
    MasterSnapshot,
)
from app.models.matching import ReconciliationProcess
from app.models.upload import DatasetType, SourceRecord, UploadBatch
from app.modules.spatial import master_preparation as preparation
from app.modules.spatial.master_builder import build_combined_master
from app.modules.spatial.master_evidence import candidate_observations
from app.modules.spatial.preparation import (
    process_master_sisa_exclusion,
    resolve_master_snapshot,
)
from tests.test_corrections import upload


def start(client: TestClient, review_id: int, key: str = "prepare_request_1") -> dict:
    target = upload(client, "idpel_kosong", "NAMA,LAT,LON\nTarget,-6.2,106.8\n")
    response = client.post(
        "/corrections/idpel_kosong/checks",
        json={
            "batch_id": target,
            "pdpj_review_id": review_id,
            "radius_meters": 100,
            "actor": "Petugas",
            "request_key": key,
            "incremental": True,
        },
    )
    assert response.status_code == 200, response.json()
    return response.json()


def advance(client: TestClient, check: dict, run: dict) -> dict:
    response = client.post(
        f"/corrections/idpel_kosong/checks/{check['process_id']}/advance",
        json={
            "run_id": run["id"],
            "revision": run["processing"]["revision"],
            "chunk_size": 2,
        },
    )
    assert response.status_code == 200, response.json()
    return response.json()


def finish_preparation(
    client: TestClient, check: dict, run: dict | None = None
) -> dict:
    value = run or check["latest_run"]
    for _ in range(150):
        if value["processing"]["stage"] != "preparing":
            return value
        value = advance(client, check, value)
    pytest.fail("Preparation did not finish")


def approved_review(client: TestClient) -> dict:
    batch = upload(client, "pdpj", "IDPEL,LAT,LON\n001,-6.2,106.8\n")
    review = client.post("/pdpj/reviews", json={"batch_id": batch}).json()
    response = client.post(
        f"/pdpj/reviews/{review['id']}/complete",
        json={"revision": review["revision"], "actor": "Petugas"},
    )
    assert response.status_code == 200
    return review


def test_reads_cached_normalization_in_bounded_committed_chunks(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = "IDPEL,NAMA,LAT,LON\n001,PDPJ,-6.2,106.8\n" + "".join(
        f"{101 + i % 50:03},Sumber,-6.2,106.8\n" for i in range(5001)
    )
    upload(client, "dil", content)
    review = approved_review(client)
    check = start(client, review["id"])
    statements: list[str] = []

    def observe(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("SELECT source_records"):
            statements.append(statement)

    event.listen(db_session.get_bind(), "before_cursor_execute", observe)
    try:
        with monkeypatch.context() as patch:
            patch.setattr(
                preparation,
                "extract_standard_fields",
                Mock(
                    side_effect=AssertionError(
                        "Cached rows must not be normalized again"
                    )
                ),
            )
            first = advance(client, check, check["latest_run"])
    finally:
        event.remove(db_session.get_bind(), "before_cursor_execute", observe)
    progress = first["processing"]["preparation"]
    assert progress["phase"] == "reading"
    assert progress["source_rows"] == progress["cached_rows"] == 2000
    assert progress["source_total"] == 5002
    assert statements and not any("source_records.data " in sql for sql in statements)
    assert db_session.query(MasterPreparationIdentity).count() == 51
    prepared = db_session.get(MasterPreparation, progress["id"])
    assert not db_session.get(MasterSnapshot, prepared.snapshot_id).ready
    assert client.get("/process/master-snapshots").json() == []
    with pytest.raises(ValueError):
        resolve_master_snapshot(db_session, prepared.snapshot_id)
    paused = client.post(
        f"/corrections/idpel_kosong/checks/{check['process_id']}/pause",
        json={"run_id": first["id"]},
    ).json()
    assert paused["processing"]["preparation"] == progress
    resumed = client.post(
        f"/corrections/idpel_kosong/checks/{check['process_id']}/resume",
        json={"run_id": first["id"]},
    ).json()
    finished = finish_preparation(client, check, resumed)
    saved = finished["processing"]["preparation"]
    assert saved["source_rows"] == saved["source_total"] == 5002
    assert saved["materialized_rows"] == saved["unique_rows"] == 51
    assert saved["eligible_rows"] == 50
    assert db_session.get(MasterSnapshot, prepared.snapshot_id).ready
    assert (
        db_session.query(SourceRecord)
        .filter_by(batch_id=prepared.master_batch_id)
        .count()
        == 51
    )


def test_matches_legacy_selection_and_preserves_all_observations(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upload(
        client,
        "pascabayar",
        "IDPEL,NAMA,LAT,LON,V_BULAN_REKAP\n001,Lama,-6.2,106.8,202609\n002,-,,,202609\n008,Pasca,-6.2,106.8,202610\n",
    )
    upload(
        client,
        "pascabayar",
        "IDPEL,NAMA,LAT,LON,V_BULAN_REKAP\n001,Terbaru,-6.25,106.85,202610\n",
    )
    upload(
        client,
        "prabayar",
        "IDPEL,NAMA,LAT,LON,V_BULAN_REKAP\n001,Pra lama,-7,107,202608\n008,Pra menang,-6.2,106.8,202610\n",
    )
    upload(
        client,
        "dil",
        "IDPEL,NAMA,LAT,LON,V_BULAN_REKAP\n001,DIL,-8,108,202611\n002,Terisi,-6.3,106.9,202610\n009,Hanya DIL,-6.4,107,202610\n",
    )
    review = approved_review(client)
    check = start(client, review["id"])
    sources = check["source_batches"]
    legacy = build_combined_master(
        db_session, sources["pascabayar"], sources["prabayar"], sources["dil"]
    )
    legacy_rows = {
        row.idpel: row.data
        for row in db_session.query(SourceRecord).filter_by(
            batch_id=legacy["master_batch_id"]
        )
    }
    expected = process_master_sisa_exclusion(
        db_session,
        legacy["master_batch_id"],
        review["batch_id"],
        pdpj_review_id=review["id"],
    )
    monkeypatch.setattr(preparation, "PREPARATION_CHUNK_ROWS", 3)
    finished = finish_preparation(client, check)
    prepared = db_session.get(
        MasterPreparation, finished["processing"]["preparation"]["id"]
    )
    combined = {
        row.idpel: row
        for row in db_session.query(SourceRecord).filter_by(
            batch_id=prepared.master_batch_id
        )
    }
    observations = candidate_observations(
        db_session, {row.id: row.data for row in combined.values()}
    )
    for idpel, row in combined.items():
        assert {
            key: value
            for key, value in row.data.items()
            if key != "source_observation_batches"
        } == {
            key: value
            for key, value in legacy_rows[idpel].items()
            if key != "source_observations"
        }
        assert observations[row.id] == legacy_rows[idpel]["source_observations"]
    fields = (
        "idpel",
        "nama",
        "latitude",
        "longitude",
        "tarif",
        "daya",
        "jenis_layanan",
    )

    def values(snapshot_id):
        return sorted(
            tuple(getattr(row, key) for key in fields)
            for row in db_session.query(MasterSisaRecord).filter_by(
                snapshot_id=snapshot_id
            )
        )

    assert values(prepared.snapshot_id) == values(expected["master_snapshot_id"])
    assert combined["001"].data["nama"] == "Terbaru"
    assert combined["001"].data["lat"] == -6.25
    assert combined["002"].data["nama"] == "Terisi"
    assert combined["002"].data["lat"] == -6.3
    assert combined["008"].data["nama"] == "Pra menang"
    assert "009" in combined


def test_ready_snapshot_is_reused_without_reading_master_again(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upload(client, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n002,-6.2,106.8\n")
    review = approved_review(client)
    first = start(client, review["id"])
    original = finish_preparation(client, first)
    snapshot = db_session.query(MasterPreparation).one().snapshot_id
    count = (
        db_session.query(UploadBatch).filter_by(dataset_type=DatasetType.MASTER).count()
    )
    second = start(client, review["id"], "prepare_request_2")
    monkeypatch.setattr(
        preparation,
        "read_source_chunk",
        Mock(side_effect=AssertionError("A ready cache must not reread sources")),
    )
    reused = finish_preparation(client, second)
    assert reused["processing"]["preparation"]["reused"] is True
    assert (
        client.get(f"/corrections/idpel_kosong/checks/{second['process_id']}").json()[
            "master_snapshot_id"
        ]
        == snapshot
    )
    assert db_session.query(MasterPreparation).count() == 1
    assert (
        db_session.query(UploadBatch).filter_by(dataset_type=DatasetType.MASTER).count()
        == count
    )
    assert original["processing"]["preparation"]["source_rows"] == 2


def test_ready_legacy_snapshot_is_adopted_without_rebuilding(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = upload(client, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n002,-6.2,106.8\n")
    review = approved_review(client)
    old = start(client, review["id"])
    combined = build_combined_master(db_session, [], [], [source])
    saved = process_master_sisa_exclusion(
        db_session,
        combined["master_batch_id"],
        review["batch_id"],
        pdpj_review_id=review["id"],
    )
    previous = db_session.get(ReconciliationProcess, old["process_id"])
    previous.master_snapshot_id = saved["master_snapshot_id"]
    db_session.commit()
    later = start(client, review["id"], "adopt_legacy_request")
    monkeypatch.setattr(
        preparation,
        "read_source_chunk",
        Mock(
            side_effect=AssertionError(
                "A compatible legacy snapshot must not be rebuilt"
            )
        ),
    )
    result = finish_preparation(client, later)
    assert result["processing"]["preparation"]["reused"] is True
    info = client.get(f"/corrections/idpel_kosong/checks/{later['process_id']}").json()
    assert info["master_snapshot_id"] == saved["master_snapshot_id"]
    assert db_session.query(MasterPreparation).count() == 1


def test_failure_rolls_back_only_active_preparation_and_can_resume(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upload(
        client,
        "dil",
        "IDPEL,LAT,LON\n" + "".join(f"{i:03},-6.2,106.8\n" for i in range(1, 15)),
    )
    review = approved_review(client)
    monkeypatch.setattr(preparation, "PREPARATION_CHUNK_ROWS", 3)
    check = start(client, review["id"])
    first = advance(client, check, check["latest_run"])
    before = first["processing"]["preparation"]
    original = preparation.read_source_chunk

    def interrupted(*args):
        original(*args)
        raise RuntimeError("Interrupted after reading and staging identities")

    with monkeypatch.context() as patch:
        patch.setattr(preparation, "read_source_chunk", interrupted)
        response = client.post(
            f"/corrections/idpel_kosong/checks/{check['process_id']}/advance",
            json={"run_id": first["id"], "revision": first["processing"]["revision"]},
        )
    assert response.status_code == 500
    stored = client.get(
        f"/corrections/idpel_kosong/checks/{check['process_id']}"
    ).json()["latest_run"]
    assert stored["processing"]["preparation"] == before
    assert db_session.query(MasterPreparationIdentity).count() == 3
    resumed = client.post(
        f"/corrections/idpel_kosong/checks/{check['process_id']}/resume",
        json={"run_id": first["id"]},
    ).json()
    result = finish_preparation(client, check, resumed)
    assert result["processing"]["preparation"]["source_rows"] == 14
    assert result["processing"]["preparation"]["materialized_rows"] == 14
    assert db_session.query(MasterSisaRecord).count() == 13


def test_materialization_failure_keeps_saved_rows_and_hides_incomplete_snapshot(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upload(
        client,
        "dil",
        "IDPEL,LAT,LON\n" + "".join(f"{i:03},-6.2,106.8\n" for i in range(1, 12)),
    )
    review = approved_review(client)
    monkeypatch.setattr(preparation, "PREPARATION_CHUNK_ROWS", 2)
    check = start(client, review["id"])
    run = check["latest_run"]
    for _ in range(40):
        run = advance(client, check, run)
        saved = run["processing"]["preparation"]
        if saved["phase"] == "materializing" and saved["materialized_rows"] > 0:
            break
    assert saved["phase"] == "materializing"
    prepared = db_session.get(MasterPreparation, saved["id"])
    count = (
        db_session.query(SourceRecord)
        .filter_by(batch_id=prepared.master_batch_id)
        .count()
    )
    original = preparation.materialize_chunk

    def fail_after_write(*args):
        original(*args)
        raise RuntimeError("Interrupted after writing a partial snapshot")

    with monkeypatch.context() as patch:
        patch.setattr(preparation, "materialize_chunk", fail_after_write)
        failed = client.post(
            f"/corrections/idpel_kosong/checks/{check['process_id']}/advance",
            json={"run_id": run["id"], "revision": run["processing"]["revision"]},
        )
    assert failed.status_code == 500
    assert (
        db_session.query(SourceRecord)
        .filter_by(batch_id=prepared.master_batch_id)
        .count()
        == count
    )
    assert client.get("/process/master-snapshots").json() == []
    reloaded = client.get(
        f"/corrections/idpel_kosong/checks/{check['process_id']}"
    ).json()["latest_run"]
    assert reloaded["processing"]["preparation"] == saved
    resumed = client.post(
        f"/corrections/idpel_kosong/checks/{check['process_id']}/resume",
        json={"run_id": run["id"]},
    ).json()
    ready = finish_preparation(client, check, resumed)
    assert ready["processing"]["preparation"]["materialized_rows"] == 11
    assert (
        db_session.query(SourceRecord)
        .filter_by(batch_id=prepared.master_batch_id)
        .count()
        == 11
    )


def test_preparation_schema_is_additive_and_legacy_snapshots_remain_ready() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        for name in ("upload_batches", "pdpj_reviews", "master_snapshots"):
            connection.execute(text(f"CREATE TABLE {name} (id INTEGER PRIMARY KEY)"))
        connection.execute(text("INSERT INTO master_snapshots VALUES (1)"))
        upgrade_master_preparation(connection)
        upgrade_master_preparation(connection)
        assert (
            connection.execute(
                text("SELECT ready FROM master_snapshots WHERE id = 1")
            ).scalar()
            == 1
        )
        assert {
            "master_preparations",
            "master_preparation_identities",
            "master_preparation_excluded",
        } <= set(inspect(connection).get_table_names())
    engine.dispose()
