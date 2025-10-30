"""
Tests for Event Routes (Core Routes).

Tests all CRUD operations and search endpoints for events.
"""

import pytest
from uuid import uuid4


# ============================================================================
# TEST: POST / (Create Event)
# ============================================================================

@pytest.mark.anyio
async def test_create_event_simple(test_client):
    """
    Test POST / creates a simple event.

    Validates event creation with minimal required fields.
    """
    event_data = {
        "content": {
            "type": "note",
            "text": "Test event creation"
        },
        "metadata": {
            "source": "test"
        }
    }

    response = await test_client.post("/v1/events/", json=event_data)

    assert response.status_code == 201
    result = response.json()

    assert "id" in result
    assert result["content"]["type"] == "note"
    assert result["content"]["text"] == "Test event creation"
    assert result["metadata"]["source"] == "test"


@pytest.mark.anyio
async def test_create_event_with_embedding(test_client):
    """
    Test POST / creates event with auto-generated embedding.

    Validates embedding generation (MockEmbeddingService returns 768D vectors).
    """
    event_data = {
        "content": {
            "type": "code",
            "text": "def hello(): return 'world'",
            "language": "python"
        },
        "metadata": {
            "source": "test",
            "file": "test.py"
        }
    }

    response = await test_client.post("/v1/events/", json=event_data)

    assert response.status_code == 201
    result = response.json()

    # MockEmbeddingService generates embeddings automatically
    assert "id" in result
    assert result["content"]["language"] == "python"


# ============================================================================
# TEST: GET /{event_id} (Get Event by ID)
# ============================================================================

@pytest.mark.anyio
async def test_get_event_success(test_client):
    """
    Test GET /{event_id} retrieves existing event.

    Validates successful event retrieval by ID.
    """
    # Create an event first
    create_response = await test_client.post("/v1/events/", json={
        "content": {"type": "note", "text": "Test get event"},
        "metadata": {"source": "test"}
    })
    event_id = create_response.json()["id"]

    # Retrieve it
    response = await test_client.get(f"/v1/events/{event_id}")

    assert response.status_code == 200
    result = response.json()

    assert result["id"] == event_id
    assert result["content"]["text"] == "Test get event"


@pytest.mark.anyio
async def test_get_event_not_found(test_client):
    """
    Test GET /{event_id} returns 404 for non-existent event.

    Validates error handling for missing events.
    """
    fake_uuid = str(uuid4())
    response = await test_client.get(f"/v1/events/{fake_uuid}")

    assert response.status_code == 404
    assert "non trouvé" in response.json()["detail"]


# ============================================================================
# TEST: PATCH /{event_id}/metadata (Update Event Metadata)
# ============================================================================

@pytest.mark.anyio
async def test_update_event_metadata_success(test_client):
    """
    Test PATCH /{event_id}/metadata updates metadata.

    Validates metadata merge (new keys added, existing preserved).
    """
    # Create event
    create_response = await test_client.post("/v1/events/", json={
        "content": {"type": "note", "text": "Test metadata update"},
        "metadata": {"source": "test", "priority": "low"}
    })
    event_id = create_response.json()["id"]

    # Update metadata
    new_metadata = {"priority": "high", "tags": ["important"]}
    response = await test_client.patch(
        f"/v1/events/{event_id}/metadata",
        json=new_metadata
    )

    assert response.status_code == 200
    result = response.json()

    # Metadata should be merged
    assert result["metadata"]["source"] == "test"  # Preserved
    assert result["metadata"]["priority"] == "high"  # Updated
    assert result["metadata"]["tags"] == ["important"]  # Added


@pytest.mark.anyio
async def test_update_event_metadata_not_found(test_client):
    """
    Test PATCH /{event_id}/metadata returns 404 for non-existent event.

    Validates error handling for missing events.
    """
    fake_uuid = str(uuid4())
    response = await test_client.patch(
        f"/v1/events/{fake_uuid}/metadata",
        json={"key": "value"}
    )

    assert response.status_code == 404
    assert "non trouvé" in response.json()["detail"]


# ============================================================================
# TEST: DELETE /{event_id} (Delete Event)
# ============================================================================

@pytest.mark.anyio
async def test_delete_event_success(test_client):
    """
    Test DELETE /{event_id} removes event.

    Validates successful deletion and subsequent 404 on retrieval.
    """
    # Create event
    create_response = await test_client.post("/v1/events/", json={
        "content": {"type": "note", "text": "Test delete"},
        "metadata": {"source": "test"}
    })
    event_id = create_response.json()["id"]

    # Delete event
    delete_response = await test_client.delete(f"/v1/events/{event_id}")
    assert delete_response.status_code == 204

    # Verify deletion
    get_response = await test_client.get(f"/api/events/{event_id}")
    assert get_response.status_code == 404


@pytest.mark.anyio
async def test_delete_event_not_found(test_client):
    """
    Test DELETE /{event_id} returns 404 for non-existent event.

    Validates error handling for missing events.
    """
    fake_uuid = str(uuid4())
    response = await test_client.delete(f"/v1/events/{fake_uuid}")

    assert response.status_code == 404
    assert "non trouvé" in response.json()["detail"]


