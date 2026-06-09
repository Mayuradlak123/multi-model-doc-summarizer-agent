import redis
import redis.asyncio as async_redis
from .logger import logger
from .settings import settings

def get_redis_client():
    try:
        client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            decode_responses=True
        )
        # Test connection
        client.ping()
        logger.info("Successfully connected to Redis")
        return client
    except Exception as e:
        logger.warning(f"Failed to connect to Redis server: {str(e)}. Continuing without Redis cache.")
        return None

def get_async_redis_client():
    try:
        client = async_redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            decode_responses=True
        )
        return client
    except Exception as e:
        logger.warning(f"Failed to connect to Async Redis: {str(e)}. Continuing without Async Redis cache.")
        return None

redis_client = get_redis_client()
async_redis_client = get_async_redis_client()
