"""
Jeffrey AIstein - Conversation Context Builder

Builds conversation context for X replies by reconstructing threads
and enforcing conversation caps.
"""

import os
import re
from datetime import datetime, timezone
from typing import Optional

import structlog

from services.social.providers import XProvider, XProviderError
from services.social.storage import (
    ThreadRepository,
    ThreadState,
    UserLimitRepository,
    get_thread_repository,
    get_user_limit_repository,
    get_runtime_setting,
    SETTING_SAFE_MODE,
)
from services.social.types import MentionFilterReason, ThreadContext, XTweet

logger = structlog.get_logger()


def get_max_replies_per_thread() -> int:
    """Get max replies per thread from environment."""
    return int(os.getenv("X_MAX_REPLIES_PER_THREAD", "5"))


def get_max_replies_per_user_per_day() -> int:
    """Get max replies per user per day from environment."""
    return int(os.getenv("X_MAX_REPLIES_PER_USER_PER_DAY", "10"))


async def is_safe_mode() -> bool:
    """Check if safe mode is enabled (DB overrides env)."""
    return await get_runtime_setting(SETTING_SAFE_MODE, "SAFE_MODE", "false")


# Keywords that indicate user wants us to stop
STOP_KEYWORDS = [
    "stop",
    "leave me alone",
    "go away",
    "shut up",
    "block",
    "blocked",
    "mute",
    "muted",
    "unfollow",
    "unfollowed",
    "don't reply",
    "dont reply",
    "stop replying",
    "no more replies",
    "enough",
]


class StopCondition:
    """Result of stop condition check."""

    def __init__(
        self,
        should_stop: bool,
        reason: Optional[MentionFilterReason] = None,
        message: Optional[str] = None,
    ):
        self.should_stop = should_stop
        self.reason = reason
        self.message = message


