"""Recover unfinished empty-ID uploads from durable batch and search state."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.correction import CorrectionCheck
from app.models.matching import MatchingRun, ProcessStatus, ReconciliationProcess
from app.models.radius_analysis import RadiusAnalysis
from app.models.upload import BatchStatus, DatasetType, UploadBatch

router = APIRouter()


def pending_for_kind(db: Session, kind: DatasetType) -> list[dict[str, Any]]:
    # One latest attempt per import, including attempts without target outcomes.
    # Reading this endpoint never starts or resumes a job.
    latest = (
        db.query(
            ReconciliationProcess.target_batch_id.label("batch_id"),
            func.max(MatchingRun.id).label("run_id"),
        )
        .join(CorrectionCheck, CorrectionCheck.process_id == ReconciliationProcess.id)
        .join(MatchingRun, MatchingRun.process_id == ReconciliationProcess.id)
        .filter(CorrectionCheck.category == kind.value)
        .group_by(ReconciliationProcess.target_batch_id)
        .subquery()
    )
    result = []
    latest_analysis = db.query(RadiusAnalysis.batch_id, func.max(RadiusAnalysis.id).label("analysis_id")).group_by(RadiusAnalysis.batch_id).subquery()
    for batch, run, analysis in (
        db.query(UploadBatch, MatchingRun, RadiusAnalysis)
        .outerjoin(latest, latest.c.batch_id == UploadBatch.id)
        .outerjoin(MatchingRun, MatchingRun.id == latest.c.run_id)
        .outerjoin(latest_analysis, latest_analysis.c.batch_id == UploadBatch.id)
        .outerjoin(RadiusAnalysis, RadiusAnalysis.id == latest_analysis.c.analysis_id)
        .filter(UploadBatch.dataset_type == kind)
        .order_by(UploadBatch.id.desc())
        .all()
    ):
        if analysis is not None:
            # A newer radius analysis is independent of an older completed run.
            # Resume only the search explicitly attached to this analysis.
            process_id = analysis.progress.get("search_process_id")
            run = db.query(MatchingRun).filter_by(process_id=process_id).order_by(MatchingRun.generation.desc()).first() if process_id else None
        if run is not None and run.status == ProcessStatus.COMPLETED:
            continue
        progress = (run.processing or {}) if run is not None else {}
        if run is None and analysis is not None:
            result.append({
                "batch_id": batch.id, "filename": batch.filename, "source_sheet": batch.source_sheet,
                "stage": "radius" if analysis.state == "ready" else "analysis", "state": analysis.state,
                "process_id": None, "analysis_id": analysis.id,
                "total_rows": analysis.total_rows, "processed_rows": analysis.processed_rows,
                "processing_stage": "radius" if analysis.state == "ready" else analysis.stage,
            })
            continue
        result.append({
            "batch_id": batch.id, "filename": batch.filename,
            "source_sheet": batch.source_sheet,
            "stage": "search" if run is not None else "analysis" if batch.status == BatchStatus.COMPLETED else "upload",
            "state": progress.get("state", run.status.value if run is not None else "waiting"),
            "process_id": run.process_id if run is not None else None,
            "analysis_id": analysis.id if analysis is not None else None,
            "total_rows": progress.get("total_rows", batch.total_rows or 0),
            "processed_rows": progress.get("processed_rows", 0),
            "processing_stage": progress.get("stage"),
        })
    return result


@router.get("/idpel_kosong/workflow/pending")
def pending(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return pending_for_kind(db, DatasetType.IDPEL_KOSONG)


@router.get("/idpel_tidak_ketemu/workflow/pending")
def not_found_pending(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return pending_for_kind(db, DatasetType.IDPEL_TIDAK_KETEMU)
