"""Add the master catalogue metadata and derive a searchable copy of legacy cells."""

from typing import cast

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import Connection

from app.performance import logger, timed


@timed("startup.catalog")
def upgrade_master_catalog(connection: Connection) -> None:
    """Retain original cells and backfill source row numbers and mapped fields."""
    from app.models.upload import BatchStatus, DatasetType, SourceRecord, UploadBatch
    from app.modules.upload.normalization import (
        NORMALIZATION_VERSION,
        extract_standard_fields,
        validate_fields,
    )

    if connection.dialect.name == "postgresql":
        connection.execute(
            sa.text("ALTER TYPE datasettype ADD VALUE IF NOT EXISTS 'DIL'")
        )
    if connection.dialect.name == "sqlite":
        driver = connection.connection.driver_connection
        assert driver is not None
        if not driver.in_transaction:
            connection.exec_driver_sql("BEGIN")
    operations = Operations(MigrationContext.configure(connection))
    for table_name, new_columns in {
        "upload_batches": [
            sa.Column("period", sa.String(), nullable=True),
            sa.Column("source_sheet", sa.String(), nullable=True),
            sa.Column("catalog_version", sa.Integer(), nullable=True),
        ],
        "source_records": [
            sa.Column("row_number", sa.Integer(), nullable=True),
            sa.Column("normalized_data", sa.JSON(), nullable=True),
        ],
    }.items():
        existing = {
            column["name"] for column in sa.inspect(connection).get_columns(table_name)
        }
        for column in new_columns:
            if column.name not in existing:
                operations.add_column(table_name, column)

    batches = cast(sa.Table, UploadBatch.__table__)
    records = cast(sa.Table, SourceRecord.__table__)
    pending_batches = (
        connection.execute(
            sa.select(batches)
            .where(
                sa.or_(
                    batches.c.catalog_version.is_(None),
                    sa.and_(
                        batches.c.status == BatchStatus.COMPLETED,
                        batches.c.catalog_version != NORMALIZATION_VERSION,
                    ),
                )
            )
            .order_by(batches.c.id)
        )
        .mappings()
        .all()
    )
    for batch in pending_batches:
        logger.info("startup catalog_batch_id=%s status=checking", batch["id"])
        last_id, position, changed = 0, 2, False
        while True:
            # Read scalar metadata in primary-key order. Avoid decoding every raw
            # JSON row or walking the IDPEL index for already-current exports.
            chunk = (
                connection.execute(
                    sa.select(
                        records.c.id,
                        records.c.row_number,
                        records.c.normalized_data["_normalization_version"]
                        .as_integer()
                        .label("version"),
                    )
                    .where(records.c.batch_id == batch["id"], records.c.id > last_id)
                    .order_by(records.c.id)
                    .limit(2000)
                )
                .mappings()
                .all()
            )
            if not chunk:
                break
            outdated = [
                row["id"]
                for row in chunk
                if batch["status"] == BatchStatus.COMPLETED
                and row["version"] != NORMALIZATION_VERSION
            ]
            originals = {}
            for offset in range(0, len(outdated), 400):
                originals.update(
                    {
                        row["id"]: row["data"]
                        for row in connection.execute(
                            sa.select(records.c.id, records.c.data).where(
                                records.c.id.in_(outdated[offset : offset + 400])
                            )
                        ).mappings()
                    }
                )
            for record in chunk:
                values = {}
                if record["row_number"] is None:
                    values["row_number"] = position
                position += 1
                if record["id"] in originals:
                    fields = extract_standard_fields(
                        originals[record["id"]] or {}, batch["column_mapping"]
                    )
                    fields["tglbaca"] = fields["tglbaca"] or batch["period"]
                    values["normalized_data"] = {
                        key: value
                        for key, value in fields.items()
                        if key != "validation_errors"
                    }
                    if batch["dataset_type"] in {
                        DatasetType.PASCABAYAR,
                        DatasetType.PRABAYAR,
                        DatasetType.DIL,
                    }:
                        errors = validate_fields(fields, batch["dataset_type"])
                        values.update(
                            idpel=fields["idpel"],
                            is_valid=not errors,
                            validation_errors=errors,
                        )
                if values:
                    connection.execute(
                        sa.update(records)
                        .where(records.c.id == record["id"])
                        .values(**values)
                    )
                    changed = True
            last_id = chunk[-1]["id"]
        version = (
            NORMALIZATION_VERSION if batch["status"] == BatchStatus.COMPLETED else 0
        )
        connection.execute(
            sa.update(batches)
            .where(batches.c.id == batch["id"])
            .values(catalog_version=version)
        )
        logger.info(
            "startup catalog_batch_id=%s status=completed rows_checked=%s changed=%s",
            batch["id"],
            position - 2,
            changed,
        )
