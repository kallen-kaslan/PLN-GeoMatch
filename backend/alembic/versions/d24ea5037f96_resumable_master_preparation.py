"""Keep bounded master preparation and ready snapshot cache."""

from alembic import op
from app.master_preparation_schema import upgrade_master_preparation

revision = "d24ea5037f96"
down_revision = "c13d94f26e85"
branch_labels = None
depends_on = None


def upgrade() -> None:
    upgrade_master_preparation(op.get_bind())


def downgrade() -> None:
    raise RuntimeError("Checkpoint persiapan dan snapshot yang sudah digunakan dipertahankan")
