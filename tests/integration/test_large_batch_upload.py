"""
Integration tests for large batch upload scenarios (EPIC-09 - Load Testing).

These tests reproduce real-world upload issues that unit tests miss:
- Large file batches (50-100+ files) with embeddings/graph enabled
- Memory consumption and connection pool exhaustion
- Background task timeouts and freezes
- Progress tracking under heavy load

CRITICAL: These tests should FAIL initially, exposing the production bug.
After fixing the upload pipeline, they should PASS.
"""

import pytest
import pytest_asyncio
import asyncio
import time
from sqlalchemy import text

from services.upload_progress_tracker import get_tracker


@pytest_asyncio.fixture
async def cleanup_tracker():
    """Clean up progress tracker after each test."""
    tracker = get_tracker()
    # Store initial sessions
    initial_sessions = await tracker.get_all_sessions()
    initial_ids = {s["upload_id"] for s in initial_sessions}

    yield

    # Clean up new sessions created during test
    final_sessions = await tracker.get_all_sessions()
    for session in final_sessions:
        if session["upload_id"] not in initial_ids:
            await tracker.remove_session(session["upload_id"])


@pytest_asyncio.fixture
async def cleanup_large_test_repository(clean_db):
    """Clean up large test repository data after each test."""
    test_repo_name = "large-batch-test"

    yield test_repo_name

    # Clean up code_chunks, nodes, and edges for test repository
    async with clean_db.begin() as conn:
        # Delete edges
        await conn.execute(text("""
            DELETE FROM edges
            WHERE source_node_id IN (
                SELECT node_id FROM nodes WHERE properties->>'repository' = :repository
            )
            OR target_node_id IN (
                SELECT node_id FROM nodes WHERE properties->>'repository' = :repository
            )
        """), {"repository": test_repo_name})

        # Delete nodes
        await conn.execute(text("""
            DELETE FROM nodes
            WHERE properties->>'repository' = :repository
        """), {"repository": test_repo_name})

        # Delete chunks
        await conn.execute(text("""
            DELETE FROM code_chunks
            WHERE repository = :repository
        """), {"repository": test_repo_name})


