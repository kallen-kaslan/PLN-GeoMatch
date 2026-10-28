"""Commit bounded correction work and resume the same run from durable cursors."""

from time import monotonic
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.correction import CorrectionCandidateEvidence, CorrectionTarget, utc_now
from app.models.matching import (
    MatchCandidate,
    MatchingRun,
    ProcessStatus,
    ReconciliationProcess,
    ReviewStatus,
)
from app.models.upload import SourceRecord
from app.modules.corrections.engine import run_correction_matching
from app.modules.corrections.service import CorrectionKind, check_process
from app.modules.pdpj.service import lock_review_session
from app.modules.spatial.master_preparation import advance_preparation


def initialize_progress(
    db: Session, process: ReconciliationProcess, run: MatchingRun
) -> None:
    """Return the run identity before preparation or candidate searches begin."""
    now = utc_now().isoformat()
    total = (
        db.query(SourceRecord)
        .filter(SourceRecord.batch_id == process.target_batch_id)
        .count()
    )
    run.processing = {
        "state": "running",
        "stage": "preparing",
        "revision": 1,
        "total_rows": total,
        "processed_rows": 0,
        "validated_rows": 0,
        "matched_rows": 0,
        "last_source_id": 0,
        "last_row_number": None,
        "last_validated_source_id": 0,
        "started_at": now,
        "updated_at": now,
        "elapsed_seconds": 0.0,
        "error": None,
    }
    run.total_targets = total
    run.status = process.matching_status = ProcessStatus.RUNNING


def locked_run(
    db: Session, kind: CorrectionKind, process_id: int, run_id: int
) -> tuple[ReconciliationProcess, MatchingRun]:
    """Serialize mutations and reject another category or an obsolete attempt."""
    lock_review_session(db)
    check_process(db, kind, process_id)
    process = (
        db.query(ReconciliationProcess)
        .filter_by(id=process_id)
        .with_for_update()
        .populate_existing()
        .one()
    )
    latest = (
        db.query(MatchingRun)
        .filter_by(process_id=process_id)
        .order_by(MatchingRun.generation.desc())
        .with_for_update()
        .populate_existing()
        .first()
    )
    if latest is None or latest.id != run_id or not latest.processing:
        raise HTTPException(
            409, "Versi pemeriksaan telah berubah. Muat ulang Data Koreksi."
        )
    return process, latest


def control_progress(
    db: Session, kind: CorrectionKind, process_id: int, run_id: int, state: str
) -> MatchingRun:
    """Pause after committed work, or resume the same saved attempt."""
    process, run = locked_run(db, kind, process_id, run_id)
    assert run.processing is not None
    if run.status == ProcessStatus.COMPLETED:
        return run
    run.processing = {
        **run.processing,
        "state": state,
        "error": None,
        "revision": run.processing["revision"] + 1,
        "updated_at": utc_now().isoformat(),
    }
    run.status = process.matching_status = ProcessStatus.RUNNING
    run.failure_code = None
    db.commit()
    return run


