"""
GraphTraversalService for EPIC-06 Phase 2 Story 4.

Traverses code dependency graphs using recursive CTEs.
Includes L2 Redis caching for performance (EPIC-10 Story 10.2).
"""

import logging
import uuid
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import text
import structlog

from db.repositories.node_repository import NodeRepository
from models.graph_models import GraphTraversal, NodeModel
from services.caches import RedisCache, cache_keys

logger = logging.getLogger(__name__)


class GraphTraversalService:
    """
    Traverse code dependency graphs using PostgreSQL recursive CTEs.

    Responsibilities:
    - Find all nodes reachable from a starting node
    - Support both outbound (dependencies) and inbound (dependents) traversal
    - Filter by relationship type (calls, imports, etc.)
    - Limit traversal depth to prevent infinite loops
    - Use recursive CTEs for performance
    - L2 Redis caching for graph traversal results (120s TTL)
    """

    def __init__(self, engine: AsyncEngine, redis_cache: Optional[RedisCache] = None):
        """
        Initialize service with database engine and optional Redis cache.

        Args:
            engine: SQLAlchemy async engine
            redis_cache: Optional L2 Redis cache for performance
        """
        self.engine = engine
        self.node_repo = NodeRepository(engine)
        self.redis_cache = redis_cache
        self.logger = structlog.get_logger()
        self.logger.info(
            "GraphTraversalService initialized",
            redis_cache_enabled=redis_cache is not None
        )

    async def traverse(
        self,
        start_node_id: uuid.UUID,
        direction: str = "outbound",
        relationship: Optional[str] = None,
        max_depth: int = 3
    ) -> GraphTraversal:
        """
        Traverse graph from starting node.

        Args:
            start_node_id: Node to start traversal from
            direction: "outbound" (dependencies) or "inbound" (dependents)
            relationship: Filter by edge type (e.g., "calls"), None = all types
            max_depth: Maximum depth to traverse (default: 3, per CLAUDE.md)

        Returns:
            GraphTraversal with discovered nodes

        Example:
            # Find all functions called by function X (up to 3 hops)
            result = await service.traverse(
                start_node_id=func_x_id,
                direction="outbound",
                relationship="calls",
                max_depth=3
            )
        """
        self.logger.info(
            f"Traversing graph from node {start_node_id}, "
            f"direction={direction}, relationship={relationship}, max_depth={max_depth}"
        )

        # Validate direction
        if direction not in ["outbound", "inbound"]:
            raise ValueError(f"Invalid direction: {direction}. Must be 'outbound' or 'inbound'.")

        # Validate start node exists
        start_node = await self.node_repo.get_by_id(start_node_id)
        if not start_node:
            self.logger.warning(f"Start node {start_node_id} not found.")
            return GraphTraversal(
                start_node=start_node_id,
                direction=direction,
                relationship=relationship or "any",
                max_depth=max_depth,
                nodes=[],
                total_nodes=0
            )

        # L2 CACHE LOOKUP (EPIC-10 Story 10.2)
        if self.redis_cache:
            # Build relation_types list for cache key
            relation_types = [relationship] if relationship else None
            cache_key = cache_keys.graph_traversal_key(
                node_id=str(start_node_id),
                max_hops=max_depth,
                relation_types=relation_types
            )
            # Add direction to cache key to distinguish inbound vs outbound
            cache_key = f"{cache_key}:{direction}"

            cached_response = await self.redis_cache.get(cache_key)

            if cached_response:
                self.logger.info(
                    "L2 cache HIT for graph traversal",
                    start_node=str(start_node_id)[:12],
                    direction=direction,
                    relationship=relationship,
                )
                # Deserialize GraphTraversal
                return self._deserialize_graph_traversal(cached_response)

            self.logger.debug(
                "L2 cache MISS for graph traversal",
                start_node=str(start_node_id)[:12],
                direction=direction,
                relationship=relationship,
            )

        # Build and execute recursive CTE query
        discovered_node_ids = await self._execute_recursive_traversal(
            start_node_id=start_node_id,
            direction=direction,
            relationship=relationship,
            max_depth=max_depth
        )

        # Fetch full node details for discovered nodes
        nodes = await self._fetch_nodes_by_ids(discovered_node_ids)

        self.logger.info(f"Traversal complete: discovered {len(nodes)} nodes")

        # Build response
        response = GraphTraversal(
            start_node=start_node_id,
            direction=direction,
            relationship=relationship or "any",
            max_depth=max_depth,
            nodes=nodes,
            total_nodes=len(nodes)
        )

        # POPULATE L2 CACHE (EPIC-10 Story 10.2)
        if self.redis_cache:
            relation_types = [relationship] if relationship else None
            cache_key = cache_keys.graph_traversal_key(
                node_id=str(start_node_id),
                max_hops=max_depth,
                relation_types=relation_types
            )
            # Add direction to cache key
            cache_key = f"{cache_key}:{direction}"

            serialized = self._serialize_graph_traversal(response)
            # Cache for 120 seconds (graph traversals)
            await self.redis_cache.set(cache_key, serialized, ttl_seconds=120)
            self.logger.debug(
                "L2 cache populated for graph traversal",
                start_node=str(start_node_id)[:12],
                direction=direction,
                relationship=relationship,
                ttl_seconds=120,
            )

        return response

    async def _execute_recursive_traversal(
        self,
        start_node_id: uuid.UUID,
        direction: str,
        relationship: Optional[str],
        max_depth: int
    ) -> List[uuid.UUID]:
        """
        Execute recursive CTE to find reachable nodes.

        Uses PostgreSQL WITH RECURSIVE for efficient graph traversal.

        Returns:
            List of discovered node IDs (excluding start node)
        """
        # Build relationship filter
        relationship_filter = ""
        if relationship:
            relationship_filter = "AND e.relation_type = :relationship"

        # Build CTE based on direction
        if direction == "outbound":
            # Follow edges FROM start node TO other nodes (dependencies)
            cte_query = f"""
                WITH RECURSIVE traversal AS (
                    -- Base case: start node at depth 0
                    SELECT
                        n.node_id AS node_id,
                        0 AS depth
                    FROM nodes n
                    WHERE n.node_id = :start_node_id

                    UNION

                    -- Recursive case: follow outbound edges
                    SELECT
                        e.target_node_id AS node_id,
                        t.depth + 1 AS depth
                    FROM traversal t
                    JOIN edges e ON e.source_node_id = t.node_id
                    WHERE t.depth < :max_depth
                      {relationship_filter}
                )
                SELECT DISTINCT node_id
                FROM traversal
                WHERE node_id != :start_node_id  -- Exclude start node from results
                ORDER BY node_id
            """
        else:
            # Follow edges TO start node FROM other nodes (dependents)
            cte_query = f"""
                WITH RECURSIVE traversal AS (
                    -- Base case: start node at depth 0
                    SELECT
                        n.node_id AS node_id,
                        0 AS depth
                    FROM nodes n
                    WHERE n.node_id = :start_node_id

                    UNION

                    -- Recursive case: follow inbound edges
                    SELECT
                        e.source_node_id AS node_id,
                        t.depth + 1 AS depth
                    FROM traversal t
                    JOIN edges e ON e.target_node_id = t.node_id
                    WHERE t.depth < :max_depth
                      {relationship_filter}
                )
                SELECT DISTINCT node_id
                FROM traversal
                WHERE node_id != :start_node_id  -- Exclude start node from results
                ORDER BY node_id
            """

        # Execute query
        async with self.engine.connect() as connection:
            params = {
                "start_node_id": str(start_node_id),
                "max_depth": max_depth
            }
            if relationship:
                params["relationship"] = relationship

            self.logger.debug(f"Executing recursive CTE with params: {params}")
            result = await connection.execute(text(cte_query), params)
            rows = result.fetchall()

        # Extract node IDs
        # Note: asyncpg returns UUID objects directly, convert to Python UUID
        node_ids = [uuid.UUID(str(row[0])) if not isinstance(row[0], uuid.UUID) else row[0] for row in rows]
        self.logger.debug(f"Recursive CTE discovered {len(node_ids)} nodes")

        return node_ids

    async def _fetch_nodes_by_ids(self, node_ids: List[uuid.UUID]) -> List[NodeModel]:
        """
        Fetch full node details for list of node IDs.

        Args:
            node_ids: List of node UUIDs to fetch

        Returns:
            List of NodeModels
        """
        if not node_ids:
            return []

        # Build query to fetch all nodes in one query
        query_str = text("""
            SELECT * FROM nodes
            WHERE node_id = ANY(:node_ids)
            ORDER BY node_type, label
        """)

        async with self.engine.connect() as connection:
            params = {"node_ids": [str(nid) for nid in node_ids]}
            result = await connection.execute(query_str, params)
            rows = result.mappings().all()

        nodes = [NodeModel.from_db_record(row) for row in rows]
        self.logger.debug(f"Fetched {len(nodes)} node details")

        return nodes

    async def find_path(
        self,
        source_node_id: uuid.UUID,
        target_node_id: uuid.UUID,
        relationship: Optional[str] = None,
        max_depth: int = 10
    ) -> Optional[List[uuid.UUID]]:
        """
        Find shortest path between two nodes.

        Uses recursive CTE with path tracking to find shortest path.

        Args:
            source_node_id: Starting node
            target_node_id: Target node
            relationship: Filter by edge type (e.g., "calls"), None = all types
            max_depth: Maximum depth to search (default: 10)

        Returns:
            List of node IDs representing path from source to target,
            or None if no path exists.

        Example:
            # Find how function A reaches function B through calls
            path = await service.find_path(
                source_node_id=func_a_id,
                target_node_id=func_b_id,
                relationship="calls"
            )
            # Returns: [func_a_id, func_x_id, func_y_id, func_b_id]
        """
        self.logger.info(
            f"Finding path from {source_node_id} to {target_node_id}, "
            f"relationship={relationship}, max_depth={max_depth}"
        )

        # L2 CACHE LOOKUP (EPIC-10 Story 10.2)
        if self.redis_cache:
            # Build custom cache key for path finding
            source_short = str(source_node_id)[:12]
            target_short = str(target_node_id)[:12]
            rel_str = relationship if relationship else "all"
            cache_key = f"graph:path:{source_short}:{target_short}:{rel_str}:hops{max_depth}"

            cached_response = await self.redis_cache.get(cache_key)

            if cached_response:
                self.logger.info(
                    "L2 cache HIT for path finding",
                    source=source_short,
                    target=target_short,
                    relationship=relationship,
                )
                # Deserialize path (List[UUID] or None)
                return self._deserialize_path(cached_response)

            self.logger.debug(
                "L2 cache MISS for path finding",
                source=source_short,
                target=target_short,
                relationship=relationship,
            )

        # Build relationship filter
        relationship_filter = ""
        if relationship:
            relationship_filter = "AND e.relation_type = :relationship"

        # Recursive CTE with path tracking
        # Note: We build the initial array using PostgreSQL syntax, not parameter binding
        cte_query = f"""
            WITH RECURSIVE path_search AS (
                -- Base case: start node with initial path
                SELECT
                    n.node_id AS node_id,
                    ARRAY[n.node_id] AS path,
                    0 AS depth
                FROM nodes n
                WHERE n.node_id = :source_node_id

                UNION

                -- Recursive case: extend path through outbound edges
                SELECT
                    e.target_node_id AS node_id,
                    p.path || e.target_node_id AS path,
                    p.depth + 1 AS depth
                FROM path_search p
                JOIN edges e ON e.source_node_id = p.node_id
                WHERE p.depth < :max_depth
                  AND NOT (e.target_node_id = ANY(p.path))  -- Prevent cycles
                  {relationship_filter}
            )
            SELECT path
            FROM path_search
            WHERE node_id = :target_node_id
            ORDER BY depth
            LIMIT 1  -- Return shortest path
        """

        # Execute query
        async with self.engine.connect() as connection:
            params = {
                "source_node_id": str(source_node_id),
                "target_node_id": str(target_node_id),
                "max_depth": max_depth
            }
            if relationship:
                params["relationship"] = relationship

            self.logger.debug(f"Executing path search with params: {params}")
            result = await connection.execute(text(cte_query), params)
            row = result.fetchone()

        if not row:
            self.logger.info(f"No path found between {source_node_id} and {target_node_id}")

            # POPULATE L2 CACHE for "no path found" case (EPIC-10 Story 10.2)
            if self.redis_cache:
                source_short = str(source_node_id)[:12]
                target_short = str(target_node_id)[:12]
                rel_str = relationship if relationship else "all"
                cache_key = f"graph:path:{source_short}:{target_short}:{rel_str}:hops{max_depth}"

                serialized = self._serialize_path(None)
                # Cache for 120 seconds (graph paths)
                await self.redis_cache.set(cache_key, serialized, ttl_seconds=120)
                self.logger.debug(
                    "L2 cache populated for path finding (no path)",
                    source=source_short,
                    target=target_short,
                    ttl_seconds=120,
                )

            return None

        # Parse path from array
        # Note: asyncpg returns UUID objects directly
        path = [uuid.UUID(str(node_id)) if not isinstance(node_id, uuid.UUID) else node_id for node_id in row[0]]
        self.logger.info(f"Found path with {len(path)} nodes")

        # POPULATE L2 CACHE for found path (EPIC-10 Story 10.2)
        if self.redis_cache:
            source_short = str(source_node_id)[:12]
            target_short = str(target_node_id)[:12]
            rel_str = relationship if relationship else "all"
            cache_key = f"graph:path:{source_short}:{target_short}:{rel_str}:hops{max_depth}"

            serialized = self._serialize_path(path)
            # Cache for 120 seconds (graph paths)
            await self.redis_cache.set(cache_key, serialized, ttl_seconds=120)
            self.logger.debug(
                "L2 cache populated for path finding",
                source=source_short,
                target=target_short,
                path_length=len(path),
                ttl_seconds=120,
            )

        return path

    def _serialize_graph_traversal(self, response: GraphTraversal) -> dict:
        """
        Serialize GraphTraversal for Redis caching.

        Converts dataclass objects to dict for JSON serialization.
        """
        return {
            "start_node": str(response.start_node),
            "direction": response.direction,
            "relationship": response.relationship,
            "max_depth": response.max_depth,
            "nodes": [
                {
                    "node_id": str(n.node_id),
                    "node_type": n.node_type,
                    "label": n.label,
                    "properties": n.properties,
                    "created_at": n.created_at.isoformat(),
                }
                for n in response.nodes
            ],
            "total_nodes": response.total_nodes,
        }

    def _deserialize_graph_traversal(self, data: dict) -> GraphTraversal:
        """
        Deserialize cached data back to GraphTraversal.

        Reconstructs dataclass objects from dict.
        """
        from datetime import datetime

        nodes = [
            NodeModel(
                node_id=uuid.UUID(n["node_id"]),
                node_type=n["node_type"],
                label=n["label"],
                properties=n["properties"],
                created_at=datetime.fromisoformat(n["created_at"]),
            )
            for n in data["nodes"]
        ]

        return GraphTraversal(
            start_node=uuid.UUID(data["start_node"]),
            direction=data["direction"],
            relationship=data["relationship"],
            max_depth=data["max_depth"],
            nodes=nodes,
            total_nodes=data["total_nodes"],
        )

    def _serialize_path(self, path: Optional[List[uuid.UUID]]) -> dict:
        """
        Serialize path for Redis caching.

        Args:
            path: List of node UUIDs or None

        Returns:
            Dict with path as list of strings, or None marker
        """
        if path is None:
            return {"path": None}

        return {"path": [str(node_id) for node_id in path]}

    def _deserialize_path(self, data: dict) -> Optional[List[uuid.UUID]]:
        """
        Deserialize cached path data.

        Args:
            data: Dict with path data

        Returns:
            List of UUIDs or None
        """
        if data["path"] is None:
            return None

        return [uuid.UUID(node_id) for node_id in data["path"]]
