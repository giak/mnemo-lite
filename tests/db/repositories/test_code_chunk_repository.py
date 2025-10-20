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


# ============================================================================
# EPIC-11 Story 11.1: name_path Storage Tests (Fix #2)
# ============================================================================


@pytest.fixture
def sample_chunk_with_name_path():
    """Create sample CodeChunkCreate with name_path."""
    return CodeChunkCreate(
        file_path="api/models/user.py",
        language="python",
        chunk_type=ChunkType.METHOD,
        name="validate",
        name_path="models.user.User.validate",  # EPIC-11: Hierarchical name
        source_code="def validate(self):\n    return self.email is not None",
        start_line=20,
        end_line=22,
        embedding_text=[0.1] * 768,
        embedding_code=[0.2] * 768,
        metadata={"complexity": {"cyclomatic": 1}},
        repository="my-project",
        commit_hash="def456"
    )


# Test 11: Create chunk with name_path

@pytest.mark.asyncio
async def test_add_code_chunk_with_name_path(code_chunk_repo, sample_chunk_with_name_path):
    """
    FIX #2: Test creating code chunk with name_path field.

    Verifies:
    - name_path is stored in database
    - name_path is retrieved correctly
    - All other fields remain intact
    """
    chunk = await code_chunk_repo.add(sample_chunk_with_name_path)

    # Verify name_path is stored
    assert chunk.id is not None
    assert chunk.name == "validate"
    assert chunk.name_path == "models.user.User.validate"
    assert chunk.file_path == "api/models/user.py"
    assert chunk.chunk_type == ChunkType.METHOD


# Test 12: Retrieve chunk with name_path

@pytest.mark.asyncio
async def test_get_chunk_with_name_path(code_chunk_repo, sample_chunk_with_name_path):
    """
    FIX #2: Test retrieving chunk with name_path from database.

    Verifies round-trip storage: CREATE → GET → name_path preserved.
    """
    # Create
    created = await code_chunk_repo.add(sample_chunk_with_name_path)

    # Retrieve
    retrieved = await code_chunk_repo.get_by_id(created.id)

    assert retrieved is not None
    assert retrieved.name_path == "models.user.User.validate"
    assert retrieved.name == "validate"


# Test 13: Update name_path

@pytest.mark.asyncio
async def test_update_name_path(code_chunk_repo, sample_chunk_with_name_path):
    """
    FIX #2: Test updating name_path field.

    Scenario: Regenerating name_path after file refactoring.
    """
    # Create
    created = await code_chunk_repo.add(sample_chunk_with_name_path)

    # Update name_path (e.g., after refactoring file moved to different module)
    update_data = CodeChunkUpdate(
        name_path="refactored.models.user.User.validate"
    )
    updated = await code_chunk_repo.update(created.id, update_data)

    assert updated is not None
    assert updated.name_path == "refactored.models.user.User.validate"
    # Other fields unchanged
    assert updated.name == created.name
    assert updated.file_path == created.file_path


# Test 14: Create chunk without name_path (NULL support)

@pytest.mark.asyncio
async def test_add_chunk_without_name_path(code_chunk_repo, sample_chunk_create):
    """
    FIX #2: Test backward compatibility - chunks without name_path.

    Old chunks or chunks from older parsers may not have name_path.
    Should store as NULL without errors.
    """
    chunk = await code_chunk_repo.add(sample_chunk_create)

    assert chunk.id is not None
    assert chunk.name == "calculate_total"
    # name_path should be None (NULL in DB)
    assert chunk.name_path is None


# Test 15: Multiple chunks with different name_paths

@pytest.mark.asyncio
async def test_multiple_chunks_with_different_name_paths(code_chunk_repo):
    """
    FIX #2: Test storing multiple chunks with different name_paths.

    Scenario: Verify name_path disambiguation for identically named symbols.
    Two "validate" functions with different qualified names.
    """
    # Create multiple chunks with different name_paths
    chunk1 = CodeChunkCreate(
        file_path="api/models/user.py",
        language="python",
        chunk_type=ChunkType.METHOD,
        name="validate",
        name_path="models.user.User.validate",
        source_code="def validate(self): pass",
        embedding_text=[0.1] * 768,
        embedding_code=[0.2] * 768,
        metadata={},
        repository="my-project",
    )

    chunk2 = CodeChunkCreate(
        file_path="api/utils/validator.py",
        language="python",
        chunk_type=ChunkType.FUNCTION,
        name="validate",
        name_path="utils.validator.validate",  # Different name_path, same name
        source_code="def validate(data): pass",
        embedding_text=[0.1] * 768,
        embedding_code=[0.2] * 768,
        metadata={},
        repository="my-project",
    )

    created1 = await code_chunk_repo.add(chunk1)
    created2 = await code_chunk_repo.add(chunk2)

    # Verify both stored correctly
    assert created1.name == "validate"
    assert created1.name_path == "models.user.User.validate"

    assert created2.name == "validate"
    assert created2.name_path == "utils.validator.validate"

    # Retrieve and verify name_paths are preserved
    retrieved1 = await code_chunk_repo.get_by_id(created1.id)
    retrieved2 = await code_chunk_repo.get_by_id(created2.id)

    assert retrieved1.name_path == "models.user.User.validate"
    assert retrieved2.name_path == "utils.validator.validate"

    # Verify we can distinguish them by name_path
    assert retrieved1.name_path != retrieved2.name_path
