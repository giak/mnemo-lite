"""
MCP Resources for Code Graph (EPIC-23 Story 23.4).

Exposes code dependency graphs via MCP 2025-06-18 protocol.
"""

import time
from typing import List, Optional
from uuid import UUID
import structlog

from mnemo_mcp.base import BaseMCPComponent
from mnemo_mcp.models.graph_models import (
    GraphNodeDetailsResponse,
    GraphNodeNeighbors,
    MCPNode,
    MCPEdge,
    CallerCalleeResponse,
    CallerCalleeMetadata,
    build_node_resource_links,
    build_pagination_links,
)
from models.graph_models import NodeModel, EdgeModel


class GraphNodeDetailsResource(BaseMCPComponent):
    """
    Resource: graph://nodes/{chunk_id}

    Returns a graph node with its immediate neighbors (callers and callees).

    MCP 2025-06-18: Resource (read-only) with resource links.
    """

    def get_name(self) -> str:
        return "graph_node_details"

    def get_description(self) -> str:
        return """
        Get code graph node with neighbors.

        Returns a node (function, class, method, module) with:
        - Immediate callers (who calls this)
        - Immediate callees (what this calls)
        - Edges connecting node to neighbors
        - Resource links for navigation

        URI: graph://nodes/{chunk_id}
        """

    async def get(self, chunk_id: str) -> dict:
        """
        Get node details with neighbors.

        Args:
            chunk_id: UUID of code chunk (maps to node_id or chunk_id property)

        Returns:
            GraphNodeDetailsResponse with node, neighbors, and resource links
        """
        start_time = time.time()
        logger = structlog.get_logger()

        logger.info(
            "graph_node_details_resource_get",
            chunk_id=chunk_id[:12] if len(chunk_id) > 12 else chunk_id
        )

        try:
            chunk_uuid = UUID(chunk_id)
        except ValueError as e:
            logger.warning("invalid_chunk_id", chunk_id=chunk_id, error=str(e))
            return GraphNodeDetailsResponse(
                success=False,
                message=f"Invalid chunk_id format: {chunk_id}",
                node=None,
                neighbors=GraphNodeNeighbors(),
            ).model_dump(mode='json')

        # Get services
        node_repo = self._services.get("node_repository")
        graph_service = self._services.get("graph_traversal_service")

        if not node_repo or not graph_service:
            logger.error("missing_services", node_repo=node_repo is not None, graph_service=graph_service is not None)
            return GraphNodeDetailsResponse(
                success=False,
                message="Graph services not available",
                node=None,
                neighbors=GraphNodeNeighbors(),
            ).model_dump(mode='json')

        # Find node by chunk_id (stored in node properties)
        node: Optional[NodeModel] = await node_repo.get_by_chunk_id(chunk_uuid)

        if not node:
            # Try direct node_id lookup (some nodes may not have chunk_id)
            node = await node_repo.get_by_id(chunk_uuid)

        if not node:
            logger.warning("node_not_found", chunk_id=chunk_id)
            return GraphNodeDetailsResponse(
                success=False,
                message=f"Node not found for chunk_id: {chunk_id}",
                node=None,
                neighbors=GraphNodeNeighbors(),
            ).model_dump(mode='json')

        # Get callers (inbound edges, depth=1)
        callers_result = await graph_service.traverse(
            start_node_id=node.node_id,
            direction="inbound",
            relationship=None,  # All relationships
            max_depth=1
        )

        # Get callees (outbound edges, depth=1)
        callees_result = await graph_service.traverse(
            start_node_id=node.node_id,
            direction="outbound",
            relationship=None,  # All relationships
            max_depth=1
        )

        # Get edges connecting node to neighbors
        # TODO: Implement EdgeRepository.get_edges_for_node()
        # For now, return empty edges list
        edges: List[EdgeModel] = []

        # Convert to MCP models
        mcp_node = self._convert_to_mcp_node(node)
        mcp_callers = [self._convert_to_mcp_node(n) for n in callers_result.nodes]
        mcp_callees = [self._convert_to_mcp_node(n) for n in callees_result.nodes]
        mcp_edges = [self._convert_to_mcp_edge(e) for e in edges]

        neighbors = GraphNodeNeighbors(
            callers=mcp_callers,
            callees=mcp_callees,
            edges=mcp_edges,
        )

        # Build resource links (MCP 2025-06-18)
        resource_links = build_node_resource_links(
            node_id=node.node_id,
            node_type=node.node_type,
            label=node.label
        )

        # Build metadata
        metadata = {
            "total_callers": len(mcp_callers),
            "total_callees": len(mcp_callees),
            "node_type": node.node_type,
            "file_path": node.properties.get("file_path", "unknown"),
            "execution_time_ms": round((time.time() - start_time) * 1000, 2),
        }

        response = GraphNodeDetailsResponse(
            success=True,
            message="Node details retrieved successfully",
            node=mcp_node,
            neighbors=neighbors,
            metadata=metadata,
            resource_links=resource_links,
        )

        logger.info(
            "graph_node_details_success",
            node_id=str(node.node_id)[:12],
            total_callers=len(mcp_callers),
            total_callees=len(mcp_callees),
            execution_time_ms=metadata["execution_time_ms"],
        )

        return response.model_dump(mode='json')

    def _convert_to_mcp_node(self, node: NodeModel) -> MCPNode:
        """Convert NodeModel to MCPNode."""
        resource_links = build_node_resource_links(
            node_id=node.node_id,
            node_type=node.node_type,
            label=node.label
        )

        return MCPNode(
            node_id=node.node_id,
            node_type=node.node_type,
            label=node.label,
            properties=node.properties,
            created_at=node.created_at,
            resource_links=resource_links,
        )

    def _convert_to_mcp_edge(self, edge: EdgeModel) -> MCPEdge:
        """Convert EdgeModel to MCPEdge."""
        return MCPEdge(
            edge_id=edge.edge_id,
            source_node_id=edge.source_node_id,
            target_node_id=edge.target_node_id,
            relation_type=edge.relation_type,
            properties=edge.properties,
            created_at=edge.created_at,
        )


