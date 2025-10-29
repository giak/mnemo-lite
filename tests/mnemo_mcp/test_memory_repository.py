"""
Tests for Memory Repository.

Tests CRUD operations, vector search, and error handling with mocked SQLAlchemy.
"""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from typing import List, Any

from db.repositories.memory_repository import MemoryRepository
from db.repositories.base import RepositoryError
from mnemo_mcp.models.memory_models import (
    Memory,
    MemoryCreate,
    MemoryUpdate,
    MemoryType,
    MemoryFilters,
)


class AsyncContextManagerMock:
    """Mock async context manager for SQLAlchemy engine.begin()."""

    def __init__(self, return_value: Any):
        self.return_value = return_value

    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


@pytest.fixture
def mock_engine():
    """Mock SQLAlchemy async engine."""
    # Use MagicMock (not AsyncMock) because begin() is a sync method
    # that returns an async context manager
    engine = MagicMock()
    return engine


@pytest.fixture
def mock_connection():
    """Mock SQLAlchemy async connection."""
    conn = AsyncMock()
    return conn


@pytest.fixture
def repository(mock_engine):
    """Create MemoryRepository with mocked engine."""
    return MemoryRepository(mock_engine)


@pytest.fixture
def sample_memory_create():
    """Sample MemoryCreate object."""
    return MemoryCreate(
        title="Test Memory",
        content="Test content for memory",
        memory_type=MemoryType.NOTE,
        tags=["test", "python"],
        author="Claude Test"
    )


@pytest.fixture
def sample_embedding():
    """Sample embedding vector."""
    return [0.1] * 768


class MockRow:
    """Mock database row."""

    def __init__(self, data: dict):
        self._data = data
        self._mapping = data

    def __getitem__(self, key):
        return self._data[key]


class TestMemoryRepositoryCreate:
    """Tests for create method."""

    @pytest.mark.asyncio
    async def test_create_success(self, repository, mock_engine, sample_memory_create, sample_embedding):
        """Test successful memory creation."""
        # Mock connection and result
        mock_conn = AsyncMock()
        mock_result = MagicMock()

        memory_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        mock_row = MockRow({
            "id": memory_id,
            "title": sample_memory_create.title,
            "content": sample_memory_create.content,
            "created_at": now,
            "updated_at": now,
            "memory_type": sample_memory_create.memory_type.value,
            "tags": "{test,python}",
            "author": sample_memory_create.author,
            "project_id": None,
            "embedding": f"[{','.join(map(str, sample_embedding))}]",
            "embedding_model": "nomic-embed-text-v1.5",
            "related_chunks": "{}",
            "resource_links": "[]",
            "deleted_at": None,
            "metadata": "{}"
        })

        mock_result.fetchone.return_value = mock_row
        mock_conn.execute = AsyncMock(return_value=mock_result)

        # Use proper async context manager
        mock_engine.begin.return_value = AsyncContextManagerMock(mock_conn)

        # Execute
        memory = await repository.create(sample_memory_create, sample_embedding)

        # Assert
        assert memory.title == "Test Memory"
        assert memory.memory_type == MemoryType.NOTE
        assert memory.tags == ["test", "python"]
        assert len(memory.embedding) == 768

    @pytest.mark.asyncio
    async def test_create_without_embedding(self, repository, mock_engine, sample_memory_create):
        """Test memory creation without embedding."""
        mock_conn = AsyncMock()
        mock_result = MagicMock()

        memory_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        mock_row = MockRow({
            "id": memory_id,
            "title": sample_memory_create.title,
            "content": sample_memory_create.content,
            "created_at": now,
            "updated_at": now,
            "memory_type": "note",
            "tags": "{test,python}",
            "author": "Claude Test",
            "project_id": None,
            "embedding": None,
            "embedding_model": None,
            "related_chunks": "{}",
            "resource_links": "[]",
            "deleted_at": None,
            "metadata": "{}"
        })

        mock_result.fetchone.return_value = mock_row
        mock_conn.execute = AsyncMock(return_value=mock_result)

        # Use proper async context manager
        mock_engine.begin.return_value = AsyncContextManagerMock(mock_conn)

        # Execute
        memory = await repository.create(sample_memory_create, embedding=None)

        # Assert
        assert memory.embedding is None
        assert memory.embedding_model is None

    @pytest.mark.asyncio
    async def test_create_duplicate_title(self, repository, mock_engine, sample_memory_create, sample_embedding):
        """Test creation with duplicate title+project_id."""
        mock_conn = AsyncMock()
        mock_conn.execute.side_effect = Exception("unique_title_per_project")

        # Use proper async context manager
        mock_engine.begin.return_value = AsyncContextManagerMock(mock_conn)

        # Execute and assert
        with pytest.raises(RepositoryError) as exc_info:
            await repository.create(sample_memory_create, sample_embedding)

        assert "already exists" in str(exc_info.value).lower()


