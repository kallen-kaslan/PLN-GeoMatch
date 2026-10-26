"""Background workers sharing the same isolated pipeline as synchronous execution."""

import logging
from typing import Any

from app.core.celery_app import celery_app
from app.database import SessionLocal
from app.models.matching import MatchingRun, ProcessStatus, ReconciliationProcess
from app.modules.spatial.engine import run_spatial_matching_job
from app.modules.spatial.pipeline import execute_pipeline

logger = logging.getLogger(__name__)


def mark_process_failed(
    db: Any,
    process_id: int,
    run_id: int | None = None,
    *,
    failure_code: str = "processing_failed",
) -> None:
    """Record failure after rollback, without modifying past candidates."""
    db.rollback()
    process = db.get(ReconciliationProcess, process_id)
    latest_id = (
        db.query(MatchingRun.id)
        .filter(MatchingRun.process_id == process_id)
        .order_by(MatchingRun.generation.desc())
        .limit(1)
        .scalar()
    )
    if (
        process
        and process.matching_status != ProcessStatus.COMPLETED
        and (run_id is None or latest_id == run_id)
    ):
        process.matching_status = ProcessStatus.FAILED
    if run_id is not None:
        run = db.get(MatchingRun, run_id)
        if run and run.status != ProcessStatus.COMPLETED:
            run.status = ProcessStatus.FAILED
            run.failure_code = failure_code
    db.commit()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=5)
def execute_matching_task(
    self: Any,
    process_id: int,
    process_name: str,
    target_batch_id: int,
    radius_meters: float = 100.0,
    max_candidates_per_target: int = 5,
    run_id: int | None = None,
) -> dict[str, Any]:
    """Redelivery of a reserved run is idempotent, including existing decisions."""
    db = SessionLocal()
    try:
        return run_spatial_matching_job(
            db,
            process_name,
            target_batch_id,
            radius_meters,
            max_candidates_per_target,
            process_id=process_id,
            run_id=run_id,
        )
    except Exception as exc:  # noqa: BLE001 -- Record every worker failure before retrying.
        mark_process_failed(db, process_id, run_id)
        logger.error(
            "Pencocokan gagal untuk proses #%s (%s)", process_id, type(exc).__name__
        )
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {"status": "failed", "error": "Pencocokan gagal"}
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=1, default_retry_delay=5)
def execute_batch_reconciliation_pipeline(
    self: Any, process_id: int, run_id: int | None = None, retry_on_failure: bool = True
) -> dict[str, Any]:
    """Use only dataset IDs pinned on the process before it was queued."""
    db = SessionLocal()
    try:
        return (
            execute_pipeline(db, process_id, run_id)
            if run_id is not None
            else execute_pipeline(db, process_id)
        )
    except Exception as exc:  # noqa: BLE001 -- Record every worker failure before retrying.
        db.rollback()
        latest = (
            db.query(MatchingRun)
            .filter(MatchingRun.process_id == process_id)
            .order_by(MatchingRun.generation.desc())
            .first()
        )
        mark_process_failed(
            db,
            process_id,
            run_id if run_id is not None else latest.id if latest else None,
        )
        logger.error(
            "Pipeline gagal untuk proses #%s (%s)", process_id, type(exc).__name__
        )
        if retry_on_failure and self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {"status": "failed", "error": "Pipeline gagal"}
    finally:
        db.close()
