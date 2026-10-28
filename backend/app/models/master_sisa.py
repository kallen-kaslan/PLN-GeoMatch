"""Master identity observations and immutable eligible source snapshots."""

from datetime import datetime
from typing import Any, cast

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Explicit nullable Columns avoid Union inference in SQLAlchemy 2.0.35 on Python 3.15.


class MasterSnapshot(Base):
    __tablename__ = "master_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ready: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=true(), nullable=False
    )
    master_batch_id: Mapped[int | None] = cast(
        Mapped[int | None], Column(ForeignKey("upload_batches.id"), nullable=True)
    )
    pdpj_batch_id: Mapped[int | None] = cast(
        Mapped[int | None], Column(ForeignKey("upload_batches.id"), nullable=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class MasterPreparation(Base):
    __tablename__ = "master_preparations"

    id: Mapped[int] = mapped_column(primary_key=True)
    signature: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    master_batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"))
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("master_snapshots.id"))
    pdpj_review_id: Mapped[int] = mapped_column(ForeignKey("pdpj_reviews.id"))
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    processing: Mapped[dict[str, Any]] = mapped_column(JSON)


class MasterPreparationIdentity(Base):
    __tablename__ = "master_preparation_identities"
    __table_args__ = (
        UniqueConstraint("preparation_id", "idpel"),
        Index("ix_preparation_identity_cursor", "preparation_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    preparation_id: Mapped[int] = mapped_column(ForeignKey("master_preparations.id"))
    idpel: Mapped[str] = mapped_column(String, nullable=False)
    base_source_id: Mapped[int | None] = cast(
        Mapped[int | None], Column(Integer, nullable=True)
    )
    dil_source_id: Mapped[int | None] = cast(
        Mapped[int | None], Column(Integer, nullable=True)
    )
    base_period: Mapped[str] = mapped_column(String, default="")
    dil_period: Mapped[str] = mapped_column(String, default="")


class MasterPreparationExcluded(Base):
    __tablename__ = "master_preparation_excluded"

    preparation_id: Mapped[int] = mapped_column(
        ForeignKey("master_preparations.id"), primary_key=True
    )
    idpel: Mapped[str] = mapped_column(String, primary_key=True)


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
    __table_args__ = (
        Index(
            "ix_master_sisa_records_snapshot_latitude_id",
            "snapshot_id",
            "latitude",
            "id",
        ),
    )

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
