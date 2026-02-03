"""
Jeffrey AIstein - Redis Lock Tests

Unit tests for the distributed lock implementation.
Uses mocks instead of real Redis for fast, deterministic tests.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.locking.redis_lock import RedisLock, reset_redis_lock


class TestRedisLockAcquire:
    """Tests for lock acquisition."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        client = AsyncMock()
        client.ping = AsyncMock(return_value=True)
        client.set = AsyncMock(return_value=True)
        client.get = AsyncMock(return_value=None)
        client.close = AsyncMock()
        # Mock script registration
        client.register_script = MagicMock(return_value=AsyncMock())
        return client

    @pytest.fixture
    def lock_with_mock(self, mock_redis):
        """Create a RedisLock with mocked client."""
        reset_redis_lock()
        lock = RedisLock(redis_url="redis://fake:6379", instance_id="test-instance-1")
        lock._client = mock_redis
        lock._renew_script = AsyncMock()
        lock._release_script = AsyncMock()
        return lock

    @pytest.mark.asyncio
    async def test_acquire_succeeds_when_lock_absent(self, lock_with_mock, mock_redis):
        """Acquire succeeds when no one holds the lock."""
        # SET NX returns True when key doesn't exist
        mock_redis.set.return_value = True

        acquired = await lock_with_mock.acquire("test:lock", ttl_seconds=60)

        assert acquired is True
        mock_redis.set.assert_called_once_with(
            "test:lock",
            "test-instance-1",
            nx=True,
            ex=60,
        )

    @pytest.mark.asyncio
    async def test_acquire_fails_when_lock_held(self, lock_with_mock, mock_redis):
        """Acquire fails when another instance holds the lock."""
        # SET NX returns None/False when key already exists
        mock_redis.set.return_value = None

        acquired = await lock_with_mock.acquire("test:lock", ttl_seconds=60)

        assert acquired is False

    @pytest.mark.asyncio
    async def test_acquire_fails_on_redis_error(self, lock_with_mock, mock_redis):
        """Acquire returns False on Redis connection error."""
        mock_redis.set.side_effect = Exception("Connection refused")

        acquired = await lock_with_mock.acquire("test:lock", ttl_seconds=60)

        assert acquired is False

    @pytest.mark.asyncio
    async def test_acquire_fails_when_no_client(self):
        """Acquire fails gracefully when Redis URL not configured."""
        reset_redis_lock()
        lock = RedisLock(redis_url=None)

        acquired = await lock.acquire("test:lock", ttl_seconds=60)

        assert acquired is False


class TestRedisLockRenew:
    """Tests for lock renewal."""

    @pytest.fixture
    def lock_with_mock(self):
        """Create a RedisLock with mocked scripts."""
        reset_redis_lock()
        lock = RedisLock(redis_url="redis://fake:6379", instance_id="test-instance-1")
        lock._client = AsyncMock()
        lock._renew_script = AsyncMock()
        lock._release_script = AsyncMock()
        return lock

    @pytest.mark.asyncio
    async def test_renew_succeeds_when_token_matches(self, lock_with_mock):
        """Renew succeeds when we hold the lock (token matches)."""
        # Lua script returns 1 on success
        lock_with_mock._renew_script.return_value = 1

        renewed = await lock_with_mock.renew("test:lock", ttl_seconds=120)

        assert renewed is True
        lock_with_mock._renew_script.assert_called_once_with(
            keys=["test:lock"],
            args=["test-instance-1", 120],
        )

    @pytest.mark.asyncio
    async def test_renew_fails_when_token_mismatch(self, lock_with_mock):
        """Renew fails when another instance holds the lock."""
        # Lua script returns 0 when token doesn't match
        lock_with_mock._renew_script.return_value = 0

        renewed = await lock_with_mock.renew("test:lock", ttl_seconds=120)

        assert renewed is False

    @pytest.mark.asyncio
    async def test_renew_fails_on_redis_error(self, lock_with_mock):
        """Renew returns False on Redis error."""
        lock_with_mock._renew_script.side_effect = Exception("Connection lost")

        renewed = await lock_with_mock.renew("test:lock", ttl_seconds=120)

        assert renewed is False

    @pytest.mark.asyncio
    async def test_renew_fails_when_no_script(self):
        """Renew fails gracefully when not connected."""
        reset_redis_lock()
        lock = RedisLock(redis_url=None)

        renewed = await lock.renew("test:lock", ttl_seconds=120)

        assert renewed is False


