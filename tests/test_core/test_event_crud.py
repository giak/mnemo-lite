"""
Core CRUD tests for events.

Pragmatic tests focusing on what users actually do.
No mocks, real database, fast feedback.
"""

import pytest
import uuid
from datetime import datetime, timezone


@pytest.mark.asyncio
class TestEventCRUD:
    """Test basic CRUD operations on events."""

    async def test_create_event(self, event_repo, sample_events):
        """Test creating an event - the most basic operation."""
        # Arrange
        event_data = sample_events[0]  # Note event

        # Act
        from models.event_models import EventCreate
        event_create = EventCreate(**event_data)
        event = await event_repo.add(event_create)

        # Assert
        assert event.id is not None
        assert event.content == event_data["content"]
        assert event.metadata == event_data["metadata"]
        assert event.timestamp is not None

    async def test_get_event_by_id(self, event_repo, sample_events):
        """Test retrieving an event by ID."""
        # Create an event
        from models.event_models import EventCreate
        event_create = EventCreate(**sample_events[0])
        created = await event_repo.add(event_create)

        # Get it back
        retrieved = await event_repo.get_by_id(created.id)

        # Should be identical
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.content == created.content
        assert retrieved.metadata == created.metadata

    async def test_get_nonexistent_event(self, event_repo):
        """Test getting an event that doesn't exist."""
        fake_id = uuid.uuid4()

        result = await event_repo.get_by_id(fake_id)

        assert result is None

    async def test_update_metadata(self, event_repo, sample_events):
        """Test updating event metadata (merge operation)."""
        # Create event
        from models.event_models import EventCreate
        event_create = EventCreate(**sample_events[0])
        event = await event_repo.add(event_create)

        # Update metadata
        metadata_update = {
            "status": "reviewed",
            "reviewer": "alice",
            "priority": "low"  # This should override existing "high"
        }
        updated = await event_repo.update_metadata(
            event.id,
            metadata_update
        )

        # Check merge worked
        assert updated is not None
        assert updated.metadata["status"] == "reviewed"
        assert updated.metadata["reviewer"] == "alice"
        assert updated.metadata["priority"] == "low"  # Override
        assert updated.metadata["source"] == "test"  # Original preserved

    async def test_delete_event(self, event_repo, sample_events):
        """Test deleting an event."""
        # Create event
        from models.event_models import EventCreate
        event_create = EventCreate(**sample_events[0])
        event = await event_repo.add(event_create)

        # Delete it
        deleted = await event_repo.delete(event.id)
        assert deleted is True

        # Verify it's gone
        retrieved = await event_repo.get_by_id(event.id)
        assert retrieved is None

    async def test_delete_nonexistent_event(self, event_repo):
        """Test deleting an event that doesn't exist."""
        fake_id = uuid.uuid4()

        deleted = await event_repo.delete(fake_id)

        assert deleted is False

    async def test_complete_crud_cycle(self, event_repo):
        """Test complete CRUD cycle - what users actually do."""
        # Create
        from models.event_models import EventCreate
        event_create = EventCreate(
            content={"type": "task", "text": "Complete CRUD test"},
            metadata={"status": "pending"}
        )
        event = await event_repo.add(event_create)
        event_id = event.id

        # Read
        retrieved = await event_repo.get_by_id(event_id)
        assert retrieved is not None
        assert retrieved.metadata["status"] == "pending"

        # Update
        updated = await event_repo.update_metadata(
            event_id,
            {"status": "in_progress", "started_at": datetime.now(timezone.utc).isoformat()}
        )
        assert updated.metadata["status"] == "in_progress"
        assert "started_at" in updated.metadata

        # Update again
        completed = await event_repo.update_metadata(
            event_id,
            {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()}
        )
        assert completed.metadata["status"] == "completed"

        # Delete
        deleted = await event_repo.delete(event_id)
        assert deleted is True

        # Verify gone
        gone = await event_repo.get_by_id(event_id)
        assert gone is None


@pytest.mark.asyncio
class TestEventFiltering:
    """Test filtering and searching events."""

    async def test_filter_by_metadata(self, event_repo, sample_events):
        """Test filtering events by metadata."""
        # Create multiple events
        from models.event_models import EventCreate

        for event_data in sample_events:
            await event_repo.add(EventCreate(**event_data))

        # Filter by source=test
        results = await event_repo.filter_by_metadata(
            {"source": "test"},
            limit=10
        )

        assert len(results) == 5  # All have source=test

        # Filter by priority=high
        high_priority = await event_repo.filter_by_metadata(
            {"priority": "high"},
            limit=10
        )

        assert len(high_priority) == 1
        assert high_priority[0].metadata["priority"] == "high"

    async def test_filter_with_pagination(self, event_repo, sample_events):
        """Test pagination works correctly."""
        # Create events
        from models.event_models import EventCreate

        created_ids = []
        for event_data in sample_events:
            event = await event_repo.add(EventCreate(**event_data))
            created_ids.append(event.id)

        # Get first page
        page1 = await event_repo.filter_by_metadata(
            {"source": "test"},
            limit=2,
            offset=0
        )
        assert len(page1) == 2

        # Get second page
        page2 = await event_repo.filter_by_metadata(
            {"source": "test"},
            limit=2,
            offset=2
        )
        assert len(page2) == 2

        # Pages should have different events
        page1_ids = [e.id for e in page1]
        page2_ids = [e.id for e in page2]
        assert set(page1_ids).isdisjoint(set(page2_ids))

    async def test_filter_no_results(self, event_repo, sample_events):
        """Test filtering with no matches."""
        # Create events
        from models.event_models import EventCreate

        for event_data in sample_events:
            await event_repo.add(EventCreate(**event_data))

        # Filter by non-existent value
        results = await event_repo.filter_by_metadata(
            {"source": "nonexistent"},
            limit=10
        )

        assert len(results) == 0


@pytest.mark.asyncio
class TestEventWithEmbeddings:
    """Test events with embedding vectors."""

    async def test_create_event_with_embedding(self, event_repo, random_vector):
        """Test creating an event with an embedding."""
        from models.event_models import EventCreate

        event_create = EventCreate(
            content={"text": "Event with embedding"},
            embedding=random_vector
        )

        event = await event_repo.add(event_create)

        assert event.embedding is not None
        assert len(event.embedding) == 768

    async def test_create_event_without_embedding(self, event_repo):
        """Test creating an event without embedding (None)."""
        from models.event_models import EventCreate

        event_create = EventCreate(
            content={"text": "Event without embedding"},
            embedding=None
        )

        event = await event_repo.add(event_create)

        assert event.id is not None
        assert event.embedding is None

    async def test_update_doesnt_lose_embedding(self, event_repo, random_vector):
        """Test that updating metadata doesn't lose the embedding."""
        from models.event_models import EventCreate

        # Create with embedding
        event_create = EventCreate(
            content={"text": "Test"},
            embedding=random_vector
        )
        event = await event_repo.add(event_create)

        # Update metadata
        updated = await event_repo.update_metadata(
            event.id,
            {"updated": True}
        )

        # Embedding should still be there
        assert updated.embedding is not None
        assert len(updated.embedding) == 768