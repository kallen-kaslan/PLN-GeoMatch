"""Return a retryable response for SQLite contention without exposing source cells."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.sqlite_runtime import sqlite_busy

logger = logging.getLogger("uvicorn.error.database")


async def database_busy_response(
    _request: Request, exc: OperationalError
) -> JSONResponse:
    if not sqlite_busy(exc):
        raise exc
    logger.warning("database busy sqlite_error_code=%s", exc.orig.sqlite_errorcode)
    return JSONResponse(
        status_code=503,
        headers={"Retry-After": "2"},
        content={
            "detail": "Database sedang menyelesaikan penulisan data. Tunggu proses "
            "pemeriksaan atau koreksi selesai, lalu coba lagi."
        },
    )


def register_database_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(OperationalError, database_busy_response)
