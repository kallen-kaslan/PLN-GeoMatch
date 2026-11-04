"""Add real authentication, revocable sessions, throttling, and security audit."""

from alembic import op
from app.auth_schema import upgrade_auth

revision = "c14e85b62a09"
down_revision = "b9c63f2a710e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    upgrade_auth(op.get_bind())


def downgrade() -> None:
    for table in ("auth_audit", "auth_guard", "auth_throttles", "auth_sessions"):
        op.drop_table(table)
