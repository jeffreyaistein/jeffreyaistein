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
from services.social.scheduler.learning_worker import (
    LearningWorker,
    get_learning_interval,
)
from services.social.scheduler.self_style_worker import (
    SelfStyleWorker,
    get_self_style_interval,
    is_self_style_enabled,
    get_self_style_min_tweets,
    get_self_style_max_tweets,
    get_self_style_days,
    is_self_style_include_replies,
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
    # Learning worker
    "LearningWorker",
    "get_learning_interval",
    # Self-style worker
    "SelfStyleWorker",
    "get_self_style_interval",
    "is_self_style_enabled",
    "get_self_style_min_tweets",
    "get_self_style_max_tweets",
    "get_self_style_days",
    "is_self_style_include_replies",
]
