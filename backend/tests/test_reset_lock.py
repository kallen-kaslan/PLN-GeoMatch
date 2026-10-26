"""A busy SQLite database must reject reset without partial deletion or raw SQL leaks."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import Base, get_db
from app.models.upload import BatchStatus, DatasetType, SourceRecord, UploadBatch
from app.models.upload_file import UploadFileArchive
from app.modules.upload.archive import archive_path
from app.modules.upload.router import router


def test_locked_reset_keeps_data_and_files_then_succeeds_after_lock_released(
    tmp_path: Path,
) -> None:
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'locked.db').as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 0.05},
    )
    Base.metadata.create_all(engine)
    key = "a" * 32
    original_file = archive_path(key)
    original_file.parent.mkdir(parents=True, exist_ok=True)
    original_file.write_bytes(b"IDPEL\n001\n")
    with Session(engine) as db:
        batch = UploadBatch(
            filename="source.csv",
            dataset_type=DatasetType.DIL,
            status=BatchStatus.COMPLETED,
        )
        db.add(batch)
        db.flush()
        db.add(SourceRecord(batch_id=batch.id, data={"IDPEL": "001"}))
        db.add(
            UploadFileArchive(
                filename="source.csv",
                sha256="b" * 64,
                storage_key=key,
                size_bytes=10,
                sheet_names=[],
            )
        )
        db.commit()
    app = FastAPI()
    app.include_router(router)

    def isolated_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = isolated_db
    try:
        with TestClient(app) as client:
            with engine.connect() as writer:
                writer.exec_driver_sql("BEGIN EXCLUSIVE")
                response = client.post("/upload/reset")
                assert response.status_code == 503, response.text
                assert "dipakai proses lain" in response.json()["detail"]
                assert "pemeriksaan selesai" in response.json()["detail"]
                assert all(
                    value not in response.text
                    for value in ["SELECT", "SQL:", "sqlalche.me", "storage_key"]
                )
                assert original_file.exists()
                writer.rollback()
            with Session(engine) as db:
                assert (
                    db.query(SourceRecord).count()
                    == db.query(UploadBatch).count()
                    == db.query(UploadFileArchive).count()
                    == 1
                )
            assert client.post("/upload/reset").status_code == 200
            with Session(engine) as db:
                assert (
                    db.query(SourceRecord).count()
                    == db.query(UploadBatch).count()
                    == db.query(UploadFileArchive).count()
                    == 0
                )
            assert not original_file.exists()
    finally:
        engine.dispose()


def test_reset_hides_unexpected_database_error_and_rolls_back(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    def fail(*_args, **_kwargs):
        raise SQLAlchemyError("private SQL statement and parameters")

    monkeypatch.setattr(db_session, "query", fail)
    response = client.post("/upload/reset")
    assert response.status_code == 500
    assert response.json() == {"detail": "Reset database gagal. Silakan coba lagi."}
    assert not db_session.in_transaction()
