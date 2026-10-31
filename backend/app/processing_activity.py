"""Report actual request activity across reloads without changing saved checkpoints."""

import hashlib
import importlib
import inspect
import json
import os
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from time import monotonic, sleep
from typing import Any, BinaryIO

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.config import settings


def utc_now() -> str:
    return datetime.now(UTC).replace(tzinfo=None).isoformat()


def database_engine(db: Session) -> Engine:
    bind = db.get_bind()
    return bind.engine if isinstance(bind, Connection) else bind


def lock_path(db: Session, scope: str, identity: int) -> Path:
    engine = database_engine(db)
    database = engine.url.database
    root = (
        Path(database).resolve().parent / ".runtime" / "processing"
        if database and database != ":memory:"
        else Path(settings.UPLOAD_STORAGE_DIR).parent / "processing"
    )
    key = hashlib.sha256(f"{scope}:{identity}".encode()).hexdigest()[:32]
    return root / f"{key}.lock"


def file_lock(stream: BinaryIO, *, release: bool = False) -> bool:
    stream.seek(0)
    if os.name == "nt":
        import msvcrt

        try:
            msvcrt.locking(
                stream.fileno(), msvcrt.LK_UNLCK if release else msvcrt.LK_NBLCK, 1
            )
        except OSError:
            if release:
                raise
            return False
    else:
        fcntl: Any = importlib.import_module("fcntl")

        try:
            fcntl.flock(
                stream, fcntl.LOCK_UN if release else fcntl.LOCK_EX | fcntl.LOCK_NB
            )
        except BlockingIOError:
            return False
    return True


@contextmanager
def activity_lock(
    db: Session, scope: str, identity: int, operation: str | None = None
) -> Iterator[dict[str, Any]]:
    """OS/advisory locks expire on process exit, even during a long transaction."""
    if database_engine(db).dialect.name == "postgresql":
        key = int.from_bytes(
            hashlib.sha256(f"{scope}:{identity}".encode()).digest()[:8], signed=True
        )
        with database_engine(db).connect() as connection:
            acquired = connection.execute(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": key}
            ).scalar()
            try:
                yield {"active": not acquired, "operation": None, "started_at": None}
            finally:
                if acquired:
                    connection.execute(
                        text("SELECT pg_advisory_unlock(:key)"), {"key": key}
                    )
        return
    path = lock_path(db, scope, identity)
    if operation is None and not path.exists():
        yield {"active": False, "operation": None, "started_at": None}
        return
    if operation is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        stream = os.fdopen(descriptor, "r+b")
    else:
        stream = path.open("r+b")
    with stream:
        if not path.stat().st_size:
            stream.write(b"\0")
            stream.flush()
        acquired = file_lock(stream)
        try:
            metadata: dict[str, Any] = {}
            if acquired and operation is not None:
                metadata = {"operation": operation, "started_at": utc_now()}
                stream.seek(1)
                stream.write(json.dumps(metadata).encode())
                stream.truncate()
                stream.flush()
            elif not acquired:
                stream.seek(1)
                try:
                    metadata = json.loads(stream.read())
                except (ValueError, OSError):
                    pass
            yield {
                "active": not acquired,
                "operation": metadata.get("operation"),
                "started_at": metadata.get("started_at"),
            }
        finally:
            if acquired:
                file_lock(stream, release=True)


def request_activity(db: Session | None, scope: str, identity: int) -> dict[str, Any]:
    """Probe activity without acquiring a database write lock or trusting `running`."""
    if db is None:
        return {
            "active": False,
            "operation": None,
            "started_at": None,
            "observed_at": utc_now(),
        }
    with activity_lock(db, scope, identity) as activity:
        pass
    with activity_lock(db, scope + ":pause", identity) as pause:
        if pause["active"]:
            activity = {**pause, "operation": "pausing"}
    return {**activity, "observed_at": utc_now()}


def monitor_request(scope: str, identity_parameter: str, operation: str) -> Callable:
    """Track the full request, including waiting for a transaction and its commit."""

    def decorate(function: Callable) -> Callable:
        signature = inspect.signature(function)

        @wraps(function)
        def monitored(*args: Any, **kwargs: Any) -> Any:
            arguments = signature.bind(*args, **kwargs).arguments
            parts = identity_parameter.split(".")
            identity = arguments[parts[0]]
            for part in parts[1:]:
                identity = getattr(identity, part)
            db = arguments["db"]
            with ExitStack() as stack:
                if operation == "pausing":
                    pause = stack.enter_context(
                        activity_lock(db, scope + ":pause", identity, "pausing")
                    )
                else:
                    with activity_lock(db, scope + ":pause", identity) as pause:
                        pass
                if pause["active"]:
                    raise HTTPException(
                        409, "Proses sedang dijeda. Tunggu pembaruan progres."
                    )
                # A status probe holds the same lock very briefly; allow it to exit.
                deadline = monotonic() + 0.15
                while True:
                    with activity_lock(db, scope, identity, operation) as activity:
                        if not activity["active"]:
                            result = function(*args, **kwargs)
                            break
                        if operation != "pausing" and monotonic() >= deadline:
                            raise HTTPException(
                                409,
                                "Bagian aktif masih diproses server. Tunggu pembaruan progres.",
                            )
                    sleep(0.05)
            if isinstance(result, dict) and "activity" in result:
                result["activity"] = request_activity(db, scope, identity)
            return result

        return monitored

    return decorate
