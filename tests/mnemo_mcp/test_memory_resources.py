"""
Tests for MCP memory resources.

Tests get_memory, list_memories, and search_memories resources with mocked dependencies.
"""

import pytest
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from mnemo_mcp.resources.memory_resources import (
    GetMemoryResource,
    ListMemoriesResource,
    SearchMemoriesResource,
)
from mnemo_mcp.models.memory_models import (
    Memory,
    MemoryType,
)


@pytest.fixture
def mock_ctx():
    """Mock MCP Context (unused for resources)."""
    return None


@pytest.fixture
def mock_memory_repository():
    """Mock MemoryRepository."""
    return AsyncMock()


@pytest.fixture
def mock_redis_client():
    """Mock Redis client."""
    redis = AsyncMock()
    redis.get.return_value = None  # Default: cache miss
    redis.set.return_value = None
    return redis


@pytest.fixture
def mock_embedding_service():
    """Mock EmbeddingService."""
    service = AsyncMock()
    service.generate_embedding.return_value = [0.1] * 768
    return service


@pytest.fixture
def sample_memory():
    """Sample Memory object."""
    return Memory(
        id=uuid.uuid4(),
        title="Test Memory",
        content="Test content for memory retrieval",
        memory_type=MemoryType.NOTE,
        tags=["test", "python"],
        author="Claude",
        project_id=None,
        related_chunks=[],
        resource_links=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        embedding=[0.1, 0.2, 0.3],
        embedding_model="nomic-embed-text-v1.5",
        deleted_at=None,
        similarity_score=None
    )


class TestGetMemoryResource:
    """Tests for GetMemoryResource."""

    def test_get_name(self):
        """Test resource name."""
        resource = GetMemoryResource()
        assert resource.get_name() == "memories://get"

    @pytest.mark.asyncio
    async def test_get_success(
        self,
        mock_ctx,
        mock_memory_repository,
        sample_memory
    ):
        """Test successful memory retrieval."""
        resource = GetMemoryResource()

        # Mock repository response
        mock_memory_repository.get_by_id.return_value = sample_memory

        resource.inject_services({
            "memory_repository": mock_memory_repository
        })

        # Execute
        uri = f"memories://get/{str(sample_memory.id)}"
        result = await resource.get(mock_ctx, uri)

        # Assert
        assert result["id"] == str(sample_memory.id)
        assert result["title"] == "Test Memory"
        assert result["memory_type"] == "note"
        mock_memory_repository.get_by_id.assert_called_once_with(str(sample_memory.id))

    @pytest.mark.asyncio
    async def test_get_not_found(
        self,
        mock_ctx,
        mock_memory_repository
    ):
        """Test get when memory not found."""
        resource = GetMemoryResource()

        # Mock repository to return None
        mock_memory_repository.get_by_id.return_value = None

        resource.inject_services({
            "memory_repository": mock_memory_repository
        })

        # Execute and assert
        uri = f"memories://get/{str(uuid.uuid4())}"
        with pytest.raises(RuntimeError) as exc_info:
            await resource.get(mock_ctx, uri)
        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_get_invalid_uri_format(
        self,
        mock_ctx,
        mock_memory_repository
    ):
        """Test get with invalid URI format."""
        resource = GetMemoryResource()
        resource.inject_services({
            "memory_repository": mock_memory_repository
        })

        # Execute and assert
        uri = "memories://get/"  # Missing ID
        with pytest.raises(ValueError) as exc_info:
            await resource.get(mock_ctx, uri)
        assert "invalid" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_get_invalid_uuid(
        self,
        mock_ctx,
        mock_memory_repository
    ):
        """Test get with invalid UUID."""
        resource = GetMemoryResource()
        resource.inject_services({
            "memory_repository": mock_memory_repository
        })

        # Execute and assert
        uri = "memories://get/not-a-uuid"
        with pytest.raises(ValueError) as exc_info:
            await resource.get(mock_ctx, uri)
        assert "uuid" in str(exc_info.value).lower()


