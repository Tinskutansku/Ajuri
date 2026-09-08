"""lisaa paiva_henkilo siirtyma_klo

Revision ID: 114af16b9f9c
Revises: cea41d0b4ec7
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '114af16b9f9c'
down_revision: Union[str, Sequence[str], None] = 'cea41d0b4ec7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('paiva_henkilo', sa.Column('siirtyma_klo', sa.Time(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('paiva_henkilo', 'siirtyma_klo')
