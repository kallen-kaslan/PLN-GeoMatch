"""Track completed repairs without rewriting historical matching evidence."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.correction import utc_now


class CoordinateRepair(Base):
    __tablename__ = "coordinate_repairs"
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("upload_batches.id"), primary_key=True
    )
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    rows_changed: Mapped[int] = mapped_column(Integer)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
