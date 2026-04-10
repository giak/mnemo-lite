"""
MCP Analytics Tools (EPIC-23 Story 23.6 + EPIC-31 Story 31.2).

Tools for cache management, indexing stats, and memory health observability.
"""
import structlog
import json
from typing import Optional

from mcp.server.fastmcp import Context

from mnemo_mcp.base import BaseMCPComponent
from mnemo_mcp.models.cache_models import ClearCacheRequest, ClearCacheResponse

logger = structlog.get_logger()


class ClearCacheTool(BaseMCPComponent):
    """
    Tool: clear_cache - Clear cache layers (admin operation).

    Uses MCP elicitation for user confirmation (destructive operation).

    Features:
    - Clear L1 (in-memory), L2 (Redis), or all layers
    - MCP elicitation for confirmation
    - Performance impact warning
    - Graceful error handling
    """

    def get_name(self) -> str:
        return "clear_cache"

    def get_description(self) -> str:
        return (
            "Clear cache layers (admin operation). "
            "Clears L1 (in-memory), L2 (Redis), or all. "
            "Performance may temporarily degrade until cache is repopulated. "
            "Requires user confirmation."
        )

    async def execute(
        self,
        layer: str = "all",
        ctx: Optional[Context] = None
    ) -> dict:
        """
        Clear cache with elicitation confirmation.

        Args:
            layer: "L1", "L2", or "all" (default: "all")
            ctx: MCP context for elicitation

        Returns:
            ClearCacheResponse with confirmation and stats
        """
        # Validate layer
        if layer not in ("L1", "L2", "all"):
            return {
                "success": False,
                "message": f"Invalid layer '{layer}'. Must be 'L1', 'L2', or 'all'."
            }

        # Elicit confirmation (MCP 2025-06-18)
        if ctx:
            layer_desc = {
                "L1": "in-memory cache (LRU)",
                "L2": "Redis distributed cache",
                "all": "all cache layers (L1 + L2)"
            }

            response = await ctx.elicit(
                prompt=(
                    f"Clear {layer} cache ({layer_desc[layer]})?\n\n"
                    f"This will:\n"
                    f"• Remove all cached data from {layer}\n"
                    f"• Temporarily degrade performance until cache is repopulated\n"
                    f"• Force all requests to hit slower storage layers\n"
                    f"• Impact: {'Low (single process)' if layer == 'L1' else 'Medium (all processes)' if layer == 'L2' else 'High (all caches)'}\n\n"
                    f"Proceed with cache clear?"
                ),
                schema={"type": "string", "enum": ["yes", "no"]}
            )

            if response.value == "no":
                return {
                    "success": False,
                    "message": f"Cache clear cancelled by user",
                    "layer": layer
                }

            logger.info(f"User confirmed cache clear for layer: {layer}")

        # Get cache service
        chunk_cache = self._services.get("chunk_cache") if self._services else None  # CascadeCache instance
        if not chunk_cache:
            return {
                "success": False,
                "message": "Cache service not available"
            }

        # Clear cache based on layer
        try:
            entries_cleared = 0

            if layer == "L1":
                # Get count before clearing
                l1_stats = chunk_cache.l1.stats()
                entries_cleared = l1_stats.get("entries", 0)

                # Clear L1 only (in-memory)
                chunk_cache.l1.clear()

                logger.info(
                    "L1 cache cleared",
                    entries_cleared=entries_cleared
                )

            elif layer == "L2":
                # Clear L2 only (Redis)
                # Note: CascadeCache.l2 is RedisCache
                await chunk_cache.l2.flush_all()

                logger.info("L2 cache (Redis) cleared")

            elif layer == "all":
                # Get count before clearing
                l1_stats = chunk_cache.l1.stats()
                entries_cleared = l1_stats.get("entries", 0)

                # Clear both L1 and L2
                await chunk_cache.clear_all()

                logger.info(
                    "All cache layers cleared",
                    l1_entries_cleared=entries_cleared
                )

            return {
                "success": True,
                "layer": layer,
                "entries_cleared": entries_cleared if layer in ("L1", "all") else 0,
                "impact_warning": (
                    f"Cache {layer} cleared successfully. "
                    f"Performance may temporarily degrade until cache is repopulated. "
                    f"Typical recovery time: 5-30 minutes depending on usage patterns."
                ),
                "message": f"Cache {layer} cleared successfully"
            }

        except Exception as e:
            logger.error(
                "Failed to clear cache",
                layer=layer,
                error=str(e),
                exc_info=True
            )
            return {
                "success": False,
                "message": f"Failed to clear cache: {str(e)}",
                "error": str(e),
                "layer": layer
            }


