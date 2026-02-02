"""
Tests for XProvider implementations.
"""

import pytest
from datetime import datetime, timedelta, timezone

from services.social.providers import (
    MockXProvider,
    XAuthError,
    XNotFoundError,
    XRateLimitError,
    get_x_provider,
    reset_provider,
)
from services.social.types import XTweet, XUser


class TestMockXProvider:
    """Tests for MockXProvider."""

    def setup_method(self):
        """Reset provider before each test."""
        reset_provider()
        self.provider = MockXProvider()

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Health check should return True."""
        result = await self.provider.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_fixture_users_loaded(self):
        """Fixture users should be available."""
        alice = await self.provider.get_user("user_alice_123")
        assert alice.username == "alice_crypto"
        assert alice.followers_count == 1200

        bob = await self.provider.get_user("user_bob_456")
        assert bob.username == "bob_trader"

    @pytest.mark.asyncio
    async def test_get_user_by_username(self):
        """Should fetch user by username."""
        alice = await self.provider.get_user_by_username("alice_crypto")
        assert alice.id == "user_alice_123"

    @pytest.mark.asyncio
    async def test_get_nonexistent_user(self):
        """Should raise XNotFoundError for unknown user."""
        with pytest.raises(XNotFoundError):
            await self.provider.get_user("unknown_user")

    @pytest.mark.asyncio
    async def test_post_tweet(self):
        """Should post a new tweet."""
        tweet = await self.provider.post_tweet("Hello, world!")

        assert tweet.id is not None
        assert tweet.text == "Hello, world!"
        assert tweet.author_id == "bot_user_123"

        # Should be retrievable
        fetched = await self.provider.get_tweet(tweet.id)
        assert fetched.text == "Hello, world!"

    @pytest.mark.asyncio
    async def test_post_reply(self):
        """Should post a reply to another tweet."""
        # Create original tweet
        original = await self.provider.post_tweet("Original tweet")

        # Reply to it
        reply = await self.provider.post_tweet(
            "This is a reply!",
            reply_to=original.id,
        )

        assert reply.reply_to_tweet_id == original.id
        assert reply.conversation_id == original.conversation_id

    @pytest.mark.asyncio
    async def test_post_tweet_length_validation(self):
        """Should reject tweets over 280 characters."""
        long_text = "x" * 300

        with pytest.raises(ValueError) as exc:
            await self.provider.post_tweet(long_text)

        assert "280" in str(exc.value)

    @pytest.mark.asyncio
    async def test_delete_tweet(self):
        """Should delete own tweet."""
        tweet = await self.provider.post_tweet("To be deleted")

        result = await self.provider.delete_tweet(tweet.id)
        assert result is True

        with pytest.raises(XNotFoundError):
            await self.provider.get_tweet(tweet.id)

    @pytest.mark.asyncio
    async def test_cannot_delete_other_user_tweet(self):
        """Should not be able to delete another user's tweet."""
        # Create a mention from another user
        mention = self.provider.create_mention(
            author_id="user_alice_123",
            text="@jeffrey_aistein hello!",
        )

        with pytest.raises(XAuthError):
            await self.provider.delete_tweet(mention.id)


class TestMockMentions:
    """Tests for mention handling."""

    def setup_method(self):
        """Reset provider before each test."""
        reset_provider()
        self.provider = MockXProvider()

    @pytest.mark.asyncio
    async def test_fetch_mentions_empty(self):
        """Should return empty list when no mentions."""
        mentions = await self.provider.fetch_mentions()
        assert mentions == []

    @pytest.mark.asyncio
    async def test_create_and_fetch_mention(self):
        """Should create and fetch mentions."""
        # Create a mention
        mention = self.provider.create_mention(
            author_id="user_alice_123",
            text="@jeffrey_aistein what do you think?",
        )

        # Fetch mentions
        mentions = await self.provider.fetch_mentions()
        assert len(mentions) == 1
        assert mentions[0].id == mention.id
        assert "@jeffrey_aistein" in mentions[0].text

    @pytest.mark.asyncio
    async def test_fetch_mentions_since_id(self):
        """Should filter mentions by since_id."""
        # Create multiple mentions
        m1 = self.provider.create_mention(
            author_id="user_alice_123",
            text="@jeffrey_aistein first",
        )
        m2 = self.provider.create_mention(
            author_id="user_bob_456",
            text="@jeffrey_aistein second",
        )

        # Fetch only new mentions
        mentions = await self.provider.fetch_mentions(since_id=m1.id)

        # Should only get m2 (newer than m1)
        assert len(mentions) == 1
        assert mentions[0].id == m2.id

    @pytest.mark.asyncio
    async def test_fetch_mentions_max_results(self):
        """Should respect max_results limit."""
        # Create 5 mentions
        for i in range(5):
            self.provider.create_mention(
                author_id="user_alice_123",
                text=f"@jeffrey_aistein mention {i}",
            )

        # Fetch only 2
        mentions = await self.provider.fetch_mentions(max_results=2)
        assert len(mentions) == 2


