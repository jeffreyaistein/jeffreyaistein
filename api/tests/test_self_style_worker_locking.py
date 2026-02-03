"""
Jeffrey AIstein - SelfStyleWorker Locking Tests

Unit tests for the leader lock integration in SelfStyleWorker.
Uses mocks for deterministic, fast tests without network/Redis.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from services.social.scheduler.self_style_worker import (
    SelfStyleWorker,
    SELF_STYLE_LOCK_KEY,
    SELF_STYLE_LOCK_TTL,
)
from services.social.scheduler.clock import FakeClock
from services.locking.redis_lock import RedisLock, reset_redis_lock


class MockRedisLock:
    """Mock RedisLock for testing."""

    def __init__(self, instance_id: str = "mock-instance", acquire_result: bool = True):
        self.instance_id = instance_id
        self.acquire_result = acquire_result
        self.acquire_called = False
        self.release_called = False
        self.is_available_result = True

    async def is_available(self) -> bool:
        return self.is_available_result

    async def acquire(self, lock_key: str, ttl_seconds: int = 120) -> bool:
        self.acquire_called = True
        self.last_acquire_key = lock_key
        self.last_acquire_ttl = ttl_seconds
        return self.acquire_result

    async def release(self, lock_key: str) -> bool:
        self.release_called = True
        self.last_release_key = lock_key
        return True

    async def get_lock_holder(self, lock_key: str) -> str:
        if not self.acquire_result:
            return "other-instance"
        return None

    async def renew(self, lock_key: str, ttl_seconds: int = 120) -> bool:
        return self.acquire_result


class TestSelfStyleWorkerLockAcquired:
    """Tests for when lock is successfully acquired."""

    @pytest.fixture
    def mock_lock_acquired(self):
        """Create a mock lock that always acquires."""
        return MockRedisLock(acquire_result=True)

    @pytest.fixture
    def worker_with_lock(self, mock_lock_acquired):
        """Create worker with mock lock."""
        reset_redis_lock()
        clock = FakeClock()
        worker = SelfStyleWorker(
            clock=clock,
            interval=3600,
            min_tweets=10,
            days=7,
            redis_lock=mock_lock_acquired,
        )
        return worker, mock_lock_acquired, clock

    @pytest.mark.asyncio
    async def test_process_once_called_when_lock_acquired(self, worker_with_lock):
        """_process_once is called exactly once when lock is acquired."""
        worker, mock_lock, clock = worker_with_lock

        # Mock _process_once to track calls
        process_once_called = []

        async def mock_process_once():
            process_once_called.append(True)
            return {"proposal_generated": False, "skipped": True, "skip_reason": "test"}

        worker._process_once = mock_process_once

        # Run with lock
        result = await worker._run_with_lock()

        # Verify lock was acquired and process_once called
        assert mock_lock.acquire_called is True
        assert len(process_once_called) == 1
        assert result["lock_acquired"] is True

    @pytest.mark.asyncio
    async def test_lock_released_after_processing(self, worker_with_lock):
        """Lock is released after _process_once completes."""
        worker, mock_lock, clock = worker_with_lock

        async def mock_process_once():
            return {"proposal_generated": False}

        worker._process_once = mock_process_once

        await worker._run_with_lock()

        # Verify release was called
        assert mock_lock.release_called is True
        assert mock_lock.last_release_key == SELF_STYLE_LOCK_KEY

    @pytest.mark.asyncio
    async def test_lock_released_even_on_exception(self, worker_with_lock):
        """Lock is released even if _process_once raises an exception."""
        worker, mock_lock, clock = worker_with_lock

        async def mock_process_once_error():
            raise ValueError("Simulated error")

        worker._process_once = mock_process_once_error

        # The exception is caught internally in _run_with_lock's exception handler
        # It should not propagate, and lock should still be released
        result = await worker._run_with_lock()

        # Lock should still be released (finally block executes)
        assert mock_lock.release_called is True
        # The error is recorded
        assert worker.last_lock_error is not None
        assert "Simulated error" in worker.last_lock_error

    @pytest.mark.asyncio
    async def test_lock_stats_updated_on_acquire(self, worker_with_lock):
        """Worker stats are updated when lock is acquired."""
        worker, mock_lock, clock = worker_with_lock

        async def mock_process_once():
            return {"proposal_generated": False}

        worker._process_once = mock_process_once

        assert worker.total_lock_acquisitions == 0

        await worker._run_with_lock()

        assert worker.total_lock_acquisitions == 1
        assert worker.leader_lock_acquired is False  # Released after processing


class TestSelfStyleWorkerLockNotAcquired:
    """Tests for when lock acquisition fails (contention)."""

    @pytest.fixture
    def mock_lock_contention(self):
        """Create a mock lock that fails to acquire (someone else holds it)."""
        return MockRedisLock(acquire_result=False)

    @pytest.fixture
    def worker_with_contention(self, mock_lock_contention):
        """Create worker with contention mock."""
        reset_redis_lock()
        clock = FakeClock()
        worker = SelfStyleWorker(
            clock=clock,
            interval=3600,
            min_tweets=10,
            days=7,
            redis_lock=mock_lock_contention,
        )
        return worker, mock_lock_contention, clock

    @pytest.mark.asyncio
    async def test_process_once_not_called_when_lock_not_acquired(self, worker_with_contention):
        """_process_once is NOT called when lock acquisition fails."""
        worker, mock_lock, clock = worker_with_contention

        process_once_called = []

        async def mock_process_once():
            process_once_called.append(True)
            return {"proposal_generated": True}

        worker._process_once = mock_process_once

        result = await worker._run_with_lock()

        # Lock acquisition was attempted
        assert mock_lock.acquire_called is True
        # But _process_once was NOT called
        assert len(process_once_called) == 0
        # Result indicates skipped
        assert result["lock_acquired"] is False
        assert result["skipped"] is True
        assert "leader lock held by another instance" in result["skip_reason"]

    @pytest.mark.asyncio
    async def test_lock_failure_stats_updated(self, worker_with_contention):
        """Worker stats track lock failures."""
        worker, mock_lock, clock = worker_with_contention

        async def mock_process_once():
            return {"proposal_generated": True}

        worker._process_once = mock_process_once

        assert worker.total_lock_failures == 0

        await worker._run_with_lock()

        assert worker.total_lock_failures == 1
        assert worker.total_lock_acquisitions == 0

    @pytest.mark.asyncio
    async def test_release_not_called_when_not_acquired(self, worker_with_contention):
        """Release is not called if we didn't acquire the lock."""
        worker, mock_lock, clock = worker_with_contention

        async def mock_process_once():
            return {}

        worker._process_once = mock_process_once

        await worker._run_with_lock()

        # Release should NOT be called since we never acquired
        assert mock_lock.release_called is False


