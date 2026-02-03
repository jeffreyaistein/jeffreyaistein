"""
Jeffrey AIstein - Self-Style Proposal Worker

Periodic background worker that generates style guide proposals
from AIstein's own tweets. Proposals are NEVER auto-activated.

Features:
- Builds corpus from x_posts table
- Analyzes patterns (length, vocabulary, structure)
- Generates versioned proposal files (MD + JSON)
- Inserts row into style_guide_versions with is_active=false
- Skips if tweet count < minimum threshold
- Redis leader lock ensures only one instance runs at a time

IMPORTANT: Proposals require explicit admin activation.
This worker only PROPOSES - it never activates.

IMPORTANT: Requires REDIS_URL for leader election in production.
Will refuse to run without Redis to prevent duplicate proposals.
"""

import asyncio
import json
import os
import signal
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog

from config import get_settings
from services.social.scheduler.clock import Clock, SystemClock
from services.locking.redis_lock import RedisLock, get_redis_lock

logger = structlog.get_logger()

# Lock key for leader election
SELF_STYLE_LOCK_KEY = "self_style:leader"
# Lock TTL - 5 minutes (proposal generation should complete within this)
SELF_STYLE_LOCK_TTL = 300


def get_self_style_interval() -> int:
    """Get self-style proposal interval from config (seconds)."""
    settings = get_settings()
    return settings.self_style_interval_hours * 3600


def is_self_style_enabled() -> bool:
    """Check if self-style worker is enabled."""
    settings = get_settings()
    return settings.self_style_enabled


def get_self_style_min_tweets() -> int:
    """Get minimum tweet count required for proposal generation."""
    settings = get_settings()
    return settings.self_style_min_tweets


def get_self_style_max_tweets() -> int:
    """Get maximum tweet count to analyze per proposal."""
    settings = get_settings()
    return settings.self_style_max_tweets


def get_self_style_days() -> int:
    """Get number of days to look back for tweets."""
    settings = get_settings()
    return settings.self_style_days


def is_self_style_include_replies() -> bool:
    """Check if replies should be included in analysis."""
    settings = get_settings()
    return settings.self_style_include_replies


