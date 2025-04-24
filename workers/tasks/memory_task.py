"""
Memory search task handler
"""
import json
import structlog
from typing import Dict, Any, List

from utils.chromadb import query_embeddings, get_collection
from utils.redis_utils import set_cache, publish_message
from config.settings import Settings

logger = structlog.get_logger(__name__)
settings = Settings()

class TaskHandler:
    def __init__(self):
        pass
    
    async def process(self, content: Dict[str, Any]) -> bool:
        """Process a memory search task"""
        try:
            task_id = content.get("id")
            logger.info("processing_memory_search_task", task_id=task_id)
            
            # Extract data from the content
            query_embedding = content.get("query_embedding")
            n_results = content.get("n_results", 5)
            collection_name = content.get("collection", "mnemo_collection")
            
            if not query_embedding:
                logger.error("invalid_memory_task", task_id=task_id, reason="missing query embedding")
                return False
            
            # Query ChromaDB
            results = await query_embeddings(
                query_embedding=query_embedding,
                n_results=n_results,
                collection_name=collection_name
            )
            
            # Cache results in Redis
            cache_key = f"memory_results:{task_id}"
            await set_cache(cache_key, json.dumps(results), expire_seconds=3600)
            
            # Notify via Redis that query is complete
            await publish_message(
                "memory_search_complete", 
                json.dumps({
                    "task_id": task_id, 
                    "cache_key": cache_key,
                    "count": len(results.get("ids", [])[0]) if results.get("ids") else 0
                })
            )
            
            logger.info(
                "memory_search_completed", 
                task_id=task_id, 
                results_count=len(results.get("ids", [])[0]) if results.get("ids") else 0
            )
            return True
            
        except Exception as e:
            logger.error("memory_search_error", error=str(e))
            # Notify of failure via Redis
            if content and content.get("id"):
                await publish_message(
                    "memory_search_complete", 
                    json.dumps({"task_id": content.get("id"), "success": False, "error": str(e)})
                )
            return False 