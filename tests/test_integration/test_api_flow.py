"""
API integration tests.

Testing complete flows through the API without mocks.
Real database, real services, real user scenarios.
"""

import pytest
import uuid
from datetime import datetime, timezone


@pytest.mark.integration
@pytest.mark.asyncio
class TestEventAPIFlow:
    """Test complete event flows through the API."""

    async def test_create_and_retrieve_event(self, test_client):
        """Test creating an event via API and retrieving it."""
        # Create event
        event_data = {
            "content": {
                "type": "note",
                "text": "API integration test note"
            },
            "metadata": {
                "source": "api_test",
                "test": True
            }
        }

        response = await test_client.post("/v1/events/", json=event_data)
        assert response.status_code == 201

        created = response.json()
        assert created["id"] is not None
        assert created["content"] == event_data["content"]

        # Retrieve it
        event_id = created["id"]
        response = await test_client.get(f"/v1/events/{event_id}")
        assert response.status_code == 200

        retrieved = response.json()
        assert retrieved["id"] == event_id
        assert retrieved["content"] == event_data["content"]

    async def test_update_event_metadata(self, test_client):
        """Test updating event metadata through API."""
        # Create event
        event_data = {
            "content": {"text": "Update test"},
            "metadata": {"version": 1}
        }

        create_response = await test_client.post("/v1/events/", json=event_data)
        event_id = create_response.json()["id"]

        # Update metadata
        update_data = {
            "version": 2,
            "updated": True,
            "updatedAt": datetime.now(timezone.utc).isoformat()
        }

        response = await test_client.patch(
            f"/v1/events/{event_id}/metadata",
            json=update_data
        )
        assert response.status_code == 200

        updated = response.json()
        assert updated["metadata"]["version"] == 2
        assert updated["metadata"]["updated"] is True

    async def test_delete_event(self, test_client):
        """Test deleting event through API."""
        # Create event
        response = await test_client.post("/v1/events/", json={
            "content": {"text": "To be deleted"}
        })
        event_id = response.json()["id"]

        # Delete it
        response = await test_client.delete(f"/v1/events/{event_id}")
        assert response.status_code == 204

        # Verify it's gone
        response = await test_client.get(f"/v1/events/{event_id}")
        assert response.status_code == 404

    async def test_search_events(self, test_client):
        """Test searching events through API."""
        # Create multiple events
        events = [
            {"content": {"text": "Python programming"}, "metadata": {"lang": "python"}},
            {"content": {"text": "JavaScript coding"}, "metadata": {"lang": "js"}},
            {"content": {"text": "Python testing"}, "metadata": {"lang": "python"}},
        ]

        for event_data in events:
            await test_client.post("/v1/events/", json=event_data)

        # Search by metadata
        response = await test_client.post("/v1/search/", json={
            "metadata": {"lang": "python"},
            "limit": 10
        })
        assert response.status_code == 200

        results = response.json()
        assert len(results["events"]) == 2
        assert results["total"] == 2

        for event in results["events"]:
            assert event["metadata"]["lang"] == "python"

    async def test_pagination(self, test_client):
        """Test pagination works correctly."""
        # Create 10 events
        for i in range(10):
            await test_client.post("/v1/events/", json={
                "content": {"text": f"Event {i}"},
                "metadata": {"index": i}
            })

        # Get first page
        response = await test_client.post("/v1/search/", json={
            "limit": 3,
            "offset": 0
        })
        page1 = response.json()
        assert len(page1["events"]) == 3
        assert page1["total"] == 10

        # Get second page
        response = await test_client.post("/v1/search/", json={
            "limit": 3,
            "offset": 3
        })
        page2 = response.json()
        assert len(page2["events"]) == 3

        # Pages should have different events
        page1_ids = {e["id"] for e in page1["events"]}
        page2_ids = {e["id"] for e in page2["events"]}
        assert page1_ids.isdisjoint(page2_ids)


@pytest.mark.integration
@pytest.mark.asyncio
class TestErrorHandling:
    """Test API error handling."""

    async def test_get_nonexistent_event(self, test_client):
        """Test 404 for non-existent event."""
        fake_id = str(uuid.uuid4())

        response = await test_client.get(f"/v1/events/{fake_id}")
        assert response.status_code == 404

        error = response.json()
        assert "detail" in error

    async def test_invalid_event_id(self, test_client):
        """Test 400 for invalid UUID."""
        response = await test_client.get("/v1/events/not-a-uuid")
        assert response.status_code == 422  # FastAPI validation error

    async def test_create_invalid_event(self, test_client):
        """Test validation for invalid event data."""
        # Missing required field
        response = await test_client.post("/v1/events/", json={})
        assert response.status_code == 422

        # Wrong type
        response = await test_client.post("/v1/events/", json={
            "content": "should be dict not string"
        })
        assert response.status_code == 422

    async def test_update_nonexistent_event(self, test_client):
        """Test updating non-existent event."""
        fake_id = str(uuid.uuid4())

        response = await test_client.patch(
            f"/v1/events/{fake_id}/metadata",
            json={"test": True}
        )
        assert response.status_code == 404

    async def test_search_with_invalid_params(self, test_client):
        """Test search with invalid parameters."""
        # Negative limit
        response = await test_client.post("/v1/search/", json={
            "limit": -1
        })
        assert response.status_code == 422

        # Limit too large
        response = await test_client.post("/v1/search/", json={
            "limit": 1001  # Assuming max is 1000
        })
        assert response.status_code == 422