class FindCallersResource(BaseMCPComponent):
    """
    Resource: graph://callers/{qualified_name}

    Find all functions/methods that call the target function.

    Performs inbound graph traversal (dependents).
    MCP 2025-06-18: Resource with pagination and resource links.
    """

    def get_name(self) -> str:
        return "find_callers"

    def get_description(self) -> str:
        return """
        Find callers of a function/method.

        Returns all functions/methods/classes that call or reference
        the target function/method, up to max_depth hops.

        Supports:
        - Pagination (limit, offset)
        - Depth filtering (max_depth)
        - Relationship filtering (calls, imports, etc.)

        URI: graph://callers/{qualified_name}?max_depth=3&limit=50&offset=0
        """

    async def get(
        self,
        qualified_name: str,
        max_depth: int = 3,
        relationship_type: str = "calls",
        limit: int = 50,
        offset: int = 0
    ) -> dict:
        """
        Find callers of a function/method.

        Args:
            qualified_name: Fully qualified name (e.g., "module.ClassName.method")
            max_depth: Maximum depth to traverse (1-10, default: 3)
            relationship_type: Edge type to follow (default: "calls")
            limit: Maximum results (1-500, default: 50)
            offset: Pagination offset (0-10000, default: 0)

        Returns:
            CallerCalleeResponse with callers and pagination links
        """
        start_time = time.time()
        logger = structlog.get_logger()

        logger.info(
            "find_callers_resource_get",
            qualified_name=qualified_name,
            max_depth=max_depth,
            limit=limit,
            offset=offset
        )

        # Get services
        node_repo = self._services.get("node_repository")
        graph_service = self._services.get("graph_traversal_service")

        if not node_repo or not graph_service:
            logger.error("missing_services")
            return CallerCalleeResponse(
                success=False,
                message="Graph services not available",
                nodes=[],
                metadata=CallerCalleeMetadata(
                    qualified_name=qualified_name,
                    direction="inbound",
                    max_depth=max_depth,
                    total_found=0,
                    returned_count=0,
                    limit=limit,
                    offset=offset,
                    has_more=False,
                ),
            ).model_dump(mode='json')

        # Find node by qualified_name (label)
        nodes = await node_repo.search_by_label(qualified_name)

        if not nodes:
            logger.warning("node_not_found", qualified_name=qualified_name)
            return CallerCalleeResponse(
                success=False,
                message=f"Node not found for qualified_name: {qualified_name}",
                nodes=[],
                metadata=CallerCalleeMetadata(
                    qualified_name=qualified_name,
                    direction="inbound",
                    max_depth=max_depth,
                    total_found=0,
                    returned_count=0,
                    limit=limit,
                    offset=offset,
                    has_more=False,
                ),
            ).model_dump(mode='json')

        # Use first match if multiple nodes have same name
        target_node = nodes[0]

        # Traverse graph inbound (find callers)
        # Note: GraphTraversalService doesn't support pagination,
        # so we fetch all and paginate manually
        traversal_result = await graph_service.traverse(
            start_node_id=target_node.node_id,
            direction="inbound",
            relationship=relationship_type if relationship_type else None,
            max_depth=max_depth
        )

        # Apply pagination
        total_found = len(traversal_result.nodes)
        paginated_nodes = traversal_result.nodes[offset:offset + limit]

        # Convert to MCP nodes
        mcp_nodes = [self._convert_to_mcp_node(n) for n in paginated_nodes]

        # Build metadata
        has_more = (offset + limit) < total_found
        cache_hit = False  # TODO: Check if result came from cache
        execution_time_ms = round((time.time() - start_time) * 1000, 2)

        metadata = CallerCalleeMetadata(
            qualified_name=qualified_name,
            direction="inbound",
            max_depth=max_depth,
            total_found=total_found,
            returned_count=len(mcp_nodes),
            limit=limit,
            offset=offset,
            has_more=has_more,
            cache_hit=cache_hit,
            execution_time_ms=execution_time_ms,
        )

        # Build pagination links (MCP 2025-06-18)
        base_uri = f"graph://callers/{qualified_name}?max_depth={max_depth}&relationship_type={relationship_type}"
        resource_links = build_pagination_links(
            base_uri=base_uri,
            limit=limit,
            offset=offset,
            total_count=total_found
        )

        response = CallerCalleeResponse(
            success=True,
            message=f"Found {total_found} callers",
            nodes=mcp_nodes,
            metadata=metadata,
            resource_links=resource_links,
        )

        logger.info(
            "find_callers_success",
            qualified_name=qualified_name,
            total_found=total_found,
            returned_count=len(mcp_nodes),
            has_more=has_more,
            execution_time_ms=execution_time_ms,
        )

        return response.model_dump(mode='json')

    def _convert_to_mcp_node(self, node: NodeModel) -> MCPNode:
        """Convert NodeModel to MCPNode."""
        resource_links = build_node_resource_links(
            node_id=node.node_id,
            node_type=node.node_type,
            label=node.label
        )

        return MCPNode(
            node_id=node.node_id,
            node_type=node.node_type,
            label=node.label,
            properties=node.properties,
            created_at=node.created_at,
            resource_links=resource_links,
        )


