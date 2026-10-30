"""Read-only catalogue of uploaded prepaid, postpaid, and DIL source observations."""

import enum
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Query as ORMQuery
from sqlalchemy.orm import Session, load_only

from app.database import get_db
from app.models.upload import BatchStatus, DatasetType, SourceRecord, UploadBatch
from app.modules.master.summary import master_summary
from app.modules.upload.normalization import extract_standard_fields
from app.modules.upload.pagination import load_original_cells, source_page_ids

DbSession = Annotated[Session, Depends(get_db)]
router = APIRouter(prefix="/master", tags=["Data Master"])


class MasterKind(str, enum.Enum):
    PRABAYAR = "prabayar"
    PASCABAYAR = "pascabayar"
    DIL = "dil"


class RecordStatus(str, enum.Enum):
    ALL = "all"
    VALID = "valid"
    INVALID = "invalid"
    INCOMPLETE = "incomplete"


def source_batch(db: Session, kind: MasterKind, batch_id: int) -> UploadBatch:
    """Prevent a request from crossing source types or selecting a target batch."""
    batch = db.get(UploadBatch, batch_id)
    if batch is None or batch.dataset_type != DatasetType(kind.value):
        raise HTTPException(status_code=404, detail="Berkas master tidak ditemukan")
    return batch


def catalogue_query(db: Session, kind: MasterKind, batch_id: int | None) -> ORMQuery:
    """Only confirmed uploads are available as master reference data."""
    if batch_id is not None:
        source_batch(db, kind, batch_id)
    query = (
        db.query(SourceRecord)
        .join(UploadBatch, UploadBatch.id == SourceRecord.batch_id)
        .filter(
            UploadBatch.dataset_type == DatasetType(kind.value),
            UploadBatch.status == BatchStatus.COMPLETED,
        )
    )
    return (
        query.filter(SourceRecord.batch_id == batch_id)
        if batch_id is not None
        else query
    )


def incomplete_location() -> Any:
    """A single missing coordinate makes the location incomplete."""
    return or_(
        SourceRecord.normalized_data["lat"].as_float().is_(None),
        SourceRecord.normalized_data["lon"].as_float().is_(None),
    )


def batch_info(batch: UploadBatch) -> dict[str, Any]:
    """Expose upload provenance separately from customer attributes."""
    return {
        "id": batch.id,
        "filename": batch.filename,
        "dataset_type": batch.dataset_type,
        "status": batch.status,
        "period": batch.period,
        "source_sheet": batch.source_sheet,
        "total_rows": batch.total_rows,
        "valid_rows": batch.valid_rows,
        "error_rows": batch.error_rows,
        "created_at": batch.created_at,
    }


def record_info(record: SourceRecord, batch: UploadBatch) -> dict[str, Any]:
    """Serialize the same fields used by extraction, retaining unknown source codes."""
    fields = record.normalized_data or extract_standard_fields(
        record.data or {}, batch.column_mapping
    )
    return {
        "id": record.id,
        "batch_id": batch.id,
        "filename": batch.filename,
        "source_sheet": batch.source_sheet,
        "row_number": record.row_number,
        "period": fields.get("tglbaca") or batch.period,
        "fields": fields,
        "is_valid": record.is_valid,
        "validation_errors": record.validation_errors or [],
        "coordinates_complete": fields.get("lat") is not None
        and fields.get("lon") is not None,
    }


@router.get("/{kind}/batches")
def list_master_batches(kind: MasterKind, db: DbSession) -> list[dict[str, Any]]:
    """List uploaded files, including those awaiting mapping so import can resume."""
    return [
        batch_info(batch)
        for batch in db.query(UploadBatch)
        .filter(UploadBatch.dataset_type == DatasetType(kind.value))
        .order_by(UploadBatch.created_at.desc(), UploadBatch.id.desc())
        .all()
    ]


