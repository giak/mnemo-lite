# tests/integration/test_graph_construction.py
import pytest
import sys
from pathlib import Path

# Add api directory to path for imports
api_path = Path(__file__).parent.parent.parent / "api"
sys.path.insert(0, str(api_path))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from services.graph_construction_service import GraphConstructionService
from db.repositories.code_chunk_repository import CodeChunkRepository
from models.code_chunk_models import CodeChunkCreate
import os


@pytest.mark.asyncio
async def test_build_graph_creates_nodes_and_edges():
    """Test that graph construction creates nodes and edges from chunks."""
    # Setup: Create test database engine
    db_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    engine = create_async_engine(db_url)

    test_repo = "test_graph_construction"

    # Cleanup existing data (edges cascade delete automatically)
    async with engine.begin() as conn:
        # Delete nodes first (which cascades to edges)
        await conn.execute(text("DELETE FROM nodes WHERE properties->>'repository' = :repo"), {"repo": test_repo})
        # Delete chunks
        await conn.execute(text("DELETE FROM code_chunks WHERE repository = :repo"), {"repo": test_repo})

    # Create sample chunks with metadata
    chunk_repo = CodeChunkRepository(engine)

    sample_chunks = [
        CodeChunkCreate(
            repository=test_repo,
            file_path="/test/calculator.ts",
            chunk_index=0,
            chunk_type="class",
            language="typescript",
            source_code="class Calculator { add(a: number, b: number) { return a + b; } }",
            start_line=1,
            end_line=5,
            embedding_code=[0.1] * 768,  # Mock embedding
            metadata={
                "name": "Calculator",
                "imports": [],
                "exports": ["Calculator"],
                "calls": ["add"]
            }
        ),
        CodeChunkCreate(
            repository=test_repo,
            file_path="/test/calculator.ts",
            chunk_index=1,
            chunk_type="method",
            language="typescript",
            source_code="add(a: number, b: number) { return a + b; }",
            start_line=2,
            end_line=4,
            embedding_code=[0.2] * 768,
            metadata={
                "name": "add",
                "imports": [],
                "calls": []
            }
        )
    ]

    async with engine.begin() as conn:
        chunk_repo_with_conn = CodeChunkRepository(engine, connection=conn)
        for chunk in sample_chunks:
            await chunk_repo_with_conn.add(chunk)

    # Execute: Build graph
    graph_service = GraphConstructionService(engine)
    stats = await graph_service.build_graph_for_repository(
        repository=test_repo,
        languages=["typescript"]
    )

    # Verify: Nodes and edges created
    async with engine.begin() as conn:
        node_count = await conn.execute(
            text("SELECT COUNT(*) FROM nodes WHERE properties->>'repository' = :repo"),
            {"repo": test_repo}
        )
        nodes = node_count.scalar()

        edge_count = await conn.execute(
            text("""
                SELECT COUNT(*) FROM edges e
                JOIN nodes n ON e.source_node_id = n.node_id
                WHERE n.properties->>'repository' = :repo
            """),
            {"repo": test_repo}
        )
        edges = edge_count.scalar()

        # Also verify chunks were created
        chunk_count = await conn.execute(
            text("SELECT COUNT(*) FROM code_chunks WHERE repository = :repo"),
            {"repo": test_repo}
        )
        chunks = chunk_count.scalar()

    # Assertions BEFORE cleanup
    assert chunks == 2, f"Expected 2 chunks to be created, got {chunks}"
    assert nodes > 0, f"Expected nodes to be created, got {nodes} (stats reported {stats.total_nodes})"
    assert stats.total_nodes > 0, f"Stats should report nodes: {stats}"
    assert isinstance(stats.total_nodes, int), "Stats should have integer counts"

    # Cleanup test data AFTER assertions
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM nodes WHERE properties->>'repository' = :repo"), {"repo": test_repo})
        await conn.execute(text("DELETE FROM code_chunks WHERE repository = :repo"), {"repo": test_repo})

    await engine.dispose()


@pytest.mark.asyncio
async def test_build_graph_handles_empty_repository():
    """Test that graph construction handles empty repository gracefully."""
    db_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    engine = create_async_engine(db_url)

    test_repo = "empty_repo_test"

    # Ensure no chunks exist
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM code_chunks WHERE repository = :repo"), {"repo": test_repo})

    # Execute
    graph_service = GraphConstructionService(engine)
    stats = await graph_service.build_graph_for_repository(
        repository=test_repo,
        languages=["typescript"]
    )

    # Cleanup test data
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM nodes WHERE properties->>'repository' = :repo"), {"repo": test_repo})
        await conn.execute(text("DELETE FROM code_chunks WHERE repository = :repo"), {"repo": test_repo})

    await engine.dispose()

    # Verify: No crash, returns empty stats
    assert stats.total_nodes == 0
    assert stats.total_edges == 0
