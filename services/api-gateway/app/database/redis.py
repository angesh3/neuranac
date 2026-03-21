"""Redis connection management with graceful degradation.

When Redis is unavailable the gateway continues to operate — features that
depend on Redis (rate-limiting, token blocklist, caching) degrade silently
rather than crashing the service.
"""
from typing import Optional
import redis.asyncio as aioredis
import structlog
from app.config import get_settings

logger = structlog.get_logger()
redis_client: Optional[aioredis.Redis] = None
_redis_available: bool = False


async def init_redis():
    """Connect to Redis.  On failure, log a warning and continue without Redis."""
    global redis_client, _redis_available
    settings = get_settings()
    try:
        redis_client = aioredis.from_url(
            settings.redis_url, decode_responses=True, max_connections=50
        )
        await redis_client.ping()
        _redis_available = True
        logger.info("Redis connected", host=settings.redis_host)
    except Exception as exc:
        _redis_available = False
        redis_client = None
        logger.warning("Redis unavailable — running in degraded mode", error=str(exc))


async def close_redis():
    global redis_client, _redis_available
    if redis_client:
        try:
            await redis_client.close()
        except Exception:
            pass
        logger.info("Redis connection closed")
    redis_client = None
    _redis_available = False


def get_redis() -> Optional[aioredis.Redis]:
    """Return the Redis client, or ``None`` when Redis is unavailable."""
    return redis_client if _redis_available else None


def is_redis_available() -> bool:
    return _redis_available


async def safe_redis_op(coro, default=None):
    """Execute a Redis coroutine, returning *default* on any error."""
    try:
        if not _redis_available:
            return default
        return await coro
    except Exception as exc:
        logger.debug("Redis op failed (degraded)", error=str(exc))
        return default
