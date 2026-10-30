"""Show imported totals immediately; persist exact coordinate and identity counts."""

import hashlib
import json
from typing import Any

from sqlalchemy import and_, func, or_, select, union_all
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.coordinate_repair import CoordinateRepair
from app.models.master_summary import MasterSummaryCache
from app.models.upload import BatchStatus, DatasetType, SourceRecord, UploadBatch
from app.modules.upload.normalization import NORMALIZATION_VERSION

COUNT_KEYS = (
    "total_rows",
    "valid_rows",
    "invalid_rows",
    "incomplete_coordinates",
    "unique_idpels",
    "duplicate_observations",
)
EMPTY_COUNTS = dict.fromkeys(COUNT_KEYS, 0)


def signature(kind: DatasetType, specs: list[dict[str, Any]]) -> str:
    encoded = json.dumps(
        {
            "algorithm": 1,
            "normalization": NORMALIZATION_VERSION,
            "kind": kind.value,
            "sources": specs,
        },
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def stored_counts(db: Session, key: str, values: dict[str, Any]) -> None:
    if db.get(MasterSummaryCache, key) is not None:
        return
    try:
        with db.begin_nested():
            db.add(MasterSummaryCache(signature=key, counts=values))
            db.flush()
    except IntegrityError:
        if db.get(MasterSummaryCache, key) is None:
            raise


def batch_counts(db: Session, batch_ids: list[int]) -> dict[int, dict[str, Any]]:
    """One pass fills counts for every missing file, including valid-only uniqueness."""
    incomplete = or_(
        SourceRecord.normalized_data["lat"].as_float().is_(None),
        SourceRecord.normalized_data["lon"].as_float().is_(None),
    )
    result = {}
    for batch_id, total, valid, invalid, missing, unique in (
        db.query(
            SourceRecord.batch_id,
            func.count(SourceRecord.id),
            func.count(SourceRecord.id).filter(SourceRecord.is_valid.is_(True)),
            func.count(SourceRecord.id).filter(SourceRecord.is_valid.is_(False)),
            func.count(SourceRecord.id).filter(
                and_(SourceRecord.is_valid.is_(True), incomplete)
            ),
            func.count(func.distinct(SourceRecord.idpel)).filter(
                SourceRecord.is_valid.is_(True)
            ),
        )
        .filter(SourceRecord.batch_id.in_(batch_ids))
        .group_by(SourceRecord.batch_id)
    ):
        result[batch_id] = dict(
            zip(COUNT_KEYS, (total, valid, invalid, missing, unique, valid - unique))
        )
    return {
        batch_id: result.get(batch_id, dict(EMPTY_COUNTS)) for batch_id in batch_ids
    }


def master_summary(
    db: Session, kind: DatasetType, batch_id: int | None, details: bool
) -> dict[str, Any]:
    batches_query = db.query(UploadBatch).filter(UploadBatch.dataset_type == kind)
    if batch_id is not None:
        batches_query = batches_query.filter(UploadBatch.id == batch_id)
    batches = batches_query.order_by(UploadBatch.id).all()
    active = [batch for batch in batches if batch.status == BatchStatus.COMPLETED]
    repairs: dict[int, list[Any]] = {}
    if active:
        for repair in db.query(CoordinateRepair).filter(
            CoordinateRepair.batch_id.in_([batch.id for batch in active])
        ):
            repairs.setdefault(repair.batch_id, []).append(
                [repair.version, repair.rows_changed, repair.completed_at.isoformat()]
            )
    specs = [
        {
            "id": batch.id,
            "created_at": batch.created_at.isoformat() if batch.created_at else None,
            "mapping": batch.column_mapping,
            "period": batch.period,
            "catalog_version": batch.catalog_version,
            "total_rows": batch.total_rows,
            "valid_rows": batch.valid_rows,
            "error_rows": batch.error_rows,
            "repairs": sorted(repairs.get(batch.id, [])),
        }
        for batch in active
    ]
    key = signature(kind, specs)
    base = {
        "dataset_type": kind.value,
        "ready_files": len(active),
        "pending_files": sum(
            batch.status is not None and batch.status != BatchStatus.COMPLETED
            for batch in batches
        ),
        "source_signature": key,
    }
    if not active:
        return {**base, **EMPTY_COUNTS, "statistics_ready": True}
    cached = db.get(MasterSummaryCache, key)
    if cached is not None:
        return {**base, **cached.counts, "statistics_ready": True}
    keys = {batch.id: signature(kind, [spec]) for batch, spec in zip(active, specs)}
    by_batch = {
        value.signature: value.counts
        for value in db.query(MasterSummaryCache).filter(
            MasterSummaryCache.signature.in_(list(keys.values()))
        )
    }
    counts = {
        batch.id: by_batch[keys[batch.id]]
        for batch in active
        if keys[batch.id] in by_batch
    }
    if not details:
        basic: dict[str, Any] = {name: None for name in COUNT_KEYS}
        imported = []
        for batch in active:
            if batch.id in counts:
                imported.append(counts[batch.id])
            elif (
                batch.total_rows
                and batch.valid_rows is not None
                and batch.error_rows is not None
                and batch.total_rows == batch.valid_rows + batch.error_rows
            ):
                imported.append(
                    {
                        "total_rows": batch.total_rows,
                        "valid_rows": batch.valid_rows,
                        "invalid_rows": batch.error_rows,
                    }
                )
        if len(imported) == len(active):
            for name in COUNT_KEYS[:3]:
                basic[name] = sum(item[name] for item in imported)
        if len(counts) == len(active):
            basic["incomplete_coordinates"] = sum(
                item["incomplete_coordinates"] for item in counts.values()
            )
        return {**base, **basic, "statistics_ready": False}
    missing_ids = [batch.id for batch in active if batch.id not in counts]
    if missing_ids:
        counts.update(batch_counts(db, missing_ids))
    combined = {
        name: sum(item[name] for item in counts.values()) for name in COUNT_KEYS[:4]
    }
    if len(active) == 1:
        unique = counts[active[0].id]["unique_idpels"]
    else:
        observations = []
        for batch in active:
            query = select(SourceRecord.idpel).where(SourceRecord.batch_id == batch.id)
            # All-valid files can use the existing covering batch/IDPEL index.
            if counts[batch.id]["valid_rows"] != counts[batch.id]["total_rows"]:
                query = query.where(SourceRecord.is_valid.is_(True))
            observations.append(query)
        identities = union_all(*observations).subquery()
        unique = db.execute(
            select(func.count(func.distinct(identities.c.idpel)))
        ).scalar_one()
    combined.update(
        unique_idpels=unique, duplicate_observations=combined["valid_rows"] - unique
    )
    for batch in active:
        stored_counts(db, keys[batch.id], counts[batch.id])
    stored_counts(db, key, combined)
    db.commit()
    return {**base, **combined, "statistics_ready": True}
