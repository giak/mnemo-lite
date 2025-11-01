"""
Tests for EPIC-25 Story 25.2: Dashboard Backend API Routes.

Tests all 3 dashboard endpoints for the Vue.js frontend.
"""

import pytest
from datetime import datetime, timezone, timedelta


@pytest.fixture
async def insert_test_memory(clean_db):
    """
    Helper fixture to insert test memories into the database.

    Uses asyncpg raw connection to avoid SQLAlchemy parameter issues.
    """
    async def _insert(
        title: str,
        content: str,
        author: str = "Test",
        created_at: datetime = None,
        embedding: list = None
    ):
        ts = created_at or datetime.now(timezone.utc)

        async with clean_db.begin() as conn:
            raw_conn = await conn.get_raw_connection()
            async_conn = raw_conn.driver_connection

            if embedding:
                # Insert with embedding
                result = await async_conn.fetch(
                    """
                    INSERT INTO memories (title, content, author, created_at, updated_at, embedding)
                    VALUES ($1, $2, $3, $4, $5, $6::vector)
                    RETURNING id
                    """,
                    title, content, author, ts, ts, str(embedding)
                )
            else:
                # Insert without embedding
                result = await async_conn.fetch(
                    """
                    INSERT INTO memories (title, content, author, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                    """,
                    title, content, author, ts, ts
                )

            return str(result[0]['id'])

    return _insert


@pytest.fixture
async def insert_test_code_chunk(clean_db):
    """
    Helper fixture to insert test code chunks into the database.
    """
    async def _insert(
        file_path: str,
        source_code: str,
        language: str = "python",
        indexed_at: datetime = None
    ):
        ts = indexed_at or datetime.now(timezone.utc)

        async with clean_db.begin() as conn:
            raw_conn = await conn.get_raw_connection()
            async_conn = raw_conn.driver_connection

            result = await async_conn.fetch(
                """
                INSERT INTO code_chunks (file_path, source_code, language, chunk_type, indexed_at, start_line, end_line)
                VALUES ($1, $2, $3, 'function', $4, 1, 10)
                RETURNING id
                """,
                file_path, source_code, language, ts
            )

            return str(result[0]['id'])

    return _insert


# ============================================================================
# TEST: /api/v1/dashboard/health
# ============================================================================

@pytest.mark.anyio
async def test_dashboard_health_success(test_client):
    """
    Test GET /api/v1/dashboard/health with healthy database.

    EPIC-25 Story 25.2: Validates health endpoint returns healthy status.
    """
    response = await test_client.get("/api/v1/dashboard/health")

    assert response.status_code == 200
    result = response.json()

    assert result["status"] == "healthy"
    assert "timestamp" in result
    assert "services" in result
    assert result["services"]["api"] is True
    assert result["services"]["database"] is True
    assert result["services"]["redis"] is True


@pytest.mark.anyio
async def test_dashboard_health_structure(test_client):
    """
    Test GET /api/v1/dashboard/health response structure.

    EPIC-25 Story 25.2: Validates all required fields are present.
    """
    response = await test_client.get("/api/v1/dashboard/health")

    assert response.status_code == 200
    result = response.json()

    # Check top-level fields
    assert "status" in result
    assert "timestamp" in result
    assert "services" in result

    # Check services structure
    services = result["services"]
    assert "api" in services
    assert "database" in services
    assert "redis" in services

    # Validate status value
    assert result["status"] in ["healthy", "degraded"]


# ============================================================================
# TEST: /api/v1/dashboard/embeddings/text
# ============================================================================

@pytest.mark.anyio
async def test_text_embeddings_stats_empty(test_client):
    """
    Test GET /api/v1/dashboard/embeddings/text with no embeddings.

    EPIC-25 Story 25.2: Validates text embeddings endpoint with empty database.
    """
    response = await test_client.get("/api/v1/dashboard/embeddings/text")

    assert response.status_code == 200
    result = response.json()

    assert result["model"] == "nomic-ai/nomic-embed-text-v1.5"
    assert result["count"] == 0
    assert result["dimension"] == 768
    assert result["lastIndexed"] is None


@pytest.mark.anyio
async def test_text_embeddings_stats_with_data(test_client, insert_test_memory):
    """
    Test GET /api/v1/dashboard/embeddings/text with embeddings.

    EPIC-25 Story 25.2: Validates text embeddings stats calculation.
    """
    now = datetime.now(timezone.utc)

    # Insert memories with embeddings
    await insert_test_memory(
        "Memory 1", "Content 1",
        created_at=now - timedelta(hours=1),
        embedding=[0.1] * 768
    )
    await insert_test_memory(
        "Memory 2", "Content 2",
        created_at=now,
        embedding=[0.2] * 768
    )

    # Insert memory without embedding (should not be counted)
    await insert_test_memory("Memory 3", "Content 3")

    response = await test_client.get("/api/v1/dashboard/embeddings/text")

    assert response.status_code == 200
    result = response.json()

    assert result["model"] == "nomic-ai/nomic-embed-text-v1.5"
    assert result["count"] == 2
    assert result["dimension"] == 768
    assert result["lastIndexed"] is not None

    # Verify lastIndexed is ISO format timestamp
    datetime.fromisoformat(result["lastIndexed"].replace('+00:00', ''))


