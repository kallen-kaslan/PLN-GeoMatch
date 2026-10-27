"""Persist per-batch normalization and completed startup migration checkpoints."""

from typing import cast

from sqlalchemy import Column, Integer, Table, inspect

from alembic import op
from app.models.schema_state import SchemaState

revision = "c7b40a193fd2"
down_revision = "f6ac81d43e20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    cast(Table, SchemaState.__table__).create(connection, checkfirst=True)
    if "catalog_version" not in {
        column["name"] for column in inspect(connection).get_columns("upload_batches")
    }:
        op.add_column(
            "upload_batches", Column("catalog_version", Integer, nullable=True)
        )


def downgrade() -> None:
    raise RuntimeError(
        "Metadata pemeriksaan startup dipertahankan; downgrade tidak didukung"
    )
