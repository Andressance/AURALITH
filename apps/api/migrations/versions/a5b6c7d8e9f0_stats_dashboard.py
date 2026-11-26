"""stats dashboard layout

Revision ID: a5b6c7d8e9f0
Revises: f3a4b5c6d7e8
Create Date: 2026-11-26 15:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a5b6c7d8e9f0'
down_revision: Union[str, Sequence[str], None] = 'f3a4b5c6d7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'stats_dashboards',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('layout', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_stats_dashboards_user_id', 'stats_dashboards', ['user_id'], unique=True
    )


def downgrade() -> None:
    op.drop_index('ix_stats_dashboards_user_id', table_name='stats_dashboards')
    op.drop_table('stats_dashboards')
