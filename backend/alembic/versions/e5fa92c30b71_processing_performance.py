"""Index batch/run queries and retain imported column names."""

from alembic import op
from app.performance_schema import upgrade_performance

revision = "e5fa92c30b71"
down_revision = "d4e91ba620f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    upgrade_performance(op.get_bind())


def downgrade() -> None:
    # Removing these additions is unnecessary for reading historical data.
    raise RuntimeError("Metadata sumber dipertahankan; downgrade tidak didukung")
