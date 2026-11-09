"""Filter saved candidate snapshots consistently across the correction workspace."""

from typing import Any

from app.models.matching import MatchCandidate, MatchingRun
from app.models.upload import SourceRecord
from app.modules.corrections.candidate_scope import candidate_scope
from fastapi import HTTPException
from sqlalchemy.orm import Session


def validate_radius(run: MatchingRun | None, radius: float | None) -> None:
    if radius is not None and (run is None or radius > run.radius_meters):
        raise HTTPException(409, "Perluas pemeriksaan terlebih dahulu untuk radius ini")


def has_candidate_in_radius(db: Session, run: MatchingRun, radius: float):
    # Rank 1 is the nearest persisted candidate. A single indexed lookup suffices.
    return (
        db.query(MatchCandidate.id)
        .filter(
            MatchCandidate.process_id == run.process_id,
            candidate_scope(run),
            MatchCandidate.target_record_id == SourceRecord.id,
            MatchCandidate.rank == 1,
            MatchCandidate.distance_meters <= radius,
        )
        .correlate(SourceRecord)
        .exists()
    )


def filtered_info(info: dict[str, Any], candidate_count: int) -> dict[str, Any]:
    if info["search_status"] in {"matched", "no_candidates"}:
        return {
            **info,
            "candidate_count": candidate_count,
            "search_status": "matched" if candidate_count else "no_candidates",
        }
    return info
