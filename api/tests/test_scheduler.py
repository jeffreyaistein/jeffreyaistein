"""
Tests for scheduler loops.
"""

from datetime import datetime, timezone

import pytest

from services.social.providers import MockXProvider
from services.social.scheduler import (
    FakeClock,
    IngestionLoop,
    TimelinePosterLoop,
)
from services.social.storage import (
    DraftStatus,
    InMemoryDraftRepository,
    InMemoryInboxRepository,
    InMemoryPostRepository,
    InMemoryReplyLogRepository,
    InMemorySettingsRepository,
    SETTING_LAST_MENTION_ID,
)


class TestFakeClock:
    """Tests for FakeClock."""

    def test_initial_time(self):
        """Clock should start at current time by default."""
        clock = FakeClock()
        assert clock.now() is not None

    def test_custom_start_time(self):
        """Clock should accept custom start time."""
        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        clock = FakeClock(start_time=start)
        assert clock.now() == start

    def test_advance(self):
        """Should advance time."""
        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        clock = FakeClock(start_time=start)

        clock.advance(60)  # 1 minute

        expected = datetime(2024, 1, 1, 12, 1, 0, tzinfo=timezone.utc)
        assert clock.now() == expected

    @pytest.mark.asyncio
    async def test_sleep_advances_time(self):
        """Sleep should advance time and record call."""
        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        clock = FakeClock(start_time=start)

        await clock.sleep(30)

        assert clock.sleep_calls == [30]
        expected = datetime(2024, 1, 1, 12, 0, 30, tzinfo=timezone.utc)
        assert clock.now() == expected


class TestIngestionLoop:
    """Tests for IngestionLoop."""

    def setup_method(self):
        """Setup test fixtures."""
        self.provider = MockXProvider()
        self.clock = FakeClock()
        self.inbox_repo = InMemoryInboxRepository()
        self.reply_log_repo = InMemoryReplyLogRepository()
        self.settings_repo = InMemorySettingsRepository()

        self.loop = IngestionLoop(
            x_provider=self.provider,
            clock=self.clock,
            inbox_repo=self.inbox_repo,
            reply_log_repo=self.reply_log_repo,
            settings_repo=self.settings_repo,
            poll_interval=45,
        )

    @pytest.mark.asyncio
    async def test_poll_no_mentions(self):
        """Should handle no mentions gracefully."""
        stats = await self.loop.poll_once()

        assert stats["fetched"] == 0
        assert stats["stored"] == 0

    @pytest.mark.asyncio
    async def test_poll_stores_high_quality_mentions(self):
        """Should store mentions from high-quality accounts."""
        # Create mention from high-quality user (alice)
        self.provider.create_mention(
            author_id="user_alice_123",
            text="@jeffrey_aistein what's your take on the market?",
        )

        stats = await self.loop.poll_once()

        assert stats["fetched"] == 1
        assert stats["stored"] == 1
        assert stats["filtered"] == 0

    @pytest.mark.asyncio
    async def test_poll_filters_low_quality_accounts(self):
        """Should filter mentions from low-quality accounts."""
        # Create mention from spam user
        self.provider.create_mention(
            author_id="user_spam_789",
            text="@jeffrey_aistein FREE CRYPTO!!!",
        )

        stats = await self.loop.poll_once()

        assert stats["fetched"] == 1
        assert stats["stored"] == 0
        assert stats["filtered"] == 1

    @pytest.mark.asyncio
    async def test_poll_deduplicates_inbox(self):
        """Should not store duplicate mentions."""
        # Create mention
        mention = self.provider.create_mention(
            author_id="user_alice_123",
            text="@jeffrey_aistein hello!",
        )

        # First poll stores it
        stats1 = await self.loop.poll_once()
        assert stats1["stored"] == 1

        # Clear last_mention_id to simulate re-poll
        await self.settings_repo.delete(SETTING_LAST_MENTION_ID)

        # Second poll should skip duplicate
        stats2 = await self.loop.poll_once()
        assert stats2["duplicates"] == 1
        assert stats2["stored"] == 0

    @pytest.mark.asyncio
    async def test_poll_updates_last_mention_id(self):
        """Should update last_mention_id after polling."""
        mention = self.provider.create_mention(
            author_id="user_alice_123",
            text="@jeffrey_aistein hello!",
        )

        await self.loop.poll_once()

        last_id = await self.settings_repo.get(SETTING_LAST_MENTION_ID)
        assert last_id == mention.id

    @pytest.mark.asyncio
    async def test_cumulative_stats(self):
        """Should track cumulative stats."""
        # Create two mentions
        self.provider.create_mention(
            author_id="user_alice_123",
            text="@jeffrey_aistein first",
        )
        self.provider.create_mention(
            author_id="user_bob_456",
            text="@jeffrey_aistein second",
        )

        await self.loop.poll_once()

        stats = self.loop.get_stats()
        assert stats["total_fetched"] == 2
        assert stats["total_stored"] == 2


