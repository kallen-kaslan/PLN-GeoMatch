"""Condition filters must use stored totals and ordered covering indexes."""

import pytest
from app.master_filter_schema import upgrade_master_filters
from app.models.upload import MASTER_FILTER_INDEX_NAMES, SourceRecord, UploadBatch
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from tests.test_master_catalog import import_master
from tests.test_master_summary_cache import source_reads


@pytest.mark.parametrize(
    "status,total,index",
    [
        ("valid", 6, "ix_source_records_batch_valid_id"),
        ("invalid", 2, "ix_source_records_batch_valid_id"),
        ("incomplete", 2, "ix_source_records_batch_valid_missing_id"),
    ],
)
def test_condition_pages_use_covering_indexes_and_preserve_file_order(
    client: TestClient, db_session: Session, status: str, total: int, index: str
) -> None:
    content = "IDPEL,NAMA,LAT,LON\n001,Lengkap,-6.2,106.8\n002,Kosong,,\n003,Bermasalah,bad,106.8\n004,Lengkap lain,-6.3,106.9\n"
    old = import_master(client, "dil", content)
    new = import_master(client, "dil", content)
    import_master(client, "prabayar", content)
    # An unconfirmed source must not enter the counts or page.
    client.post(
        "/upload/",
        data={"dataset_type": "dil"},
        files={"file": ("pending.csv", content.encode())},
    )
    response, reads = source_reads(
        db_session,
        lambda: client.get(
            "/master/dil/records", params={"status": status, "limit": 100}
        ),
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["total"] == total
    assert [row["batch_id"] for row in result["items"]] == [new] * (total // 2) + [
        old
    ] * (total // 2)
    assert all(row["is_valid"] == (status != "invalid") for row in result["items"])
    if status == "incomplete":
        assert all(not row["coordinates_complete"] for row in result["items"])
    count_reads = [(sql, params) for sql, params in reads if "count(" in sql.lower()]
    assert bool(count_reads) == (status == "incomplete")
    page_reads = [
        (sql, params)
        for sql, params in reads
        if "LIMIT" in sql and "ORDER BY source_records.id" in sql
    ]
    assert len(page_reads) == 2
    for sql, params in page_reads + count_reads:
        plan = (
            db_session.connection()
            .exec_driver_sql("EXPLAIN QUERY PLAN " + sql, params)
            .all()
        )
        assert any(f"USING COVERING INDEX {index}" in row[3] for row in plan), plan
        if "LIMIT" in sql:
            assert not any("TEMP B-TREE" in row[3] for row in plan)
    assert not any("source_records.data" in sql for sql, _ in reads)
    # Counts with a text query still reflect the query, rather than the file total.
    filtered = client.get(
        "/master/dil/records", params={"status": status, "q": "tidak-ada"}
    ).json()
    assert filtered["total"] == 0 and filtered["items"] == []
    page = client.get(
        "/master/dil/records",
        params={"status": status, "skip": total // 2 - 1, "limit": 2},
    ).json()
    assert [row["batch_id"] for row in page["items"]] == [new, old]


def test_zero_condition_counts_skip_rows_and_legacy_counts_only_read_unknown_files(
    client: TestClient, db_session: Session
) -> None:
    known = import_master(
        client, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n002,-6.3,106.9\n"
    )
    response, reads = source_reads(
        db_session,
        lambda: client.get("/master/dil/records", params={"status": "invalid"}),
    )
    assert response.json()["total"] == 0 and reads == []
    legacy = import_master(
        client, "dil", "IDPEL,LAT,LON\n003,-6.2,106.8\n004,bad,106.9\n"
    )
    db_session.execute(
        update(UploadBatch)
        .where(UploadBatch.id == legacy)
        .values(total_rows=0, valid_rows=0, error_rows=0)
    )
    db_session.commit()
    response, reads = source_reads(
        db_session,
        lambda: client.get("/master/dil/records", params={"status": "valid"}),
    )
    assert response.json()["total"] == 3
    count_reads = [(sql, params) for sql, params in reads if "count(" in sql.lower()]
    assert len(count_reads) == 1
    assert legacy in count_reads[0][1] and known not in count_reads[0][1]


def test_condition_indexes_update_after_remapping_and_upgrade_preserves_cells(
    client: TestClient, db_session: Session
) -> None:
    batch = import_master(
        client,
        "dil",
        "IDPEL,LAT,LON,NEWLAT,NEWLON\n001,-6.2,106.8,,\n002,-6.3,106.9,,\n",
    )
    assert (
        client.get("/master/dil/records", params={"status": "incomplete"}).json()[
            "total"
        ]
        == 0
    )
    response = client.post(
        "/upload/confirm-mapping",
        json={
            "batch_id": batch,
            "column_mapping": {"idpel": "IDPEL", "lat": "NEWLAT", "lon": "NEWLON"},
        },
    )
    assert response.status_code == 200
    assert (
        client.get("/master/dil/records", params={"status": "incomplete"}).json()[
            "total"
        ]
        == 2
    )
    originals = [
        (row.id, row.data, row.normalized_data)
        for row in db_session.query(SourceRecord)
    ]
    db_session.commit()
    with db_session.get_bind().begin() as connection:
        for index in SourceRecord.__table__.indexes:
            if index.name in MASTER_FILTER_INDEX_NAMES:
                index.drop(connection)
        upgrade_master_filters(connection)
        upgrade_master_filters(connection)
        names = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA index_list('source_records')")
        }
        assert set(MASTER_FILTER_INDEX_NAMES) <= names
    db_session.expire_all()
    assert [
        (row.id, row.data, row.normalized_data)
        for row in db_session.query(SourceRecord)
    ] == originals
