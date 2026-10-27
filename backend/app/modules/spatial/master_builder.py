"""Build a combined master while retaining identities without usable coordinates."""

import re
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.upload import BatchStatus, DatasetType, SourceRecord, UploadBatch
from app.modules.upload.normalization import (  # noqa: F401
    NORMALIZATION_VERSION,
    extract_standard_fields,
    normalize_column_name,
)
from app.performance import timed

MASTER_READ_CHUNK_ROWS = 400


def observation_period(value: str | None) -> tuple[date, str]:
    """Compare compact DIL months and ISO periods without changing source values."""
    text = value or ""
    match = re.fullmatch(r"(\d{4})[-/]?(\d{2})(?:[-/]?(\d{2}))?(?:[ T].*)?", text)
    if match:
        try:
            return date(int(match[1]), int(match[2]), int(match[3] or 1)), text
        except ValueError:
            pass
    return date.min, text


@timed("master.build")
def build_combined_master(
    db: Session,
    pascabayar_batch_ids: list[int],
    prabayar_batch_ids: list[int],
    dil_batch_ids: list[int] | None = None,
    *,
    commit: bool = True,
) -> dict[str, Any]:
    """Keep the latest observation per IDPEL, including incomplete locations."""
    deduplicated: dict[str, dict[str, Any]] = {}
    latest_dil: dict[str, dict[str, Any]] = {}
    observations: dict[str, list[dict[str, Any]]] = {}
    counts = {DatasetType.PASCABAYAR: 0, DatasetType.PRABAYAR: 0, DatasetType.DIL: 0}
    skipped = 0
    for batch_ids, dataset_type in (
        (pascabayar_batch_ids, DatasetType.PASCABAYAR),
        (prabayar_batch_ids, DatasetType.PRABAYAR),
        (dil_batch_ids or [], DatasetType.DIL),
    ):
        for batch_id in dict.fromkeys(batch_ids):
            batch = db.get(UploadBatch, batch_id)
            if (
                batch is None
                or batch.dataset_type != dataset_type
                or batch.status != BatchStatus.COMPLETED
            ):
                raise ValueError(
                    "Batch master tidak ditemukan, belum selesai, atau jenisnya tidak sesuai"
                )
            records = (
                db.query(SourceRecord)
                .filter(SourceRecord.batch_id == batch_id)
                .order_by(SourceRecord.id)
                .yield_per(MASTER_READ_CHUNK_ROWS)
            )
            for source_row, record in enumerate(records, start=2):
                counts[dataset_type] += 1
                if record.row_number is None:
                    record.row_number = source_row
                # Invalid, already-normalized imports cannot become candidates.
                # Retain legacy metadata backfills without parsing every rejected row.
                fields = (
                    extract_standard_fields(record.data or {}, batch.column_mapping)
                    if record.is_valid or record.normalized_data is None
                    else None
                )
                if fields is not None:
                    fields["tglbaca"] = fields["tglbaca"] or batch.period
                if record.normalized_data is None:
                    assert fields is not None
                    record.normalized_data = {
                        key: value
                        for key, value in fields.items()
                        if key != "validation_errors"
                    }
                if (source_row - 1) % MASTER_READ_CHUNK_ROWS == 0:
                    db.flush()
                if (
                    not record.is_valid
                    or fields is None
                    or not fields["idpel"]
                    or fields["validation_errors"]
                ):
                    skipped += 1
                    continue
                observations.setdefault(fields["idpel"], []).append(
                    {
                        "batch_id": batch.id,
                        "record_id": record.id,
                        "filename": batch.filename,
                        "row_number": record.row_number,
                        "source_sheet": batch.source_sheet,
                        "dataset_type": dataset_type.value,
                        "fields": {
                            key: value
                            for key, value in fields.items()
                            if key != "validation_errors"
                        },
                    }
                )
                fields.update(
                    jenis_pel=dataset_type.value.upper()
                    if dataset_type != DatasetType.DIL
                    else fields["jenis_pel"],
                    source_batch_id=batch.id,
                    source_record_id=record.id,
                    source_dataset_type=dataset_type.value,
                )
                destination = (
                    latest_dil if dataset_type == DatasetType.DIL else deduplicated
                )
                existing = destination.get(fields["idpel"])
                if existing is None or observation_period(
                    fields["tglbaca"]
                ) >= observation_period(existing["tglbaca"]):
                    destination[fields["idpel"]] = fields
            db.flush()

    for idpel, fields in latest_dil.items():
        existing = deduplicated.get(idpel)
        if existing is None:
            deduplicated[idpel] = fields
            continue
        # Supplement from the latest DIL source, after preserving every observation.
        # Known coordinates and the prepaid/postpaid service remain authoritative.
        for key, value in fields.items():
            if key not in {
                "lat",
                "lon",
                "source_batch_id",
                "source_record_id",
                "source_dataset_type",
                "validation_errors",
            } and existing.get(key) in (None, "", "-"):
                existing[key] = value
        if (
            (existing["lat"] is None or existing["lon"] is None)
            and fields["lat"] is not None
            and fields["lon"] is not None
        ):
            existing["lat"], existing["lon"] = fields["lat"], fields["lon"]

    master_batch = UploadBatch(
        filename=f"Master_Gabungan_{datetime.now(UTC).replace(tzinfo=None):%Y%m%d_%H%M%S}.csv",
        dataset_type=DatasetType.MASTER,
        status=BatchStatus.COMPLETED,
        total_rows=len(deduplicated),
        valid_rows=len(deduplicated),
        catalog_version=NORMALIZATION_VERSION,
    )
    db.add(master_batch)
    db.flush()
    pending = []
    for source_number, (idpel, fields) in enumerate(deduplicated.items(), start=2):
        data = {
            key: value for key, value in fields.items() if key != "validation_errors"
        }
        data.update(
            latitude=fields["lat"],
            longitude=fields["lon"],
            koordinat_x=fields["lon"],
            koordinat_y=fields["lat"],
        )
        data["source_observations"] = observations[idpel]
        pending.append(
            {
                "batch_id": master_batch.id,
                "row_number": source_number,
                "idpel": idpel,
                "data": data,
                "normalized_data": {
                    key: value
                    for key, value in data.items()
                    if key != "source_observations"
                },
            }
        )
        if len(pending) >= MASTER_READ_CHUNK_ROWS:
            db.bulk_insert_mappings(SourceRecord.__mapper__, pending)
            pending.clear()
    if pending:
        db.bulk_insert_mappings(SourceRecord.__mapper__, pending)
    if commit:
        db.commit()
    else:
        db.flush()
    return {
        "status": "success",
        "master_batch_id": master_batch.id,
        "total_pascabayar_raw": counts[DatasetType.PASCABAYAR],
        "total_prabayar_raw": counts[DatasetType.PRABAYAR],
        "total_dil_raw": counts[DatasetType.DIL],
        "total_master_clean": len(deduplicated),
        "incomplete_coordinates": sum(
            row["lat"] is None or row["lon"] is None for row in deduplicated.values()
        ),
        "skipped_invalid_rows": skipped,
        "removed_duplicates": sum(counts.values()) - skipped - len(deduplicated),
    }
