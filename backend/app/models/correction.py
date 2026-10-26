"""Categorized correction checks, complete target outcomes, and candidate evidence."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    """Return a consistent naive UTC timestamp for the existing storage convention."""
    return datetime.now(UTC).replace(tzinfo=None)


class CorrectionCheck(Base):
    __tablename__ = "correction_checks"

    process_id: Mapped[int] = mapped_column(
        ForeignKey("reconciliation_processes.id"), primary_key=True
    )
    category: Mapped[str] = mapped_column(String, index=True)
    pdpj_review_id: Mapped[int] = mapped_column(ForeignKey("pdpj_reviews.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class CorrectionAttempt(Base):
    __tablename__ = "correction_attempts"

    run_id: Mapped[int] = mapped_column(
        ForeignKey("matching_runs.id"), primary_key=True
    )
    process_id: Mapped[int] = mapped_column(
        ForeignKey("correction_checks.process_id"), index=True
    )
    request_key: Mapped[str] = mapped_column(String(64), unique=True)
    actor: Mapped[str] = mapped_column(String(80))


class CorrectionTarget(Base):
    __tablename__ = "correction_targets"
    __table_args__ = (UniqueConstraint("run_id", "source_record_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("matching_runs.id"), index=True)
    source_record_id: Mapped[int] = mapped_column(
        ForeignKey("source_records.id"), index=True
    )
    fields: Mapped[dict[str, Any]] = mapped_column(JSON)
    identity_status: Mapped[str] = mapped_column(String)
    search_status: Mapped[str] = mapped_column(String, index=True)
    candidate_count: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)
    conflicts: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)


class CorrectionCandidateEvidence(Base):
    __tablename__ = "correction_candidate_evidence"

    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("match_candidates.id"), primary_key=True
    )
    master_record_id: Mapped[int] = mapped_column(ForeignKey("master_sisa_records.id"))
    fields: Mapped[dict[str, Any]] = mapped_column(JSON)
    observations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
