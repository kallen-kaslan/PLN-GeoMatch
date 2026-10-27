"""Warm startup must not revisit source cells; failed preparation remains retryable."""

from io import BytesIO

import pytest
from sqlalchemy import create_engine, event, select

from app.master_schema import upgrade_master_catalog
from app.models.coordinate_repair import CoordinateRepair
from app.models.schema_state import SchemaState
from app.models.upload import BatchStatus, DatasetType, SourceRecord, UploadBatch
from app.modules.spatial.master_builder import build_combined_master
from app.modules.upload.normalization import NORMALIZATION_VERSION
from app.schema_compatibility import validate_sqlite_foreign_keys
from app.startup_schema import apply_once, prepare_database


def test_mapping_and_warm_startup_do_not_rescan_raw_rows(client, db_session):
    response = client.post(
        "/upload/",
        data={"dataset_type": "dil"},
        files={
            "file": ("source.csv", BytesIO(b"IDPEL,NAMA\n001,Original\n"), "text/csv")
        },
    )
    assert response.status_code == 200, response.text
    batch_id = response.json()["id"]
    assert db_session.get(UploadBatch, batch_id).catalog_version == 0
    response = client.post(
        "/upload/confirm-mapping",
        json={"batch_id": batch_id, "column_mapping": {"idpel": "IDPEL"}},
    )
    assert response.status_code == 200, response.text
    assert (
        db_session.get(UploadBatch, batch_id).catalog_version == NORMALIZATION_VERSION
    )
    assert db_session.query(CoordinateRepair).filter_by(batch_id=batch_id).count() == 1
    engine = db_session.get_bind()
    db_session.commit()
    with engine.begin() as connection:
        prepare_database(connection)
    # Files imported after the checkpoint and generated masters must also avoid
    # legacy scans on the next boot, even before a new file is mapped.
    combined = build_combined_master(db_session, [], [], [batch_id])
    master_id = combined["master_batch_id"]
    assert (
        db_session.get(UploadBatch, master_id).catalog_version == NORMALIZATION_VERSION
    )
    assert (
        db_session.query(SourceRecord).filter_by(batch_id=master_id).one().row_number
        == 2
    )
    response = client.post(
        "/upload/",
        data={"dataset_type": "dil"},
        files={"file": ("pending.csv", BytesIO(b"IDPEL\n002\n"), "text/csv")},
    )
    assert response.status_code == 200, response.text
    assert db_session.get(UploadBatch, response.json()["id"]).catalog_version == 0
    db_session.commit()
    statements = []

    def capture(_conn, _cursor, statement, _params, _context, _many):
        statements.append(statement.lower())

    event.listen(engine, "before_cursor_execute", capture)
    try:
        with engine.begin() as connection:
            prepare_database(connection)
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert not any(
        "from source_records" in sql or "foreign_key_check" in sql for sql in statements
    )
    assert db_session.query(SourceRecord).filter_by(batch_id=batch_id).one().data == {
        "IDPEL": "001",
        "NAMA": "Original",
    }


def test_catalog_certifies_legacy_once_and_detects_new_batches_and_versions(db_session):
    batch = UploadBatch(dataset_type=DatasetType.DIL, status=BatchStatus.COMPLETED)
    db_session.add(batch)
    db_session.flush()
    raw = {"IDPEL": "000123", "NAMA": "Original"}
    record = SourceRecord(
        batch_id=batch.id,
        data=raw,
        row_number=17,
        normalized_data={
            "idpel": "000123",
            "_normalization_version": NORMALIZATION_VERSION,
        },
    )
    db_session.add(record)
    db_session.commit()
    with db_session.get_bind().begin() as connection:
        upgrade_master_catalog(connection)
    db_session.refresh(batch)
    db_session.refresh(record)
    assert batch.catalog_version == NORMALIZATION_VERSION
    assert record.row_number == 17 and record.data == raw
    # A previously certified batch must be refreshed after a version change.
    batch.catalog_version = NORMALIZATION_VERSION - 1
    record.normalized_data = {
        "idpel": "wrong",
        "_normalization_version": NORMALIZATION_VERSION - 1,
    }
    added = UploadBatch(dataset_type=DatasetType.DIL, status=BatchStatus.COMPLETED)
    db_session.add(added)
    db_session.flush()
    new_record = SourceRecord(batch_id=added.id, data={"IDPEL": "009"})
    db_session.add(new_record)
    db_session.commit()
    with db_session.get_bind().begin() as connection:
        upgrade_master_catalog(connection)
    db_session.expire_all()
    assert record.normalized_data["idpel"] == "000123" and record.data == raw
    assert new_record.row_number == 2 and new_record.normalized_data["idpel"] == "009"
    assert added.catalog_version == batch.catalog_version == NORMALIZATION_VERSION


