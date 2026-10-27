"""Keep committed data readable while one SQLite writer prepares an atomic result."""

import logging
import sqlite3
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

logger = logging.getLogger("uvicorn.error.database")
BUSY_TIMEOUT_MS = 5000


def sqlite_busy(exc: OperationalError) -> bool:
    code = getattr(exc.orig, "sqlite_errorcode", None)
    return isinstance(code, int) and code & 0xFF in {
        sqlite3.SQLITE_BUSY,
        sqlite3.SQLITE_LOCKED,
    }


def configure_connection(connection: Any, _record: object) -> None:
    cursor = connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
        # Retain crash durability; concurrency does not require weaker syncing.
        cursor.execute("PRAGMA synchronous=FULL")
    finally:
        cursor.close()


def configure_sqlite_engine(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    if not event.contains(engine, "connect", configure_connection):
        event.listen(engine, "connect", configure_connection)
    try:
        # A journal-mode transition must happen outside a transaction. WAL is
        # persistent, so existing WAL databases do not need a write on startup.
        with engine.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as connection:
            mode = connection.exec_driver_sql("PRAGMA journal_mode").scalar_one()
            if mode == "memory":
                return
            if mode != "wal":
                mode = connection.exec_driver_sql(
                    "PRAGMA journal_mode=WAL"
                ).scalar_one()
            if mode != "wal":
                raise RuntimeError("Database SQLite belum dapat memakai mode WAL.")
        logger.info(
            "sqlite journal_mode=wal busy_timeout_ms=%s synchronous=FULL",
            BUSY_TIMEOUT_MS,
        )
    except OperationalError as exc:
        if sqlite_busy(exc):
            raise RuntimeError(
                "Database sedang dipakai proses lain. Selesaikan atau hentikan pekerjaan "
                "database yang sedang berjalan sebelum menjalankan backend kembali."
            ) from None
        raise
