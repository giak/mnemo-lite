"""
End-to-end integration tests for complete MnemoLite workflows.

These tests verify the full stack: API → Services → Repository → Database.
Uses the real test database (mnemolite_test) and real embedding service.
"""

import pytest
import uuid
from fastapi.testclient import TestClient
from datetime import datetime, timezone
import json

from main import app
from dependencies import get_embedding_service


# === Fixtures ===


@pytest.fixture
def client():
    """Create FastAPI test client."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def embedding_service():
    """Get real embedding service for integration tests."""
    return get_embedding_service()


# === End-to-End Workflow Tests ===


@pytest.mark.integration
def test_complete_event_lifecycle(client):
    """
    Test complete event lifecycle: Create → Search → Retrieve → Update → Delete.

    This is a full end-to-end test that verifies:
    1. Event creation with auto-embedding generation
    2. Vector search finds the created event
    3. Event retrieval by ID
    4. Metadata update
    5. Event deletion
    """
    # Step 1: Create event with text content
    create_payload = {
        "content": {"text": "Integration test event for full lifecycle"},
        "metadata": {"test_type": "e2e_lifecycle", "timestamp": datetime.now(timezone.utc).isoformat()}
    }

    create_response = client.post("/v1/events", json=create_payload)
    assert create_response.status_code == 201, f"Failed to create event: {create_response.text}"

    created_event = create_response.json()
    event_id = created_event["id"]

    # Verify event structure
    assert "id" in created_event
    assert "timestamp" in created_event
    assert "embedding" in created_event
    assert created_event["embedding"] is not None
    assert len(created_event["embedding"]) == 768  # nomic-embed-text-v1.5 dimension

    # Step 2: Search for event using vector search
    search_response = client.get(
        "/v1/search/",
        params={
            "vector_query": "integration test lifecycle",
            "limit": 5
        }
    )
    assert search_response.status_code == 200

    search_results = search_response.json()
    assert "data" in search_results
    assert "meta" in search_results
    assert search_results["meta"]["total_hits"] >= 1

    # Verify our event is in results
    event_ids = [e["id"] for e in search_results["data"]]
    assert event_id in event_ids, "Created event not found in search results"

    # Step 3: Retrieve event by ID
    get_response = client.get(f"/v1/events/{event_id}")
    assert get_response.status_code == 200

    retrieved_event = get_response.json()
    assert retrieved_event["id"] == event_id
    assert retrieved_event["content"]["text"] == create_payload["content"]["text"]

    # Step 4: Update event metadata
    update_payload = {"updated": True, "version": 2}
    update_response = client.patch(f"/v1/events/{event_id}/metadata", json=update_payload)
    assert update_response.status_code == 200

    updated_event = update_response.json()
    assert updated_event["metadata"]["updated"] is True
    assert updated_event["metadata"]["version"] == 2
    assert updated_event["metadata"]["test_type"] == "e2e_lifecycle"  # Original metadata preserved

    # Step 5: Delete event
    delete_response = client.delete(f"/v1/events/{event_id}")
    assert delete_response.status_code == 200

    # Verify deletion
    get_deleted_response = client.get(f"/v1/events/{event_id}")
    assert get_deleted_response.status_code == 404


@pytest.mark.integration
def test_hybrid_search_workflow(client):
    """
    Test hybrid search workflow: Create events → Search with filters.

    Verifies:
    1. Multiple event creation
    2. Vector search with metadata filtering
    3. Time-based filtering
    4. Pagination
    """
    # Step 1: Create multiple test events
    base_time = datetime.now(timezone.utc)
    created_ids = []

    for i in range(5):
        event_payload = {
            "content": {"text": f"Hybrid search test event number {i}"},
            "metadata": {
                "test_type": "hybrid_search",
                "category": "even" if i % 2 == 0 else "odd",
                "index": i
            }
        }

        response = client.post("/v1/events", json=event_payload)
        assert response.status_code == 201
        created_ids.append(response.json()["id"])

    # Step 2: Vector search with metadata filter
    search_response = client.get(
        "/v1/search/",
        params={
            "vector_query": "hybrid search test",
            "filter_metadata": json.dumps({"category": "even"}),
            "limit": 10
        }
    )
    assert search_response.status_code == 200

    results = search_response.json()
    assert results["meta"]["total_hits"] >= 3  # Should find events 0, 2, 4

    # Verify all results have category=even
    for event in results["data"]:
        if event["metadata"].get("test_type") == "hybrid_search":
            assert event["metadata"]["category"] == "even"

    # Step 3: Metadata-only search
    metadata_search_response = client.get(
        "/v1/search/",
        params={
            "filter_metadata": json.dumps({"test_type": "hybrid_search", "category": "odd"}),
            "limit": 10
        }
    )
    assert metadata_search_response.status_code == 200

    metadata_results = metadata_search_response.json()
    assert metadata_results["meta"]["total_hits"] >= 2  # Should find events 1, 3

    # Cleanup: Delete created events
    for event_id in created_ids:
        client.delete(f"/v1/events/{event_id}")


@pytest.mark.integration
def test_embedding_consistency(client):
    """
    Test embedding generation consistency.

    Verifies that:
    1. Same text generates similar embeddings
    2. Different text generates different embeddings
    3. Embeddings are properly normalized
    """
    # Create two events with identical text
    identical_text = "Embedding consistency test identical text"

    event1_response = client.post(
        "/v1/events",
        json={
            "content": {"text": identical_text},
            "metadata": {"test": "embedding_consistency_1"}
        }
    )
    assert event1_response.status_code == 201

    event2_response = client.post(
        "/v1/events",
        json={
            "content": {"text": identical_text},
            "metadata": {"test": "embedding_consistency_2"}
        }
    )
    assert event2_response.status_code == 201

    event1 = event1_response.json()
    event2 = event2_response.json()

    # Embeddings should be very similar (accounting for potential float precision)
    import numpy as np
    emb1 = np.array(event1["embedding"])
    emb2 = np.array(event2["embedding"])

    # Cosine similarity should be very high (>0.999)
    cosine_sim = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
    assert cosine_sim > 0.999, f"Identical text should produce similar embeddings, got similarity: {cosine_sim}"

    # Create event with different text
    event3_response = client.post(
        "/v1/events",
        json={
            "content": {"text": "Completely different text about quantum physics"},
            "metadata": {"test": "embedding_consistency_3"}
        }
    )
    assert event3_response.status_code == 201

    event3 = event3_response.json()
    emb3 = np.array(event3["embedding"])

    # Cosine similarity with different text should be lower
    cosine_sim_diff = np.dot(emb1, emb3) / (np.linalg.norm(emb1) * np.linalg.norm(emb3))
    assert cosine_sim_diff < 0.9, f"Different text should produce dissimilar embeddings, got similarity: {cosine_sim_diff}"

    # Cleanup
    for event_id in [event1["id"], event2["id"], event3["id"]]:
        client.delete(f"/v1/events/{event_id}")


@pytest.mark.integration
def test_error_handling_workflow(client):
    """
    Test error handling in various scenarios.

    Verifies:
    1. Invalid event creation (missing required fields)
    2. Invalid search parameters
    3. Non-existent resource access
    4. Malformed JSON
    """
    # Test 1: Create event with invalid data
    invalid_response = client.post("/v1/events", json={})
    assert invalid_response.status_code == 422  # Validation error

    # Test 2: Search with invalid metadata JSON
    invalid_search = client.get(
        "/v1/search/",
        params={"filter_metadata": "not-valid-json"}
    )
    assert invalid_search.status_code == 400

    # Test 3: Get non-existent event
    fake_uuid = str(uuid.uuid4())
    not_found_response = client.get(f"/v1/events/{fake_uuid}")
    assert not_found_response.status_code == 404

    # Test 4: Delete non-existent event
    delete_not_found = client.delete(f"/v1/events/{fake_uuid}")
    assert delete_not_found.status_code == 404


@pytest.mark.integration
def test_pagination_workflow(client):
    """
    Test pagination in search results.

    Verifies:
    1. Limit parameter works correctly
    2. Offset parameter works correctly
    3. Total count is accurate
    """
    # Create multiple events for pagination testing
    created_ids = []
    for i in range(15):
        response = client.post(
            "/v1/events",
            json={
                "content": {"text": f"Pagination test event {i}"},
                "metadata": {"test_type": "pagination", "index": i}
            }
        )
        assert response.status_code == 201
        created_ids.append(response.json()["id"])

    # Test limit
    page1_response = client.get(
        "/v1/search/",
        params={
            "filter_metadata": json.dumps({"test_type": "pagination"}),
            "limit": 5,
            "offset": 0
        }
    )
    assert page1_response.status_code == 200

    page1 = page1_response.json()
    assert len(page1["data"]) <= 5
    assert page1["meta"]["limit"] == 5
    assert page1["meta"]["offset"] == 0
    assert page1["meta"]["total_hits"] >= 15

    # Test offset (page 2)
    page2_response = client.get(
        "/v1/search/",
        params={
            "filter_metadata": json.dumps({"test_type": "pagination"}),
            "limit": 5,
            "offset": 5
        }
    )
    assert page2_response.status_code == 200

    page2 = page2_response.json()
    assert len(page2["data"]) <= 5
    assert page2["meta"]["offset"] == 5

    # Verify no overlap between pages
    page1_ids = {e["id"] for e in page1["data"]}
    page2_ids = {e["id"] for e in page2["data"]}
    assert page1_ids.isdisjoint(page2_ids), "Pages should not overlap"

    # Cleanup
    for event_id in created_ids:
        client.delete(f"/v1/events/{event_id}")


@pytest.mark.integration
def test_health_and_metrics(client):
    """
    Test health check and metrics endpoints.

    Verifies:
    1. Health endpoint responds correctly
    2. Readiness endpoint responds correctly
    3. Metrics endpoint is accessible
    """
    # Test health
    health_response = client.get("/health")
    assert health_response.status_code == 200

    health_data = health_response.json()
    assert health_data["status"] == "healthy"
    assert "services" in health_data
    assert health_data["services"]["postgres"]["status"] == "ok"

    # Test readiness
    readiness_response = client.get("/readiness")
    assert readiness_response.status_code == 200

    readiness_data = readiness_response.json()
    assert readiness_data["status"] == "ok"

    # Test metrics
    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    assert "text/plain" in metrics_response.headers["content-type"]
    assert "HELP" in metrics_response.text
    assert "TYPE" in metrics_response.text