class TestMockThreadContext:
    """Tests for thread context reconstruction."""

    def setup_method(self):
        """Reset provider before each test."""
        reset_provider()
        self.provider = MockXProvider()

    @pytest.mark.asyncio
    async def test_fetch_thread_single_tweet(self):
        """Single tweet should return just itself."""
        tweet = await self.provider.post_tweet("Standalone tweet")

        thread = await self.provider.fetch_thread_context(tweet.id)
        assert len(thread) == 1
        assert thread[0].id == tweet.id

    @pytest.mark.asyncio
    async def test_fetch_thread_with_replies(self):
        """Should reconstruct thread from reply chain."""
        # Create a conversation
        t1 = await self.provider.post_tweet("First message")
        t2 = await self.provider.post_tweet("Reply to first", reply_to=t1.id)
        t3 = await self.provider.post_tweet("Reply to reply", reply_to=t2.id)

        # Fetch thread from last tweet
        thread = await self.provider.fetch_thread_context(t3.id)

        assert len(thread) == 3
        assert thread[0].id == t1.id  # Oldest first
        assert thread[1].id == t2.id
        assert thread[2].id == t3.id  # Newest last

    @pytest.mark.asyncio
    async def test_fetch_thread_max_depth(self):
        """Should respect max_depth limit."""
        # Create a long chain
        tweets = []
        prev_id = None
        for i in range(10):
            t = await self.provider.post_tweet(
                f"Tweet {i}",
                reply_to=prev_id,
            )
            tweets.append(t)
            prev_id = t.id

        # Fetch with max_depth=3
        thread = await self.provider.fetch_thread_context(tweets[-1].id, max_depth=3)

        # Should get 4 tweets (current + 3 parents)
        assert len(thread) == 4


class TestMockRateLimiting:
    """Tests for rate limiting simulation."""

    @pytest.mark.asyncio
    async def test_rate_limit_triggered(self):
        """Should trigger rate limit after configured calls."""
        provider = MockXProvider(rate_limit_after=3)

        # First 3 calls succeed
        await provider.health_check()
        await provider.health_check()
        await provider.health_check()

        # 4th call fails
        with pytest.raises(XRateLimitError) as exc:
            await provider.health_check()

        assert exc.value.retry_after_seconds == 60


class TestProviderFactory:
    """Tests for get_x_provider factory."""

    def setup_method(self):
        """Reset provider singleton."""
        reset_provider()

    def test_force_mock(self):
        """force_mock should always return MockXProvider."""
        provider = get_x_provider(force_mock=True)
        assert isinstance(provider, MockXProvider)

    def test_default_is_mock_without_credentials(self, monkeypatch):
        """Should default to mock when no credentials."""
        monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
        monkeypatch.delenv("X_USE_MOCK", raising=False)

        provider = get_x_provider()
        assert isinstance(provider, MockXProvider)

    def test_env_var_forces_mock(self, monkeypatch):
        """X_USE_MOCK=true should force mock."""
        monkeypatch.setenv("X_USE_MOCK", "true")
        monkeypatch.setenv("X_BEARER_TOKEN", "fake_token")

        provider = get_x_provider()
        assert isinstance(provider, MockXProvider)
