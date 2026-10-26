"""Add the immutable choice log without changing stored search evidence."""

from typing import cast

from sqlalchemy import Table
from sqlalchemy.engine import Connection

from app.models.correction_decision import CorrectionDecision


def upgrade_correction_map(connection: Connection) -> None:
    cast(Table, CorrectionDecision.__table__).create(connection, checkfirst=True)
