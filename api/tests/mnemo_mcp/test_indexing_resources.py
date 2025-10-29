"""
Unit tests for Indexing Resources (EPIC-23 Story 23.5).

Tests cover:
- IndexStatusResource functionality
- Status determination logic (in_progress, completed, not_indexed, failed)
- Redis + PostgreSQL hybrid queries
- Cache statistics integration
- Graceful degradation when services unavailable
"""
import pytest
import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock, MagicMock
from sqlalchemy import text

from mnemo_mcp.resources.indexing_resources import (
    IndexStatusResource,
    index_status_resource,
)


@pytest.fixture
def mock_services_with_data():
    """Create mock services with indexed data."""
    # Mock Redis with in_progress status
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=json.dumps({
        "status": "in_progress",
        "total_files": 100,
        "indexed_files": 50,
        "started_at": datetime.utcnow().isoformat(),
        "repository": "test_repo",
    }))

    # Mock SQLAlchemy engine with connection
    mock_conn = AsyncMock()

    # Mock chunk count query (total_chunks)
    mock_chunk_result = Mock()
    mock_chunk_result.scalar = Mock(return_value=500)

    # Mock file count query (total_files)
    mock_file_result = Mock()
    mock_file_result.scalar = Mock(return_value=100)

    # Mock languages query
    mock_languages_result = AsyncMock()
    mock_languages_result.__aiter__ = Mock(
        return_value=iter([("Python",), ("JavaScript",), ("TypeScript",)])
    )

    # Mock last_indexed_at query
    mock_last_indexed_result = Mock()
    mock_last_indexed_result.scalar = Mock(return_value=datetime.utcnow())

    # Configure connection execute to return appropriate results
    execute_call_count = 0

    async def mock_execute(query):
        nonlocal execute_call_count
        execute_call_count += 1

        # Return different results based on call order
        if execute_call_count == 1:
            return mock_chunk_result  # total_chunks
        elif execute_call_count == 2:
            return mock_file_result  # total_files
        elif execute_call_count == 3:
            return mock_languages_result  # languages
        else:
            return mock_last_indexed_result  # last_indexed_at

    mock_conn.execute = AsyncMock(side_effect=mock_execute)

    # Mock engine connection context manager
    mock_engine = AsyncMock()
    mock_engine.connect = MagicMock(return_value=mock_conn)
    mock_engine.connect().__aenter__ = AsyncMock(return_value=mock_conn)
    mock_engine.connect().__aexit__ = AsyncMock()

    # Mock ChunkCache
    mock_cache = Mock()
    mock_cache.get_stats = Mock(return_value={
        "l1_hits": 100,
        "l1_misses": 20,
        "l2_hits": 15,
        "l2_misses": 5,
    })

    return {
        "redis": mock_redis,
        "sqlalchemy_engine": mock_engine,
        "chunk_cache": mock_cache,
    }


@pytest.fixture
def mock_services_empty():
    """Create mock services with no indexed data."""
    # Mock Redis with no status
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)

    # Mock SQLAlchemy engine with empty results
    mock_conn = AsyncMock()

    # All queries return 0 or empty
    mock_empty_result = Mock()
    mock_empty_result.scalar = Mock(return_value=0)

    mock_empty_languages = AsyncMock()
    mock_empty_languages.__aiter__ = Mock(return_value=iter([]))

    execute_call_count = 0

    async def mock_execute(query):
        nonlocal execute_call_count
        execute_call_count += 1

        if execute_call_count == 3:
            return mock_empty_languages
        else:
            return mock_empty_result

    mock_conn.execute = AsyncMock(side_effect=mock_execute)

    mock_engine = AsyncMock()
    mock_engine.connect = MagicMock(return_value=mock_conn)
    mock_engine.connect().__aenter__ = AsyncMock(return_value=mock_conn)
    mock_engine.connect().__aexit__ = AsyncMock()

    return {
        "redis": mock_redis,
        "sqlalchemy_engine": mock_engine,
        "chunk_cache": None,
    }


@pytest.mark.asyncio
async def test_index_status_in_progress(mock_services_with_data):
    """Test status resource returns in_progress status."""
    resource = IndexStatusResource()
    resource.inject_services(mock_services_with_data)

    result = await resource.get(repository="test_repo")

    assert result["success"] is True
    assert result["repository"] == "test_repo"
    assert result["status"] == "in_progress"
    assert result["total_files"] == 100
    assert result["indexed_files"] == 50  # Progress from Redis
    assert result["total_chunks"] == 500
    assert "Python" in result["languages"]
    assert "JavaScript" in result["languages"]
    assert result["embedding_model"] == "nomic-embed-text-v1.5"
    assert result["cache_stats"]["l1_hits"] == 100