class TestMemoryRepositoryGetById:
    """Tests for get_by_id method."""

    @pytest.mark.asyncio
    async def test_get_by_id_success(self, repository, mock_engine):
        """Test successful get by ID."""
        mock_conn = AsyncMock()
        mock_result = MagicMock()

        memory_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        mock_row = MockRow({
            "id": memory_id,
            "title": "Test Memory",
            "content": "Test content",
            "created_at": now,
            "updated_at": now,
            "memory_type": "note",
            "tags": "{python,async}",
            "author": "Claude",
            "project_id": None,
            "embedding": "[0.1,0.2,0.3]",
            "embedding_model": "nomic-embed-text-v1.5",
            "related_chunks": "{}",
            "resource_links": "[]",
            "deleted_at": None,
            "metadata": "{}"
        })

        mock_result.fetchone.return_value = mock_row
        mock_conn.execute = AsyncMock(return_value=mock_result)

        # Use proper async context manager
        mock_engine.begin.return_value = AsyncContextManagerMock(mock_conn)

        # Execute
        memory = await repository.get_by_id(str(memory_id))

        # Assert
        assert memory is not None
        assert memory.title == "Test Memory"
        assert memory.tags == ["python", "async"]
        assert memory.embedding == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repository, mock_engine):
        """Test get by ID when not found."""
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_conn.execute = AsyncMock(return_value=mock_result)

        # Use proper async context manager
        mock_engine.begin.return_value = AsyncContextManagerMock(mock_conn)

        # Execute
        memory = await repository.get_by_id(str(uuid.uuid4()))

        # Assert
        assert memory is None


class TestMemoryRepositoryUpdate:
    """Tests for update method."""

    @pytest.mark.asyncio
    async def test_update_partial(self, repository, mock_engine):
        """Test partial update (only title)."""
        mock_conn = AsyncMock()
        mock_result = MagicMock()

        memory_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        mock_row = MockRow({
            "id": memory_id,
            "title": "Updated Title",
            "content": "Original content",
            "created_at": now,
            "updated_at": now,
            "memory_type": "note",
            "tags": "{python}",
            "author": "Claude",
            "project_id": None,
            "embedding": "[0.1,0.2]",
            "embedding_model": "nomic-embed-text-v1.5",
            "related_chunks": "{}",
            "resource_links": "[]",
            "deleted_at": None,
            "metadata": "{}"
        })

        mock_result.fetchone.return_value = mock_row
        mock_conn.execute = AsyncMock(return_value=mock_result)

        # Use proper async context manager
        mock_engine.begin.return_value = AsyncContextManagerMock(mock_conn)

        # Execute
        memory_update = MemoryUpdate(title="Updated Title")
        memory = await repository.update(str(memory_id), memory_update)

        # Assert
        assert memory is not None
        assert memory.title == "Updated Title"

    @pytest.mark.asyncio
    async def test_update_not_found(self, repository, mock_engine):
        """Test update when memory not found."""
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_conn.execute = AsyncMock(return_value=mock_result)

        # Use proper async context manager
        mock_engine.begin.return_value = AsyncContextManagerMock(mock_conn)

        # Execute
        memory_update = MemoryUpdate(title="New Title")
        memory = await repository.update(str(uuid.uuid4()), memory_update)

        # Assert
        assert memory is None


class TestMemoryRepositorySoftDelete:
    """Tests for soft_delete method."""

    @pytest.mark.asyncio
    async def test_soft_delete_success(self, repository, mock_engine):
        """Test successful soft delete."""
        mock_conn = AsyncMock()
        mock_result = MagicMock()

        memory_id = uuid.uuid4()
        mock_row = MockRow({"id": memory_id})
        mock_result.fetchone.return_value = mock_row
        mock_conn.execute = AsyncMock(return_value=mock_result)

        # Use proper async context manager
        mock_engine.begin.return_value = AsyncContextManagerMock(mock_conn)

        # Execute
        success = await repository.soft_delete(str(memory_id))

        # Assert
        assert success is True

    @pytest.mark.asyncio
    async def test_soft_delete_not_found(self, repository, mock_engine):
        """Test soft delete when memory not found."""
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_conn.execute = AsyncMock(return_value=mock_result)

        # Use proper async context manager
        mock_engine.begin.return_value = AsyncContextManagerMock(mock_conn)

        # Execute
        success = await repository.soft_delete(str(uuid.uuid4()))

        # Assert
        assert success is False


class TestMemoryRepositoryDeletePermanently:
    """Tests for delete_permanently method."""

    @pytest.mark.asyncio
    async def test_delete_permanently_success(self, repository, mock_engine):
        """Test successful permanent delete."""
        mock_conn = AsyncMock()
        mock_result = MagicMock()

        memory_id = uuid.uuid4()
        mock_row = MockRow({"id": memory_id})
        mock_result.fetchone.return_value = mock_row
        mock_conn.execute = AsyncMock(return_value=mock_result)

        # Use proper async context manager
        mock_engine.begin.return_value = AsyncContextManagerMock(mock_conn)

        # Execute
        success = await repository.delete_permanently(str(memory_id))

        # Assert
        assert success is True


