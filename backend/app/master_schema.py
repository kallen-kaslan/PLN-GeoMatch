"""Add the master catalogue metadata and derive a searchable copy of legacy cells."""

from typing import cast

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import Connection


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
            sa.select(batches).where(
                sa.exists(
                    sa.select(records.c.id).where(
                        records.c.batch_id == batches.c.id,
                        sa.or_(
                            records.c.row_number.is_(None),
                            sa.and_(
                                batches.c.status == BatchStatus.COMPLETED,
                                sa.or_(
                                    records.c.normalized_data["_normalization_version"]
                                    .as_integer()
                                    .is_(None),
                                    records.c.normalized_data[
                                        "_normalization_version"
                                    ].as_integer()
                                    != NORMALIZATION_VERSION,
                                ),
                            ),
                        ),
                    )
                )
            )
        )
        .mappings()
        .all()
    )
    for batch in pending_batches:
        source_rows = (
            connection.execute(
                sa.select(records)
                .where(records.c.batch_id == batch["id"])
                .order_by(records.c.id)
            )
            .mappings()
            .all()
        )
        for position, record in enumerate(source_rows, start=2):
            values: dict = {}
            if record["row_number"] is None:
                values["row_number"] = position
            if (record["normalized_data"] or {}).get(
                "_normalization_version"
            ) != NORMALIZATION_VERSION and batch["status"] == BatchStatus.COMPLETED:
                fields = extract_standard_fields(
                    record["data"] or {}, batch["column_mapping"]
                )
                fields["tglbaca"] = fields["tglbaca"] or batch["period"]
                values["normalized_data"] = {
                    key: value
                    for key, value in fields.items()
                    if key != "validation_errors"
                }
                # Only catalogue sources are revalidated here; historical target
                # and PDPJ decisions remain untouched.
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
