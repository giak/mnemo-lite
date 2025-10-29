"""
Tests for MCP memory tools.

Tests write_memory, update_memory, and delete_memory tools with mocked dependencies.
"""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from mnemo_mcp.tools.memory_tools import (
    WriteMemoryTool,
    UpdateMemoryTool,
    DeleteMemoryTool,
)
from mnemo_mcp.models.memory_models import (
    Memory,
    MemoryType,
)


@pytest.fixture
def mock_ctx():
    """Mock MCP Context."""
    ctx = MagicMock()
    # Mock elicit for elicitation (Story 23.11) - default to "yes" confirmation
    ctx.elicit = AsyncMock(return_value=MagicMock(value="yes"))
    return ctx


@pytest.fixture
def mock_memory_repository():
    """Mock MemoryRepository."""
    return AsyncMock()


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
        content="Test content",
        memory_type=MemoryType.NOTE,
        tags=["test", "python"],
        author="Claude",
        project_id=None,
        related_chunks=[],
        resource_links=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        embedding=[0.1] * 768,
        embedding_model="nomic-embed-text-v1.5",
        deleted_at=None
    )


class TestWriteMemoryTool:
    """Tests for WriteMemoryTool."""

    def test_get_name(self):
        """Test tool name."""
        tool = WriteMemoryTool()
        assert tool.get_name() == "write_memory"

    @pytest.mark.asyncio
    async def test_execute_success(
        self,
        mock_ctx,
        mock_memory_repository,
        mock_embedding_service,
        sample_memory
    ):
        """Test successful memory creation."""
        tool = WriteMemoryTool()

        # Inject services
        tool.inject_services({
            "memory_repository": mock_memory_repository,
            "embedding_service": mock_embedding_service
        })

        # Mock repository response
        mock_memory_repository.create.return_value = sample_memory

        # Execute
        response = await tool.execute(
            ctx=mock_ctx,
            title="Test Memory",
            content="Test content",
            memory_type="note",
            tags=["test", "python"],
            author="Claude"
        )

        # Assert
        assert response["id"] is not None
        assert response["title"] == "Test Memory"
        assert response["memory_type"] == "note"
        assert response["embedding_generated"] is True

        # Verify embedding service was called
        mock_embedding_service.generate_embedding.assert_called_once()
        # Verify repository was called
        mock_memory_repository.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_invalid_title_empty(self, mock_ctx):
        """Test execution with empty title."""
        tool = WriteMemoryTool()
        tool.inject_services({
            "memory_repository": AsyncMock(),
            "embedding_service": AsyncMock()
        })

        # Execute and assert
        with pytest.raises(ValueError) as exc_info:
            await tool.execute(
                ctx=mock_ctx,
                title="",
                content="Test content"
            )
        assert "title" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_invalid_title_too_long(self, mock_ctx):
        """Test execution with title exceeding 200 chars."""
        tool = WriteMemoryTool()
        tool.inject_services({
            "memory_repository": AsyncMock(),
            "embedding_service": AsyncMock()
        })

        # Execute and assert
        with pytest.raises(ValueError) as exc_info:
            await tool.execute(
                ctx=mock_ctx,
                title="a" * 201,
                content="Test content"
            )
        assert "title" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_invalid_content_empty(self, mock_ctx):
        """Test execution with empty content."""
        tool = WriteMemoryTool()
        tool.inject_services({
            "memory_repository": AsyncMock(),
            "embedding_service": AsyncMock()
        })

        # Execute and assert
        with pytest.raises(ValueError) as exc_info:
            await tool.execute(
                ctx=mock_ctx,
                title="Test",
                content=""
            )
        assert "content" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_invalid_memory_type(self, mock_ctx):
        """Test execution with invalid memory_type."""
        tool = WriteMemoryTool()
        tool.inject_services({
            "memory_repository": AsyncMock(),
            "embedding_service": AsyncMock()
        })

        # Execute and assert
        with pytest.raises(ValueError) as exc_info:
            await tool.execute(
                ctx=mock_ctx,
                title="Test",
                content="Content",
                memory_type="invalid_type"
            )
        assert "invalid_type" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_invalid_project_id(self, mock_ctx):
        """Test execution with invalid project_id UUID."""
        tool = WriteMemoryTool()
        tool.inject_services({
            "memory_repository": AsyncMock(),
            "embedding_service": AsyncMock()
        })

        # Execute and assert
        with pytest.raises(ValueError) as exc_info:
            await tool.execute(
                ctx=mock_ctx,
                title="Test",
                content="Content",
                project_id="not-a-uuid"
            )
        assert "project_id" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_invalid_related_chunks(self, mock_ctx):
        """Test execution with invalid related_chunks UUIDs."""
        tool = WriteMemoryTool()
        tool.inject_services({
            "memory_repository": AsyncMock(),
            "embedding_service": AsyncMock()
        })

        # Execute and assert
        with pytest.raises(ValueError) as exc_info:
            await tool.execute(
                ctx=mock_ctx,
                title="Test",
                content="Content",
                related_chunks=["not-a-uuid"]
            )
        assert "related_chunks" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_embedding_failure_graceful_degradation(
        self,
        mock_ctx,
        mock_memory_repository,
        sample_memory
    ):
        """Test graceful degradation when embedding generation fails."""
        tool = WriteMemoryTool()

        # Mock embedding service that fails
        mock_embedding_service = AsyncMock()
        mock_embedding_service.generate_embedding.side_effect = Exception("Embedding service error")

        # Mock memory without embedding
        memory_without_embedding = Memory(
            id=uuid.uuid4(),
            title="Test Memory",
            content="Test content",
            memory_type=MemoryType.NOTE,
            tags=[],
            author=None,
            project_id=None,
            related_chunks=[],
            resource_links=[],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            embedding=None,
            embedding_model=None,
            deleted_at=None
        )

        mock_memory_repository.create.return_value = memory_without_embedding

        tool.inject_services({
            "memory_repository": mock_memory_repository,
            "embedding_service": mock_embedding_service
        })

        # Execute (should not raise exception)
        response = await tool.execute(
            ctx=mock_ctx,
            title="Test Memory",
            content="Test content"
        )

        # Assert - memory was created without embedding
        assert response["id"] is not None
        assert response["embedding_generated"] is False
        mock_memory_repository.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_no_embedding_service(
        self,
        mock_ctx,
        mock_memory_repository,
        sample_memory
    ):
        """Test execution when no embedding service available."""
        tool = WriteMemoryTool()

        # Mock memory without embedding
        memory_without_embedding = Memory(
            id=uuid.uuid4(),
            title="Test Memory",
            content="Test content",
            memory_type=MemoryType.NOTE,
            tags=[],
            author=None,
            project_id=None,
            related_chunks=[],
            resource_links=[],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            embedding=None,
            embedding_model=None,
            deleted_at=None
        )

        mock_memory_repository.create.return_value = memory_without_embedding

        tool.inject_services({
            "memory_repository": mock_memory_repository,
            "embedding_service": None  # No embedding service
        })

        # Execute (should not raise exception)
        response = await tool.execute(
            ctx=mock_ctx,
            title="Test Memory",
            content="Test content"
        )

        # Assert
        assert response["embedding_generated"] is False


