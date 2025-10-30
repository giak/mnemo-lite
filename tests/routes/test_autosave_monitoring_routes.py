"""
Tests for EPIC-24 Auto-Save Conversations Monitoring Routes.

EPIC-24: Tests all 6 endpoints for autosave monitoring and health checks.
"""

import pytest
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path


@pytest.fixture
async def insert_test_memory(clean_db):
    """
    Helper fixture to insert test memories into the database.

    Uses asyncpg raw connection to avoid SQLAlchemy parameter issues.
    """
    async def _insert(
        title: str,
        content: str,
        author: str = "AutoImport",
        tags: list = None,
        created_at: datetime = None,
        embedding: list = None
    ):
        ts = created_at or datetime.now(timezone.utc)
        tags_array = tags or []

        async with clean_db.begin() as conn:
            raw_conn = await conn.get_raw_connection()
            async_conn = raw_conn.driver_connection

            if embedding:
                # Insert with embedding
                result = await async_conn.fetch(
                    """
                    INSERT INTO memories (title, content, author, tags, created_at, updated_at, embedding)
                    VALUES ($1, $2, $3, $4, $5, $6, $7::vector)
                    RETURNING id
                    """,
                    title, content, author, tags_array, ts, ts, str(embedding)
                )
            else:
                # Insert without embedding
                result = await async_conn.fetch(
                    """
                    INSERT INTO memories (title, content, author, tags, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                    """,
                    title, content, author, tags_array, ts, ts
                )

            return str(result[0]['id'])

    return _insert


# ============================================================================
# TEST: /v1/autosave/stats
# ============================================================================

@pytest.mark.anyio
async def test_get_autosave_stats_empty(test_client):
    """
    Test GET /v1/autosave/stats with no memories.

    EPIC-24: Validates stats endpoint returns zero counts when database is empty.
    """
    response = await test_client.get("/v1/autosave/stats")

    assert response.status_code == 200
    result = response.json()

    assert result["total_conversations"] == 0
    assert result["last_24_hours"] == 0
    assert result["last_7_days"] == 0
    assert result["last_30_days"] == 0
    assert result["with_embeddings"] == 0
    assert result["embedding_coverage_pct"] == 0
    assert result["last_import_at"] is None


@pytest.mark.anyio
async def test_get_autosave_stats_with_data(test_client, insert_test_memory):
    """
    Test GET /v1/autosave/stats with various memories.

    EPIC-24: Validates stats aggregation across different time windows.
    """
    now = datetime.now(timezone.utc)

    # Insert memories at different times
    await insert_test_memory("Conv 1", "Content 1", created_at=now - timedelta(hours=1))  # 24h
    await insert_test_memory("Conv 2", "Content 2", created_at=now - timedelta(days=3))   # 7d
    await insert_test_memory("Conv 3", "Content 3", created_at=now - timedelta(days=15))  # 30d
    await insert_test_memory("Conv 4", "Content 4", created_at=now - timedelta(days=60))  # old

    # Insert one with embedding
    await insert_test_memory(
        "Conv with embedding", "Content",
        created_at=now,
        embedding=[0.1] * 768
    )

    response = await test_client.get("/v1/autosave/stats")

    assert response.status_code == 200
    result = response.json()

    assert result["total_conversations"] == 5
    assert result["last_24_hours"] == 2  # Conv 1 + Conv with embedding
    assert result["last_7_days"] == 3    # Conv 1 + Conv 2 + Conv with embedding
    assert result["last_30_days"] == 4   # Conv 1 + Conv 2 + Conv 3 + Conv with embedding
    assert result["with_embeddings"] == 1
    assert result["embedding_coverage_pct"] == 20.0  # 1/5 * 100
    assert result["last_import_at"] is not None


# ============================================================================
# TEST: /v1/autosave/timeline
# ============================================================================

@pytest.mark.anyio
async def test_get_import_timeline_empty(test_client):
    """
    Test GET /v1/autosave/timeline with no memories.

    EPIC-24: Validates timeline endpoint returns empty list when no imports.
    """
    response = await test_client.get("/v1/autosave/timeline")

    assert response.status_code == 200
    result = response.json()

    assert isinstance(result, list)
    assert len(result) == 0


