"""
Vector search tests.

Testing the core functionality: semantic search with embeddings.
"""

import pytest
import numpy as np
from datetime import datetime, timedelta, timezone


@pytest.mark.asyncio
class TestVectorSearch:
    """Test vector-based semantic search."""

    async def test_vector_search_basic(self, event_repo):
        """Test basic vector search functionality."""
        from models.event_models import EventCreate

        # Create events with similar embeddings
        base_vector = [0.5] * 768

        # Very similar vector (small perturbation)
        similar_vector = base_vector.copy()
        similar_vector[0] = 0.51

        # Less similar vector (larger perturbation)
        different_vector = base_vector.copy()
        for i in range(100):
            different_vector[i] = 0.8

        # Create events
        event1 = await event_repo.add(EventCreate(
            content={"text": "Base event"},
            embedding=base_vector
        ))

        event2 = await event_repo.add(EventCreate(
            content={"text": "Similar event"},
            embedding=similar_vector
        ))

        event3 = await event_repo.add(EventCreate(
            content={"text": "Different event"},
            embedding=different_vector
        ))

        # Search with query vector (same as base)
        results, total = await event_repo.search_vector(
            vector=base_vector,
            limit=10
        )

        # Should find all 3, ordered by similarity
        assert len(results) == 3
        assert total == 3

        # First result should be exact match
        assert results[0].id == event1.id

        # Second should be similar
        assert results[1].id == event2.id

        # Third should be different
        assert results[2].id == event3.id

    async def test_vector_search_with_limit(self, event_repo):
        """Test vector search respects limit."""
        from models.event_models import EventCreate

        # Create 10 events with random embeddings
        import random
        for i in range(10):
            vector = [random.random() for _ in range(768)]
            await event_repo.add(EventCreate(
                content={"text": f"Event {i}"},
                embedding=vector
            ))

        # Search with limit
        query_vector = [0.5] * 768
        results, total = await event_repo.search_vector(
            vector=query_vector,
            limit=3
        )

        # Should return exactly 3
        assert len(results) == 3
        # But total should be 10
        assert total == 10

    async def test_vector_search_without_vector(self, event_repo, sample_events):
        """Test search without vector (just returns latest events)."""
        from models.event_models import EventCreate

        # Create events without embeddings
        for event_data in sample_events[:3]:
            await event_repo.add(EventCreate(**event_data))

        # Search without vector
        results, total = await event_repo.search_vector(
            vector=None,
            limit=10
        )

        # Should return all events, ordered by timestamp
        assert len(results) == 3
        assert total == 3

        # Check ordered by timestamp DESC
        for i in range(len(results) - 1):
            assert results[i].timestamp >= results[i + 1].timestamp

    async def test_vector_search_with_distance_threshold(self, event_repo):
        """Test vector search with distance threshold."""
        from models.event_models import EventCreate

        # Create events with varying distances
        base_vector = [0.5] * 768

        # Very close (L2 distance ~0.1)
        close_vector = base_vector.copy()
        close_vector[0] = 0.55

        # Far (L2 distance ~3.16)
        far_vector = [0.6] * 768

        await event_repo.add(EventCreate(
            content={"text": "Base"},
            embedding=base_vector
        ))

        await event_repo.add(EventCreate(
            content={"text": "Close"},
            embedding=close_vector
        ))

        await event_repo.add(EventCreate(
            content={"text": "Far"},
            embedding=far_vector
        ))

        # Search with strict threshold
        results, total = await event_repo.search_vector(
            vector=base_vector,
            distance_threshold=0.5,  # Only very close matches
            limit=10
        )

        # Should only find base and close
        assert len(results) <= 2

        # Search with loose threshold
        results, total = await event_repo.search_vector(
            vector=base_vector,
            distance_threshold=5.0,  # Very loose
            limit=10
        )

        # Should find all
        assert len(results) == 3


