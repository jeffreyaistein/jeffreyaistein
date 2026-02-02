"""
Tests for social storage repositories.
"""

from datetime import datetime, timedelta, timezone

import pytest

from services.social.storage import (
    DraftEntry,
    DraftStatus,
    InboxEntry,
    InMemoryDraftRepository,
    InMemoryInboxRepository,
    InMemoryPostRepository,
    InMemoryReplyLogRepository,
    InMemorySettingsRepository,
    InMemoryThreadRepository,
    InMemoryUserLimitRepository,
    PostEntry,
    ReplyLogEntry,
    ThreadState,
    get_inbox_repository,
    get_settings_repository,
    reset_all_repositories,
)
from services.social.types import PostStatus, PostType, XTweet, XUser


def make_test_tweet(tweet_id: str = "tweet_123", text: str = "Hello!") -> XTweet:
    """Create a test tweet."""
    return XTweet(
        id=tweet_id,
        text=text,
        author_id="user_123",
        created_at=datetime.now(timezone.utc),
    )


class TestInboxRepository:
    """Tests for InMemoryInboxRepository."""

    def setup_method(self):
        self.repo = InMemoryInboxRepository()

    @pytest.mark.asyncio
    async def test_save_and_get(self):
        """Should save and retrieve an entry."""
        entry = InboxEntry(
            id="tweet_123",
            tweet=make_test_tweet("tweet_123"),
            author_id="user_123",
            quality_score=75,
            received_at=datetime.now(timezone.utc),
        )

        saved = await self.repo.save(entry)
        assert saved.id == "tweet_123"

        fetched = await self.repo.get("tweet_123")
        assert fetched is not None
        assert fetched.quality_score == 75

    @pytest.mark.asyncio
    async def test_exists(self):
        """Should check if entry exists."""
        assert await self.repo.exists("tweet_123") is False

        entry = InboxEntry(
            id="tweet_123",
            tweet=make_test_tweet("tweet_123"),
            author_id="user_123",
            quality_score=75,
            received_at=datetime.now(timezone.utc),
        )
        await self.repo.save(entry)

        assert await self.repo.exists("tweet_123") is True

    @pytest.mark.asyncio
    async def test_list_unprocessed(self):
        """Should list unprocessed entries."""
        # Create two entries, one processed
        e1 = InboxEntry(
            id="tweet_1",
            tweet=make_test_tweet("tweet_1"),
            author_id="user_123",
            quality_score=50,
            received_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        e2 = InboxEntry(
            id="tweet_2",
            tweet=make_test_tweet("tweet_2"),
            author_id="user_456",
            quality_score=80,
            received_at=datetime.now(timezone.utc),
            processed=True,
        )
        e3 = InboxEntry(
            id="tweet_3",
            tweet=make_test_tweet("tweet_3"),
            author_id="user_789",
            quality_score=60,
            received_at=datetime.now(timezone.utc) - timedelta(minutes=2),
        )

        await self.repo.save(e1)
        await self.repo.save(e2)
        await self.repo.save(e3)

        unprocessed = await self.repo.list_unprocessed()
        assert len(unprocessed) == 2
        # Should be sorted by received_at (oldest first)
        assert unprocessed[0].id == "tweet_1"
        assert unprocessed[1].id == "tweet_3"

    @pytest.mark.asyncio
    async def test_mark_processed(self):
        """Should mark entry as processed."""
        entry = InboxEntry(
            id="tweet_123",
            tweet=make_test_tweet("tweet_123"),
            author_id="user_123",
            quality_score=75,
            received_at=datetime.now(timezone.utc),
        )
        await self.repo.save(entry)

        result = await self.repo.mark_processed("tweet_123", skipped=True, skip_reason="test")
        assert result is True

        fetched = await self.repo.get("tweet_123")
        assert fetched.processed is True
        assert fetched.skipped is True
        assert fetched.skip_reason == "test"


class TestPostRepository:
    """Tests for InMemoryPostRepository."""

    def setup_method(self):
        self.repo = InMemoryPostRepository()

    @pytest.mark.asyncio
    async def test_save_generates_id(self):
        """Should generate ID if not provided."""
        entry = PostEntry(
            id="",
            tweet_id=None,
            text="Hello world!",
            post_type=PostType.TIMELINE,
        )

        saved = await self.repo.save(entry)
        assert saved.id.startswith("post_")
        assert saved.created_at is not None

    @pytest.mark.asyncio
    async def test_update_status(self):
        """Should update post status."""
        entry = PostEntry(
            id="",
            tweet_id=None,
            text="Hello world!",
            post_type=PostType.TIMELINE,
        )
        saved = await self.repo.save(entry)

        result = await self.repo.update_status(
            saved.id,
            PostStatus.POSTED,
            tweet_id="tweet_abc123",
        )
        assert result is True

        fetched = await self.repo.get(saved.id)
        assert fetched.status == PostStatus.POSTED
        assert fetched.tweet_id == "tweet_abc123"
        assert fetched.posted_at is not None

    @pytest.mark.asyncio
    async def test_count_today(self):
        """Should count posts made today."""
        entry = PostEntry(
            id="",
            tweet_id="tweet_1",
            text="Hello!",
            post_type=PostType.TIMELINE,
            status=PostStatus.POSTED,
            posted_at=datetime.now(timezone.utc),
        )
        await self.repo.save(entry)

        count = await self.repo.count_today()
        assert count == 1


class TestDraftRepository:
    """Tests for InMemoryDraftRepository."""

    def setup_method(self):
        self.repo = InMemoryDraftRepository()

    @pytest.mark.asyncio
    async def test_list_pending(self):
        """Should list pending drafts."""
        d1 = DraftEntry(id="", text="Draft 1", post_type=PostType.TIMELINE)
        d2 = DraftEntry(id="", text="Draft 2", post_type=PostType.REPLY, status=DraftStatus.APPROVED)
        d3 = DraftEntry(id="", text="Draft 3", post_type=PostType.TIMELINE)

        await self.repo.save(d1)
        await self.repo.save(d2)
        await self.repo.save(d3)

        pending = await self.repo.list_pending()
        assert len(pending) == 2

    @pytest.mark.asyncio
    async def test_approve(self):
        """Should approve a draft."""
        entry = DraftEntry(id="", text="Draft 1", post_type=PostType.TIMELINE)
        saved = await self.repo.save(entry)

        result = await self.repo.approve(saved.id)
        assert result is True

        fetched = await self.repo.get(saved.id)
        assert fetched.status == DraftStatus.APPROVED
        assert fetched.approved_at is not None

    @pytest.mark.asyncio
    async def test_reject(self):
        """Should reject a draft with reason."""
        entry = DraftEntry(id="", text="Draft 1", post_type=PostType.TIMELINE)
        saved = await self.repo.save(entry)

        result = await self.repo.reject(saved.id, reason="Inappropriate content")
        assert result is True

        fetched = await self.repo.get(saved.id)
        assert fetched.status == DraftStatus.REJECTED
        assert fetched.rejection_reason == "Inappropriate content"


class TestReplyLogRepository:
    """Tests for InMemoryReplyLogRepository."""

    def setup_method(self):
        self.repo = InMemoryReplyLogRepository()

    @pytest.mark.asyncio
    async def test_idempotency(self):
        """Should prevent duplicate replies."""
        assert await self.repo.has_replied("tweet_123") is False

        entry = ReplyLogEntry(
            tweet_id="tweet_123",
            reply_tweet_id="tweet_reply_456",
            replied_at=datetime.now(timezone.utc),
        )
        await self.repo.save(entry)

        assert await self.repo.has_replied("tweet_123") is True

        # Can retrieve the log entry
        fetched = await self.repo.get("tweet_123")
        assert fetched.reply_tweet_id == "tweet_reply_456"


class TestThreadRepository:
    """Tests for InMemoryThreadRepository."""

    def setup_method(self):
        self.repo = InMemoryThreadRepository()

    @pytest.mark.asyncio
    async def test_increment_creates_state(self):
        """Should create state if not exists."""
        count = await self.repo.increment_reply_count("conv_123")
        assert count == 1

        state = await self.repo.get("conv_123")
        assert state is not None
        assert state.our_reply_count == 1

    @pytest.mark.asyncio
    async def test_increment_existing(self):
        """Should increment existing state."""
        state = ThreadState(
            conversation_id="conv_123",
            author_id="user_123",
            our_reply_count=3,
        )
        await self.repo.save(state)

        count = await self.repo.increment_reply_count("conv_123")
        assert count == 4

    @pytest.mark.asyncio
    async def test_stop_thread(self):
        """Should mark thread as stopped."""
        result = await self.repo.stop_thread("conv_123", "user_requested")
        assert result is True

        assert await self.repo.is_stopped("conv_123") is True

        state = await self.repo.get("conv_123")
        assert state.stop_reason == "user_requested"


class TestUserLimitRepository:
    """Tests for InMemoryUserLimitRepository."""

    def setup_method(self):
        self.repo = InMemoryUserLimitRepository()

    @pytest.mark.asyncio
    async def test_increment(self):
        """Should increment user's daily count."""
        count1 = await self.repo.increment("user_123")
        assert count1 == 1

        count2 = await self.repo.increment("user_123")
        assert count2 == 2

        today_count = await self.repo.get_today_count("user_123")
        assert today_count == 2

    @pytest.mark.asyncio
    async def test_different_users(self):
        """Should track different users separately."""
        await self.repo.increment("user_1")
        await self.repo.increment("user_1")
        await self.repo.increment("user_2")

        assert await self.repo.get_today_count("user_1") == 2
        assert await self.repo.get_today_count("user_2") == 1


class TestSettingsRepository:
    """Tests for InMemorySettingsRepository."""

    def setup_method(self):
        self.repo = InMemorySettingsRepository()

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """Should set and get values."""
        await self.repo.set("last_mention_id", "tweet_123")

        value = await self.repo.get("last_mention_id")
        assert value == "tweet_123"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        """Should return None for nonexistent key."""
        value = await self.repo.get("nonexistent")
        assert value is None

    @pytest.mark.asyncio
    async def test_delete(self):
        """Should delete a setting."""
        await self.repo.set("key", "value")
        assert await self.repo.get("key") == "value"

        result = await self.repo.delete("key")
        assert result is True
        assert await self.repo.get("key") is None


class TestRepositoryFactory:
    """Tests for repository factory functions."""

    def setup_method(self):
        reset_all_repositories()

    def teardown_method(self):
        reset_all_repositories()

    @pytest.mark.asyncio
    async def test_singleton_behavior(self):
        """Should return same instance."""
        repo1 = get_inbox_repository()
        repo2 = get_inbox_repository()
        assert repo1 is repo2

    @pytest.mark.asyncio
    async def test_reset_clears_singletons(self):
        """Reset should clear singletons."""
        repo1 = get_settings_repository()
        reset_all_repositories()
        repo2 = get_settings_repository()
        assert repo1 is not repo2
