"""rewards ledger and challenge period

Revision ID: a7f3e91c2d05
Revises: f6a2c8d4e1b3
Create Date: 2026-07-04 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a7f3e91c2d05'
down_revision: Union[str, Sequence[str], None] = 'f6a2c8d4e1b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'challenges',
        sa.Column('period', sa.String(length=20), nullable=False, server_default='one_time'),
    )
    op.create_check_constraint(
        'ck_challenges_period', 'challenges', "period in ('one_time', 'weekly')"
    )

    op.create_table(
        'rewards',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reward_type', sa.String(length=50), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('source_challenge_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('completion_key', sa.String(length=50), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_rewards_user_id_users'),
        sa.ForeignKeyConstraint(
            ['source_challenge_id'],
            ['challenges.id'],
            name='fk_rewards_source_challenge_id_challenges',
        ),
        sa.UniqueConstraint(
            'user_id',
            'source_challenge_id',
            'completion_key',
            name='uq_rewards_user_challenge_completion',
        ),
    )
    op.create_index('ix_rewards_user_id', 'rewards', ['user_id'])
    op.create_index('ix_rewards_source_challenge_id', 'rewards', ['source_challenge_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_rewards_source_challenge_id', table_name='rewards')
    op.drop_index('ix_rewards_user_id', table_name='rewards')
    op.drop_table('rewards')

    op.drop_constraint('ck_challenges_period', 'challenges', type_='check')
    op.drop_column('challenges', 'period')
