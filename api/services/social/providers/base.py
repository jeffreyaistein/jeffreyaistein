"""
Jeffrey AIstein - X Provider Base Interface

Abstract interface for X (Twitter) API operations.
Enables dependency injection for testing with MockXProvider.
"""

from abc import ABC, abstractmethod
from typing import Optional

import structlog

from services.social.types import XTweet, XUser

logger = structlog.get_logger()


class XProviderError(Exception):
    """Base exception for X provider errors."""
    pass


class XRateLimitError(XProviderError):
    """Raised when X API rate limit is exceeded."""

    def __init__(self, message: str, retry_after_seconds: Optional[int] = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class XAuthError(XProviderError):
    """Raised when X API authentication fails."""
    pass


class XNotFoundError(XProviderError):
    """Raised when requested resource is not found."""
    pass


class XProvider(ABC):
    """
    Abstract base class for X (Twitter) API providers.

    Implementations:
    - MockXProvider: For testing with in-memory data
    - RealXProvider: Production Twitter API v2 integration
    """

    @abstractmethod
    async def fetch_mentions(
        self,
        since_id: Optional[str] = None,
        max_results: int = 100,
    ) -> list[XTweet]:
        """
        Fetch mentions of the authenticated user.

        Args:
            since_id: Only return tweets newer than this ID
            max_results: Maximum number of tweets to return (default 100)

        Returns:
            List of XTweet objects mentioning the bot, newest first

        Raises:
            XRateLimitError: If rate limit exceeded
            XAuthError: If authentication fails
        """
        pass

    @abstractmethod
    async def fetch_thread_context(
        self,
        tweet_id: str,
        max_depth: int = 10,
    ) -> list[XTweet]:
        """
        Fetch conversation thread context for a tweet.

        Reconstructs the thread by following reply chains up to max_depth.
        Returns tweets in chronological order (oldest first).

        Args:
            tweet_id: The tweet ID to get context for
            max_depth: Maximum number of parent tweets to fetch

        Returns:
            List of XTweet objects forming the thread, oldest first

        Raises:
            XNotFoundError: If tweet not found
            XRateLimitError: If rate limit exceeded
        """
        pass

    @abstractmethod
    async def post_tweet(
        self,
        text: str,
        reply_to: Optional[str] = None,
    ) -> XTweet:
        """
        Post a new tweet.

        Args:
            text: Tweet text (max 280 characters)
            reply_to: Optional tweet ID to reply to

        Returns:
            The posted XTweet

        Raises:
            XRateLimitError: If rate limit exceeded
            XAuthError: If authentication fails
            ValueError: If text exceeds 280 characters
        """
        pass

    @abstractmethod
    async def get_user(self, user_id: str) -> XUser:
        """
        Fetch user profile by ID.

        Args:
            user_id: The X user ID

        Returns:
            XUser object with profile data

        Raises:
            XNotFoundError: If user not found
            XRateLimitError: If rate limit exceeded
        """
        pass

    @abstractmethod
    async def get_user_by_username(self, username: str) -> XUser:
        """
        Fetch user profile by username.

        Args:
            username: The X username (without @)

        Returns:
            XUser object with profile data

        Raises:
            XNotFoundError: If user not found
            XRateLimitError: If rate limit exceeded
        """
        pass

    @abstractmethod
    async def get_tweet(self, tweet_id: str) -> XTweet:
        """
        Fetch a single tweet by ID.

        Args:
            tweet_id: The tweet ID

        Returns:
            XTweet object

        Raises:
            XNotFoundError: If tweet not found
            XRateLimitError: If rate limit exceeded
        """
        pass

    @abstractmethod
    async def delete_tweet(self, tweet_id: str) -> bool:
        """
        Delete a tweet.

        Args:
            tweet_id: The tweet ID to delete

        Returns:
            True if deleted successfully

        Raises:
            XNotFoundError: If tweet not found
            XAuthError: If not authorized to delete
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the provider is healthy and can make API calls.

        Returns:
            True if healthy, False otherwise
        """
        pass