class TestListMemoriesResource:
    """Tests for ListMemoriesResource."""

    def test_get_name(self):
        """Test resource name."""
        resource = ListMemoriesResource()
        assert resource.get_name() == "memories://list"

    @pytest.mark.asyncio
    async def test_list_success_no_filters(
        self,
        mock_ctx,
        mock_memory_repository,
        mock_redis_client,
        sample_memory
    ):
        """Test successful memory listing without filters."""
        resource = ListMemoriesResource()

        # Mock repository response
        mock_memory_repository.list_memories.return_value = ([sample_memory], 1)

        resource.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis_client
        })

        # Execute
        uri = "memories://list"
        result = await resource.get(mock_ctx, uri)

        # Assert
        assert len(result["memories"]) == 1
        assert result["memories"][0]["title"] == "Test Memory"
        assert result["pagination"]["total"] == 1
        assert result["pagination"]["has_more"] is False

        # Verify cache was set
        mock_redis_client.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_with_filters(
        self,
        mock_ctx,
        mock_memory_repository,
        mock_redis_client,
        sample_memory
    ):
        """Test listing with filters."""
        resource = ListMemoriesResource()

        mock_memory_repository.list_memories.return_value = ([sample_memory], 1)

        resource.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis_client
        })

        # Execute
        uri = "memories://list?memory_type=note&tags=python&limit=5&offset=0"
        result = await resource.get(mock_ctx, uri)

        # Assert
        assert len(result["memories"]) == 1
        assert result["pagination"]["limit"] == 5
        mock_memory_repository.list_memories.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_cache_hit(
        self,
        mock_ctx,
        mock_memory_repository,
        mock_redis_client,
        sample_memory
    ):
        """Test cache hit scenario."""
        resource = ListMemoriesResource()

        # Mock Redis cache hit
        cached_response = {
            "memories": [sample_memory.model_dump(mode='json')],
            "pagination": {
                "limit": 10,
                "offset": 0,
                "total": 1,
                "has_more": False
            }
        }
        mock_redis_client.get.return_value = json.dumps(cached_response)

        resource.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis_client
        })

        # Execute
        uri = "memories://list"
        result = await resource.get(mock_ctx, uri)

        # Assert - result from cache
        assert len(result["memories"]) == 1
        # Repository should NOT be called (cache hit)
        mock_memory_repository.list_memories.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_pagination(
        self,
        mock_ctx,
        mock_memory_repository,
        mock_redis_client
    ):
        """Test pagination with has_more."""
        resource = ListMemoriesResource()

        # Mock 3 memories out of 10 total
        memories = [
            Memory(
                id=uuid.uuid4(),
                title=f"Memory {i}",
                content=f"Content {i}",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            for i in range(3)
        ]

        mock_memory_repository.list_memories.return_value = (memories, 10)

        resource.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis_client
        })

        # Execute
        uri = "memories://list?limit=3&offset=0"
        result = await resource.get(mock_ctx, uri)

        # Assert
        assert len(result["memories"]) == 3
        assert result["pagination"]["total"] == 10
        assert result["pagination"]["has_more"] is True  # 0 + 3 < 10