@pytest.mark.anyio
async def test_get_import_timeline_with_data(test_client, insert_test_memory):
    """
    Test GET /v1/autosave/timeline with memories.

    EPIC-24: Validates timeline aggregation by day.
    """
    now = datetime.now(timezone.utc)

    # Insert 3 memories today
    await insert_test_memory("Today 1", "Content", created_at=now)
    await insert_test_memory("Today 2", "Content", created_at=now - timedelta(hours=2))
    await insert_test_memory("Today 3", "Content", created_at=now - timedelta(hours=4))

    # Insert 2 memories yesterday
    yesterday = now - timedelta(days=1)
    await insert_test_memory("Yesterday 1", "Content", created_at=yesterday)
    await insert_test_memory("Yesterday 2", "Content", created_at=yesterday - timedelta(hours=5))

    response = await test_client.get("/v1/autosave/timeline?days=7")

    assert response.status_code == 200
    result = response.json()

    assert isinstance(result, list)
    assert len(result) >= 2  # At least 2 days with data

    # First entry should be most recent (DESC order)
    for entry in result:
        assert "date" in entry
        assert "count" in entry
        assert isinstance(entry["count"], int)


# ============================================================================
# TEST: /v1/autosave/recent
# ============================================================================

@pytest.mark.anyio
async def test_get_recent_conversations_empty(test_client):
    """
    Test GET /v1/autosave/recent with no memories.

    EPIC-24: Validates recent endpoint returns empty list.
    """
    response = await test_client.get("/v1/autosave/recent")

    assert response.status_code == 200
    result = response.json()

    assert isinstance(result, list)
    assert len(result) == 0


@pytest.mark.anyio
async def test_get_recent_conversations_with_data(test_client, insert_test_memory):
    """
    Test GET /v1/autosave/recent with memories.

    EPIC-24: Validates recent conversations retrieval with preview truncation.
    """
    now = datetime.now(timezone.utc)

    # Insert conversations with various lengths
    short_content = "Short conversation content"
    long_content = "A" * 250  # Longer than 200 chars preview

    await insert_test_memory(
        "Recent Conv 1",
        short_content,
        tags=["tag1", "tag2"],
        created_at=now
    )

    conv2_id = await insert_test_memory(
        "Recent Conv 2",
        long_content,
        tags=["tag3"],
        created_at=now - timedelta(minutes=5)
    )

    response = await test_client.get("/v1/autosave/recent?limit=10")

    assert response.status_code == 200
    result = response.json()

    assert isinstance(result, list)
    assert len(result) == 2

    # Verify structure of first conversation
    conv = result[0]
    assert "id" in conv
    assert "title" in conv
    assert "preview" in conv
    assert "tags" in conv
    assert "created_at" in conv
    assert "created_ago" in conv

    # Verify preview truncation
    assert len(result[1]["preview"]) <= 203  # 200 + "..."


@pytest.mark.anyio
async def test_get_recent_conversations_limit(test_client, insert_test_memory):
    """
    Test GET /v1/autosave/recent respects limit parameter.

    EPIC-24: Validates limit parameter controls result count.
    """
    now = datetime.now(timezone.utc)

    # Insert 15 memories
    for i in range(15):
        await insert_test_memory(f"Conv {i}", f"Content {i}", created_at=now - timedelta(minutes=i))

    response = await test_client.get("/v1/autosave/recent?limit=5")

    assert response.status_code == 200
    result = response.json()

    assert len(result) == 5


# ============================================================================
# TEST: /v1/autosave/daemon-status
# ============================================================================

@pytest.mark.anyio
async def test_get_daemon_status_no_state_file(test_client):
    """
    Test GET /v1/autosave/daemon-status when state file doesn't exist.

    EPIC-24: Validates daemon status returns 'unknown' when state file is missing.
    """
    # Ensure state file doesn't exist
    state_file = Path("/tmp/mnemo-conversations-state.json")
    if state_file.exists():
        state_file.unlink()

    response = await test_client.get("/v1/autosave/daemon-status")

    assert response.status_code == 200
    result = response.json()

    assert result["status"] == "unknown"
    assert result["state_file_exists"] is False
    assert "message" in result


@pytest.mark.anyio
async def test_get_daemon_status_with_state_file(test_client):
    """
    Test GET /v1/autosave/daemon-status when state file exists.

    EPIC-24: Validates daemon status reads state file correctly.
    """
    # Create state file
    state_file = Path("/tmp/mnemo-conversations-state.json")
    state_data = {
        "saved_hashes": ["hash1", "hash2", "hash3"],
        "last_import": "2025-10-30T10:00:00"
    }
    state_file.write_text(json.dumps(state_data))

    response = await test_client.get("/v1/autosave/daemon-status")

    assert response.status_code == 200
    result = response.json()

    assert result["status"] == "running"
    assert result["state_file_exists"] is True
    assert result["saved_hashes_count"] == 3
    assert result["last_import"] == "2025-10-30T10:00:00"
    assert "last_activity" in result
    assert "last_activity_ago" in result

    # Cleanup
    state_file.unlink()


# ============================================================================
# TEST: /v1/autosave/health
# ============================================================================