def validate_chunk(
    db: Session, run: MatchingRun, progress: dict[str, Any], chunk_size: int
) -> None:
    """Check stored outcome/candidate/evidence counts before publishing the run."""
    outcomes = (
        db.query(CorrectionTarget)
        .filter(
            CorrectionTarget.run_id == run.id,
            CorrectionTarget.source_record_id > progress["last_validated_source_id"],
        )
        .order_by(CorrectionTarget.source_record_id)
        .limit(chunk_size)
        .all()
    )
    totals = {
        record_id: (candidates, evidence)
        for record_id, candidates, evidence in db.query(
            MatchCandidate.target_record_id,
            func.count(MatchCandidate.id),
            func.count(CorrectionCandidateEvidence.candidate_id),
        )
        .outerjoin(
            CorrectionCandidateEvidence,
            CorrectionCandidateEvidence.candidate_id == MatchCandidate.id,
        )
        .filter(
            MatchCandidate.process_id == run.process_id,
            MatchCandidate.generation == run.generation,
            MatchCandidate.target_record_id.in_(
                [row.source_record_id for row in outcomes]
            ),
        )
        .group_by(MatchCandidate.target_record_id)
        .all()
    }
    for row in outcomes:
        if totals.get(row.source_record_id, (0, 0)) != (
            row.candidate_count,
            row.candidate_count,
        ):
            raise ValueError("Jumlah hasil dan bukti kandidat tidak sesuai")
    if outcomes:
        progress["last_validated_source_id"] = outcomes[-1].source_record_id
        progress["validated_rows"] += len(outcomes)
    elif progress["validated_rows"] != progress["total_rows"]:
        raise ValueError("Jumlah hasil koreksi tidak sesuai checkpoint")
    if progress["validated_rows"] == progress["total_rows"]:
        progress["stage"] = "publishing"


def advance_progress(
    db: Session,
    kind: CorrectionKind,
    process_id: int,
    run_id: int,
    revision: int,
    chunk_size: int,
) -> MatchingRun:
    """Commit one preparation, matching, validation, or publication transaction."""
    process, run = locked_run(db, kind, process_id, run_id)
    assert run.processing is not None
    if run.processing["revision"] != revision:
        raise HTTPException(
            409, "Progres telah berubah. Muat ulang sebelum melanjutkan."
        )
    if run.status == ProcessStatus.COMPLETED:
        return run
    if run.processing["state"] != "running":
        raise HTTPException(
            409, "Pemeriksaan dijeda. Pilih Lanjutkan pemeriksaan koreksi."
        )
    progress = dict(run.processing)
    started = monotonic()
    try:
        if progress["stage"] == "matching":
            assert process.target_batch_id is not None
            run_correction_matching(
                db, process_id, process.target_batch_id, run_id, chunk_size=chunk_size
            )
            return run
        if progress["stage"] == "preparing":
            progress["preparation"] = advance_preparation(
                db, process, progress.get("preparation")
            )
            if progress["preparation"]["phase"] == "ready":
                progress["stage"] = "matching"
        elif progress["stage"] == "validating":
            validate_chunk(db, run, progress, chunk_size)
        elif progress["stage"] == "publishing":
            run.status = process.matching_status = ProcessStatus.COMPLETED
            run.total_targets = process.total_targets = progress["total_rows"]
            run.matched_targets = process.matched_targets = progress["matched_rows"]
            process.unmatched_targets = (
                progress["total_rows"] - progress["matched_rows"]
            )
            process.current_generation, process.radius_meters = (
                run.generation,
                run.radius_meters,
            )
            process.review_status = ReviewStatus.IN_PROGRESS
            run.completed_at = process.completed_at = utc_now()
            progress.update(state="ready", stage="done")
        progress.update(
            revision=progress["revision"] + 1,
            updated_at=utc_now().isoformat(),
            elapsed_seconds=progress["elapsed_seconds"] + monotonic() - started,
        )
        run.processing = progress
        db.commit()
        return run
    except Exception as exc:
        db.rollback()
        try:
            process, run = locked_run(db, kind, process_id, run_id)
            saved = run.processing or {}
            run.processing = {
                **saved,
                "state": "failed",
                "error": "Bagian aktif belum tersimpan. Hasil sebelumnya tetap tersedia.",
                "revision": saved["revision"] + 1,
                "updated_at": utc_now().isoformat(),
            }
            run.status = process.matching_status = ProcessStatus.FAILED
            run.failure_code = "processing_failed"
            db.commit()
        except SQLAlchemyError:
            db.rollback()
        if isinstance(exc, SQLAlchemyError):
            raise
        raise HTTPException(
            500,
            "Pemeriksaan koreksi terhenti. Lanjutkan dari hasil terakhir yang tersimpan.",
        ) from exc
