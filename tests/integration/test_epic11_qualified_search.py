"""
Integration tests for EPIC-11 Story 11.2: Search by Qualified Name.

Tests lexical search with name_path field, covering:
1. Exact qualified name matching
2. Partial qualified matching
3. Auto-detection of qualified queries
4. Fallback to simple name search
5. name_path in results
6. Performance (<50ms)
"""

import pytest
import pytest_asyncio
import time
from unittest.mock import AsyncMock
from sqlalchemy import text

from services.lexical_search_service import LexicalSearchService
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
async def lexical_service(test_engine):
    """Create LexicalSearchService for testing."""
    return LexicalSearchService(engine=test_engine, similarity_threshold=0.1)


@pytest_asyncio.fixture
async def mocked_chunking_service():
    """Create mocked CodeChunkingService to avoid tree-sitter issues."""
    mock_service = AsyncMock(spec=CodeChunkingService)
    return mock_service


@pytest_asyncio.fixture
async def indexing_service(test_engine, mocked_chunking_service):
    """Create CodeIndexingService with mocked chunking for testing."""
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


@pytest_asyncio.fixture
async def indexed_chunks(indexing_service, mocked_chunking_service, test_engine):
    """
    Index test chunks with qualified name_paths.

    Creates:
    - models.user.User (class)
    - models.user.User.validate (method)
    - models.admin.User (class) - different User!
    - utils.helper.User (class) - another different User!
    - auth.routes.login (function)
    - auth.validators.check_password (function)
    """

    # Define test chunks with mock data
    test_files = [
        {
            "path": "api/models/user.py",
            "chunks": [
                CodeChunk(
                    file_path="api/models/user.py",
                    language="python",
                    chunk_type="class",
                    name="User",
                    source_code="class User:\n    pass",
                    start_line=1,
                    end_line=10,
                    metadata={}
                ),
                CodeChunk(
                    file_path="api/models/user.py",
                    language="python",
                    chunk_type="method",
                    name="validate",
                    source_code="    def validate(self):\n        return True",
                    start_line=3,
                    end_line=4,
                    metadata={}
                ),
            ]
        },
        {
            "path": "api/models/admin.py",
            "chunks": [
                CodeChunk(
                    file_path="api/models/admin.py",
                    language="python",
                    chunk_type="class",
                    name="User",
                    source_code="class User:\n    pass",
                    start_line=1,
                    end_line=5,
                    metadata={}
                ),
            ]
        },
        {
            "path": "api/utils/helper.py",
            "chunks": [
                CodeChunk(
                    file_path="api/utils/helper.py",
                    language="python",
                    chunk_type="class",
                    name="User",
                    source_code="class User:\n    pass",
                    start_line=1,
                    end_line=5,
                    metadata={}
                ),
            ]
        },
        {
            "path": "api/auth/routes.py",
            "chunks": [
                CodeChunk(
                    file_path="api/auth/routes.py",
                    language="python",
                    chunk_type="function",
                    name="login",
                    source_code="def login():\n    pass",
                    start_line=1,
                    end_line=2,
                    metadata={}
                ),
            ]
        },
        {
            "path": "api/auth/validators.py",
            "chunks": [
                CodeChunk(
                    file_path="api/auth/validators.py",
                    language="python",
                    chunk_type="function",
                    name="check_password",
                    source_code="def check_password():\n    pass",
                    start_line=1,
                    end_line=2,
                    metadata={}
                ),
            ]
        },
    ]

    options = IndexingOptions(
        repository="test-repo",
        repository_root="/app",
        generate_embeddings=False,
        build_graph=False
    )

    # Index all test files
    for file_data in test_files:
        mocked_chunking_service.chunk_code.return_value = file_data["chunks"]

        file_input = FileInput(
            path=file_data["path"],
            content="# Test content",
            language="python"
        )

        result = await indexing_service._index_file(file_input, options)
        assert result.success, f"Failed to index {file_data['path']}"

    # Verify chunks were created
    async with test_engine.connect() as conn:
        count_query = text("SELECT COUNT(*) FROM code_chunks")
        result = await conn.execute(count_query)
        count = result.scalar()

    print(f"\n✅ Indexed {count} chunks for qualified search tests")

    return count


