"""Persist exact aggregate counts without storing customer identities."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class MasterSummaryCache(Base):
    __tablename__ = "master_summary_caches"

    signature: Mapped[str] = mapped_column(String(64), primary_key=True)
    counts: Mapped[dict[str, Any]] = mapped_column(JSON)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
