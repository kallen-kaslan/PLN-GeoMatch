"""Add versioned PDPJ validation and retained recommendations.

Revision ID: d901c38ae240
Revises: c284bd7945a1
"""

from alembic import op

from app.pdpj_schema import upgrade_pdpj_validation

revision = "d901c38ae240"
down_revision = "c284bd7945a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add PDPJ validation tables without changing raw uploads."""
    upgrade_pdpj_validation(op.get_bind())


def downgrade() -> None:
    """Require deliberate recovery before discarding review decisions."""
    raise RuntimeError("Pulihkan backup untuk kembali ke skema sebelum validasi PDPJ")
