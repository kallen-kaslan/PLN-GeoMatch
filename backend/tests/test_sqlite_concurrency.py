"""Use real independent SQLite connections to verify reads during atomic writes."""

import logging
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.database import Base, get_db
from app.database_errors import register_database_error_handlers
from app.models.upload import BatchStatus, DatasetType, SourceRecord, UploadBatch
from app.modules.master.router import router as master_router
from app.modules.pdpj.router import router as pdpj_router
from app.sqlite_runtime import configure_sqlite_engine, sqlite_busy


def batch(kind):
    return UploadBatch(
        filename="private-source.csv",
        dataset_type=kind,
        status=BatchStatus.COMPLETED,
        catalog_version=3,
    )


def api_for(engine):
    app = FastAPI()
    register_database_error_handlers(app)
    app.include_router(master_router)
    app.include_router(pdpj_router)

    def isolated_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = isolated_db
    return app


def test_wal_lists_committed_pdpj_and_master_while_writer_is_active(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'wal.db'}", poolclass=NullPool)
    configure_sqlite_engine(engine)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([batch(DatasetType.PDPJ), batch(DatasetType.PRABAYAR)])
        session.commit()
    try:
        with TestClient(api_for(engine)) as client, engine.connect() as writer:
            assert writer.exec_driver_sql("PRAGMA journal_mode").scalar_one() == "wal"
            writer.exec_driver_sql("BEGIN EXCLUSIVE")
            writer.execute(
                UploadBatch.__table__.insert().values(
                    filename="not-committed.csv",
                    dataset_type=DatasetType.PDPJ,
                    status=BatchStatus.COMPLETED,
                )
            )
            # Initializing another process/engine must not attempt a journal-mode
            # change on an already-WAL database while a writer is working.
            another = create_engine(engine.url, poolclass=NullPool)
            try:
                configure_sqlite_engine(another)
            finally:
                another.dispose()
            for path in ["/pdpj/batches", "/master/prabayar/batches"]:
                response = client.get(path)
                assert response.status_code == 200, response.text
                assert len(response.json()) == 1
                assert "not-committed.csv" not in response.text
            writer.commit()
            assert len(client.get("/pdpj/batches").json()) == 2
    finally:
        engine.dispose()


def test_connections_keep_foreign_keys_and_full_durability_and_rollback(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'settings.db'}", poolclass=NullPool)
    configure_sqlite_engine(engine)
    Base.metadata.create_all(engine)
    try:
        for _ in range(2):
            with engine.connect() as connection:
                assert (
                    connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
                )
                assert (
                    connection.exec_driver_sql("PRAGMA synchronous").scalar_one() == 2
                )
                assert (
                    connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one()
                    == 5000
                )
                with pytest.raises(IntegrityError):
                    connection.execute(
                        SourceRecord.__table__.insert().values(batch_id=999)
                    )
        with engine.connect() as writer:
            writer.execute(
                UploadBatch.__table__.insert().values(filename="rolled-back.csv")
            )
            writer.rollback()
        with Session(engine) as session:
            assert session.query(UploadBatch).count() == 0
            assert session.query(SourceRecord).count() == 0
    finally:
        engine.dispose()


def test_busy_legacy_reader_returns_503_then_recovers_without_sql_leaks(
    tmp_path, caplog
):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'legacy.db'}",
        connect_args={"timeout": 0.03},
        poolclass=NullPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(batch(DatasetType.PDPJ))
        session.commit()
    try:
        with TestClient(api_for(engine)) as client, engine.connect() as writer:
            writer.exec_driver_sql("BEGIN EXCLUSIVE")
            with caplog.at_level(logging.WARNING, logger="uvicorn.error.database"):
                response = client.get("/pdpj/batches")
            assert response.status_code == 503, response.text
            assert response.headers["Retry-After"] == "2"
            assert "pemeriksaan atau koreksi" in response.json()["detail"]
            assert all(
                word not in response.text + caplog.text
                for word in [
                    "SELECT",
                    "parameters:",
                    "private-source.csv",
                    "sqlalche.me",
                ]
            )
            writer.rollback()
            response = client.get("/pdpj/batches")
            assert response.status_code == 200 and len(response.json()) == 1
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "code", [sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED, sqlite3.SQLITE_BUSY_SNAPSHOT]
)
def test_extended_sqlite_busy_codes_are_retryable(code):
    original = sqlite3.OperationalError("private SQL must not be shown")
    original.sqlite_errorcode = code
    assert sqlite_busy(OperationalError(None, None, original))


def test_unrelated_database_failures_are_not_reported_as_busy():
    original = sqlite3.OperationalError("unrelated storage failure")
    original.sqlite_errorcode = sqlite3.SQLITE_IOERR
    assert not sqlite_busy(OperationalError(None, None, original))


def test_memory_database_retains_its_supported_journal_mode():
    engine = create_engine("sqlite:///:memory:")
    try:
        configure_sqlite_engine(engine)
        with engine.connect() as connection:
            assert (
                connection.exec_driver_sql("PRAGMA journal_mode").scalar_one()
                == "memory"
            )
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
    finally:
        engine.dispose()
