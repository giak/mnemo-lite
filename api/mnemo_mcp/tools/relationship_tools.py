"""
Memory Relationship MCP Tools — Tools for navigating the memory graph.
"""
from typing import Dict, Any, List, Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncEngine

logger = structlog.get_logger()


class GetRelatedMemoriesTool:
    """MCP tool to get memories related to a specific memory."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def execute(
        self,
        memory_id: str,
        max_depth: int = 1,
        min_score: float = 0.1,
    ) -> Dict[str, Any]:
        """Get related memories via BFS."""
        try:
            from services.memory_relationship_service import MemoryRelationshipService
            from sqlalchemy.sql import text

            service = MemoryRelationshipService(engine=self.engine)
            related = await service.get_related_memories(
                memory_id=memory_id,
                max_depth=max_depth,
                min_score=min_score,
            )

            # Enrich with memory details
            if related:
                memory_ids = [r["memory_id"] for r in related]
                query = text("""
                    SELECT id::text, title, memory_type, tags
                    FROM memories
                    WHERE id = ANY(:ids) AND deleted_at IS NULL
                """)
                async with self.engine.begin() as conn:
                    result = await conn.execute(query, {"ids": memory_ids})
                    memories = {str(row[0]): {"title": row[1], "memory_type": row[2], "tags": row[3]} for row in result}

                for r in related:
                    mem_info = memories.get(r["memory_id"], {})
                    r.update(mem_info)

            return {
                "memory_id": memory_id,
                "related": related,
                "total": len(related),
            }

        except Exception as e:
            logger.error("get_related_memories_error", error=str(e))
            return {"error": str(e), "total": 0, "related": []}


class GetMemoryGraphTool:
    """MCP tool to get the memory relationship graph."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def execute(
        self,
        min_score: float = 0.3,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Get memory graph for visualization."""
        try:
            from sqlalchemy.sql import text

            query = text("""
                SELECT
                    mr.source_id::text,
                    mr.target_id::text,
                    mr.score,
                    mr.relationship_types,
                    m1.title as source_title,
                    m1.memory_type as source_type,
                    m2.title as target_title,
                    m2.memory_type as target_type
                FROM memory_relationships mr
                JOIN memories m1 ON m1.id = mr.source_id
                JOIN memories m2 ON m2.id = mr.target_id
                WHERE mr.score >= :min_score
                  AND m1.deleted_at IS NULL
                  AND m2.deleted_at IS NULL
                ORDER BY mr.score DESC
                LIMIT :limit
            """)

            async with self.engine.begin() as conn:
                result = await conn.execute(query, {"min_score": min_score, "limit": limit})
                rows = result.fetchall()

            nodes = {}
            edges = []

            for row in rows:
                source_id, target_id, score, rel_types, source_title, source_type, target_title, target_type = row

                if source_id not in nodes:
                    nodes[source_id] = {"id": source_id, "title": source_title, "memory_type": source_type, "size": 0}
                if target_id not in nodes:
                    nodes[target_id] = {"id": target_id, "title": target_title, "memory_type": target_type, "size": 0}

                nodes[source_id]["size"] += 1
                nodes[target_id]["size"] += 1

                edges.append({
                    "source": source_id,
                    "target": target_id,
                    "score": score,
                    "types": rel_types or [],
                })

            return {
                "nodes": list(nodes.values()),
                "edges": edges,
                "total_nodes": len(nodes),
                "total_edges": len(edges),
            }

        except Exception as e:
            logger.error("get_memory_graph_error", error=str(e))
            return {"error": str(e), "nodes": [], "edges": []}