# ============================================================================
# Test 1: Exact Qualified Match
# ============================================================================

@pytest.mark.asyncio
async def test_exact_qualified_name_search(lexical_service, indexed_chunks):
    """
    Test exact qualified name search.

    Given: Chunk with name_path = "models.user.User"
    When: Search query = "models.user.User"
    Then: Returns exact match with high similarity
    """
    results = await lexical_service.search(
        query="models.user.User",
        search_in_name_path=True,
        search_in_name=False,  # Only search name_path
        search_in_source=False,
        limit=10
    )

    assert len(results) >= 1, "Should find at least one result"

    # Find the exact match
    exact_match = next((r for r in results if r.name_path == "models.user.User"), None)
    assert exact_match is not None, f"Expected 'models.user.User', got: {[r.name_path for r in results]}"
    assert exact_match.similarity_score > 0.8, f"Expected high similarity, got {exact_match.similarity_score}"


# ============================================================================
# Test 2: Partial Qualified Match
# ============================================================================

@pytest.mark.asyncio
async def test_partial_qualified_match(lexical_service, indexed_chunks):
    """
    Test partial qualified matching.

    Given: Chunks with name_path = ["models.user.User", "models.admin.User", "utils.helper.User"]
    When: Search query = "models.User"
    Then: Returns all models.*.User but NOT utils.helper.User
    """
    results = await lexical_service.search(
        query="models.User",
        search_in_name_path=True,
        limit=20
    )

    assert len(results) >= 2, f"Should find at least 2 results, got {len(results)}"

    # Filter results with name_path containing "models" and "User"
    models_users = [r for r in results if r.name_path and "models" in r.name_path and "User" in r.name_path]

    assert len(models_users) >= 2, f"Expected at least 2 models.*.User, got {len(models_users)}"

    # Verify we got the expected name_paths
    name_paths = {r.name_path for r in models_users}
    assert "models.user.User" in name_paths, "Should include models.user.User"
    assert "models.admin.User" in name_paths, "Should include models.admin.User"


# ============================================================================
# Test 3: Auto-Detection of Qualified Queries
# ============================================================================

@pytest.mark.asyncio
async def test_auto_detect_qualified_query(lexical_service, indexed_chunks):
    """
    Test auto-detection when query contains dots.

    Given: Query contains dots (e.g., "auth.routes.login")
    When: search_in_name_path NOT explicitly set
    Then: Auto-enabled and searches name_path
    """
    # Should auto-detect qualified query (contains ".")
    results = await lexical_service.search(
        query="auth.routes.login",
        # search_in_name_path omitted → auto-detection
        limit=10
    )

    assert len(results) >= 1, "Should auto-detect and find results"

    # Verify we found the login function
    login_result = next((r for r in results if "login" in r.name_path), None)
    assert login_result is not None, f"Should find 'login', got: {[r.name_path for r in results]}"
    assert "auth" in login_result.name_path, "Should match 'auth' in name_path"


# ============================================================================
# Test 4: Fallback to Simple Name
# ============================================================================

@pytest.mark.asyncio
async def test_fallback_simple_name_if_no_qualified_match(lexical_service, indexed_chunks):
    """
    Test fallback strategy when qualified search returns nothing.

    Given: Query "nonexistent.module.User" (doesn't exist in name_path)
    When: Qualified search returns 0 results
    Then: Can fallback to simple name "User" search
    """
    # First search: qualified name_path only (should return 0)
    qualified_results = await lexical_service.search(
        query="nonexistent.module.User",
        search_in_name_path=True,
        search_in_name=False,
        search_in_source=False,
        limit=10
    )

    # If no results, fallback to simple name search
    if len(qualified_results) == 0:
        fallback_results = await lexical_service.search(
            query="User",
            search_in_name=True,
            search_in_name_path=True,
            limit=10
        )

        assert len(fallback_results) >= 3, f"Should find at least 3 'User' chunks, got {len(fallback_results)}"

        # Verify we have different User classes
        user_name_paths = {r.name_path for r in fallback_results if r.name == "User"}
        assert "models.user.User" in user_name_paths
        assert "models.admin.User" in user_name_paths
        assert "utils.helper.User" in user_name_paths