class FindCalleesResource(BaseMCPComponent):
    """
    Resource: graph://callees/{qualified_name}

    Find all functions/methods called by the target function.

    Performs outbound graph traversal (dependencies).
    MCP 2025-06-18: Resource with pagination and resource links.
    """

    def get_name(self) -> str:
        return "find_callees"

    def get_description(self) -> str:
        return """
        Find callees of a function/method.

        Returns all functions/methods/classes called or referenced
        by the target function/method, up to max_depth hops.

        Supports:
        - Pagination (limit, offset)
        - Depth filtering (max_depth)
        - Relationship filtering (calls, imports, etc.)

        URI: graph://callees/{qualified_name}?max_depth=3&limit=50&offset=0
        """

    async def get(
        self,
        qualified_name: str,
        max_depth: int = 3,
        relationship_type: str = "calls",
        limit: int = 50,
        offset: int = 0
    ) -> dict:
        """
        Find callees of a function/method.

        Args:
            qualified_name: Fully qualified name (e.g., "module.ClassName.method")
            max_depth: Maximum depth to traverse (1-10, default: 3)
            relationship_type: Edge type to follow (default: "calls")
            limit: Maximum results (1-500, default: 50)
            offset: Pagination offset (0-10000, default: 0)

        Returns:
            CallerCalleeResponse with callees and pagination links
        """
        start_time = time.time()
        logger = structlog.get_logger()

        logger.info(
            "find_callees_resource_get",
            qualified_name=qualified_name,
            max_depth=max_depth,
            limit=limit,
            offset=offset
        )

        # Get services
        node_repo = self._services.get("node_repository")
        graph_service = self._services.get("graph_traversal_service")

        if not node_repo or not graph_service:
            logger.error("missing_services")
            return CallerCalleeResponse(
                success=False,
                message="Graph services not available",
                nodes=[],
                metadata=CallerCalleeMetadata(
                    qualified_name=qualified_name,
                    direction="outbound",
                    max_depth=max_depth,
                    total_found=0,
                    returned_count=0,
                    limit=limit,
                    offset=offset,
                    has_more=False,
                ),
            ).model_dump(mode='json')

        # Find node by qualified_name (label)
        nodes = await node_repo.search_by_label(qualified_name)

        if not nodes:
            logger.warning("node_not_found", qualified_name=qualified_name)
            return CallerCalleeResponse(
                success=False,
                message=f"Node not found for qualified_name: {qualified_name}",
                nodes=[],
                metadata=CallerCalleeMetadata(
                    qualified_name=qualified_name,
                    direction="outbound",
                    max_depth=max_depth,
                    total_found=0,
                    returned_count=0,
                    limit=limit,
                    offset=offset,
                    has_more=False,
                ),
            ).model_dump(mode='json')

        # Use first match if multiple nodes have same name
        target_node = nodes[0]

        # Traverse graph outbound (find callees)
        # Note: GraphTraversalService doesn't support pagination,
        # so we fetch all and paginate manually
        traversal_result = await graph_service.traverse(
            start_node_id=target_node.node_id,
            direction="outbound",
            relationship=relationship_type if relationship_type else None,
            max_depth=max_depth
        )

        # Apply pagination
        total_found = len(traversal_result.nodes)
        paginated_nodes = traversal_result.nodes[offset:offset + limit]

        # Convert to MCP nodes
        mcp_nodes = [self._convert_to_mcp_node(n) for n in paginated_nodes]

        # Build metadata
        has_more = (offset + limit) < total_found
        cache_hit = False  # TODO: Check if result came from cache
        execution_time_ms = round((time.time() - start_time) * 1000, 2)

        metadata = CallerCalleeMetadata(
            qualified_name=qualified_name,
            direction="outbound",
            max_depth=max_depth,
            total_found=total_found,
            returned_count=len(mcp_nodes),
            limit=limit,
            offset=offset,
            has_more=has_more,
            cache_hit=cache_hit,
            execution_time_ms=execution_time_ms,
        )

        # Build pagination links (MCP 2025-06-18)
        base_uri = f"graph://callees/{qualified_name}?max_depth={max_depth}&relationship_type={relationship_type}"
        resource_links = build_pagination_links(
            base_uri=base_uri,
            limit=limit,
            offset=offset,
            total_count=total_found
        )

        response = CallerCalleeResponse(
            success=True,
            message=f"Found {total_found} callees",
            nodes=mcp_nodes,
            metadata=metadata,
            resource_links=resource_links,
        )

        logger.info(
            "find_callees_success",
            qualified_name=qualified_name,
            total_found=total_found,
            returned_count=len(mcp_nodes),
            has_more=has_more,
            execution_time_ms=execution_time_ms,
        )

        return response.model_dump(mode='json')

    def _convert_to_mcp_node(self, node: NodeModel) -> MCPNode:
        """Convert NodeModel to MCPNode."""
        resource_links = build_node_resource_links(
            node_id=node.node_id,
            node_type=node.node_type,
            label=node.label
        )

        return MCPNode(
            node_id=node.node_id,
            node_type=node.node_type,
            label=node.label,
            properties=node.properties,
            created_at=node.created_at,
            resource_links=resource_links,
        )


# ============================================================================
# Singleton Instances for Registration
# ============================================================================

graph_node_details_resource = GraphNodeDetailsResource()
find_callers_resource = FindCallersResource()
find_callees_resource = FindCalleesResource()
