"""keikan tila ja kuittausajat (ROADMAP N3)

Revision ID: e7b3a9c2d104
Revises: c04587ed7c14
Create Date: 2026-11-27 01:30:00.000000

Tanjan päätös issuessa #38 (vaihtoehto A): tila ja aikaleimat keikka-tauluun.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7b3a9c2d104'
down_revision: Union[str, Sequence[str], None] = 'c04587ed7c14'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

keikkatila = sa.Enum('ODOTTAA', 'KYYDISSA', 'PERILLA', name='keikkatila')


def upgrade() -> None:
    """Upgrade schema."""
    keikkatila.create(op.get_bind(), checkfirst=True)
    # Olemassa olevat keikat: odottaa. server_default vain migraation ajaksi
    # kuten aiemmissa NOT NULL -lisäyksissä.
    op.add_column(
        'keikka',
        sa.Column('tila', keikkatila, nullable=False, server_default='ODOTTAA'),
    )
    op.alter_column('keikka', 'tila', server_default=None)
    op.add_column('keikka', sa.Column('kyydissa_klo', sa.DateTime(), nullable=True))
    op.add_column('keikka', sa.Column('perilla_klo', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('keikka', 'perilla_klo')
    op.drop_column('keikka', 'kyydissa_klo')
    op.drop_column('keikka', 'tila')
    keikkatila.drop(op.get_bind(), checkfirst=True)
