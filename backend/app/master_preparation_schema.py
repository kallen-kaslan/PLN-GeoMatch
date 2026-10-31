"""Persist resumable preparation without exposing incomplete master snapshots."""

from typing import cast

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Boolean, Column, Table, inspect, true
from sqlalchemy.engine import Connection


def upgrade_master_preparation(connection: Connection) -> None:
    from app.models.master_sisa import (
        MasterPreparation,
        MasterPreparationExcluded,
        MasterPreparationIdentity,
    )

    if "ready" not in {
        column["name"] for column in inspect(connection).get_columns("master_snapshots")
    }:
        Operations(MigrationContext.configure(connection)).add_column(
            "master_snapshots",
            Column("ready", Boolean(), nullable=False, server_default=true()),
        )
    for model in (
        MasterPreparation,
        MasterPreparationIdentity,
        MasterPreparationExcluded,
    ):
        cast(Table, model.__table__).create(connection, checkfirst=True)
