"""
Tests for MCP memory models.

Tests Pydantic model validation, field validators, and serialization.
"""

import pytest
import uuid
from datetime import datetime, timezone
from pydantic import ValidationError

from mnemo_mcp.models.memory_models import (
    MemoryType,
    MemoryBase,
    MemoryCreate,
    MemoryUpdate,
    Memory,
    MemoryResponse,
    DeleteMemoryResponse,
    PaginationMetadata,
    MemoryListResponse,
    MemorySearchResponse,
    MemoryFilters,
)


class TestMemoryType:
    """Tests for MemoryType enum."""

    def test_memory_type_values(self):
        """Test all memory type values."""
        assert MemoryType.NOTE.value == "note"
        assert MemoryType.DECISION.value == "decision"
        assert MemoryType.TASK.value == "task"
        assert MemoryType.REFERENCE.value == "reference"
        assert MemoryType.CONVERSATION.value == "conversation"

    def test_memory_type_count(self):
        """Test number of memory types."""
        assert len(list(MemoryType)) == 5


class TestMemoryBase:
    """Tests for MemoryBase model."""

    def test_memory_base_valid(self):
        """Test valid MemoryBase creation."""
        memory = MemoryBase(
            title="Test Memory",
            content="Test content",
            memory_type=MemoryType.NOTE,
            tags=["test", "python"],
            author="Claude",
        )
        assert memory.title == "Test Memory"
        assert memory.content == "Test content"
        assert memory.memory_type == MemoryType.NOTE
        assert memory.tags == ["test", "python"]
        assert memory.author == "Claude"

    def test_memory_base_title_too_long(self):
        """Test title exceeding 200 chars."""
        with pytest.raises(ValidationError) as exc_info:
            MemoryBase(
                title="a" * 201,
                content="Test content"
            )
        assert "title" in str(exc_info.value).lower()

    def test_memory_base_title_empty(self):
        """Test empty title."""
        with pytest.raises(ValidationError):
            MemoryBase(
                title="",
                content="Test content"
            )

    def test_memory_base_content_empty(self):
        """Test empty content."""
        with pytest.raises(ValidationError):
            MemoryBase(
                title="Test",
                content=""
            )

    def test_memory_base_defaults(self):
        """Test default values."""
        memory = MemoryBase(
            title="Test",
            content="Content"
        )
        assert memory.memory_type == MemoryType.NOTE
        assert memory.tags == []
        assert memory.author is None
        assert memory.project_id is None
        assert memory.related_chunks == []
        assert memory.resource_links == []

    def test_tags_validator_lowercase(self):
        """Test tags are converted to lowercase."""
        memory = MemoryBase(
            title="Test",
            content="Content",
            tags=["Python", "ASYNC", "Test"]
        )
        assert memory.tags == ["python", "async", "test"]

    def test_tags_validator_duplicates_removed(self):
        """Test duplicate tags are removed."""
        memory = MemoryBase(
            title="Test",
            content="Content",
            tags=["python", "async", "python", "test"]
        )
        assert memory.tags == ["python", "async", "test"]

    def test_tags_validator_whitespace_trimmed(self):
        """Test whitespace is trimmed from tags."""
        memory = MemoryBase(
            title="Test",
            content="Content",
            tags=["  python  ", "async", "  test  "]
        )
        assert memory.tags == ["python", "async", "test"]

    def test_tags_validator_empty_strings_removed(self):
        """Test empty strings are removed from tags."""
        memory = MemoryBase(
            title="Test",
            content="Content",
            tags=["python", "", "  ", "async"]
        )
        assert memory.tags == ["python", "async"]

    def test_resource_links_valid(self):
        """Test valid resource links."""
        memory = MemoryBase(
            title="Test",
            content="Content",
            resource_links=[
                {"uri": "code://chunk/123", "type": "related"},
                {"uri": "memories://get/456", "type": "reference"}
            ]
        )
        assert len(memory.resource_links) == 2
        assert memory.resource_links[0]["uri"] == "code://chunk/123"

    def test_resource_links_missing_uri(self):
        """Test resource link without uri field."""
        with pytest.raises(ValidationError) as exc_info:
            MemoryBase(
                title="Test",
                content="Content",
                resource_links=[{"type": "related"}]
            )
        assert "uri" in str(exc_info.value).lower()

    def test_project_id_valid_uuid(self):
        """Test valid project_id UUID."""
        project_uuid = uuid.uuid4()
        memory = MemoryBase(
            title="Test",
            content="Content",
            project_id=project_uuid
        )
        assert memory.project_id == project_uuid

    def test_related_chunks_valid_uuids(self):
        """Test valid related_chunks UUIDs."""
        chunk1 = uuid.uuid4()
        chunk2 = uuid.uuid4()
        memory = MemoryBase(
            title="Test",
            content="Content",
            related_chunks=[chunk1, chunk2]
        )
        assert len(memory.related_chunks) == 2
        assert memory.related_chunks[0] == chunk1


