"""Index result pagination without rewriting PDPJ rows or validation decisions."""

from typing import cast

from sqlalchemy import Table
from sqlalchemy.engine import Connection


def upgrade_pdpj_results(connection: Connection) -> None:
    from app.models.pdpj import PdpjRow

    for index in cast(Table, PdpjRow.__table__).indexes:
        if index.name in {
            "ix_pdpj_rows_review_row_number_id",
            "ix_pdpj_rows_review_existence_row_number_id",
        }:
            index.create(connection, checkfirst=True)
