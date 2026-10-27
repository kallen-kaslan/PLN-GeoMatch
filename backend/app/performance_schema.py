"""Add indexes for actual batch/run access paths without rewriting source rows."""

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import JSON, Column, Index, inspect
from sqlalchemy.engine import Connection

INDEX_COLUMNS = {
    "source_records": [
        ("ix_source_records_batch_id_id", ("batch_id", "id")),
        ("ix_source_records_batch_id_idpel", ("batch_id", "idpel")),
    ],
    "match_candidates": [
        (
            "ix_match_candidates_process_generation_target_rank",
            ("process_id", "generation", "target_record_id", "rank"),
        ),
    ],
    "master_sisa_records": [
        (
            "ix_master_sisa_records_snapshot_latitude_id",
            ("snapshot_id", "latitude", "id"),
        ),
    ],
}


def upgrade_performance(connection: Connection) -> None:
    from app.database import Base

    op = Operations(MigrationContext.configure(connection))
    existing_columns = {
        column["name"] for column in inspect(connection).get_columns("upload_batches")
    }
    if "source_headers" not in existing_columns:
        op.add_column("upload_batches", Column("source_headers", JSON, nullable=True))
    for table_name, indexes in INDEX_COLUMNS.items():
        table = Base.metadata.tables[table_name]
        for name, columns in indexes:
            index = next((index for index in table.indexes if index.name == name), None)
            if index is None:
                index = Index(name, *(table.c[column] for column in columns))
            index.create(connection, checkfirst=True)
