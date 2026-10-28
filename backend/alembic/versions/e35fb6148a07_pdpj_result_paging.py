"""Use indexed result ordering for deep PDPJ pages."""

from alembic import op
from app.pdpj_results_schema import upgrade_pdpj_results

revision = "e35fb6148a07"
down_revision = "d24ea5037f96"
branch_labels = None
depends_on = None


def upgrade() -> None:
    upgrade_pdpj_results(op.get_bind())


def downgrade() -> None:
    op.drop_index("ix_pdpj_rows_review_existence_row_number_id", table_name="pdpj_rows")
    op.drop_index("ix_pdpj_rows_review_row_number_id", table_name="pdpj_rows")
