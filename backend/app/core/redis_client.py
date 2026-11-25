import redis.asyncio as redis

from app.core.config import get_settings

settings = get_settings()

redis_pool: redis.ConnectionPool | None = None
redis_client: redis.Redis | None = None


async def init_redis(test_client: redis.Redis | None = None) -> None:
    global redis_pool, redis_client
    if test_client is not None:
        redis_client = test_client
    else:
        redis_pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
        )
        redis_client = redis.Redis(connection_pool=redis_pool)
        await redis_client.ping()


async def close_redis() -> None:
    global redis_client, redis_pool
    if redis_client:
        await redis_client.close()
    if redis_pool:
        await redis_pool.disconnect()
    redis_client = None
    redis_pool = None


def get_redis() -> redis.Redis:
    if redis_client is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return redis_client
