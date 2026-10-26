"""Retain failure categories on matching runs without rewriting their results."""

from alembic import op
from app.schema_compatibility import upgrade_foundations

revision = "b7e3c40d291a"
down_revision = "a4b19c7e6201"
branch_labels = None
depends_on = None


def upgrade() -> None:
    upgrade_foundations(op.get_bind())


def downgrade() -> None:
    raise RuntimeError(
        "Riwayat kegagalan pemeriksaan dipertahankan; downgrade tidak didukung"
    )