@pytest.mark.integration
@pytest.mark.real_embeddings
@pytest.mark.asyncio
class TestEmbeddingIntegration:
    """Test embedding generation and search (requires real embeddings)."""

    async def test_auto_embedding_generation(self, test_client_with_real_embeddings):
        """Test that embeddings are auto-generated."""
        # Create event without explicit embedding
        response = await test_client_with_real_embeddings.post("/v1/events/", json={
            "content": {
                "text": "Machine learning is fascinating"
            }
        })
        assert response.status_code == 201

        event = response.json()

        # Get the event to check embedding
        response = await test_client_with_real_embeddings.get(f"/v1/events/{event['id']}")
        retrieved = response.json()

        # Should have generated embedding
        assert retrieved.get("embedding") is not None

    async def test_vector_search_similarity(self, test_client_with_real_embeddings):
        """Test that vector search returns semantically similar results."""
        # Create events with related content
        texts = [
            "Python is a programming language",
            "JavaScript is used for web development",
            "Machine learning uses Python",
            "Cooking pasta requires boiling water"  # Unrelated
        ]

        for text in texts:
            await test_client_with_real_embeddings.post("/v1/events/", json={
                "content": {"text": text}
            })

        # Search for "Python programming"
        response = await test_client_with_real_embeddings.post("/v1/search/", json={
            "query": "Python programming",
            "limit": 3
        })

        results = response.json()
        assert len(results["events"]) > 0

        # Top results should be Python-related
        top_result_texts = [e["content"]["text"] for e in results["events"][:2]]
        assert any("Python" in text for text in top_result_texts)

        # Pasta should not be in top results
        assert "pasta" not in " ".join(top_result_texts).lower()


@pytest.mark.integration
@pytest.mark.asyncio
class TestHealthAndMonitoring:
    """Test health and monitoring endpoints."""

    async def test_health_endpoint(self, test_client):
        """Test health check endpoint."""
        response = await test_client.get("/health")
        assert response.status_code == 200

        health = response.json()
        assert health["status"] == "healthy"
        assert "database" in health
        assert "timestamp" in health

    async def test_metrics_endpoint(self, test_client):
        """Test metrics endpoint (if implemented)."""
        response = await test_client.get("/performance/metrics")

        # Check if endpoint exists
        if response.status_code == 200:
            metrics = response.json()
            assert isinstance(metrics, dict)

    async def test_cache_stats(self, test_client):
        """Test cache statistics endpoint."""
        response = await test_client.get("/performance/cache/stats")

        if response.status_code == 200:
            stats = response.json()
            assert "query_cache" in stats or "embedding_cache" in stats


@pytest.mark.integration
@pytest.mark.asyncio
class TestConcurrentRequests:
    """Test handling concurrent requests."""

    async def test_concurrent_creates(self, test_client):
        """Test creating multiple events concurrently."""
        import asyncio

        async def create_event(index):
            response = await test_client.post("/v1/events/", json={
                "content": {"text": f"Concurrent event {index}"},
                "metadata": {"index": index}
            })
            return response.status_code == 201

        # Create 10 events concurrently
        tasks = [create_event(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        assert all(results)

    async def test_concurrent_reads(self, test_client):
        """Test reading events concurrently."""
        import asyncio

        # Create an event
        response = await test_client.post("/v1/events/", json={
            "content": {"text": "Concurrent read test"}
        })
        event_id = response.json()["id"]

        async def read_event():
            response = await test_client.get(f"/v1/events/{event_id}")
            return response.status_code == 200

        # Read 20 times concurrently
        tasks = [read_event() for _ in range(20)]
        results = await asyncio.gather(*tasks)

        assert all(results)

    async def test_concurrent_search(self, test_client):
        """Test searching concurrently."""
        import asyncio

        # Create some events first
        for i in range(5):
            await test_client.post("/v1/events/", json={
                "content": {"text": f"Search target {i}"}
            })

        async def search():
            response = await test_client.post("/v1/search/", json={
                "limit": 5
            })
            return response.status_code == 200

        # Search 10 times concurrently
        tasks = [search() for _ in range(10)]
        results = await asyncio.gather(*tasks)

        assert all(results)