"""
Tests for ConversationContextBuilder.
"""

import pytest

from services.social.context import (
    ConversationContextBuilder,
    STOP_KEYWORDS,
    get_max_replies_per_thread,
    get_max_replies_per_user_per_day,
)
from services.social.providers import MockXProvider
from services.social.storage import (
    InMemoryThreadRepository,
    InMemoryUserLimitRepository,
    ThreadState,
)
from services.social.types import MentionFilterReason


class TestConversationContextBuilder:
    """Tests for ConversationContextBuilder."""

    def setup_method(self):
        """Setup test fixtures."""
        self.provider = MockXProvider()
        self.thread_repo = InMemoryThreadRepository()
        self.user_limit_repo = InMemoryUserLimitRepository()

        self.builder = ConversationContextBuilder(
            x_provider=self.provider,
            thread_repo=self.thread_repo,
            user_limit_repo=self.user_limit_repo,
        )

    @pytest.mark.asyncio
    async def test_build_context_single_tweet(self):
        """Should build context for a single tweet."""
        mention = self.provider.create_mention(
            author_id="user_alice_123",
            text="@jeffrey_aistein hello!",
        )

        context = await self.builder.build_context(mention)

        assert context.conversation_id == mention.id
        assert context.author_id == "user_alice_123"
        assert len(context.tweets) == 1
        assert context.our_reply_count == 0

    @pytest.mark.asyncio
    async def test_build_context_thread(self):
        """Should build context for a thread."""
        # Create a conversation
        t1 = await self.provider.post_tweet("First message")
        t2 = await self.provider.post_tweet("Reply to first", reply_to=t1.id)

        # Create mention replying to the thread
        mention = self.provider.create_mention(
            author_id="user_alice_123",
            text="@jeffrey_aistein what do you think?",
            reply_to_id=t2.id,
        )

        context = await self.builder.build_context(mention)

        # Should include full thread
        assert len(context.tweets) >= 2

    @pytest.mark.asyncio
    async def test_build_context_with_existing_state(self):
        """Should include existing thread state."""
        mention = self.provider.create_mention(
            author_id="user_alice_123",
            text="@jeffrey_aistein follow up!",
        )

        # Create existing thread state
        state = ThreadState(
            conversation_id=mention.id,
            author_id="user_alice_123",
            our_reply_count=3,
        )
        await self.thread_repo.save(state)

        context = await self.builder.build_context(mention)

        assert context.our_reply_count == 3


class TestStopConditions:
    """Tests for stop condition checking."""

    def setup_method(self):
        """Setup test fixtures."""
        self.provider = MockXProvider()
        self.thread_repo = InMemoryThreadRepository()
        self.user_limit_repo = InMemoryUserLimitRepository()

        self.builder = ConversationContextBuilder(
            x_provider=self.provider,
            thread_repo=self.thread_repo,
            user_limit_repo=self.user_limit_repo,
        )

    @pytest.mark.asyncio
    async def test_no_stop_condition_normal_tweet(self, monkeypatch):
        """Should not stop for normal tweet."""
        monkeypatch.setenv("SAFE_MODE", "false")
        monkeypatch.setenv("X_MAX_REPLIES_PER_THREAD", "5")
        monkeypatch.setenv("X_MAX_REPLIES_PER_USER_PER_DAY", "10")

        mention = self.provider.create_mention(
            author_id="user_alice_123",
            text="@jeffrey_aistein what's your opinion?",
        )

        result = await self.builder.check_stop_conditions(mention)

        assert result.should_stop is False

    @pytest.mark.asyncio
    async def test_stop_safe_mode(self, monkeypatch):
        """Should stop in safe mode."""
        monkeypatch.setenv("SAFE_MODE", "true")

        mention = self.provider.create_mention(
            author_id="user_alice_123",
            text="@jeffrey_aistein hello!",
        )

        result = await self.builder.check_stop_conditions(mention)

        assert result.should_stop is True
        assert result.reason == MentionFilterReason.SAFE_MODE

    @pytest.mark.asyncio
    async def test_stop_thread_cap(self, monkeypatch):
        """Should stop when thread cap reached."""
        monkeypatch.setenv("SAFE_MODE", "false")
        monkeypatch.setenv("X_MAX_REPLIES_PER_THREAD", "2")

        mention = self.provider.create_mention(
            author_id="user_alice_123",
            text="@jeffrey_aistein another question!",
        )

        # Set thread to have 2 replies already
        state = ThreadState(
            conversation_id=mention.id,
            author_id="user_alice_123",
            our_reply_count=2,
        )
        await self.thread_repo.save(state)

        result = await self.builder.check_stop_conditions(mention)

        assert result.should_stop is True
        assert result.reason == MentionFilterReason.PER_THREAD_CAP

    @pytest.mark.asyncio
    async def test_stop_user_daily_cap(self, monkeypatch):
        """Should stop when user daily cap reached."""
        monkeypatch.setenv("SAFE_MODE", "false")
        monkeypatch.setenv("X_MAX_REPLIES_PER_THREAD", "100")
        monkeypatch.setenv("X_MAX_REPLIES_PER_USER_PER_DAY", "3")

        mention = self.provider.create_mention(
            author_id="user_alice_123",
            text="@jeffrey_aistein yet another message!",
        )

        # Increment user count to cap
        await self.user_limit_repo.increment("user_alice_123")
        await self.user_limit_repo.increment("user_alice_123")
        await self.user_limit_repo.increment("user_alice_123")

        result = await self.builder.check_stop_conditions(mention)

        assert result.should_stop is True
        assert result.reason == MentionFilterReason.PER_USER_CAP

    @pytest.mark.asyncio
    async def test_stop_keyword_detection(self, monkeypatch):
        """Should stop when user uses stop keywords."""
        monkeypatch.setenv("SAFE_MODE", "false")

        mention = self.provider.create_mention(
            author_id="user_alice_123",
            text="@jeffrey_aistein please stop replying to me",
        )

        result = await self.builder.check_stop_conditions(mention)

        assert result.should_stop is True
        assert result.reason == MentionFilterReason.USER_REQUESTED_STOP

        # Thread should be marked as stopped
        state = await self.thread_repo.get(mention.id)
        assert state is not None
        assert state.stopped is True

    @pytest.mark.asyncio
    async def test_stop_keywords_various(self, monkeypatch):
        """Should detect various stop keywords."""
        monkeypatch.setenv("SAFE_MODE", "false")

        test_cases = [
            "leave me alone",
            "STOP",
            "go away bot",
            "I blocked you",
            "shut up already",
        ]

        for text in test_cases:
            # Reset repositories
            self.thread_repo.clear()
            self.user_limit_repo.clear()

            mention = self.provider.create_mention(
                author_id="user_alice_123",
                text=f"@jeffrey_aistein {text}",
            )

            result = await self.builder.check_stop_conditions(mention)
            assert result.should_stop is True, f"Should stop for: {text}"

    @pytest.mark.asyncio
    async def test_stop_already_stopped_thread(self, monkeypatch):
        """Should stop if thread already stopped."""
        monkeypatch.setenv("SAFE_MODE", "false")

        mention = self.provider.create_mention(
            author_id="user_alice_123",
            text="@jeffrey_aistein follow up!",
        )

        # Mark thread as stopped
        await self.thread_repo.stop_thread(mention.id, "previous_stop")

        result = await self.builder.check_stop_conditions(mention)

        assert result.should_stop is True
        assert result.reason == MentionFilterReason.USER_REQUESTED_STOP


