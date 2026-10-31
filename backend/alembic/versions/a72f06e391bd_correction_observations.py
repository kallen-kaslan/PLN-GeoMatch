"""Index original correction coordinates and pin matching policies by search version."""

from alembic import op
from app.correction_observation_schema import upgrade_correction_observations

revision = "a72f06e391bd"
down_revision = "f46ac7259b18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    upgrade_correction_observations(op.get_bind())


def downgrade() -> None:
    raise RuntimeError("Observasi dan aturan pemeriksaan tersimpan dipertahankan")
