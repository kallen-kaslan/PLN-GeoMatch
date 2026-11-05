"""Server-owned, row-atomic empty-ID jobs, independent of browser connections.

Each transaction commits one target plus all its candidates and evidence. OS /
PostgreSQL advisory locks prevent duplicate workers and signal a pending pause
without competing for SQLite's writer lock. Checkpoints remain in the database;
after a backend restart an explicit resume continues from the committed row.
"""

import logging
from threading import Thread
from time import monotonic, sleep
from typing import Literal

from fastapi import HTTPException
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.matching import MatchingRun, ProcessStatus
from app.models.radius_analysis import RadiusAnalysis
from app.models.upload import UploadBatch
from app.modules.corrections.progress import advance_progress, control_progress
from app.modules.corrections.radius_analysis import analysis_info, advance_analysis, get_analysis
from app.modules.corrections.service import CorrectionKind
from app.processing_activity import activity_lock, database_engine, request_activity

logger = logging.getLogger(__name__)
SCOPE = "empty_workflow"
JobKind = Literal["analysis", "search"]


def analysis_category(db: Session, item: RadiusAnalysis) -> CorrectionKind:
    batch = db.get(UploadBatch, item.batch_id)
    if batch is None:
        raise HTTPException(404, "Unggahan koreksi tidak ditemukan")
    return CorrectionKind(batch.dataset_type.value)


def search_run(db: Session, item: RadiusAnalysis) -> MatchingRun | None:
    process_id = item.progress.get("search_process_id")
    if not process_id:
        return None
    return db.query(MatchingRun).filter_by(process_id=process_id).order_by(MatchingRun.generation.desc()).first()


def workflow_info(db: Session, item: RadiusAnalysis, radius: float | None = None) -> dict:
    run = search_run(db, item)
    progress = (run.processing or {}) if run else {}
    return {
        "analysis": analysis_info(db, item, radius),
        "activity": request_activity(db, SCOPE, item.id),
        "job_kind": item.progress.get("job_kind"),
        "search": None if run is None else {
            "process_id": run.process_id, "run_id": run.id,
            "generation": run.generation, "status": run.status.value,
            "state": progress.get("state", run.status.value),
            "stage": progress.get("stage"),
            "total_rows": progress.get("total_rows", run.total_targets),
            "processed_rows": progress.get("processed_rows", 0),
            "matched_rows": progress.get("matched_rows", 0),
            "no_candidate_rows": progress.get("no_candidate_rows", 0),
            "coordinate_rows": progress.get("coordinate_rows", 0),
            "other_issue_rows": progress.get("other_issue_rows", 0),
            "idpel_in_pdpj_rows": progress.get("idpel_in_pdpj_rows", 0),
            "elapsed_seconds": progress.get("elapsed_seconds", 0.0),
            "radius_meters": run.radius_meters, "error": progress.get("error"),
        },
    }


def work(bind: Engine, analysis_id: int, kind: JobKind) -> None:
    factory = sessionmaker(bind=bind, expire_on_commit=False)
    with factory() as db:
        deadline = monotonic() + 1.0
        while True:
            with activity_lock(db, SCOPE, analysis_id, kind) as activity:
                if not activity["active"]:
                    _work_locked(db, analysis_id, kind)
                    return
            # Status probes acquire the same lock very briefly. Do not abandon a
            # queued job merely because a simultaneous GET is observing activity.
            if monotonic() >= deadline:
                return
            sleep(0.02)


def _work_locked(db: Session, analysis_id: int, kind: JobKind) -> None:
    try:
        while True:
            if pause_requested(db, analysis_id):
                return
            db.expire_all()
            item = db.get(RadiusAnalysis, analysis_id)
            if item is None or item.progress.get("job_kind") != kind:
                return
            if kind == "analysis":
                if item.state != "running":
                    return
                advance_analysis(db, item.id, item.revision, chunk_size=1)
            else:
                run = search_run(db, item)
                if run is None or run.status == ProcessStatus.COMPLETED or (run.processing or {}).get("state") != "running":
                    return
                progress = run.processing or {}
                advance_progress(db, analysis_category(db, item), run.process_id, run.id, progress["revision"], 1 if progress["stage"] == "matching" else 400)
            # End read transactions before checking a pause / next writer.
            db.rollback()
            sleep(0)
    except Exception:
        db.rollback()
        logger.exception("Pekerjaan IDPEL Kosong #%s terhenti", analysis_id)


def pause_requested(db: Session, analysis_id: int) -> bool:
    # A read-only activity probe can briefly own this lock too. Only treat a
    # sustained lock as a pause command; do not advance a row while checking.
    for _ in range(3):
        with activity_lock(db, SCOPE + ":pause", analysis_id) as pause:
            if not pause["active"]:
                return False
        sleep(0.02)
    return True


def launch(bind: Engine, analysis_id: int, kind: JobKind) -> None:
    # The database-specific advisory/file lock elects the sole worker, including
    # across API processes; no browser-held lease or shared ORM session.
    Thread(target=work, args=(bind, analysis_id, kind), daemon=True, name=f"empty-{kind}-{analysis_id}").start()


def _set_state(db: Session, analysis_id: int, kind: JobKind, state: str) -> None:
    item = get_analysis(db, analysis_id, locked=True)
    if kind == "analysis":
        if item.progress.get("search_process_id"):
            raise HTTPException(409, "Pencarian sudah dibuat; lanjutkan pencarian tersebut")
        if item.state != "ready":
            item.state, item.error = state, None
            item.revision += 1
    else:
        run = search_run(db, item)
        if run is None:
            raise HTTPException(409, "Pencarian belum dibuat")
        control_progress(db, analysis_category(db, item), run.process_id, run.id, state)
    item.progress = {**item.progress, "managed": True, "job_kind": kind}
    db.commit()


def control_job(db: Session, analysis_id: int, kind: JobKind, state: Literal["running", "paused"]) -> dict:
    bind = database_engine(db)
    existing = get_analysis(db, analysis_id)
    if state == "paused" and existing.progress.get("job_kind") not in {None, kind}:
        raise HTTPException(409, "Tahap proses sudah berubah. Muat ulang progres")
    # Do not hold an old read snapshot while the worker commits its active row.
    db.rollback()
    if state == "paused":
        # Keep the pause signal held until the worker's current row commits and
        # the durable paused state is saved. A client disconnect cannot lose it.
        with activity_lock(db, SCOPE + ":pause", analysis_id, "pausing") as pause:
            if pause["active"]:
                raise HTTPException(409, "Permintaan jeda sedang diselesaikan")
            while True:
                with activity_lock(db, SCOPE, analysis_id, "pausing") as active:
                    if not active["active"]:
                        _set_state(db, analysis_id, kind, "paused")
                        break
                sleep(0.05)
    else:
        if pause_requested(db, analysis_id):
            raise HTTPException(409, "Tunggu baris aktif selesai dan jeda tersimpan")
        deadline = monotonic() + 0.2
        while True:
            with activity_lock(db, SCOPE, analysis_id, "starting") as active:
                if not active["active"]:
                    _set_state(db, analysis_id, kind, "running")
                    break
            if monotonic() >= deadline:
                return workflow_info(db, get_analysis(db, analysis_id))
            sleep(0.02)
        launch(bind, analysis_id, kind)
    db.expire_all()
    return workflow_info(db, get_analysis(db, analysis_id))
