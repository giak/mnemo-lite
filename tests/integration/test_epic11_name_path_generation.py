"""
Integration tests for EPIC-11 Story 11.1: name_path generation during indexing.

Tests the complete pipeline from CodeIndexingService to database storage,
verifying that name_path is correctly generated and persisted.

NOTE: These tests mock CodeChunkingService to avoid tree-sitter parsing issues
and focus solely on testing name_path generation logic.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from services.code_indexing_service import (
    CodeIndexingService,
    FileInput,
    IndexingOptions,
)
from services.code_chunking_service import CodeChunkingService, CodeChunk
from services.dual_embedding_service import DualEmbeddingService
from services.graph_construction_service import GraphConstructionService
from services.metadata_extractor_service import MetadataExtractorService
from services.symbol_path_service import SymbolPathService
from db.repositories.code_chunk_repository import CodeChunkRepository


@pytest_asyncio.fixture
async def mocked_chunking_service():
    """Create mocked CodeChunkingService that returns predefined chunks.

    This avoids tree-sitter parsing issues and allows us to focus on
    testing name_path generation logic.
    """
    mock_service = AsyncMock(spec=CodeChunkingService)
    # Will be configured per-test with return_value
    return mock_service


@pytest_asyncio.fixture
async def indexing_service(test_engine, mocked_chunking_service):
    """Create CodeIndexingService with mocked chunking service for testing."""
    metadata_service = MetadataExtractorService()
    embedding_service = DualEmbeddingService()
    graph_service = GraphConstructionService(test_engine)
    chunk_repository = CodeChunkRepository(test_engine)
    symbol_path_service = SymbolPathService()

    return CodeIndexingService(
        engine=test_engine,
        chunking_service=mocked_chunking_service,
        metadata_service=metadata_service,
        embedding_service=embedding_service,
        graph_service=graph_service,
        chunk_repository=chunk_repository,
        chunk_cache=None,  # Disable cache for testing
        symbol_path_service=symbol_path_service,
    )


@pytest.mark.asyncio
async def test_simple_function_generates_name_path(indexing_service, mocked_chunking_service, test_engine):
    """
    Test that indexing a simple function generates correct name_path.

    Expected: api/utils/helper.py::test_function → utils.helper.test_function
    """
    source_code = '''def test_function():
    """A simple test function."""
    return True
'''

    # Configure mock to return a function chunk
    mock_chunk = CodeChunk(
        file_path="api/utils/helper.py",
        language="python",
        chunk_type="function",
        name="test_function",
        source_code=source_code.strip(),
        start_line=1,
        end_line=3,
        metadata={}
    )
    mocked_chunking_service.chunk_code.return_value = [mock_chunk]

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

    # Retrieve chunks from DB directly using SQL
    from sqlalchemy import text

    async with test_engine.connect() as conn:
        query = text("""
            SELECT id, name, name_path, file_path, chunk_type
            FROM code_chunks
            WHERE file_path = :file_path
            ORDER BY start_line
        """)
        result = await conn.execute(query, {"file_path": "api/utils/helper.py"})
        rows = result.fetchall()

    # Debug: print what we found
    print(f"\n🔍 Found {len(rows)} chunks in DB:")
    for row in rows:
        print(f"  - {row.name} (type: {row.chunk_type}) → name_path: {row.name_path}")

    # Find the test_function chunk
    test_chunk_row = None
    for row in rows:
        if row.name == "test_function":
            test_chunk_row = row
            break

    assert test_chunk_row is not None, f"test_function chunk not found in DB. Found chunks: {[r.name for r in rows]}"

    # CRITICAL: Verify name_path is generated correctly
    assert test_chunk_row.name_path == "utils.helper.test_function", \
        f"Expected 'utils.helper.test_function', got '{test_chunk_row.name_path}'"


@pytest.mark.asyncio
async def test_class_method_generates_hierarchical_name_path(indexing_service, mocked_chunking_service, test_engine):
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

    # Configure mock to return class + method chunks
    mock_chunks = [
        CodeChunk(
            file_path="api/models/user.py",
            language="python",
            chunk_type="class",
            name="User",
            source_code="class User:\n    ...",
            start_line=1,
            end_line=9,
            metadata={}
        ),
        CodeChunk(
            file_path="api/models/user.py",
            language="python",
            chunk_type="method",
            name="validate",
            source_code="    def validate(self):\n        return self.email is not None",
            start_line=4,
            end_line=5,
            metadata={}
        ),
        CodeChunk(
            file_path="api/models/user.py",
            language="python",
            chunk_type="method",
            name="save",
            source_code="    def save(self):\n        pass",
            start_line=7,
            end_line=8,
            metadata={}
        ),
    ]
    mocked_chunking_service.chunk_code.return_value = mock_chunks

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

    # Retrieve all chunks from DB directly
    from sqlalchemy import text

    async with test_engine.connect() as conn:
        query = text("""
            SELECT name, name_path, chunk_type
            FROM code_chunks
            WHERE file_path = :file_path
            ORDER BY start_line
        """)
        result_db = await conn.execute(query, {"file_path": "api/models/user.py"})
        rows = result_db.fetchall()

    # Build chunk map
    chunk_map = {row.name: row for row in rows}

    # Verify User class name_path
    assert "User" in chunk_map, f"User class not found. Found: {list(chunk_map.keys())}"
    assert chunk_map["User"].name_path == "models.user.User", \
        f"User name_path: expected 'models.user.User', got '{chunk_map['User'].name_path}'"

    # Verify validate method name_path (includes parent class)
    assert "validate" in chunk_map, f"validate method not found. Found: {list(chunk_map.keys())}"
    assert chunk_map["validate"].name_path == "models.user.User.validate", \
        f"validate name_path: expected 'models.user.User.validate', got '{chunk_map['validate'].name_path}'"

    # Verify save method name_path (includes parent class)
    assert "save" in chunk_map, f"save method not found. Found: {list(chunk_map.keys())}"
    assert chunk_map["save"].name_path == "models.user.User.save", \
        f"save name_path: expected 'models.user.User.save', got '{chunk_map['save'].name_path}'"


@pytest.mark.asyncio
async def test_nested_classes_generate_correct_parent_order(indexing_service, mocked_chunking_service, test_engine):
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

    # Configure mock to return nested class + method chunks
    # IMPORTANT: Outer must END AFTER Inner for parent detection to work!
    mock_chunks = [
        CodeChunk(
            file_path="api/models/nested.py",
            language="python",
            chunk_type="class",
            name="Outer",
            source_code="class Outer:\n    ...",
            start_line=1,
            end_line=10,  # Outer ends AFTER Inner (line 8)
            metadata={}
        ),
        CodeChunk(
            file_path="api/models/nested.py",
            language="python",
            chunk_type="class",
            name="Inner",
            source_code="    class Inner:\n        ...",
            start_line=4,
            end_line=8,  # Inner ends BEFORE Outer
            metadata={}
        ),
        CodeChunk(
            file_path="api/models/nested.py",
            language="python",
            chunk_type="method",
            name="method",
            source_code="        def method(self):\n            return True",
            start_line=6,
            end_line=7,  # method inside Inner
            metadata={}
        ),
    ]
    mocked_chunking_service.chunk_code.return_value = mock_chunks

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

    # Retrieve chunks from DB directly
    from sqlalchemy import text

    async with test_engine.connect() as conn:
        query = text("""
            SELECT name, name_path, chunk_type
            FROM code_chunks
            WHERE file_path = :file_path
            ORDER BY start_line
        """)
        result_db = await conn.execute(query, {"file_path": "api/models/nested.py"})
        rows = result_db.fetchall()

    chunk_map = {row.name: row for row in rows}

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
async def test_multiple_files_generate_unique_name_paths(indexing_service, mocked_chunking_service, test_engine):
    """
    Test that identically named symbols in different files get different name_paths.

    This verifies that name_path enables disambiguation.
    """
    # File 1: models/user.py with User class
    mock_chunks_file1 = [
        CodeChunk(
            file_path="api/models/user.py",
            language="python",
            chunk_type="class",
            name="User",
            source_code="class User:\n    pass",
            start_line=1,
            end_line=2,
            metadata={}
        )
    ]

    # File 2: utils/helper.py with User class (different location)
    mock_chunks_file2 = [
        CodeChunk(
            file_path="api/utils/helper.py",
            language="python",
            chunk_type="class",
            name="User",
            source_code="class User:\n    pass",
            start_line=1,
            end_line=2,
            metadata={}
        )
    ]

    file1 = FileInput(
        path="api/models/user.py",
        content="class User:\n    pass",
        language="python"
    )

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

    # Index file 1
    mocked_chunking_service.chunk_code.return_value = mock_chunks_file1
    result1 = await indexing_service._index_file(file1, options)

    # Index file 2
    mocked_chunking_service.chunk_code.return_value = mock_chunks_file2
    result2 = await indexing_service._index_file(file2, options)

    assert result1.success and result2.success

    # Retrieve all User chunks from DB directly
    from sqlalchemy import text

    async with test_engine.connect() as conn:
        query = text("""
            SELECT name, name_path, file_path
            FROM code_chunks
            WHERE name = :name
            ORDER BY file_path
        """)
        result_db = await conn.execute(query, {"name": "User"})
        rows = result_db.fetchall()

    # Should have at least 2 User chunks (from different files)
    assert len(rows) >= 2, f"Expected at least 2 User chunks, found {len(rows)}"

    # Extract name_paths
    name_paths = {row.name_path for row in rows}

    # Verify different name_paths
    assert "models.user.User" in name_paths, "models.user.User not found"
    assert "utils.helper.User" in name_paths, "utils.helper.User not found"

    # Verify they are different (disambiguation works!)
    assert "models.user.User" != "utils.helper.User", \
        "name_path should enable disambiguation between identically named symbols"


@pytest.mark.asyncio
async def test_name_path_persists_through_db_roundtrip(indexing_service, mocked_chunking_service, test_engine):
    """
    Test that name_path is correctly stored and retrieved from database.

    Verifies the full pipeline: generate → store → retrieve.
    """
    source_code = '''def critical_function():
    """This function tests DB storage."""
    return "success"
'''

    # Configure mock to return a simple function chunk
    mock_chunk = CodeChunk(
        file_path="api/services/critical.py",
        language="python",
        chunk_type="function",
        name="critical_function",
        source_code=source_code.strip(),
        start_line=1,
        end_line=3,
        metadata={}
    )
    mocked_chunking_service.chunk_code.return_value = [mock_chunk]

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

    # Retrieve by file path from DB directly
    from sqlalchemy import text

    async with test_engine.connect() as conn:
        query = text("""
            SELECT id, name, name_path
            FROM code_chunks
            WHERE file_path = :file_path AND name = :name
        """)
        result_db = await conn.execute(query, {
            "file_path": "api/services/critical.py",
            "name": "critical_function"
        })
        row = result_db.fetchone()

    assert row is not None
    assert row.name_path == "services.critical.critical_function"

    # Also retrieve by ID to verify round-trip
    repo = indexing_service.chunk_repository
    chunk_by_id = await repo.get_by_id(row.id)

    assert chunk_by_id is not None
    assert chunk_by_id.name_path == "services.critical.critical_function", \
        "name_path not preserved in DB round-trip (get_by_id)"
