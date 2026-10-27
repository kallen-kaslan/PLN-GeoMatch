"""Create additive PDPJ tables in both Alembic and local startup compatibility paths."""

from typing import cast

from sqlalchemy import Table
from sqlalchemy.engine import Connection

from app.models.pdpj import PdpjChange, PdpjRecommendation, PdpjReview, PdpjRow
from app.pdpj_warning_schema import upgrade_pdpj_warnings


def upgrade_pdpj_validation(connection: Connection) -> None:
    """Keep previous sources, process snapshots, and history untouched."""
    for model in (PdpjReview, PdpjRow, PdpjRecommendation, PdpjChange):
        cast(Table, model.__table__).create(connection, checkfirst=True)
    upgrade_pdpj_warnings(connection)
