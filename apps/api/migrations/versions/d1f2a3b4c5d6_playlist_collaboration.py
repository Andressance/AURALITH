"""playlist collaboration

Revision ID: d1f2a3b4c5d6
Revises: c0e600a71fdd
Create Date: 2026-11-25 20:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'c0e600a71fdd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('playlist_shares', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('can_edit', sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column('saved', sa.Boolean(), nullable=False, server_default=sa.true())
        )


def downgrade() -> None:
    with op.batch_alter_table('playlist_shares', schema=None) as batch_op:
        batch_op.drop_column('saved')
        batch_op.drop_column('can_edit')
