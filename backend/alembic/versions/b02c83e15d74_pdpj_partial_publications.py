"""Retain approved partial PDPJ versions independently from processing cursors."""

from alembic import op
from app.pdpj_publication_schema import upgrade_pdpj_publications

revision = "b02c83e15d74"
down_revision = "a91d72f04c63"
branch_labels = None
depends_on = None


def upgrade() -> None:
    upgrade_pdpj_publications(op.get_bind())


def downgrade() -> None:
    raise RuntimeError("Versi PDPJ yang sudah digunakan koreksi harus dipertahankan")
