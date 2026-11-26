"""listening plays

Revision ID: f3a4b5c6d7e8
Revises: e2a3b4c5d6e7
Create Date: 2026-11-26 14:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f3a4b5c6d7e8'
down_revision: Union[str, Sequence[str], None] = 'e2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'listening_plays',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('track_id', sa.Integer(), nullable=False),
        sa.Column('seconds', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('played_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['track_id'], ['tracks.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_listening_plays_user_id', 'listening_plays', ['user_id'], unique=False)
    op.create_index('ix_listening_plays_track_id', 'listening_plays', ['track_id'], unique=False)
    op.create_index('ix_listening_plays_played_at', 'listening_plays', ['played_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_listening_plays_played_at', table_name='listening_plays')
    op.drop_index('ix_listening_plays_track_id', table_name='listening_plays')
    op.drop_index('ix_listening_plays_user_id', table_name='listening_plays')
    op.drop_table('listening_plays')