class TestMemoryCreate:
    """Tests for MemoryCreate model."""

    def test_memory_create_inherits_validation(self):
        """Test MemoryCreate inherits all MemoryBase validation."""
        with pytest.raises(ValidationError):
            MemoryCreate(
                title="a" * 201,
                content="Test"
            )


class TestMemoryUpdate:
    """Tests for MemoryUpdate model."""

    def test_memory_update_all_optional(self):
        """Test all fields are optional."""
        update = MemoryUpdate()
        assert update.title is None
        assert update.content is None
        assert update.memory_type is None
        assert update.tags is None

    def test_memory_update_partial(self):
        """Test partial update with only some fields."""
        update = MemoryUpdate(
            title="Updated title",
            tags=["new", "tags"]
        )
        assert update.title == "Updated title"
        assert update.tags == ["new", "tags"]
        assert update.content is None
        assert update.memory_type is None

    def test_memory_update_tags_validation(self):
        """Test tags validation works for updates."""
        update = MemoryUpdate(
            tags=["Python", "ASYNC", "  test  "]
        )
        assert update.tags == ["python", "async", "test"]

    def test_memory_update_title_too_long(self):
        """Test title validation works for updates."""
        with pytest.raises(ValidationError):
            MemoryUpdate(title="a" * 201)

    def test_memory_update_empty_content(self):
        """Test content validation works for updates."""
        with pytest.raises(ValidationError):
            MemoryUpdate(content="")


class TestMemory:
    """Tests for Memory model (complete with all fields)."""

    def test_memory_complete_model(self):
        """Test complete Memory model with all fields."""
        memory_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        memory = Memory(
            id=memory_id,
            title="Test Memory",
            content="Test content",
            memory_type=MemoryType.DECISION,
            tags=["architecture", "redis"],
            author="Claude",
            project_id=uuid.uuid4(),
            related_chunks=[uuid.uuid4()],
            resource_links=[{"uri": "code://chunk/123", "type": "related"}],
            created_at=now,
            updated_at=now,
            embedding=[0.1, 0.2, 0.3],
            embedding_model="nomic-embed-text-v1.5",
            deleted_at=None,
            similarity_score=None
        )

        assert memory.id == memory_id
        assert memory.title == "Test Memory"
        assert memory.memory_type == MemoryType.DECISION
        assert memory.created_at == now
        assert memory.embedding == [0.1, 0.2, 0.3]

    def test_memory_with_similarity_score(self):
        """Test Memory with similarity_score (search result)."""
        memory = Memory(
            id=uuid.uuid4(),
            title="Test",
            content="Content",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            similarity_score=0.89
        )
        assert memory.similarity_score == 0.89

    def test_memory_with_deleted_at(self):
        """Test Memory with deleted_at (soft deleted)."""
        now = datetime.now(timezone.utc)
        memory = Memory(
            id=uuid.uuid4(),
            title="Test",
            content="Content",
            created_at=now,
            updated_at=now,
            deleted_at=now
        )
        assert memory.deleted_at == now


