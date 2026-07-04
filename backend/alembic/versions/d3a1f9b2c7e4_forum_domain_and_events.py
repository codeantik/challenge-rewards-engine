"""forum domain and events

Revision ID: d3a1f9b2c7e4
Revises: c1cf4340c3f3
Create Date: 2026-07-04 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd3a1f9b2c7e4'
down_revision: Union[str, Sequence[str], None] = 'c1cf4340c3f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # posts.solution_comment_id references comments, which doesn't exist yet
    # (comments.post_id references posts) — create the column bare here and
    # add its FK constraint once both tables exist, to avoid a circular
    # create-table dependency.
    op.create_table(
        'posts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('author_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('comment_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('view_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('solution_comment_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], name='fk_posts_author_id_users'),
    )
    op.create_index('ix_posts_author_id', 'posts', ['author_id'])

    op.create_table(
        'comments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('post_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('author_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id'], name='fk_comments_post_id_posts'),
        sa.ForeignKeyConstraint(
            ['author_id'], ['users.id'], name='fk_comments_author_id_users'
        ),
    )
    op.create_index('ix_comments_post_id', 'comments', ['post_id'])
    op.create_index('ix_comments_author_id', 'comments', ['author_id'])

    op.create_foreign_key(
        'fk_posts_solution_comment_id_comments',
        'posts',
        'comments',
        ['solution_comment_id'],
        ['id'],
    )

    op.create_table(
        'events',
        sa.Column('event_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_events_user_id_users'),
    )
    op.create_index('ix_events_event_type', 'events', ['event_type'])
    op.create_index('ix_events_user_id', 'events', ['user_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_events_user_id', table_name='events')
    op.drop_index('ix_events_event_type', table_name='events')
    op.drop_table('events')

    op.drop_constraint('fk_posts_solution_comment_id_comments', 'posts', type_='foreignkey')

    op.drop_index('ix_comments_author_id', table_name='comments')
    op.drop_index('ix_comments_post_id', table_name='comments')
    op.drop_table('comments')

    op.drop_index('ix_posts_author_id', table_name='posts')
    op.drop_table('posts')
