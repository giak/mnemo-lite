"""
Integration tests for CodeChunkRepository (EPIC-06 Phase 1 Story 2bis).

Tests CRUD operations, vector search, and similarity search.
"""

import pytest
import pytest_asyncio
import uuid
from datetime import datetime

from db.repositories.code_chunk_repository import CodeChunkRepository
from models.code_chunk_models import CodeChunkCreate, CodeChunkUpdate, ChunkType


@pytest_asyncio.fixture
async def code_chunk_repo(test_engine):
    """Get CodeChunkRepository with test engine."""
    return CodeChunkRepository(engine=test_engine)


@pytest.fixture
def sample_chunk_create():
    """Create sample CodeChunkCreate data."""
    return CodeChunkCreate(
        file_path="src/utils/calculator.py",
        language="python",
        chunk_type=ChunkType.FUNCTION,
        name="calculate_total",
        source_code="def calculate_total(items):\n    return sum(item.price for item in items)",
        start_line=10,
        end_line=12,
        embedding_text=[0.1] * 768,  # Mock embedding
        embedding_code=[0.2] * 768,  # Mock embedding
        metadata={"complexity": {"cyclomatic": 2}, "parameters": ["items"]},
        repository="my-project",
        commit_hash="abc123"
    )


# Test 1: Create code chunk

@pytest.mark.asyncio
async def test_add_code_chunk(code_chunk_repo, sample_chunk_create):
    """Test adding a new code chunk."""
    chunk = await code_chunk_repo.add(sample_chunk_create)

    # Verify
    assert chunk.id is not None
    assert chunk.name == "calculate_total"
    assert chunk.language == "python"
    assert chunk.chunk_type == ChunkType.FUNCTION
    assert len(chunk.embedding_text) == 768
    assert len(chunk.embedding_code) == 768
    assert chunk.indexed_at is not None


# Test 2: Get by ID

@pytest.mark.asyncio
async def test_get_by_id(code_chunk_repo, sample_chunk_create):
    """Test getting code chunk by ID."""
    # Create first
    created = await code_chunk_repo.add(sample_chunk_create)

    # Get by ID
    retrieved = await code_chunk_repo.get_by_id(created.id)

    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.name == created.name
    assert retrieved.source_code == created.source_code


# Test 3: Get by ID (not found)

@pytest.mark.asyncio
async def test_get_by_id_not_found(code_chunk_repo):
    """Test getting non-existent chunk returns None."""
    fake_id = uuid.uuid4()
    chunk = await code_chunk_repo.get_by_id(fake_id)
    assert chunk is None


# Test 4: Update code chunk

@pytest.mark.asyncio
async def test_update_code_chunk(code_chunk_repo, sample_chunk_create):
    """Test updating code chunk."""
    # Create first
    created = await code_chunk_repo.add(sample_chunk_create)

    # Update
    update_data = CodeChunkUpdate(
        source_code="def calculate_total(items):\n    # Updated\n    return sum(item.price for item in items)",
        metadata={"updated": True},
    )
    updated = await code_chunk_repo.update(created.id, update_data)

    assert updated is not None
    assert "Updated" in updated.source_code
    assert updated.metadata["updated"] is True
    assert updated.metadata["complexity"] == {"cyclomatic": 2}  # Original metadata preserved
    assert updated.last_modified is not None


# Test 5: Delete code chunk

@pytest.mark.asyncio
async def test_delete_code_chunk(code_chunk_repo, sample_chunk_create):
    """Test deleting code chunk."""
    # Create first
    created = await code_chunk_repo.add(sample_chunk_create)

    # Delete
    deleted = await code_chunk_repo.delete(created.id)
    assert deleted is True

    # Verify deleted
    chunk = await code_chunk_repo.get_by_id(created.id)
    assert chunk is None


# Test 6: Vector search (embedding_code)

@pytest.mark.asyncio
async def test_search_vector_code_embedding(code_chunk_repo, sample_chunk_create):
    """Test vector search using embedding_code."""
    # Create multiple chunks
    await code_chunk_repo.add(sample_chunk_create)

    chunk2 = CodeChunkCreate(
        file_path="src/utils/processor.py",
        language="python",
        chunk_type=ChunkType.FUNCTION,
        name="process_data",
        source_code="def process_data(data): pass",
        embedding_text=[0.3] * 768,
        embedding_code=[0.25] * 768,  # Similar to sample_chunk_create
        metadata={},
        repository="my-project",
    )
    await code_chunk_repo.add(chunk2)

    # Search with embedding similar to sample_chunk_create
    query_embedding = [0.21] * 768  # Close to 0.2
    results = await code_chunk_repo.search_vector(
        embedding=query_embedding,
        embedding_type="code",
        language="python",
        limit=10,
    )

    assert len(results) >= 1
    assert all(chunk.language == "python" for chunk in results)


# Test 7: Vector search with filters

@pytest.mark.asyncio
async def test_search_vector_with_filters(code_chunk_repo, sample_chunk_create):
    """Test vector search with language and chunk_type filters."""
    # Create chunk
    await code_chunk_repo.add(sample_chunk_create)

    # Search with filters
    query_embedding = [0.2] * 768
    results = await code_chunk_repo.search_vector(
        embedding=query_embedding,
        embedding_type="code",
        language="python",
        chunk_type="function",
        limit=10,
    )

    assert all(chunk.language == "python" for chunk in results)
    assert all(chunk.chunk_type == ChunkType.FUNCTION for chunk in results)


# Test 8: Similarity search (pg_trgm)

@pytest.mark.asyncio
async def test_search_similarity_pg_trgm(code_chunk_repo, sample_chunk_create):
    """Test pg_trgm similarity search."""
    # Create chunk
    await code_chunk_repo.add(sample_chunk_create)

    # Search for similar text
    results = await code_chunk_repo.search_similarity(
        query="calculate total",
        language="python",
        threshold=0.1,
        limit=10,
    )

    assert len(results) >= 1
    assert any("calculate" in chunk.source_code.lower() for chunk in results)


# Test 9: Vector search invalid embedding dimension

@pytest.mark.asyncio
async def test_search_vector_invalid_dimension(code_chunk_repo):
    """Test that invalid embedding dimension raises ValueError."""
    invalid_embedding = [0.1] * 512  # Wrong dimension

    with pytest.raises(ValueError, match="Embedding must be 768D"):
        await code_chunk_repo.search_vector(
            embedding=invalid_embedding,
            embedding_type="code",
        )


# Test 10: Update with no fields raises ValueError

@pytest.mark.asyncio
async def test_update_no_fields(code_chunk_repo, sample_chunk_create):
    """Test that updating with no fields raises ValueError."""
    # Create chunk
    created = await code_chunk_repo.add(sample_chunk_create)

    # Try to update with empty data
    update_data = CodeChunkUpdate()

    with pytest.raises(ValueError, match="No fields to update"):
        await code_chunk_repo.update(created.id, update_data)
