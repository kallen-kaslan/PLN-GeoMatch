"""Index validation and incomplete-coordinate filters for large master files."""

from alembic import op
from app.master_filter_schema import upgrade_master_filters
from app.models.upload import MASTER_FILTER_INDEX_NAMES

revision = "a8d13f04c621"
down_revision = "a72f06e391bd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    upgrade_master_filters(op.get_bind())


def downgrade() -> None:
    for name in reversed(MASTER_FILTER_INDEX_NAMES):
        op.drop_index(name, table_name="source_records")