class TestSelfStyleWorkerRedisUnavailable:
    """Tests for when Redis is unavailable."""

    @pytest.fixture
    def mock_lock_unavailable(self):
        """Create a mock lock where Redis is unavailable."""
        lock = MockRedisLock()
        lock.is_available_result = False
        return lock

    @pytest.mark.asyncio
    async def test_worker_refuses_to_start_without_redis(self, mock_lock_unavailable):
        """Worker refuses to start when Redis is unavailable."""
        reset_redis_lock()
        clock = FakeClock()
        worker = SelfStyleWorker(
            clock=clock,
            interval=3600,
            min_tweets=10,
            days=7,
            redis_lock=mock_lock_unavailable,
        )

        # Patch is_self_style_enabled to return True
        with patch("services.social.scheduler.self_style_worker.is_self_style_enabled", return_value=True):
            # Start should return early without running
            await worker.start()

        # Worker should not be running
        assert worker._running is False
        # Error should be recorded
        assert worker.last_lock_error is not None
        # Should indicate Redis issue (either "not configured" or "connection failed")
        assert "REDIS_URL" in worker.last_lock_error or "Redis" in worker.last_lock_error
        # disabled_reason should be set
        assert worker.disabled_reason in ("redis_missing", "redis_unavailable")

    @pytest.mark.asyncio
    async def test_worker_sets_error_when_redis_missing(self, mock_lock_unavailable):
        """Worker sets appropriate error message when Redis unavailable."""
        reset_redis_lock()
        clock = FakeClock()
        worker = SelfStyleWorker(
            clock=clock,
            interval=3600,
            min_tweets=10,
            days=7,
            redis_lock=mock_lock_unavailable,
        )

        with patch("services.social.scheduler.self_style_worker.is_self_style_enabled", return_value=True):
            await worker.start()

        assert "refused to start" in worker.last_lock_error


