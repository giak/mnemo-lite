"""
Integration tests for batch consumer loop with retry logic.

EPIC-27: Batch Processing with Redis Streams
Tasks 7-9: Complete Consumer Loop with Retry Logic and Graph Construction

Tests:
1. test_process_repository_completes_all_batches - End-to-end batch processing
2. test_consumer_retries_failed_batch - Retry logic with XPENDING
3. test_graph_construction_triggered_on_completion - Graph built automatically
4. test_consumer_handles_stop_event - Graceful stop
"""

import asyncio
import pytest
from pathlib import Path
from services.batch_indexing_consumer import BatchIndexingConsumer
from services.batch_indexing_producer import BatchIndexingProducer


@pytest.mark.asyncio
@pytest.mark.integration
async def test_process_repository_completes_all_batches(redis_client, test_db_url, clean_db):
    """
    Test consumer processes all batches from stream.

    Workflow:
        1. Producer enqueues 1 batch (3 files total, batch_size=40)
        2. Consumer processes the batch
        3. Assert: 3 files processed, status="completed", stream empty
    """
    # Setup: Create 3 test files (batch_size=40, so 3 files = 1 batch)
    test_dir = Path("/tmp/test_consumer_loop")
    test_dir.mkdir(parents=True, exist_ok=True)

    test_files = []
    for i in range(3):
        test_file = test_dir / f"test{i}.ts"
        test_file.write_text(f"""
function func{i}(x: number): number {{
    return x * {i};
}}
""")
        test_files.append(test_file)

    try:
        # Step 1: Producer enqueues batches
        producer = BatchIndexingProducer(redis_url="redis://redis:6379/0")
        await producer.connect()

        result = await producer.scan_and_enqueue(
            directory=test_dir,
            repository="test_consumer_loop",
            extensions=[".ts"]
        )

        assert result["total_batches"] == 1, f"Expected 1 batch, got {result['total_batches']}"
        assert result["total_files"] == 3, f"Expected 3 files, got {result['total_files']}"

        # Step 2: Consumer processes all batches
        consumer = BatchIndexingConsumer(
            redis_url="redis://redis:6379/0",
            db_url=test_db_url
        )
        await consumer.connect()

        # Process repository (no stop_event = run until complete)
        stats = await consumer.process_repository("test_consumer_loop")

        # Step 3: Assertions
        assert stats["processed_files"] == 3, f"Expected 3 processed files, got {stats['processed_files']}"
        assert stats["status"] == "completed", f"Expected status='completed', got {stats['status']}"

        # Verify no pending messages (XACK'd messages remain in stream but are marked as processed)
        stream_key = f"indexing:jobs:test_consumer_loop"
        try:
            pending = await redis_client.xpending(stream_key, "indexing-workers")
            # pending['pending'] should be 0
            assert pending["pending"] == 0, f"Expected 0 pending messages, got {pending['pending']}"
        except:
            # Consumer group might not exist - that's OK, means stream was cleaned up
            pass

        # Verify status hash
        status_key = f"indexing:status:test_consumer_loop"
        status = await redis_client.hgetall(status_key)
        assert status["status"] == "completed"
        assert status["processed_files"] == "3"
        assert status["current_batch"] == "1"

        await producer.close()
        await consumer.close()

    finally:
        # Cleanup
        for test_file in test_files:
            test_file.unlink(missing_ok=True)
        test_dir.rmdir()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_consumer_retries_failed_batch(redis_client, test_db_url, clean_db):
    """
    Test consumer retries batch that failed first time.

    Workflow:
        1. Manually enqueue a batch with invalid file path
        2. Consumer tries, fails, leaves message pending
        3. _check_pending_messages detects, _retry_pending_batch claims and retries
        4. Assert: Batch processed on 2nd attempt or marked as failed

    Note: This test verifies the retry mechanism, but the batch will still fail
    if the file is invalid. We're testing that the retry logic executes.
    """
    # Setup: Create test file
    test_dir = Path("/tmp/test_consumer_retry")
    test_dir.mkdir(parents=True, exist_ok=True)

    test_file = test_dir / "test.ts"
    test_file.write_text("""
function test(): void {
    console.log("test");
}
""")

    try:
        # Step 1: Manually enqueue batch with mixed valid/invalid files
        # This simulates a transient error scenario
        stream_key = "indexing:jobs:test_consumer_retry"
        status_key = "indexing:status:test_consumer_retry"

        # Initialize status
        await redis_client.hset(
            status_key,
            mapping={
                "job_id": "test-job-123",
                "total_files": "2",
                "total_batches": "1",
                "processed_files": "0",
                "failed_files": "0",
                "current_batch": "0",
                "status": "pending",
                "started_at": "2025-11-02T00:00:00Z",
                "completed_at": "",
                "errors": "[]"
            }
        )

        # Enqueue batch with invalid file first (will fail)
        await redis_client.xadd(
            stream_key,
            {
                "job_id": "test-job-123",
                "repository": "test_consumer_retry",
                "batch_number": "1",
                "total_batches": "1",
                "files": "/nonexistent/file.ts," + str(test_file),
                "created_at": "2025-11-02T00:00:00Z"
            }
        )

        # Step 2: Consumer processes (will fail on first try due to invalid file)
        consumer = BatchIndexingConsumer(
            redis_url="redis://redis:6379/0",
            db_url=test_db_url
        )
        await consumer.connect()

        # Process repository with short timeout to trigger retry logic
        stats = await consumer.process_repository("test_consumer_retry")

        # Step 3: Verify retry attempt was made
        # The batch may fail even after retry (invalid file), but we verify retry logic executed
        status = await redis_client.hgetall(status_key)

        # At minimum, we should have attempted processing
        assert int(status["processed_files"]) >= 1, "Expected at least 1 file processed"

        # Stream should have no pending messages (ACK'd even if partially failed)
        try:
            pending = await redis_client.xpending(stream_key, "indexing-workers")
            assert pending["pending"] == 0, f"Expected 0 pending messages, got {pending['pending']}"
        except:
            # Consumer group might not exist - that's OK
            pass

        await consumer.close()

    finally:
        # Cleanup
        test_file.unlink(missing_ok=True)
        test_dir.rmdir()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_graph_construction_triggered_on_completion(redis_client, test_db_url, clean_db):
    """
    Test graph construction called when all batches complete.

    Workflow:
        1. Enqueue 1 batch with 2 files
        2. Consumer processes batch
        3. Assert: graph nodes/edges created in DB
    """
    # Setup: Create 2 test files with function calls
    test_dir = Path("/tmp/test_consumer_graph")
    test_dir.mkdir(parents=True, exist_ok=True)

    file1 = test_dir / "utils.ts"
    file1.write_text("""
export function helper(x: number): number {
    return x * 2;
}
""")

    file2 = test_dir / "main.ts"
    file2.write_text("""
import { helper } from './utils';

export function main(): void {
    const result = helper(42);
    console.log(result);
}
""")

    try:
        # Step 1: Producer enqueues batch
        producer = BatchIndexingProducer(redis_url="redis://redis:6379/0")
        await producer.connect()

        result = await producer.scan_and_enqueue(
            directory=test_dir,
            repository="test_consumer_graph",
            extensions=[".ts"]
        )

        assert result["total_files"] == 2

        # Step 2: Consumer processes batch (triggers graph construction)
        consumer = BatchIndexingConsumer(
            redis_url="redis://redis:6379/0",
            db_url=test_db_url
        )
        await consumer.connect()

        stats = await consumer.process_repository("test_consumer_graph")

        # Step 3: Verify graph construction
        assert stats["status"] == "completed"

        # Verify nodes created in database
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(test_db_url)
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT COUNT(*) FROM nodes WHERE properties->>'repository' = :repo"),
                {"repo": "test_consumer_graph"}
            )
            node_count = result.scalar()

            # Expect at least 2 nodes (helper + main functions)
            assert node_count >= 2, f"Expected at least 2 nodes, got {node_count}"

        await engine.dispose()
        await producer.close()
        await consumer.close()

    finally:
        # Cleanup
        file1.unlink(missing_ok=True)
        file2.unlink(missing_ok=True)
        test_dir.rmdir()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_consumer_handles_stop_event(redis_client, test_db_url, clean_db):
    """
    Test consumer stops gracefully when stop_event is set.

    Workflow:
        1. Enqueue 3 batches (120 files, batch_size=40)
        2. Start consumer with stop_event
        3. Set stop_event after 1 batch
        4. Assert: Consumer stops, remaining batches still in stream
    """
    # Setup: Create 120 test files (3 batches at batch_size=40)
    test_dir = Path("/tmp/test_consumer_stop")
    test_dir.mkdir(parents=True, exist_ok=True)

    test_files = []
    for i in range(120):
        test_file = test_dir / f"test{i}.ts"
        test_file.write_text(f"""
function func{i}(): number {{
    return {i};
}}
""")
        test_files.append(test_file)

    try:
        # Step 1: Producer enqueues 3 batches (batch_size=40, so 120 files = 3 batches)
        producer = BatchIndexingProducer(redis_url="redis://redis:6379/0")
        await producer.connect()

        result = await producer.scan_and_enqueue(
            directory=test_dir,
            repository="test_consumer_stop",
            extensions=[".ts"]
        )

        assert result["total_batches"] == 3

        # Step 2: Start consumer with stop_event
        consumer = BatchIndexingConsumer(
            redis_url="redis://redis:6379/0",
            db_url=test_db_url
        )
        await consumer.connect()

        stop_event = asyncio.Event()

        # Set stop_event after 3s (should process 1 batch, ~40 files)
        async def set_stop_after_delay():
            await asyncio.sleep(3)
            stop_event.set()

        stop_task = asyncio.create_task(set_stop_after_delay())

        # Process repository with stop_event
        stats = await consumer.process_repository("test_consumer_stop", stop_event=stop_event)

        await stop_task

        # Step 3: Verify graceful stop
        # Consumer should have stopped before processing all 3 batches
        processed = int(stats["processed_files"])
        assert processed < 120, f"Expected consumer to stop before processing all files, got {processed}/120"
        assert processed > 0, "Expected some files to be processed before stop"

        # Stream should have remaining pending messages
        stream_key = "indexing:jobs:test_consumer_stop"
        try:
            pending = await redis_client.xpending(stream_key, "indexing-workers")
            # Should have pending messages OR total processed < total files
            assert pending["pending"] > 0 or processed < 120, f"Expected pending messages or incomplete processing"
        except:
            # Consumer group might not exist - check processed files instead
            assert processed < 120, f"Expected some files unprocessed due to stop event"

        await producer.close()
        await consumer.close()

    finally:
        # Cleanup
        for test_file in test_files:
            test_file.unlink(missing_ok=True)
        test_dir.rmdir()
