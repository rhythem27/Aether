from typing import Optional
from redis.asyncio import Redis, from_url
from backend.core.config import settings
from backend.core.logging import logger

_redis_client: Optional[Redis] = None


def get_redis_client() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


async def close_redis_client():
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None


async def check_redis_health() -> bool:
    try:
        client = get_redis_client()
        return await client.ping()
    except Exception as e:
        logger.error("redis_health_check_failed", error=str(e))
        return False