class TestSelfStyleWorkerLockError:
    """Tests for lock operation errors."""

    @pytest.fixture
    def mock_lock_error(self):
        """Create a mock lock that raises errors."""
        lock = MockRedisLock()
        lock.is_available_result = True
        return lock

    @pytest.mark.asyncio
    async def test_lock_error_handled_gracefully(self, mock_lock_error):
        """Lock errors are caught and handled gracefully."""
        reset_redis_lock()
        clock = FakeClock()
        worker = SelfStyleWorker(
            clock=clock,
            interval=3600,
            min_tweets=10,
            days=7,
            redis_lock=mock_lock_error,
        )

        # Make acquire raise an exception
        async def failing_acquire(key, ttl_seconds):
            raise Exception("Redis connection lost")

        mock_lock_error.acquire = failing_acquire

        result = await worker._run_with_lock()

        # Should not crash, should return error info
        assert result["lock_acquired"] is False
        assert result["skipped"] is True
        assert "error" in result["skip_reason"]
        assert worker.last_lock_error is not None


class TestSelfStyleWorkerTimestamps:
    """Tests for run timestamp tracking."""

    @pytest.fixture
    def worker_with_mock_lock(self):
        """Create worker with working mock lock."""
        reset_redis_lock()
        clock = FakeClock()
        mock_lock = MockRedisLock(acquire_result=True)
        worker = SelfStyleWorker(
            clock=clock,
            interval=3600,
            min_tweets=10,
            days=7,
            redis_lock=mock_lock,
        )
        return worker

    @pytest.mark.asyncio
    async def test_timestamps_set_on_run(self, worker_with_mock_lock):
        """last_run_started_at and last_run_finished_at are set."""
        worker = worker_with_mock_lock

        async def mock_process_once():
            return {"proposal_generated": False}

        worker._process_once = mock_process_once

        assert worker.last_run_started_at is None
        assert worker.last_run_finished_at is None

        await worker._run_with_lock()

        assert worker.last_run_started_at is not None
        assert worker.last_run_finished_at is not None
        assert worker.last_run_started_at <= worker.last_run_finished_at


class TestSelfStyleWorkerStats:
    """Tests for get_stats() including lock info."""

    @pytest.mark.asyncio
    async def test_stats_include_lock_info(self):
        """get_stats() includes leader_lock section."""
        reset_redis_lock()
        clock = FakeClock()
        mock_lock = MockRedisLock(instance_id="stats-test-instance")
        worker = SelfStyleWorker(
            clock=clock,
            interval=3600,
            min_tweets=10,
            days=7,
            redis_lock=mock_lock,
        )

        stats = worker.get_stats()

        assert "leader_lock" in stats
        assert stats["leader_lock"]["lock_key"] == SELF_STYLE_LOCK_KEY
        assert stats["leader_lock"]["lock_ttl_seconds"] == SELF_STYLE_LOCK_TTL
        assert stats["leader_lock"]["instance_id"] == "stats-test-instance"
        assert stats["leader_lock"]["total_acquisitions"] == 0
        assert stats["leader_lock"]["total_failures"] == 0
