"""
Consolidation MCP Tools — Tools for suggesting and performing memory consolidation.
"""
from typing import Dict, Any, List, Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncEngine

logger = structlog.get_logger()


class SuggestConsolidationTool:
    """MCP tool to suggest groups of similar memories for consolidation."""

    def __init__(self, engine: AsyncEngine, redis_client=None):
        self.engine = engine
        self.redis = redis_client

    async def execute(
        self,
        min_shared_entities: int = 2,
        min_shared_concepts: int = 1,
        memory_types: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        max_age_days: int = 30,
        min_group_size: int = 3,
        max_groups: int = 5,
        similarity_threshold: float = 0.3,
    ) -> Dict[str, Any]:
        """
        Suggest groups of similar memories for consolidation.
        
        Uses entity and concept overlap (TF-IDF weighted) to find
        memories that cover similar topics and could be merged.
        
        Args:
            min_shared_entities: Minimum shared entities to consider similar
            min_shared_concepts: Minimum shared concepts to consider similar
            memory_types: Filter by memory type enum values (default: ["note"])
            tags: Filter by tag patterns (default: ["sys:history"])
            max_age_days: Only consider memories from the last N days
            min_group_size: Minimum memories per group
            max_groups: Maximum groups to return
            similarity_threshold: Minimum similarity score to include
            
        Returns:
            Dict with "groups" list and "total_groups_found" count
        """
        try:
            from services.consolidation_suggestion_service import (
                ConsolidationSuggestionService,
            )

            service = ConsolidationSuggestionService(
                engine=self.engine, redis_client=self.redis
            )
            groups = await service.suggest_consolidation(
                min_shared_entities=min_shared_entities,
                min_shared_concepts=min_shared_concepts,
                memory_types=memory_types or ["note"],
                tags=tags or ["sys:history"],
                max_age_days=max_age_days,
                min_group_size=min_group_size,
                max_groups=max_groups,
                similarity_threshold=similarity_threshold,
            )

            result_groups = []
            for g in groups:
                result_groups.append({
                    "source_ids": g.memory_ids,
                    "titles": g.titles,
                    "content_previews": g.content_previews,
                    "shared_entities": list(g.shared_entities),
                    "shared_concepts": list(g.shared_concepts),
                    "avg_similarity": round(g.avg_similarity, 3),
                    "suggested_title": service.suggest_title(g),
                    "suggested_tags": ["sys:history"],
                    "suggested_summary_hint": service.suggest_hint(g),
                })

            return {
                "groups": result_groups,
                "total_groups_found": len(result_groups),
            }

        except Exception as e:
            logger.error("suggest_consolidation_error", error=str(e))
            return {"error": str(e), "groups": [], "total_groups_found": 0}
