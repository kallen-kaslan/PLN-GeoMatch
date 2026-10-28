"""Add durable processing checkpoints without changing existing review decisions."""

from typing import cast

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import JSON, Column, Table, inspect
from sqlalchemy.engine import Connection
from sqlalchemy.schema import CreateIndex


def upgrade_pdpj_progress(connection: Connection) -> None:
    """A null checkpoint means an older, fully materialized review."""
    if "processing" not in {
        column["name"] for column in inspect(connection).get_columns("pdpj_reviews")
    }:
        Operations(MigrationContext.configure(connection)).add_column(
            "pdpj_reviews", Column("processing", JSON(), nullable=True)
        )
    if inspect(connection).has_table("pdpj_rows"):
        from app.models.pdpj import PdpjRow

        for index in cast(Table, PdpjRow.__table__).indexes:
            if index.name == "ix_pdpj_rows_review_identity":
                # SQLite's inspector omits expression indexes; let the database
                # check the name so repeated startup upgrades remain safe.
                connection.execute(CreateIndex(index, if_not_exists=True))
