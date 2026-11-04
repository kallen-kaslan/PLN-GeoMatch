"""Cover stored PDPJ summary states without scanning original row payloads."""

from alembic import op
from app.models.pdpj import PDPJ_SUMMARY_INDEX
from app.pdpj_summary_schema import upgrade_pdpj_summary

revision = "b9c63f2a710e"
down_revision = "a8d13f04c621"
branch_labels = None
depends_on = None


def upgrade() -> None:
    upgrade_pdpj_summary(op.get_bind())


def downgrade() -> None:
    op.drop_index(PDPJ_SUMMARY_INDEX, table_name="pdpj_rows")