class TestRedisLockRelease:
    """Tests for lock release."""

    @pytest.fixture
    def lock_with_mock(self):
        """Create a RedisLock with mocked scripts."""
        reset_redis_lock()
        lock = RedisLock(redis_url="redis://fake:6379", instance_id="test-instance-1")
        lock._client = AsyncMock()
        lock._renew_script = AsyncMock()
        lock._release_script = AsyncMock()
        return lock

    @pytest.mark.asyncio
    async def test_release_succeeds_when_token_matches(self, lock_with_mock):
        """Release succeeds when we hold the lock."""
        # Lua script returns 1 on successful delete
        lock_with_mock._release_script.return_value = 1

        released = await lock_with_mock.release("test:lock")

        assert released is True
        lock_with_mock._release_script.assert_called_once_with(
            keys=["test:lock"],
            args=["test-instance-1"],
        )

    @pytest.mark.asyncio
    async def test_release_fails_when_token_mismatch(self, lock_with_mock):
        """Release does nothing when another instance holds the lock."""
        # Lua script returns 0 when token doesn't match
        lock_with_mock._release_script.return_value = 0

        released = await lock_with_mock.release("test:lock")

        assert released is False

    @pytest.mark.asyncio
    async def test_release_does_not_delete_others_lock(self, lock_with_mock):
        """Verify release only deletes our own lock via token check."""
        # Simulate: lock held by "other-instance"
        # Our release should fail because Lua script checks token
        lock_with_mock._release_script.return_value = 0

        # Even though we call release, it should not delete
        released = await lock_with_mock.release("test:lock")

        assert released is False
        # Script was called but returned 0 (no delete happened)
        lock_with_mock._release_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_release_fails_on_redis_error(self, lock_with_mock):
        """Release returns False on Redis error."""
        lock_with_mock._release_script.side_effect = Exception("Network error")

        released = await lock_with_mock.release("test:lock")

        assert released is False


class TestRedisLockAvailability:
    """Tests for Redis availability checking."""

    @pytest.mark.asyncio
    async def test_is_available_true_when_ping_succeeds(self):
        """is_available returns True when Redis ping succeeds."""
        reset_redis_lock()
        lock = RedisLock(redis_url="redis://fake:6379")

        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)
        mock_client.register_script = MagicMock(return_value=AsyncMock())

        with patch("services.locking.redis_lock.aioredis") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_client

            available = await lock.is_available()

            assert available is True

    @pytest.mark.asyncio
    async def test_is_available_false_when_no_url(self):
        """is_available returns False when no Redis URL configured."""
        reset_redis_lock()
        lock = RedisLock(redis_url=None)

        available = await lock.is_available()

        assert available is False

    @pytest.mark.asyncio
    async def test_is_available_false_when_ping_fails(self):
        """is_available returns False when Redis ping fails."""
        reset_redis_lock()
        lock = RedisLock(redis_url="redis://fake:6379")

        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.register_script = MagicMock(return_value=AsyncMock())

        with patch("services.locking.redis_lock.aioredis") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_client

            available = await lock.is_available()

            assert available is False


class TestRedisLockContention:
    """Tests simulating lock contention between instances."""

    @pytest.mark.asyncio
    async def test_two_instances_contend_for_lock(self):
        """Second instance fails to acquire when first holds lock."""
        reset_redis_lock()

        # Simulate shared Redis state
        lock_state = {"holder": None}

        def mock_set(key, value, nx=False, ex=None):
            if nx and lock_state["holder"] is not None:
                return None  # Lock already held
            lock_state["holder"] = value
            return True

        async def mock_set_async(key, value, nx=False, ex=None):
            return mock_set(key, value, nx=nx, ex=ex)

        # Instance 1
        lock1 = RedisLock(redis_url="redis://fake:6379", instance_id="instance-1")
        lock1._client = AsyncMock()
        lock1._client.set = mock_set_async
        lock1._release_script = AsyncMock(return_value=1)
        lock1._renew_script = AsyncMock()

        # Instance 2
        lock2 = RedisLock(redis_url="redis://fake:6379", instance_id="instance-2")
        lock2._client = AsyncMock()
        lock2._client.set = mock_set_async
        lock2._release_script = AsyncMock(return_value=1)
        lock2._renew_script = AsyncMock()

        # Instance 1 acquires lock
        acquired1 = await lock1.acquire("shared:lock", ttl_seconds=60)
        assert acquired1 is True
        assert lock_state["holder"] == "instance-1"

        # Instance 2 fails to acquire (lock held)
        acquired2 = await lock2.acquire("shared:lock", ttl_seconds=60)
        assert acquired2 is False
        assert lock_state["holder"] == "instance-1"  # Unchanged

    @pytest.mark.asyncio
    async def test_instance_can_acquire_after_release(self):
        """Instance can acquire lock after previous holder releases."""
        reset_redis_lock()

        # Simulate shared Redis state
        lock_state = {"holder": None}

        async def mock_set(key, value, nx=False, ex=None):
            if nx and lock_state["holder"] is not None:
                return None
            lock_state["holder"] = value
            return True

        def mock_release_script(keys, args):
            token = args[0]
            if lock_state["holder"] == token:
                lock_state["holder"] = None
                return 1
            return 0

        # Instance 1
        lock1 = RedisLock(redis_url="redis://fake:6379", instance_id="instance-1")
        lock1._client = AsyncMock()
        lock1._client.set = mock_set
        lock1._release_script = AsyncMock(side_effect=lambda keys, args: mock_release_script(keys, args))
        lock1._renew_script = AsyncMock()

        # Instance 2
        lock2 = RedisLock(redis_url="redis://fake:6379", instance_id="instance-2")
        lock2._client = AsyncMock()
        lock2._client.set = mock_set
        lock2._release_script = AsyncMock()
        lock2._renew_script = AsyncMock()

        # Instance 1 acquires and releases
        await lock1.acquire("shared:lock", ttl_seconds=60)
        await lock1.release("shared:lock")
        assert lock_state["holder"] is None

        # Instance 2 can now acquire
        acquired2 = await lock2.acquire("shared:lock", ttl_seconds=60)
        assert acquired2 is True
        assert lock_state["holder"] == "instance-2"