# ============================================================================
# TEST: POST /filter/metadata (Filter Events by Metadata)
# ============================================================================

@pytest.mark.anyio
async def test_filter_events_by_metadata_empty(test_client):
    """
    Test POST /filter/metadata returns empty list when no matches.

    Validates filtering logic with non-matching criteria.
    """
    response = await test_client.post(
        "/v1/events/filter/metadata",
        json={"source": "nonexistent"}
    )

    assert response.status_code == 200
    result = response.json()

    assert isinstance(result, list)
    assert len(result) == 0


@pytest.mark.anyio
async def test_filter_events_by_metadata_with_results(test_client):
    """
    Test POST /filter/metadata returns matching events.

    Validates metadata filtering with multiple matching events.
    """
    # Create events with different metadata
    await test_client.post("/v1/events/", json={
        "content": {"type": "note", "text": "Event 1"},
        "metadata": {"source": "test-filter", "priority": "high"}
    })
    await test_client.post("/v1/events/", json={
        "content": {"type": "note", "text": "Event 2"},
        "metadata": {"source": "test-filter", "priority": "low"}
    })
    await test_client.post("/v1/events/", json={
        "content": {"type": "note", "text": "Event 3"},
        "metadata": {"source": "other"}
    })

    # Filter by source="test-filter"
    response = await test_client.post(
        "/v1/events/filter/metadata",
        json={"source": "test-filter"}
    )

    assert response.status_code == 200
    result = response.json()

    assert len(result) == 2
    for event in result:
        assert event["metadata"]["source"] == "test-filter"


@pytest.mark.anyio
async def test_filter_events_pagination(test_client):
    """
    Test POST /filter/metadata respects limit and offset.

    Validates pagination parameters.
    """
    # Create 5 events
    for i in range(5):
        await test_client.post("/v1/events/", json={
            "content": {"type": "note", "text": f"Event {i}"},
            "metadata": {"source": "pagination-test"}
        })

    # Get first 2
    response = await test_client.post(
        "/v1/events/filter/metadata?limit=2&offset=0",
        json={"source": "pagination-test"}
    )

    assert response.status_code == 200
    result = response.json()

    assert len(result) == 2


# ============================================================================
# TEST: POST /search/embedding (Search Events by Embedding)
# ============================================================================

@pytest.mark.anyio
async def test_search_events_by_embedding_empty(test_client):
    """
    Test POST /search/embedding returns empty list when no events.

    Validates embedding search with empty database.
    """
    # Generate a random embedding (768 dimensions for mock)
    embedding = [0.1] * 768

    response = await test_client.post(
        "/v1/events/search/embedding",
        json=embedding
    )

    assert response.status_code == 200
    result = response.json()

    assert isinstance(result, list)
    # May be empty or contain events depending on DB state


@pytest.mark.anyio
async def test_search_events_by_embedding_with_results(test_client):
    """
    Test POST /search/embedding returns similar events.

    Validates vector similarity search.
    """
    # Create events (embeddings auto-generated by MockEmbeddingService)
    await test_client.post("/v1/events/", json={
        "content": {"type": "note", "text": "Machine learning in Python"},
        "metadata": {"source": "test"}
    })
    await test_client.post("/v1/events/", json={
        "content": {"type": "note", "text": "Deep learning tutorial"},
        "metadata": {"source": "test"}
    })

    # Search with a random embedding
    embedding = [0.5] * 768

    response = await test_client.post(
        "/v1/events/search/embedding?limit=5",
        json=embedding
    )

    assert response.status_code == 200
    result = response.json()

    assert isinstance(result, list)
    # Should return results (cosine similarity with mock embeddings)


@pytest.mark.anyio
async def test_search_events_limit_parameter(test_client):
    """
    Test POST /search/embedding respects limit parameter.

    Validates result count limit.
    """
    # Create 10 events
    for i in range(10):
        await test_client.post("/v1/events/", json={
            "content": {"type": "note", "text": f"Event {i}"},
            "metadata": {"source": "test"}
        })

    # Search with limit=3
    embedding = [0.2] * 768

    response = await test_client.post(
        "/v1/events/search/embedding?limit=3",
        json=embedding
    )

    assert response.status_code == 200
    result = response.json()

    assert len(result) <= 3


# ============================================================================
# TEST: GET /cache/stats (Cache Statistics - Optional)
# ============================================================================

@pytest.mark.anyio
async def test_get_cache_stats(test_client):
    """
    Test GET /cache/stats returns cache statistics.

    Validates cache stats endpoint (if cache module available).
    """
    response = await test_client.get("/v1/events/cache/stats")

    # Cache module may not be available (ImportError)
    if response.status_code == 200:
        result = response.json()
        assert isinstance(result, dict)
    elif response.status_code == 404:
        # Cache module not found - acceptable
        pass
    else:
        pytest.fail(f"Unexpected status code: {response.status_code}")
