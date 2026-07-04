"""events jobs outbox

Revision ID: d2d29db3cc1e
Revises: d3a1f9b2c7e4
Create Date: 2026-07-04 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd2d29db3cc1e'
down_revision: Union[str, Sequence[str], None] = 'd3a1f9b2c7e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(['event_id'], ['events.event_id'], name='fk_jobs_event_id_events'),
        sa.UniqueConstraint('event_id', name='uq_jobs_event_id'),
        sa.CheckConstraint(
            "status in ('pending', 'processing', 'done', 'failed')", name='ck_jobs_status'
        ),
    )
    op.create_index('ix_jobs_status', 'jobs', ['status'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_jobs_status', table_name='jobs')
    op.drop_table('jobs')
