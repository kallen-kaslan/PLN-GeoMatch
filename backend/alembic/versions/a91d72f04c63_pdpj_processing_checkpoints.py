"""Persist resumable PDPJ matching and validation checkpoints."""

from alembic import op
from app.pdpj_progress_schema import upgrade_pdpj_progress

revision = "a91d72f04c63"
down_revision = "c7b40a193fd2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    upgrade_pdpj_progress(op.get_bind())


def downgrade() -> None:
    raise RuntimeError("Checkpoint PDPJ dipertahankan agar proses dapat dilanjutkan")