@pytest.mark.asyncio
class TestHybridSearch:
    """Test combined vector + metadata + time search."""

    async def test_vector_with_metadata_filter(self, event_repo):
        """Test combining vector search with metadata filters."""
        from models.event_models import EventCreate

        base_vector = [0.5] * 768

        # Create events with different metadata
        await event_repo.add(EventCreate(
            content={"text": "High priority task"},
            metadata={"priority": "high", "type": "task"},
            embedding=base_vector
        ))

        await event_repo.add(EventCreate(
            content={"text": "Low priority task"},
            metadata={"priority": "low", "type": "task"},
            embedding=base_vector
        ))

        await event_repo.add(EventCreate(
            content={"text": "High priority note"},
            metadata={"priority": "high", "type": "note"},
            embedding=base_vector
        ))

        # Search for high priority only
        results, total = await event_repo.search_vector(
            vector=base_vector,
            metadata={"priority": "high"},
            limit=10
        )

        assert len(results) == 2
        for result in results:
            assert result.metadata["priority"] == "high"

    async def test_vector_with_time_range(self, event_repo):
        """Test combining vector search with time filters."""
        from models.event_models import EventCreate

        base_vector = [0.5] * 768
        now = datetime.now(timezone.utc)

        # Create events at different times
        await event_repo.add(EventCreate(
            content={"text": "Yesterday"},
            embedding=base_vector,
            timestamp=now - timedelta(days=1)
        ))

        today_event = await event_repo.add(EventCreate(
            content={"text": "Today"},
            embedding=base_vector,
            timestamp=now
        ))

        await event_repo.add(EventCreate(
            content={"text": "Tomorrow"},
            embedding=base_vector,
            timestamp=now + timedelta(days=1)
        ))

        # Search for today only
        results, total = await event_repo.search_vector(
            vector=base_vector,
            ts_start=now - timedelta(hours=1),
            ts_end=now + timedelta(hours=1),
            limit=10
        )

        assert len(results) == 1
        assert results[0].id == today_event.id

    async def test_complex_hybrid_search(self, event_repo):
        """Test complex search combining all filters."""
        from models.event_models import EventCreate

        base_vector = [0.5] * 768
        now = datetime.now(timezone.utc)

        # Create diverse events
        for i in range(10):
            await event_repo.add(EventCreate(
                content={"text": f"Event {i}"},
                metadata={
                    "index": i,
                    "type": "task" if i % 2 == 0 else "note",
                    "priority": "high" if i % 3 == 0 else "low"
                },
                embedding=[0.5 + i * 0.01] * 768,  # Slightly different vectors
                timestamp=now - timedelta(hours=i)
            ))

        # Complex search: high priority tasks from last 5 hours
        results, total = await event_repo.search_vector(
            vector=base_vector,
            metadata={"priority": "high"},
            ts_start=now - timedelta(hours=5),
            limit=10
        )

        # Should find events 0 and 3 (high priority, recent)
        assert len(results) >= 1
        for result in results:
            assert result.metadata["priority"] == "high"
            assert result.timestamp >= now - timedelta(hours=5)


@pytest.mark.asyncio
class TestSearchFallback:
    """Test fallback behavior when search returns no results."""

    async def test_fallback_on_empty_results(self, event_repo):
        """Test fallback when strict threshold returns nothing."""
        from models.event_models import EventCreate

        # Create event with specific embedding
        base_vector = [0.5] * 768
        await event_repo.add(EventCreate(
            content={"text": "Only event"},
            embedding=base_vector
        ))

        # Search with very different vector and strict threshold
        query_vector = [0.9] * 768

        # With fallback (default)
        results, total = await event_repo.search_vector(
            vector=query_vector,
            distance_threshold=0.1,  # Too strict
            limit=10,
            enable_fallback=True
        )

        # Should fallback and return result
        assert len(results) == 1

        # Without fallback
        results, total = await event_repo.search_vector(
            vector=query_vector,
            distance_threshold=0.1,  # Too strict
            limit=10,
            enable_fallback=False
        )

        # Should return empty
        assert len(results) == 0

    async def test_no_fallback_with_metadata_filters(self, event_repo):
        """Test that fallback doesn't apply with metadata filters."""
        from models.event_models import EventCreate

        base_vector = [0.5] * 768

        await event_repo.add(EventCreate(
            content={"text": "Event"},
            metadata={"type": "note"},
            embedding=base_vector
        ))

        # Search with metadata filter and strict threshold
        query_vector = [0.9] * 768

        results, total = await event_repo.search_vector(
            vector=query_vector,
            metadata={"type": "task"},  # Wrong type
            distance_threshold=0.1,
            limit=10,
            enable_fallback=True
        )

        # Should NOT fallback (metadata filter present)
        assert len(results) == 0


@pytest.mark.performance
@pytest.mark.asyncio
class TestSearchPerformance:
    """Test search performance with realistic data."""

    async def test_search_performance_100_events(self, event_repo, timer):
        """Test search is fast with 100 events."""
        from models.event_models import EventCreate
        import random

        # Create 100 events
        for i in range(100):
            vector = [random.random() for _ in range(768)]
            await event_repo.add(EventCreate(
                content={"text": f"Event {i}", "index": i},
                metadata={"batch": "perf_test"},
                embedding=vector
            ))

        # Time the search
        query_vector = [0.5] * 768

        with timer.measure("search"):
            results, total = await event_repo.search_vector(
                vector=query_vector,
                limit=10
            )

        # Should complete quickly
        assert timer.elapsed("search") < 0.1  # 100ms
        assert len(results) == 10
        assert total == 100

    @pytest.mark.slow
    async def test_search_performance_1000_events(self, event_repo, timer):
        """Test search is still fast with 1000 events."""
        from models.event_models import EventCreate
        import random

        # Create 1000 events (this will be slow)
        for i in range(1000):
            if i % 100 == 0:
                print(f"Created {i}/1000 events...")

            vector = [random.random() for _ in range(768)]
            await event_repo.add(EventCreate(
                content={"text": f"Event {i}"},
                metadata={"batch": "large_perf_test"},
                embedding=vector
            ))

        # Time the search
        query_vector = [0.5] * 768

        with timer.measure("search_1000"):
            results, total = await event_repo.search_vector(
                vector=query_vector,
                limit=10
            )

        # Should still be fast
        assert timer.elapsed("search_1000") < 0.2  # 200ms
        assert len(results) == 10
        assert total == 1000