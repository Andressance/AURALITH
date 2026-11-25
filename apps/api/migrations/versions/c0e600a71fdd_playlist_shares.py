"""playlist shares

Revision ID: c0e600a71fdd
Revises: 08670140ed6e
Create Date: 2026-11-25 19:38:44.368954
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c0e600a71fdd'
down_revision: Union[str, Sequence[str], None] = '08670140ed6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'playlist_shares',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('playlist_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['playlist_id'], ['playlists.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('playlist_id', 'user_id', name='uq_playlist_share'),
    )
    with op.batch_alter_table('playlist_shares', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_playlist_shares_playlist_id'), ['playlist_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_playlist_shares_user_id'), ['user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('playlist_shares', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_playlist_shares_user_id'))
        batch_op.drop_index(batch_op.f('ix_playlist_shares_playlist_id'))
    op.drop_table('playlist_shares')
