import pytest
import uuid
from sqlalchemy.sql import text
from db.repositories.computed_metrics_repository import ComputedMetricsRepository


@pytest.mark.asyncio
async def test_create_computed_metrics(clean_db):
    """Test creating computed metrics."""
    repo = ComputedMetricsRepository(clean_db)

    # Create sample node and chunk IDs
    sample_node_id = uuid.uuid4()
    sample_chunk_id = uuid.uuid4()

    # Create prerequisite node and chunk in database
    async with clean_db.begin() as conn:
        # Create node
        await conn.execute(text("""
            INSERT INTO nodes (node_id, label, node_type, properties)
            VALUES (:node_id, 'testFunc', 'function', '{"repository": "test_repo"}'::jsonb)
        """), {"node_id": str(sample_node_id)})

        # Create chunk
        await conn.execute(text("""
            INSERT INTO code_chunks (id, file_path, language, chunk_type, source_code, metadata, indexed_at)
            VALUES (:chunk_id, '/test.ts', 'typescript', 'function', 'test code', '{}'::jsonb, NOW())
        """), {"chunk_id": str(sample_chunk_id)})

    metrics = await repo.create(
        node_id=sample_node_id,
        chunk_id=sample_chunk_id,
        repository="test_repo",
        cyclomatic_complexity=5,
        cognitive_complexity=3,
        lines_of_code=50,
        afferent_coupling=2,
        efferent_coupling=4
    )

    assert metrics.cyclomatic_complexity == 5
    assert metrics.afferent_coupling == 2
    assert metrics.repository == "test_repo"


@pytest.mark.asyncio
async def test_update_coupling_metrics(clean_db):
    """Test updating coupling metrics after graph analysis."""
    repo = ComputedMetricsRepository(clean_db)

    # Create sample node and chunk IDs
    sample_node_id = uuid.uuid4()
    sample_chunk_id = uuid.uuid4()

    # Create prerequisite node and chunk in database
    async with clean_db.begin() as conn:
        # Create node
        await conn.execute(text("""
            INSERT INTO nodes (node_id, label, node_type, properties)
            VALUES (:node_id, 'testFunc', 'function', '{"repository": "test_repo"}'::jsonb)
        """), {"node_id": str(sample_node_id)})

        # Create chunk
        await conn.execute(text("""
            INSERT INTO code_chunks (id, file_path, language, chunk_type, source_code, metadata, indexed_at)
            VALUES (:chunk_id, '/test.ts', 'typescript', 'function', 'test code', '{}'::jsonb, NOW())
        """), {"chunk_id": str(sample_chunk_id)})

    # Create initial
    metrics = await repo.create(sample_node_id, sample_chunk_id, "test_repo")

    # Update coupling
    updated = await repo.update_coupling(
        node_id=sample_node_id,
        afferent_coupling=10,
        efferent_coupling=5
    )

    assert updated.afferent_coupling == 10
    assert updated.efferent_coupling == 5