@router.get("/{kind}/batches/{batch_id}")
def get_master_batch(kind: MasterKind, batch_id: int, db: DbSession) -> dict[str, Any]:
    """Return saved headers and preview rows for a resumable column-mapping form."""
    batch = source_batch(db, kind, batch_id)
    rows = (
        db.query(SourceRecord)
        .filter(SourceRecord.batch_id == batch.id)
        .order_by(SourceRecord.id)
        .limit(5)
        .all()
    )
    return {
        **batch_info(batch),
        "column_mapping": batch.column_mapping or {},
        "headers": list((rows[0].data or {}).keys()) if rows else [],
        "preview": [record.data for record in rows],
        "row_numbers": [record.row_number for record in rows],
    }


@router.get("/{kind}/summary")
def get_master_summary(
    kind: MasterKind,
    db: DbSession,
    batch_id: int | None = Query(None, gt=0),
    details: bool = True,
) -> dict[str, Any]:
    """Restore stored totals first; cache exact counts for the selected source set."""
    if batch_id is not None:
        source_batch(db, kind, batch_id)
    return master_summary(db, DatasetType(kind.value), batch_id, details)


@router.get("/{kind}/records")
def list_master_records(
    kind: MasterKind,
    db: DbSession,
    batch_id: int | None = Query(None, gt=0),
    q: str = Query("", max_length=120),
    status: RecordStatus = RecordStatus.ALL,
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
) -> dict[str, Any]:
    """Paginate source observations without collapsing repeated IDPEL or periods."""
    query = catalogue_query(db, kind, batch_id)
    if q.strip():
        escaped = (
            q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        pattern = f"%{escaped}%"
        query = query.filter(
            or_(
                SourceRecord.idpel.ilike(pattern, escape="\\"),
                *(
                    SourceRecord.normalized_data[field]
                    .as_string()
                    .ilike(pattern, escape="\\")
                    for field in (
                        "nama",
                        "kode_dil",
                        "kode_dlpd",
                        "kddk",
                        "kode_gardu",
                        "target_ref",
                        "nomor_meter_kwh",
                        "nomor_meter_prepaid",
                    )
                ),
            )
        )
    if status == RecordStatus.VALID:
        query = query.filter(SourceRecord.is_valid.is_(True))
    elif status == RecordStatus.INVALID:
        query = query.filter(SourceRecord.is_valid.is_(False))
    elif status == RecordStatus.INCOMPLETE:
        query = query.filter(SourceRecord.is_valid.is_(True), incomplete_location())
    selected_batches = db.query(UploadBatch).filter(
        UploadBatch.dataset_type == DatasetType(kind.value),
        UploadBatch.status == BatchStatus.COMPLETED,
    )
    if batch_id is not None:
        selected_batches = selected_batches.filter(UploadBatch.id == batch_id)
    batches = {batch.id: batch for batch in selected_batches.all()}
    total, identities = source_page_ids(
        db,
        query,
        list(batches),
        skip,
        limit,
        unfiltered=not q.strip() and status == RecordStatus.ALL,
        known_totals={value: batch.total_rows for value, batch in batches.items()},
    )
    records = (
        db.query(SourceRecord)
        .filter(SourceRecord.id.in_(identities))
        .options(
            load_only(
                SourceRecord.id,
                SourceRecord.batch_id,
                SourceRecord.row_number,
                SourceRecord.normalized_data,
                SourceRecord.is_valid,
                SourceRecord.validation_errors,
            )
        )
        .order_by(SourceRecord.batch_id.desc(), SourceRecord.id)
        .all()
        if identities
        else []
    )
    load_original_cells(
        db, [record.id for record in records if not record.normalized_data]
    )
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [record_info(record, batches[record.batch_id]) for record in records],
    }


@router.get("/{kind}/records/{record_id}")
def get_master_record(
    kind: MasterKind, record_id: int, db: DbSession
) -> dict[str, Any]:
    """Show original cells alongside mapped values and exact source metadata."""
    record = db.get(SourceRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Baris master tidak ditemukan")
    batch = source_batch(db, kind, record.batch_id)
    return {
        **record_info(record, batch),
        "raw_data": record.data,
        "column_mapping": batch.column_mapping or {},
        "batch_status": batch.status,
    }
