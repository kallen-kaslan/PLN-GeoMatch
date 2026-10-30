"""Add an aggregate-only cache; source records and validation stay untouched."""

from typing import cast

from sqlalchemy import Table
from sqlalchemy.engine import Connection


def upgrade_master_summary(connection: Connection) -> None:
    from app.models.master_summary import MasterSummaryCache

    cast(Table, MasterSummaryCache.__table__).create(connection, checkfirst=True)
