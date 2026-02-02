"""
Jeffrey AIstein - Clock Interface

Abstraction for time operations to enable testable scheduling.
"""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional


class Clock(ABC):
    """Abstract clock interface for testable time operations."""

    @abstractmethod
    def now(self) -> datetime:
        """Get current UTC time."""
        pass

    @abstractmethod
    async def sleep(self, seconds: float) -> None:
        """Sleep for the given duration."""
        pass

    @abstractmethod
    def timestamp(self) -> float:
        """Get current Unix timestamp."""
        pass


class SystemClock(Clock):
    """Real system clock implementation."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)

    def timestamp(self) -> float:
        return datetime.now(timezone.utc).timestamp()


class FakeClock(Clock):
    """
    Fake clock for testing.

    Allows manual time advancement without actual sleeping.
    """

    def __init__(self, start_time: Optional[datetime] = None):
        """
        Initialize fake clock.

        Args:
            start_time: Initial time (defaults to now)
        """
        if start_time is None:
            start_time = datetime.now(timezone.utc)
        self._current_time = start_time
        self._sleep_calls: list[float] = []

    def now(self) -> datetime:
        return self._current_time

    async def sleep(self, seconds: float) -> None:
        """Record sleep call and advance time."""
        self._sleep_calls.append(seconds)
        self.advance(seconds)

    def timestamp(self) -> float:
        return self._current_time.timestamp()

    def advance(self, seconds: float) -> None:
        """Advance the clock by the given seconds."""
        from datetime import timedelta
        self._current_time += timedelta(seconds=seconds)

    def set(self, time: datetime) -> None:
        """Set the clock to a specific time."""
        self._current_time = time

    @property
    def sleep_calls(self) -> list[float]:
        """Get list of sleep durations that were called."""
        return self._sleep_calls.copy()

    def clear_sleep_calls(self) -> None:
        """Clear recorded sleep calls."""
        self._sleep_calls.clear()
