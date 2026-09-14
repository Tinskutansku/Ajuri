"""perusdata soft delete

Revision ID: a1b2c3d4e5f6
Revises: 0932cb138cf2
Create Date: 2026-09-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '0932cb138cf2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'henkilo',
        sa.Column('aktiivinen', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column('henkilo', 'aktiivinen', server_default=None)
    op.add_column(
        'kuski',
        sa.Column('aktiivinen', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column('kuski', 'aktiivinen', server_default=None)
    op.add_column(
        'lokaatio',
        sa.Column('aktiivinen', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column('lokaatio', 'aktiivinen', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('lokaatio', 'aktiivinen')
    op.drop_column('kuski', 'aktiivinen')
    op.drop_column('henkilo', 'aktiivinen')