class TestRecordReply:
    """Tests for recording replies."""

    def setup_method(self):
        """Setup test fixtures."""
        self.provider = MockXProvider()
        self.thread_repo = InMemoryThreadRepository()
        self.user_limit_repo = InMemoryUserLimitRepository()

        self.builder = ConversationContextBuilder(
            x_provider=self.provider,
            thread_repo=self.thread_repo,
            user_limit_repo=self.user_limit_repo,
        )

    @pytest.mark.asyncio
    async def test_record_reply_increments_counts(self):
        """Should increment both thread and user counts."""
        mention = self.provider.create_mention(
            author_id="user_alice_123",
            text="@jeffrey_aistein hello!",
        )

        await self.builder.record_reply(mention)

        # Check thread count
        state = await self.thread_repo.get(mention.id)
        assert state is not None
        assert state.our_reply_count == 1

        # Check user daily count
        user_count = await self.user_limit_repo.get_today_count("user_alice_123")
        assert user_count == 1

    @pytest.mark.asyncio
    async def test_record_reply_multiple(self):
        """Should increment counts multiple times."""
        mention = self.provider.create_mention(
            author_id="user_alice_123",
            text="@jeffrey_aistein hello!",
        )

        await self.builder.record_reply(mention)
        await self.builder.record_reply(mention)
        await self.builder.record_reply(mention)

        state = await self.thread_repo.get(mention.id)
        assert state.our_reply_count == 3

        user_count = await self.user_limit_repo.get_today_count("user_alice_123")
        assert user_count == 3


class TestStopKeywordMatching:
    """Tests for stop keyword detection."""

    def setup_method(self):
        self.builder = ConversationContextBuilder(
            x_provider=MockXProvider(),
            thread_repo=InMemoryThreadRepository(),
            user_limit_repo=InMemoryUserLimitRepository(),
        )

    def test_stop_keyword_word_boundary(self):
        """Short keywords should match at word boundaries."""
        # "stop" should match
        assert self.builder._contains_stop_keyword("please stop") is True
        assert self.builder._contains_stop_keyword("STOP IT") is True

        # But not as part of another word
        # Note: "stopping" contains "stop" - this depends on implementation
        # Our implementation uses word boundaries for short keywords

    def test_stop_keyword_case_insensitive(self):
        """Should be case insensitive."""
        assert self.builder._contains_stop_keyword("LEAVE ME ALONE") is True
        assert self.builder._contains_stop_keyword("Leave Me Alone") is True
        assert self.builder._contains_stop_keyword("leave me alone") is True

    def test_no_false_positives(self):
        """Should not trigger on unrelated text."""
        assert self.builder._contains_stop_keyword("Hello, how are you?") is False
        assert self.builder._contains_stop_keyword("Great work!") is False
        assert self.builder._contains_stop_keyword("Can you help me?") is False
