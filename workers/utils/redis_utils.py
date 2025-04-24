"""
Redis utilities for caching and messaging
"""
import redis.asyncio as redis
import structlog
from typing import Optional, Dict, Any, Union

from config.settings import Settings

logger = structlog.get_logger(__name__)
settings = Settings()

# Global Redis connection
_redis_client: Optional[redis.Redis] = None

async def get_redis_client() -> redis.Redis:
    """Get or create a Redis client connection"""
    global _redis_client
    
    if _redis_client is None or not _redis_client.ping():
        logger.info("Creating Redis client connection")
        
        _redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            db=settings.redis_db,
            decode_responses=True
        )
        
        # Test connection
        ping_result = await _redis_client.ping()
        logger.info("Redis client connection created", ping_result=ping_result)
    
    return _redis_client

async def close_redis_client() -> None:
    """Close the Redis client connection"""
    global _redis_client
    
    if _redis_client:
        logger.info("Closing Redis client connection")
        await _redis_client.close()
        _redis_client = None

async def set_cache(key: str, value: Union[str, Dict[str, Any]], expire_seconds: Optional[int] = None) -> bool:
    """Set a value in Redis cache with optional expiration"""
    client = await get_redis_client()
    
    try:
        if isinstance(value, dict):
            result = await client.hset(key, mapping=value)
        else:
            result = await client.set(key, value)
        
        if expire_seconds:
            await client.expire(key, expire_seconds)
            
        logger.debug("Set value in Redis cache", key=key, expire_seconds=expire_seconds)
        return bool(result)
    except Exception as e:
        logger.error("Failed to set value in Redis cache", key=key, error=str(e))
        return False

async def get_cache(key: str, is_hash: bool = False) -> Optional[Union[str, Dict[str, str]]]:
    """Get a value from Redis cache"""
    client = await get_redis_client()
    
    try:
        if is_hash:
            result = await client.hgetall(key)
        else:
            result = await client.get(key)
            
        if result:
            logger.debug("Retrieved value from Redis cache", key=key)
        else:
            logger.debug("Cache miss", key=key)
            
        return result
    except Exception as e:
        logger.error("Failed to get value from Redis cache", key=key, error=str(e))
        return None

async def delete_cache(key: str) -> bool:
    """Delete a value from Redis cache"""
    client = await get_redis_client()
    
    try:
        result = await client.delete(key)
        logger.debug("Deleted value from Redis cache", key=key)
        return bool(result)
    except Exception as e:
        logger.error("Failed to delete value from Redis cache", key=key, error=str(e))
        return False

async def publish_message(channel: str, message: str) -> int:
    """Publish a message to a Redis channel"""
    client = await get_redis_client()
    
    try:
        result = await client.publish(channel, message)
        logger.debug("Published message to Redis channel", channel=channel, recipients=result)
        return result
    except Exception as e:
        logger.error("Failed to publish message to Redis channel", channel=channel, error=str(e))
        return 0 