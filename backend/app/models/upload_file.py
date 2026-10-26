"""Original file history is separate from validated reference batches."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.correction import utc_now


class UploadFileArchive(Base):
    __tablename__ = "upload_file_archives"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    storage_key: Mapped[str] = mapped_column(String(32), unique=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    sheet_names: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class UploadSheetImport(Base):
    __tablename__ = "upload_sheet_imports"
    __table_args__ = (
        UniqueConstraint("file_id", "dataset_type", "sheet_key", "period_key"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    file_id: Mapped[int] = mapped_column(
        ForeignKey("upload_file_archives.id"), index=True
    )
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), unique=True)
    dataset_type: Mapped[str] = mapped_column(String)
    sheet_key: Mapped[str] = mapped_column(String)
    period_key: Mapped[str] = mapped_column(String)
