"""jams

Revision ID: e2a3b4c5d6e7
Revises: d1f2a3b4c5d6
Create Date: 2026-11-25 21:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e2a3b4c5d6e7'
down_revision: Union[str, Sequence[str], None] = 'd1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'jams',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=12), nullable=False),
        sa.Column('host_user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='active'),
        sa.Column('current_track_id', sa.Integer(), nullable=True),
        sa.Column('is_playing', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('position', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('position_updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['host_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['current_track_id'], ['tracks.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    op.create_index('ix_jams_code', 'jams', ['code'], unique=True)

    op.create_table(
        'jam_participants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('jam_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('joined_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['jam_id'], ['jams.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('jam_id', 'user_id', name='uq_jam_participant'),
    )
    op.create_index('ix_jam_participants_jam_id', 'jam_participants', ['jam_id'], unique=False)
    op.create_index('ix_jam_participants_user_id', 'jam_participants', ['user_id'], unique=False)

    op.create_table(
        'jam_queue_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('jam_id', sa.Integer(), nullable=False),
        sa.Column('track_id', sa.Integer(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('added_by', sa.Integer(), nullable=True),
        sa.Column('added_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['jam_id'], ['jams.id']),
        sa.ForeignKeyConstraint(['track_id'], ['tracks.id']),
        sa.ForeignKeyConstraint(['added_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_jam_queue_items_jam_id', 'jam_queue_items', ['jam_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_jam_queue_items_jam_id', table_name='jam_queue_items')
    op.drop_table('jam_queue_items')
    op.drop_index('ix_jam_participants_user_id', table_name='jam_participants')
    op.drop_index('ix_jam_participants_jam_id', table_name='jam_participants')
    op.drop_table('jam_participants')
    op.drop_index('ix_jams_code', table_name='jams')
    op.drop_table('jams')
