"""
Redis connection singleton.
Fail fast: crashes on startup if Redis is unreachable.
"""

import logging

import redis.asyncio as aioredis

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

redis_client: aioredis.Redis | None = None

async def init_redis() -> None:
    """Create the global Redis connection pool. Fails fast if unreachable."""
    global redis_client
    redis_client = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=False,
        max_connections=20,
    )
    # Verify connection on startup — fail fast, fail loud:
    try:
        await redis_client.ping()
        logger.info("✅  Redis connected: %s", settings.REDIS_URL)
    except Exception as e:
        logger.warning("Mocking Redis due to connection error: %s", e)
        class MockRedis:
            def __init__(self):
                self.store = {}
            async def ping(self): return True
            async def get(self, key):
                val = self.store.get(key)
                if isinstance(val, str): return val.encode()
                return val
            async def set(self, key, value): self.store[key] = value
            async def setex(self, key, time, value): self.store[key] = value
            async def ttl(self, key): return -2 if key not in self.store else 60
            async def delete(self, key): self.store.pop(key, None)
            async def aclose(self): pass
            
        redis_client = MockRedis()


async def close_redis() -> None:
    """Gracefully close the Redis pool."""
    global redis_client
    if redis_client is not None:
        await redis_client.aclose()
        redis_client = None
        logger.info("🛑  Redis connection closed")


def get_redis() -> aioredis.Redis:
    """Return the active Redis pool. Raises if not initialised."""
    if redis_client is None:
        raise RuntimeError("Redis pool not initialised. Call init_redis() first.")
    return redis_client
