"""
Unit tests for MCP Graph Models (EPIC-23 Story 23.4).

Tests Pydantic models for graph resources.
"""

import pytest
from datetime import datetime
from uuid import uuid4

from mnemo_mcp.models.graph_models import (
    MCPNode,
    MCPEdge,
    GraphTraversalQuery,
    GraphTraversalMetadata,
    GraphTraversalResponse,
    CallerCalleeQuery,
    CallerCalleeMetadata,
    CallerCalleeResponse,
    GraphNodeDetailsQuery,
    GraphNodeNeighbors,
    GraphNodeDetailsResponse,
    build_node_resource_links,
    build_pagination_links,
)


class TestMCPNode:
    """Test MCPNode model."""

    def test_create_node_minimal(self):
        """Test creating node with minimal fields."""
        node_id = uuid4()
        node = MCPNode(
            node_id=node_id,
            node_type="function",
            label="test_function",
            created_at=datetime.utcnow(),
        )

        assert node.node_id == node_id
        assert node.node_type == "function"
        assert node.label == "test_function"
        assert node.properties == {}
        assert node.resource_links == []

    def test_create_node_full(self):
        """Test creating node with all fields."""
        node_id = uuid4()
        properties = {"file_path": "test.py", "line_number": 42}
        resource_links = ["graph://nodes/123", "graph://callers/test_function"]

        node = MCPNode(
            node_id=node_id,
            node_type="function",
            label="test_function",
            properties=properties,
            created_at=datetime.utcnow(),
            resource_links=resource_links,
        )

        assert node.properties == properties
        assert node.resource_links == resource_links

    def test_node_json_serialization(self):
        """Test node JSON serialization."""
        node_id = uuid4()
        node = MCPNode(
            node_id=node_id,
            node_type="class",
            label="TestClass",
            created_at=datetime.utcnow(),
        )

        # model_dump(mode='json') should serialize UUID and datetime
        data = node.model_dump(mode='json')

        assert isinstance(data['node_id'], str)
        assert isinstance(data['created_at'], str)
        assert data['node_type'] == "class"


class TestMCPEdge:
    """Test MCPEdge model."""

    def test_create_edge(self):
        """Test creating edge."""
        edge_id = uuid4()
        source_id = uuid4()
        target_id = uuid4()

        edge = MCPEdge(
            edge_id=edge_id,
            source_node_id=source_id,
            target_node_id=target_id,
            relation_type="calls",
            created_at=datetime.utcnow(),
        )

        assert edge.edge_id == edge_id
        assert edge.source_node_id == source_id
        assert edge.target_node_id == target_id
        assert edge.relation_type == "calls"
        assert edge.properties == {}

    def test_edge_with_properties(self):
        """Test edge with custom properties."""
        edge = MCPEdge(
            edge_id=uuid4(),
            source_node_id=uuid4(),
            target_node_id=uuid4(),
            relation_type="imports",
            properties={"call_count": 5, "line_number": 10},
            created_at=datetime.utcnow(),
        )

        assert edge.properties["call_count"] == 5
        assert edge.properties["line_number"] == 10


