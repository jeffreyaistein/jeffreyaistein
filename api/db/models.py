"""
Jeffrey AIstein - Database Models
SQLAlchemy ORM models for all tables.
"""

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship

from db.base import Base


# ===========================================
# CORE TABLES (Phase 1)
# ===========================================


class User(Base):
    """User table for anonymous and authenticated users."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id = Column(String(255), unique=True, nullable=True, index=True)
    session_id = Column(String(255), unique=True, nullable=True, index=True)
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    memories = relationship("Memory", back_populates="user", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="user", cascade="all, delete-orphan")


class Conversation(Base):
    """Conversation threads between users and AIstein."""

    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=True)
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    """Individual messages within conversations."""

    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSONB, default=dict)  # tokens_used, model, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    retrieval_trace = relationship("RetrievalTrace", back_populates="message", uselist=False)

    # Indexes
    __table_args__ = (
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )


class Event(Base):
    """Episodic memory - all events in the system."""

    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(String(50), nullable=False, index=True)  # message_received, message_sent, tool_call, x_mention, etc.
    source = Column(String(20), nullable=False, index=True)  # web, x, system
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    payload = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    user = relationship("User", back_populates="events")

    # Indexes
    __table_args__ = (
        Index("ix_events_type_created", "type", "created_at"),
        Index("ix_events_user_created", "user_id", "created_at"),
    )


# ===========================================
# MEMORY TABLES (Phase 4)
# ===========================================


class Memory(Base):
    """Semantic memory - extracted facts, preferences, goals, etc."""

    __tablename__ = "memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    type = Column(String(30), nullable=False, index=True)  # fact, preference, goal, constraint, open_loop, persona_fact
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1536), nullable=True)  # OpenAI ada-002 dimension
    confidence = Column(Float, default=1.0)
    source_event_ids = Column(ARRAY(UUID(as_uuid=True)), default=list)
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="memories")

    # Indexes
    __table_args__ = (
        Index("ix_memories_user_type", "user_id", "type"),
    )


class Summary(Base):
    """Compressed context summaries."""

    __tablename__ = "summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scope = Column(String(20), nullable=False, index=True)  # conversation, user, public
    scope_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # conversation_id or user_id, NULL for public
    kind = Column(String(30), nullable=False, index=True)  # rolling_summary, user_profile, persona_memory, public_lore
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Indexes
    __table_args__ = (
        Index("ix_summaries_scope_kind", "scope", "scope_id", "kind", unique=True),
    )


class RetrievalTrace(Base):
    """Audit log of what memories were retrieved for each response."""

    __tablename__ = "retrieval_traces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, unique=True)
    memories_retrieved = Column(ARRAY(UUID(as_uuid=True)), default=list)
    scores = Column(ARRAY(Float), default=list)
    context_tokens = Column(Integer, nullable=True)
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    message = relationship("Message", back_populates="retrieval_trace")


# ===========================================
# TOKEN DATA TABLES (Phase 5)
# ===========================================


class TokenMetrics(Base):
    """Current token metrics (single row, updated frequently)."""

    __tablename__ = "token_metrics"

    id = Column(Integer, primary_key=True, default=1)
    price = Column(Float, nullable=False, default=0)
    market_cap = Column(Float, nullable=False, default=0)
    volume_24h = Column(Float, nullable=False, default=0)
    liquidity = Column(Float, nullable=True)
    holders = Column(Integer, nullable=True)
    price_change_24h = Column(Float, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TokenATH(Base):
    """ATH tracking and meter max (persisted across restarts)."""

    __tablename__ = "token_ath"

    id = Column(Integer, primary_key=True, default=1)
    market_cap_ath = Column(Float, nullable=False, default=0)
    meter_max = Column(Float, nullable=False, default=1000000)
    ath_reached_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TokenSnapshot(Base):
    """Historical token data for charts."""

    __tablename__ = "token_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    price = Column(Float, nullable=False)
    market_cap = Column(Float, nullable=False)
    volume_24h = Column(Float, nullable=True)
    holders = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


# ===========================================
# AGENT STATS TABLES (Phase 6)
# ===========================================


class AgentStats(Base):
    """Agent statistics (single row, updated on each message)."""

    __tablename__ = "agent_stats"

    id = Column(Integer, primary_key=True, default=1)
    messages_processed = Column(Integer, nullable=False, default=0)
    messages_replied = Column(Integer, nullable=False, default=0)
    messages_web = Column(Integer, nullable=False, default=0)
    messages_x = Column(Integer, nullable=False, default=0)
    semantic_memories_count = Column(Integer, nullable=False, default=0)
    learning_score = Column(Float, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ===========================================
# SOCIAL TABLES (Phase 8)
# ===========================================


class SocialInbox(Base):
    """Tweets mentioning the bot."""

    __tablename__ = "social_inbox"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tweet_id = Column(String(30), unique=True, nullable=False, index=True)
    author_id = Column(String(30), nullable=False, index=True)
    author_username = Column(String(100), nullable=False)
    text = Column(Text, nullable=False)
    in_reply_to_tweet_id = Column(String(30), nullable=True)
    conversation_id = Column(String(30), nullable=True)
    created_at_twitter = Column(DateTime(timezone=True), nullable=False)
    ingested_at = Column(DateTime(timezone=True), server_default=func.now())
    processed = Column(Boolean, default=False, index=True)
    response_id = Column(UUID(as_uuid=True), nullable=True)


class SocialPost(Base):
    """Bot's posts to X."""

    __tablename__ = "social_posts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tweet_id = Column(String(30), nullable=True, unique=True)  # NULL until posted
    type = Column(String(20), nullable=False)  # reply, post, quote
    text = Column(Text, nullable=False)
    in_reply_to_tweet_id = Column(String(30), nullable=True)
    media_ids = Column(ARRAY(String(30)), default=list)
    status = Column(String(20), nullable=False, default="draft", index=True)  # draft, approved, posted, rejected
    posted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SocialDraft(Base):
    """Pending approval queue for social posts."""

    __tablename__ = "social_drafts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id = Column(UUID(as_uuid=True), ForeignKey("social_posts.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), default="pending", index=True)  # pending, approved, rejected
    reviewer_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    post = relationship("SocialPost")


# ===========================================
# KNOWLEDGE DOCUMENTS (Phase 11)
# ===========================================


class KnowledgeDocument(Base):
    """Ingested knowledge documents (DOJ, etc.)."""

    __tablename__ = "knowledge_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(50), nullable=False, index=True)  # doj_epstein, style_tweets
    url = Column(Text, nullable=True)
    title = Column(String(500), nullable=True)
    text = Column(Text, nullable=False)
    text_hash = Column(String(64), nullable=False, index=True)  # SHA256 for deduplication
    metadata_ = Column("metadata", JSONB, default=dict)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())
    processed = Column(Boolean, default=False)


# ===========================================
# TOOL CALLS (for audit)
# ===========================================


class ToolCall(Base):
    """Log of all tool calls made by the agent."""

    __tablename__ = "tool_calls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, index=True)
    tool_name = Column(String(100), nullable=False, index=True)
    input_params = Column(JSONB, nullable=False, default=dict)
    output_result = Column(JSONB, nullable=True)
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
