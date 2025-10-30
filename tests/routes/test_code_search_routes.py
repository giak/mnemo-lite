"""
Tests for Code Search Routes (Core Routes).

Tests hybrid, lexical, and vector search endpoints for code chunks.
"""

import pytest


# ============================================================================
# TEST: GET /health (Health Check)
# ============================================================================

@pytest.mark.anyio
async def test_search_health_check(test_client):
    """
    Test GET /health returns service status.

    Validates database connectivity and required tables existence.
    """
    response = await test_client.get("/v1/code/search/health")

    assert response.status_code == 200
    result = response.json()

    assert result["status"] == "healthy"
    assert result["database"] == "connected"
    assert "required_tables" in result
    assert result["services"]["lexical_search"] == "available"
    assert result["services"]["vector_search"] == "available"
    assert result["services"]["hybrid_search"] == "available"


# ============================================================================
# TEST: POST /lexical (Lexical-Only Search)
# ============================================================================

@pytest.mark.anyio
async def test_lexical_search_empty_db(test_client):
    """
    Test POST /lexical with empty database.

    Validates lexical search returns empty results when no code chunks exist.
    """
    request_data = {
        "query": "calculate total price",
        "limit": 10
    }

    response = await test_client.post("/v1/code/search/lexical", json=request_data)

    assert response.status_code == 200
    result = response.json()

    assert isinstance(result["results"], list)
    assert result["total_results"] == 0


@pytest.mark.anyio
async def test_lexical_search_with_filters(test_client):
    """
    Test POST /lexical with language filter.

    Validates filter parameter handling.
    """
    request_data = {
        "query": "def hello",
        "filters": {
            "language": "python"
        },
        "limit": 10
    }

    response = await test_client.post("/v1/code/search/lexical", json=request_data)

    assert response.status_code == 200
    result = response.json()

    assert isinstance(result["results"], list)
    assert result["total_results"] >= 0


# ============================================================================
# TEST: POST /vector (Vector-Only Search)
# ============================================================================

@pytest.mark.anyio
async def test_vector_search_empty_db(test_client):
    """
    Test POST /vector with empty database.

    Validates vector search returns empty results when no code chunks exist.
    """
    request_data = {
        "embedding": [0.1] * 768,  # Mock 768D embedding
        "embedding_domain": "TEXT",
        "limit": 10
    }

    response = await test_client.post("/v1/code/search/vector", json=request_data)

    assert response.status_code == 200
    result = response.json()

    assert isinstance(result["results"], list)
    assert result["total_results"] == 0
    assert result["embedding_domain"] == "TEXT"


@pytest.mark.anyio
async def test_vector_search_invalid_domain(test_client):
    """
    Test POST /vector with invalid embedding_domain.

    Validates error handling for incorrect domain values.
    """
    request_data = {
        "embedding": [0.1] * 768,
        "embedding_domain": "INVALID",
        "limit": 10
    }

    response = await test_client.post("/v1/code/search/vector", json=request_data)

    assert response.status_code == 400
    assert "must be 'TEXT' or 'CODE'" in response.json()["detail"]


@pytest.mark.anyio
async def test_vector_search_code_domain(test_client):
    """
    Test POST /vector with CODE embedding domain.

    Validates CODE domain parameter handling.
    """
    request_data = {
        "embedding": [0.2] * 768,
        "embedding_domain": "CODE",
        "limit": 5
    }

    response = await test_client.post("/v1/code/search/vector", json=request_data)

    assert response.status_code == 200
    result = response.json()

    assert isinstance(result["results"], list)
    assert result["embedding_domain"] == "CODE"


# ============================================================================
# TEST: POST /hybrid (Hybrid Search)
# ============================================================================

@pytest.mark.anyio
async def test_hybrid_search_lexical_only(test_client):
    """
    Test POST /hybrid with lexical-only mode.

    Validates hybrid search with vector disabled.
    """
    request_data = {
        "query": "calculate total",
        "enable_lexical": True,
        "enable_vector": False,
        "top_k": 10
    }

    response = await test_client.post("/v1/code/search/hybrid", json=request_data)

    assert response.status_code == 200
    result = response.json()

    assert "results" in result
    assert "metadata" in result
    assert isinstance(result["results"], list)

    # Metadata validation
    metadata = result["metadata"]
    assert metadata["lexical_enabled"] is True
    assert metadata["vector_enabled"] is False