class TestGraphTraversalQuery:
    """Test GraphTraversalQuery model."""

    def test_query_defaults(self):
        """Test query with default values."""
        start_id = uuid4()
        query = GraphTraversalQuery(start_node_id=start_id)

        assert query.start_node_id == start_id
        assert query.direction == "outbound"
        assert query.relationship is None
        assert query.max_depth == 3
        assert query.limit == 50
        assert query.offset == 0

    def test_query_custom_values(self):
        """Test query with custom values."""
        query = GraphTraversalQuery(
            start_node_id=uuid4(),
            direction="inbound",
            relationship="calls",
            max_depth=5,
            limit=100,
            offset=50,
        )

        assert query.direction == "inbound"
        assert query.relationship == "calls"
        assert query.max_depth == 5
        assert query.limit == 100
        assert query.offset == 50

    def test_query_validation_max_depth(self):
        """Test max_depth validation."""
        # Should fail: max_depth > 10
        with pytest.raises(ValueError):
            GraphTraversalQuery(
                start_node_id=uuid4(),
                max_depth=15,
            )

        # Should fail: max_depth < 1
        with pytest.raises(ValueError):
            GraphTraversalQuery(
                start_node_id=uuid4(),
                max_depth=0,
            )

    def test_query_validation_limit(self):
        """Test limit validation."""
        # Should fail: limit > 500
        with pytest.raises(ValueError):
            GraphTraversalQuery(
                start_node_id=uuid4(),
                limit=600,
            )

        # Should fail: limit < 1
        with pytest.raises(ValueError):
            GraphTraversalQuery(
                start_node_id=uuid4(),
                limit=0,
            )


class TestGraphTraversalResponse:
    """Test GraphTraversalResponse model."""

    def test_response_empty(self):
        """Test response with no nodes."""
        metadata = GraphTraversalMetadata(
            start_node=uuid4(),
            direction="outbound",
            relationship="calls",
            max_depth=3,
            total_nodes=0,
            returned_nodes=0,
            limit=50,
            offset=0,
            has_more=False,
        )

        response = GraphTraversalResponse(
            success=True,
            message="No nodes found",
            nodes=[],
            metadata=metadata,
        )

        assert response.success is True
        assert len(response.nodes) == 0
        assert response.metadata.total_nodes == 0

    def test_response_with_nodes(self):
        """Test response with nodes."""
        nodes = [
            MCPNode(
                node_id=uuid4(),
                node_type="function",
                label=f"func_{i}",
                created_at=datetime.utcnow(),
            )
            for i in range(5)
        ]

        metadata = GraphTraversalMetadata(
            start_node=uuid4(),
            direction="outbound",
            relationship="calls",
            max_depth=3,
            total_nodes=10,
            returned_nodes=5,
            limit=5,
            offset=0,
            has_more=True,
        )

        response = GraphTraversalResponse(
            success=True,
            message="Found 10 nodes",
            nodes=nodes,
            metadata=metadata,
        )

        assert len(response.nodes) == 5
        assert response.metadata.total_nodes == 10
        assert response.metadata.has_more is True


class TestCallerCalleeModels:
    """Test caller/callee models."""

    def test_caller_callee_query(self):
        """Test CallerCalleeQuery model."""
        query = CallerCalleeQuery(
            qualified_name="module.ClassName.method",
            max_depth=2,
            relationship_type="calls",
            limit=20,
            offset=10,
        )

        assert query.qualified_name == "module.ClassName.method"
        assert query.max_depth == 2
        assert query.relationship_type == "calls"
        assert query.limit == 20
        assert query.offset == 10

    def test_caller_callee_response(self):
        """Test CallerCalleeResponse model."""
        nodes = [
            MCPNode(
                node_id=uuid4(),
                node_type="function",
                label=f"caller_{i}",
                created_at=datetime.utcnow(),
            )
            for i in range(3)
        ]

        metadata = CallerCalleeMetadata(
            qualified_name="test.func",
            direction="inbound",
            max_depth=3,
            total_found=10,
            returned_count=3,
            limit=3,
            offset=0,
            has_more=True,
        )

        response = CallerCalleeResponse(
            success=True,
            message="Found 10 callers",
            nodes=nodes,
            metadata=metadata,
        )

        assert len(response.nodes) == 3
        assert response.metadata.total_found == 10
        assert response.metadata.direction == "inbound"


