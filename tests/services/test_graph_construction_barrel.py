"""Tests for barrel node creation in graph (EPIC-29 Task 5)."""
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock
from api.services.graph_construction_service import GraphConstructionService
from api.models.code_chunk_models import CodeChunk, ChunkType


@pytest.fixture
def mock_engine():
    """Create a mock database engine."""
    return MagicMock()


@pytest.mark.asyncio
async def test_create_barrel_node(mock_engine):
    """Barrel chunks should create Module nodes with is_barrel=True."""
    graph_service = GraphConstructionService(mock_engine)

    barrel_chunk = CodeChunk(
        file_path="packages/shared/src/index.ts",
        language="typescript",
        chunk_type=ChunkType.BARREL,
        name="shared",
        source_code="export { createSuccess } from './utils/result.utils';",
        start_line=1,
        end_line=1,
        repository="CVGenerator",
        metadata={
            "re_exports": [
                {"symbol": "createSuccess", "source": "./utils/result.utils"},
                {"symbol": "Success", "source": "./types/result.type"},
            ]
        }
    )

    # Create node
    node = await graph_service._create_node_from_chunk(barrel_chunk)

    # Verify node properties
    assert node["label"] == "shared"
    assert node["node_type"] == "Module"  # Barrels are Module nodes
    assert node["properties"]["chunk_id"] == str(barrel_chunk.id)
    assert node["properties"]["node_type"] == "Module"
    assert node["properties"]["is_barrel"] is True
    assert len(node["properties"]["re_exports"]) == 2


@pytest.mark.asyncio
async def test_create_reexport_edges(mock_engine):
    """Re-exports should create edges to original symbols."""
    graph_service = GraphConstructionService(mock_engine)

    # Barrel chunk
    barrel_chunk = CodeChunk(
        id=uuid4(),
        file_path="packages/shared/src/index.ts",
        language="typescript",
        chunk_type=ChunkType.BARREL,
        name="shared",
        source_code="export { createSuccess } from './utils/result.utils';",
        start_line=1,
        end_line=1,
        repository="CVGenerator",
        metadata={
            "re_exports": [
                {"symbol": "createSuccess", "source": "./utils/result.utils"},
            ]
        }
    )

    # Original function chunk (already in graph)
    function_chunk = CodeChunk(
        id=uuid4(),
        file_path="packages/shared/src/utils/result.utils.ts",
        language="typescript",
        chunk_type=ChunkType.FUNCTION,
        name="createSuccess",
        source_code="export function createSuccess() { ... }",
        start_line=1,
        end_line=3,
        repository="CVGenerator",
        metadata={"imports": [], "calls": []}
    )

    # Mock: Assume both nodes exist in graph
    # Build edges
    edges = await graph_service._create_reexport_edges(
        barrel_chunk, [function_chunk]
    )

    # Should create 1 edge: shared -> createSuccess
    assert len(edges) == 1
    assert edges[0]["edge_type"] == "re_exports"
    assert edges[0]["properties"]["symbol"] == "createSuccess"


@pytest.mark.asyncio
async def test_filter_anonymous_functions(mock_engine):
    """
    Anonymous functions should be filtered out from graph nodes.

    EPIC-30: Reduce visual noise by filtering 413/581 anonymous nodes.
    """
    # Setup mocks
    graph_service = GraphConstructionService(mock_engine)

    # Mock node repository to track what nodes would be created
    created_nodes = []

    class MockNode:
        def __init__(self, node_id, node_type, label, properties):
            self.node_id = node_id
            self.node_type = node_type
            self.label = label
            self.properties = properties

    async def mock_create_node(**kwargs):
        node = MockNode(
            node_id=uuid4(),
            node_type=kwargs["node_type"],
            label=kwargs["label"],
            properties=kwargs.get("metadata", {})
        )
        created_nodes.append(node)
        return node

    graph_service.node_repo = AsyncMock()
    graph_service.node_repo.create_code_node = mock_create_node

    # Create test chunks: 2 named functions + 3 anonymous functions
    chunks = [
        # Named function - should be included
        CodeChunk(
            id=uuid4(),
            file_path="src/validation.ts",
            language="typescript",
            chunk_type=ChunkType.FUNCTION,
            name="validateResume",
            source_code="function validateResume() { ... }",
            start_line=10,
            end_line=20,
            repository="CVGenerator",
            metadata={"imports": [], "calls": []}
        ),
        # Anonymous arrow function - should be filtered
        CodeChunk(
            id=uuid4(),
            file_path="src/test.spec.ts",
            language="typescript",
            chunk_type=ChunkType.ARROW_FUNCTION,
            name="anonymous_arrow_function",
            source_code="() => { expect(1).toBe(1) }",
            start_line=5,
            end_line=7,
            repository="CVGenerator",
            metadata={"imports": [], "calls": []}
        ),
        # Named method - should be included
        CodeChunk(
            id=uuid4(),
            file_path="src/Resume.ts",
            language="typescript",
            chunk_type=ChunkType.METHOD,
            name="getErrors",
            source_code="getErrors() { ... }",
            start_line=15,
            end_line=18,
            repository="CVGenerator",
            metadata={"imports": [], "calls": []}
        ),
        # Anonymous method - should be filtered
        CodeChunk(
            id=uuid4(),
            file_path="src/test.spec.ts",
            language="typescript",
            chunk_type=ChunkType.METHOD,
            name="anonymous_method_definition",
            source_code="() => { ... }",
            start_line=25,
            end_line=27,
            repository="CVGenerator",
            metadata={"imports": [], "calls": []}
        ),
        # Another anonymous - should be filtered
        CodeChunk(
            id=uuid4(),
            file_path="src/callbacks.ts",
            language="typescript",
            chunk_type=ChunkType.FUNCTION,
            name="anonymous_function",
            source_code="function() { ... }",
            start_line=30,
            end_line=32,
            repository="CVGenerator",
            metadata={"imports": [], "calls": []}
        ),
    ]

    # Create nodes from chunks
    chunk_to_node = await graph_service._create_nodes_from_chunks(chunks, connection=None)

    # Verify only named functions created nodes (2 nodes, not 5)
    assert len(chunk_to_node) == 2
    assert len(created_nodes) == 2

    # Verify the correct chunks were included
    created_names = [node.label for node in created_nodes]
    assert "validateResume" in created_names
    assert "getErrors" in created_names

    # Verify anonymous functions were filtered
    assert "anonymous_arrow_function" not in created_names
    assert "anonymous_method_definition" not in created_names
    assert "anonymous_function" not in created_names