@pytest.mark.anyio
async def test_text_embeddings_stats_only_counts_with_embeddings(test_client, insert_test_memory):
    """
    Test GET /api/v1/dashboard/embeddings/text only counts memories with embeddings.

    EPIC-25 Story 25.2: Validates filtering by embedding IS NOT NULL.
    """
    now = datetime.now(timezone.utc)

    # Insert 5 memories without embeddings
    for i in range(5):
        await insert_test_memory(f"No embedding {i}", f"Content {i}")

    # Insert 3 memories with embeddings
    for i in range(3):
        await insert_test_memory(
            f"With embedding {i}", f"Content {i}",
            created_at=now - timedelta(minutes=i),
            embedding=[0.1 * i] * 768
        )

    response = await test_client.get("/api/v1/dashboard/embeddings/text")

    assert response.status_code == 200
    result = response.json()

    assert result["count"] == 3  # Only those with embeddings


@pytest.mark.anyio
async def test_text_embeddings_stats_response_structure(test_client):
    """
    Test GET /api/v1/dashboard/embeddings/text response structure.

    EPIC-25 Story 25.2: Validates all required fields are present.
    """
    response = await test_client.get("/api/v1/dashboard/embeddings/text")

    assert response.status_code == 200
    result = response.json()

    # Check all required fields
    assert "model" in result
    assert "count" in result
    assert "dimension" in result
    assert "lastIndexed" in result

    # Validate types
    assert isinstance(result["model"], str)
    assert isinstance(result["count"], int)
    assert isinstance(result["dimension"], int)
    assert result["lastIndexed"] is None or isinstance(result["lastIndexed"], str)


# ============================================================================
# TEST: /api/v1/dashboard/embeddings/code
# ============================================================================

@pytest.mark.anyio
async def test_code_embeddings_stats_empty(test_client):
    """
    Test GET /api/v1/dashboard/embeddings/code with no code chunks.

    EPIC-25 Story 25.2: Validates code embeddings endpoint with empty database.
    """
    response = await test_client.get("/api/v1/dashboard/embeddings/code")

    assert response.status_code == 200
    result = response.json()

    assert result["model"] == "jinaai/jina-embeddings-v2-base-code"
    assert result["count"] == 0
    assert result["dimension"] == 768
    assert result["lastIndexed"] is None


@pytest.mark.anyio
async def test_code_embeddings_stats_with_data(test_client, insert_test_code_chunk):
    """
    Test GET /api/v1/dashboard/embeddings/code with code chunks.

    EPIC-25 Story 25.2: Validates code embeddings stats calculation.
    """
    now = datetime.now(timezone.utc)

    # Insert code chunks
    await insert_test_code_chunk(
        "/test/file1.py", "def foo(): pass",
        indexed_at=now - timedelta(hours=2)
    )
    await insert_test_code_chunk(
        "/test/file2.js", "function bar() {}",
        language="javascript",
        indexed_at=now
    )
    await insert_test_code_chunk(
        "/test/file3.py", "class Baz: pass",
        indexed_at=now - timedelta(days=1)
    )

    response = await test_client.get("/api/v1/dashboard/embeddings/code")

    assert response.status_code == 200
    result = response.json()

    assert result["model"] == "jinaai/jina-embeddings-v2-base-code"
    assert result["count"] == 3
    assert result["dimension"] == 768
    assert result["lastIndexed"] is not None

    # Verify lastIndexed is ISO format timestamp
    datetime.fromisoformat(result["lastIndexed"].replace('+00:00', ''))


@pytest.mark.anyio
async def test_code_embeddings_stats_response_structure(test_client):
    """
    Test GET /api/v1/dashboard/embeddings/code response structure.

    EPIC-25 Story 25.2: Validates all required fields are present.
    """
    response = await test_client.get("/api/v1/dashboard/embeddings/code")

    assert response.status_code == 200
    result = response.json()

    # Check all required fields
    assert "model" in result
    assert "count" in result
    assert "dimension" in result
    assert "lastIndexed" in result

    # Validate types
    assert isinstance(result["model"], str)
    assert isinstance(result["count"], int)
    assert isinstance(result["dimension"], int)
    assert result["lastIndexed"] is None or isinstance(result["lastIndexed"], str)


@pytest.mark.anyio
async def test_code_embeddings_stats_counts_all_chunks(test_client, insert_test_code_chunk):
    """
    Test GET /api/v1/dashboard/embeddings/code counts all code chunks.

    EPIC-25 Story 25.2: Validates total count includes all chunks regardless of language.
    """
    now = datetime.now(timezone.utc)

    # Insert chunks in various languages
    languages = ["python", "javascript", "typescript", "go", "rust"]
    for i, lang in enumerate(languages):
        await insert_test_code_chunk(
            f"/test/file{i}.{lang}", f"code content {i}",
            language=lang,
            indexed_at=now - timedelta(minutes=i)
        )

    response = await test_client.get("/api/v1/dashboard/embeddings/code")

    assert response.status_code == 200
    result = response.json()

    assert result["count"] == 5  # All languages