@pytest.mark.anyio
async def test_hybrid_search_vector_only(test_client):
    """
    Test POST /hybrid with vector-only mode.

    Validates hybrid search with lexical disabled.
    """
    request_data = {
        "query": "test query",
        "embedding_text": [0.5] * 768,
        "enable_lexical": False,
        "enable_vector": True,
        "top_k": 5
    }

    response = await test_client.post("/v1/code/search/hybrid", json=request_data)

    assert response.status_code == 200
    result = response.json()

    metadata = result["metadata"]
    assert metadata["lexical_enabled"] is False
    assert metadata["vector_enabled"] is True


@pytest.mark.anyio
async def test_hybrid_search_full_hybrid(test_client):
    """
    Test POST /hybrid with both lexical and vector enabled.

    Validates RRF fusion with custom weights.
    """
    request_data = {
        "query": "function calculate",
        "embedding_text": [0.3] * 768,
        "enable_lexical": True,
        "enable_vector": True,
        "lexical_weight": 0.6,
        "vector_weight": 0.4,
        "top_k": 10
    }

    response = await test_client.post("/v1/code/search/hybrid", json=request_data)

    assert response.status_code == 200
    result = response.json()

    metadata = result["metadata"]
    assert metadata["lexical_enabled"] is True
    assert metadata["vector_enabled"] is True
    assert metadata["lexical_weight"] == 0.6
    assert metadata["vector_weight"] == 0.4


@pytest.mark.anyio
async def test_hybrid_search_auto_weights(test_client):
    """
    Test POST /hybrid with auto_weights enabled.

    Validates automatic weight selection based on query analysis.
    """
    request_data = {
        "query": "models.User.authenticate",  # Qualified name
        "embedding_text": [0.4] * 768,
        "auto_weights": True,
        "top_k": 10
    }

    response = await test_client.post("/v1/code/search/hybrid", json=request_data)

    assert response.status_code == 200
    result = response.json()

    # Auto-weights should adjust based on query
    metadata = result["metadata"]
    assert "lexical_weight" in metadata
    assert "vector_weight" in metadata


@pytest.mark.anyio
async def test_hybrid_search_with_filters(test_client):
    """
    Test POST /hybrid with multiple filters.

    Validates filter combination (language + chunk_type).
    """
    request_data = {
        "query": "def process",
        "filters": {
            "language": "python",
            "chunk_type": "function"
        },
        "top_k": 10
    }

    response = await test_client.post("/v1/code/search/hybrid", json=request_data)

    assert response.status_code == 200
    result = response.json()

    assert isinstance(result["results"], list)


@pytest.mark.anyio
async def test_hybrid_search_code_embedding(test_client):
    """
    Test POST /hybrid with CODE domain embedding.

    Validates CODE embedding usage (prioritized over TEXT if provided).
    """
    request_data = {
        "query": "function implementation",
        "embedding_text": [0.1] * 768,
        "embedding_code": [0.9] * 768,  # CODE embedding (should be prioritized)
        "enable_vector": True,
        "top_k": 5
    }

    response = await test_client.post("/v1/code/search/hybrid", json=request_data)

    assert response.status_code == 200
    result = response.json()

    assert isinstance(result["results"], list)
    assert result["metadata"]["vector_enabled"] is True


@pytest.mark.anyio
async def test_hybrid_search_metadata_timing(test_client):
    """
    Test POST /hybrid returns execution timing metadata.

    Validates performance metrics in response.
    """
    request_data = {
        "query": "test",
        "embedding_text": [0.2] * 768,
        "top_k": 10
    }

    response = await test_client.post("/v1/code/search/hybrid", json=request_data)

    assert response.status_code == 200
    result = response.json()

    metadata = result["metadata"]
    assert "execution_time_ms" in metadata
    assert isinstance(metadata["execution_time_ms"], float)
    assert metadata["execution_time_ms"] >= 0