class TestMemoryRepositoryListMemories:
    """Tests for list_memories method."""

    @pytest.mark.asyncio
    async def test_list_memories_success(self, repository, mock_engine):
        """Test successful memory listing."""
        mock_conn = AsyncMock()

        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.fetchone.return_value = [5]  # total count

        # Mock data query
        mock_data_result = MagicMock()
        now = datetime.now(timezone.utc)

        mock_rows = [
            MockRow({
                "id": uuid.uuid4(),
                "title": f"Memory {i}",
                "content": f"Content {i}",
                "created_at": now,
                "updated_at": now,
                "memory_type": "note",
                "tags": "{python}",
                "author": "Claude",
                "project_id": None,
                "embedding_model": "nomic-embed-text-v1.5",
                "related_chunks": "{}",
                "resource_links": "[]",
                "deleted_at": None
            })
            for i in range(3)
        ]

        mock_data_result.fetchall.return_value = mock_rows

        # Setup execute to return different results for count vs data
        mock_conn.execute = AsyncMock(side_effect=[mock_count_result, mock_data_result])

        # Use proper async context manager
        mock_engine.begin.return_value = AsyncContextManagerMock(mock_conn)

        # Execute
        memories, total = await repository.list_memories(limit=10, offset=0)

        # Assert
        assert len(memories) == 3
        assert total == 5
        assert memories[0].title == "Memory 0"

    @pytest.mark.asyncio
    async def test_list_memories_with_filters(self, repository, mock_engine):
        """Test listing with filters."""
        mock_conn = AsyncMock()

        mock_count_result = MagicMock()
        mock_count_result.fetchone.return_value = [1]

        mock_data_result = MagicMock()
        now = datetime.now(timezone.utc)

        mock_row = MockRow({
            "id": uuid.uuid4(),
            "title": "Test Memory",
            "content": "Test content",
            "created_at": now,
            "updated_at": now,
            "memory_type": "decision",
            "tags": "{python,async}",
            "author": "Claude",
            "project_id": None,
            "embedding_model": "nomic-embed-text-v1.5",
            "related_chunks": "{}",
            "resource_links": "[]",
            "deleted_at": None
        })

        mock_data_result.fetchall.return_value = [mock_row]
        mock_conn.execute = AsyncMock(side_effect=[mock_count_result, mock_data_result])

        # Use proper async context manager
        mock_engine.begin.return_value = AsyncContextManagerMock(mock_conn)

        # Execute
        filters = MemoryFilters(
            memory_type=MemoryType.DECISION,
            tags=["python"]
        )
        memories, total = await repository.list_memories(filters=filters, limit=10, offset=0)

        # Assert
        assert len(memories) == 1
        assert memories[0].memory_type == MemoryType.DECISION


class TestMemoryRepositorySearchByVector:
    """Tests for search_by_vector method."""

    @pytest.mark.asyncio
    async def test_search_by_vector_success(self, repository, mock_engine):
        """Test successful vector search."""
        mock_conn = AsyncMock()

        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.fetchone.return_value = [3]

        # Mock search query
        mock_search_result = MagicMock()
        now = datetime.now(timezone.utc)

        mock_rows = [
            MockRow({
                "id": uuid.uuid4(),
                "title": "Async patterns",
                "content": "Using async/await in Python",
                "created_at": now,
                "updated_at": now,
                "memory_type": "note",
                "tags": "{python,async}",
                "author": "Claude",
                "project_id": None,
                "embedding": "[0.1,0.2,0.3]",
                "embedding_model": "nomic-embed-text-v1.5",
                "related_chunks": "{}",
                "resource_links": "[]",
                "deleted_at": None,
                "distance": 0.15,
                "similarity_score": 0.85
            })
        ]

        mock_search_result.fetchall.return_value = mock_rows
        mock_conn.execute = AsyncMock(side_effect=[mock_count_result, mock_search_result])

        # Use proper async context manager
        mock_engine.begin.return_value = AsyncContextManagerMock(mock_conn)

        # Execute
        vector = [0.1] * 768
        memories, total = await repository.search_by_vector(
            vector=vector,
            limit=5,
            distance_threshold=1.0
        )

        # Assert
        assert len(memories) == 1
        assert total == 3
        assert memories[0].similarity_score == 0.85
        assert memories[0].title == "Async patterns"

    @pytest.mark.asyncio
    async def test_search_by_vector_with_filters(self, repository, mock_engine):
        """Test vector search with filters."""
        mock_conn = AsyncMock()

        mock_count_result = MagicMock()
        mock_count_result.fetchone.return_value = [1]

        mock_search_result = MagicMock()
        mock_search_result.fetchall.return_value = []

        mock_conn.execute = AsyncMock(side_effect=[mock_count_result, mock_search_result])

        # Use proper async context manager
        mock_engine.begin.return_value = AsyncContextManagerMock(mock_conn)

        # Execute
        vector = [0.1] * 768
        filters = MemoryFilters(memory_type=MemoryType.TASK)
        memories, total = await repository.search_by_vector(
            vector=vector,
            filters=filters,
            limit=5
        )

        # Assert
        assert len(memories) == 0
        assert total == 1
