"""Allow repeated PDPJ identities while retaining duplicate information."""

from alembic import op
from app.pdpj_warning_schema import upgrade_pdpj_warnings

revision = "f6ac81d43e20"
down_revision = "e5fa92c30b71"
branch_labels = None
depends_on = None


def upgrade() -> None:
    upgrade_pdpj_warnings(op.get_bind())


def downgrade() -> None:
    raise RuntimeError("Catatan duplikasi dipertahankan; downgrade tidak didukung")