class TestSearchMemoriesResource:
    """Tests for SearchMemoriesResource."""

    def test_get_name(self):
        """Test resource name."""
        resource = SearchMemoriesResource()
        assert resource.get_name() == "memories://search"

    @pytest.mark.asyncio
    async def test_search_success(
        self,
        mock_ctx,
        mock_memory_repository,
        mock_redis_client,
        mock_embedding_service,
        sample_memory
    ):
        """Test successful memory search."""
        resource = SearchMemoriesResource()

        # Mock memory with similarity score
        search_result = Memory(
            **{**sample_memory.model_dump(), "similarity_score": 0.89}
        )

        # Mock repository search response
        mock_memory_repository.search_by_vector.return_value = ([search_result], 1)

        resource.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis_client,
            "embedding_service": mock_embedding_service
        })

        # Execute
        uri = "memories://search/async%20patterns"
        result = await resource.get(mock_ctx, uri)

        # Assert
        assert result["query"] == "async patterns"
        assert len(result["memories"]) == 1
        assert result["memories"][0]["similarity_score"] == 0.89
        assert result["metadata"]["threshold"] == 0.7

        # Verify embedding was generated
        mock_embedding_service.generate_embedding.assert_called_once_with("async patterns")
        # Verify repository search was called
        mock_memory_repository.search_by_vector.assert_called_once()
        # Verify cache was set
        mock_redis_client.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_cache_hit(
        self,
        mock_ctx,
        mock_memory_repository,
        mock_redis_client,
        mock_embedding_service
    ):
        """Test search cache hit."""
        resource = SearchMemoriesResource()

        # Mock Redis cache hit
        cached_response = {
            "query": "async patterns",
            "memories": [],
            "pagination": {"limit": 5, "offset": 0, "total": 0, "has_more": False},
            "metadata": {"threshold": 0.7, "embedding_model": "nomic-embed-text-v1.5"}
        }
        mock_redis_client.get.return_value = json.dumps(cached_response)

        resource.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis_client,
            "embedding_service": mock_embedding_service
        })

        # Execute
        uri = "memories://search/async%20patterns"
        result = await resource.get(mock_ctx, uri)

        # Assert - result from cache
        assert result["query"] == "async patterns"
        # Embedding service should NOT be called (cache hit)
        mock_embedding_service.generate_embedding.assert_not_called()
        # Repository should NOT be called (cache hit)
        mock_memory_repository.search_by_vector.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_with_filters(
        self,
        mock_ctx,
        mock_memory_repository,
        mock_redis_client,
        mock_embedding_service
    ):
        """Test search with filters and custom threshold."""
        resource = SearchMemoriesResource()

        mock_memory_repository.search_by_vector.return_value = ([], 0)

        resource.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis_client,
            "embedding_service": mock_embedding_service
        })

        # Execute
        uri = "memories://search/redis%20cache?memory_type=decision&threshold=0.9&limit=3"
        result = await resource.get(mock_ctx, uri)

        # Assert
        assert result["query"] == "redis cache"
        assert result["metadata"]["threshold"] == 0.9
        assert result["pagination"]["limit"] == 3

        # Verify repository was called with correct parameters
        call_args = mock_memory_repository.search_by_vector.call_args
        assert call_args.kwargs["limit"] == 3
        assert call_args.kwargs["distance_threshold"] == 0.9

    @pytest.mark.asyncio
    async def test_search_query_empty(
        self,
        mock_ctx,
        mock_memory_repository,
        mock_redis_client,
        mock_embedding_service
    ):
        """Test search with empty query."""
        resource = SearchMemoriesResource()

        resource.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis_client,
            "embedding_service": mock_embedding_service
        })

        # Execute and assert
        uri = "memories://search/"
        with pytest.raises(ValueError) as exc_info:
            await resource.get(mock_ctx, uri)
        assert "query" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_search_query_too_long(
        self,
        mock_ctx,
        mock_memory_repository,
        mock_redis_client,
        mock_embedding_service
    ):
        """Test search with query exceeding 500 chars."""
        resource = SearchMemoriesResource()

        resource.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis_client,
            "embedding_service": mock_embedding_service
        })

        # Execute and assert
        long_query = "a" * 501
        uri = f"memories://search/{long_query}"
        with pytest.raises(ValueError) as exc_info:
            await resource.get(mock_ctx, uri)
        assert "query" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_search_no_embedding_service(
        self,
        mock_ctx,
        mock_memory_repository,
        mock_redis_client
    ):
        """Test search when no embedding service available."""
        resource = SearchMemoriesResource()

        resource.inject_services({
            "memory_repository": mock_memory_repository,
            "redis_client": mock_redis_client,
            "embedding_service": None  # No embedding service
        })

        # Execute and assert
        uri = "memories://search/test"
        with pytest.raises(RuntimeError) as exc_info:
            await resource.get(mock_ctx, uri)
        assert "embedding service" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_search_no_redis_cache(
        self,
        mock_ctx,
        mock_memory_repository,
        mock_embedding_service,
        sample_memory
    ):
        """Test search without Redis cache (graceful degradation)."""
        resource = SearchMemoriesResource()

        search_result = Memory(
            **{**sample_memory.model_dump(), "similarity_score": 0.85}
        )

        mock_memory_repository.search_by_vector.return_value = ([search_result], 1)

        resource.inject_services({
            "memory_repository": mock_memory_repository,
            "redis_client": None,  # No Redis
            "embedding_service": mock_embedding_service
        })

        # Execute (should work without cache)
        uri = "memories://search/test"
        result = await resource.get(mock_ctx, uri)

        # Assert
        assert result["query"] == "test"
        assert len(result["memories"]) == 1

    @pytest.mark.asyncio
    async def test_search_url_encoding(
        self,
        mock_ctx,
        mock_memory_repository,
        mock_redis_client,
        mock_embedding_service
    ):
        """Test search with URL-encoded query."""
        resource = SearchMemoriesResource()

        mock_memory_repository.search_by_vector.return_value = ([], 0)

        resource.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis_client,
            "embedding_service": mock_embedding_service
        })

        # Execute - URL-encoded query "async/await patterns"
        uri = "memories://search/async%2Fawait%20patterns"
        result = await resource.get(mock_ctx, uri)

        # Assert - query should be decoded
        assert result["query"] == "async/await patterns"
        mock_embedding_service.generate_embedding.assert_called_with("async/await patterns")
