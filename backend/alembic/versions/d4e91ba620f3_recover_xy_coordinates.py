"""Recover reversed X/Y source coordinates without changing frozen histories."""

from alembic import op
from app.coordinate_schema import repair_xy_coordinates

revision = "d4e91ba620f3"
down_revision = "c8d72fe610ab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    repair_xy_coordinates(op.get_bind())


def downgrade() -> None:
    raise RuntimeError("Pemulihan koordinat sumber tidak dibatalkan secara otomatis")
