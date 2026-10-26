"""Add DIL and source metadata for the master catalogue.

Revision ID: c284bd7945a1
Revises: 7adf4a6e9120
"""

from alembic import op

from app.master_schema import upgrade_master_catalog

revision = "c284bd7945a1"
down_revision = "7adf4a6e9120"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Keep original source values while extending master metadata."""
    upgrade_master_catalog(op.get_bind())


def downgrade() -> None:
    """Prevent silently discarding DIL observations and their source metadata."""
    raise RuntimeError("Pulihkan backup untuk kembali ke skema sebelum katalog master")