# Singleton instance for registration
clear_cache_tool = ClearCacheTool()


class GetIndexingStatsTool(BaseMCPComponent):
    """Tool: get_indexing_stats — Get indexing statistics for a repository."""

    def get_name(self) -> str:
        return "get_indexing_stats"

    def get_description(self) -> str:
        return (
            "Get indexing statistics for a repository including file counts, "
            "chunk counts, node/edge counts, and last indexed time."
        )

    async def execute(
        self,
        repository: str = "default",
        ctx: Optional[Context] = None
    ) -> dict:
        """Get indexing stats for a repository."""
        engine = self._services.get("engine") if self._services else None
        redis = self._services.get("redis") if self._services else None

        if not engine:
            return {"success": False, "message": "Database engine not available"}

        try:
            from sqlalchemy import text

            async with engine.connect() as conn:
                chunk_result = await conn.execute(text("""
                    SELECT COUNT(*) as total_chunks,
                           COUNT(DISTINCT file_path) as total_files,
                           MAX(indexed_at) as last_indexed,
                           MIN(indexed_at) as first_indexed,
                           COUNT(DISTINCT language) as languages
                    FROM code_chunks WHERE repository = :repo
                """), {"repo": repository})
                chunk_row = chunk_result.fetchone()

                try:
                    graph_result = await conn.execute(text("""
                        SELECT COUNT(*) as total_nodes,
                               COUNT(DISTINCT module) as modules
                        FROM graph_nodes WHERE repository = :repo
                    """), {"repo": repository})
                    graph_row = graph_result.fetchone()
                except Exception:
                    graph_row = (0, 0)

                try:
                    edge_result = await conn.execute(text("""
                        SELECT COUNT(*) as total_edges
                        FROM graph_edges WHERE repository = :repo
                    """), {"repo": repository})
                    edge_row = edge_result.fetchone()
                except Exception:
                    edge_row = (0,)

            indexing_status = None
            if redis:
                try:
                    status_data = await redis.get(f"indexing:status:{repository}")
                    if status_data:
                        indexing_status = json.loads(status_data)
                except Exception:
                    pass

            return {
                "success": True,
                "repository": repository,
                "total_chunks": chunk_row[0] if chunk_row else 0,
                "total_files": chunk_row[1] if chunk_row else 0,
                "total_nodes": graph_row[0] if graph_row else 0,
                "total_edges": edge_row[0] if edge_row else 0,
                "languages": chunk_row[4] if chunk_row else 0,
                "last_indexed": str(chunk_row[2]) if chunk_row and chunk_row[2] else None,
                "first_indexed": str(chunk_row[3]) if chunk_row and chunk_row[3] else None,
                "modules": graph_row[1] if graph_row else 0,
                "indexing_status": indexing_status,
            }

        except Exception as e:
            logger.error(f"Failed to get indexing stats: {e}", exc_info=True)
            return {"success": False, "message": f"Failed to get indexing stats: {e}"}


