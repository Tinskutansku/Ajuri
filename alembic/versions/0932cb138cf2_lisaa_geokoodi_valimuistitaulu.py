"""lisaa geokoodi valimuistitaulu

Revision ID: 0932cb138cf2
Revises: fd18d4f9fe3a
Create Date: 2026-09-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0932cb138cf2'
down_revision: Union[str, Sequence[str], None] = 'fd18d4f9fe3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('geokoodi',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('osoite', sa.String(length=300), nullable=False),
    sa.Column('lat', sa.Float(), nullable=True),
    sa.Column('lon', sa.Float(), nullable=True),
    sa.Column('haettu', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('lahde', sa.String(length=50), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('osoite'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('geokoodi')
