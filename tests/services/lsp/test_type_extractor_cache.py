"""
Unit tests for TypeExtractorService L2 Redis caching.

Story: EPIC-13 Story 13.4 - LSP Result Caching (L2 Redis)
Author: Claude Code
Date: 2025-10-22

Tests cache behavior: hit/miss, graceful degradation, TTL.
"""

import pytest
import hashlib
from unittest.mock import Mock, AsyncMock, patch, call

from services.lsp import PyrightLSPClient, TypeExtractorService, LSPError
from services.caches import RedisCache
from models.code_chunk_models import CodeChunk, ChunkType


# Mark all tests as async
pytestmark = pytest.mark.anyio


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def mock_lsp_client():
    """Create a mock LSP client."""
    client = AsyncMock(spec=PyrightLSPClient)
    client.hover = AsyncMock()
    return client


@pytest.fixture
def mock_redis_cache():
    """Create a mock Redis cache."""
    cache = AsyncMock(spec=RedisCache)
    cache.get = AsyncMock()
    cache.set = AsyncMock()
    return cache


@pytest.fixture
def type_extractor_with_cache(mock_lsp_client, mock_redis_cache):
    """Create TypeExtractorService with mocked LSP client and Redis cache."""
    return TypeExtractorService(
        lsp_client=mock_lsp_client,
        redis_cache=mock_redis_cache
    )


@pytest.fixture
def sample_chunk():
    """Sample code chunk for testing."""
    return CodeChunk(
        file_path="/app/test.py",
        language="python",
        chunk_type=ChunkType.FUNCTION,
        name="process_user",
        source_code="def process_user(user_id: int) -> User: ...",
        start_line=10,
        end_line=12,
        metadata={}
    )


@pytest.fixture
def sample_source_code():
    """Sample source code for testing."""
    return "def process_user(user_id: int) -> User: ..."


# ============================================
# Cache Hit Tests
# ============================================

async def test_cache_hit_returns_cached_metadata(
    type_extractor_with_cache,
    mock_lsp_client,
    mock_redis_cache,
    sample_chunk,
    sample_source_code
):
    """Test cache hit: Returns cached metadata without querying LSP."""
    # Setup: Cached metadata exists
    cached_metadata = {
        "return_type": "User",
        "param_types": {"user_id": "int"},
        "signature": "process_user(user_id: int) -> User"
    }
    mock_redis_cache.get.return_value = cached_metadata

    # Execute
    metadata = await type_extractor_with_cache.extract_type_metadata(
        "/app/test.py",
        sample_source_code,
        sample_chunk
    )

    # Verify: Returns cached metadata
    assert metadata == cached_metadata
    assert metadata["return_type"] == "User"
    assert metadata["param_types"] == {"user_id": "int"}

    # Verify: LSP was NOT called (cache hit)
    mock_lsp_client.hover.assert_not_called()

    # Verify: Redis cache was queried with correct key
    content_hash = hashlib.md5(sample_source_code.encode()).hexdigest()
    expected_cache_key = f"lsp:type:{content_hash}:10"
    mock_redis_cache.get.assert_called_once_with(expected_cache_key)


async def test_cache_hit_for_same_file_different_line(
    type_extractor_with_cache,
    mock_redis_cache,
    sample_source_code
):
    """Test cache uses different keys for different lines in same file."""
    # Setup: Two chunks at different lines
    chunk_line_10 = CodeChunk(
        file_path="/app/test.py",
        language="python",
        chunk_type=ChunkType.FUNCTION,
        name="func1",
        source_code=sample_source_code,
        start_line=10,
        end_line=12,
        metadata={}
    )

    chunk_line_20 = CodeChunk(
        file_path="/app/test.py",
        language="python",
        chunk_type=ChunkType.FUNCTION,
        name="func2",
        source_code=sample_source_code,
        start_line=20,
        end_line=22,
        metadata={}
    )

    mock_redis_cache.get.return_value = None  # Cache miss

    # Execute both
    await type_extractor_with_cache.extract_type_metadata(
        "/app/test.py", sample_source_code, chunk_line_10
    )
    await type_extractor_with_cache.extract_type_metadata(
        "/app/test.py", sample_source_code, chunk_line_20
    )

    # Verify: Different cache keys used
    content_hash = hashlib.md5(sample_source_code.encode()).hexdigest()
    expected_key_line_10 = f"lsp:type:{content_hash}:10"
    expected_key_line_20 = f"lsp:type:{content_hash}:20"

    assert mock_redis_cache.get.call_count == 2
    mock_redis_cache.get.assert_any_call(expected_key_line_10)
    mock_redis_cache.get.assert_any_call(expected_key_line_20)


