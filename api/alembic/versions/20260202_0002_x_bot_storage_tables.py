"""Add X bot storage tables for persistent storage

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-02 21:00:00.000000

These tables support the X bot storage interfaces:
- x_drafts: DraftRepository (pending drafts for approval)
- x_inbox: InboxRepository (processed mentions)
- x_reply_log: ReplyLogRepository (idempotency tracking)
- x_threads: ThreadRepository (conversation state)
- x_user_limits: UserLimitRepository (per-user daily limits)
- x_settings: SettingsRepository (runtime config like last_mention_id)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ===========================================
    # X Bot Drafts (approval queue)
    # ===========================================
    op.create_table(
        'x_drafts',
        sa.Column('id', sa.String(36), primary_key=True),  # UUID string
        sa.Column('text', sa.Text, nullable=False),
        sa.Column('post_type', sa.String(20), nullable=False),  # 'reply', 'timeline', 'quote'
        sa.Column('reply_to_id', sa.String(30), nullable=True),  # Tweet ID we're replying to
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.Text, nullable=True),
    )
    op.create_index('ix_x_drafts_status', 'x_drafts', ['status'])
    op.create_index('ix_x_drafts_created_at', 'x_drafts', ['created_at'])
    op.create_index('ix_x_drafts_reply_to_id', 'x_drafts', ['reply_to_id'])

    # ===========================================
    # X Bot Inbox (processed mentions)
    # ===========================================
    op.create_table(
        'x_inbox',
        sa.Column('id', sa.String(30), primary_key=True),  # Same as tweet_id
        sa.Column('tweet_data', postgresql.JSONB, nullable=False),  # Serialized XTweet
        sa.Column('author_id', sa.String(30), nullable=False),
        sa.Column('quality_score', sa.Integer, nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('processed', sa.Boolean, server_default='false'),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('skipped', sa.Boolean, server_default='false'),
        sa.Column('skip_reason', sa.String(255), nullable=True),
    )
    op.create_index('ix_x_inbox_author_id', 'x_inbox', ['author_id'])
    op.create_index('ix_x_inbox_processed', 'x_inbox', ['processed'])
    op.create_index('ix_x_inbox_received_at', 'x_inbox', ['received_at'])

    # ===========================================
    # X Bot Reply Log (idempotency)
    # ===========================================
    op.create_table(
        'x_reply_log',
        sa.Column('tweet_id', sa.String(30), primary_key=True),  # Tweet we replied to
        sa.Column('reply_tweet_id', sa.String(30), nullable=False),  # Our reply's tweet ID
        sa.Column('replied_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_x_reply_log_replied_at', 'x_reply_log', ['replied_at'])

    # ===========================================
    # X Bot Threads (conversation state)
    # ===========================================
    op.create_table(
        'x_threads',
        sa.Column('conversation_id', sa.String(30), primary_key=True),
        sa.Column('author_id', sa.String(30), nullable=False),
        sa.Column('our_reply_count', sa.Integer, server_default='0'),
        sa.Column('last_reply_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('stopped', sa.Boolean, server_default='false'),
        sa.Column('stop_reason', sa.String(255), nullable=True),
    )
    op.create_index('ix_x_threads_author_id', 'x_threads', ['author_id'])
    op.create_index('ix_x_threads_stopped', 'x_threads', ['stopped'])

    # ===========================================
    # X Bot User Limits (per-user daily caps)
    # ===========================================
    op.create_table(
        'x_user_limits',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.String(30), nullable=False),
        sa.Column('date', sa.String(10), nullable=False),  # YYYY-MM-DD
        sa.Column('reply_count', sa.Integer, server_default='0'),
    )
    op.create_index('ix_x_user_limits_user_date', 'x_user_limits', ['user_id', 'date'], unique=True)
    op.create_index('ix_x_user_limits_date', 'x_user_limits', ['date'])

    # ===========================================
    # X Bot Settings (runtime config)
    # ===========================================
    op.create_table(
        'x_settings',
        sa.Column('key', sa.String(100), primary_key=True),
        sa.Column('value', sa.Text, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ===========================================
    # X Bot Posts (outgoing posts tracking)
    # ===========================================
    op.create_table(
        'x_posts',
        sa.Column('id', sa.String(36), primary_key=True),  # Internal UUID
        sa.Column('tweet_id', sa.String(30), nullable=True, unique=True),  # X tweet ID once posted
        sa.Column('text', sa.Text, nullable=False),
        sa.Column('post_type', sa.String(20), nullable=False),
        sa.Column('reply_to_id', sa.String(30), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_x_posts_tweet_id', 'x_posts', ['tweet_id'])
    op.create_index('ix_x_posts_status', 'x_posts', ['status'])
    op.create_index('ix_x_posts_posted_at', 'x_posts', ['posted_at'])


def downgrade() -> None:
    op.drop_table('x_posts')
    op.drop_table('x_settings')
    op.drop_table('x_user_limits')
    op.drop_table('x_threads')
    op.drop_table('x_reply_log')
    op.drop_table('x_inbox')
    op.drop_table('x_drafts')
