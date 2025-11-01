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
