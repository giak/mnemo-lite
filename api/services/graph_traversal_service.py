"""
GraphTraversalService for EPIC-06 Phase 2 Story 4.

Traverses code dependency graphs using recursive CTEs.
"""

import logging
import uuid
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import text

from db.repositories.node_repository import NodeRepository
from models.graph_models import GraphTraversal, NodeModel

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
    """

    def __init__(self, engine: AsyncEngine):
        """Initialize service with database engine."""
        self.engine = engine
        self.node_repo = NodeRepository(engine)
        self.logger = logging.getLogger(__name__)
        self.logger.info("GraphTraversalService initialized.")

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

        return GraphTraversal(
            start_node=start_node_id,
            direction=direction,
            relationship=relationship or "any",
            max_depth=max_depth,
            nodes=nodes,
            total_nodes=len(nodes)
        )

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
            return None

        # Parse path from array
        # Note: asyncpg returns UUID objects directly
        path = [uuid.UUID(str(node_id)) if not isinstance(node_id, uuid.UUID) else node_id for node_id in row[0]]
        self.logger.info(f"Found path with {len(path)} nodes")

        return path