class TestUpdateMemoryTool:
    """Tests for UpdateMemoryTool."""

    def test_get_name(self):
        """Test tool name."""
        tool = UpdateMemoryTool()
        assert tool.get_name() == "update_memory"

    @pytest.mark.asyncio
    async def test_execute_update_title_success(
        self,
        mock_ctx,
        mock_memory_repository,
        mock_embedding_service,
        sample_memory
    ):
        """Test successful title update."""
        tool = UpdateMemoryTool()

        # Mock get_by_id to return existing memory
        mock_memory_repository.get_by_id.return_value = sample_memory

        # Mock updated memory
        updated_memory = Memory(
            **{**sample_memory.model_dump(), "title": "Updated Title"}
        )
        mock_memory_repository.update.return_value = updated_memory

        tool.inject_services({
            "memory_repository": mock_memory_repository,
            "embedding_service": mock_embedding_service
        })

        # Execute
        response = await tool.execute(
            ctx=mock_ctx,
            id=str(sample_memory.id),
            title="Updated Title"
        )

        # Assert
        assert response["id"] == str(sample_memory.id)
        assert response["embedding_regenerated"] is True  # Title changed
        mock_memory_repository.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_update_tags_only(
        self,
        mock_ctx,
        mock_memory_repository,
        sample_memory
    ):
        """Test update with only tags (no embedding regen)."""
        tool = UpdateMemoryTool()

        mock_memory_repository.get_by_id.return_value = sample_memory

        updated_memory = Memory(
            **{**sample_memory.model_dump(), "tags": ["new", "tags"]}
        )
        mock_memory_repository.update.return_value = updated_memory

        tool.inject_services({
            "memory_repository": mock_memory_repository,
            "embedding_service": AsyncMock()
        })

        # Execute
        response = await tool.execute(
            ctx=mock_ctx,
            id=str(sample_memory.id),
            tags=["new", "tags"]
        )

        # Assert
        assert response["embedding_regenerated"] is False  # No title/content change

    @pytest.mark.asyncio
    async def test_execute_invalid_memory_id(self, mock_ctx):
        """Test update with invalid memory ID."""
        tool = UpdateMemoryTool()
        tool.inject_services({
            "memory_repository": AsyncMock(),
            "embedding_service": AsyncMock()
        })

        # Execute and assert
        with pytest.raises(ValueError) as exc_info:
            await tool.execute(
                ctx=mock_ctx,
                id="not-a-uuid",
                title="New Title"
            )
        assert "uuid" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_memory_not_found(
        self,
        mock_ctx,
        mock_memory_repository
    ):
        """Test update when memory not found."""
        tool = UpdateMemoryTool()

        # Mock get_by_id to return None
        mock_memory_repository.get_by_id.return_value = None

        tool.inject_services({
            "memory_repository": mock_memory_repository,
            "embedding_service": AsyncMock()
        })

        # Execute and assert
        with pytest.raises(RuntimeError) as exc_info:
            await tool.execute(
                ctx=mock_ctx,
                id=str(uuid.uuid4()),
                title="New Title"
            )
        assert "not found" in str(exc_info.value).lower()


