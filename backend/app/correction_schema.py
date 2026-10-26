"""Add correction categories and retained per-target outcomes without rewriting legacy data."""

from typing import cast

from sqlalchemy import Table, text
from sqlalchemy.engine import Connection

from app.models.correction import (
    CorrectionAttempt,
    CorrectionCandidateEvidence,
    CorrectionCheck,
    CorrectionTarget,
)


def upgrade_corrections(connection: Connection) -> None:
    """Leave legacy target uploads uncategorized instead of guessing their origin."""
    if connection.dialect.name == "postgresql":
        for name in ("IDPEL_TIDAK_KETEMU", "IDPEL_KOSONG"):
            connection.execute(
                text(f"ALTER TYPE datasettype ADD VALUE IF NOT EXISTS '{name}'")
            )
    for model in (
        CorrectionCheck,
        CorrectionAttempt,
        CorrectionTarget,
        CorrectionCandidateEvidence,
    ):
        cast(Table, model.__table__).create(connection, checkfirst=True)