class TestGraphNodeDetailsModels:
    """Test graph node details models."""

    def test_node_details_query(self):
        """Test GraphNodeDetailsQuery model."""
        query = GraphNodeDetailsQuery(
            chunk_id=uuid4(),
            include_callers=True,
            include_callees=False,
            max_neighbors=10,
        )

        assert query.include_callers is True
        assert query.include_callees is False
        assert query.max_neighbors == 10

    def test_node_neighbors(self):
        """Test GraphNodeNeighbors model."""
        callers = [
            MCPNode(
                node_id=uuid4(),
                node_type="function",
                label="caller",
                created_at=datetime.utcnow(),
            )
        ]

        callees = [
            MCPNode(
                node_id=uuid4(),
                node_type="function",
                label="callee",
                created_at=datetime.utcnow(),
            )
        ]

        edges = [
            MCPEdge(
                edge_id=uuid4(),
                source_node_id=uuid4(),
                target_node_id=uuid4(),
                relation_type="calls",
                created_at=datetime.utcnow(),
            )
        ]

        neighbors = GraphNodeNeighbors(
            callers=callers,
            callees=callees,
            edges=edges,
        )

        assert len(neighbors.callers) == 1
        assert len(neighbors.callees) == 1
        assert len(neighbors.edges) == 1

    def test_node_details_response(self):
        """Test GraphNodeDetailsResponse model."""
        node = MCPNode(
            node_id=uuid4(),
            node_type="function",
            label="test_func",
            created_at=datetime.utcnow(),
        )

        neighbors = GraphNodeNeighbors()

        response = GraphNodeDetailsResponse(
            success=True,
            message="Node details retrieved",
            node=node,
            neighbors=neighbors,
            metadata={"total_callers": 5, "total_callees": 3},
        )

        assert response.node.label == "test_func"
        assert response.metadata["total_callers"] == 5


class TestHelperFunctions:
    """Test helper functions."""

    def test_build_node_resource_links(self):
        """Test build_node_resource_links function."""
        node_id = uuid4()
        links = build_node_resource_links(
            node_id=node_id,
            node_type="function",
            label="test.func",
        )

        assert f"graph://nodes/{node_id}" in links
        assert "graph://callers/test.func" in links
        assert "graph://callees/test.func" in links

    def test_build_node_resource_links_module(self):
        """Test resource links for module (no callers/callees)."""
        node_id = uuid4()
        links = build_node_resource_links(
            node_id=node_id,
            node_type="module",
            label="test_module",
        )

        # Modules don't have caller/callee links
        assert f"graph://nodes/{node_id}" in links
        assert not any("callers" in link for link in links)
        assert not any("callees" in link for link in links)

    def test_build_pagination_links(self):
        """Test build_pagination_links function."""
        base_uri = "graph://callers/test.func?"
        links = build_pagination_links(
            base_uri=base_uri,
            limit=10,
            offset=10,
            total_count=50,
        )

        # Should have next, prev, first, last
        assert any("next_page" in link for link in links)
        assert any("prev_page" in link for link in links)
        assert any("first_page" in link for link in links)
        assert any("last_page" in link for link in links)

    def test_build_pagination_links_first_page(self):
        """Test pagination links for first page."""
        base_uri = "graph://test?"
        links = build_pagination_links(
            base_uri=base_uri,
            limit=10,
            offset=0,
            total_count=50,
        )

        # Should have next, first, last but not prev
        assert any("next_page" in link for link in links)
        assert not any("prev_page" in link for link in links)

    def test_build_pagination_links_last_page(self):
        """Test pagination links for last page."""
        base_uri = "graph://test?"
        links = build_pagination_links(
            base_uri=base_uri,
            limit=10,
            offset=40,
            total_count=50,
        )

        # Should have prev, first but not next
        assert not any("next_page" in link for link in links)
        assert any("prev_page" in link for link in links)

    def test_build_pagination_links_single_page(self):
        """Test pagination links when all results fit in one page."""
        base_uri = "graph://test?"
        links = build_pagination_links(
            base_uri=base_uri,
            limit=50,
            offset=0,
            total_count=10,
        )

        # No pagination links needed
        assert len(links) == 0
