"""Add columns for X learning memory extraction

Revision ID: 0003
Revises: 0002
Create Date: 2026-02-02 17:15:00.000000

Adds:
- memories.source_tweet_ids: ARRAY(VARCHAR(30)) for citing X tweet IDs
- x_inbox.learning_processed: Boolean for idempotent extraction
- x_posts.learning_processed: Boolean for idempotent extraction
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add source_tweet_ids column to memories table
    # This stores X tweet IDs that were the source of this memory
    op.add_column(
        'memories',
        sa.Column('source_tweet_ids', postgresql.ARRAY(sa.String(30)), nullable=True)
    )
    op.create_index('ix_memories_source_tweet_ids', 'memories', ['source_tweet_ids'], postgresql_using='gin')

    # Add learning_processed column to x_inbox
    # Tracks whether we've extracted learning memories from this inbound tweet
    op.add_column(
        'x_inbox',
        sa.Column('learning_processed', sa.Boolean, server_default='false', nullable=False)
    )
    op.add_column(
        'x_inbox',
        sa.Column('learning_processed_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index('ix_x_inbox_learning_processed', 'x_inbox', ['learning_processed'])

    # Add learning_processed column to x_posts
    # Tracks whether we've extracted learning memories from this outbound post
    op.add_column(
        'x_posts',
        sa.Column('learning_processed', sa.Boolean, server_default='false', nullable=False)
    )
    op.add_column(
        'x_posts',
        sa.Column('learning_processed_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index('ix_x_posts_learning_processed', 'x_posts', ['learning_processed'])


def downgrade() -> None:
    # Remove from x_posts
    op.drop_index('ix_x_posts_learning_processed', table_name='x_posts')
    op.drop_column('x_posts', 'learning_processed_at')
    op.drop_column('x_posts', 'learning_processed')

    # Remove from x_inbox
    op.drop_index('ix_x_inbox_learning_processed', table_name='x_inbox')
    op.drop_column('x_inbox', 'learning_processed_at')
    op.drop_column('x_inbox', 'learning_processed')

    # Remove from memories
    op.drop_index('ix_memories_source_tweet_ids', table_name='memories')
    op.drop_column('memories', 'source_tweet_ids')