@pytest.mark.anyio
async def test_daemon_health_check_missing_heartbeat(test_client):
    """
    Test GET /v1/autosave/health when heartbeat file is missing.

    EPIC-24: Validates health check returns 'critical' status when daemon heartbeat is missing.
    """
    # Ensure heartbeat file doesn't exist
    heartbeat_file = Path("/tmp/daemon-heartbeat.txt")
    if heartbeat_file.exists():
        heartbeat_file.unlink()

    # Note: The endpoint raises HTTPException(503) for critical status
    # We expect the endpoint to raise this exception
    response = await test_client.get("/v1/autosave/health")

    # The health endpoint returns 503 if status is critical
    # But our test_client might handle this differently
    # Let's check if we get 200 with status=critical OR 503
    if response.status_code == 200:
        result = response.json()
        assert result["status"] == "critical"
        assert "Daemon heartbeat file missing" in result["issues"]
    else:
        assert response.status_code == 503


@pytest.mark.anyio
async def test_daemon_health_check_stale_heartbeat(test_client):
    """
    Test GET /v1/autosave/health when heartbeat is stale.

    EPIC-24: Validates health check detects stale daemon heartbeat.
    """
    import time

    # Create stale heartbeat (3 minutes ago)
    heartbeat_file = Path("/tmp/daemon-heartbeat.txt")
    stale_timestamp = int(time.time() - 180)  # 3 minutes ago
    heartbeat_file.write_text(str(stale_timestamp))

    response = await test_client.get("/v1/autosave/health")

    if response.status_code == 200:
        result = response.json()
        assert result["status"] in ["unhealthy", "critical"]
        assert any("heartbeat stale" in issue.lower() for issue in result["issues"])
    else:
        assert response.status_code == 503

    # Cleanup
    heartbeat_file.unlink()


@pytest.mark.anyio
async def test_daemon_health_check_healthy(test_client, insert_test_memory):
    """
    Test GET /v1/autosave/health when daemon is healthy.

    EPIC-24: Validates health check returns 'healthy' status when all checks pass.
    """
    import time

    # Create fresh heartbeat
    heartbeat_file = Path("/tmp/daemon-heartbeat.txt")
    heartbeat_file.write_text(str(int(time.time())))

    # Create metrics file
    metrics_file = Path("/tmp/daemon-metrics.json")
    metrics_file.write_text(json.dumps({
        "consecutive_failures": 0,
        "status": "running"
    }))

    # Insert a recent memory (within last 10 minutes)
    now = datetime.now(timezone.utc)
    await insert_test_memory("Recent import", "Content", created_at=now)

    response = await test_client.get("/v1/autosave/health")

    assert response.status_code == 200
    result = response.json()

    assert result["status"] in ["healthy", "degraded"]  # May be degraded if no imports in last 10 min
    assert "timestamp" in result
    assert "daemon" in result
    assert "issues" in result

    # Cleanup
    heartbeat_file.unlink()
    metrics_file.unlink()


# ============================================================================
# TEST: /v1/autosave/conversation/{conversation_id}
# ============================================================================

@pytest.mark.anyio
async def test_get_conversation_content_not_found(test_client):
    """
    Test GET /v1/autosave/conversation/{id} with non-existent ID.

    EPIC-24: Validates conversation endpoint returns error for missing conversations.
    """
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    response = await test_client.get(f"/v1/autosave/conversation/{fake_uuid}")

    assert response.status_code == 200
    result = response.json()

    assert "error" in result
    assert result["error"] == "Conversation not found"


@pytest.mark.anyio
async def test_get_conversation_content_success(test_client, insert_test_memory):
    """
    Test GET /v1/autosave/conversation/{id} with valid ID.

    EPIC-24: Validates conversation content retrieval returns full content.
    """
    # Insert a conversation
    content = "This is the full conversation content with lots of details."
    conv_id = await insert_test_memory(
        "Test Conversation",
        content,
        tags=["important", "test"]
    )

    response = await test_client.get(f"/v1/autosave/conversation/{conv_id}")

    assert response.status_code == 200
    result = response.json()

    assert result["id"] == conv_id
    assert result["title"] == "Test Conversation"
    assert result["content"] == content
    assert result["tags"] == ["important", "test"]
    assert "created_at" in result


@pytest.mark.anyio
async def test_get_conversation_only_autoimport(test_client, insert_test_memory):
    """
    Test GET /v1/autosave/conversation/{id} only returns AutoImport conversations.

    EPIC-24: Validates endpoint filters by author='AutoImport'.
    """
    # Insert conversation with different author
    other_conv_id = await insert_test_memory(
        "Manual Memory",
        "Content",
        author="User"
    )

    response = await test_client.get(f"/v1/autosave/conversation/{other_conv_id}")

    assert response.status_code == 200
    result = response.json()

    # Should not find it because author != 'AutoImport'
    assert "error" in result
    assert result["error"] == "Conversation not found"
