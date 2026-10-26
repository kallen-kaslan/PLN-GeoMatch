"""Recover rejected X/Y pairs in bounded chunks; original cells and snapshots stay intact."""

from collections.abc import Callable
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from app.models.coordinate_repair import CoordinateRepair
from app.models.upload import BatchStatus, DatasetType, SourceRecord, UploadBatch
from app.modules.upload.normalization import (
    coordinate_source_columns,
    extract_standard_fields,
    is_xy_pair,
    normalize_column_name,
    validate_fields,
)

REPAIR_VERSION = 1
REPAIR_CHUNK_ROWS = 1000


def repair_xy_coordinates(
    connection: Connection,
    batch_ids: list[int] | None = None,
    progress: Callable[[int, int, int], None] | None = None,
) -> dict[int, int]:
    """Repair source fields once per batch, retaining every historical review/run snapshot."""
    repairs = cast(sa.Table, CoordinateRepair.__table__)
    repairs.create(connection, checkfirst=True)
    batches, records = (
        cast(sa.Table, UploadBatch.__table__),
        cast(sa.Table, SourceRecord.__table__),
    )
    query = sa.select(batches).where(
        batches.c.status == BatchStatus.COMPLETED,
        batches.c.dataset_type != DatasetType.MASTER,
        ~sa.exists(
            sa.select(repairs.c.batch_id).where(
                repairs.c.batch_id == batches.c.id,
                repairs.c.version == REPAIR_VERSION,
            )
        ),
    )
    if batch_ids is not None:
        query = query.where(batches.c.id.in_(batch_ids))
    results: dict[int, int] = {}
    for batch in connection.execute(query.order_by(batches.c.id)).mappings().all():
        sample = connection.execute(
            sa.select(records.c.data)
            .where(records.c.batch_id == batch["id"])
            .order_by(records.c.id)
            .limit(1)
        ).scalar()
        changed = scanned = 0
        headers = {normalize_column_name(key) for key in (sample or {})}
        has_xy_headers = bool(
            headers & {"x", "koordinatx"} and headers & {"y", "koordinaty"}
        )
        if sample and (
            is_xy_pair(coordinate_source_columns(sample, batch["column_mapping"]))
            or has_xy_headers
        ):
            last_id = 0
            while True:
                chunk = (
                    connection.execute(
                        sa.select(records)
                        .where(
                            records.c.batch_id == batch["id"],
                            records.c.id > last_id,
                            records.c.normalized_data["lat"].as_float().is_(None),
                        )
                        .order_by(records.c.id)
                        .limit(REPAIR_CHUNK_ROWS)
                    )
                    .mappings()
                    .all()
                )
                if not chunk:
                    break
                updates: list[dict[str, Any]] = []
                for record in chunk:
                    scanned += 1
                    fields = extract_standard_fields(
                        record["data"] or {}, batch["column_mapping"]
                    )
                    if not fields.get("_coordinate_axes_swapped"):
                        continue
                    fields["tglbaca"] = fields["tglbaca"] or batch["period"]
                    errors = validate_fields(fields, batch["dataset_type"])
                    updates.append(
                        {
                            "_record_id": record["id"],
                            "idpel": fields["idpel"],
                            "normalized_data": {
                                key: value
                                for key, value in fields.items()
                                if key != "validation_errors"
                            },
                            "is_valid": not errors,
                            "validation_errors": errors,
                        }
                    )
                if updates:
                    connection.execute(
                        sa.update(records)
                        .where(records.c.id == sa.bindparam("_record_id"))
                        .values(
                            idpel=sa.bindparam("idpel"),
                            normalized_data=sa.bindparam("normalized_data"),
                            is_valid=sa.bindparam("is_valid"),
                            validation_errors=sa.bindparam("validation_errors"),
                        ),
                        updates,
                    )
                    changed += len(updates)
                last_id = chunk[-1]["id"]
                if progress:
                    progress(batch["id"], scanned, changed)
        if changed:
            valid = connection.execute(
                sa.select(sa.func.count())
                .select_from(records)
                .where(
                    records.c.batch_id == batch["id"],
                    records.c.is_valid.is_(True),
                )
            ).scalar_one()
            total = connection.execute(
                sa.select(sa.func.count())
                .select_from(records)
                .where(records.c.batch_id == batch["id"])
            ).scalar_one()
            connection.execute(
                sa.update(batches)
                .where(batches.c.id == batch["id"])
                .values(valid_rows=valid, error_rows=total - valid)
            )
        connection.execute(
            sa.insert(repairs).values(
                batch_id=batch["id"], version=REPAIR_VERSION, rows_changed=changed
            )
        )
        results[batch["id"]] = changed
    return results
