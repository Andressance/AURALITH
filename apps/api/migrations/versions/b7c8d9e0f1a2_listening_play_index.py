"""listening play account index

Revision ID: b7c8d9e0f1a2
Revises: a5b6c7d8e9f0
Create Date: 2026-11-26 16:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, Sequence[str], None] = 'a5b6c7d8e9f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Every statistics request filters by account and a date range.
    op.create_index(
        'ix_listening_plays_user_played',
        'listening_plays',
        ['user_id', 'played_at'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_listening_plays_user_played', table_name='listening_plays')
