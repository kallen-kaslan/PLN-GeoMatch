"""Add categorized correction checks and complete target outcomes.

Revision ID: f21a85db4e09
Revises: d901c38ae240
"""

from alembic import op

from app.correction_schema import upgrade_corrections

revision = "f21a85db4e09"
down_revision = "d901c38ae240"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Preserve uploads and old search generations while adding new categories."""
    upgrade_corrections(op.get_bind())


def downgrade() -> None:
    """Require deliberate recovery before discarding correction evidence."""
    raise RuntimeError("Pulihkan backup untuk kembali ke skema sebelum kategori koreksi")
