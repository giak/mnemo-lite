"""
MCP Analytics Tools (EPIC-23 Story 23.6).

Tools for cache management and observability.
"""
import structlog
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
