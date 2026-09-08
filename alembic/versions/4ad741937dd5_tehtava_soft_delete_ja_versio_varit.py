"""tehtava soft delete ja versio varit

Revision ID: 4ad741937dd5
Revises: 114af16b9f9c
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4ad741937dd5'
down_revision: Union[str, Sequence[str], None] = '114af16b9f9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'tehtava',
        sa.Column('aktiivinen', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column('tehtava', 'aktiivinen', server_default=None)
    op.add_column('ajolista_versio', sa.Column('tunniste', sa.String(length=20), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('ajolista_versio', 'tunniste')
    op.drop_column('tehtava', 'aktiivinen')
