"""
Integration tests for EPIC-11 Story 11.1: name_path generation during indexing.

Tests the complete pipeline from CodeIndexingService to database storage,
verifying that name_path is correctly generated and persisted.
"""

import pytest
import pytest_asyncio
from services.code_indexing_service import (
    CodeIndexingService,
    FileInput,
    IndexingOptions,
)
from services.code_chunking_service import CodeChunkingService
from services.dual_embedding_service import DualEmbeddingService
from services.graph_construction_service import GraphConstructionService
from services.metadata_extractor_service import MetadataExtractorService
from services.symbol_path_service import SymbolPathService
from db.repositories.code_chunk_repository import CodeChunkRepository


@pytest_asyncio.fixture
async def indexing_service(test_engine):
    """Create CodeIndexingService with all dependencies for testing."""
    chunking_service = CodeChunkingService()
    metadata_service = MetadataExtractorService()
    embedding_service = DualEmbeddingService()
    graph_service = GraphConstructionService(test_engine)
    chunk_repository = CodeChunkRepository(test_engine)
    symbol_path_service = SymbolPathService()

    return CodeIndexingService(
        engine=test_engine,
        chunking_service=chunking_service,
        metadata_service=metadata_service,
        embedding_service=embedding_service,
        graph_service=graph_service,
        chunk_repository=chunk_repository,
        chunk_cache=None,  # Disable cache for testing
        symbol_path_service=symbol_path_service,
    )


@pytest.mark.asyncio
async def test_simple_function_generates_name_path(indexing_service):
    """
    Test that indexing a simple function generates correct name_path.

    Expected: api/utils/helper.py::test_function → utils.helper.test_function
    """
    source_code = '''def test_function():
    """A simple test function."""
    return True
'''

    file_input = FileInput(
        path="api/utils/helper.py",
        content=source_code,
        language="python"
    )

    options = IndexingOptions(
        repository="test-repo",
        repository_root="/app",  # EPIC-11: Required for name_path generation
        generate_embeddings=False,  # Skip embeddings for speed
        build_graph=False
    )

    # Index file
    result = await indexing_service._index_file(file_input, options)

    # Verify success
    assert result.success is True
    assert result.chunks_created >= 1

    # Retrieve chunks from DB
    repo = indexing_service.chunk_repository
    chunks = await repo.search_similarity(
        query="test_function",
        language="python",
        threshold=0.0,
        limit=10
    )

    # Find the test_function chunk
    test_chunk = None
    for chunk in chunks:
        if chunk.name == "test_function":
            test_chunk = chunk
            break

    assert test_chunk is not None, "test_function chunk not found in DB"

    # CRITICAL: Verify name_path is generated correctly
    assert test_chunk.name_path == "utils.helper.test_function", \
        f"Expected 'utils.helper.test_function', got '{test_chunk.name_path}'"


@pytest.mark.asyncio
async def test_class_method_generates_hierarchical_name_path(indexing_service):
    """
    Test that class methods generate correct hierarchical name_path.

    Expected:
    - User class → models.user.User
    - validate method → models.user.User.validate
    """
    source_code = '''class User:
    """User model class."""

    def validate(self):
        """Validate user data."""
        return self.email is not None

    def save(self):
        """Save user to database."""
        pass
'''

    file_input = FileInput(
        path="api/models/user.py",
        content=source_code,
        language="python"
    )

    options = IndexingOptions(
        repository="test-repo",
        repository_root="/app",
        generate_embeddings=False,
        build_graph=False
    )

    result = await indexing_service._index_file(file_input, options)

    assert result.success is True
    assert result.chunks_created >= 3  # User, validate, save

    # Retrieve all chunks
    repo = indexing_service.chunk_repository
    all_chunks = await repo.search_similarity(
        query="User validate save",
        language="python",
        threshold=0.0,
        limit=20
    )

    # Build chunk map
    chunk_map = {chunk.name: chunk for chunk in all_chunks}

    # Verify User class name_path
    assert "User" in chunk_map, "User class not found"
    assert chunk_map["User"].name_path == "models.user.User", \
        f"User name_path: expected 'models.user.User', got '{chunk_map['User'].name_path}'"

    # Verify validate method name_path (includes parent class)
    assert "validate" in chunk_map, "validate method not found"
    assert chunk_map["validate"].name_path == "models.user.User.validate", \
        f"validate name_path: expected 'models.user.User.validate', got '{chunk_map['validate'].name_path}'"

    # Verify save method name_path (includes parent class)
    assert "save" in chunk_map, "save method not found"
    assert chunk_map["save"].name_path == "models.user.User.save", \
        f"save name_path: expected 'models.user.User.save', got '{chunk_map['save'].name_path}'"


