"""Count stored correction outcomes at a radius without searching master again."""

from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.correction import CorrectionTarget
from app.models.matching import MatchCandidate, MatchingRun, ProcessStatus
from app.models.upload import SourceRecord, UploadBatch
from app.modules.corrections.service import CorrectionKind, check_process, selected_run


def radius_summary(
    db: Session,
    kind: CorrectionKind,
    process_id: int,
    generation: int | None,
    radius: float,
) -> dict[str, Any]:
    """Count targets once, retain blocked statuses, and compare with saved results."""
    _, process = check_process(db, kind, process_id)
    run = selected_run(db, process, generation, include_partial=True)
    if run is None or radius > run.radius_meters:
        raise HTTPException(409, "Perluas pemeriksaan terlebih dahulu untuk radius ini")
    cursor = (run.processing or {}).get("last_source_id")

    def statuses(run_id: int) -> dict[str, int]:
        query = db.query(
            CorrectionTarget.search_status, func.count(CorrectionTarget.id)
        ).filter(CorrectionTarget.run_id == run_id)
        if run_id == run.id and cursor is not None:
            query = query.filter(CorrectionTarget.source_record_id <= cursor)
        return {
            status: count
            for status, count in query.group_by(CorrectionTarget.search_status).all()
        }

    counts = statuses(run.id)
    candidates = (
        db.query(
            MatchCandidate.target_record_id.label("source_record_id"),
            func.count(MatchCandidate.id).label("candidate_count"),
        )
        .join(
            CorrectionTarget,
            (CorrectionTarget.source_record_id == MatchCandidate.target_record_id)
            & (CorrectionTarget.run_id == run.id),
        )
        .filter(
            MatchCandidate.process_id == process.id,
            MatchCandidate.generation == run.generation,
            MatchCandidate.distance_meters <= radius,
            CorrectionTarget.search_status == "matched",
        )
        .group_by(MatchCandidate.target_record_id)
    )
    if cursor is not None:
        # A later chunk may commit between SELECTs. Keep every count on this
        # response's durable cursor and revision instead of mixing checkpoints.
        candidates = candidates.filter(MatchCandidate.target_record_id <= cursor)
    by_target = {record: count for record, count in candidates.all()}
    previous = (
        db.query(MatchingRun)
        .filter(
            MatchingRun.process_id == process.id,
            MatchingRun.generation < run.generation,
            MatchingRun.status == ProcessStatus.COMPLETED,
        )
        .order_by(MatchingRun.generation.desc())
        .first()
        if radius == run.radius_meters
        else None
    )
    baseline = previous or run
    baseline_counts = statuses(baseline.id) if baseline.id != run.id else counts
    matched_targets = candidates.subquery()
    newly_matched = (
        db.query(func.count(CorrectionTarget.id))
        .join(
            matched_targets,
            matched_targets.c.source_record_id == CorrectionTarget.source_record_id,
        )
        .filter(
            CorrectionTarget.run_id == baseline.id,
            CorrectionTarget.search_status == "no_candidates",
        )
        .scalar()
        or 0
    )
    batch = db.get(UploadBatch, process.target_batch_id)
    assert batch is not None
    total = batch.total_rows or (
        db.query(func.count(SourceRecord.id))
        .filter(SourceRecord.batch_id == batch.id)
        .scalar()
    )
    saved = sum(counts.values())
    eligible = counts.get("matched", 0) + counts.get("no_candidates", 0)
    return {
        "process_id": process.id,
        "generation": run.generation,
        "revision": (run.processing or {}).get("revision", 0),
        "radius_meters": radius,
        "stored_radius_meters": run.radius_meters,
        "partial": run.status != ProcessStatus.COMPLETED,
        "total_rows": total,
        "saved_rows": saved,
        "not_checked": max(0, total - saved),
        "matched": len(by_target),
        "no_candidates": eligible - len(by_target),
        "pdpj_conflicts": counts.get("pdpj_conflict", 0),
        "invalid_data": counts.get("invalid_data", 0),
        "incomplete_coordinates": counts.get("incomplete_coordinates", 0),
        "candidate_total": sum(by_target.values()),
        "candidate_counts": by_target,
        "newly_matched": newly_matched,
        "baseline": {
            "generation": baseline.generation,
            "radius_meters": baseline.radius_meters,
            "matched": baseline_counts.get("matched", 0),
            "no_candidates": baseline_counts.get("no_candidates", 0),
            "saved_rows": sum(baseline_counts.values()),
        },
    }
