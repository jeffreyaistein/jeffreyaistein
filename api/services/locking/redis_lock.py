"""
Jeffrey AIstein - Redis Distributed Lock

Provides a distributed lock using Redis for leader election.
Uses atomic operations to ensure exactly one holder at a time.

Key features:
- SET NX EX for atomic acquire
- Lua scripts for atomic renew/release with token verification
- Unique instance_id prevents accidental release of another instance's lock
"""

import os
import uuid
from typing import Optional

import redis.asyncio as aioredis
import structlog

logger = structlog.get_logger(__name__)


# Lua script for atomic renew: only extend TTL if we own the lock
# KEYS[1] = lock key
# ARGV[1] = our token
# ARGV[2] = new TTL in seconds
# Returns: 1 if renewed, 0 if not owner or lock doesn't exist
RENEW_SCRIPT = """
local current = redis.call('GET', KEYS[1])
if current == ARGV[1] then
    redis.call('EXPIRE', KEYS[1], ARGV[2])
    return 1
else
    return 0
end
"""

# Lua script for atomic release: only delete if we own the lock
# KEYS[1] = lock key
# ARGV[1] = our token
# Returns: 1 if released, 0 if not owner or lock doesn't exist
RELEASE_SCRIPT = """
local current = redis.call('GET', KEYS[1])
if current == ARGV[1] then
    redis.call('DEL', KEYS[1])
    return 1
else
    return 0
end
"""


class RedisLock:
    """
    Distributed lock using Redis.

    Uses a unique instance_id (token) to ensure only the lock holder
    can renew or release the lock.

    Usage:
        lock = RedisLock(redis_url)

        # Acquire lock
        if await lock.acquire("my_lock", ttl_seconds=120):
            try:
                # Do work...
                # Optionally renew if work takes longer
                await lock.renew("my_lock", ttl_seconds=120)
            finally:
                await lock.release("my_lock")
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        instance_id: Optional[str] = None,
    ):
        """
        Initialize the Redis lock.

        Args:
            redis_url: Redis connection URL. Defaults to REDIS_URL env var.
            instance_id: Unique identifier for this instance. Defaults to UUID.
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL")
        self.instance_id = instance_id or str(uuid.uuid4())
        self._client: Optional[aioredis.Redis] = None
        self._renew_script: Optional[aioredis.client.Script] = None
        self._release_script: Optional[aioredis.client.Script] = None

    async def _get_client(self) -> Optional[aioredis.Redis]:
        """Get or create Redis client."""
        if not self.redis_url:
            return None

        if self._client is None:
            try:
                self._client = aioredis.from_url(
                    self.redis_url,
                    decode_responses=True,
                )
                # Register Lua scripts
                self._renew_script = self._client.register_script(RENEW_SCRIPT)
                self._release_script = self._client.register_script(RELEASE_SCRIPT)
            except Exception as e:
                logger.error("redis_lock_connection_failed", error=str(e))
                return None

        return self._client

    async def is_available(self) -> bool:
        """Check if Redis is available for locking."""
        if not self.redis_url:
            return False

        try:
            client = await self._get_client()
            if client:
                await client.ping()
                return True
        except Exception as e:
            logger.warning("redis_lock_not_available", error=str(e))

        return False

    async def acquire(self, lock_key: str, ttl_seconds: int = 120) -> bool:
        """
        Attempt to acquire the lock.

        Uses SET NX EX for atomic acquire:
        - NX: Only set if key does not exist
        - EX: Set expiry in seconds

        Args:
            lock_key: The key to lock
            ttl_seconds: Lock time-to-live in seconds

        Returns:
            True if lock acquired, False otherwise
        """
        client = await self._get_client()
        if not client:
            logger.warning(
                "redis_lock_acquire_no_client",
                lock_key=lock_key,
            )
            return False

        try:
            # SET key value NX EX ttl
            # NX = only set if not exists
            # EX = expire in seconds
            result = await client.set(
                lock_key,
                self.instance_id,
                nx=True,
                ex=ttl_seconds,
            )

            acquired = result is True

            logger.info(
                "redis_lock_acquire_attempt",
                lock_key=lock_key,
                acquired=acquired,
                instance_id=self.instance_id,
                ttl_seconds=ttl_seconds,
            )

            return acquired

        except Exception as e:
            logger.error(
                "redis_lock_acquire_error",
                lock_key=lock_key,
                error=str(e),
            )
            return False

    async def renew(self, lock_key: str, ttl_seconds: int = 120) -> bool:
        """
        Renew the lock TTL.

        Only succeeds if we currently hold the lock (token matches).
        Uses Lua script for atomic check-and-extend.

        Args:
            lock_key: The key to renew
            ttl_seconds: New TTL in seconds

        Returns:
            True if renewed, False if not owner or error
        """
        client = await self._get_client()
        if not client or not self._renew_script:
            logger.warning(
                "redis_lock_renew_no_client",
                lock_key=lock_key,
            )
            return False

        try:
            result = await self._renew_script(
                keys=[lock_key],
                args=[self.instance_id, ttl_seconds],
            )

            renewed = result == 1

            if renewed:
                logger.debug(
                    "redis_lock_renewed",
                    lock_key=lock_key,
                    instance_id=self.instance_id,
                    ttl_seconds=ttl_seconds,
                )
            else:
                logger.warning(
                    "redis_lock_renew_failed_not_owner",
                    lock_key=lock_key,
                    instance_id=self.instance_id,
                )

            return renewed

        except Exception as e:
            logger.error(
                "redis_lock_renew_error",
                lock_key=lock_key,
                error=str(e),
            )
            return False

    async def release(self, lock_key: str) -> bool:
        """
        Release the lock.

        Only succeeds if we currently hold the lock (token matches).
        Uses Lua script for atomic check-and-delete.

        Args:
            lock_key: The key to release

        Returns:
            True if released, False if not owner or error
        """
        client = await self._get_client()
        if not client or not self._release_script:
            logger.warning(
                "redis_lock_release_no_client",
                lock_key=lock_key,
            )
            return False

        try:
            result = await self._release_script(
                keys=[lock_key],
                args=[self.instance_id],
            )

            released = result == 1

            if released:
                logger.info(
                    "redis_lock_released",
                    lock_key=lock_key,
                    instance_id=self.instance_id,
                )
            else:
                logger.warning(
                    "redis_lock_release_failed_not_owner",
                    lock_key=lock_key,
                    instance_id=self.instance_id,
                )

            return released

        except Exception as e:
            logger.error(
                "redis_lock_release_error",
                lock_key=lock_key,
                error=str(e),
            )
            return False

    async def get_lock_holder(self, lock_key: str) -> Optional[str]:
        """
        Get the current lock holder's instance_id.

        Useful for debugging and status checks.

        Args:
            lock_key: The key to check

        Returns:
            The instance_id holding the lock, or None if unlocked
        """
        client = await self._get_client()
        if not client:
            return None

        try:
            return await client.get(lock_key)
        except Exception as e:
            logger.error(
                "redis_lock_get_holder_error",
                lock_key=lock_key,
                error=str(e),
            )
            return None

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
            self._renew_script = None
            self._release_script = None


# Module-level singleton
_redis_lock: Optional[RedisLock] = None


def get_redis_lock() -> RedisLock:
    """
    Get the singleton RedisLock instance.

    Returns:
        The shared RedisLock instance
    """
    global _redis_lock
    if _redis_lock is None:
        _redis_lock = RedisLock()
    return _redis_lock


def reset_redis_lock() -> None:
    """Reset the singleton (for testing)."""
    global _redis_lock
    _redis_lock = None
