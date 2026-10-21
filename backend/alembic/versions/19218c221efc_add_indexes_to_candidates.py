"""add_indexes_to_candidates

Revision ID: 19218c221efc
Revises: e4031d758f1b
Create Date: 2026-10-21 00:18:59.531846

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '19218c221efc'
down_revision: Union[str, None] = 'e4031d758f1b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_match_candidates_process_id', 'match_candidates', ['process_id'])
    op.create_index('ix_match_candidates_is_accepted', 'match_candidates', ['is_accepted'])


def downgrade() -> None:
    op.drop_index('ix_match_candidates_process_id', table_name='match_candidates')
    op.drop_index('ix_match_candidates_is_accepted', table_name='match_candidates')
