"""Fast imported totals, exact persistent aggregates, and source-aware invalidation."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import create_engine, event, inspect, update
from sqlalchemy.orm import Session

from app.master_summary_schema import upgrade_master_summary
from app.models.master_summary import MasterSummaryCache
from app.models.upload import SourceRecord, UploadBatch
from tests.test_master_catalog import import_master


def source_reads(
    db: Session, work: Callable[[], Response]
) -> tuple[Response, list[tuple[str, Any]]]:
    statements: list[tuple[str, Any]] = []

    def capture(
        _conn: Any,
        _cursor: Any,
        statement: str,
        parameters: Any,
        _context: Any,
        _many: bool,
    ) -> None:
        if statement.lstrip().startswith("SELECT") and "source_records" in statement:
            statements.append((statement, parameters))

    event.listen(db.get_bind(), "before_cursor_execute", capture)
    try:
        response = work()
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", capture)
    return response, statements


@pytest.mark.parametrize("kind", ["prabayar", "pascabayar", "dil"])
def test_fast_totals_do_not_scan_rows_and_exact_counts_survive_session_refresh(
    client: TestClient, db_session: Session, kind: str
) -> None:
    batch = import_master(
        client,
        kind,
        "IDPEL,NAMA,LAT,LON\n001,A,-6.2,106.8\n001,B,,\n002,C,broken,106.8\n003,D,-6.3,106.9\n",
    )
    path = f"/master/{kind}/summary"
    quick, reads = source_reads(
        db_session, lambda: client.get(path, params={"details": False})
    )
    assert quick.status_code == 200
    assert reads == []
    data = quick.json()
    assert (
        data["total_rows"] == 4
        and data["valid_rows"] == 3
        and data["invalid_rows"] == 1
    )
    assert data["incomplete_coordinates"] is None and data["unique_idpels"] is None
    assert data["statistics_ready"] is False
    before = [
        (r.id, r.data, r.normalized_data)
        for r in db_session.query(SourceRecord).filter_by(batch_id=batch)
    ]
    exact = client.get(path).json()
    assert exact["statistics_ready"] is True
    assert exact["incomplete_coordinates"] == 1
    assert exact["unique_idpels"] == 2 and exact["duplicate_observations"] == 1
    assert exact["source_signature"] == data["source_signature"]
    db_session.expunge_all()
    for params in [{}, {"details": False}, {"batch_id": batch}]:
        response, reads = source_reads(
            db_session, lambda params=params: client.get(path, params=params)
        )
        assert response.status_code == 200 and response.json() == exact
        assert reads == []
    assert [
        (r.id, r.data, r.normalized_data)
        for r in db_session.query(SourceRecord).filter_by(batch_id=batch)
    ] == before
    assert db_session.query(MasterSummaryCache).count() == 1


def test_combined_unique_count_deduplicates_files_and_new_upload_only_scans_new_payload(
    client: TestClient, db_session: Session
) -> None:
    first = import_master(client, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n002,,\n")
    import_master(client, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n003,-6.2,106.8\n")
    path = "/master/dil/summary"
    original = client.get(path).json()
    assert original["total_rows"] == 4 and original["unique_idpels"] == 3
    assert (
        original["duplicate_observations"] == 1
        and original["incomplete_coordinates"] == 1
    )
    selected, reads = source_reads(
        db_session,
        lambda: client.get(path, params={"batch_id": first, "details": False}),
    )
    assert selected.json()["total_rows"] == 2
    assert selected.json()["statistics_ready"] is True and reads == []
    added = import_master(
        client, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n004,-6.2,106.8\n"
    )
    quick, reads = source_reads(
        db_session, lambda: client.get(path, params={"details": False})
    )
    assert reads == [] and quick.json()["total_rows"] == 6
    assert quick.json()["source_signature"] != original["source_signature"]
    result, reads = source_reads(db_session, lambda: client.get(path))
    assert result.json()["total_rows"] == 6 and result.json()["unique_idpels"] == 4
    assert result.json()["duplicate_observations"] == 2
    payload_reads = [(sql, values) for sql, values in reads if "normalized_data" in sql]
    assert len(payload_reads) == 1
    assert [v for v in payload_reads[0][1] if isinstance(v, int)] == [added]


def test_pending_and_legacy_metadata_never_manufacture_zero_totals(
    client: TestClient, db_session: Session
) -> None:
    uploaded = client.post(
        "/upload/",
        data={"dataset_type": "dil"},
        files={"file": ("pending.csv", b"IDPEL,LAT,LON\n001,,\n", "text/csv")},
    ).json()
    path = "/master/dil/summary"
    quick = client.get(path, params={"details": False}).json()
    assert quick["total_rows"] == 0 and quick["statistics_ready"] is True
    assert quick["pending_files"] == 1
    assert (
        client.post(
            "/upload/confirm-mapping",
            json={"batch_id": uploaded["id"], "column_mapping": {"idpel": "IDPEL"}},
        ).status_code
        == 200
    )
    db_session.execute(
        update(UploadBatch)
        .where(UploadBatch.id == uploaded["id"])
        .values(total_rows=0, valid_rows=0, error_rows=0)
    )
    db_session.commit()
    quick = client.get(path, params={"details": False}).json()
    assert quick["total_rows"] is None and quick["statistics_ready"] is False
    exact = client.get(path).json()
    assert exact["total_rows"] == exact["valid_rows"] == 1
    assert exact["incomplete_coordinates"] == 1
    assert client.get(path, params={"details": False}).json() == exact


def test_remapping_same_row_counts_invalidates_coordinate_statistics(
    client: TestClient,
) -> None:
    batch = import_master(
        client,
        "dil",
        "IDPEL,LAT,LON,NEWLAT,NEWLON\n001,-6.2,106.8,,\n002,-6.2,106.8,,\n",
    )
    first = client.get("/master/dil/summary").json()
    assert first["incomplete_coordinates"] == 0
    response = client.post(
        "/upload/confirm-mapping",
        json={
            "batch_id": batch,
            "column_mapping": {"idpel": "IDPEL", "lat": "NEWLAT", "lon": "NEWLON"},
        },
    )
    assert response.status_code == 200
    quick = client.get("/master/dil/summary", params={"details": False}).json()
    assert quick["source_signature"] != first["source_signature"]
    assert quick["total_rows"] == first["total_rows"]
    assert client.get("/master/dil/summary").json()["incomplete_coordinates"] == 2


def test_summary_cache_upgrade_is_additive_and_reset_clears_derived_counts(
    client: TestClient, db_session: Session
) -> None:
    import_master(client, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n")
    assert client.get("/master/dil/summary").status_code == 200
    assert db_session.query(MasterSummaryCache).count() == 1
    assert client.post("/upload/reset").status_code == 200
    assert db_session.query(MasterSummaryCache).count() == 0
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE source_records (id INTEGER PRIMARY KEY, data TEXT)"
        )
        connection.exec_driver_sql("INSERT INTO source_records VALUES (1, 'original')")
        upgrade_master_summary(connection)
        upgrade_master_summary(connection)
        assert "master_summary_caches" in inspect(connection).get_table_names()
        assert (
            connection.exec_driver_sql("SELECT data FROM source_records").scalar_one()
            == "original"
        )
    engine.dispose()
