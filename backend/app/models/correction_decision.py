"""Append-only correction choices, retained across matching generations."""

from datetime import datetime
from typing import Any, cast

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.correction import utc_now


class CorrectionDecision(Base):
    __tablename__ = "correction_decisions"
    __table_args__ = (UniqueConstraint("process_id", "target_record_id", "revision"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    process_id: Mapped[int] = mapped_column(
        ForeignKey("correction_checks.process_id"), index=True
    )
    target_record_id: Mapped[int] = mapped_column(
        ForeignKey("source_records.id"), index=True
    )
    generation: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer)
    candidate_id = cast(
        Mapped[int | None],
        Column(Integer, ForeignKey("match_candidates.id"), nullable=True),
    )
    request_key: Mapped[str] = mapped_column(String(64), unique=True)
    actor: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(String(1000))
    target_fields: Mapped[dict[str, Any]] = mapped_column(JSON)
    candidate: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
