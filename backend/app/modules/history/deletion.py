"""Remove process-owned history atomically while retaining shared source snapshots."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.correction import (
    CorrectionAttempt,
    CorrectionCandidateEvidence,
    CorrectionCheck,
    CorrectionTarget,
)
from app.models.correction_decision import CorrectionDecision
from app.models.radius_analysis import RadiusAnalysis, RadiusAnalysisRow
from app.models.matching import (
    MatchCandidate,
    MatchingRun,
    ProcessStatus,
    ReconciliationProcess,
)
from app.modules.pdpj.service import lock_review_session
from app.processing_activity import request_activity


def delete_history(db: Session, process_id: int | None = None) -> None:
    """Lock, validate, and delete children first; the caller commits or rolls back."""
    lock_review_session(db)
    processes_query = db.query(ReconciliationProcess)
    if process_id is not None:
        processes_query = processes_query.filter(ReconciliationProcess.id == process_id)
    processes = (
        processes_query.order_by(ReconciliationProcess.id)
        .with_for_update()
        .populate_existing()
        .all()
    )
    if process_id is not None and not processes:
        raise HTTPException(404, "Proses tidak ditemukan")

    if not processes:
        return
    # Freeze the scope checked above: a concurrent new process must not be swept
    # into a clear-all request after its activity checks have already finished.
    process_ids = select(ReconciliationProcess.id).where(
        ReconciliationProcess.id.in_([process.id for process in processes])
    )
    selected_ids = {process.id for process in processes}
    analyses = db.query(RadiusAnalysis).order_by(RadiusAnalysis.id).populate_existing().all()
    affected = [item for item in analyses if item.process_id in selected_ids
                or item.progress.get("search_process_id") in selected_ids]
    owned = {item.process_id: item for item in affected if item.process_id in selected_ids}
    for item in affected:
        if request_activity(db, "empty_workflow", item.id)["active"] or (
            item.state == "running" and not item.progress.get("search_process_id")
        ):
            raise HTTPException(409, "Proses IDPEL Kosong masih berjalan. Jeda dan tunggu progres tersimpan sebelum menghapus riwayat.")
        search_id = item.progress.get("search_process_id")
        if item.process_id in selected_ids and search_id and search_id not in selected_ids:
            if db.get(ReconciliationProcess, search_id) is not None:
                raise HTTPException(409, "Analisis masih digunakan pencarian kandidat. Hapus riwayat pencariannya dahulu atau hapus seluruh riwayat setelah dijeda.")
    runs = (
        db.query(MatchingRun)
        .filter(MatchingRun.process_id.in_(process_ids))
        .order_by(MatchingRun.process_id, MatchingRun.generation)
        .with_for_update()
        .populate_existing()
        .all()
    )
    processes_with_runs = {run.process_id for run in runs}
    for run in runs:
        pending = run.status in {ProcessStatus.QUEUED, ProcessStatus.RUNNING}
        if request_activity(db, "correction", run.id)["active"] or (
            pending and (run.processing or {}).get("state") != "paused"
        ):
            raise HTTPException(
                409,
                f"Proses #{run.process_id} masih berjalan atau menunggu pemrosesan. "
                "Hentikan sementara dan tunggu bagian aktif tersimpan sebelum menghapus riwayat.",
            )
    for process in processes:
        if process.id not in processes_with_runs and process.matching_status in {
            ProcessStatus.QUEUED,
            ProcessStatus.RUNNING,
        } and process.id not in owned:
            raise HTTPException(
                409, f"Proses #{process.id} masih berjalan atau menunggu pemrosesan."
            )

    # Deleting a search retains its completed analysis and prepared master.
    # Clear only its search link so the saved import can start a new search.
    for item in affected:
        if item.process_id not in selected_ids:
            progress = dict(item.progress)
            progress.pop("search_process_id", None)
            progress["job_kind"] = "analysis"
            item.progress = progress
            item.revision += 1
    analysis_ids = [item.id for item in owned.values()]
    if analysis_ids:
        db.query(RadiusAnalysisRow).filter(RadiusAnalysisRow.analysis_id.in_(analysis_ids)).delete(synchronize_session=False)
        db.query(RadiusAnalysis).filter(RadiusAnalysis.id.in_(analysis_ids)).delete(synchronize_session="fetch")
    candidate_ids = select(MatchCandidate.id).where(
        MatchCandidate.process_id.in_(process_ids)
    )
    run_ids = select(MatchingRun.id).where(MatchingRun.process_id.in_(process_ids))
    # Bulk deletes do not invoke ORM relationship cascades. Cover every FK explicitly,
    # including decisions pointing to candidates from earlier search generations.
    db.query(CorrectionDecision).filter(
        CorrectionDecision.process_id.in_(process_ids)
    ).delete(synchronize_session=False)
    db.query(CorrectionCandidateEvidence).filter(
        CorrectionCandidateEvidence.candidate_id.in_(candidate_ids)
    ).delete(synchronize_session=False)
    db.query(CorrectionTarget).filter(CorrectionTarget.run_id.in_(run_ids)).delete(
        synchronize_session=False
    )
    db.query(CorrectionAttempt).filter(
        CorrectionAttempt.process_id.in_(process_ids)
    ).delete(synchronize_session=False)
    db.query(MatchCandidate).filter(MatchCandidate.process_id.in_(process_ids)).delete(
        synchronize_session=False
    )
    db.query(MatchingRun).filter(MatchingRun.process_id.in_(process_ids)).delete(
        synchronize_session=False
    )
    db.query(CorrectionCheck).filter(
        CorrectionCheck.process_id.in_(process_ids)
    ).delete(synchronize_session=False)
    db.query(ReconciliationProcess).filter(
        ReconciliationProcess.id.in_(process_ids)
    ).delete(synchronize_session="fetch")