class GetMemoryHealthTool(BaseMCPComponent):
    """Tool: get_memory_health — Get health of the memory system."""

    def get_name(self) -> str:
        return "get_memory_health"

    def get_description(self) -> str:
        return (
            "Get memory system health including total memories, "
            "embedding coverage, decay stats, and consolidation status."
        )

    async def execute(
        self,
        ctx: Optional[Context] = None
    ) -> dict:
        """Get memory system health."""
        engine = self._services.get("engine") if self._services else None

        if not engine:
            return {"success": False, "message": "Database engine not available"}

        try:
            from sqlalchemy import text

            async with engine.connect() as conn:
                total_result = await conn.execute(text(
                    "SELECT COUNT(*) FROM memories WHERE deleted_at IS NULL"
                ))
                total = total_result.fetchone()[0]

                embedding_result = await conn.execute(text("""
                    SELECT COUNT(*) FROM memories
                    WHERE deleted_at IS NULL AND embedding IS NOT NULL
                """))
                with_embedding = embedding_result.fetchone()[0]

                type_result = await conn.execute(text("""
                    SELECT memory_type, COUNT(*) as cnt
                    FROM memories WHERE deleted_at IS NULL
                    GROUP BY memory_type ORDER BY cnt DESC
                """))
                by_type = {row[0]: row[1] for row in type_result.fetchall()}

                history_result = await conn.execute(text("""
                    SELECT COUNT(*) FROM memories
                    WHERE 'sys:history' = ANY(tags) AND deleted_at IS NULL
                """))
                history_count = history_result.fetchone()[0]

                drift_result = await conn.execute(text("""
                    SELECT COUNT(*) FROM memories
                    WHERE 'sys:drift' = ANY(tags) AND consumed_at IS NULL AND deleted_at IS NULL
                """))
                drift_count = drift_result.fetchone()[0]

                decay_result = await conn.execute(text(
                    "SELECT COUNT(*) FROM memory_decay_config"
                ))
                decay_rules = decay_result.fetchone()[0]

                outcome_stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) FILTER (WHERE outcome_positive > 0 OR outcome_negative > 0) as rated_count,
                        AVG(outcome_score) FILTER (WHERE outcome_score IS NOT NULL) as avg_score,
                        COUNT(*) FILTER (WHERE outcome_positive > outcome_negative + 2) as positive_count,
                        COUNT(*) FILTER (WHERE outcome_negative > outcome_positive + 2) as negative_count
                    FROM memories 
                    WHERE deleted_at IS NULL
                """)

            embedding_pct = round(with_embedding / total * 100, 1) if total > 0 else 0

            rated_count = outcome_stats["rated_count"] if outcome_stats else 0
            avg_score = outcome_stats["avg_score"] if outcome_stats and outcome_stats["avg_score"] else None
            positive_count = outcome_stats["positive_count"] if outcome_stats else 0
            negative_count = outcome_stats["negative_count"] if outcome_stats else 0
            positive_rate = f"{round(100 * positive_count / max(1, rated_count))}%" if rated_count > 0 else "N/A"

            return {
                "success": True,
                "total_memories": total,
                "with_embeddings": with_embedding,
                "embedding_coverage_pct": embedding_pct,
                "by_type": by_type,
                "history_count": history_count,
                "needs_consolidation": history_count > 20,
                "unconsumed_drifts": drift_count,
                "decay_rules": decay_rules,
                "outcome_metrics": {
                    "rated_memories": rated_count,
                    "avg_outcome_score": round(avg_score, 2) if avg_score else None,
                    "positive_count": positive_count,
                    "negative_count": negative_count,
                    "positive_rate": positive_rate,
                },
            }

        except Exception as e:
            logger.error(f"Failed to get memory health: {e}", exc_info=True)
            return {"success": False, "message": f"Failed to get memory health: {e}"}


class GetCacheStatsTool(BaseMCPComponent):
    """Tool: get_cache_stats — Get cache layer statistics."""

    def get_name(self) -> str:
        return "get_cache_stats"

    def get_description(self) -> str:
        return (
            "Get cache layer statistics including L1 (in-memory) and L2 (Redis) "
            "hit rates, sizes, and entry counts."
        )

    async def execute(
        self,
        ctx: Optional[Context] = None
    ) -> dict:
        """Get cache statistics."""
        chunk_cache = self._services.get("chunk_cache") if self._services else None
        redis = self._services.get("redis") if self._services else None

        stats = {"success": True, "l1": {}, "l2": {}, "redis_keys": {}}

        if chunk_cache:
            try:
                l1_stats = chunk_cache.l1.stats()
                stats["l1"] = {
                    "entries": l1_stats.get("entries", 0),
                    "hits": l1_stats.get("hits", 0),
                    "misses": l1_stats.get("misses", 0),
                    "hit_rate": l1_stats.get("hit_rate", 0),
                    "max_size": l1_stats.get("max_size", 0),
                }
            except Exception as e:
                stats["l1_error"] = str(e)

        if redis:
            try:
                info = await redis.info("memory")
                stats["l2"] = {
                    "used_memory_human": info.get("used_memory_human", "unknown"),
                    "connected_clients": info.get("connected_clients", 0),
                }
                cursor, search_keys = await redis.scan(0, match="search:v1:*", count=0)
                stats["redis_keys"]["search_cache"] = search_keys
                cursor, idx_keys = await redis.scan(0, match="indexing:status:*", count=0)
                stats["redis_keys"]["indexing_status"] = idx_keys
                cursor, lock_keys = await redis.scan(0, match="indexing:lock:*", count=0)
                stats["redis_keys"]["locks"] = lock_keys
            except Exception as e:
                stats["l2_error"] = str(e)
        else:
            stats["l2"] = {"status": "redis not available"}

        return stats


# Singleton instances for registration
get_indexing_stats_tool = GetIndexingStatsTool()
get_memory_health_tool = GetMemoryHealthTool()
get_cache_stats_tool = GetCacheStatsTool()