def test_catalog_failure_does_not_certify_partial_batch(db_session, monkeypatch):
    from app.modules.upload import normalization

    batch = UploadBatch(dataset_type=DatasetType.DIL, status=BatchStatus.COMPLETED)
    db_session.add(batch)
    db_session.flush()
    db_session.add(SourceRecord(batch_id=batch.id, data={"IDPEL": "001"}))
    db_session.commit()
    original = normalization.extract_standard_fields

    def fail(*_args):
        raise RuntimeError("interrupted")

    monkeypatch.setattr(normalization, "extract_standard_fields", fail)
    with (
        pytest.raises(RuntimeError, match="interrupted"),
        db_session.get_bind().begin() as connection,
    ):
        upgrade_master_catalog(connection)
    db_session.refresh(batch)
    assert batch.catalog_version is None
    assert db_session.query(SourceRecord).one().row_number is None
    db_session.commit()
    monkeypatch.setattr(normalization, "extract_standard_fields", original)
    with db_session.get_bind().begin() as connection:
        upgrade_master_catalog(connection)
    db_session.refresh(batch)
    assert batch.catalog_version == NORMALIZATION_VERSION


def test_legacy_row_numbers_continue_across_chunks_and_preserve_existing_numbers(
    db_session,
):
    batch = UploadBatch(dataset_type=DatasetType.DIL, status=BatchStatus.COMPLETED)
    db_session.add(batch)
    db_session.flush()
    rows = [
        {
            "batch_id": batch.id,
            "data": {"IDPEL": "001"},
            "normalized_data": {"_normalization_version": NORMALIZATION_VERSION},
            "row_number": 9000 if number == 2002 else None,
        }
        for number in range(1, 2003)
    ]
    db_session.execute(SourceRecord.__table__.insert(), rows)
    db_session.commit()
    with db_session.get_bind().begin() as connection:
        upgrade_master_catalog(connection)
    numbers = (
        db_session.execute(
            select(SourceRecord.row_number)
            .where(SourceRecord.batch_id == batch.id)
            .order_by(SourceRecord.id)
        )
        .scalars()
        .all()
    )
    assert numbers == [*range(2, 2003), 9000]
    assert all(
        record.data == {"IDPEL": "001"} for record in db_session.query(SourceRecord)
    )


def test_schema_checkpoint_retries_failed_operation_and_changed_version(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'schema.db'}")
    SchemaState.__table__.create(engine)
    calls = []

    def fail(connection):
        connection.execute(
            SchemaState.__table__.insert().values(stage="partial", version="1")
        )
        raise RuntimeError("interrupted")

    with pytest.raises(RuntimeError, match="interrupted"), engine.begin() as connection:
        apply_once(connection, "test", "1", fail)
    with engine.begin() as connection:
        assert connection.execute(select(SchemaState)).first() is None
        apply_once(connection, "test", "1", lambda _conn: calls.append(1))
    with engine.begin() as connection:
        apply_once(connection, "test", "1", lambda _conn: calls.append(1))
        apply_once(connection, "test", "2", lambda _conn: calls.append(2))
    assert calls == [1, 2]
    engine.dispose()


@pytest.mark.parametrize("extra_foreign_key", [False, True])
def test_foreign_key_validation_detects_orphans_with_optimized_and_native_checks(
    extra_foreign_key,
):
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE upload_batches (id INTEGER PRIMARY KEY)"
        )
        extra = (
            ", other INTEGER REFERENCES upload_batches(id)" if extra_foreign_key else ""
        )
        connection.exec_driver_sql(
            f"CREATE TABLE source_records (id INTEGER PRIMARY KEY, batch_id INTEGER REFERENCES upload_batches(id){extra})"
        )
        connection.exec_driver_sql("INSERT INTO upload_batches VALUES (1)")
        connection.exec_driver_sql(
            "INSERT INTO source_records (id, batch_id) VALUES (1, 1), (2, NULL)"
        )
        validate_sqlite_foreign_keys(connection)
        if extra_foreign_key:
            connection.exec_driver_sql(
                "INSERT INTO source_records (id, batch_id, other) VALUES (3, 1, 999)"
            )
        else:
            connection.exec_driver_sql(
                "INSERT INTO source_records (id, batch_id) VALUES (3, 999)"
            )
        with pytest.raises(RuntimeError, match="Relasi database"):
            validate_sqlite_foreign_keys(connection)
    engine.dispose()
