"""Versioned PDPJ validation, source recommendations, and append-only change history."""

from datetime import datetime
from typing import Any, cast

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PdpjReview(Base):
    __tablename__ = "pdpj_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), index=True)
    master_batch_ids: Mapped[list[int]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, default="in_progress")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = cast(
        Mapped[datetime | None], Column(DateTime, nullable=True)
    )
    completed_by: Mapped[str] = mapped_column(String, default="")
    processing: Mapped[dict[str, Any] | None] = cast(
        Mapped[dict[str, Any] | None], Column(JSON, nullable=True)
    )


class PdpjRow(Base):
    __tablename__ = "pdpj_rows"
    __table_args__ = (UniqueConstraint("review_id", "source_record_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("pdpj_reviews.id"), index=True)
    source_record_id: Mapped[int] = mapped_column(ForeignKey("source_records.id"))
    row_number: Mapped[int] = mapped_column(Integer)
    original_fields: Mapped[dict[str, Any]] = mapped_column(JSON)
    current_fields: Mapped[dict[str, Any]] = mapped_column(JSON)
    existence: Mapped[str] = mapped_column(String)
    issues: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)
    warnings: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)
    recommendation_count: Mapped[int] = mapped_column(Integer, default=0)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    exception: Mapped[bool] = mapped_column(Boolean, default=False)
    exception_reason: Mapped[str] = mapped_column(String, default="")


Index(
    "ix_pdpj_rows_review_identity",
    PdpjRow.review_id,
    PdpjRow.current_fields["idpel"].as_string(),
)


class PdpjRecommendation(Base):
    __tablename__ = "pdpj_recommendations"
    __table_args__ = (UniqueConstraint("row_id", "source_record_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    row_id: Mapped[int] = mapped_column(ForeignKey("pdpj_rows.id"), index=True)
    source_record_id: Mapped[int] = mapped_column(ForeignKey("source_records.id"))
    fields: Mapped[dict[str, Any]] = mapped_column(JSON)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON)
    validation_errors: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)


class PdpjChange(Base):
    __tablename__ = "pdpj_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    row_id: Mapped[int] = mapped_column(ForeignKey("pdpj_rows.id"), index=True)
    action: Mapped[str] = mapped_column(String)
    actor: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(String, default="")
    before: Mapped[dict[str, Any]] = mapped_column(JSON)
    after: Mapped[dict[str, Any]] = mapped_column(JSON)
    sources: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
