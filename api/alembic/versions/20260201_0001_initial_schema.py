"""Initial schema with all tables

Revision ID: 0001
Revises:
Create Date: 2026-02-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector"')

    # ===========================================
    # CORE TABLES (Phase 1)
    # ===========================================

    # Users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('external_id', sa.String(255), unique=True, nullable=True),
        sa.Column('session_id', sa.String(255), unique=True, nullable=True),
        sa.Column('metadata', postgresql.JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_users_external_id', 'users', ['external_id'])
    op.create_index('ix_users_session_id', 'users', ['session_id'])

    # Conversations table
    op.create_table(
        'conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('metadata', postgresql.JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_conversations_user_id', 'conversations', ['user_id'])

    # Messages table
    op.create_table(
        'messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('metadata', postgresql.JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_messages_conversation_id', 'messages', ['conversation_id'])
    op.create_index('ix_messages_conversation_created', 'messages', ['conversation_id', 'created_at'])

    # Events table (episodic memory)
    op.create_table(
        'events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('source', sa.String(20), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('payload', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_events_type', 'events', ['type'])
    op.create_index('ix_events_source', 'events', ['source'])
    op.create_index('ix_events_user_id', 'events', ['user_id'])
    op.create_index('ix_events_created_at', 'events', ['created_at'])
    op.create_index('ix_events_type_created', 'events', ['type', 'created_at'])
    op.create_index('ix_events_user_created', 'events', ['user_id', 'created_at'])

    # ===========================================
    # MEMORY TABLES (Phase 4)
    # ===========================================

    # Memories table (semantic memory with vector embeddings)
    op.create_table(
        'memories',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True),
        sa.Column('type', sa.String(30), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('embedding', sa.Column('embedding', sa.LargeBinary), nullable=True),  # Will be vector(1536)
        sa.Column('confidence', sa.Float, server_default='1.0'),
        sa.Column('source_event_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), server_default='{}'),
        sa.Column('metadata', postgresql.JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # Drop and recreate embedding column with proper vector type
    op.execute('ALTER TABLE memories DROP COLUMN IF EXISTS embedding')
    op.execute('ALTER TABLE memories ADD COLUMN embedding vector(1536)')
    op.create_index('ix_memories_user_id', 'memories', ['user_id'])
    op.create_index('ix_memories_type', 'memories', ['type'])
    op.create_index('ix_memories_user_type', 'memories', ['user_id', 'type'])

    # Summaries table
    op.create_table(
        'summaries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('scope', sa.String(20), nullable=False),
        sa.Column('scope_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('kind', sa.String(30), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('metadata', postgresql.JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_summaries_scope', 'summaries', ['scope'])
    op.create_index('ix_summaries_scope_id', 'summaries', ['scope_id'])
    op.create_index('ix_summaries_kind', 'summaries', ['kind'])
    op.create_unique_constraint('uq_summaries_scope_kind', 'summaries', ['scope', 'scope_id', 'kind'])

    # Retrieval traces table
    op.create_table(
        'retrieval_traces',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('message_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('messages.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('memories_retrieved', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), server_default='{}'),
        sa.Column('scores', postgresql.ARRAY(sa.Float), server_default='{}'),
        sa.Column('context_tokens', sa.Integer, nullable=True),
        sa.Column('metadata', postgresql.JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ===========================================
    # TOKEN DATA TABLES (Phase 5)
    # ===========================================

    # Token metrics (single row)
    op.create_table(
        'token_metrics',
        sa.Column('id', sa.Integer, primary_key=True, server_default='1'),
        sa.Column('price', sa.Float, nullable=False, server_default='0'),
        sa.Column('market_cap', sa.Float, nullable=False, server_default='0'),
        sa.Column('volume_24h', sa.Float, nullable=False, server_default='0'),
        sa.Column('liquidity', sa.Float, nullable=True),
        sa.Column('holders', sa.Integer, nullable=True),
        sa.Column('price_change_24h', sa.Float, nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.execute("INSERT INTO token_metrics (id) VALUES (1) ON CONFLICT DO NOTHING")

    # Token ATH (single row)
    op.create_table(
        'token_ath',
        sa.Column('id', sa.Integer, primary_key=True, server_default='1'),
        sa.Column('market_cap_ath', sa.Float, nullable=False, server_default='0'),
        sa.Column('meter_max', sa.Float, nullable=False, server_default='1000000'),
        sa.Column('ath_reached_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.execute("INSERT INTO token_ath (id) VALUES (1) ON CONFLICT DO NOTHING")

    # Token snapshots (historical)
    op.create_table(
        'token_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('price', sa.Float, nullable=False),
        sa.Column('market_cap', sa.Float, nullable=False),
        sa.Column('volume_24h', sa.Float, nullable=True),
        sa.Column('holders', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_token_snapshots_created_at', 'token_snapshots', ['created_at'])

    # ===========================================
    # AGENT STATS TABLE (Phase 6)
    # ===========================================

    op.create_table(
        'agent_stats',
        sa.Column('id', sa.Integer, primary_key=True, server_default='1'),
        sa.Column('messages_processed', sa.Integer, nullable=False, server_default='0'),
        sa.Column('messages_replied', sa.Integer, nullable=False, server_default='0'),
        sa.Column('messages_web', sa.Integer, nullable=False, server_default='0'),
        sa.Column('messages_x', sa.Integer, nullable=False, server_default='0'),
        sa.Column('semantic_memories_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('learning_score', sa.Float, nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.execute("INSERT INTO agent_stats (id) VALUES (1) ON CONFLICT DO NOTHING")

    # ===========================================
    # SOCIAL TABLES (Phase 8)
    # ===========================================

    # Social inbox (incoming mentions)
    op.create_table(
        'social_inbox',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('tweet_id', sa.String(30), unique=True, nullable=False),
        sa.Column('author_id', sa.String(30), nullable=False),
        sa.Column('author_username', sa.String(100), nullable=False),
        sa.Column('text', sa.Text, nullable=False),
        sa.Column('in_reply_to_tweet_id', sa.String(30), nullable=True),
        sa.Column('conversation_id', sa.String(30), nullable=True),
        sa.Column('created_at_twitter', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ingested_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('processed', sa.Boolean, server_default='false'),
        sa.Column('response_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index('ix_social_inbox_tweet_id', 'social_inbox', ['tweet_id'])
    op.create_index('ix_social_inbox_author_id', 'social_inbox', ['author_id'])
    op.create_index('ix_social_inbox_processed', 'social_inbox', ['processed'])

    # Social posts (outgoing posts)
    op.create_table(
        'social_posts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('tweet_id', sa.String(30), unique=True, nullable=True),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('text', sa.Text, nullable=False),
        sa.Column('in_reply_to_tweet_id', sa.String(30), nullable=True),
        sa.Column('media_ids', postgresql.ARRAY(sa.String(30)), server_default='{}'),
        sa.Column('status', sa.String(20), nullable=False, server_default="'draft'"),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_social_posts_status', 'social_posts', ['status'])

    # Social drafts (approval queue)
    op.create_table(
        'social_drafts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('post_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('social_posts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(20), server_default="'pending'"),
        sa.Column('reviewer_notes', sa.Text, nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_social_drafts_status', 'social_drafts', ['status'])

    # ===========================================
    # KNOWLEDGE DOCUMENTS (Phase 11)
    # ===========================================

    op.create_table(
        'knowledge_documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('url', sa.Text, nullable=True),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('text', sa.Text, nullable=False),
        sa.Column('text_hash', sa.String(64), nullable=False),
        sa.Column('metadata', postgresql.JSONB, server_default='{}'),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('processed', sa.Boolean, server_default='false'),
    )
    op.create_index('ix_knowledge_documents_source', 'knowledge_documents', ['source'])
    op.create_index('ix_knowledge_documents_text_hash', 'knowledge_documents', ['text_hash'])

    # ===========================================
    # TOOL CALLS (Audit)
    # ===========================================

    op.create_table(
        'tool_calls',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('message_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('messages.id', ondelete='SET NULL'), nullable=True),
        sa.Column('tool_name', sa.String(100), nullable=False),
        sa.Column('input_params', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('output_result', postgresql.JSONB, nullable=True),
        sa.Column('success', sa.Boolean, nullable=False),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('duration_ms', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_tool_calls_message_id', 'tool_calls', ['message_id'])
    op.create_index('ix_tool_calls_tool_name', 'tool_calls', ['tool_name'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('tool_calls')
    op.drop_table('knowledge_documents')
    op.drop_table('social_drafts')
    op.drop_table('social_posts')
    op.drop_table('social_inbox')
    op.drop_table('agent_stats')
    op.drop_table('token_snapshots')
    op.drop_table('token_ath')
    op.drop_table('token_metrics')
    op.drop_table('retrieval_traces')
    op.drop_table('summaries')
    op.drop_table('memories')
    op.drop_table('events')
    op.drop_table('messages')
    op.drop_table('conversations')
    op.drop_table('users')
