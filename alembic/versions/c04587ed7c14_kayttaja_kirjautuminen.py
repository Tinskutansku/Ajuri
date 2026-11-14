"""kayttaja kirjautuminen

Revision ID: c04587ed7c14
Revises: a1b2c3d4e5f6
Create Date: 2026-11-14 00:51:19.463225

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c04587ed7c14'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('kayttaja', sa.Column('salasana_hash', sa.String(length=255), nullable=True))
    # Olemassa olevat käyttäjät jäävät aktiivisiksi; server_default vain
    # migraation ajaksi kuten perusdatan soft deletessä.
    op.add_column(
        'kayttaja',
        sa.Column('aktiivinen', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column('kayttaja', 'aktiivinen', server_default=None)
    op.add_column('kayttaja', sa.Column('viimeksi_kirjautunut', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('kayttaja', 'viimeksi_kirjautunut')
    op.drop_column('kayttaja', 'aktiivinen')
    op.drop_column('kayttaja', 'salasana_hash')
