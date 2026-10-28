"""Processes, versioned search attempts, and their retained candidates."""

import enum
from datetime import datetime
from typing import Any, cast

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Explicit nullable Columns avoid Union inference in SQLAlchemy 2.0.35 on Python 3.15.


class ProcessStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    FINALIZED = "finalized"


class ReconciliationProcess(Base):
    __tablename__ = "reconciliation_processes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    process_name: Mapped[str] = mapped_column(String, nullable=False)
    radius_meters: Mapped[float] = mapped_column(Float, default=50.0, nullable=True)
    matching_status: Mapped[ProcessStatus] = mapped_column(
        Enum(ProcessStatus), default=ProcessStatus.QUEUED, nullable=True
    )
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus), default=ReviewStatus.NOT_STARTED, nullable=True
    )
    master_snapshot_id: Mapped[int | None] = cast(
        Mapped[int | None], Column(ForeignKey("master_snapshots.id"), nullable=True)
    )
    target_batch_id: Mapped[int | None] = cast(
        Mapped[int | None], Column(ForeignKey("upload_batches.id"), nullable=True)
    )
    current_generation: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_batches: Mapped[dict[str, Any] | None] = cast(
        Mapped[dict[str, Any] | None], Column(JSON, nullable=True)
    )
    total_targets: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    matched_targets: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    unmatched_targets: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=True
    )
    completed_at: Mapped[datetime | None] = cast(
        Mapped[datetime | None], Column(DateTime, nullable=True)
    )

    candidates: Mapped[list["MatchCandidate"]] = relationship(
        back_populates="process", cascade="all, delete-orphan"
    )
    runs: Mapped[list["MatchingRun"]] = relationship(cascade="all, delete-orphan")


class MatchingRun(Base):
    __tablename__ = "matching_runs"
    __table_args__ = (UniqueConstraint("process_id", "generation"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    process_id: Mapped[int] = mapped_column(
        ForeignKey("reconciliation_processes.id"), index=True, nullable=False
    )
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ProcessStatus] = mapped_column(
        Enum(ProcessStatus), default=ProcessStatus.QUEUED, nullable=False
    )
    failure_code: Mapped[str | None] = cast(
        Mapped[str | None], Column(String(40), nullable=True)
    )
    processing: Mapped[dict[str, Any] | None] = cast(
        Mapped[dict[str, Any] | None], Column(JSON, nullable=True)
    )
    radius_meters: Mapped[float] = mapped_column(Float, nullable=False)
    max_candidates: Mapped[int | None] = cast(
        Mapped[int | None], Column(Integer, nullable=True)
    )
    total_targets: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    matched_targets: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    completed_at: Mapped[datetime | None] = cast(
        Mapped[datetime | None], Column(DateTime, nullable=True)
    )


class MatchCandidate(Base):
    __tablename__ = "match_candidates"
    __table_args__ = (
        Index(
            "ix_match_candidates_process_generation_target_rank",
            "process_id",
            "generation",
            "target_record_id",
            "rank",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    process_id: Mapped[int] = mapped_column(
        ForeignKey("reconciliation_processes.id"), nullable=True
    )
    generation: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False, index=True
    )
    target_record_id: Mapped[int | None] = cast(
        Mapped[int | None], Column(ForeignKey("source_records.id"), nullable=True)
    )
    target_ref: Mapped[str] = mapped_column(String, nullable=False)
    target_lat: Mapped[float] = mapped_column(Float, nullable=False)
    target_lon: Mapped[float] = mapped_column(Float, nullable=False)
    candidate_idpel: Mapped[str] = mapped_column(String, nullable=False)
    candidate_nama: Mapped[str | None] = cast(
        Mapped[str | None], Column(String, nullable=True)
    )
    candidate_lat: Mapped[float] = mapped_column(Float, nullable=False)
    candidate_lon: Mapped[float] = mapped_column(Float, nullable=False)
    distance_meters: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, default=1, nullable=True)
    jenis_layanan: Mapped[str] = mapped_column(
        String, default="PASCABAYAR", nullable=True
    )
    validity_status: Mapped[str] = mapped_column(String, default="VALID", nullable=True)
    is_under_5m: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    is_accepted: Mapped[int] = mapped_column(Integer, default=0, nullable=True)

    process: Mapped[ReconciliationProcess] = relationship(back_populates="candidates")
