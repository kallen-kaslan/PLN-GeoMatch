"""Storage failures must preserve the raw upload and allow a safe mapping retry."""

import logging
import sqlite3
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.upload import BatchStatus, SourceRecord, UploadBatch
from app.modules.upload import router, storage
from app.modules.upload.storage import database_write_error


def storage_failure(code=sqlite3.SQLITE_IOERR_DELETE):
    original = sqlite3.OperationalError("disk I/O error")
    original.sqlite_errorcode = code
    original.sqlite_errorname = "SQLITE_IOERR_DELETE"
    return OperationalError(None, None, original)


@pytest.mark.parametrize("phase", ["flush", "commit"])
def test_mapping_storage_failure_rolls_back_all_chunks_and_can_retry(
    client, db_session, monkeypatch, phase, caplog
):
    # Alembic's logging configuration in migration tests disables existing loggers.
    monkeypatch.setattr(storage.logger, "disabled", False)
    caplog.set_level(logging.ERROR, logger=storage.logger.name)
    monkeypatch.setattr(router, "IMPORT_CHUNK_ROWS", 2)
    uploaded = client.post(
        "/upload/",
        data={"dataset_type": "pdpj"},
        files={
            "file": (
                "pdpj.csv",
                b"CUSTOMER,NAMA\n001,Private Name\n002,B\n003,C\n004,D\n005,E\n",
                "text/csv",
            )
        },
    )
    assert uploaded.status_code == 200
    batch_id = uploaded.json()["id"]
    body = {"batch_id": batch_id, "column_mapping": {"idpel": "CUSTOMER"}}
    original_method = getattr(db_session, phase)
    calls = 0

    def fail(*args, **kwargs):
        nonlocal calls
        calls += 1
        if phase == "commit" or calls == 2:
            raise storage_failure()
        return original_method(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(db_session, phase, fail)
        failed = client.post("/upload/confirm-mapping", json=body)
    assert failed.status_code == 503, failed.text
    assert "disk" in failed.json()["detail"]
    assert "SQLITE_IOERR_DELETE" in caplog.text
    assert "Private Name" not in caplog.text
    db_session.expire_all()
    batch = db_session.get(UploadBatch, batch_id)
    assert batch.status == BatchStatus.NEEDS_MAPPING
    assert batch.column_mapping is None
    records = db_session.query(SourceRecord).filter_by(batch_id=batch_id).all()
    assert len(records) == 5
    assert all(
        record.normalized_data is None and record.idpel is None for record in records
    )
    assert records[0].data == {"CUSTOMER": "001", "NAMA": "Private Name"}

    retried = client.post("/upload/confirm-mapping", json=body)
    assert retried.status_code == 200, retried.text
    assert retried.json()["valid_rows"] == 5
    db_session.expire_all()
    assert db_session.get(UploadBatch, batch_id).status == BatchStatus.COMPLETED
    assert db_session.query(SourceRecord).filter_by(batch_id=batch_id).count() == 5


@pytest.mark.parametrize(
    "code, status, message",
    [
        (sqlite3.SQLITE_FULL, 507, "penuh"),
        (sqlite3.SQLITE_READONLY, 503, "izin akses"),
        (sqlite3.SQLITE_BUSY, 503, "dipakai proses lain"),
    ],
)
def test_upload_storage_errors_are_actionable_and_do_not_leave_partial_data(
    client, db_session, monkeypatch, code, status, message
):
    def fail():
        raise storage_failure(code)

    monkeypatch.setattr(db_session, "commit", fail)
    result = client.post(
        "/upload/",
        data={"dataset_type": "pdpj"},
        files={"file": ("pdpj.csv", b"IDPEL\n001\n", "text/csv")},
    )
    assert result.status_code == status, result.text
    assert message in result.json()["detail"]
    assert db_session.query(UploadBatch).count() == 0
    assert db_session.query(SourceRecord).count() == 0


def test_failed_rollback_discards_the_broken_connection():
    session = Mock(spec=Session)
    session.rollback.side_effect = SQLAlchemyError("rollback failed")
    response = database_write_error(session, storage_failure(), "konfirmasi mapping")
    assert response.status_code == 503
    session.invalidate.assert_called_once_with()
