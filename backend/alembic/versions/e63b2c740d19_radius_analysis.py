"""Persist nearest eligible distances independently of candidate searches."""

from alembic import op
from app.models.radius_analysis import RadiusAnalysis, RadiusAnalysisRow

revision = "e63b2c740d19"
down_revision = "a72f06e391bd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    RadiusAnalysis.__table__.create(op.get_bind(), checkfirst=True)
    RadiusAnalysisRow.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    raise RuntimeError("Riwayat analisis radius dipertahankan")
