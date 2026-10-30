"""Persist exact master aggregates without rescanning source rows on refresh."""

from alembic import op
from app.master_summary_schema import upgrade_master_summary

revision = "f46ac7259b18"
down_revision = "e35fb6148a07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    upgrade_master_summary(op.get_bind())


def downgrade() -> None:
    op.drop_table("master_summary_caches")
