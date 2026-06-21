"""add is_indexed to chunks

Revision ID: a1b2c3d4e5f6
Revises: c039d3b629be
Create Date: 2026-05-20 18:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'c039d3b629be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_indexed column to chunks table."""
    op.add_column('chunks',
        sa.Column('is_indexed', sa.Integer(), server_default='0', nullable=False)
    )


def downgrade() -> None:
    """Remove is_indexed column from chunks table."""
    op.drop_column('chunks', 'is_indexed')