@pytest.mark.asyncio
async def test_index_status_completed():
    """Test status resource returns completed status."""
    # Mock services with completed status
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=json.dumps({
        "status": "completed",
        "total_files": 100,
        "indexed_files": 100,
        "started_at": datetime.utcnow().isoformat(),
        "completed_at": datetime.utcnow().isoformat(),
        "repository": "test_repo",
    }))

    # Mock DB with data
    mock_conn = AsyncMock()
    mock_chunk_result = Mock()
    mock_chunk_result.scalar = Mock(return_value=1000)

    mock_file_result = Mock()
    mock_file_result.scalar = Mock(return_value=100)

    mock_languages_result = AsyncMock()
    mock_languages_result.__aiter__ = Mock(return_value=iter([("Python",)]))

    mock_last_indexed_result = Mock()
    mock_last_indexed_result.scalar = Mock(return_value=datetime.utcnow())

    execute_call_count = 0

    async def mock_execute(query):
        nonlocal execute_call_count
        execute_call_count += 1

        if execute_call_count == 1:
            return mock_chunk_result
        elif execute_call_count == 2:
            return mock_file_result
        elif execute_call_count == 3:
            return mock_languages_result
        else:
            return mock_last_indexed_result

    mock_conn.execute = AsyncMock(side_effect=mock_execute)

    mock_engine = AsyncMock()
    mock_engine.connect = MagicMock(return_value=mock_conn)
    mock_engine.connect().__aenter__ = AsyncMock(return_value=mock_conn)
    mock_engine.connect().__aexit__ = AsyncMock()

    services = {
        "redis": mock_redis,
        "sqlalchemy_engine": mock_engine,
        "chunk_cache": None,
    }

    resource = IndexStatusResource()
    resource.inject_services(services)

    result = await resource.get(repository="test_repo")

    assert result["success"] is True
    assert result["status"] == "completed"
    assert result["total_files"] == 100
    assert result["indexed_files"] == 100
    assert result["total_chunks"] == 1000
    assert result["completed_at"] is not None


@pytest.mark.asyncio
async def test_index_status_not_indexed(mock_services_empty):
    """Test status resource returns not_indexed when no data."""
    resource = IndexStatusResource()
    resource.inject_services(mock_services_empty)

    result = await resource.get(repository="test_repo")

    assert result["success"] is True
    assert result["repository"] == "test_repo"
    assert result["status"] == "not_indexed"
    assert result["total_files"] == 0
    assert result["indexed_files"] == 0
    assert result["total_chunks"] == 0
    assert result["languages"] == []
    assert "not indexed yet" in result["message"].lower()


@pytest.mark.asyncio
async def test_index_status_with_cache_stats(mock_services_with_data):
    """Test status resource includes cache statistics."""
    resource = IndexStatusResource()
    resource.inject_services(mock_services_with_data)

    result = await resource.get(repository="test_repo")

    assert result["success"] is True
    assert "cache_stats" in result
    assert result["cache_stats"]["l1_hits"] == 100
    assert result["cache_stats"]["l1_misses"] == 20
    assert result["cache_stats"]["l2_hits"] == 15
    assert result["cache_stats"]["l2_misses"] == 5


@pytest.mark.asyncio
async def test_index_status_redis_unavailable():
    """Test graceful degradation when Redis is unavailable."""
    # Services without Redis
    mock_conn = AsyncMock()

    # Mock DB with data
    mock_chunk_result = Mock()
    mock_chunk_result.scalar = Mock(return_value=500)

    mock_file_result = Mock()
    mock_file_result.scalar = Mock(return_value=50)

    mock_languages_result = AsyncMock()
    mock_languages_result.__aiter__ = Mock(return_value=iter([("Python",)]))

    mock_last_indexed_result = Mock()
    mock_last_indexed_result.scalar = Mock(return_value=datetime.utcnow())

    execute_call_count = 0

    async def mock_execute(query):
        nonlocal execute_call_count
        execute_call_count += 1

        if execute_call_count == 1:
            return mock_chunk_result
        elif execute_call_count == 2:
            return mock_file_result
        elif execute_call_count == 3:
            return mock_languages_result
        else:
            return mock_last_indexed_result

    mock_conn.execute = AsyncMock(side_effect=mock_execute)

    mock_engine = AsyncMock()
    mock_engine.connect = MagicMock(return_value=mock_conn)
    mock_engine.connect().__aenter__ = AsyncMock(return_value=mock_conn)
    mock_engine.connect().__aexit__ = AsyncMock()

    services = {
        "redis": None,  # Redis unavailable
        "sqlalchemy_engine": mock_engine,
        "chunk_cache": None,
    }

    resource = IndexStatusResource()
    resource.inject_services(services)

    result = await resource.get(repository="test_repo")

    # Should still work using DB data
    assert result["success"] is True
    assert result["status"] == "completed"  # Determined from DB (has chunks)
    assert result["total_chunks"] == 500
    assert result["total_files"] == 50


@pytest.mark.asyncio
async def test_index_status_database_unavailable():
    """Test error handling when database is unavailable."""
    services = {
        "redis": AsyncMock(),
        "sqlalchemy_engine": None,  # Database unavailable
        "chunk_cache": None,
    }

    services["redis"].get = AsyncMock(return_value=None)

    resource = IndexStatusResource()
    resource.inject_services(services)

    result = await resource.get(repository="test_repo")

    assert result["success"] is False
    assert "not available" in result["message"].lower()


@pytest.mark.asyncio
async def test_singleton_instance_available():
    """Test that singleton resource instance is available for registration."""
    assert index_status_resource is not None
    assert isinstance(index_status_resource, IndexStatusResource)
