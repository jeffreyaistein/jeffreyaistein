"""
Jeffrey AIstein - Timeline Posting Scheduler

Posts original content to the timeline on a schedule with jitter.
"""

import asyncio
import os
import random
import signal
from typing import Optional

import structlog

from services.social.content import ContentGenerator, get_content_generator
from services.social.providers import XProvider, XProviderError, XRateLimitError
from services.social.scheduler.clock import Clock, SystemClock
from services.social.storage import (
    DraftEntry,
    DraftRepository,
    DraftStatus,
    PostEntry,
    PostRepository,
    SettingsRepository,
    SETTING_LAST_TIMELINE_POST,
    SETTING_NEXT_TIMELINE_POST,
    SETTING_SAFE_MODE,
    SETTING_APPROVAL_REQUIRED,
    get_draft_repository,
    get_post_repository,
    get_settings_repository,
    get_runtime_setting,
)
from services.social.types import PostStatus, PostType

logger = structlog.get_logger()


def get_timeline_interval() -> int:
    """Get timeline posting interval from environment (seconds)."""
    return int(os.getenv("X_TIMELINE_POST_INTERVAL_SECONDS", "10800"))  # 3h default


def get_timeline_jitter() -> int:
    """Get timeline posting jitter from environment (seconds)."""
    return int(os.getenv("X_TIMELINE_POST_JITTER_SECONDS", "600"))  # 10min default


def get_hourly_limit() -> int:
    """Get hourly posting limit."""
    return int(os.getenv("X_HOURLY_POST_LIMIT", "5"))


def get_daily_limit() -> int:
    """Get daily posting limit."""
    return int(os.getenv("X_DAILY_POST_LIMIT", "20"))


async def is_safe_mode() -> bool:
    """Check if safe mode is enabled (DB overrides env)."""
    return await get_runtime_setting(SETTING_SAFE_MODE, "SAFE_MODE", "false")


async def is_approval_required() -> bool:
    """Check if approval is required for posts (DB overrides env)."""
    return await get_runtime_setting(SETTING_APPROVAL_REQUIRED, "APPROVAL_REQUIRED", "true")


