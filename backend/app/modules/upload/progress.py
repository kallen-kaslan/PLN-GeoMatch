"""Small, cross-worker progress snapshots independent of the import transaction."""

import json
import logging
import os
import re
import time
from collections.abc import Callable
from functools import wraps
from inspect import signature
from pathlib import Path
from typing import Annotated, Any, ParamSpec, TypeVar
from uuid import uuid4

from app.config import settings
from fastapi import APIRouter, Header, HTTPException, Response
from sqlalchemy.orm import Session

router = APIRouter()
logger = logging.getLogger(__name__)


def progress_path(token: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}", token):
        raise HTTPException(422, "ID progres tidak valid")
    return Path(settings.UPLOAD_STORAGE_DIR).resolve() / "progress" / f"{token}.json"


def read_progress(token: str) -> dict[str, Any]:
    try:
        return json.loads(progress_path(token).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HTTPException(404, "Progres unggahan tidak ditemukan") from exc


def pause_path(token: str) -> Path:
    return progress_path(token).with_suffix(".pause")


class UploadProgress:
    def __init__(self, token: str | None):
        self.token = token
        self.snapshot = read_progress(token) if token else {}
        self.last_write = 0.0
        self.batch_id: int | None = None
        self.checkpoint_committed = False

    def write(self, *, force: bool = False) -> None:
        if not self.token or (not force and time.monotonic() - self.last_write < 0.25):
            return
        path = progress_path(self.token)
        temporary = path.with_suffix(f".{uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps(self.snapshot), encoding="utf-8")
            for attempt in range(5):
                try:
                    os.replace(temporary, path)
                    break
                except PermissionError:
                    # Windows can briefly hold the destination while a poll reads it.
                    if attempt == 4:
                        raise
                    time.sleep(0.01)
        except OSError:
            # A missed status update must not abort or misreport a committed import.
            logger.warning("Pembaruan progres unggahan belum dapat ditulis")
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        self.last_write = time.monotonic()

    def stage(self, phase: str, total: int | None = None, unit: str = "rows") -> None:
        if not self.token:
            return
        self.snapshot.update(
            phase=phase,
            total=total,
            unit=unit,
            processed=0,
            status="running",
            phase_started_at=time.time(),
            updated_at=time.time(),
            error=None,
        )
        self.write(force=True)

    def update(self, processed: int, total: int | None = None) -> None:
        if not self.token:
            return
        self.snapshot.update(processed=processed, updated_at=time.time())
        if total is not None:
            self.snapshot["total"] = total
        self.write()

    def finish(self, status: str = "completed") -> None:
        if not self.token:
            return
        self.snapshot.update(status=status, updated_at=time.time())
        self.write(force=True)

    def checkpoint(self, db: Session | None = None) -> None:
        """Stop at a completed chunk; never wait while holding database locks."""
        if not self.token or not pause_path(self.token).exists():
            return
        if db is not None:
            db.commit()
            self.checkpoint_committed = True
        started = time.time()
        self.snapshot.update(status="paused", paused_at=started, updated_at=started)
        self.write(force=True)
        while pause_path(self.token).exists():
            time.sleep(0.2)
        if db is not None:
            from app.modules.pdpj.service import lock_review_session

            lock_review_session(db)
        # Exclude the pause from the throughput and ETA for this phase.
        self.snapshot["phase_started_at"] += time.time() - started
        self.snapshot.update(status="running", paused_at=None, updated_at=time.time())
        self.write(force=True)


def track_upload(
    token: Annotated[str | None, Header(alias="X-Upload-Progress")] = None,
) -> UploadProgress:
    return UploadProgress(token)


P = ParamSpec("P")
R = TypeVar("R")


def report_progress(operation: Callable[P, R]) -> Callable[P, R]:
    parameters = signature(operation)

    @wraps(operation)
    def tracked(*args: P.args, **kwargs: P.kwargs) -> R:
        progress = parameters.bind(*args, **kwargs).arguments["progress"]
        try:
            result = operation(*args, **kwargs)
        except Exception:
            progress.finish("failed")
            raise
        # Publish before the response: a subsequent phase can reuse this token.
        progress.finish()
        return result

    return tracked


@router.post("/progress")
def create_progress() -> dict[str, Any]:
    token = uuid4().hex
    path = progress_path(token)
    path.parent.mkdir(parents=True, exist_ok=True)
    # These are temporary status files, never source data. Bound their retention.
    cutoff = time.time() - 86400
    for previous in path.parent.glob("*.json"):
        try:
            if (
                previous.stat().st_mtime < cutoff
                and not previous.with_suffix(".pause").exists()
            ):
                previous.unlink(missing_ok=True)
                previous.with_suffix(".pause").unlink(missing_ok=True)
        except OSError:
            pass
    now = time.time()
    snapshot = {
        "id": token,
        "phase": "waiting",
        "status": "running",
        "processed": 0,
        "total": None,
        "unit": "bytes",
        "started_at": now,
        "phase_started_at": now,
        "updated_at": now,
    }
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    return snapshot


@router.get("/progress/{token}")
async def get_progress(token: str, response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return {**read_progress(token), "pause_requested": pause_path(token).exists()}


@router.post("/progress/{token}/pause")
async def pause_upload(token: str) -> dict[str, Any]:
    read_progress(token)
    pause_path(token).touch(exist_ok=True)
    return {"pause_requested": True}


@router.post("/progress/{token}/resume")
async def resume_upload(token: str) -> dict[str, Any]:
    read_progress(token)
    pause_path(token).unlink(missing_ok=True)
    return {"pause_requested": False}
