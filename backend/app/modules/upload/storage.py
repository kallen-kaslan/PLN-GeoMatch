"""Report database write failures after discarding the failed transaction."""

import logging
import sqlite3

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def database_write_error(
    db: Session, exc: SQLAlchemyError, operation: str
) -> HTTPException:
    original = getattr(exc, "orig", None)
    code = getattr(original, "sqlite_errorcode", None)
    name = getattr(original, "sqlite_errorname", None)
    # Never log SQL parameters: uploaded customer cells may be present in them.
    logger.error(
        "%s gagal: %s; sqlite_error=%s (%s)", operation, type(exc).__name__, name, code
    )
    try:
        db.rollback()
    except SQLAlchemyError:
        db.invalidate()

    primary = code & 0xFF if isinstance(code, int) else None
    if primary == sqlite3.SQLITE_FULL:
        return HTTPException(
            507,
            "Penyimpanan database penuh. Sediakan ruang kosong pada drive database "
            "dan folder sementara, lalu coba lagi.",
        )
    if primary == sqlite3.SQLITE_IOERR:
        return HTTPException(
            503,
            "Database gagal menulis ke disk. Periksa akses folder database dan "
            "ruang disk, lalu coba lagi setelah penyimpanan pulih.",
        )
    if primary in {
        sqlite3.SQLITE_READONLY,
        sqlite3.SQLITE_CANTOPEN,
        sqlite3.SQLITE_PERM,
    }:
        return HTTPException(
            503,
            "Database tidak dapat ditulis. Periksa izin akses file dan folder database, "
            "lalu coba lagi.",
        )
    if primary in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
        return HTTPException(
            503, "Database sedang dipakai proses lain. Tunggu sebentar, lalu coba lagi."
        )
    return HTTPException(500, f"Gagal menyimpan {operation}. Silakan coba lagi.")
