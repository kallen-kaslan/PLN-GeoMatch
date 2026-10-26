"""Raw uploads and validation metadata; source cells are never overwritten."""

import enum
from datetime import datetime
from typing import Any, cast

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Explicit nullable Columns avoid Union inference in SQLAlchemy 2.0.35 on Python 3.15.


class BatchStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    NEEDS_MAPPING = "needs_mapping"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DatasetType(str, enum.Enum):
    PASCABAYAR = "pascabayar"
    PRABAYAR = "prabayar"
    MASTER = "master"
    DIL = "dil"
    PDPJ = "pdpj"
    KOORDINAT_KOSONG = "koordinat_kosong"
    TARGET = "target"
    IDPEL_TIDAK_KETEMU = "idpel_tidak_ketemu"
    IDPEL_KOSONG = "idpel_kosong"


class UploadBatch(Base):
    __tablename__ = "upload_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String, nullable=True)
    dataset_type: Mapped[DatasetType] = mapped_column(Enum(DatasetType), nullable=True)
    status: Mapped[BatchStatus] = mapped_column(
        Enum(BatchStatus), default=BatchStatus.UPLOADED, nullable=True
    )
    column_mapping: Mapped[dict[str, str] | None] = cast(
        Mapped[dict[str, str] | None], Column(JSON, nullable=True)
    )
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    error_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=True
    )
    period: Mapped[str | None] = cast(Mapped[str | None], Column(String, nullable=True))
    source_sheet: Mapped[str | None] = cast(
        Mapped[str | None], Column(String, nullable=True)
    )

    records: Mapped[list["SourceRecord"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class SourceRecord(Base):
    __tablename__ = "source_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("upload_batches.id"), nullable=True
    )
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=True)
    idpel: Mapped[str | None] = cast(
        Mapped[str | None], Column(String, index=True, nullable=True)
    )
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    validation_errors: Mapped[list[dict[str, str]] | None] = cast(
        Mapped[list[dict[str, str]] | None], Column(JSON, nullable=True)
    )
    row_number: Mapped[int | None] = cast(
        Mapped[int | None], Column(Integer, nullable=True)
    )
    normalized_data: Mapped[dict[str, Any] | None] = cast(
        Mapped[dict[str, Any] | None], Column(JSON, nullable=True)
    )

    batch: Mapped[UploadBatch] = relationship(back_populates="records")
