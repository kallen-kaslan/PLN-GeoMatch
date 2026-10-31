"""Keep correction checkpoints without changing existing runs or decisions."""

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import JSON, Column, inspect
from sqlalchemy.engine import Connection


def upgrade_correction_progress(connection: Connection) -> None:
    if "processing" not in {
        column["name"] for column in inspect(connection).get_columns("matching_runs")
    }:
        Operations(MigrationContext.configure(connection)).add_column(
            "matching_runs", Column("processing", JSON(), nullable=True)
        )