class SelfStyleWorker:
    """
    Background worker for self-style proposal generation.

    Periodically generates style guide proposals from AIstein's
    own posted tweets. Proposals are stored in the database
    with is_active=false and require manual admin activation.

    NEVER auto-activates proposals.
    """

    def __init__(
        self,
        clock: Optional[Clock] = None,
        interval: Optional[int] = None,
        min_tweets: Optional[int] = None,
        days: Optional[int] = None,
        redis_lock: Optional[RedisLock] = None,
    ):
        """
        Initialize self-style worker.

        Args:
            clock: Clock implementation (defaults to SystemClock)
            interval: Override interval in seconds (defaults to env)
            min_tweets: Minimum tweets required (defaults to env)
            days: Days to look back for tweets (defaults to env)
            redis_lock: RedisLock for leader election (defaults to singleton)
        """
        self.clock = clock or SystemClock()
        self.interval = interval or get_self_style_interval()
        self.min_tweets = min_tweets or get_self_style_min_tweets()
        self.days = days or get_self_style_days()
        self._lock = redis_lock or get_redis_lock()

        self._running = False
        self._shutdown_event = asyncio.Event()

        # Gating state (exposed for status endpoints)
        self.enabled: bool = is_self_style_enabled()
        self.disabled_reason: Optional[str] = None  # "disabled", "redis_missing", "redis_unavailable"
        self.last_run_status: Optional[str] = None  # "success", "skipped_insufficient_data", "skipped_lock_contention", "failed"

        # Stats
        self.total_runs = 0
        self.total_proposals_generated = 0
        self.total_proposals_skipped = 0
        self.total_errors = 0
        self.total_lock_acquisitions = 0
        self.total_lock_failures = 0
        self.last_run_at: Optional[datetime] = None
        self.last_proposal_version_id: Optional[str] = None
        self.last_proposal_generated_at: Optional[datetime] = None
        self.last_error: Optional[str] = None

        # Leader lock state (exposed for status endpoints)
        self.leader_lock_acquired: bool = False
        self.last_lock_error: Optional[str] = None
        self.last_run_started_at: Optional[datetime] = None
        self.last_run_finished_at: Optional[datetime] = None

        # Set initial disabled_reason if not enabled
        if not self.enabled:
            self.disabled_reason = "disabled"

    def _setup_signal_handlers(self):
        """Setup graceful shutdown on SIGTERM/SIGINT."""
        loop = asyncio.get_event_loop()

        def shutdown_handler():
            logger.info("self_style_worker_shutdown_requested")
            self._shutdown_event.set()

        try:
            loop.add_signal_handler(signal.SIGTERM, shutdown_handler)
            loop.add_signal_handler(signal.SIGINT, shutdown_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    async def start(self) -> None:
        """Start the self-style worker loop."""
        if self._running:
            logger.warning("self_style_worker_already_running")
            return

        # Check if worker is enabled
        self.enabled = is_self_style_enabled()
        if not self.enabled:
            self.disabled_reason = "disabled"
            logger.info(
                "self_style_worker_disabled",
                disabled_reason=self.disabled_reason,
                message="Set SELF_STYLE_ENABLED=true to enable",
            )
            return

        # CRITICAL: Check Redis availability before starting
        # We MUST have leader lock capability in production to prevent
        # duplicate proposals from multiple instances
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            # No Redis URL configured at all
            self.disabled_reason = "redis_missing"
            logger.error(
                "self_style_worker_redis_not_configured",
                disabled_reason=self.disabled_reason,
                redis_url_configured=False,
                action="REFUSING TO START - leader lock required",
                message="REDIS_URL not set. Leader lock required to prevent duplicate proposals.",
            )
            self.last_lock_error = "REDIS_URL not configured - worker refused to start"
            return

        redis_available = await self._lock.is_available()
        if not redis_available:
            # Redis URL configured but connection failed
            self.disabled_reason = "redis_unavailable"
            logger.error(
                "self_style_worker_redis_unavailable",
                disabled_reason=self.disabled_reason,
                redis_url_configured=True,
                action="REFUSING TO START - leader lock required",
                message="Redis connection failed. Fix Redis or disable SELF_STYLE_ENABLED.",
            )
            self.last_lock_error = "Redis connection failed - worker refused to start"
            return

        # All checks passed - clear disabled_reason
        self.disabled_reason = None

        self._running = True
        self._shutdown_event.clear()
        self._setup_signal_handlers()

        logger.info(
            "self_style_worker_started",
            interval_hours=self.interval / 3600,
            min_tweets=self.min_tweets,
            days=self.days,
            lock_key=SELF_STYLE_LOCK_KEY,
            lock_ttl=SELF_STYLE_LOCK_TTL,
        )

        while self._running and not self._shutdown_event.is_set():
            try:
                await self._run_with_lock()
            except Exception as e:
                logger.exception("self_style_worker_unexpected_error", error=str(e))
                self.total_errors += 1
                self.last_error = str(e)
                # Continue running - don't let errors stop the worker

            # Wait for next iteration
            await self.clock.sleep(self.interval)

        logger.info("self_style_worker_stopped")

    async def stop(self) -> None:
        """Stop the self-style worker gracefully."""
        logger.info("self_style_worker_stop_requested")
        self._running = False
        self._shutdown_event.set()

    async def _run_with_lock(self) -> dict:
        """
        Attempt to acquire leader lock and run proposal generation.

        If lock acquisition fails (another instance holds it), skip this cycle.
        If lock acquisition succeeds, run _process_once() and release lock.

        Returns:
            Stats dict from _process_once(), or lock failure info
        """
        self.last_run_started_at = datetime.now(timezone.utc)
        self.leader_lock_acquired = False
        self.last_lock_error = None

        try:
            # Attempt to acquire leader lock
            acquired = await self._lock.acquire(
                SELF_STYLE_LOCK_KEY,
                ttl_seconds=SELF_STYLE_LOCK_TTL,
            )

            if not acquired:
                # Another instance holds the lock - skip this cycle
                self.total_lock_failures += 1
                self.leader_lock_acquired = False
                self.last_run_status = "skipped_lock_contention"

                # Check who holds the lock (for debugging)
                holder = await self._lock.get_lock_holder(SELF_STYLE_LOCK_KEY)

                logger.info(
                    "self_style_lock_not_acquired",
                    lock_key=SELF_STYLE_LOCK_KEY,
                    current_holder=holder,
                    our_instance=self._lock.instance_id,
                    action="skipping this cycle",
                )

                self.last_run_finished_at = datetime.now(timezone.utc)
                return {
                    "lock_acquired": False,
                    "skipped": True,
                    "skip_reason": "leader lock held by another instance",
                    "lock_holder": holder,
                }

            # Lock acquired - we are the leader
            self.leader_lock_acquired = True
            self.total_lock_acquisitions += 1

            logger.info(
                "self_style_lock_acquired",
                lock_key=SELF_STYLE_LOCK_KEY,
                instance_id=self._lock.instance_id,
                ttl_seconds=SELF_STYLE_LOCK_TTL,
            )

            try:
                # Run the actual proposal generation
                stats = await self._process_once()
                stats["lock_acquired"] = True
                return stats
            finally:
                # Always release lock when done
                released = await self._lock.release(SELF_STYLE_LOCK_KEY)
                self.leader_lock_acquired = False

                if released:
                    logger.info(
                        "self_style_lock_released",
                        lock_key=SELF_STYLE_LOCK_KEY,
                        instance_id=self._lock.instance_id,
                    )
                else:
                    # Lock may have expired (TTL) or been taken
                    logger.warning(
                        "self_style_lock_release_failed",
                        lock_key=SELF_STYLE_LOCK_KEY,
                        instance_id=self._lock.instance_id,
                        message="Lock may have expired or been taken by another instance",
                    )

        except Exception as e:
            error_msg = f"Lock operation failed: {str(e)}"
            self.last_lock_error = error_msg
            self.leader_lock_acquired = False

            logger.error(
                "self_style_lock_error",
                lock_key=SELF_STYLE_LOCK_KEY,
                error=str(e),
            )

            return {
                "lock_acquired": False,
                "skipped": True,
                "skip_reason": "lock operation error",
                "error": error_msg,
            }
        finally:
            self.last_run_finished_at = datetime.now(timezone.utc)

    async def process_once(self) -> dict:
        """
        Execute a single proposal generation.

        Returns:
            Stats dict with generation results
        """
        return await self._process_once()

    async def _process_once(self) -> dict:
        """Internal processing implementation."""
        self.last_run_at = datetime.now(timezone.utc)
        self.total_runs += 1

        stats = {
            "proposal_generated": False,
            "version_id": None,
            "tweet_count": 0,
            "skipped": False,
            "skip_reason": None,
            "error": None,
        }

        try:
            # Import here to avoid circular imports
            from scripts.propose_style_guide import propose_style_guide
            from db.base import async_session_maker
            from sqlalchemy import text

            # PRE-CHECK: Count available tweets before attempting to generate
            # This allows us to skip early and log the specific count
            max_tweets = get_self_style_max_tweets()
            include_replies = is_self_style_include_replies()

            async with async_session_maker() as session:
                # Build count query matching propose_style_guide filters
                count_query = text("""
                    SELECT COUNT(*) as tweet_count
                    FROM x_posts
                    WHERE status = 'posted'
                    AND posted_at >= NOW() - INTERVAL ':days days'
                    AND (:include_replies OR post_type != 'reply')
                """.replace(":days", str(self.days)).replace(":include_replies", "true" if include_replies else "false"))

                result_row = await session.execute(count_query)
                available_count = result_row.scalar() or 0

            # Check if we have enough tweets
            if available_count < self.min_tweets:
                stats["skipped"] = True
                stats["skip_reason"] = f"insufficient_data: {available_count} tweets < {self.min_tweets} minimum"
                stats["tweet_count"] = available_count
                self.total_proposals_skipped += 1
                self.last_run_status = "skipped_insufficient_data"

                logger.info(
                    "self_style_skipped_insufficient_data",
                    tweet_count=available_count,
                    min_tweets=self.min_tweets,
                    days=self.days,
                    include_replies=include_replies,
                    message=f"Skipping proposal: {available_count} tweets < {self.min_tweets} minimum required",
                )

                return stats

            logger.info(
                "self_style_worker_starting_proposal",
                days=self.days,
                min_tweets=self.min_tweets,
                max_tweets=max_tweets,
                available_tweets=available_count,
            )

            # Generate proposal (does NOT activate)
            result = await propose_style_guide(
                days=self.days,
                limit=max_tweets,
                min_tweets=self.min_tweets,
            )

            version_id = result["version_id"]
            tweet_count = result["tweet_count"]
            # Parse generated_at - it comes as ISO string from propose_style_guide
            generated_at_str = result["generated_at"]
            if isinstance(generated_at_str, str):
                generated_at = datetime.fromisoformat(generated_at_str.replace("Z", "+00:00"))
            else:
                generated_at = generated_at_str
            md_path = result["files"]["markdown"]
            json_path = result["files"]["json"]

            # Insert row into style_guide_versions with is_active=false
            async with async_session_maker() as session:
                insert_query = text("""
                    INSERT INTO style_guide_versions (
                        version_id,
                        generated_at,
                        source,
                        tweet_count,
                        md_path,
                        json_path,
                        is_active,
                        metadata_json,
                        created_at
                    ) VALUES (
                        :version_id,
                        :generated_at,
                        'self_style',
                        :tweet_count,
                        :md_path,
                        :json_path,
                        false,
                        CAST(:metadata AS jsonb),
                        :created_at
                    )
                """)

                metadata = json.dumps({
                    "analysis": result.get("analysis", {}),
                    "hard_constraints": result.get("hard_constraints", {}),
                    "source_script": "self_style_worker",
                })

                await session.execute(insert_query, {
                    "version_id": version_id,
                    "generated_at": generated_at,
                    "tweet_count": tweet_count,
                    "md_path": md_path,
                    "json_path": json_path,
                    "metadata": metadata,
                    "created_at": datetime.now(timezone.utc),
                })
                await session.commit()

            # Update stats
            stats["proposal_generated"] = True
            stats["version_id"] = version_id
            stats["tweet_count"] = tweet_count

            self.total_proposals_generated += 1
            self.last_proposal_version_id = version_id
            self.last_proposal_generated_at = datetime.now(timezone.utc)
            self.last_error = None
            self.last_run_status = "success"

            logger.info(
                "proposal_generated",
                version_id=version_id,
                tweet_count=tweet_count,
                md_path=md_path,
                json_path=json_path,
                is_active=False,
                message="Proposal created - requires admin activation",
            )

        except ValueError as e:
            # Insufficient tweets - this is expected sometimes
            error_msg = str(e)
            if "Insufficient tweets" in error_msg:
                stats["skipped"] = True
                stats["skip_reason"] = error_msg
                self.total_proposals_skipped += 1
                self.last_run_status = "skipped_insufficient_data"

                logger.info(
                    "self_style_skipped_insufficient_data",
                    reason=error_msg,
                    min_tweets=self.min_tweets,
                )
            else:
                stats["error"] = error_msg
                self.total_errors += 1
                self.last_error = error_msg
                self.last_run_status = "failed"

                logger.error(
                    "proposal_failed",
                    error=error_msg,
                )

        except Exception as e:
            error_msg = str(e)
            stats["error"] = error_msg
            self.total_errors += 1
            self.last_error = error_msg
            self.last_run_status = "failed"

            logger.exception(
                "proposal_failed",
                error=error_msg,
            )

        return stats

    def get_stats(self) -> dict:
        """Get cumulative stats."""
        return {
            # Gating status
            "enabled": self.enabled,
            "disabled_reason": self.disabled_reason,
            "last_run_status": self.last_run_status,
            # Core stats
            "total_runs": self.total_runs,
            "total_proposals_generated": self.total_proposals_generated,
            "total_proposals_skipped": self.total_proposals_skipped,
            "total_errors": self.total_errors,
            "running": self._running,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_proposal_version_id": self.last_proposal_version_id,
            "last_proposal_generated_at": self.last_proposal_generated_at.isoformat() if self.last_proposal_generated_at else None,
            "last_error": self.last_error,
            # Leader lock stats
            "leader_lock": {
                "lock_key": SELF_STYLE_LOCK_KEY,
                "lock_ttl_seconds": SELF_STYLE_LOCK_TTL,
                "currently_acquired": self.leader_lock_acquired,
                "instance_id": self._lock.instance_id,
                "total_acquisitions": self.total_lock_acquisitions,
                "total_failures": self.total_lock_failures,
                "last_error": self.last_lock_error,
            },
            "last_run_started_at": self.last_run_started_at.isoformat() if self.last_run_started_at else None,
            "last_run_finished_at": self.last_run_finished_at.isoformat() if self.last_run_finished_at else None,
            "config": {
                "interval_hours": self.interval / 3600,
                "min_tweets": self.min_tweets,
                "max_tweets": get_self_style_max_tweets(),
                "days": self.days,
                "include_replies": is_self_style_include_replies(),
            },
        }
