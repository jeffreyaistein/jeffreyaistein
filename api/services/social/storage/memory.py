"""
Jeffrey AIstein - In-Memory Storage Implementations

In-memory implementations for testing and development.
All data is lost when the process restarts.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

import structlog

from services.social.storage.base import (
    DraftEntry,
    DraftRepository,
    DraftStatus,
    InboxEntry,
    InboxRepository,
    PostEntry,
    PostRepository,
    PostStatus,
    ReplyLogEntry,
    ReplyLogRepository,
    Settings,
    SettingsRepository,
    ThreadRepository,
    ThreadState,
    UserLimitRepository,
    UserLimitState,
)

logger = structlog.get_logger()


class InMemoryInboxRepository(InboxRepository):
    """In-memory inbox repository."""

    def __init__(self):
        self._entries: dict[str, InboxEntry] = {}

    async def save(self, entry: InboxEntry) -> InboxEntry:
        self._entries[entry.id] = entry
        logger.debug("inbox_entry_saved", tweet_id=entry.id)
        return entry

    async def get(self, tweet_id: str) -> Optional[InboxEntry]:
        return self._entries.get(tweet_id)

    async def exists(self, tweet_id: str) -> bool:
        return tweet_id in self._entries

    async def list_unprocessed(self, limit: int = 100) -> list[InboxEntry]:
        unprocessed = [e for e in self._entries.values() if not e.processed]
        unprocessed.sort(key=lambda e: e.received_at)
        return unprocessed[:limit]

    async def mark_processed(
        self,
        tweet_id: str,
        skipped: bool = False,
        skip_reason: Optional[str] = None,
    ) -> bool:
        entry = self._entries.get(tweet_id)
        if not entry:
            return False

        entry.processed = True
        entry.processed_at = datetime.now(timezone.utc)
        entry.skipped = skipped
        entry.skip_reason = skip_reason
        return True

    def clear(self):
        """Clear all entries (for testing)."""
        self._entries.clear()


class InMemoryPostRepository(PostRepository):
    """In-memory post repository."""

    def __init__(self):
        self._entries: dict[str, PostEntry] = {}
        self._by_tweet_id: dict[str, str] = {}  # tweet_id -> post_id

    async def save(self, entry: PostEntry) -> PostEntry:
        if not entry.id:
            entry.id = f"post_{uuid4().hex[:12]}"
        if not entry.created_at:
            entry.created_at = datetime.now(timezone.utc)

        self._entries[entry.id] = entry
        if entry.tweet_id:
            self._by_tweet_id[entry.tweet_id] = entry.id

        logger.debug("post_entry_saved", post_id=entry.id, tweet_id=entry.tweet_id)
        return entry

    async def get(self, post_id: str) -> Optional[PostEntry]:
        return self._entries.get(post_id)

    async def get_by_tweet_id(self, tweet_id: str) -> Optional[PostEntry]:
        post_id = self._by_tweet_id.get(tweet_id)
        if post_id:
            return self._entries.get(post_id)
        return None

    async def update_status(
        self,
        post_id: str,
        status: PostStatus,
        tweet_id: Optional[str] = None,
    ) -> bool:
        entry = self._entries.get(post_id)
        if not entry:
            return False

        entry.status = status
        if tweet_id:
            entry.tweet_id = tweet_id
            self._by_tweet_id[tweet_id] = post_id
        if status == PostStatus.POSTED:
            entry.posted_at = datetime.now(timezone.utc)

        return True

    async def count_today(self) -> int:
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return sum(
            1 for e in self._entries.values()
            if e.posted_at and e.posted_at >= today_start
        )

    async def count_last_hour(self) -> int:
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        return sum(
            1 for e in self._entries.values()
            if e.posted_at and e.posted_at >= one_hour_ago
        )

    def clear(self):
        """Clear all entries (for testing)."""
        self._entries.clear()
        self._by_tweet_id.clear()


class InMemoryDraftRepository(DraftRepository):
    """In-memory draft repository."""

    def __init__(self):
        self._entries: dict[str, DraftEntry] = {}

    async def save(self, entry: DraftEntry) -> DraftEntry:
        if not entry.id:
            entry.id = f"draft_{uuid4().hex[:12]}"
        if not entry.created_at:
            entry.created_at = datetime.now(timezone.utc)

        self._entries[entry.id] = entry
        logger.debug("draft_entry_saved", draft_id=entry.id)
        return entry

    async def get(self, draft_id: str) -> Optional[DraftEntry]:
        return self._entries.get(draft_id)

    async def list_pending(self, limit: int = 100) -> list[DraftEntry]:
        pending = [
            e for e in self._entries.values()
            if e.status == DraftStatus.PENDING
        ]
        pending.sort(key=lambda e: e.created_at or datetime.min)
        return pending[:limit]

    async def approve(self, draft_id: str) -> bool:
        entry = self._entries.get(draft_id)
        if not entry:
            return False

        entry.status = DraftStatus.APPROVED
        entry.approved_at = datetime.now(timezone.utc)
        return True

    async def reject(self, draft_id: str, reason: Optional[str] = None) -> bool:
        entry = self._entries.get(draft_id)
        if not entry:
            return False

        entry.status = DraftStatus.REJECTED
        entry.rejected_at = datetime.now(timezone.utc)
        entry.rejection_reason = reason
        return True

    def clear(self):
        """Clear all entries (for testing)."""
        self._entries.clear()


class InMemoryReplyLogRepository(ReplyLogRepository):
    """In-memory reply log repository for idempotency."""

    def __init__(self):
        self._entries: dict[str, ReplyLogEntry] = {}

    async def save(self, entry: ReplyLogEntry) -> ReplyLogEntry:
        self._entries[entry.tweet_id] = entry
        logger.debug(
            "reply_log_saved",
            tweet_id=entry.tweet_id,
            reply_tweet_id=entry.reply_tweet_id,
        )
        return entry

    async def has_replied(self, tweet_id: str) -> bool:
        return tweet_id in self._entries

    async def get(self, tweet_id: str) -> Optional[ReplyLogEntry]:
        return self._entries.get(tweet_id)

    def clear(self):
        """Clear all entries (for testing)."""
        self._entries.clear()


class InMemoryThreadRepository(ThreadRepository):
    """In-memory thread state repository."""

    def __init__(self):
        self._entries: dict[str, ThreadState] = {}

    async def save(self, state: ThreadState) -> ThreadState:
        self._entries[state.conversation_id] = state
        logger.debug(
            "thread_state_saved",
            conversation_id=state.conversation_id,
            reply_count=state.our_reply_count,
        )
        return state

    async def get(self, conversation_id: str) -> Optional[ThreadState]:
        return self._entries.get(conversation_id)

    async def increment_reply_count(self, conversation_id: str) -> int:
        state = self._entries.get(conversation_id)
        if not state:
            # Create new state
            state = ThreadState(
                conversation_id=conversation_id,
                author_id="",  # Will be set later
                our_reply_count=0,
            )
            self._entries[conversation_id] = state

        state.our_reply_count += 1
        state.last_reply_at = datetime.now(timezone.utc)
        return state.our_reply_count

    async def stop_thread(self, conversation_id: str, reason: str) -> bool:
        state = self._entries.get(conversation_id)
        if not state:
            state = ThreadState(
                conversation_id=conversation_id,
                author_id="",
            )
            self._entries[conversation_id] = state

        state.stopped = True
        state.stop_reason = reason
        logger.info(
            "thread_stopped",
            conversation_id=conversation_id,
            reason=reason,
        )
        return True

    async def is_stopped(self, conversation_id: str) -> bool:
        state = self._entries.get(conversation_id)
        if not state:
            return False
        return state.stopped

    def clear(self):
        """Clear all entries (for testing)."""
        self._entries.clear()


class InMemoryUserLimitRepository(UserLimitRepository):
    """In-memory per-user daily limit repository."""

    def __init__(self):
        self._entries: dict[str, UserLimitState] = {}  # key = f"{user_id}:{date}"

    def _make_key(self, user_id: str, date: Optional[str] = None) -> str:
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return f"{user_id}:{date}"

    async def get_today_count(self, user_id: str) -> int:
        key = self._make_key(user_id)
        state = self._entries.get(key)
        return state.reply_count if state else 0

    async def increment(self, user_id: str) -> int:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        key = self._make_key(user_id, date)

        state = self._entries.get(key)
        if not state:
            state = UserLimitState(user_id=user_id, date=date, reply_count=0)
            self._entries[key] = state

        state.reply_count += 1
        logger.debug(
            "user_limit_incremented",
            user_id=user_id,
            date=date,
            count=state.reply_count,
        )
        return state.reply_count

    async def reset_for_day(self, date: str) -> int:
        """Reset counts for entries older than the given date."""
        keys_to_delete = [
            k for k in self._entries.keys()
            if not k.endswith(f":{date}")
        ]
        for key in keys_to_delete:
            del self._entries[key]
        return len(keys_to_delete)

    def clear(self):
        """Clear all entries (for testing)."""
        self._entries.clear()


class InMemorySettingsRepository(SettingsRepository):
    """In-memory settings repository."""

    def __init__(self):
        self._entries: dict[str, Settings] = {}

    async def get(self, key: str) -> Optional[str]:
        setting = self._entries.get(key)
        return setting.value if setting else None

    async def set(self, key: str, value: str) -> bool:
        self._entries[key] = Settings(
            key=key,
            value=value,
            updated_at=datetime.now(timezone.utc),
        )
        return True

    async def delete(self, key: str) -> bool:
        if key in self._entries:
            del self._entries[key]
            return True
        return False

    def clear(self):
        """Clear all entries (for testing)."""
        self._entries.clear()
