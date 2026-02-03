"""
Jeffrey AIstein - Learning Extraction Worker

Periodic background worker that processes unprocessed inbox/posts
to extract learning memories. Designed to be safe and non-blocking.
"""

import asyncio
import os
import signal
from typing import Optional

import structlog

from services.social.scheduler.clock import Clock, SystemClock

logger = structlog.get_logger()


def get_learning_interval() -> int:
    """Get learning extraction interval from environment (seconds)."""
    return int(os.getenv("X_LEARNING_INTERVAL_SECONDS", "60"))


class LearningWorker:
    """
    Background worker for learning extraction.

    Periodically processes unprocessed inbox items and posts
    to extract learning memories. Runs independently of main loops
    to avoid blocking ingestion or posting operations.
    """

    def __init__(
        self,
        clock: Optional[Clock] = None,
        interval: Optional[int] = None,
        batch_size: int = 50,
    ):
        """
        Initialize learning worker.

        Args:
            clock: Clock implementation (defaults to SystemClock)
            interval: Override polling interval (defaults to env)
            batch_size: Number of items to process per iteration
        """
        self.clock = clock or SystemClock()
        self.interval = interval or get_learning_interval()
        self.batch_size = batch_size

        self._running = False
        self._shutdown_event = asyncio.Event()

        # Stats
        self.total_runs = 0
        self.total_inbox_processed = 0
        self.total_posts_processed = 0
        self.total_memories_created = 0
        self.total_errors = 0

    def _setup_signal_handlers(self):
        """Setup graceful shutdown on SIGTERM/SIGINT."""
        loop = asyncio.get_event_loop()

        def shutdown_handler():
            logger.info("learning_worker_shutdown_requested")
            self._shutdown_event.set()

        try:
            loop.add_signal_handler(signal.SIGTERM, shutdown_handler)
            loop.add_signal_handler(signal.SIGINT, shutdown_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    async def start(self) -> None:
        """Start the learning worker loop."""
        if self._running:
            logger.warning("learning_worker_already_running")
            return

        self._running = True
        self._shutdown_event.clear()
        self._setup_signal_handlers()

        logger.info(
            "learning_worker_started",
            interval=self.interval,
            batch_size=self.batch_size,
        )

        while self._running and not self._shutdown_event.is_set():
            try:
                await self._process_once()
            except Exception as e:
                logger.exception("learning_worker_unexpected_error", error=str(e))
                self.total_errors += 1
                # Continue running - don't let errors stop the worker

            # Wait for next iteration
            await self.clock.sleep(self.interval)

        logger.info("learning_worker_stopped")

    async def stop(self) -> None:
        """Stop the learning worker gracefully."""
        logger.info("learning_worker_stop_requested")
        self._running = False
        self._shutdown_event.set()

    async def process_once(self) -> dict:
        """
        Execute a single processing iteration.

        Returns:
            Stats dict with processing results
        """
        return await self._process_once()

    async def _process_once(self) -> dict:
        """Internal processing implementation."""
        # Import here to avoid circular imports
        from services.learning import get_learning_extractor

        stats = {
            "inbox_processed": 0,
            "posts_processed": 0,
            "memories_created": 0,
            "errors": 0,
        }

        try:
            extractor = get_learning_extractor()
            result = await extractor.process_unprocessed_items(limit=self.batch_size)

            stats["inbox_processed"] = result.get("inbox_processed", 0)
            stats["posts_processed"] = result.get("posts_processed", 0)
            stats["memories_created"] = result.get("total_memories", 0)
            stats["errors"] = result.get("errors", 0)

            self.total_inbox_processed += stats["inbox_processed"]
            self.total_posts_processed += stats["posts_processed"]
            self.total_memories_created += stats["memories_created"]

            if stats["inbox_processed"] > 0 or stats["posts_processed"] > 0:
                logger.info(
                    "learning_worker_processed",
                    inbox=stats["inbox_processed"],
                    posts=stats["posts_processed"],
                    memories=stats["memories_created"],
                )
            else:
                logger.debug("learning_worker_nothing_to_process")

        except Exception as e:
            logger.exception("learning_worker_processing_failed", error=str(e))
            stats["errors"] = 1
            self.total_errors += 1

        self.total_runs += 1
        return stats

    def get_stats(self) -> dict:
        """Get cumulative stats."""
        return {
            "total_runs": self.total_runs,
            "total_inbox_processed": self.total_inbox_processed,
            "total_posts_processed": self.total_posts_processed,
            "total_memories_created": self.total_memories_created,
            "total_errors": self.total_errors,
            "running": self._running,
        }
