"""Add immutable approved PDPJ versions alongside resumable working reviews."""

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import JSON, Column, Integer, inspect, text
from sqlalchemy.engine import Connection


def upgrade_pdpj_publications(connection: Connection) -> None:
    """Keep legacy completed reviews and their correction references unchanged."""
    columns = {
        column["name"] for column in inspect(connection).get_columns("pdpj_reviews")
    }
    operation = Operations(MigrationContext.configure(connection))
    for column in (
        Column("source_review_id", Integer(), nullable=True),
        Column("publication", JSON(), nullable=True),
    ):
        if column.name not in columns:
            operation.add_column("pdpj_reviews", column)
    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_pdpj_reviews_source_review_id "
            "ON pdpj_reviews (source_review_id)"
        )
    )