@pytest.mark.asyncio
async def test_nested_classes_generate_correct_parent_order(indexing_service):
    """
    Test that nested classes generate name_path in correct order (outermost → innermost).

    Structure:
        class Outer:
            class Inner:
                def method():
                    pass

    Expected:
    - Outer → models.nested.Outer
    - Inner → models.nested.Outer.Inner
    - method → models.nested.Outer.Inner.method  (NOT Inner.Outer.method!)
    """
    source_code = '''class Outer:
    """Outer class."""

    class Inner:
        """Nested inner class."""

        def method(self):
            """Method in nested class."""
            return True
'''

    file_input = FileInput(
        path="api/models/nested.py",
        content=source_code,
        language="python"
    )

    options = IndexingOptions(
        repository="test-repo",
        repository_root="/app",
        generate_embeddings=False,
        build_graph=False
    )

    result = await indexing_service._index_file(file_input, options)

    assert result.success is True
    assert result.chunks_created >= 3  # Outer, Inner, method

    # Retrieve chunks
    repo = indexing_service.chunk_repository
    all_chunks = await repo.search_similarity(
        query="Outer Inner method",
        language="python",
        threshold=0.0,
        limit=20
    )

    chunk_map = {chunk.name: chunk for chunk in all_chunks}

    # Verify Outer class
    assert "Outer" in chunk_map
    assert chunk_map["Outer"].name_path == "models.nested.Outer"

    # Verify Inner class (has Outer as parent)
    assert "Inner" in chunk_map
    assert chunk_map["Inner"].name_path == "models.nested.Outer.Inner", \
        f"Inner name_path: expected 'models.nested.Outer.Inner', got '{chunk_map['Inner'].name_path}'"

    # CRITICAL: Verify method has correct parent order (Outer.Inner, NOT Inner.Outer)
    assert "method" in chunk_map
    expected_name_path = "models.nested.Outer.Inner.method"
    actual_name_path = chunk_map["method"].name_path

    assert actual_name_path == expected_name_path, \
        f"Method name_path INCORRECT! Expected '{expected_name_path}', got '{actual_name_path}'. " \
        f"This indicates parent context ordering is reversed (reverse=True missing)!"


@pytest.mark.asyncio
async def test_multiple_files_generate_unique_name_paths(indexing_service):
    """
    Test that identically named symbols in different files get different name_paths.

    This verifies that name_path enables disambiguation.
    """
    # File 1: models/user.py with User class
    file1 = FileInput(
        path="api/models/user.py",
        content="class User:\n    pass",
        language="python"
    )

    # File 2: utils/helper.py with User class (different location)
    file2 = FileInput(
        path="api/utils/helper.py",
        content="class User:\n    pass",
        language="python"
    )

    options = IndexingOptions(
        repository="test-repo",
        repository_root="/app",
        generate_embeddings=False,
        build_graph=False
    )

    # Index both files
    result1 = await indexing_service._index_file(file1, options)
    result2 = await indexing_service._index_file(file2, options)

    assert result1.success and result2.success

    # Retrieve all User chunks
    repo = indexing_service.chunk_repository
    all_chunks = await repo.search_similarity(
        query="User",
        language="python",
        threshold=0.0,
        limit=20
    )

    # Filter for User chunks only
    user_chunks = [c for c in all_chunks if c.name == "User"]

    # Should have at least 2 User chunks (from different files)
    assert len(user_chunks) >= 2, f"Expected at least 2 User chunks, found {len(user_chunks)}"

    # Extract name_paths
    name_paths = {chunk.name_path for chunk in user_chunks}

    # Verify different name_paths
    assert "models.user.User" in name_paths, "models.user.User not found"
    assert "utils.helper.User" in name_paths, "utils.helper.User not found"

    # Verify they are different (disambiguation works!)
    assert "models.user.User" != "utils.helper.User", \
        "name_path should enable disambiguation between identically named symbols"


@pytest.mark.asyncio
async def test_name_path_persists_through_db_roundtrip(indexing_service):
    """
    Test that name_path is correctly stored and retrieved from database.

    Verifies the full pipeline: generate → store → retrieve.
    """
    source_code = '''def critical_function():
    """This function tests DB storage."""
    return "success"
'''

    file_input = FileInput(
        path="api/services/critical.py",
        content=source_code,
        language="python"
    )

    options = IndexingOptions(
        repository="test-repo",
        repository_root="/app",
        generate_embeddings=False,
        build_graph=False
    )

    # Index file
    result = await indexing_service._index_file(file_input, options)
    assert result.success

    # Retrieve by file path
    repo = indexing_service.chunk_repository
    chunks = await repo.search_similarity(
        query="critical_function",
        language="python",
        threshold=0.0,
        limit=10
    )

    critical_chunk = next((c for c in chunks if c.name == "critical_function"), None)

    assert critical_chunk is not None
    assert critical_chunk.name_path == "services.critical.critical_function"

    # Also retrieve by ID to verify round-trip
    chunk_by_id = await repo.get_by_id(critical_chunk.id)

    assert chunk_by_id is not None
    assert chunk_by_id.name_path == "services.critical.critical_function", \
        "name_path not preserved in DB round-trip (get_by_id)"
