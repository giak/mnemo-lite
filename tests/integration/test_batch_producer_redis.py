import pytest
import json
from pathlib import Path
from services.batch_indexing_producer import BatchIndexingProducer


@pytest.mark.asyncio
@pytest.mark.integration
async def test_scan_and_enqueue_creates_batches(redis_client, tmp_path):
    """Test producer enqueues batches into Redis Stream."""
    # Create 10 test files
    for i in range(10):
        (tmp_path / f"file{i}.ts").write_text(f"// test {i}")

    producer = BatchIndexingProducer()
    await producer.connect()

    try:
        result = await producer.scan_and_enqueue(
            directory=tmp_path,
            repository="test_repo"
        )

        # Verify result
        assert result["total_files"] == 10
        assert result["total_batches"] == 1  # 10 files = 1 batch (size 40)
        assert result["status"] == "pending"
        assert "job_id" in result

        # Verify stream contains message
        stream_key = "indexing:jobs:test_repo"
        messages = await redis_client.xread({stream_key: "0"}, count=10)

        assert len(messages) == 1
        stream_name, message_list = messages[0]
        assert len(message_list) == 1  # 1 batch

        message_id, message_data = message_list[0]
        assert message_data["repository"] == "test_repo"
        assert message_data["batch_number"] == "1"
        assert message_data["total_batches"] == "1"
        assert len(message_data["files"].split(",")) == 10

    finally:
        await producer.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_scan_and_enqueue_multiple_batches(redis_client, tmp_path):
    """Test producer creates multiple batches for large directories."""
    # Create 100 files (should create 3 batches: 40, 40, 20)
    for i in range(100):
        (tmp_path / f"file{i}.ts").write_text(f"// test {i}")

    producer = BatchIndexingProducer()
    await producer.connect()

    try:
        result = await producer.scan_and_enqueue(
            directory=tmp_path,
            repository="test_large"
        )

        assert result["total_files"] == 100
        assert result["total_batches"] == 3  # 100 ÷ 40 = 3 batches

        # Verify stream contains 3 messages
        stream_key = "indexing:jobs:test_large"
        messages = await redis_client.xread({stream_key: "0"}, count=10)

        stream_name, message_list = messages[0]
        assert len(message_list) == 3  # 3 batches

        # Verify batch numbers
        batch_numbers = [msg[1]["batch_number"] for msg in message_list]
        assert batch_numbers == ["1", "2", "3"]

    finally:
        await producer.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_init_status_creates_hash(redis_client):
    """Test status hash initialization."""
    producer = BatchIndexingProducer()
    await producer.connect()

    try:
        await producer._init_status(
            repository="test_status",
            job_id="test-job-123",
            total_files=100,
            total_batches=3
        )

        # Verify status hash
        status_key = "indexing:status:test_status"
        status = await redis_client.hgetall(status_key)

        assert status["job_id"] == "test-job-123"
        assert status["total_files"] == "100"
        assert status["total_batches"] == "3"
        assert status["processed_files"] == "0"
        assert status["failed_files"] == "0"
        assert status["current_batch"] == "0"
        assert status["status"] == "pending"
        assert status["started_at"] != ""
        assert status["errors"] == "[]"

        # Verify TTL is set
        ttl = await redis_client.ttl(status_key)
        assert ttl > 0
        assert ttl <= 86400

    finally:
        await producer.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_status_returns_dict(redis_client):
    """Test get_status returns formatted dict."""
    producer = BatchIndexingProducer()
    await producer.connect()

    try:
        # Initialize status
        await producer._init_status(
            repository="test_get",
            job_id="job-456",
            total_files=50,
            total_batches=2
        )

        # Get status
        status = await producer.get_status("test_get")

        assert status["job_id"] == "job-456"
        assert status["total_files"] == 50
        assert status["processed_files"] == 0
        assert status["failed_files"] == 0
        assert status["current_batch"] == 0
        assert status["total_batches"] == 2
        assert status["status"] == "pending"
        assert "progress" in status
        assert status["progress"] == "0/50"

    finally:
        await producer.close()
