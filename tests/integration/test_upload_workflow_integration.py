"""
Integration tests for end-to-end upload workflow (EPIC-09).

Tests the complete file upload and indexing pipeline from API request
to database storage, including:
- Security validation (size, path safety, rate limiting)
- File filtering (lock files, binary files, size limits)
- Background processing with progress tracking
- 7-stage pipeline execution (parse → chunk → metadata → embed → store → graph → index)
- Error handling and partial completion scenarios
"""

import pytest
import pytest_asyncio
import asyncio
import uuid
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
async def cleanup_test_repository(clean_db):
    """Clean up test repository data after each test."""
    test_repo_name = "integration-test-repo"

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
class TestUploadWorkflowIntegration:
    """Integration tests for the complete upload workflow."""

    async def test_single_file_upload_success(
        self,
        test_client,
        cleanup_tracker,
        cleanup_test_repository,
        clean_db
    ):
        """Test successful upload and indexing of a single Python file."""
        # Prepare upload payload
        payload = {
            "repository": cleanup_test_repository,
            "files": [
                {
                    "path": "test_module.py",
                    "content": '''def hello_world():
    """Say hello."""
    return "Hello, World!"

class Calculator:
    """A simple calculator."""

    def add(self, a, b):
        """Add two numbers."""
        return a + b
''',
                    "language": "python"
                }
            ],
            "extract_metadata": True,
            "generate_embeddings": False,  # Disable for faster test
            "build_graph": False  # Disable for faster test
        }

        # Send upload request
        response = await test_client.post("/ui/code/upload/process", json=payload)

        # Verify response
        assert response.status_code == 200
        result = response.json()

        assert result["status"] == "processing"
        assert "upload_id" in result
        assert result["repository"] == cleanup_test_repository
        assert result["total_files"] == 1

        upload_id = result["upload_id"]

        # Poll for completion (max 10 seconds)
        max_wait = 10
        start_time = time.time()
        status = None

        while time.time() - start_time < max_wait:
            status_response = await test_client.get(f"/ui/code/upload/status/{upload_id}")
            assert status_response.status_code == 200

            status = status_response.json()

            if status["status"] in ["completed", "partial", "error"]:
                break

            await asyncio.sleep(0.2)

        # Verify completion
        assert status is not None
        assert status["status"] in ["completed", "partial"]
        assert status["counters"]["indexed_files"] == 1
        assert status["counters"]["indexed_chunks"] >= 3  # function + class + method
        assert status["counters"]["failed_files"] == 0

        # Verify data in database
        async with clean_db.connect() as conn:
            # Check code_chunks
            chunks_result = await conn.execute(text("""
                SELECT COUNT(*) FROM code_chunks WHERE repository = :repository
            """), {"repository": cleanup_test_repository})
            chunk_count = chunks_result.scalar()

            assert chunk_count >= 3  # Should have at least 3 chunks


    async def test_multiple_files_batch_processing(
        self,
        test_client,
        cleanup_tracker,
        cleanup_test_repository,
        clean_db
    ):
        """Test batch processing of multiple files."""
        # Create 5 files
        files = []
        for i in range(5):
            files.append({
                "path": f"module_{i}.py",
                "content": f'''def func_{i}():
    """Function {i}."""
    return {i}
''',
                "language": "python"
            })

        payload = {
            "repository": cleanup_test_repository,
            "files": files,
            "extract_metadata": True,
            "generate_embeddings": False,
            "build_graph": False
        }

        # Send upload request
        response = await test_client.post("/ui/code/upload/process", json=payload)
        assert response.status_code == 200

        result = response.json()
        upload_id = result["upload_id"]

        # Wait for completion
        max_wait = 15
        start_time = time.time()
        status = None

        while time.time() - start_time < max_wait:
            status_response = await test_client.get(f"/ui/code/upload/status/{upload_id}")
            status = status_response.json()

            if status["status"] in ["completed", "partial", "error"]:
                break

            await asyncio.sleep(0.2)

        # Verify all files were indexed
        assert status["status"] in ["completed", "partial"]
        assert status["counters"]["indexed_files"] == 5
        assert status["counters"]["indexed_chunks"] >= 5  # At least 1 function per file
        assert status["counters"]["failed_files"] == 0


    async def test_file_validation_lock_files_filtered(
        self,
        test_client,
        cleanup_tracker,
        cleanup_test_repository
    ):
        """Test that lock files are automatically filtered out."""
        payload = {
            "repository": cleanup_test_repository,
            "files": [
                {
                    "path": "package-lock.json",
                    "content": '{"lockfileVersion": 2}',
                    "language": "json"
                },
                {
                    "path": "valid_module.py",
                    "content": 'def test(): pass',
                    "language": "python"
                },
                {
                    "path": "yarn.lock",
                    "content": "# yarn lockfile",
                    "language": "text"
                }
            ],
            "extract_metadata": False,
            "generate_embeddings": False,
            "build_graph": False
        }

        response = await test_client.post("/ui/code/upload/process", json=payload)
        assert response.status_code == 200

        upload_id = response.json()["upload_id"]

        # Wait for completion
        await asyncio.sleep(2)

        status_response = await test_client.get(f"/ui/code/upload/status/{upload_id}")
        status = status_response.json()

        # Should have indexed 1 file, failed 2 lock files
        assert status["counters"]["indexed_files"] == 1
        assert status["counters"]["failed_files"] == 2

        # Check errors contain lock file mentions
        error_files = [e["file"] for e in status.get("errors", [])]
        assert "package-lock.json" in error_files or "yarn.lock" in error_files


    async def test_file_size_limit_enforcement(
        self,
        test_client,
        cleanup_tracker,
        cleanup_test_repository
    ):
        """Test that files exceeding size limit are rejected."""
        # Create a file larger than 500KB
        large_content = "# " + ("x" * (600 * 1024))  # 600KB

        payload = {
            "repository": cleanup_test_repository,
            "files": [
                {
                    "path": "large_file.py",
                    "content": large_content,
                    "language": "python"
                },
                {
                    "path": "small_file.py",
                    "content": "def test(): pass",
                    "language": "python"
                }
            ],
            "extract_metadata": False,
            "generate_embeddings": False,
            "build_graph": False
        }

        response = await test_client.post("/ui/code/upload/process", json=payload)
        assert response.status_code == 200

        upload_id = response.json()["upload_id"]

        # Wait for completion
        await asyncio.sleep(2)

        status_response = await test_client.get(f"/ui/code/upload/status/{upload_id}")
        status = status_response.json()

        # Large file should be rejected, small file should succeed
        assert status["counters"]["indexed_files"] == 1
        assert status["counters"]["failed_files"] == 1

        # Check error message mentions size
        errors = status.get("errors", [])
        assert len(errors) >= 1
        assert any("too large" in e["error"].lower() for e in errors)


    async def test_security_path_traversal_blocked(
        self,
        test_client,
        cleanup_tracker,
        cleanup_test_repository
    ):
        """Test that path traversal attacks are blocked."""
        payload = {
            "repository": cleanup_test_repository,
            "files": [
                {
                    "path": "../../etc/passwd",
                    "content": "malicious content",
                    "language": "text"
                },
                {
                    "path": "../sensitive.py",
                    "content": "def hack(): pass",
                    "language": "python"
                },
                {
                    "path": "safe/file.py",
                    "content": "def safe(): pass",
                    "language": "python"
                }
            ],
            "extract_metadata": False,
            "generate_embeddings": False,
            "build_graph": False
        }

        response = await test_client.post("/ui/code/upload/process", json=payload)
        assert response.status_code == 200

        upload_id = response.json()["upload_id"]

        # Wait for completion
        await asyncio.sleep(2)

        status_response = await test_client.get(f"/ui/code/upload/status/{upload_id}")
        status = status_response.json()

        # Only safe file should be indexed
        assert status["counters"]["indexed_files"] == 1
        assert status["counters"]["failed_files"] == 2

        # Check errors mention path traversal
        errors = status.get("errors", [])
        assert any("traversal" in e["error"].lower() for e in errors)


    async def test_security_invalid_repository_name(
        self,
        test_client,
        cleanup_tracker
    ):
        """Test that invalid repository names are rejected."""
        # Test special characters
        payload = {
            "repository": "test@repo!",
            "files": [{
                "path": "test.py",
                "content": "def test(): pass",
                "language": "python"
            }]
        }

        response = await test_client.post("/ui/code/upload/process", json=payload)
        assert response.status_code == 400
        assert "invalid repository name" in response.json()["detail"].lower()

        # Test path traversal in repository name
        payload["repository"] = "../../../malicious"
        response = await test_client.post("/ui/code/upload/process", json=payload)
        assert response.status_code == 400


    async def test_security_payload_too_large(
        self,
        test_client,
        cleanup_tracker
    ):
        """Test that payloads exceeding max size are rejected."""
        # Note: We can't easily test this without actually sending 50MB+ payload
        # This is a placeholder for manual testing
        # In production, this is handled by content-length header check
        pass


    async def test_progress_tracking_updates(
        self,
        test_client,
        cleanup_tracker,
        cleanup_test_repository
    ):
        """Test that progress tracking updates throughout processing."""
        payload = {
            "repository": cleanup_test_repository,
            "files": [
                {"path": f"file_{i}.py", "content": f"def func_{i}(): pass", "language": "python"}
                for i in range(3)
            ],
            "extract_metadata": False,
            "generate_embeddings": False,
            "build_graph": False
        }

        response = await test_client.post("/ui/code/upload/process", json=payload)
        upload_id = response.json()["upload_id"]

        # Collect status updates
        statuses = []
        max_wait = 10
        start_time = time.time()

        while time.time() - start_time < max_wait:
            status_response = await test_client.get(f"/ui/code/upload/status/{upload_id}")
            status = status_response.json()
            statuses.append(status)

            if status["status"] in ["completed", "partial", "error"]:
                break

            await asyncio.sleep(0.2)

        # Verify we got multiple status updates
        assert len(statuses) >= 2

        # Verify percentage increased over time
        percentages = [s["percentage"] for s in statuses]
        assert percentages[0] <= percentages[-1]

        # Final status should be complete
        final_status = statuses[-1]
        assert final_status["status"] in ["completed", "partial"]
        assert final_status["percentage"] == 100


    async def test_error_handling_partial_completion(
        self,
        test_client,
        cleanup_tracker,
        cleanup_test_repository
    ):
        """Test partial completion when some files fail."""
        payload = {
            "repository": cleanup_test_repository,
            "files": [
                # Valid file
                {
                    "path": "valid.py",
                    "content": "def valid(): pass",
                    "language": "python"
                },
                # Lock file (should be filtered)
                {
                    "path": "package-lock.json",
                    "content": "{}",
                    "language": "json"
                },
                # Another valid file
                {
                    "path": "valid2.py",
                    "content": "def valid2(): pass",
                    "language": "python"
                }
            ],
            "extract_metadata": False,
            "generate_embeddings": False,
            "build_graph": False
        }

        response = await test_client.post("/ui/code/upload/process", json=payload)
        upload_id = response.json()["upload_id"]

        # Wait for completion
        await asyncio.sleep(2)

        status_response = await test_client.get(f"/ui/code/upload/status/{upload_id}")
        status = status_response.json()

        # Should have partial completion
        assert status["status"] == "partial"
        assert status["counters"]["indexed_files"] == 2
        assert status["counters"]["failed_files"] == 1
        assert len(status["errors"]) >= 1


    async def test_progress_tracker_session_cleanup(
        self,
        test_client,
        cleanup_tracker,
        cleanup_test_repository
    ):
        """Test that upload sessions are created and can be retrieved."""
        payload = {
            "repository": cleanup_test_repository,
            "files": [{
                "path": "test.py",
                "content": "def test(): pass",
                "language": "python"
            }],
            "extract_metadata": False,
            "generate_embeddings": False,
            "build_graph": False
        }

        response = await test_client.post("/ui/code/upload/process", json=payload)
        upload_id = response.json()["upload_id"]

        # Verify session exists
        tracker = get_tracker()
        session = await tracker.get_session(upload_id)
        assert session is not None
        assert session.upload_id == upload_id
        assert session.repository == cleanup_test_repository

        # Wait for completion
        await asyncio.sleep(2)

        # Session should still exist after completion
        session = await tracker.get_session(upload_id)
        assert session is not None
        assert session.status in ["completed", "partial"]


    async def test_upload_status_not_found(
        self,
        test_client
    ):
        """Test status endpoint returns not_found for invalid upload_id."""
        fake_upload_id = str(uuid.uuid4())

        response = await test_client.get(f"/ui/code/upload/status/{fake_upload_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "not_found"
        assert "error" in data


    async def test_empty_files_array_rejected(
        self,
        test_client,
        cleanup_tracker
    ):
        """Test that empty files array is rejected."""
        payload = {
            "repository": "test-repo",
            "files": []
        }

        response = await test_client.post("/ui/code/upload/process", json=payload)
        assert response.status_code == 400
        # The error message says "No files provided" or contains "empty"
        detail = response.json()["detail"].lower()
        assert "empty" in detail or "no files" in detail


    async def test_missing_repository_rejected(
        self,
        test_client,
        cleanup_tracker
    ):
        """Test that missing repository name is rejected."""
        payload = {
            "files": [{
                "path": "test.py",
                "content": "def test(): pass"
            }]
        }

        response = await test_client.post("/ui/code/upload/process", json=payload)
        assert response.status_code == 400
        assert "repository" in response.json()["detail"].lower()
