"""
Jeffrey AIstein - Mock X Provider

In-memory mock implementation for testing.
Provides deterministic responses and configurable behavior.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

import structlog

from services.social.providers.base import (
    XAuthError,
    XNotFoundError,
    XProvider,
    XRateLimitError,
)
from services.social.types import XTweet, XUser

logger = structlog.get_logger()


class MockXProvider(XProvider):
    """
    Mock X provider for testing.

    Features:
    - In-memory tweet and user storage
    - Configurable delays to simulate network latency
    - Configurable failure simulation
    - Fixture data for common test scenarios
    """

    def __init__(
        self,
        simulate_delay: float = 0.0,
        fail_rate: float = 0.0,
        rate_limit_after: Optional[int] = None,
    ):
        """
        Initialize mock provider.

        Args:
            simulate_delay: Seconds to delay each call (simulates network)
            fail_rate: Probability (0.0-1.0) of random failure
            rate_limit_after: Trigger rate limit error after N calls
        """
        self.simulate_delay = simulate_delay
        self.fail_rate = fail_rate
        self.rate_limit_after = rate_limit_after
        self._call_count = 0
        self._tweet_counter = 0  # Monotonic counter for sortable tweet IDs

        # In-memory stores
        self._tweets: dict[str, XTweet] = {}
        self._users: dict[str, XUser] = {}
        self._mentions: list[str] = []  # Tweet IDs that mention the bot
        self._bot_user_id = "bot_user_123"
        self._bot_username = "jeffrey_aistein"

        # Load default fixtures
        self._load_fixtures()

    def _load_fixtures(self):
        """Load default test fixtures."""
        # Create bot user
        bot_user = XUser(
            id=self._bot_user_id,
            username=self._bot_username,
            name="Jeffrey AIstein",
            created_at=datetime.now(timezone.utc) - timedelta(days=365),
            followers_count=10000,
            following_count=500,
            tweet_count=5000,
            verified=True,
            description="AGI-style investigator bot. Hyper-sarcastic truth seeker.",
            location="The Matrix",
            default_profile_image=False,
        )
        self._users[bot_user.id] = bot_user
        self._users[bot_user.username.lower()] = bot_user

        # Create some fixture users
        self._create_fixture_user(
            user_id="user_alice_123",
            username="alice_crypto",
            name="Alice",
            days_old=400,
            followers=1200,
            following=500,
            tweets=3000,
            verified=False,
        )

        self._create_fixture_user(
            user_id="user_bob_456",
            username="bob_trader",
            name="Bob",
            days_old=200,
            followers=500,
            following=300,
            tweets=1500,
            verified=False,
        )

        self._create_fixture_user(
            user_id="user_spam_789",
            username="totally_not_spam",
            name="FREE CRYPTO",
            days_old=7,
            followers=5,
            following=5000,
            tweets=50,
            verified=False,
            has_bio=False,
            default_image=True,
        )

    def _create_fixture_user(
        self,
        user_id: str,
        username: str,
        name: str,
        days_old: int,
        followers: int,
        following: int,
        tweets: int,
        verified: bool = False,
        has_bio: bool = True,
        has_location: bool = True,
        default_image: bool = False,
    ) -> XUser:
        """Create and store a fixture user."""
        user = XUser(
            id=user_id,
            username=username,
            name=name,
            created_at=datetime.now(timezone.utc) - timedelta(days=days_old),
            followers_count=followers,
            following_count=following,
            tweet_count=tweets,
            verified=verified,
            description=f"Test user {username} bio with enough characters" if has_bio else None,
            location="Test City" if has_location else None,
            default_profile_image=default_image,
        )
        self._users[user_id] = user
        self._users[username.lower()] = user
        return user

    async def _maybe_delay(self):
        """Apply simulated delay if configured."""
        if self.simulate_delay > 0:
            await asyncio.sleep(self.simulate_delay)

    def _check_rate_limit(self):
        """Check if we should simulate a rate limit error."""
        self._call_count += 1
        if self.rate_limit_after and self._call_count > self.rate_limit_after:
            raise XRateLimitError(
                "Rate limit exceeded (mock)",
                retry_after_seconds=60,
            )

    def add_tweet(self, tweet: XTweet) -> XTweet:
        """
        Add a tweet to the mock store.

        Args:
            tweet: XTweet to add

        Returns:
            The added tweet
        """
        self._tweets[tweet.id] = tweet
        return tweet

    def add_mention(self, tweet: XTweet) -> XTweet:
        """
        Add a tweet as a mention of the bot.

        Args:
            tweet: XTweet mentioning the bot

        Returns:
            The added tweet
        """
        self._tweets[tweet.id] = tweet
        self._mentions.append(tweet.id)
        return tweet

    def create_mention(
        self,
        author_id: str,
        text: str,
        reply_to_id: Optional[str] = None,
    ) -> XTweet:
        """
        Create and add a mention tweet.

        Args:
            author_id: User ID of the author
            text: Tweet text (should include @jeffrey_aistein)
            reply_to_id: Optional tweet ID this is replying to

        Returns:
            The created XTweet
        """
        author = self._users.get(author_id)
        if not author:
            raise ValueError(f"Unknown author_id: {author_id}")

        self._tweet_counter += 1
        tweet_id = f"tweet_{self._tweet_counter:012d}"
        tweet = XTweet(
            id=tweet_id,
            text=text,
            author_id=author_id,
            author=author,
            created_at=datetime.now(timezone.utc),
            conversation_id=reply_to_id or tweet_id,
            reply_to_tweet_id=reply_to_id,
            reply_to_user_id=self._bot_user_id if reply_to_id else None,
        )
        return self.add_mention(tweet)

    def clear(self):
        """Clear all mock data (keeps fixtures)."""
        self._tweets.clear()
        self._mentions.clear()
        self._call_count = 0
        self._tweet_counter = 0
        self._load_fixtures()

    async def fetch_mentions(
        self,
        since_id: Optional[str] = None,
        max_results: int = 100,
    ) -> list[XTweet]:
        """Fetch mentions from mock store."""
        await self._maybe_delay()
        self._check_rate_limit()

        logger.debug(
            "mock_fetch_mentions",
            since_id=since_id,
            max_results=max_results,
            total_mentions=len(self._mentions),
        )

        mentions = []
        for tweet_id in self._mentions:
            tweet = self._tweets.get(tweet_id)
            if not tweet:
                continue

            # Filter by since_id (assuming IDs are sortable)
            if since_id and tweet.id <= since_id:
                continue

            mentions.append(tweet)

        # Sort by created_at descending (newest first)
        mentions.sort(key=lambda t: t.created_at, reverse=True)

        return mentions[:max_results]

    async def fetch_thread_context(
        self,
        tweet_id: str,
        max_depth: int = 10,
    ) -> list[XTweet]:
        """Fetch thread context by following reply chain."""
        await self._maybe_delay()
        self._check_rate_limit()

        tweet = self._tweets.get(tweet_id)
        if not tweet:
            raise XNotFoundError(f"Tweet {tweet_id} not found")

        thread = [tweet]
        current = tweet
        depth = 0

        # Walk up the reply chain
        while current.reply_to_tweet_id and depth < max_depth:
            parent = self._tweets.get(current.reply_to_tweet_id)
            if not parent:
                break
            thread.insert(0, parent)
            current = parent
            depth += 1

        logger.debug(
            "mock_fetch_thread_context",
            tweet_id=tweet_id,
            thread_length=len(thread),
        )

        return thread

    async def post_tweet(
        self,
        text: str,
        reply_to: Optional[str] = None,
    ) -> XTweet:
        """Post a tweet to mock store."""
        await self._maybe_delay()
        self._check_rate_limit()

        if len(text) > 280:
            raise ValueError(f"Tweet exceeds 280 characters (got {len(text)})")

        self._tweet_counter += 1
        tweet_id = f"tweet_{self._tweet_counter:012d}"
        bot_user = self._users.get(self._bot_user_id)

        # Determine conversation_id
        if reply_to:
            parent = self._tweets.get(reply_to)
            if parent:
                conversation_id = parent.conversation_id
                reply_to_user_id = parent.author_id
            else:
                conversation_id = reply_to
                reply_to_user_id = None
        else:
            conversation_id = tweet_id
            reply_to_user_id = None

        tweet = XTweet(
            id=tweet_id,
            text=text,
            author_id=self._bot_user_id,
            author=bot_user,
            created_at=datetime.now(timezone.utc),
            conversation_id=conversation_id,
            reply_to_tweet_id=reply_to,
            reply_to_user_id=reply_to_user_id,
        )

        self._tweets[tweet_id] = tweet

        logger.info(
            "mock_post_tweet",
            tweet_id=tweet_id,
            reply_to=reply_to,
            text_length=len(text),
        )

        return tweet

    async def get_user(self, user_id: str) -> XUser:
        """Get user by ID from mock store."""
        await self._maybe_delay()
        self._check_rate_limit()

        user = self._users.get(user_id)
        if not user:
            raise XNotFoundError(f"User {user_id} not found")

        return user

    async def get_user_by_username(self, username: str) -> XUser:
        """Get user by username from mock store."""
        await self._maybe_delay()
        self._check_rate_limit()

        user = self._users.get(username.lower())
        if not user:
            raise XNotFoundError(f"User @{username} not found")

        return user

    async def get_tweet(self, tweet_id: str) -> XTweet:
        """Get tweet by ID from mock store."""
        await self._maybe_delay()
        self._check_rate_limit()

        tweet = self._tweets.get(tweet_id)
        if not tweet:
            raise XNotFoundError(f"Tweet {tweet_id} not found")

        return tweet

    async def delete_tweet(self, tweet_id: str) -> bool:
        """Delete tweet from mock store."""
        await self._maybe_delay()
        self._check_rate_limit()

        if tweet_id not in self._tweets:
            raise XNotFoundError(f"Tweet {tweet_id} not found")

        tweet = self._tweets[tweet_id]
        if tweet.author_id != self._bot_user_id:
            raise XAuthError("Cannot delete tweet from another user")

        del self._tweets[tweet_id]
        if tweet_id in self._mentions:
            self._mentions.remove(tweet_id)

        logger.info("mock_delete_tweet", tweet_id=tweet_id)

        return True

    async def health_check(self) -> bool:
        """Mock health check always returns True."""
        await self._maybe_delay()
        self._check_rate_limit()
        return True
