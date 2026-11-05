"""Durable nearest-eligible distances, separate from candidate search results."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.correction import utc_now


class RadiusAnalysis(Base):
    __tablename__ = "correction_radius_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), index=True)
    pdpj_review_id: Mapped[int] = mapped_column(ForeignKey("pdpj_reviews.id"))
    process_id: Mapped[int] = mapped_column(ForeignKey("reconciliation_processes.id"), unique=True)
    request_key: Mapped[str] = mapped_column(String(64), unique=True)
    actor: Mapped[str] = mapped_column(String(80))
    state: Mapped[str] = mapped_column(String(20), default="running")
    stage: Mapped[str] = mapped_column(String(20), default="preparing")
    revision: Mapped[int] = mapped_column(default=1)
    last_source_id: Mapped[int] = mapped_column(default=0)
    processed_rows: Mapped[int] = mapped_column(default=0)
    total_rows: Mapped[int] = mapped_column(default=0)
    progress: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class RadiusAnalysisRow(Base):
    __tablename__ = "correction_radius_analysis_rows"
    __table_args__ = (
        UniqueConstraint("analysis_id", "source_record_id"),
        Index("ix_radius_analysis_distance", "analysis_id", "distance_meters"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("correction_radius_analyses.id"), index=True)
    source_record_id: Mapped[int] = mapped_column(ForeignKey("source_records.id"))
    distance_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    candidate_idpel: Mapped[str | None] = mapped_column(String, nullable=True)
    observation_source_id: Mapped[int | None] = mapped_column(ForeignKey("source_records.id"), nullable=True)
    issue: Mapped[str | None] = mapped_column(String(30), nullable=True)
