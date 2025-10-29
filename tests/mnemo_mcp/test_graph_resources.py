"""
Unit tests for MCP Graph Resources (EPIC-23 Story 23.4).

Tests graph resource implementations with mocked services.
"""

import pytest
from datetime import datetime
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, MagicMock

from mnemo_mcp.resources.graph_resources import (
    GraphNodeDetailsResource,
    FindCallersResource,
    FindCalleesResource,
)
from models.graph_models import NodeModel, GraphTraversal


@pytest.fixture
def sample_node():
    """Sample NodeModel for testing."""
    return NodeModel(
        node_id=uuid4(),
        node_type="function",
        label="test.module.function_name",
        properties={
            "file_path": "/path/to/file.py",
            "line_number": 42,
            "chunk_id": str(uuid4()),
        },
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_nodes():
    """Sample list of nodes."""
    return [
        NodeModel(
            node_id=uuid4(),
            node_type="function",
            label=f"test.func_{i}",
            properties={"file_path": f"test_{i}.py"},
            created_at=datetime.utcnow(),
        )
        for i in range(5)
    ]


@pytest.fixture
def mock_node_repository():
    """Mock NodeRepository."""
    repo = MagicMock()
    repo.get_by_chunk_id = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.search_by_label = AsyncMock()
    return repo


@pytest.fixture
def mock_graph_service():
    """Mock GraphTraversalService."""
    service = MagicMock()
    service.traverse = AsyncMock()
    return service


class TestGraphNodeDetailsResource:
    """Test GraphNodeDetailsResource."""

    @pytest.mark.asyncio
    async def test_get_node_details_success(
        self,
        sample_node,
        sample_nodes,
        mock_node_repository,
        mock_graph_service,
    ):
        """Test successful node details retrieval."""
        # Setup mocks
        chunk_id = str(sample_node.properties["chunk_id"])
        mock_node_repository.get_by_chunk_id.return_value = sample_node

        # Mock callers (inbound)
        callers_result = GraphTraversal(
            start_node=sample_node.node_id,
            direction="inbound",
            relationship="any",
            max_depth=1,
            nodes=sample_nodes[:2],  # 2 callers
            total_nodes=2,
        )
        # Mock callees (outbound)
        callees_result = GraphTraversal(
            start_node=sample_node.node_id,
            direction="outbound",
            relationship="any",
            max_depth=1,
            nodes=sample_nodes[2:5],  # 3 callees
            total_nodes=3,
        )

        # Configure traverse mock to return different results based on direction
        async def traverse_side_effect(*args, **kwargs):
            if kwargs.get("direction") == "inbound":
                return callers_result
            else:
                return callees_result

        mock_graph_service.traverse.side_effect = traverse_side_effect

        # Create resource and inject services
        resource = GraphNodeDetailsResource()
        resource.inject_services({
            "node_repository": mock_node_repository,
            "graph_traversal_service": mock_graph_service,
        })

        # Execute
        response = await resource.get(chunk_id=chunk_id)

        # Verify
        assert response["success"] is True
        assert response["node"]["label"] == sample_node.label
        assert len(response["neighbors"]["callers"]) == 2
        assert len(response["neighbors"]["callees"]) == 3
        assert response["metadata"]["total_callers"] == 2
        assert response["metadata"]["total_callees"] == 3

        # Verify mocks called
        mock_node_repository.get_by_chunk_id.assert_called_once()
        assert mock_graph_service.traverse.call_count == 2  # Once for callers, once for callees

    @pytest.mark.asyncio
    async def test_get_node_details_invalid_chunk_id(
        self,
        mock_node_repository,
        mock_graph_service,
    ):
        """Test invalid chunk_id format."""
        resource = GraphNodeDetailsResource()
        resource.inject_services({
            "node_repository": mock_node_repository,
            "graph_traversal_service": mock_graph_service,
        })

        # Execute with invalid UUID
        response = await resource.get(chunk_id="not-a-uuid")

        # Verify
        assert response["success"] is False
        assert "Invalid chunk_id" in response["message"]

    @pytest.mark.asyncio
    async def test_get_node_details_not_found(
        self,
        mock_node_repository,
        mock_graph_service,
    ):
        """Test node not found."""
        chunk_id = str(uuid4())
        mock_node_repository.get_by_chunk_id.return_value = None
        mock_node_repository.get_by_id.return_value = None

        resource = GraphNodeDetailsResource()
        resource.inject_services({
            "node_repository": mock_node_repository,
            "graph_traversal_service": mock_graph_service,
        })

        # Execute
        response = await resource.get(chunk_id=chunk_id)

        # Verify
        assert response["success"] is False
        assert "Node not found" in response["message"]

    @pytest.mark.asyncio
    async def test_get_node_details_missing_services(self):
        """Test missing services."""
        resource = GraphNodeDetailsResource()
        resource.inject_services({})

        # Execute
        response = await resource.get(chunk_id=str(uuid4()))

        # Verify
        assert response["success"] is False
        assert "services not available" in response["message"]

    @pytest.mark.asyncio
    async def test_resource_links_generated(
        self,
        sample_node,
        mock_node_repository,
        mock_graph_service,
    ):
        """Test resource links are generated correctly."""
        chunk_id = str(sample_node.properties["chunk_id"])
        mock_node_repository.get_by_chunk_id.return_value = sample_node

        # Empty traversal results
        empty_result = GraphTraversal(
            start_node=sample_node.node_id,
            direction="inbound",
            relationship="any",
            max_depth=1,
            nodes=[],
            total_nodes=0,
        )
        mock_graph_service.traverse.return_value = empty_result

        resource = GraphNodeDetailsResource()
        resource.inject_services({
            "node_repository": mock_node_repository,
            "graph_traversal_service": mock_graph_service,
        })

        # Execute
        response = await resource.get(chunk_id=chunk_id)

        # Verify resource links
        assert "resource_links" in response
        assert len(response["resource_links"]) > 0
        assert any(f"graph://nodes/{sample_node.node_id}" in link for link in response["resource_links"])


class TestFindCallersResource:
    """Test FindCallersResource."""

    @pytest.mark.asyncio
    async def test_find_callers_success(
        self,
        sample_node,
        sample_nodes,
        mock_node_repository,
        mock_graph_service,
    ):
        """Test successful caller finding."""
        qualified_name = "test.module.function"
        mock_node_repository.search_by_label.return_value = [sample_node]

        # Mock inbound traversal (callers)
        callers_result = GraphTraversal(
            start_node=sample_node.node_id,
            direction="inbound",
            relationship="calls",
            max_depth=3,
            nodes=sample_nodes,
            total_nodes=5,
        )
        mock_graph_service.traverse.return_value = callers_result

        resource = FindCallersResource()
        resource.inject_services({
            "node_repository": mock_node_repository,
            "graph_traversal_service": mock_graph_service,
        })

        # Execute
        response = await resource.get(
            qualified_name=qualified_name,
            max_depth=3,
            relationship_type="calls",
            limit=50,
            offset=0,
        )

        # Verify
        assert response["success"] is True
        assert response["metadata"]["qualified_name"] == qualified_name
        assert response["metadata"]["direction"] == "inbound"
        assert response["metadata"]["total_found"] == 5
        assert len(response["nodes"]) == 5

        # Verify mock calls
        mock_node_repository.search_by_label.assert_called_once_with(qualified_name)
        mock_graph_service.traverse.assert_called_once_with(
            start_node_id=sample_node.node_id,
            direction="inbound",
            relationship="calls",
            max_depth=3,
        )

    @pytest.mark.asyncio
    async def test_find_callers_pagination(
        self,
        sample_node,
        sample_nodes,
        mock_node_repository,
        mock_graph_service,
    ):
        """Test pagination in caller finding."""
        qualified_name = "test.func"
        mock_node_repository.search_by_label.return_value = [sample_node]

        # Return 10 callers
        many_nodes = sample_nodes * 2
        callers_result = GraphTraversal(
            start_node=sample_node.node_id,
            direction="inbound",
            relationship="calls",
            max_depth=3,
            nodes=many_nodes,
            total_nodes=10,
        )
        mock_graph_service.traverse.return_value = callers_result

        resource = FindCallersResource()
        resource.inject_services({
            "node_repository": mock_node_repository,
            "graph_traversal_service": mock_graph_service,
        })

        # Execute with pagination
        response = await resource.get(
            qualified_name=qualified_name,
            limit=3,
            offset=2,
        )

        # Verify pagination
        assert response["metadata"]["total_found"] == 10
        assert response["metadata"]["returned_count"] == 3
        assert response["metadata"]["limit"] == 3
        assert response["metadata"]["offset"] == 2
        assert response["metadata"]["has_more"] is True

        # Verify resource links for pagination
        assert "resource_links" in response
        assert len(response["resource_links"]) > 0

    @pytest.mark.asyncio
    async def test_find_callers_node_not_found(
        self,
        mock_node_repository,
        mock_graph_service,
    ):
        """Test caller finding when node not found."""
        qualified_name = "nonexistent.func"
        mock_node_repository.search_by_label.return_value = []

        resource = FindCallersResource()
        resource.inject_services({
            "node_repository": mock_node_repository,
            "graph_traversal_service": mock_graph_service,
        })

        # Execute
        response = await resource.get(qualified_name=qualified_name)

        # Verify
        assert response["success"] is False
        assert "Node not found" in response["message"]
        assert response["metadata"]["total_found"] == 0

    @pytest.mark.asyncio
    async def test_find_callers_missing_services(self):
        """Test missing services."""
        resource = FindCallersResource()
        resource.inject_services({})

        # Execute
        response = await resource.get(qualified_name="test.func")

        # Verify
        assert response["success"] is False
        assert "services not available" in response["message"]


class TestFindCalleesResource:
    """Test FindCalleesResource."""

    @pytest.mark.asyncio
    async def test_find_callees_success(
        self,
        sample_node,
        sample_nodes,
        mock_node_repository,
        mock_graph_service,
    ):
        """Test successful callee finding."""
        qualified_name = "test.module.function"
        mock_node_repository.search_by_label.return_value = [sample_node]

        # Mock outbound traversal (callees)
        callees_result = GraphTraversal(
            start_node=sample_node.node_id,
            direction="outbound",
            relationship="calls",
            max_depth=3,
            nodes=sample_nodes,
            total_nodes=5,
        )
        mock_graph_service.traverse.return_value = callees_result

        resource = FindCalleesResource()
        resource.inject_services({
            "node_repository": mock_node_repository,
            "graph_traversal_service": mock_graph_service,
        })

        # Execute
        response = await resource.get(
            qualified_name=qualified_name,
            max_depth=3,
            relationship_type="calls",
            limit=50,
            offset=0,
        )

        # Verify
        assert response["success"] is True
        assert response["metadata"]["qualified_name"] == qualified_name
        assert response["metadata"]["direction"] == "outbound"
        assert response["metadata"]["total_found"] == 5
        assert len(response["nodes"]) == 5

        # Verify mock calls
        mock_graph_service.traverse.assert_called_once_with(
            start_node_id=sample_node.node_id,
            direction="outbound",
            relationship="calls",
            max_depth=3,
        )

    @pytest.mark.asyncio
    async def test_find_callees_empty_result(
        self,
        sample_node,
        mock_node_repository,
        mock_graph_service,
    ):
        """Test callee finding with no results."""
        qualified_name = "test.leaf_function"
        mock_node_repository.search_by_label.return_value = [sample_node]

        # Empty traversal result (leaf function calls nothing)
        empty_result = GraphTraversal(
            start_node=sample_node.node_id,
            direction="outbound",
            relationship="calls",
            max_depth=3,
            nodes=[],
            total_nodes=0,
        )
        mock_graph_service.traverse.return_value = empty_result

        resource = FindCalleesResource()
        resource.inject_services({
            "node_repository": mock_node_repository,
            "graph_traversal_service": mock_graph_service,
        })

        # Execute
        response = await resource.get(qualified_name=qualified_name)

        # Verify
        assert response["success"] is True
        assert response["metadata"]["total_found"] == 0
        assert len(response["nodes"]) == 0
        assert response["metadata"]["has_more"] is False

    @pytest.mark.asyncio
    async def test_find_callees_multiple_matches(
        self,
        sample_nodes,
        mock_node_repository,
        mock_graph_service,
    ):
        """Test callee finding when multiple nodes match the name."""
        qualified_name = "test.common_name"
        # Return multiple matches (e.g., same function name in different modules)
        mock_node_repository.search_by_label.return_value = sample_nodes[:2]

        # Should use first match
        first_node = sample_nodes[0]
        callees_result = GraphTraversal(
            start_node=first_node.node_id,
            direction="outbound",
            relationship="calls",
            max_depth=3,
            nodes=[sample_nodes[2]],
            total_nodes=1,
        )
        mock_graph_service.traverse.return_value = callees_result

        resource = FindCalleesResource()
        resource.inject_services({
            "node_repository": mock_node_repository,
            "graph_traversal_service": mock_graph_service,
        })

        # Execute
        response = await resource.get(qualified_name=qualified_name)

        # Verify - should use first match
        assert response["success"] is True
        mock_graph_service.traverse.assert_called_once()
        call_args = mock_graph_service.traverse.call_args
        assert call_args.kwargs["start_node_id"] == first_node.node_id


class TestResourceIntegration:
    """Integration tests for graph resources."""

    @pytest.mark.asyncio
    async def test_all_resources_return_json_serializable(
        self,
        sample_node,
        sample_nodes,
        mock_node_repository,
        mock_graph_service,
    ):
        """Test all resources return JSON-serializable responses."""
        import json

        chunk_id = str(sample_node.properties["chunk_id"])
        qualified_name = "test.func"

        mock_node_repository.get_by_chunk_id.return_value = sample_node
        mock_node_repository.search_by_label.return_value = [sample_node]

        empty_result = GraphTraversal(
            start_node=sample_node.node_id,
            direction="inbound",
            relationship="any",
            max_depth=1,
            nodes=[],
            total_nodes=0,
        )
        mock_graph_service.traverse.return_value = empty_result

        # Test GraphNodeDetailsResource
        resource1 = GraphNodeDetailsResource()
        resource1.inject_services({
            "node_repository": mock_node_repository,
            "graph_traversal_service": mock_graph_service,
        })
        response1 = await resource1.get(chunk_id=chunk_id)
        json.dumps(response1)  # Should not raise

        # Test FindCallersResource
        resource2 = FindCallersResource()
        resource2.inject_services({
            "node_repository": mock_node_repository,
            "graph_traversal_service": mock_graph_service,
        })
        response2 = await resource2.get(qualified_name=qualified_name)
        json.dumps(response2)  # Should not raise

        # Test FindCalleesResource
        resource3 = FindCalleesResource()
        resource3.inject_services({
            "node_repository": mock_node_repository,
            "graph_traversal_service": mock_graph_service,
        })
        response3 = await resource3.get(qualified_name=qualified_name)
        json.dumps(response3)  # Should not raise