class TimelinePosterLoop:
    """
    Timeline posting scheduler.

    Posts original content at configured intervals with jitter.
    Respects SAFE_MODE and APPROVAL_REQUIRED settings.
    """

    def __init__(
        self,
        x_provider: XProvider,
        clock: Optional[Clock] = None,
        post_repo: Optional[PostRepository] = None,
        draft_repo: Optional[DraftRepository] = None,
        settings_repo: Optional[SettingsRepository] = None,
        content_generator: Optional[ContentGenerator] = None,
        interval: Optional[int] = None,
        jitter: Optional[int] = None,
    ):
        """
        Initialize timeline poster.

        Args:
            x_provider: X API provider
            clock: Clock implementation (defaults to SystemClock)
            post_repo: Post repository (defaults to singleton)
            draft_repo: Draft repository (defaults to singleton)
            settings_repo: Settings repository (defaults to singleton)
            content_generator: Content generator (defaults to singleton)
            interval: Override posting interval (defaults to env)
            jitter: Override jitter (defaults to env)
        """
        self.x_provider = x_provider
        self.clock = clock or SystemClock()
        self.post_repo = post_repo or get_post_repository()
        self.draft_repo = draft_repo or get_draft_repository()
        self.settings_repo = settings_repo or get_settings_repository()
        self.content_generator = content_generator or get_content_generator()
        self.interval = interval or get_timeline_interval()
        self.jitter = jitter or get_timeline_jitter()

        self._running = False
        self._shutdown_event = asyncio.Event()
        self._random = random.Random()  # Seeded instance for testing

        # Stats
        self.total_posts = 0
        self.total_drafts = 0
        self.total_skipped_safe_mode = 0
        self.total_skipped_limit = 0

    def seed_random(self, seed: int) -> None:
        """Seed the random generator for deterministic testing."""
        self._random.seed(seed)

    def _calculate_next_post_time(self) -> float:
        """Calculate next post time with jitter."""
        jitter_offset = self._random.uniform(-self.jitter, self.jitter)
        return self.clock.timestamp() + self.interval + jitter_offset

    def _setup_signal_handlers(self):
        """Setup graceful shutdown on SIGTERM/SIGINT."""
        loop = asyncio.get_event_loop()

        def shutdown_handler():
            logger.info("timeline_poster_shutdown_requested")
            self._shutdown_event.set()

        try:
            loop.add_signal_handler(signal.SIGTERM, shutdown_handler)
            loop.add_signal_handler(signal.SIGINT, shutdown_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    async def start(self) -> None:
        """Start the timeline posting loop."""
        if self._running:
            logger.warning("timeline_poster_already_running")
            return

        self._running = True
        self._shutdown_event.clear()
        self._setup_signal_handlers()

        logger.info(
            "timeline_poster_started",
            interval=self.interval,
            jitter=self.jitter,
            safe_mode=await is_safe_mode(),
            approval_required=await is_approval_required(),
        )

        # Calculate initial next post time
        next_post_timestamp = self._calculate_next_post_time()
        await self.settings_repo.set(
            SETTING_NEXT_TIMELINE_POST,
            str(next_post_timestamp),
        )

        while self._running and not self._shutdown_event.is_set():
            # Get scheduled time
            next_post_str = await self.settings_repo.get(SETTING_NEXT_TIMELINE_POST)
            if next_post_str:
                next_post_timestamp = float(next_post_str)
            else:
                next_post_timestamp = self._calculate_next_post_time()
                await self.settings_repo.set(
                    SETTING_NEXT_TIMELINE_POST,
                    str(next_post_timestamp),
                )

            # Wait until it's time to post
            wait_time = next_post_timestamp - self.clock.timestamp()
            if wait_time > 0:
                logger.debug(
                    "timeline_poster_waiting",
                    wait_seconds=wait_time,
                )
                await self.clock.sleep(min(wait_time, 60))  # Wake periodically to check shutdown
                continue

            # Time to post!
            try:
                await self._post_once()
            except XRateLimitError as e:
                wait_time = e.retry_after_seconds or 60
                logger.warning(
                    "timeline_poster_rate_limited",
                    wait_seconds=wait_time,
                )
                await self.clock.sleep(wait_time)
                continue
            except XProviderError as e:
                logger.error("timeline_poster_provider_error", error=str(e))
                await self.clock.sleep(30)
                continue
            except Exception as e:
                logger.exception("timeline_poster_unexpected_error", error=str(e))
                await self.clock.sleep(30)
                continue

            # Schedule next post
            next_post_timestamp = self._calculate_next_post_time()
            await self.settings_repo.set(
                SETTING_NEXT_TIMELINE_POST,
                str(next_post_timestamp),
            )

        logger.info("timeline_poster_stopped")

    async def stop(self) -> None:
        """Stop the timeline posting loop gracefully."""
        logger.info("timeline_poster_stop_requested")
        self._running = False
        self._shutdown_event.set()

    async def post_once(self) -> dict:
        """
        Execute a single post attempt.

        Returns:
            Result dict with status and details
        """
        return await self._post_once()

    async def _post_once(self) -> dict:
        """Internal post implementation."""
        result = {
            "posted": False,
            "drafted": False,
            "skipped": False,
            "reason": None,
            "tweet_id": None,
            "draft_id": None,
        }

        # Check safe mode
        if await is_safe_mode():
            logger.info("timeline_poster_safe_mode_skip")
            result["skipped"] = True
            result["reason"] = "safe_mode"
            self.total_skipped_safe_mode += 1
            return result

        # Check limits
        hourly_count = await self.post_repo.count_last_hour()
        daily_count = await self.post_repo.count_today()

        if hourly_count >= get_hourly_limit():
            logger.info(
                "timeline_poster_hourly_limit_reached",
                count=hourly_count,
                limit=get_hourly_limit(),
            )
            result["skipped"] = True
            result["reason"] = "hourly_limit"
            self.total_skipped_limit += 1
            return result

        if daily_count >= get_daily_limit():
            logger.info(
                "timeline_poster_daily_limit_reached",
                count=daily_count,
                limit=get_daily_limit(),
            )
            result["skipped"] = True
            result["reason"] = "daily_limit"
            self.total_skipped_limit += 1
            return result

        # Generate content using LLM
        content = await self._generate_content()

        # Check if approval required
        if await is_approval_required():
            # Create draft
            draft = DraftEntry(
                id="",
                text=content,
                post_type=PostType.TIMELINE,
                status=DraftStatus.PENDING,
            )
            saved_draft = await self.draft_repo.save(draft)

            logger.info(
                "timeline_poster_draft_created",
                draft_id=saved_draft.id,
                text_length=len(content),
            )

            result["drafted"] = True
            result["draft_id"] = saved_draft.id
            self.total_drafts += 1
            return result

        # Post directly
        tweet = await self.x_provider.post_tweet(content)

        # Record post
        post = PostEntry(
            id="",
            tweet_id=tweet.id,
            text=content,
            post_type=PostType.TIMELINE,
            status=PostStatus.POSTED,
            posted_at=self.clock.now(),
        )
        await self.post_repo.save(post)

        # Update last post time
        await self.settings_repo.set(
            SETTING_LAST_TIMELINE_POST,
            str(self.clock.timestamp()),
        )

        logger.info(
            "timeline_poster_posted",
            tweet_id=tweet.id,
            text_length=len(content),
        )

        result["posted"] = True
        result["tweet_id"] = tweet.id
        self.total_posts += 1
        return result

    async def _generate_content(self) -> str:
        """
        Generate content for a timeline post using the LLM.

        Returns:
            Generated tweet text
        """
        try:
            content = await self.content_generator.generate_timeline_post()
            logger.debug(
                "timeline_content_generated",
                length=len(content),
            )
            return content
        except Exception as e:
            logger.error("timeline_content_generation_failed", error=str(e))
            # Fallback to placeholder if LLM fails
            return "[AIstein is experiencing technical difficulties. Please stand by for sardonic commentary.]"

    def get_stats(self) -> dict:
        """Get cumulative stats."""
        return {
            "total_posts": self.total_posts,
            "total_drafts": self.total_drafts,
            "total_skipped_safe_mode": self.total_skipped_safe_mode,
            "total_skipped_limit": self.total_skipped_limit,
            "running": self._running,
        }
