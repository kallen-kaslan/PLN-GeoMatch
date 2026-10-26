"""Isolate master snapshots, validate source rows, and preserve matching generations.

Revision ID: 7adf4a6e9120
Revises: 19218c221efc
"""

from alembic import op

from app.schema_compatibility import upgrade_foundations

revision = "7adf4a6e9120"
down_revision = "19218c221efc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Retain all old source records, candidates, and acceptance decisions."""
    upgrade_foundations(op.get_bind())


def downgrade() -> None:
    """Refuse to discard historical attempts implicitly."""
    raise RuntimeError(
        "Downgrade menghapus riwayat pencarian; pulihkan backup untuk kembali ke versi lama"
    )