class TestDeleteMemoryTool:
    """Tests for DeleteMemoryTool."""

    def test_get_name(self):
        """Test tool name."""
        tool = DeleteMemoryTool()
        assert tool.get_name() == "delete_memory"

    @pytest.mark.asyncio
    async def test_execute_soft_delete_success(
        self,
        mock_ctx,
        mock_memory_repository,
        sample_memory
    ):
        """Test successful soft delete."""
        tool = DeleteMemoryTool()

        # Mock get_by_id to return existing memory
        mock_memory_repository.get_by_id.return_value = sample_memory

        # Mock soft_delete to return True
        mock_memory_repository.soft_delete.return_value = True

        tool.inject_services({
            "memory_repository": mock_memory_repository
        })

        # Execute
        response = await tool.execute(
            ctx=mock_ctx,
            id=str(sample_memory.id),
            permanent=False
        )

        # Assert
        assert response["id"] == str(sample_memory.id)
        assert response["permanent"] is False
        assert response["can_restore"] is True
        mock_memory_repository.soft_delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_hard_delete_requires_soft_delete_first(
        self,
        mock_ctx,
        mock_memory_repository,
        sample_memory
    ):
        """Test hard delete requires soft delete first."""
        tool = DeleteMemoryTool()

        # Mock memory not soft deleted yet (deleted_at is None)
        mock_memory_repository.get_by_id.return_value = sample_memory

        tool.inject_services({
            "memory_repository": mock_memory_repository
        })

        # Execute and assert
        with pytest.raises(ValueError) as exc_info:
            await tool.execute(
                ctx=mock_ctx,
                id=str(sample_memory.id),
                permanent=True
            )
        assert "soft deleted" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_hard_delete_success(
        self,
        mock_ctx,
        mock_memory_repository
    ):
        """Test successful hard delete."""
        tool = DeleteMemoryTool()

        # Mock memory that is already soft deleted
        soft_deleted_memory = Memory(
            id=uuid.uuid4(),
            title="Test",
            content="Content",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            deleted_at=datetime.now(timezone.utc)  # Soft deleted
        )

        mock_memory_repository.get_by_id.return_value = soft_deleted_memory
        mock_memory_repository.delete_permanently.return_value = True

        tool.inject_services({
            "memory_repository": mock_memory_repository
        })

        # Execute
        response = await tool.execute(
            ctx=mock_ctx,
            id=str(soft_deleted_memory.id),
            permanent=True
        )

        # Assert
        assert response["permanent"] is True
        assert response["can_restore"] is False
        mock_memory_repository.delete_permanently.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_invalid_memory_id(self, mock_ctx):
        """Test delete with invalid memory ID."""
        tool = DeleteMemoryTool()
        tool.inject_services({
            "memory_repository": AsyncMock()
        })

        # Execute and assert
        with pytest.raises(ValueError) as exc_info:
            await tool.execute(
                ctx=mock_ctx,
                id="not-a-uuid"
            )
        assert "uuid" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_memory_not_found(
        self,
        mock_ctx,
        mock_memory_repository
    ):
        """Test delete when memory not found."""
        tool = DeleteMemoryTool()

        # Mock get_by_id to return None
        mock_memory_repository.get_by_id.return_value = None

        tool.inject_services({
            "memory_repository": mock_memory_repository
        })

        # Execute and assert
        with pytest.raises(RuntimeError) as exc_info:
            await tool.execute(
                ctx=mock_ctx,
                id=str(uuid.uuid4())
            )
        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_soft_delete_failed(
        self,
        mock_ctx,
        mock_memory_repository,
        sample_memory
    ):
        """Test soft delete when operation fails."""
        tool = DeleteMemoryTool()

        mock_memory_repository.get_by_id.return_value = sample_memory
        mock_memory_repository.soft_delete.return_value = False  # Failed

        tool.inject_services({
            "memory_repository": mock_memory_repository
        })

        # Execute and assert
        with pytest.raises(RuntimeError) as exc_info:
            await tool.execute(
                ctx=mock_ctx,
                id=str(sample_memory.id)
            )
        assert "failed" in str(exc_info.value).lower()
