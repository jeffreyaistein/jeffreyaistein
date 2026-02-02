"""
Jeffrey AIstein - Scheduler Package

Scheduling components for X bot operations.
"""

from services.social.scheduler.clock import Clock, FakeClock, SystemClock
from services.social.scheduler.ingestion import (
    IngestionLoop,
    get_poll_interval,
)
from services.social.scheduler.timeline_poster import (
    TimelinePosterLoop,
    get_daily_limit,
    get_hourly_limit,
    get_timeline_interval,
    get_timeline_jitter,
    is_approval_required,
    is_safe_mode,
)

__all__ = [
    # Clock
    "Clock",
    "FakeClock",
    "SystemClock",
    # Ingestion
    "IngestionLoop",
    "get_poll_interval",
    # Timeline poster
    "TimelinePosterLoop",
    "get_timeline_interval",
    "get_timeline_jitter",
    "get_hourly_limit",
    "get_daily_limit",
    "is_safe_mode",
    "is_approval_required",
]