@pytest.mark.anyio
class TestLargeBatchUpload:
    """
    Integration tests for large batch uploads.

    EXPECTED BEHAVIOR:
    - Test should complete within reasonable time (< 2 minutes for 50 files)
    - Progress should update incrementally (not stuck at 0%)
    - All files should be processed (no freezes or hangs)
    - Memory should stay within limits (< 500MB per upload)
    """

    async def test_large_batch_upload_with_embeddings(
        self,
        test_client,
        cleanup_tracker,
        cleanup_large_test_repository,
        clean_db
    ):
        """
        Test upload of 50 files with embeddings enabled.

        REPRODUCES: CV upload freeze issue (401 files stuck at 0%)

        This test should FAIL initially with timeout or 0% stuck issue,
        then PASS after implementing batch processing fixes.
        """
        # Generate 50 Python files
        files = []
        for i in range(50):
            files.append({
                "path": f"module_{i:03d}.py",
                "content": f'''"""Module {i} - Test code for batch upload."""

def function_{i}(x, y):
    """Function {i} that does computation."""
    result = x + y + {i}
    return result

class Class_{i}:
    """Class {i} for testing."""

    def __init__(self):
        self.value = {i}

    def method_{i}(self, param):
        """Method {i}."""
        return param * self.value
''',
                "language": "python"
            })

        payload = {
            "repository": cleanup_large_test_repository,
            "files": files,
            "extract_metadata": True,
            "generate_embeddings": True,  # CRITICAL: Embeddings enabled (causes freeze)
            "build_graph": False  # Graph disabled to isolate embedding issue
        }

        # Start upload
        response = await test_client.post("/ui/code/upload/process", json=payload)
        assert response.status_code == 200

        result = response.json()
        upload_id = result["upload_id"]

        # Monitor progress with timeout protection
        max_wait = 120  # 2 minutes max (should be enough for 50 files)
        start_time = time.time()
        status = None
        last_indexed = 0
        progress_updates = []

        while time.time() - start_time < max_wait:
            status_response = await test_client.get(f"/ui/code/upload/status/{upload_id}")
            assert status_response.status_code == 200

            status = status_response.json()
            indexed_files = status["counters"]["indexed_files"]

            # Track progress updates
            if indexed_files > last_indexed:
                progress_updates.append({
                    "time": time.time() - start_time,
                    "indexed": indexed_files,
                    "percentage": status["percentage"]
                })
                last_indexed = indexed_files

            if status["status"] in ["completed", "partial", "error"]:
                break

            await asyncio.sleep(1)  # Poll every second

        # Verify completion
        elapsed = time.time() - start_time

        assert status is not None, "Upload status should be available"
        assert status["status"] in ["completed", "partial"], \
            f"Upload should complete, got: {status['status']}"

        # CRITICAL ASSERTIONS: These should fail initially
        assert status["counters"]["indexed_files"] > 0, \
            "REPRODUCTION: Files stuck at 0% - no files indexed"

        assert len(progress_updates) >= 4, \
            f"REPRODUCTION: Progress not updating - only {len(progress_updates)} updates (expected >= 4 for batched processing)"

        assert status["counters"]["indexed_files"] >= 40, \
            f"REPRODUCTION: Most files should be indexed, got {status['counters']['indexed_files']}/50"

        assert elapsed < 120, \
            f"REPRODUCTION: Upload took {elapsed:.1f}s (timeout threshold: 120s)"

        # Verify data in database
        async with clean_db.connect() as conn:
            # Check code_chunks
            chunks_result = await conn.execute(text("""
                SELECT COUNT(*) FROM code_chunks WHERE repository = :repository
            """), {"repository": cleanup_large_test_repository})
            chunk_count = chunks_result.scalar()

            # Should have at least 100 chunks (50 files * 2 chunks/file avg)
            assert chunk_count >= 100, \
                f"Expected at least 100 chunks, got {chunk_count}"

        print(f"\n✅ Large batch upload completed in {elapsed:.1f}s")
        print(f"   - Files indexed: {status['counters']['indexed_files']}/50")
        print(f"   - Chunks created: {status['counters']['indexed_chunks']}")
        print(f"   - Progress updates: {len(progress_updates)}")
        print(f"   - Throughput: {status['counters']['indexed_files']/elapsed:.2f} files/sec")


    async def test_very_large_batch_upload(
        self,
        test_client,
        cleanup_tracker,
        cleanup_large_test_repository,
        clean_db
    ):
        """
        Test upload of 100 files with embeddings and graph enabled.

        REPRODUCES: Full production scenario like CV upload (401 files)

        This test simulates the exact scenario that freezes in production.
        """
        # Generate 100 files (smaller scale than 401 but enough to reproduce issue)
        files = []
        for i in range(100):
            files.append({
                "path": f"file_{i:03d}.py",
                "content": f'def func_{i}(): return {i}\n',
                "language": "python"
            })

        payload = {
            "repository": cleanup_large_test_repository,
            "files": files,
            "extract_metadata": True,
            "generate_embeddings": True,  # Embeddings enabled
            "build_graph": True  # Graph enabled (full pipeline)
        }

        # Start upload
        response = await test_client.post("/ui/code/upload/process", json=payload)
        assert response.status_code == 200

        upload_id = response.json()["upload_id"]

        # Monitor with extended timeout
        max_wait = 300  # 5 minutes for 100 files with full processing
        start_time = time.time()
        status = None

        while time.time() - start_time < max_wait:
            status_response = await test_client.get(f"/ui/code/upload/status/{upload_id}")
            status = status_response.json()

            if status["status"] in ["completed", "partial", "error"]:
                break

            await asyncio.sleep(2)

        # Verify completion
        assert status is not None
        assert status["status"] in ["completed", "partial"]
        assert status["counters"]["indexed_files"] >= 80, \
            f"Most files should be indexed (100 files), got {status['counters']['indexed_files']}"


    async def test_concurrent_uploads_no_interference(
        self,
        test_client,
        cleanup_tracker,
        clean_db
    ):
        """
        Test that multiple concurrent uploads don't interfere with each other.

        REPRODUCES: Connection pool exhaustion and session conflicts
        """
        # Create 3 concurrent uploads
        upload_tasks = []

        for batch_id in range(3):
            files = [{
                "path": f"batch{batch_id}_file{i}.py",
                "content": f"def func(): return {i}",
                "language": "python"
            } for i in range(10)]

            payload = {
                "repository": f"concurrent-test-{batch_id}",
                "files": files,
                "extract_metadata": True,
                "generate_embeddings": False,
                "build_graph": False
            }

            async def upload_and_wait(p):
                resp = await test_client.post("/ui/code/upload/process", json=p)
                assert resp.status_code == 200
                upload_id = resp.json()["upload_id"]

                # Wait for completion
                for _ in range(30):  # 30 seconds max
                    status_resp = await test_client.get(f"/ui/code/upload/status/{upload_id}")
                    status = status_resp.json()
                    if status["status"] in ["completed", "partial", "error"]:
                        return status
                    await asyncio.sleep(1)
                return status

            upload_tasks.append(upload_and_wait(payload))

        # Run all uploads concurrently
        results = await asyncio.gather(*upload_tasks)

        # Verify all completed successfully
        for i, result in enumerate(results):
            assert result["status"] in ["completed", "partial"], \
                f"Upload {i} failed with status: {result['status']}"
            assert result["counters"]["indexed_files"] == 10, \
                f"Upload {i} should index all 10 files"

        # Cleanup
        for batch_id in range(3):
            async with clean_db.begin() as conn:
                await conn.execute(text("""
                    DELETE FROM code_chunks WHERE repository = :repository
                """), {"repository": f"concurrent-test-{batch_id}"})


    async def test_upload_progress_not_stuck_at_zero(
        self,
        test_client,
        cleanup_tracker,
        cleanup_large_test_repository
    ):
        """
        Test that progress tracker doesn't get stuck at 0%.

        REPRODUCES: The exact bug reported - progress stuck at 0%

        This test monitors progress every 0.5s and ensures it updates.
        """
        # Create 20 files
        files = [{
            "path": f"progress_test_{i}.py",
            "content": f"def func_{i}(): pass",
            "language": "python"
        } for i in range(20)]

        payload = {
            "repository": cleanup_large_test_repository,
            "files": files,
            "extract_metadata": True,
            "generate_embeddings": True,
            "build_graph": False
        }

        response = await test_client.post("/ui/code/upload/process", json=payload)
        upload_id = response.json()["upload_id"]

        # Monitor progress frequently
        progress_snapshots = []
        max_wait = 60
        start_time = time.time()

        while time.time() - start_time < max_wait:
            status_response = await test_client.get(f"/ui/code/upload/status/{upload_id}")
            status = status_response.json()

            progress_snapshots.append({
                "time": time.time() - start_time,
                "percentage": status["percentage"],
                "indexed": status["counters"]["indexed_files"],
                "step": status["current_step"]
            })

            if status["status"] in ["completed", "partial", "error"]:
                break

            await asyncio.sleep(0.5)

        # CRITICAL: Verify progress actually moved
        percentages = [s["percentage"] for s in progress_snapshots]

        assert len(progress_snapshots) >= 5, \
            "Should have multiple progress snapshots"

        assert max(percentages) > 0, \
            "REPRODUCTION: Progress stuck at 0% - percentages never increased"

        assert percentages[-1] == 100, \
            f"Final percentage should be 100%, got {percentages[-1]}"

        # Verify progress was incremental (not just 0% then suddenly 100%)
        non_zero_updates = [p for p in percentages if 0 < p < 100]
        assert len(non_zero_updates) > 0, \
            "Progress should update incrementally, not jump from 0% to 100%"

        print(f"\n✅ Progress tracking verified:")
        print(f"   - Total snapshots: {len(progress_snapshots)}")
        print(f"   - Percentage range: {min(percentages)}% → {max(percentages)}%")
        print(f"   - Intermediate updates: {len(non_zero_updates)}")