# ============================================
# Cache Miss Tests
# ============================================

async def test_cache_miss_queries_lsp_and_caches_result(
    type_extractor_with_cache,
    mock_lsp_client,
    mock_redis_cache,
    sample_chunk,
    sample_source_code
):
    """Test cache miss: Queries LSP and caches the result."""
    # Setup: Cache miss (returns None)
    mock_redis_cache.get.return_value = None

    # Mock LSP hover response
    mock_lsp_client.hover.return_value = "(function) process_user: (user_id: int) -> User"

    # Execute
    metadata = await type_extractor_with_cache.extract_type_metadata(
        "/app/test.py",
        sample_source_code,
        sample_chunk
    )

    # Verify: LSP was called
    mock_lsp_client.hover.assert_called_once()

    # Verify: Result was cached with correct key and TTL
    content_hash = hashlib.md5(sample_source_code.encode()).hexdigest()
    expected_cache_key = f"lsp:type:{content_hash}:10"

    mock_redis_cache.set.assert_called_once_with(
        expected_cache_key,
        metadata,
        ttl_seconds=300
    )

    # Verify: Correct metadata returned
    assert metadata["return_type"] == "User"
    assert metadata["param_types"] == {"user_id": "int"}


async def test_cache_miss_empty_hover_not_cached(
    type_extractor_with_cache,
    mock_lsp_client,
    mock_redis_cache,
    sample_chunk,
    sample_source_code
):
    """Test cache miss with empty hover: Does not cache empty result."""
    # Setup: Cache miss
    mock_redis_cache.get.return_value = None

    # Mock LSP hover returns None (no hover info)
    mock_lsp_client.hover.return_value = None

    # Execute
    metadata = await type_extractor_with_cache.extract_type_metadata(
        "/app/test.py",
        sample_source_code,
        sample_chunk
    )

    # Verify: LSP was called
    mock_lsp_client.hover.assert_called_once()

    # Verify: Empty result was NOT cached (no signature)
    mock_redis_cache.set.assert_not_called()

    # Verify: Empty metadata returned
    assert metadata["return_type"] is None
    assert metadata["param_types"] == {}
    assert metadata["signature"] is None


# ============================================
# Cache Disabled Tests
# ============================================

async def test_no_cache_queries_lsp_directly(mock_lsp_client, sample_chunk, sample_source_code):
    """Test no cache: Queries LSP directly without caching."""
    # Create TypeExtractorService without Redis cache
    extractor = TypeExtractorService(lsp_client=mock_lsp_client, redis_cache=None)

    # Mock LSP hover response
    mock_lsp_client.hover.return_value = "(function) process_user: (user_id: int) -> User"

    # Execute
    metadata = await extractor.extract_type_metadata(
        "/app/test.py",
        sample_source_code,
        sample_chunk
    )

    # Verify: LSP was called
    mock_lsp_client.hover.assert_called_once()

    # Verify: Correct metadata returned
    assert metadata["return_type"] == "User"
    assert metadata["param_types"] == {"user_id": "int"}


# ============================================
# Graceful Degradation Tests
# ============================================

async def test_cache_lookup_failure_queries_lsp(
    type_extractor_with_cache,
    mock_lsp_client,
    mock_redis_cache,
    sample_chunk,
    sample_source_code
):
    """Test cache lookup failure: Degrades gracefully and queries LSP."""
    # Setup: Cache lookup raises exception
    mock_redis_cache.get.side_effect = Exception("Redis connection error")

    # Mock LSP hover response
    mock_lsp_client.hover.return_value = "(function) process_user: (user_id: int) -> User"

    # Execute (should not raise)
    metadata = await type_extractor_with_cache.extract_type_metadata(
        "/app/test.py",
        sample_source_code,
        sample_chunk
    )

    # Verify: LSP was called (graceful degradation)
    mock_lsp_client.hover.assert_called_once()

    # Verify: Correct metadata returned
    assert metadata["return_type"] == "User"