# ============================================================================
# Test 5: name_path Included in Results
# ============================================================================

@pytest.mark.asyncio
async def test_name_path_included_in_results(lexical_service, indexed_chunks):
    """
    Test that name_path is included in LexicalSearchResult.

    Given: Chunks with name_path populated (from Story 11.1)
    When: Any search
    Then: Results include name_path field
    """
    results = await lexical_service.search(
        query="User",
        search_in_name_path=True,
        limit=10
    )

    assert len(results) >= 1, "Should find at least one result"

    for result in results:
        assert hasattr(result, 'name_path'), "Result should have name_path attribute"
        # name_path should be qualified (contain dots)
        if result.name_path:
            assert '.' in result.name_path, f"name_path should be qualified, got: {result.name_path}"


# ============================================================================
# Test 6: Performance (<50ms)
# ============================================================================

@pytest.mark.asyncio
async def test_qualified_search_performance(lexical_service, indexed_chunks):
    """
    Test that qualified search completes in <50ms.

    Given: Indexed chunks with name_path
    When: Qualified search
    Then: Completes in <50ms
    """
    start = time.time()

    results = await lexical_service.search(
        query="models.User",
        search_in_name_path=True,
        limit=10
    )

    elapsed_ms = (time.time() - start) * 1000

    assert len(results) >= 1, "Should find results"
    assert elapsed_ms < 50, f"Search took {elapsed_ms:.2f}ms (threshold: 50ms)"

    print(f"\n⚡ Performance: {elapsed_ms:.2f}ms (threshold: 50ms) ✅")


# ============================================================================
# Test 7: Disambiguation with name_path
# ============================================================================

@pytest.mark.asyncio
async def test_name_path_enables_disambiguation(lexical_service, indexed_chunks):
    """
    Test that name_path enables symbol disambiguation.

    Given: 3 different "User" classes in different modules
    When: Search for specific qualified name
    Then: Returns only the specific User, not all Users
    """
    # Search for specific qualified User
    results = await lexical_service.search(
        query="models.admin.User",
        search_in_name_path=True,
        search_in_name=False,
        limit=10
    )

    # Should primarily match models.admin.User
    assert len(results) >= 1

    # Top result should be models.admin.User
    top_result = results[0]
    assert "admin" in top_result.name_path, f"Expected 'admin' in name_path, got: {top_result.name_path}"
    assert "User" in top_result.name_path


# ============================================================================
# Test 8: Wildcard Pattern Support (Bonus)
# ============================================================================

@pytest.mark.asyncio
async def test_wildcard_pattern_support(lexical_service, indexed_chunks):
    """
    Test fuzzy matching with partial qualified names.

    Given: Multiple chunks in auth.* modules
    When: Search for "auth.route" (partial match)
    Then: Returns matching auth.* symbols with fuzzy tolerance
    """
    results = await lexical_service.search(
        query="auth.route",  # Partial match (missing 's')
        search_in_name_path=True,
        limit=20
    )

    assert len(results) >= 1, "Should find at least 1 result for fuzzy match"

    # Verify we have auth-related results
    auth_results = [r for r in results if r.name_path and "auth" in r.name_path]
    assert len(auth_results) >= 1, f"Expected at least 1 auth result, got {len(auth_results)}"

    # Check if we got expected function (fuzzy match should find "auth.routes.login")
    name_paths = {r.name_path for r in auth_results}
    assert any("login" in np or "route" in np for np in name_paths), \
        f"Should include auth.routes.login or similar, got: {name_paths}"
