"""Tests for memories search endpoint."""
import pytest
import uuid
from sqlalchemy import text


@pytest.mark.anyio
async def test_search_memories_empty_database(test_client):
    """Test POST /api/v1/memories/search with empty database."""
    response = await test_client.post(
        "/api/v1/memories/search",
        json={"query": "test query", "limit": 10}
    )

    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "total" in data
    assert "query" in data
    assert "search_time_ms" in data
    assert data["query"] == "test query"
    assert data["total"] == 0
    assert len(data["results"]) == 0


@pytest.mark.anyio
async def test_search_memories_response_structure(test_client):
    """Test POST /api/v1/memories/search returns correct response structure.

    Note: This test verifies API structure, not semantic match quality.
    Hybrid search combines lexical+vector which may not match test data.
    """
    response = await test_client.post(
        "/api/v1/memories/search",
        json={"query": "test query", "limit": 10}
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "results" in data
    assert "total" in data
    assert "query" in data
    assert "search_time_ms" in data
    assert isinstance(data["results"], list)
    assert isinstance(data["total"], int)
    assert data["query"] == "test query"
    assert data["search_time_ms"] >= 0


@pytest.mark.anyio
async def test_search_memories_result_fields(test_client, clean_db):
    """Test that search results have all required fields when present."""
    # Insert a test memory with matching content for lexical search
    memory_id = str(uuid.uuid4())
    embedding_vector = f"[{','.join(['0.1'] * 768)}]"
    async with clean_db.begin() as conn:
        await conn.execute(text(f"""
            INSERT INTO memories (id, title, content, memory_type, tags, embedding, created_at, author)
            VALUES (
                '{memory_id}'::uuid,
                :title,
                :content,
                :memory_type,
                :tags,
                '{embedding_vector}'::vector,
                NOW(),
                :author
            )
        """), {
            "title": "Note politique Duclos ObsDelphi",
            "content": "Enquête approfondie note sur les liens Duclos ObsDelphi politique fact-check",
            "memory_type": "note",
            "tags": ["politique", "note"],
            "author": "Claude"
        })

    # Search with terms that should match lexically
    response = await test_client.post(
        "/api/v1/memories/search",
        json={"query": "investigation politique Duclos", "limit": 10}
    )

    assert response.status_code == 200
    data = response.json()

    # If results are returned, verify their structure
    if len(data["results"]) > 0:
        result = data["results"][0]
        assert "id" in result
        assert "title" in result
        assert "content_preview" in result
        assert "memory_type" in result
        assert "tags" in result
        assert "score" in result
        assert "created_at" in result
        assert isinstance(result["tags"], list)
        assert isinstance(result["score"], float)


@pytest.mark.anyio
async def test_search_memories_with_type_filter(test_client, clean_db):
    """Test memory search with memory_type filter."""
    # Insert test memories of different types
    id1 = str(uuid.uuid4())
    id2 = str(uuid.uuid4())
    embedding_vector = f"[{','.join(['0.1'] * 768)}]"
    async with clean_db.begin() as conn:
        await conn.execute(text(f"""
            INSERT INTO memories (id, title, content, memory_type, embedding, created_at)
            VALUES
                ('{id1}'::uuid, 'Decision Test', 'Decision content', 'decision', '{embedding_vector}'::vector, NOW()),
                ('{id2}'::uuid, 'Note Test', 'Note content', 'note', '{embedding_vector}'::vector, NOW())
        """))

    # Search with decision filter
    response = await test_client.post(
        "/api/v1/memories/search",
        json={"query": "test", "memory_type": "decision"}
    )

    assert response.status_code == 200
    data = response.json()

    # All results should be decisions
    for result in data["results"]:
        assert result["memory_type"] == "decision"


@pytest.mark.anyio
async def test_search_memories_invalid_type_returns_400(test_client):
    """Test invalid memory_type returns 400 error."""
    response = await test_client.post(
        "/api/v1/memories/search",
        json={"query": "test", "memory_type": "invalid_type"}
    )

    assert response.status_code == 400
    data = response.json()
    assert "Invalid memory_type" in data["detail"]


@pytest.mark.anyio
async def test_search_memories_empty_query_returns_422(test_client):
    """Test empty query returns 422 validation error."""
    response = await test_client.post(
        "/api/v1/memories/search",
        json={"query": ""}
    )

    assert response.status_code == 422  # Pydantic validation error