class ConversationContextBuilder:
    """
    Builds conversation context for X replies.

    Features:
    - Thread reconstruction (following reply chains)
    - Conversation caps enforcement
    - Stop condition detection
    - Per-user daily limit tracking
    """

    def __init__(
        self,
        x_provider: XProvider,
        thread_repo: Optional[ThreadRepository] = None,
        user_limit_repo: Optional[UserLimitRepository] = None,
    ):
        """
        Initialize context builder.

        Args:
            x_provider: X API provider
            thread_repo: Thread state repository (defaults to singleton)
            user_limit_repo: User limit repository (defaults to singleton)
        """
        self.x_provider = x_provider
        self.thread_repo = thread_repo or get_thread_repository()
        self.user_limit_repo = user_limit_repo or get_user_limit_repository()

    async def build_context(
        self,
        tweet: XTweet,
        max_thread_depth: int = 10,
    ) -> ThreadContext:
        """
        Build conversation context for a tweet.

        Args:
            tweet: The tweet to build context for
            max_thread_depth: Maximum depth of thread to fetch

        Returns:
            ThreadContext with conversation history
        """
        # Get thread context from X API
        thread_tweets = await self.x_provider.fetch_thread_context(
            tweet.id,
            max_depth=max_thread_depth,
        )

        # Get author info
        author = tweet.author
        if not author and tweet.author_id:
            try:
                author = await self.x_provider.get_user(tweet.author_id)
            except XProviderError:
                pass

        # Determine conversation_id
        conversation_id = tweet.conversation_id or tweet.id

        # Get thread state
        thread_state = await self.thread_repo.get(conversation_id)
        our_reply_count = thread_state.our_reply_count if thread_state else 0

        # Find last activity time
        last_activity = tweet.created_at
        if thread_tweets:
            for t in thread_tweets:
                if t.created_at and (not last_activity or t.created_at > last_activity):
                    last_activity = t.created_at

        # Check if thread is stopped
        stopped = thread_state.stopped if thread_state else False
        stop_reason = thread_state.stop_reason if thread_state else None

        return ThreadContext(
            conversation_id=conversation_id,
            author_id=tweet.author_id,
            author_username=author.username if author else "unknown",
            tweets=thread_tweets,
            our_reply_count=our_reply_count,
            last_activity_at=last_activity,
            stopped=stopped,
            stop_reason=stop_reason,
        )

    async def check_stop_conditions(
        self,
        tweet: XTweet,
        context: Optional[ThreadContext] = None,
    ) -> StopCondition:
        """
        Check all stop conditions for a mention.

        Args:
            tweet: The tweet to check
            context: Optional pre-built context

        Returns:
            StopCondition with should_stop flag and reason
        """
        # Check safe mode
        if await is_safe_mode():
            return StopCondition(
                should_stop=True,
                reason=MentionFilterReason.SAFE_MODE,
                message="Safe mode is enabled",
            )

        # Get or build context
        if context is None:
            context = await self.build_context(tweet)

        # Check if thread is already stopped
        if context.stopped:
            return StopCondition(
                should_stop=True,
                reason=MentionFilterReason.USER_REQUESTED_STOP,
                message=f"Thread stopped: {context.stop_reason}",
            )

        # Check per-thread cap
        max_per_thread = get_max_replies_per_thread()
        if context.our_reply_count >= max_per_thread:
            return StopCondition(
                should_stop=True,
                reason=MentionFilterReason.PER_THREAD_CAP,
                message=f"Thread cap reached ({context.our_reply_count}/{max_per_thread})",
            )

        # Check per-user daily cap
        max_per_user = get_max_replies_per_user_per_day()
        user_today_count = await self.user_limit_repo.get_today_count(tweet.author_id)
        if user_today_count >= max_per_user:
            return StopCondition(
                should_stop=True,
                reason=MentionFilterReason.PER_USER_CAP,
                message=f"User daily cap reached ({user_today_count}/{max_per_user})",
            )

        # Check for stop keywords in tweet text
        if self._contains_stop_keyword(tweet.text):
            # Mark thread as stopped
            await self.thread_repo.stop_thread(
                context.conversation_id,
                "user_requested_stop",
            )
            return StopCondition(
                should_stop=True,
                reason=MentionFilterReason.USER_REQUESTED_STOP,
                message="User requested to stop",
            )

        return StopCondition(should_stop=False)

    def _contains_stop_keyword(self, text: str) -> bool:
        """Check if text contains stop keywords."""
        text_lower = text.lower()
        for keyword in STOP_KEYWORDS:
            # Use word boundary matching for short keywords
            if len(keyword) <= 5:
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, text_lower):
                    return True
            else:
                # For longer phrases, substring match is fine
                if keyword in text_lower:
                    return True
        return False

    async def record_reply(
        self,
        tweet: XTweet,
        context: Optional[ThreadContext] = None,
    ) -> None:
        """
        Record that we replied to a tweet.

        Updates thread reply count and user daily count.

        Args:
            tweet: The tweet we replied to
            context: Optional pre-built context
        """
        # Get conversation_id
        conversation_id = tweet.conversation_id or tweet.id

        # Increment thread reply count
        new_count = await self.thread_repo.increment_reply_count(conversation_id)
        logger.info(
            "thread_reply_recorded",
            conversation_id=conversation_id,
            new_count=new_count,
        )

        # Increment user daily count
        user_count = await self.user_limit_repo.increment(tweet.author_id)
        logger.info(
            "user_daily_count_incremented",
            user_id=tweet.author_id,
            new_count=user_count,
        )

    async def get_our_bot_replies_in_thread(
        self,
        context: ThreadContext,
        bot_user_id: str,
    ) -> list[XTweet]:
        """
        Find our bot's replies in a thread context.

        Args:
            context: Thread context
            bot_user_id: Our bot's user ID

        Returns:
            List of our bot's tweets in the thread
        """
        return [t for t in context.tweets if t.author_id == bot_user_id]
