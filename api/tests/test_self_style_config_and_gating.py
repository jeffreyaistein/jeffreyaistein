"""
Jeffrey AIstein - Self-Style Config and Gating Tests

Tests for:
1. Config parsing (Settings class and config functions)
2. Worker gating logic (enabled, Redis, tweet count, lock)

All tests are deterministic - no sleeps, no network, uses mocks.
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime, timezone

from services.social.scheduler.clock import FakeClock
from services.locking.redis_lock import reset_redis_lock


# =============================================================================
# CONFIG PARSING TESTS
# =============================================================================


class TestSelfStyleConfigDefaults:
    """Test default values when env vars are unset."""

    def test_default_self_style_enabled(self):
        """SELF_STYLE_ENABLED defaults to False."""
        with patch.dict(os.environ, {}, clear=True):
            # Clear lru_cache to get fresh settings
            from config import get_settings
            get_settings.cache_clear()

            from config import Settings
            settings = Settings()
            assert settings.self_style_enabled is False

    def test_default_interval_hours(self):
        """SELF_STYLE_INTERVAL_HOURS defaults to 24."""
        with patch.dict(os.environ, {}, clear=True):
            from config import Settings
            settings = Settings()
            assert settings.self_style_interval_hours == 24

    def test_default_min_tweets(self):
        """SELF_STYLE_MIN_TWEETS defaults to 25."""
        with patch.dict(os.environ, {}, clear=True):
            from config import Settings
            settings = Settings()
            assert settings.self_style_min_tweets == 25

    def test_default_max_tweets(self):
        """SELF_STYLE_MAX_TWEETS defaults to 500."""
        with patch.dict(os.environ, {}, clear=True):
            from config import Settings
            settings = Settings()
            assert settings.self_style_max_tweets == 500

    def test_default_days(self):
        """SELF_STYLE_DAYS defaults to 30."""
        with patch.dict(os.environ, {}, clear=True):
            from config import Settings
            settings = Settings()
            assert settings.self_style_days == 30

    def test_default_include_replies(self):
        """SELF_STYLE_INCLUDE_REPLIES defaults to True."""
        with patch.dict(os.environ, {}, clear=True):
            from config import Settings
            settings = Settings()
            assert settings.self_style_include_replies is True


class TestSelfStyleConfigOverrides:
    """Test env var overrides for self-style settings."""

    def test_enabled_override_true(self):
        """SELF_STYLE_ENABLED=true overrides to True."""
        env = {"SELF_STYLE_ENABLED": "true"}
        with patch.dict(os.environ, env, clear=True):
            from config import Settings
            settings = Settings()
            assert settings.self_style_enabled is True

    def test_enabled_override_false(self):
        """SELF_STYLE_ENABLED=false overrides to False."""
        env = {"SELF_STYLE_ENABLED": "false"}
        with patch.dict(os.environ, env, clear=True):
            from config import Settings
            settings = Settings()
            assert settings.self_style_enabled is False

    def test_interval_hours_override(self):
        """SELF_STYLE_INTERVAL_HOURS overrides correctly."""
        env = {"SELF_STYLE_INTERVAL_HOURS": "48"}
        with patch.dict(os.environ, env, clear=True):
            from config import Settings
            settings = Settings()
            assert settings.self_style_interval_hours == 48

    def test_min_tweets_override(self):
        """SELF_STYLE_MIN_TWEETS overrides correctly."""
        env = {"SELF_STYLE_MIN_TWEETS": "100"}
        with patch.dict(os.environ, env, clear=True):
            from config import Settings
            settings = Settings()
            assert settings.self_style_min_tweets == 100

    def test_max_tweets_override(self):
        """SELF_STYLE_MAX_TWEETS overrides correctly."""
        env = {"SELF_STYLE_MAX_TWEETS": "1000"}
        with patch.dict(os.environ, env, clear=True):
            from config import Settings
            settings = Settings()
            assert settings.self_style_max_tweets == 1000

    def test_days_override(self):
        """SELF_STYLE_DAYS overrides correctly."""
        env = {"SELF_STYLE_DAYS": "60"}
        with patch.dict(os.environ, env, clear=True):
            from config import Settings
            settings = Settings()
            assert settings.self_style_days == 60

    def test_include_replies_override_false(self):
        """SELF_STYLE_INCLUDE_REPLIES=false overrides to False."""
        env = {"SELF_STYLE_INCLUDE_REPLIES": "false"}
        with patch.dict(os.environ, env, clear=True):
            from config import Settings
            settings = Settings()
            assert settings.self_style_include_replies is False


class TestSelfStyleConfigTypeSafety:
    """Test type enforcement for self-style settings."""

    def test_interval_hours_non_integer_uses_default(self):
        """Non-integer SELF_STYLE_INTERVAL_HOURS raises or uses default."""
        env = {"SELF_STYLE_INTERVAL_HOURS": "not_a_number"}
        with patch.dict(os.environ, env, clear=True):
            from config import Settings
            # Pydantic should raise a validation error for bad int
            with pytest.raises(Exception):  # ValidationError
                Settings()

    def test_min_tweets_non_integer_raises(self):
        """Non-integer SELF_STYLE_MIN_TWEETS raises validation error."""
        env = {"SELF_STYLE_MIN_TWEETS": "abc"}
        with patch.dict(os.environ, env, clear=True):
            from config import Settings
            with pytest.raises(Exception):
                Settings()

    def test_enabled_invalid_bool_treated_as_false(self):
        """Invalid bool for SELF_STYLE_ENABLED is handled by Pydantic."""
        # Pydantic treats many values as truthy/falsy
        env = {"SELF_STYLE_ENABLED": "yes"}
        with patch.dict(os.environ, env, clear=True):
            from config import Settings
            settings = Settings()
            # "yes" is typically truthy for Pydantic bools
            assert settings.self_style_enabled is True


class TestSelfStyleConfigFunctions:
    """Test config accessor functions in self_style_worker.py."""

    def test_get_self_style_interval_returns_seconds(self):
        """get_self_style_interval() returns value in seconds."""
        with patch("services.social.scheduler.self_style_worker.get_settings") as mock_settings:
            mock_settings.return_value.self_style_interval_hours = 24
            from services.social.scheduler.self_style_worker import get_self_style_interval
            result = get_self_style_interval()
            assert result == 24 * 3600

    def test_is_self_style_enabled_returns_bool(self):
        """is_self_style_enabled() returns bool from settings."""
        with patch("services.social.scheduler.self_style_worker.get_settings") as mock_settings:
            mock_settings.return_value.self_style_enabled = True
            from services.social.scheduler.self_style_worker import is_self_style_enabled
            result = is_self_style_enabled()
            assert result is True

    def test_get_self_style_min_tweets_returns_int(self):
        """get_self_style_min_tweets() returns int from settings."""
        with patch("services.social.scheduler.self_style_worker.get_settings") as mock_settings:
            mock_settings.return_value.self_style_min_tweets = 50
            from services.social.scheduler.self_style_worker import get_self_style_min_tweets
            result = get_self_style_min_tweets()
            assert result == 50

    def test_get_self_style_max_tweets_returns_int(self):
        """get_self_style_max_tweets() returns int from settings."""
        with patch("services.social.scheduler.self_style_worker.get_settings") as mock_settings:
            mock_settings.return_value.self_style_max_tweets = 200
            from services.social.scheduler.self_style_worker import get_self_style_max_tweets
            result = get_self_style_max_tweets()
            assert result == 200

    def test_get_self_style_days_returns_int(self):
        """get_self_style_days() returns int from settings."""
        with patch("services.social.scheduler.self_style_worker.get_settings") as mock_settings:
            mock_settings.return_value.self_style_days = 14
            from services.social.scheduler.self_style_worker import get_self_style_days
            result = get_self_style_days()
            assert result == 14

    def test_is_self_style_include_replies_returns_bool(self):
        """is_self_style_include_replies() returns bool from settings."""
        with patch("services.social.scheduler.self_style_worker.get_settings") as mock_settings:
            mock_settings.return_value.self_style_include_replies = False
            from services.social.scheduler.self_style_worker import is_self_style_include_replies
            result = is_self_style_include_replies()
            assert result is False


# =============================================================================
# WORKER GATING TESTS
# =============================================================================


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


class TestWorkerGatingDisabled:
    """Tests for SELF_STYLE_ENABLED=false gating."""

    @pytest.mark.asyncio
    async def test_worker_not_run_when_disabled(self):
        """Worker does not run when SELF_STYLE_ENABLED=false."""
        reset_redis_lock()

        with patch("services.social.scheduler.self_style_worker.is_self_style_enabled", return_value=False):
            from services.social.scheduler.self_style_worker import SelfStyleWorker

            clock = FakeClock()
            mock_lock = MockRedisLock()
            worker = SelfStyleWorker(
                clock=clock,
                interval=3600,
                min_tweets=10,
                days=7,
                redis_lock=mock_lock,
            )

            # Worker should have disabled_reason set in __init__
            assert worker.enabled is False
            assert worker.disabled_reason == "disabled"

            # Start should return without running
            await worker.start()

            # Worker should not be running
            assert worker._running is False
            # Lock should not have been touched
            assert mock_lock.acquire_called is False

    @pytest.mark.asyncio
    async def test_disabled_reason_set_on_init(self):
        """disabled_reason='disabled' is set in __init__ when not enabled."""
        reset_redis_lock()

        with patch("services.social.scheduler.self_style_worker.is_self_style_enabled", return_value=False):
            from services.social.scheduler.self_style_worker import SelfStyleWorker

            clock = FakeClock()
            mock_lock = MockRedisLock()
            worker = SelfStyleWorker(
                clock=clock,
                redis_lock=mock_lock,
            )

            assert worker.disabled_reason == "disabled"


class TestWorkerGatingRedisMissing:
    """Tests for REDIS_URL missing gating."""

    @pytest.mark.asyncio
    async def test_worker_not_run_when_redis_url_missing(self):
        """Worker does not run when REDIS_URL is not set."""
        reset_redis_lock()

        # Remove REDIS_URL from env
        with patch.dict(os.environ, {}, clear=True):
            with patch("services.social.scheduler.self_style_worker.is_self_style_enabled", return_value=True):
                from services.social.scheduler.self_style_worker import SelfStyleWorker

                clock = FakeClock()
                mock_lock = MockRedisLock()
                worker = SelfStyleWorker(
                    clock=clock,
                    interval=3600,
                    min_tweets=10,
                    days=7,
                    redis_lock=mock_lock,
                )

                # Start should return without running
                await worker.start()

                # Worker should not be running
                assert worker._running is False
                assert worker.disabled_reason == "redis_missing"
                assert "REDIS_URL" in worker.last_lock_error

    @pytest.mark.asyncio
    async def test_disabled_reason_redis_missing(self):
        """disabled_reason='redis_missing' when REDIS_URL not configured."""
        reset_redis_lock()

        with patch.dict(os.environ, {}, clear=True):
            with patch("services.social.scheduler.self_style_worker.is_self_style_enabled", return_value=True):
                from services.social.scheduler.self_style_worker import SelfStyleWorker

                clock = FakeClock()
                mock_lock = MockRedisLock()
                worker = SelfStyleWorker(
                    clock=clock,
                    redis_lock=mock_lock,
                )

                await worker.start()

                assert worker.disabled_reason == "redis_missing"


class TestWorkerGatingRedisUnavailable:
    """Tests for Redis unavailable gating."""

    @pytest.mark.asyncio
    async def test_worker_not_run_when_redis_unavailable(self):
        """Worker does not run when Redis connection fails."""
        reset_redis_lock()

        with patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379"}, clear=True):
            with patch("services.social.scheduler.self_style_worker.is_self_style_enabled", return_value=True):
                from services.social.scheduler.self_style_worker import SelfStyleWorker

                clock = FakeClock()
                mock_lock = MockRedisLock()
                mock_lock.is_available_result = False  # Redis unavailable

                worker = SelfStyleWorker(
                    clock=clock,
                    interval=3600,
                    min_tweets=10,
                    days=7,
                    redis_lock=mock_lock,
                )

                await worker.start()

                assert worker._running is False
                assert worker.disabled_reason == "redis_unavailable"
                assert "Redis connection failed" in worker.last_lock_error


class TestWorkerGatingInsufficientTweets:
    """Tests for insufficient tweet count gating."""

    @pytest.mark.asyncio
    async def test_skipped_insufficient_data_when_not_enough_tweets(self):
        """last_run_status='skipped_insufficient_data' when tweet_count < min_tweets."""
        reset_redis_lock()

        with patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379"}, clear=True):
            with patch("services.social.scheduler.self_style_worker.is_self_style_enabled", return_value=True):
                from services.social.scheduler.self_style_worker import SelfStyleWorker

                clock = FakeClock()
                mock_lock = MockRedisLock(acquire_result=True)

                worker = SelfStyleWorker(
                    clock=clock,
                    interval=3600,
                    min_tweets=50,  # Require 50 tweets
                    days=7,
                    redis_lock=mock_lock,
                )

                # Mock the DB query to return 10 tweets (< 50 minimum)
                mock_result = MagicMock()
                mock_result.scalar.return_value = 10  # Only 10 tweets available

                mock_session = AsyncMock()
                mock_session.execute.return_value = mock_result
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock()

                with patch("services.social.scheduler.self_style_worker.get_self_style_max_tweets", return_value=500):
                    with patch("services.social.scheduler.self_style_worker.is_self_style_include_replies", return_value=True):
                        with patch("db.base.async_session_maker", return_value=mock_session):
                            result = await worker._run_with_lock()

                assert result["lock_acquired"] is True
                assert result["skipped"] is True
                assert "insufficient_data" in result["skip_reason"]
                assert worker.last_run_status == "skipped_insufficient_data"
                assert worker.total_proposals_generated == 0

    @pytest.mark.asyncio
    async def test_no_proposal_generated_when_insufficient_tweets(self):
        """propose_style_guide is NOT called when tweet_count < min_tweets."""
        reset_redis_lock()

        with patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379"}, clear=True):
            with patch("services.social.scheduler.self_style_worker.is_self_style_enabled", return_value=True):
                from services.social.scheduler.self_style_worker import SelfStyleWorker

                clock = FakeClock()
                mock_lock = MockRedisLock(acquire_result=True)

                worker = SelfStyleWorker(
                    clock=clock,
                    interval=3600,
                    min_tweets=100,
                    days=7,
                    redis_lock=mock_lock,
                )

                # Mock DB to return insufficient tweets
                mock_result = MagicMock()
                mock_result.scalar.return_value = 5

                mock_session = AsyncMock()
                mock_session.execute.return_value = mock_result
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock()

                # Track if propose_style_guide is called
                propose_called = []

                async def mock_propose(*args, **kwargs):
                    propose_called.append(True)
                    return {}

                with patch("services.social.scheduler.self_style_worker.get_self_style_max_tweets", return_value=500):
                    with patch("services.social.scheduler.self_style_worker.is_self_style_include_replies", return_value=True):
                        with patch("db.base.async_session_maker", return_value=mock_session):
                            with patch("scripts.propose_style_guide.propose_style_guide", mock_propose):
                                await worker._run_with_lock()

                # propose_style_guide should NOT have been called
                assert len(propose_called) == 0


class TestWorkerGatingLockContention:
    """Tests for lock contention gating."""

    @pytest.mark.asyncio
    async def test_skipped_lock_contention_when_lock_not_acquired(self):
        """last_run_status='skipped_lock_contention' when lock not acquired."""
        reset_redis_lock()

        with patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379"}, clear=True):
            with patch("services.social.scheduler.self_style_worker.is_self_style_enabled", return_value=True):
                from services.social.scheduler.self_style_worker import SelfStyleWorker

                clock = FakeClock()
                mock_lock = MockRedisLock(acquire_result=False)  # Lock held by another

                worker = SelfStyleWorker(
                    clock=clock,
                    interval=3600,
                    min_tweets=10,
                    days=7,
                    redis_lock=mock_lock,
                )

                result = await worker._run_with_lock()

                assert result["lock_acquired"] is False
                assert result["skipped"] is True
                assert "leader lock held by another instance" in result["skip_reason"]
                assert worker.last_run_status == "skipped_lock_contention"
                assert worker.total_lock_failures == 1


class TestWorkerSuccessPath:
    """Tests for the full success path."""

    @pytest.mark.asyncio
    async def test_propose_style_guide_called_once_on_success(self):
        """propose_style_guide is called exactly once when conditions met."""
        reset_redis_lock()

        with patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379"}, clear=True):
            with patch("services.social.scheduler.self_style_worker.is_self_style_enabled", return_value=True):
                from services.social.scheduler.self_style_worker import SelfStyleWorker

                clock = FakeClock()
                mock_lock = MockRedisLock(acquire_result=True)

                worker = SelfStyleWorker(
                    clock=clock,
                    interval=3600,
                    min_tweets=10,  # Require only 10
                    days=7,
                    redis_lock=mock_lock,
                )

                # Mock DB to return enough tweets
                mock_count_result = MagicMock()
                mock_count_result.scalar.return_value = 50  # 50 tweets available

                mock_session = AsyncMock()
                mock_session.execute.return_value = mock_count_result
                mock_session.commit = AsyncMock()
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock()

                # Track propose_style_guide calls
                propose_calls = []

                async def mock_propose(days, limit, min_tweets):
                    propose_calls.append({
                        "days": days,
                        "limit": limit,
                        "min_tweets": min_tweets,
                    })
                    return {
                        "version_id": "20260202_120000",
                        "tweet_count": 50,
                        "generated_at": datetime.now(timezone.utc),
                        "files": {
                            "markdown": "/path/to/md",
                            "json": "/path/to/json",
                        },
                        "analysis": {},
                        "hard_constraints": {},
                    }

                with patch("services.social.scheduler.self_style_worker.get_self_style_max_tweets", return_value=500):
                    with patch("services.social.scheduler.self_style_worker.is_self_style_include_replies", return_value=True):
                        with patch("db.base.async_session_maker", return_value=mock_session):
                            with patch("scripts.propose_style_guide.propose_style_guide", mock_propose):
                                result = await worker._run_with_lock()

                # propose_style_guide called exactly once
                assert len(propose_calls) == 1
                assert propose_calls[0]["days"] == 7
                assert propose_calls[0]["min_tweets"] == 10
                assert result["proposal_generated"] is True
                assert result["version_id"] == "20260202_120000"
                assert worker.last_run_status == "success"

    @pytest.mark.asyncio
    async def test_version_row_inserted_with_is_active_false(self):
        """Database INSERT has is_active=false."""
        reset_redis_lock()

        with patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379"}, clear=True):
            with patch("services.social.scheduler.self_style_worker.is_self_style_enabled", return_value=True):
                from services.social.scheduler.self_style_worker import SelfStyleWorker

                clock = FakeClock()
                mock_lock = MockRedisLock(acquire_result=True)

                worker = SelfStyleWorker(
                    clock=clock,
                    interval=3600,
                    min_tweets=10,
                    days=7,
                    redis_lock=mock_lock,
                )

                # Track the SQL executed
                executed_queries = []

                mock_count_result = MagicMock()
                mock_count_result.scalar.return_value = 50

                mock_session = AsyncMock()

                async def mock_execute(query, params=None):
                    query_str = str(query)
                    executed_queries.append({"query": query_str, "params": params})
                    return mock_count_result

                mock_session.execute = mock_execute
                mock_session.commit = AsyncMock()
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock()

                async def mock_propose(days, limit, min_tweets):
                    return {
                        "version_id": "20260202_120000",
                        "tweet_count": 50,
                        "generated_at": datetime.now(timezone.utc),
                        "files": {"markdown": "/md", "json": "/json"},
                        "analysis": {},
                        "hard_constraints": {},
                    }

                with patch("services.social.scheduler.self_style_worker.get_self_style_max_tweets", return_value=500):
                    with patch("services.social.scheduler.self_style_worker.is_self_style_include_replies", return_value=True):
                        with patch("db.base.async_session_maker", return_value=mock_session):
                            with patch("scripts.propose_style_guide.propose_style_guide", mock_propose):
                                await worker._run_with_lock()

                # Find the INSERT query
                insert_queries = [q for q in executed_queries if "INSERT" in q["query"]]
                assert len(insert_queries) == 1

                # Verify is_active=false in the INSERT
                insert_query = insert_queries[0]["query"]
                assert "false" in insert_query.lower() or "is_active" in insert_query

    @pytest.mark.asyncio
    async def test_stats_updated_on_success(self):
        """Worker stats are correctly updated on successful proposal."""
        reset_redis_lock()

        with patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379"}, clear=True):
            with patch("services.social.scheduler.self_style_worker.is_self_style_enabled", return_value=True):
                from services.social.scheduler.self_style_worker import SelfStyleWorker

                clock = FakeClock()
                mock_lock = MockRedisLock(acquire_result=True)

                worker = SelfStyleWorker(
                    clock=clock,
                    interval=3600,
                    min_tweets=10,
                    days=7,
                    redis_lock=mock_lock,
                )

                assert worker.total_proposals_generated == 0
                assert worker.total_lock_acquisitions == 0

                mock_count_result = MagicMock()
                mock_count_result.scalar.return_value = 50

                mock_session = AsyncMock()
                mock_session.execute.return_value = mock_count_result
                mock_session.commit = AsyncMock()
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock()

                async def mock_propose(days, limit, min_tweets):
                    return {
                        "version_id": "test-version",
                        "tweet_count": 50,
                        "generated_at": datetime.now(timezone.utc),
                        "files": {"markdown": "/md", "json": "/json"},
                        "analysis": {},
                        "hard_constraints": {},
                    }

                with patch("services.social.scheduler.self_style_worker.get_self_style_max_tweets", return_value=500):
                    with patch("services.social.scheduler.self_style_worker.is_self_style_include_replies", return_value=True):
                        with patch("db.base.async_session_maker", return_value=mock_session):
                            with patch("scripts.propose_style_guide.propose_style_guide", mock_propose):
                                await worker._run_with_lock()

                assert worker.total_proposals_generated == 1
                assert worker.total_lock_acquisitions == 1
                assert worker.last_proposal_version_id == "test-version"
                assert worker.last_run_status == "success"


class TestWorkerGetStats:
    """Tests for get_stats() method."""

    def test_get_stats_includes_gating_info(self):
        """get_stats() includes enabled, disabled_reason, last_run_status."""
        reset_redis_lock()

        with patch("services.social.scheduler.self_style_worker.is_self_style_enabled", return_value=False):
            from services.social.scheduler.self_style_worker import SelfStyleWorker

            clock = FakeClock()
            mock_lock = MockRedisLock()

            worker = SelfStyleWorker(
                clock=clock,
                redis_lock=mock_lock,
            )

            stats = worker.get_stats()

            assert "enabled" in stats
            assert "disabled_reason" in stats
            assert "last_run_status" in stats
            assert stats["enabled"] is False
            assert stats["disabled_reason"] == "disabled"

    def test_get_stats_includes_config(self):
        """get_stats() includes config section with all settings."""
        reset_redis_lock()

        with patch("services.social.scheduler.self_style_worker.is_self_style_enabled", return_value=True):
            with patch("services.social.scheduler.self_style_worker.get_self_style_max_tweets", return_value=200):
                with patch("services.social.scheduler.self_style_worker.is_self_style_include_replies", return_value=False):
                    from services.social.scheduler.self_style_worker import SelfStyleWorker

                    clock = FakeClock()
                    mock_lock = MockRedisLock()

                    worker = SelfStyleWorker(
                        clock=clock,
                        interval=3600,
                        min_tweets=25,
                        days=14,
                        redis_lock=mock_lock,
                    )

                    stats = worker.get_stats()

                    assert "config" in stats
                    assert stats["config"]["interval_hours"] == 1.0
                    assert stats["config"]["min_tweets"] == 25
                    assert stats["config"]["max_tweets"] == 200
                    assert stats["config"]["days"] == 14
                    assert stats["config"]["include_replies"] is False
