"""bufferit ja max_etuajassa_min

Revision ID: fd18d4f9fe3a
Revises: 4ad741937dd5
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fd18d4f9fe3a'
down_revision: Union[str, Sequence[str], None] = '4ad741937dd5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'kuski',
        sa.Column('pickup_bufferi_min', sa.Integer(), nullable=False, server_default='0'),
    )
    op.alter_column('kuski', 'pickup_bufferi_min', server_default=None)

    op.add_column(
        'henkilo',
        sa.Column('nouto_bufferi_min', sa.Integer(), nullable=False, server_default='0'),
    )
    op.alter_column('henkilo', 'nouto_bufferi_min', server_default=None)

    op.add_column('henkilo', sa.Column('max_etuajassa_min', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('henkilo', 'max_etuajassa_min')
    op.drop_column('henkilo', 'nouto_bufferi_min')
    op.drop_column('kuski', 'pickup_bufferi_min')