class TestTimelinePosterLoop:
    """Tests for TimelinePosterLoop."""

    def setup_method(self):
        """Setup test fixtures."""
        self.provider = MockXProvider()
        self.clock = FakeClock()
        self.post_repo = InMemoryPostRepository()
        self.draft_repo = InMemoryDraftRepository()
        self.settings_repo = InMemorySettingsRepository()

        self.loop = TimelinePosterLoop(
            x_provider=self.provider,
            clock=self.clock,
            post_repo=self.post_repo,
            draft_repo=self.draft_repo,
            settings_repo=self.settings_repo,
            interval=10800,  # 3h
            jitter=600,  # 10min
        )
        self.loop.seed_random(42)  # Deterministic for testing

    @pytest.mark.asyncio
    async def test_post_creates_draft_when_approval_required(self, monkeypatch):
        """Should create draft when APPROVAL_REQUIRED=true."""
        monkeypatch.setenv("APPROVAL_REQUIRED", "true")
        monkeypatch.setenv("SAFE_MODE", "false")

        result = await self.loop.post_once()

        assert result["drafted"] is True
        assert result["posted"] is False
        assert result["draft_id"] is not None

        # Check draft was created
        drafts = await self.draft_repo.list_pending()
        assert len(drafts) == 1
        assert drafts[0].status == DraftStatus.PENDING

    @pytest.mark.asyncio
    async def test_post_directly_when_no_approval_required(self, monkeypatch):
        """Should post directly when APPROVAL_REQUIRED=false."""
        monkeypatch.setenv("APPROVAL_REQUIRED", "false")
        monkeypatch.setenv("SAFE_MODE", "false")

        result = await self.loop.post_once()

        assert result["posted"] is True
        assert result["drafted"] is False
        assert result["tweet_id"] is not None

    @pytest.mark.asyncio
    async def test_skip_in_safe_mode(self, monkeypatch):
        """Should skip posting in SAFE_MODE."""
        monkeypatch.setenv("SAFE_MODE", "true")

        result = await self.loop.post_once()

        assert result["skipped"] is True
        assert result["reason"] == "safe_mode"
        assert result["posted"] is False
        assert result["drafted"] is False

    @pytest.mark.asyncio
    async def test_skip_on_hourly_limit(self, monkeypatch):
        """Should skip when hourly limit reached."""
        monkeypatch.setenv("APPROVAL_REQUIRED", "false")
        monkeypatch.setenv("SAFE_MODE", "false")
        monkeypatch.setenv("X_HOURLY_POST_LIMIT", "2")

        # Post twice to reach limit
        await self.loop.post_once()
        await self.loop.post_once()

        # Third should be skipped
        result = await self.loop.post_once()

        assert result["skipped"] is True
        assert result["reason"] == "hourly_limit"

    @pytest.mark.asyncio
    async def test_skip_on_daily_limit(self, monkeypatch):
        """Should skip when daily limit reached."""
        monkeypatch.setenv("APPROVAL_REQUIRED", "false")
        monkeypatch.setenv("SAFE_MODE", "false")
        monkeypatch.setenv("X_HOURLY_POST_LIMIT", "100")  # High hourly
        monkeypatch.setenv("X_DAILY_POST_LIMIT", "2")

        # Post twice to reach limit
        await self.loop.post_once()
        await self.loop.post_once()

        # Third should be skipped
        result = await self.loop.post_once()

        assert result["skipped"] is True
        assert result["reason"] == "daily_limit"

    @pytest.mark.asyncio
    async def test_cumulative_stats(self, monkeypatch):
        """Should track cumulative stats."""
        monkeypatch.setenv("APPROVAL_REQUIRED", "false")
        monkeypatch.setenv("SAFE_MODE", "false")

        await self.loop.post_once()

        stats = self.loop.get_stats()
        assert stats["total_posts"] == 1
        assert stats["total_drafts"] == 0

    @pytest.mark.asyncio
    async def test_jitter_calculation(self):
        """Should calculate next post time with jitter."""
        self.loop.seed_random(42)

        # Calculate several times, should vary within jitter range
        times = []
        for _ in range(5):
            next_time = self.loop._calculate_next_post_time()
            times.append(next_time)
            self.clock.advance(1)  # Small advance to change base time

        # All times should be different (due to jitter)
        assert len(set(times)) == 5

        # Should be roughly interval +/- jitter from current time
        current = self.clock.timestamp()
        for t in times:
            offset = t - current
            # Within interval ± jitter (with some tolerance for clock advance)
            assert 10800 - 700 <= offset <= 10800 + 700
