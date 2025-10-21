"""
Integration tests for EPIC-12 Story 12.2: Transaction Boundaries.

Tests verify that all database operations use transactions correctly and
that rollback works when operations fail.
"""

import pytest
import uuid
from sqlalchemy.ext.asyncio import AsyncEngine

from db.repositories.code_chunk_repository import CodeChunkRepository
from db.repositories.node_repository import NodeRepository
from db.repositories.edge_repository import EdgeRepository
from models.code_chunk_models import CodeChunkCreate, ChunkType
from models.graph_models import NodeCreate


@pytest.mark.anyio
async def test_chunk_repository_transaction_rollback(test_engine: AsyncEngine):
    """
    Test that chunk repository operations roll back on transaction failure.

    EPIC-12 Story 12.2: Transaction rollback should prevent partial commits.
    """
    chunk_repo = CodeChunkRepository(test_engine)
    async_engine = test_engine

    # Prepare test data
    chunk_data = CodeChunkCreate(
        file_path="test.py",
        language="python",
        chunk_type=ChunkType.FUNCTION,
        name="test_function",
        name_path="test.test_function",
        source_code="def test_function(): pass",
        start_line=1,
        end_line=1,
        embedding_text=[0.1] * 768,
        embedding_code=[0.2] * 768,
        metadata={"test": "data"},
        repository="test_repo",
    )

    try:
        # Use transaction and deliberately cause it to fail
        async with async_engine.begin() as conn:
            # Add chunk
            chunk = await chunk_repo.add(chunk_data, connection=conn)
            assert chunk is not None

            # Deliberately raise error to trigger rollback
            raise ValueError("Deliberate error for testing rollback")

    except ValueError:
        # Expected error, transaction should have rolled back
        pass

    # Verify chunk was NOT persisted (transaction rolled back)
    async with async_engine.begin() as conn:
        from sqlalchemy import text
        result = await conn.execute(
            text("SELECT COUNT(*) FROM code_chunks WHERE name = 'test_function'")
        )
        count = result.scalar()
        assert count == 0, "Chunk should not exist after rollback"


@pytest.mark.anyio
async def test_node_repository_transaction_commit(test_engine: AsyncEngine):
    """
    Test that node repository operations commit successfully in transaction.

    EPIC-12 Story 12.2: Successful transaction should persist all changes.
    """
    async_engine = test_engine
    node_repo = NodeRepository(async_engine)

    # Prepare test data
    node_data = NodeCreate(
        node_type="function",
        label="test_node",
        properties={"test": "data"},
    )

    # Use transaction and let it commit successfully
    node_id = None
    async with async_engine.begin() as conn:
        # Create node
        node = await node_repo.create(node_data, connection=conn)
        assert node is not None
        node_id = node.node_id

    # Verify node was persisted (transaction committed)
    async with async_engine.begin() as conn:
        from sqlalchemy import text
        result = await conn.execute(
            text(f"SELECT COUNT(*) FROM nodes WHERE node_id = '{node_id}'")
        )
        count = result.scalar()
        assert count == 1, "Node should exist after successful commit"

    # Cleanup
    async with async_engine.begin() as conn:
        await conn.execute(
            text(f"DELETE FROM nodes WHERE node_id = '{node_id}'")
        )


@pytest.mark.anyio
async def test_batch_insert_transaction(test_engine: AsyncEngine):
    """
    Test that batch insert operations use transactions correctly.

    EPIC-12 Story 12.2: Batch operations should be atomic (all-or-nothing).
    """
    async_engine = test_engine
    chunk_repo = CodeChunkRepository(async_engine)

    # Prepare batch test data
    chunks_data = [
        CodeChunkCreate(
            file_path="batch_test.py",
            language="python",
            chunk_type=ChunkType.FUNCTION,
            name=f"test_function_{i}",
            name_path=f"test.test_function_{i}",
            source_code=f"def test_function_{i}(): pass",
            start_line=i,
            end_line=i,
            embedding_text=[0.1] * 768,
            embedding_code=[0.2] * 768,
            metadata={"index": i},
            repository="batch_test_repo",
        )
        for i in range(5)
    ]

    # Use transaction for batch insert
    async with async_engine.begin() as conn:
        rows_affected = await chunk_repo.add_batch(chunks_data, connection=conn)
        assert rows_affected == 5, "Should insert all 5 chunks"

    # Verify all chunks were persisted
    async with async_engine.begin() as conn:
        from sqlalchemy import text
        result = await conn.execute(
            text("SELECT COUNT(*) FROM code_chunks WHERE repository = 'batch_test_repo'")
        )
        count = result.scalar()
        assert count == 5, "All 5 chunks should exist after commit"

    # Cleanup
    async with async_engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM code_chunks WHERE repository = 'batch_test_repo'")
        )


@pytest.mark.anyio
async def test_graph_construction_transaction(test_engine: AsyncEngine):
    """
    Test that graph construction uses transactions correctly.

    EPIC-12 Story 12.2: Multiple node and edge creations should be atomic.
    """
    async_engine = test_engine
    node_repo = NodeRepository(async_engine)
    edge_repo = EdgeRepository(async_engine)

    # Create test nodes and edges in transaction
    node_ids = []
    async with async_engine.begin() as conn:
        # Create 2 nodes
        for i in range(2):
            node_data = NodeCreate(
                node_type="function",
                label=f"graph_test_node_{i}",
                properties={"test": "graph"},
            )
            node = await node_repo.create(node_data, connection=conn)
            node_ids.append(node.node_id)

        # Create edge between them
        from models.graph_models import EdgeCreate
        edge_data = EdgeCreate(
            source_node_id=node_ids[0],
            target_node_id=node_ids[1],
            relation_type="calls",
            properties={"test": "edge"},
        )
        edge = await edge_repo.create(edge_data, connection=conn)
        assert edge is not None

    # Verify all graph elements were persisted
    async with async_engine.begin() as conn:
        from sqlalchemy import text
        result = await conn.execute(
            text(f"SELECT COUNT(*) FROM nodes WHERE node_id IN ('{node_ids[0]}', '{node_ids[1]}')")
        )
        node_count = result.scalar()
        assert node_count == 2, "Both nodes should exist"

        result = await conn.execute(
            text(f"SELECT COUNT(*) FROM edges WHERE source_node_id = '{node_ids[0]}'")
        )
        edge_count = result.scalar()
        assert edge_count == 1, "Edge should exist"

    # Cleanup
    async with async_engine.begin() as conn:
        await conn.execute(
            text(f"DELETE FROM edges WHERE source_node_id = '{node_ids[0]}'")
        )
        await conn.execute(
            text(f"DELETE FROM nodes WHERE node_id IN ('{node_ids[0]}', '{node_ids[1]}')")
        )
