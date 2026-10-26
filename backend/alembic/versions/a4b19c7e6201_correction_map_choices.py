"""Retain correction map choices and their audit history.

Revision ID: a4b19c7e6201
Revises: f21a85db4e09
"""

from alembic import op
from app.correction_map_schema import upgrade_correction_map

revision = "a4b19c7e6201"
down_revision = "f21a85db4e09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    upgrade_correction_map(op.get_bind())


def downgrade() -> None:
    op.drop_table("correction_decisions")