class TestMemoryResponse:
    """Tests for MemoryResponse model."""

    def test_memory_response_valid(self):
        """Test valid MemoryResponse."""
        response = MemoryResponse(
            id=uuid.uuid4(),
            title="Test Memory",
            memory_type=MemoryType.NOTE,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            embedding_generated=True
        )
        assert response.embedding_generated is True
        assert isinstance(response.id, uuid.UUID)


class TestDeleteMemoryResponse:
    """Tests for DeleteMemoryResponse model."""

    def test_delete_memory_response_soft_delete(self):
        """Test soft delete response."""
        response = DeleteMemoryResponse(
            id=uuid.uuid4(),
            deleted_at=datetime.now(timezone.utc),
            permanent=False,
            can_restore=True
        )
        assert response.permanent is False
        assert response.can_restore is True

    def test_delete_memory_response_hard_delete(self):
        """Test hard delete response."""
        response = DeleteMemoryResponse(
            id=uuid.uuid4(),
            deleted_at=datetime.now(timezone.utc),
            permanent=True,
            can_restore=False
        )
        assert response.permanent is True
        assert response.can_restore is False


class TestPaginationMetadata:
    """Tests for PaginationMetadata model."""

    def test_pagination_metadata_valid(self):
        """Test valid pagination metadata."""
        pagination = PaginationMetadata(
            limit=10,
            offset=0,
            total=42,
            has_more=True
        )
        assert pagination.limit == 10
        assert pagination.total == 42
        assert pagination.has_more is True

    def test_pagination_metadata_no_more(self):
        """Test pagination with no more results."""
        pagination = PaginationMetadata(
            limit=10,
            offset=30,
            total=35,
            has_more=False
        )
        assert pagination.has_more is False


class TestMemoryListResponse:
    """Tests for MemoryListResponse model."""

    def test_memory_list_response_valid(self):
        """Test valid memory list response."""
        memory = Memory(
            id=uuid.uuid4(),
            title="Test",
            content="Content",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        response = MemoryListResponse(
            memories=[memory],
            pagination=PaginationMetadata(
                limit=10,
                offset=0,
                total=1,
                has_more=False
            )
        )

        assert len(response.memories) == 1
        assert response.pagination.total == 1


class TestMemorySearchResponse:
    """Tests for MemorySearchResponse model."""

    def test_memory_search_response_valid(self):
        """Test valid memory search response."""
        memory = Memory(
            id=uuid.uuid4(),
            title="Test",
            content="Content",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            similarity_score=0.89
        )

        response = MemorySearchResponse(
            query="async patterns",
            memories=[memory],
            pagination=PaginationMetadata(
                limit=5,
                offset=0,
                total=1,
                has_more=False
            ),
            metadata={
                "threshold": 0.7,
                "embedding_model": "nomic-embed-text-v1.5"
            }
        )

        assert response.query == "async patterns"
        assert len(response.memories) == 1
        assert response.metadata["threshold"] == 0.7


class TestMemoryFilters:
    """Tests for MemoryFilters model."""

    def test_memory_filters_all_fields(self):
        """Test filters with all fields."""
        filters = MemoryFilters(
            project_id=uuid.uuid4(),
            memory_type=MemoryType.DECISION,
            tags=["python", "async"],
            author="Claude",
            include_deleted=True,
            created_after=datetime.now(timezone.utc),
            created_before=datetime.now(timezone.utc)
        )

        assert filters.memory_type == MemoryType.DECISION
        assert len(filters.tags) == 2
        assert filters.include_deleted is True

    def test_memory_filters_defaults(self):
        """Test filter defaults."""
        filters = MemoryFilters()

        assert filters.project_id is None
        assert filters.memory_type is None
        assert filters.tags == []
        assert filters.include_deleted is False

    def test_memory_filters_partial(self):
        """Test filters with only some fields."""
        filters = MemoryFilters(
            memory_type=MemoryType.TASK,
            tags=["todo"]
        )

        assert filters.memory_type == MemoryType.TASK
        assert filters.tags == ["todo"]
        assert filters.project_id is None
