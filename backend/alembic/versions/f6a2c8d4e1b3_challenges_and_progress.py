"""challenges and progress

Revision ID: f6a2c8d4e1b3
Revises: d2d29db3cc1e
Create Date: 2026-07-04 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f6a2c8d4e1b3'
down_revision: Union[str, Sequence[str], None] = 'd2d29db3cc1e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'challenges',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('rule_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('reward', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('start_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status in ('draft', 'active', 'expired', 'archived')", name='ck_challenges_status'
        ),
    )
    op.create_index('ix_challenges_event_type', 'challenges', ['event_type'])
    op.create_index('ix_challenges_status', 'challenges', ['status'])

    op.create_table(
        'progress',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('challenge_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('current_value', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('target_value', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_complete', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_progress_user_id_users'),
        sa.ForeignKeyConstraint(
            ['challenge_id'], ['challenges.id'], name='fk_progress_challenge_id_challenges'
        ),
        sa.UniqueConstraint('user_id', 'challenge_id', name='uq_progress_user_challenge'),
    )
    op.create_index('ix_progress_user_id', 'progress', ['user_id'])
    op.create_index('ix_progress_challenge_id', 'progress', ['challenge_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_progress_challenge_id', table_name='progress')
    op.drop_index('ix_progress_user_id', table_name='progress')
    op.drop_table('progress')

    op.drop_index('ix_challenges_status', table_name='challenges')
    op.drop_index('ix_challenges_event_type', table_name='challenges')
    op.drop_table('challenges')
