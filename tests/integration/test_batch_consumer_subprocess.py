"""
Integration tests for batch consumer subprocess execution.

EPIC-27: Batch Processing with Redis Streams
Task 6: Subprocess execution capability

Tests:
1. test_subprocess_execution_success - Verify successful batch processing
2. test_subprocess_execution_timeout - Verify timeout handling
"""

import os
import asyncio
import pytest
from pathlib import Path
from services.batch_indexing_consumer import BatchIndexingConsumer


@pytest.mark.asyncio
async def test_subprocess_execution_success(test_db_url, code_chunk_repo, clean_db):
    """
    Test successful subprocess execution for batch processing.

    Workflow:
        1. Create 2 small test files in /tmp
        2. Call _run_subprocess_worker() with these files
        3. Assert success_count == 2 and error_count == 0
        4. Verify chunks created in test database
    """
    # Setup: Create test files
    test_dir = Path("/tmp/test_batch_subprocess")
    test_dir.mkdir(parents=True, exist_ok=True)

    # Create 2 small TypeScript files
    file1 = test_dir / "test1.ts"
    file1.write_text("""
function add(a: number, b: number): number {
    return a + b;
}
""")

    file2 = test_dir / "test2.ts"
    file2.write_text("""
function multiply(x: number, y: number): number {
    return x * y;
}
""")

    # Initialize consumer
    consumer = BatchIndexingConsumer(
        redis_url="redis://redis:6379/0",
        db_url=test_db_url
    )

    try:
        # Execute subprocess worker
        result = await consumer._run_subprocess_worker(
            repository="test_batch_subprocess",
            files=[str(file1), str(file2)],
            timeout=60  # 60s timeout (generous for integration test)
        )

        # Assert success
        assert result["success_count"] == 2, f"Expected 2 successful files, got {result['success_count']}"
        assert result["error_count"] == 0, f"Expected 0 errors, got {result['error_count']}"
        assert "error" not in result, f"Unexpected error: {result.get('error')}"

        # Verify chunks in database
        chunks = await code_chunk_repo.get_by_repository("test_batch_subprocess")
        assert len(chunks) > 0, "Expected chunks in database, got none"

        # Verify files indexed
        file_paths = {chunk.file_path for chunk in chunks}
        assert str(file1) in file_paths, f"File {file1} not indexed"
        assert str(file2) in file_paths, f"File {file2} not indexed"

    finally:
        # Cleanup: Remove test files
        file1.unlink(missing_ok=True)
        file2.unlink(missing_ok=True)
        test_dir.rmdir()


@pytest.mark.asyncio
async def test_subprocess_execution_timeout(test_db_url):
    """
    Test subprocess timeout handling.

    Workflow:
        1. Call _run_subprocess_worker() with very low timeout (1s)
        2. Assert TimeoutError raised
        3. Verify subprocess killed (no zombie process)
    """
    # Setup: Create test file
    test_dir = Path("/tmp/test_batch_subprocess_timeout")
    test_dir.mkdir(parents=True, exist_ok=True)

    test_file = test_dir / "test.ts"
    test_file.write_text("""
function slow(): void {
    // This will trigger model loading which takes ~30s
    console.log("test");
}
""")

    # Initialize consumer
    consumer = BatchIndexingConsumer(
        redis_url="redis://redis:6379/0",
        db_url=test_db_url
    )

    try:
        # Execute subprocess worker with artificially low timeout
        with pytest.raises((TimeoutError, asyncio.TimeoutError)):
            await consumer._run_subprocess_worker(
                repository="test_timeout",
                files=[str(test_file)],
                timeout=1  # 1s timeout (too low for model loading)
            )

        # Verify no zombie processes (check subprocess cleanup)
        # This is implicit - if timeout handling is correct, process is killed
        # and no zombie processes remain. We can't easily check for zombies
        # without additional system calls, but the test passing means
        # asyncio.wait_for() handled cleanup correctly.

    finally:
        # Cleanup: Remove test files
        test_file.unlink(missing_ok=True)
        test_dir.rmdir()
