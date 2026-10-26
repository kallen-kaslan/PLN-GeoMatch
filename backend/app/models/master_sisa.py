"""Master identity observations and immutable eligible source snapshots."""

from datetime import datetime
from typing import cast

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Explicit nullable Columns avoid Union inference in SQLAlchemy 2.0.35 on Python 3.15.


class MasterSnapshot(Base):
    __tablename__ = "master_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    master_batch_id: Mapped[int | None] = cast(
        Mapped[int | None], Column(ForeignKey("upload_batches.id"), nullable=True)
    )
    pdpj_batch_id: Mapped[int | None] = cast(
        Mapped[int | None], Column(ForeignKey("upload_batches.id"), nullable=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class CleanedMasterRecord(Base):
    __tablename__ = "cleaned_master_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("upload_batches.id"), nullable=True
    )
    idpel: Mapped[str] = mapped_column(String, index=True, nullable=False)
    nama: Mapped[str | None] = cast(Mapped[str | None], Column(String, nullable=True))
    tarif: Mapped[str | None] = cast(Mapped[str | None], Column(String, nullable=True))
    daya: Mapped[int | None] = cast(Mapped[int | None], Column(Integer, nullable=True))
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    periode: Mapped[str | None] = cast(
        Mapped[str | None], Column(String, nullable=True)
    )
    is_excluded_by_pdpj: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=True
    )


class MasterSisaRecord(Base):
    __tablename__ = "master_sisa_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    snapshot_id: Mapped[int | None] = cast(
        Mapped[int | None],
        Column(ForeignKey("master_snapshots.id"), index=True, nullable=True),
    )
    source_record_id: Mapped[int | None] = cast(
        Mapped[int | None], Column(ForeignKey("source_records.id"), nullable=True)
    )
    idpel: Mapped[str] = mapped_column(String, index=True, nullable=False)
    nama: Mapped[str | None] = cast(Mapped[str | None], Column(String, nullable=True))
    latitude: Mapped[float | None] = cast(
        Mapped[float | None], Column(Float, nullable=True)
    )
    longitude: Mapped[float | None] = cast(
        Mapped[float | None], Column(Float, nullable=True)
    )
    tarif: Mapped[str | None] = cast(Mapped[str | None], Column(String, nullable=True))
    daya: Mapped[int | None] = cast(Mapped[int | None], Column(Integer, nullable=True))
    jenis_layanan: Mapped[str] = mapped_column(
        String, default="PASCABAYAR", nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=True
    )
