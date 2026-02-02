"""
Jeffrey AIstein - Storage Base Interfaces

Abstract repository interfaces for X bot state management.
Implementations: InMemory (for testing/dev), Postgres (for production).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from services.social.types import PostStatus, PostType, XTweet


class DraftStatus(str, Enum):
    """Status of a draft post."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    POSTED = "posted"
    EXPIRED = "expired"


@dataclass
class InboxEntry:
    """A mention stored in the inbox."""
    id: str  # Same as tweet_id
    tweet: XTweet
    author_id: str
    quality_score: int
    received_at: datetime
    processed: bool = False
    processed_at: Optional[datetime] = None
    skipped: bool = False
    skip_reason: Optional[str] = None


@dataclass
class PostEntry:
    """A post made by the bot."""
    id: str  # Internal ID
    tweet_id: Optional[str]  # X tweet ID (None if not posted yet)
    text: str
    post_type: PostType
    reply_to_id: Optional[str] = None  # Tweet we're replying to
    status: PostStatus = PostStatus.DRAFT
    created_at: Optional[datetime] = None
    posted_at: Optional[datetime] = None


@dataclass
class DraftEntry:
    """A draft awaiting approval."""
    id: str
    text: str
    post_type: PostType
    reply_to_id: Optional[str] = None
    status: DraftStatus = DraftStatus.PENDING
    created_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None


@dataclass
class ReplyLogEntry:
    """Record of a reply to prevent duplicates (idempotency)."""
    tweet_id: str  # Tweet we replied to
    reply_tweet_id: str  # Our reply's tweet ID
    replied_at: datetime


@dataclass
class ThreadState:
    """State of an active conversation thread."""
    conversation_id: str
    author_id: str
    our_reply_count: int = 0
    last_reply_at: Optional[datetime] = None
    stopped: bool = False
    stop_reason: Optional[str] = None


@dataclass
class UserLimitState:
    """Per-user daily limit tracking."""
    user_id: str
    date: str  # YYYY-MM-DD
    reply_count: int = 0


@dataclass
class Settings:
    """Runtime settings/state."""
    key: str
    value: str
    updated_at: Optional[datetime] = None


class InboxRepository(ABC):
    """Repository for incoming mentions."""

    @abstractmethod
    async def save(self, entry: InboxEntry) -> InboxEntry:
        """Save an inbox entry."""
        pass

    @abstractmethod
    async def get(self, tweet_id: str) -> Optional[InboxEntry]:
        """Get an inbox entry by tweet ID."""
        pass

    @abstractmethod
    async def exists(self, tweet_id: str) -> bool:
        """Check if a tweet is already in the inbox."""
        pass

    @abstractmethod
    async def list_unprocessed(self, limit: int = 100) -> list[InboxEntry]:
        """List unprocessed inbox entries."""
        pass

    @abstractmethod
    async def mark_processed(self, tweet_id: str, skipped: bool = False, skip_reason: Optional[str] = None) -> bool:
        """Mark an entry as processed."""
        pass


class PostRepository(ABC):
    """Repository for bot's posts."""

    @abstractmethod
    async def save(self, entry: PostEntry) -> PostEntry:
        """Save a post entry."""
        pass

    @abstractmethod
    async def get(self, post_id: str) -> Optional[PostEntry]:
        """Get a post by internal ID."""
        pass

    @abstractmethod
    async def get_by_tweet_id(self, tweet_id: str) -> Optional[PostEntry]:
        """Get a post by X tweet ID."""
        pass

    @abstractmethod
    async def update_status(self, post_id: str, status: PostStatus, tweet_id: Optional[str] = None) -> bool:
        """Update post status."""
        pass

    @abstractmethod
    async def count_today(self) -> int:
        """Count posts made today."""
        pass

    @abstractmethod
    async def count_last_hour(self) -> int:
        """Count posts made in the last hour."""
        pass


class DraftRepository(ABC):
    """Repository for drafts awaiting approval."""

    @abstractmethod
    async def save(self, entry: DraftEntry) -> DraftEntry:
        """Save a draft."""
        pass

    @abstractmethod
    async def get(self, draft_id: str) -> Optional[DraftEntry]:
        """Get a draft by ID."""
        pass

    @abstractmethod
    async def list_pending(self, limit: int = 100) -> list[DraftEntry]:
        """List pending drafts."""
        pass

    @abstractmethod
    async def approve(self, draft_id: str) -> bool:
        """Approve a draft."""
        pass

    @abstractmethod
    async def reject(self, draft_id: str, reason: Optional[str] = None) -> bool:
        """Reject a draft."""
        pass


class ReplyLogRepository(ABC):
    """Repository for reply idempotency tracking."""

    @abstractmethod
    async def save(self, entry: ReplyLogEntry) -> ReplyLogEntry:
        """Save a reply log entry."""
        pass

    @abstractmethod
    async def has_replied(self, tweet_id: str) -> bool:
        """Check if we've already replied to a tweet."""
        pass

    @abstractmethod
    async def get(self, tweet_id: str) -> Optional[ReplyLogEntry]:
        """Get reply log entry for a tweet."""
        pass


class ThreadRepository(ABC):
    """Repository for conversation thread state."""

    @abstractmethod
    async def save(self, state: ThreadState) -> ThreadState:
        """Save thread state."""
        pass

    @abstractmethod
    async def get(self, conversation_id: str) -> Optional[ThreadState]:
        """Get thread state by conversation ID."""
        pass

    @abstractmethod
    async def increment_reply_count(self, conversation_id: str) -> int:
        """Increment reply count and return new value."""
        pass

    @abstractmethod
    async def stop_thread(self, conversation_id: str, reason: str) -> bool:
        """Mark a thread as stopped."""
        pass

    @abstractmethod
    async def is_stopped(self, conversation_id: str) -> bool:
        """Check if a thread is stopped."""
        pass


class UserLimitRepository(ABC):
    """Repository for per-user daily limits."""

    @abstractmethod
    async def get_today_count(self, user_id: str) -> int:
        """Get reply count for user today."""
        pass

    @abstractmethod
    async def increment(self, user_id: str) -> int:
        """Increment user's reply count and return new value."""
        pass

    @abstractmethod
    async def reset_for_day(self, date: str) -> int:
        """Reset all counts for a new day. Returns count of reset entries."""
        pass


class SettingsRepository(ABC):
    """Repository for runtime settings."""

    @abstractmethod
    async def get(self, key: str) -> Optional[str]:
        """Get a setting value."""
        pass

    @abstractmethod
    async def set(self, key: str, value: str) -> bool:
        """Set a setting value."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a setting."""
        pass


# Well-known setting keys
SETTING_LAST_MENTION_ID = "last_mention_id"
SETTING_LAST_TIMELINE_POST = "last_timeline_post_at"
SETTING_NEXT_TIMELINE_POST = "next_timeline_post_at"

# Runtime toggleable settings (can override env vars)
SETTING_SAFE_MODE = "safe_mode"
SETTING_APPROVAL_REQUIRED = "approval_required"
