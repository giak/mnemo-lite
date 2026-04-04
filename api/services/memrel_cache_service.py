"""
Memory Relationship Cache Service — Redis caching for relationship queries.

Caches:
- Related memories: memrel:{id}:d{depth} (TTL 5 min)
- Graph data: memgraph:min{score} (TTL 10 min)

Invalidation:
- When relationships are computed for a memory, invalidate its cache
"""

import json
from typing import Optional, List, Dict, Any

import structlog

logger = structlog.get_logger()


class MemRelCacheService:
    """Redis cache for memory relationship queries."""

    def __init__(self, redis_client=None):
        self.redis = redis_client

    async def get_related(self, memory_id: str, max_depth: int) -> Optional[List[Dict[str, Any]]]:
        """Get cached related memories."""
        if not self.redis:
            return None
        
        key = f"memrel:{memory_id}:d{max_depth}"
        try:
            data = await self.redis.get(key)
            if data:
                logger.debug("memrel_cache_hit", key=key)
                return json.loads(data)
            logger.debug("memrel_cache_miss", key=key)
            return None
        except Exception as e:
            logger.warning("memrel_cache_get_error", error=str(e))
            return None

    async def set_related(self, memory_id: str, max_depth: int, data: List[Dict[str, Any]], ttl: int = 300) -> None:
        """Cache related memories."""
        if not self.redis:
            return
        
        key = f"memrel:{memory_id}:d{max_depth}"
        try:
            await self.redis.setex(key, ttl, json.dumps(data))
            logger.debug("memrel_cache_set", key=key, ttl=ttl)
        except Exception as e:
            logger.warning("memrel_cache_set_error", error=str(e))

    async def get_graph(self, min_score: float) -> Optional[Dict[str, Any]]:
        """Get cached graph data."""
        if not self.redis:
            return None
        
        key = f"memgraph:min{min_score}"
        try:
            data = await self.redis.get(key)
            if data:
                logger.debug("memrel_graph_cache_hit", key=key)
                return json.loads(data)
            logger.debug("memrel_graph_cache_miss", key=key)
            return None
        except Exception as e:
            logger.warning("memrel_graph_cache_get_error", error=str(e))
            return None

    async def set_graph(self, min_score: float, data: Dict[str, Any], ttl: int = 600) -> None:
        """Cache graph data."""
        if not self.redis:
            return
        
        key = f"memgraph:min{min_score}"
        try:
            await self.redis.setex(key, ttl, json.dumps(data))
            logger.debug("memrel_graph_cache_set", key=key, ttl=ttl)
        except Exception as e:
            logger.warning("memrel_graph_cache_set_error", error=str(e))

    async def invalidate_memory(self, memory_id: str) -> None:
        """Invalidate all caches for a specific memory."""
        if not self.redis:
            return
        
        try:
            # Invalidate related memories caches (depth 1-3)
            for depth in range(1, 4):
                key = f"memrel:{memory_id}:d{depth}"
                await self.redis.delete(key)
            
            # Invalidate graph caches (common thresholds)
            for score in [0.1, 0.2, 0.3, 0.5]:
                key = f"memgraph:min{score}"
                await self.redis.delete(key)
                
            logger.debug("memrel_cache_invalidated", memory_id=memory_id)
        except Exception as e:
            logger.warning("memrel_cache_invalidate_error", error=str(e))
