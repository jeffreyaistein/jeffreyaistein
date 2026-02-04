"""
Jeffrey AIstein - Mention Ingestion Loop

Polls X for new mentions, stores them, and generates draft replies.
"""

import asyncio
import os
import signal
import uuid
from datetime import datetime
from typing import Optional

import structlog

from services.social.providers import XProvider, XProviderError, XRateLimitError
from services.social.scheduler.clock import Clock, SystemClock
from services.social.scorer import compute_quality_score, get_quality_threshold
from services.social.storage import (
    DraftEntry,
    DraftStatus,
    InboxEntry,
    InboxRepository,
    PostType,
    ReplyLogRepository,
    SettingsRepository,
    SETTING_LAST_MENTION_ID,
    SETTING_LAST_REPLY_ID,
    SETTING_SAFE_MODE,
    SETTING_APPROVAL_REQUIRED,
    get_draft_repository,
    get_inbox_repository,
    get_reply_log_repository,
    get_settings_repository,
    get_runtime_setting,
)
from services.social.content import get_content_generator

logger = structlog.get_logger()


def get_poll_interval() -> int:
    """Get polling interval from environment."""
    return int(os.getenv("X_POLL_INTERVAL_SECONDS", "45"))


class IngestionLoop:
    """
    Mention ingestion loop.

    Polls X for new mentions at a configurable interval,
    filters by quality score, and stores for processing.
    """

    def __init__(
        self,
        x_provider: XProvider,
        clock: Optional[Clock] = None,
        inbox_repo: Optional[InboxRepository] = None,
        reply_log_repo: Optional[ReplyLogRepository] = None,
        settings_repo: Optional[SettingsRepository] = None,
        poll_interval: Optional[int] = None,
    ):
        """
        Initialize ingestion loop.

        Args:
            x_provider: X API provider
            clock: Clock implementation (defaults to SystemClock)
            inbox_repo: Inbox repository (defaults to singleton)
            reply_log_repo: Reply log repository (defaults to singleton)
            settings_repo: Settings repository (defaults to singleton)
            poll_interval: Override poll interval (defaults to env)
        """
        self.x_provider = x_provider
        self.clock = clock or SystemClock()
        self.inbox_repo = inbox_repo or get_inbox_repository()
        self.reply_log_repo = reply_log_repo or get_reply_log_repository()
        self.settings_repo = settings_repo or get_settings_repository()
        self.poll_interval = poll_interval or get_poll_interval()

        self._running = False
        self._shutdown_event = asyncio.Event()

        # Stats
        self.total_fetched = 0
        self.total_stored = 0
        self.total_filtered = 0
        self.total_duplicates = 0

    def _setup_signal_handlers(self):
        """Setup graceful shutdown on SIGTERM/SIGINT."""
        loop = asyncio.get_event_loop()

        def shutdown_handler():
            logger.info("ingestion_shutdown_requested")
            self._shutdown_event.set()

        try:
            loop.add_signal_handler(signal.SIGTERM, shutdown_handler)
            loop.add_signal_handler(signal.SIGINT, shutdown_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    async def start(self) -> None:
        """Start the ingestion loop."""
        if self._running:
            logger.warning("ingestion_already_running")
            return

        self._running = True
        self._shutdown_event.clear()
        self._setup_signal_handlers()

        logger.info(
            "ingestion_started",
            poll_interval=self.poll_interval,
            quality_threshold=get_quality_threshold(),
        )

        while self._running and not self._shutdown_event.is_set():
            try:
                await self._poll_once()
            except XRateLimitError as e:
                wait_time = e.retry_after_seconds or 60
                logger.warning(
                    "ingestion_rate_limited",
                    wait_seconds=wait_time,
                )
                await self.clock.sleep(wait_time)
                continue
            except XProviderError as e:
                logger.error("ingestion_provider_error", error=str(e))
                # Wait before retry
                await self.clock.sleep(30)
                continue
            except Exception as e:
                logger.exception("ingestion_unexpected_error", error=str(e))
                await self.clock.sleep(30)
                continue

            # Wait for next poll
            await self.clock.sleep(self.poll_interval)

        logger.info("ingestion_stopped")

    async def stop(self) -> None:
        """Stop the ingestion loop gracefully."""
        logger.info("ingestion_stop_requested")
        self._running = False
        self._shutdown_event.set()

    async def poll_once(self) -> dict:
        """
        Execute a single poll iteration.

        Returns:
            Stats dict with fetched, stored, filtered, duplicate counts
        """
        return await self._poll_once()

    async def _poll_once(self) -> dict:
        """Internal poll implementation."""
        # Poll both mentions AND replies (replies don't require @mention)
        mention_stats = await self._poll_mentions()
        reply_stats = await self._poll_replies()

        # Combine stats
        stats = {
            "fetched": mention_stats["fetched"] + reply_stats["fetched"],
            "stored": mention_stats["stored"] + reply_stats["stored"],
            "filtered": mention_stats["filtered"] + reply_stats["filtered"],
            "duplicates": mention_stats["duplicates"] + reply_stats["duplicates"],
        }

        if stats["fetched"] == 0:
            logger.debug("ingestion_no_new_interactions")

        return stats

    async def _poll_mentions(self) -> dict:
        """Poll for new @mentions."""
        last_mention_id = await self.settings_repo.get(SETTING_LAST_MENTION_ID)

        logger.debug(
            "ingestion_polling_mentions",
            since_id=last_mention_id,
        )

        mentions = await self.x_provider.fetch_mentions(
            since_id=last_mention_id,
            max_results=100,
        )

        stats = await self._process_tweets(mentions, "mention", SETTING_LAST_MENTION_ID)

        if not mentions:
            logger.debug("ingestion_no_new_mentions")

        return stats

    async def _poll_replies(self) -> dict:
        """Poll for replies to bot's tweets (without @mention)."""
        last_reply_id = await self.settings_repo.get(SETTING_LAST_REPLY_ID)

        logger.debug(
            "ingestion_polling_replies",
            since_id=last_reply_id,
        )

        try:
            replies = await self.x_provider.fetch_replies(
                since_id=last_reply_id,
                max_results=100,
            )
        except Exception as e:
            # Search API might not be available on all tiers
            logger.warning(
                "ingestion_replies_fetch_failed",
                error=str(e),
            )
            return {"fetched": 0, "stored": 0, "filtered": 0, "duplicates": 0}

        stats = await self._process_tweets(replies, "reply", SETTING_LAST_REPLY_ID)

        if not replies:
            logger.debug("ingestion_no_new_replies")

        return stats

    async def _process_tweets(
        self,
        tweets: list,
        source: str,
        last_id_setting: str,
    ) -> dict:
        """Process a list of tweets (mentions or replies)."""
        stats = {
            "fetched": len(tweets),
            "stored": 0,
            "filtered": 0,
            "duplicates": 0,
        }

        if not tweets:
            return stats

        self.total_fetched += len(tweets)
        quality_threshold = get_quality_threshold()
        newest_id = None

        for tweet in tweets:
            # Track newest for pagination
            if newest_id is None or tweet.id > newest_id:
                newest_id = tweet.id

            # Check if already in inbox (dedup)
            if await self.inbox_repo.exists(tweet.id):
                stats["duplicates"] += 1
                self.total_duplicates += 1
                continue

            # Check if already replied (idempotency)
            if await self.reply_log_repo.has_replied(tweet.id):
                stats["duplicates"] += 1
                self.total_duplicates += 1
                continue

            # Get author for quality scoring
            author = tweet.author
            if not author:
                try:
                    author = await self.x_provider.get_user(tweet.author_id)
                except XProviderError:
                    logger.warning(
                        f"ingestion_{source}_author_fetch_failed",
                        tweet_id=tweet.id,
                        author_id=tweet.author_id,
                    )
                    continue

            # Compute quality score
            quality_result = compute_quality_score(author)

            # Filter low-quality accounts
            if not quality_result.passed:
                logger.info(
                    f"ingestion_{source}_filtered_low_quality",
                    tweet_id=tweet.id,
                    author=author.username,
                    score=quality_result.score,
                    threshold=quality_threshold,
                )
                stats["filtered"] += 1
                self.total_filtered += 1
                continue

            # Store in inbox
            entry = InboxEntry(
                id=tweet.id,
                tweet=tweet,
                author_id=tweet.author_id,
                quality_score=quality_result.score,
                received_at=self.clock.now(),
            )
            await self.inbox_repo.save(entry)

            logger.info(
                f"ingestion_{source}_stored",
                tweet_id=tweet.id,
                author=author.username,
                quality_score=quality_result.score,
            )
            stats["stored"] += 1
            self.total_stored += 1

            # Generate draft reply immediately
            try:
                await self._generate_draft_reply(tweet, author)
            except Exception as e:
                logger.exception(
                    "ingestion_draft_generation_failed",
                    tweet_id=tweet.id,
                    error=str(e),
                )

        # Update last ID for pagination
        if newest_id:
            await self.settings_repo.set(last_id_setting, newest_id)

        logger.info(
            f"ingestion_{source}_poll_complete",
            **stats,
        )

        return stats

    def get_stats(self) -> dict:
        """Get cumulative stats."""
        return {
            "total_fetched": self.total_fetched,
            "total_stored": self.total_stored,
            "total_filtered": self.total_filtered,
            "total_duplicates": self.total_duplicates,
            "running": self._running,
        }

    async def _generate_draft_reply(self, mention, author) -> None:
        """
        Generate a draft reply for a mention.

        Args:
            mention: The XTweet mention
            author: The XUser author
        """
        # Check if SAFE_MODE or APPROVAL_REQUIRED (database settings override env vars)
        safe_mode = await get_runtime_setting(SETTING_SAFE_MODE, "SAFE_MODE", "false")
        approval_required = await get_runtime_setting(SETTING_APPROVAL_REQUIRED, "APPROVAL_REQUIRED", "true")

        if safe_mode and not approval_required:
            # Safe mode without approval - just skip
            logger.info(
                "ingestion_safe_mode_skip",
                tweet_id=mention.id,
            )
            return

        # Generate reply using content generator
        content_gen = get_content_generator()

        logger.info(
            "ingestion_generating_reply",
            tweet_id=mention.id,
            author=author.username,
        )

        reply_text = await content_gen.generate_reply(
            mention_text=mention.text,
            author_username=author.username,
            thread_context=None,  # Could enhance with thread context later
        )

        # Create draft
        draft_repo = get_draft_repository()
        draft = DraftEntry(
            id=str(uuid.uuid4()),
            text=reply_text,
            post_type=PostType.REPLY,
            reply_to_id=mention.id,
            status=DraftStatus.PENDING,
            created_at=datetime.utcnow(),
        )
        await draft_repo.save(draft)

        logger.info(
            "ingestion_draft_created",
            draft_id=draft.id,
            tweet_id=mention.id,
            reply_length=len(reply_text),
        )
