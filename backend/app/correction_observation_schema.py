"""Keep previous searches on their original coordinate policy."""

from typing import cast

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, Integer, Table, inspect
from sqlalchemy.engine import Connection


def upgrade_correction_observations(connection: Connection) -> None:
    from app.models.master_sisa import (
        CorrectionMasterObservation,
        CorrectionObservationCatalog,
    )

    if "candidate_policy" not in {
        column["name"] for column in inspect(connection).get_columns("matching_runs")
    }:
        Operations(MigrationContext.configure(connection)).add_column(
            "matching_runs",
            Column("candidate_policy", Integer(), nullable=False, server_default="1"),
        )
    for model in (CorrectionObservationCatalog, CorrectionMasterObservation):
        cast(Table, model.__table__).create(connection, checkfirst=True)
