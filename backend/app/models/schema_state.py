"""Durable checkpoints for completed compatibility upgrades, not user data."""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SchemaState(Base):
    __tablename__ = "app_schema_state"

    stage: Mapped[str] = mapped_column(String(80), primary_key=True)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
