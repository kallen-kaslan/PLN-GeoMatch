"""Retain original uploads and separately track validated sheet imports."""

from alembic import op
from app.upload_file_schema import upgrade_upload_files

revision = "c8d72fe610ab"
down_revision = "b7e3c40d291a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    upgrade_upload_files(op.get_bind())


def downgrade() -> None:
    op.drop_table("upload_sheet_imports")
    op.drop_table("upload_file_archives")
