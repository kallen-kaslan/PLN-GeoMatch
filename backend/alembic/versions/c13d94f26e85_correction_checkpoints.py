"""Save correction processing and validation checkpoints."""

from alembic import op
from app.correction_progress_schema import upgrade_correction_progress

revision = "c13d94f26e85"
down_revision = "b02c83e15d74"
branch_labels = None
depends_on = None


def upgrade() -> None:
    upgrade_correction_progress(op.get_bind())


def downgrade() -> None:
    raise RuntimeError("Hasil koreksi yang tersimpan dipertahankan")
