"""
Tests for event_service.py - Event business logic with auto-embedding generation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4, UUID
from typing import List

from services.event_service import EventService
from models.event_models import EventModel, EventCreate
from interfaces.repositories import EventRepositoryProtocol
from interfaces.services import EmbeddingServiceProtocol


# === Fixtures ===


@pytest.fixture
def mock_repository():
    """Create mock event repository."""
    repo = AsyncMock(spec=EventRepositoryProtocol)
    return repo


@pytest.fixture
def mock_embedding_service():
    """Create mock embedding service."""
    svc = AsyncMock(spec=EmbeddingServiceProtocol)
    svc.generate_embedding = AsyncMock(return_value=[0.1] * 768)
    return svc


@pytest.fixture
def event_service(mock_repository, mock_embedding_service):
    """Create EventService with default config."""
    return EventService(
        repository=mock_repository,
        embedding_service=mock_embedding_service
    )


@pytest.fixture
def event_service_no_auto(mock_repository, mock_embedding_service):
    """Create EventService with auto-generation disabled."""
    return EventService(
        repository=mock_repository,
        embedding_service=mock_embedding_service,
        config={"auto_generate_embeddings": False}
    )


@pytest.fixture
def event_service_hard_fail(mock_repository, mock_embedding_service):
    """Create EventService with hard fail strategy."""
    return EventService(
        repository=mock_repository,
        embedding_service=mock_embedding_service,
        config={"embedding_fail_strategy": "hard"}
    )


@pytest.fixture
def sample_event_data():
    """Create sample event creation data."""
    return EventCreate(
        content={"text": "Sample event content"},
        metadata={"type": "test", "source": "unit_test"}
    )


@pytest.fixture
def sample_event_model():
    """Create sample event model."""
    return EventModel(
        id=uuid4(),
        timestamp="2025-10-14T10:00:00Z",
        content={"text": "Sample event content"},
        metadata={"type": "test"},
        embedding=[0.1] * 768
    )


# === Initialization Tests ===


def test_event_service_initialization_default_config(mock_repository, mock_embedding_service):
    """
    Test EventService initialization with default configuration.

    Verifies default values for auto_generate, fail_strategy, and source_fields.
    """
    service = EventService(
        repository=mock_repository,
        embedding_service=mock_embedding_service
    )

    assert service.repo == mock_repository
    assert service.embedding_svc == mock_embedding_service
    assert service.auto_generate is True
    assert service.fail_strategy == "soft"
    assert "text" in service.source_fields
    assert "message" in service.source_fields


def test_event_service_initialization_custom_config(mock_repository, mock_embedding_service):
    """
    Test EventService initialization with custom configuration.

    Verifies that config overrides are applied correctly.
    """
    custom_config = {
        "auto_generate_embeddings": False,
        "embedding_fail_strategy": "hard",
        "embedding_source_fields": ["custom_field"]
    }

    service = EventService(
        repository=mock_repository,
        embedding_service=mock_embedding_service,
        config=custom_config
    )

    assert service.auto_generate is False
    assert service.fail_strategy == "hard"
    assert service.source_fields == ["custom_field"]


# === create_event Tests ===


@pytest.mark.anyio
async def test_create_event_with_provided_embedding(event_service, mock_repository, sample_event_data):
    """
    Test event creation when embedding is already provided.

    Verifies that embedding generation is skipped when embedding exists.
    """
    # Event with embedding already provided
    event_data = EventCreate(
        content={"text": "Test content"},
        metadata={"type": "test"},
        embedding=[0.5] * 768  # Pre-generated embedding
    )

    mock_event = EventModel(
        id=uuid4(),
        timestamp="2025-10-14T10:00:00Z",
        content=event_data.content,
        metadata=event_data.metadata,
        embedding=event_data.embedding
    )
    mock_repository.add = AsyncMock(return_value=mock_event)

    result = await event_service.create_event(event_data)

    assert result == mock_event
    mock_repository.add.assert_called_once_with(event_data)
    event_service.embedding_svc.generate_embedding.assert_not_called()


@pytest.mark.anyio
async def test_create_event_generates_embedding_from_text(event_service, mock_repository, mock_embedding_service):
    """
    Test automatic embedding generation from content text.

    Verifies that embedding is generated when not provided.
    """
    event_data = EventCreate(
        content={"text": "Generate embedding for this"},
        metadata={"type": "test"}
    )

    generated_embedding = [0.2] * 768
    mock_embedding_service.generate_embedding.return_value = generated_embedding

    mock_event = EventModel(
        id=uuid4(),
        timestamp="2025-10-14T10:00:00Z",
        content=event_data.content,
        metadata=event_data.metadata,
        embedding=generated_embedding
    )
    mock_repository.add.return_value = mock_event

    result = await event_service.create_event(event_data)

    assert result == mock_event
    mock_embedding_service.generate_embedding.assert_called_once_with("Generate embedding for this")
    assert event_data.embedding == generated_embedding


@pytest.mark.anyio
async def test_create_event_skips_generation_when_auto_disabled(event_service_no_auto, mock_repository, mock_embedding_service):
    """
    Test that embedding generation is skipped when auto_generate=False.

    Verifies config setting is respected.
    """
    event_data = EventCreate(
        content={"text": "No embedding generated"},
        metadata={"type": "test"}
    )

    mock_event = EventModel(
        id=uuid4(),
        timestamp="2025-10-14T10:00:00Z",
        content=event_data.content,
        metadata=event_data.metadata,
        embedding=None
    )
    mock_repository.add.return_value = mock_event

    result = await event_service_no_auto.create_event(event_data)

    assert result == mock_event
    mock_embedding_service.generate_embedding.assert_not_called()


@pytest.mark.anyio
async def test_create_event_handles_embedding_error_soft(event_service, mock_repository, mock_embedding_service):
    """
    Test soft error handling when embedding generation fails.

    Verifies that event is still created with warning logged.
    """
    event_data = EventCreate(
        content={"text": "This will fail"},
        metadata={"type": "test"}
    )

    mock_embedding_service.generate_embedding.side_effect = Exception("Embedding service down")

    mock_event = EventModel(
        id=uuid4(),
        timestamp="2025-10-14T10:00:00Z",
        content=event_data.content,
        metadata=event_data.metadata,
        embedding=None
    )
    mock_repository.add.return_value = mock_event

    # Should NOT raise exception (soft fail)
    result = await event_service.create_event(event_data)

    assert result == mock_event
    mock_repository.add.assert_called_once()


@pytest.mark.anyio
async def test_create_event_handles_embedding_error_hard(event_service_hard_fail, mock_embedding_service):
    """
    Test hard error handling when embedding generation fails.

    Verifies that exception is raised and event is not created.
    """
    event_data = EventCreate(
        content={"text": "This will fail hard"},
        metadata={"type": "test"}
    )

    mock_embedding_service.generate_embedding.side_effect = Exception("Embedding service down")

    # Should raise exception (hard fail)
    with pytest.raises(Exception, match="Embedding service down"):
        await event_service_hard_fail.create_event(event_data)

    event_service_hard_fail.repo.add.assert_not_called()


@pytest.mark.anyio
async def test_create_event_extracts_text_from_multiple_fields(event_service, mock_repository, mock_embedding_service):
    """
    Test text extraction with priority order.

    Verifies that source_fields are tried in order.
    """
    # Test with 'message' field (should use this)
    event_data = EventCreate(
        content={"message": "Use this", "title": "Not this"},
        metadata={"type": "test"}
    )

    mock_event = EventModel(
        id=uuid4(),
        timestamp="2025-10-14T10:00:00Z",
        content=event_data.content,
        metadata=event_data.metadata,
        embedding=[0.1] * 768
    )
    mock_repository.add.return_value = mock_event

    await event_service.create_event(event_data)

    mock_embedding_service.generate_embedding.assert_called_once_with("Use this")


@pytest.mark.anyio
async def test_create_event_handles_no_text_content(event_service, mock_repository, mock_embedding_service):
    """
    Test event creation when no extractable text is found.

    Verifies that event is created without embedding.
    """
    event_data = EventCreate(
        content={"random_field": "Not in source_fields"},
        metadata={"type": "test"}
    )

    mock_event = EventModel(
        id=uuid4(),
        timestamp="2025-10-14T10:00:00Z",
        content=event_data.content,
        metadata=event_data.metadata,
        embedding=None
    )
    mock_repository.add.return_value = mock_event

    result = await event_service.create_event(event_data)

    assert result == mock_event
    mock_embedding_service.generate_embedding.assert_not_called()


# === _extract_text_for_embedding Tests ===


def test_extract_text_priority_order(event_service):
    """
    Test that text extraction follows priority order.

    Default priority: text > body > message > content > title
    """
    # Test 'text' has highest priority
    content1 = {"text": "First", "body": "Second", "message": "Third"}
    assert event_service._extract_text_for_embedding(content1) == "First"

    # Test 'body' when 'text' missing
    content2 = {"body": "Second", "message": "Third"}
    assert event_service._extract_text_for_embedding(content2) == "Second"

    # Test 'message' when text/body missing
    content3 = {"message": "Third", "title": "Fourth"}
    assert event_service._extract_text_for_embedding(content3) == "Third"


def test_extract_text_ignores_empty_strings(event_service):
    """
    Test that empty/whitespace strings are skipped.

    Verifies that only non-empty text is extracted.
    """
    content = {"text": "  ", "message": "Actual content"}
    assert event_service._extract_text_for_embedding(content) == "Actual content"


def test_extract_text_returns_none_when_no_text(event_service):
    """
    Test that None is returned when no valid text field exists.
    """
    content = {"random_field": "Not in source_fields"}
    assert event_service._extract_text_for_embedding(content) is None


def test_extract_text_strips_whitespace(event_service):
    """
    Test that extracted text is stripped of surrounding whitespace.
    """
    content = {"text": "  Content with spaces  "}
    assert event_service._extract_text_for_embedding(content) == "Content with spaces"


# === get_event Tests ===


@pytest.mark.anyio
async def test_get_event_by_id_success(event_service, mock_repository, sample_event_model):
    """
    Test successful event retrieval by ID.
    """
    event_id = sample_event_model.id
    mock_repository.get_by_id.return_value = sample_event_model

    result = await event_service.get_event(event_id)

    assert result == sample_event_model
    mock_repository.get_by_id.assert_called_once_with(event_id)


@pytest.mark.anyio
async def test_get_event_by_id_not_found(event_service, mock_repository):
    """
    Test event retrieval when ID doesn't exist.
    """
    event_id = uuid4()
    mock_repository.get_by_id.return_value = None

    result = await event_service.get_event(event_id)

    assert result is None
    mock_repository.get_by_id.assert_called_once_with(event_id)


# === update_event_metadata Tests ===


@pytest.mark.anyio
async def test_update_event_metadata_success(event_service, mock_repository, sample_event_model):
    """
    Test successful metadata update.
    """
    event_id = sample_event_model.id
    new_metadata = {"updated": "yes", "version": 2}
    mock_repository.update_metadata.return_value = sample_event_model

    result = await event_service.update_event_metadata(event_id, new_metadata)

    assert result == sample_event_model
    mock_repository.update_metadata.assert_called_once_with(event_id, new_metadata)


@pytest.mark.anyio
async def test_update_event_metadata_not_found(event_service, mock_repository):
    """
    Test metadata update when event doesn't exist.
    """
    event_id = uuid4()
    new_metadata = {"updated": "yes"}
    mock_repository.update_metadata.return_value = None

    result = await event_service.update_event_metadata(event_id, new_metadata)

    assert result is None


# === delete_event Tests ===


@pytest.mark.anyio
async def test_delete_event_success(event_service, mock_repository):
    """
    Test successful event deletion.
    """
    event_id = uuid4()
    mock_repository.delete.return_value = True

    result = await event_service.delete_event(event_id)

    assert result is True
    mock_repository.delete.assert_called_once_with(event_id)


@pytest.mark.anyio
async def test_delete_event_not_found(event_service, mock_repository):
    """
    Test deletion when event doesn't exist.
    """
    event_id = uuid4()
    mock_repository.delete.return_value = False

    result = await event_service.delete_event(event_id)

    assert result is False


# === filter_events_by_metadata Tests ===


@pytest.mark.anyio
async def test_filter_events_by_metadata(event_service, mock_repository, sample_event_model):
    """
    Test filtering events by metadata criteria.
    """
    metadata_filter = {"type": "test"}
    limit = 10
    offset = 0

    mock_repository.filter_by_metadata.return_value = [sample_event_model]

    result = await event_service.filter_events_by_metadata(metadata_filter, limit, offset)

    assert result == [sample_event_model]
    mock_repository.filter_by_metadata.assert_called_once_with(metadata_filter, limit, offset)


# === search_events_by_embedding Tests ===


@pytest.mark.anyio
async def test_search_events_by_embedding(event_service, sample_event_model):
    """
    Test vector search by embedding.

    Verifies that search_vector is called correctly.
    """
    embedding = [0.3] * 768
    limit = 5

    # Configure mock repository (accessed via event_service.repo)
    event_service.repo.search_vector = AsyncMock(return_value=([sample_event_model], 1))

    result = await event_service.search_events_by_embedding(embedding, limit)

    assert result == [sample_event_model]
    event_service.repo.search_vector.assert_called_once_with(
        vector=embedding,
        limit=limit,
        offset=0
    )


# === Edge Cases & Integration ===


@pytest.mark.anyio
async def test_create_event_with_custom_source_fields(mock_repository, mock_embedding_service):
    """
    Test event creation with custom source fields configuration.
    """
    service = EventService(
        repository=mock_repository,
        embedding_service=mock_embedding_service,
        config={"embedding_source_fields": ["custom_text"]}
    )

    event_data = EventCreate(
        content={"custom_text": "Extract from custom field"},
        metadata={"type": "test"}
    )

    mock_event = EventModel(
        id=uuid4(),
        timestamp="2025-10-14T10:00:00Z",
        content=event_data.content,
        metadata=event_data.metadata,
        embedding=[0.1] * 768
    )
    mock_repository.add.return_value = mock_event

    await service.create_event(event_data)

    mock_embedding_service.generate_embedding.assert_called_once_with("Extract from custom field")


@pytest.mark.anyio
async def test_create_event_full_workflow(event_service, mock_repository, mock_embedding_service):
    """
    Test complete event creation workflow end-to-end.

    Verifies: text extraction → embedding generation → repository save.
    """
    event_data = EventCreate(
        content={"text": "Complete workflow test", "metadata_field": "extra"},
        metadata={"type": "integration_test", "user": "test_user"}
    )

    generated_embedding = [0.7] * 768
    mock_embedding_service.generate_embedding.return_value = generated_embedding

    created_event = EventModel(
        id=uuid4(),
        timestamp="2025-10-14T10:00:00Z",
        content=event_data.content,
        metadata=event_data.metadata,
        embedding=generated_embedding
    )
    mock_repository.add.return_value = created_event

    result = await event_service.create_event(event_data)

    # Verify full workflow
    assert result == created_event
    assert result.embedding == generated_embedding
    mock_embedding_service.generate_embedding.assert_called_once_with("Complete workflow test")
    mock_repository.add.assert_called_once()
    assert mock_repository.add.call_args[0][0].embedding == generated_embedding