async def test_cache_set_failure_returns_result(
    type_extractor_with_cache,
    mock_lsp_client,
    mock_redis_cache,
    sample_chunk,
    sample_source_code
):
    """Test cache set failure: Returns result without crashing."""
    # Setup: Cache miss
    mock_redis_cache.get.return_value = None

    # Mock LSP hover response
    mock_lsp_client.hover.return_value = "(function) process_user: (user_id: int) -> User"

    # Setup: Cache set raises exception
    mock_redis_cache.set.side_effect = Exception("Redis set failed")

    # Execute (should not raise)
    metadata = await type_extractor_with_cache.extract_type_metadata(
        "/app/test.py",
        sample_source_code,
        sample_chunk
    )

    # Verify: Result was returned despite cache failure
    assert metadata["return_type"] == "User"
    assert metadata["param_types"] == {"user_id": "int"}


async def test_lsp_error_returns_empty_metadata(
    type_extractor_with_cache,
    mock_lsp_client,
    mock_redis_cache,
    sample_chunk,
    sample_source_code
):
    """Test LSP error: Returns empty metadata (graceful degradation)."""
    # Setup: Cache miss
    mock_redis_cache.get.return_value = None

    # Mock LSP hover raises LSPError
    mock_lsp_client.hover.side_effect = LSPError("LSP timeout")

    # Execute (should not raise)
    metadata = await type_extractor_with_cache.extract_type_metadata(
        "/app/test.py",
        sample_source_code,
        sample_chunk
    )

    # Verify: Empty metadata returned
    assert metadata["return_type"] is None
    assert metadata["param_types"] == {}
    assert metadata["signature"] is None

    # Verify: Cache was not populated (no valid result)
    mock_redis_cache.set.assert_not_called()


# ============================================
# Cache Key Tests
# ============================================

async def test_cache_key_changes_with_source_code(
    type_extractor_with_cache,
    mock_redis_cache,
    sample_chunk
):
    """Test cache key changes when source code changes."""
    # Setup: Cache miss
    mock_redis_cache.get.return_value = None

    source_v1 = "def process_user(user_id: int) -> User: ..."
    source_v2 = "def process_user(user_id: str) -> User: ..."  # Changed type

    # Execute with version 1
    await type_extractor_with_cache.extract_type_metadata(
        "/app/test.py", source_v1, sample_chunk
    )

    # Execute with version 2
    await type_extractor_with_cache.extract_type_metadata(
        "/app/test.py", source_v2, sample_chunk
    )

    # Verify: Different cache keys used
    hash_v1 = hashlib.md5(source_v1.encode()).hexdigest()
    hash_v2 = hashlib.md5(source_v2.encode()).hexdigest()

    expected_key_v1 = f"lsp:type:{hash_v1}:10"
    expected_key_v2 = f"lsp:type:{hash_v2}:10"

    assert expected_key_v1 != expected_key_v2  # Keys are different
    assert mock_redis_cache.get.call_count == 2
    mock_redis_cache.get.assert_any_call(expected_key_v1)
    mock_redis_cache.get.assert_any_call(expected_key_v2)


# ============================================
# Integration-like Tests
# ============================================

async def test_multiple_calls_same_file_uses_cache(
    type_extractor_with_cache,
    mock_lsp_client,
    mock_redis_cache,
    sample_chunk,
    sample_source_code
):
    """Test multiple calls for same file: Only queries LSP once (cache working)."""
    # Setup: First call is cache miss, second is cache hit
    cached_metadata = {
        "return_type": "User",
        "param_types": {"user_id": "int"},
        "signature": "process_user(user_id: int) -> User"
    }

    # First call: cache miss -> then cache hit
    mock_redis_cache.get.side_effect = [None, cached_metadata]

    # Mock LSP hover response (only called once)
    mock_lsp_client.hover.return_value = "(function) process_user: (user_id: int) -> User"

    # First call (cache miss)
    metadata1 = await type_extractor_with_cache.extract_type_metadata(
        "/app/test.py",
        sample_source_code,
        sample_chunk
    )

    # Second call (cache hit)
    metadata2 = await type_extractor_with_cache.extract_type_metadata(
        "/app/test.py",
        sample_source_code,
        sample_chunk
    )

    # Verify: LSP was called only ONCE (first call)
    assert mock_lsp_client.hover.call_count == 1

    # Verify: Cache was populated after first call
    assert mock_redis_cache.set.call_count == 1

    # Verify: Both calls return correct metadata
    assert metadata1["return_type"] == "User"
    assert metadata2["return_type"] == "User"
