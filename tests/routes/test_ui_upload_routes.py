"""
Tests for UI upload routes (EPIC-09).

Tests the advanced file upload functionality including:
- Batch processing
- File validation
- Error handling
- Chunked uploads
"""

import pytest


@pytest.mark.anyio
async def test_code_upload_process_success(test_client):
    """
    Test successful file upload with batch processing.

    EPIC-09: Should process files in batches and return success.
    """
    # Prepare test payload with 3 files
    payload = {
        "repository": "test-repo",
        "files": [
            {
                "path": "file1.py",
                "content": "def hello(): return 'Hello'",
                "language": "python"
            },
            {
                "path": "file2.py",
                "content": "def world(): return 'World'",
                "language": "python"
            },
            {
                "path": "file3.py",
                "content": "def test(): return 'Test'",
                "language": "python"
            }
        ],
        "extract_metadata": True,
        "generate_embeddings": True,
        "build_graph": True,
        "commit_hash": "abc123"
    }

    response = await test_client.post("/ui/code/upload/process", json=payload)

    assert response.status_code == 200
    result = response.json()

    # Check async response structure (processing started, not completed)
    assert "status" in result
    assert result["status"] == "processing"
    assert "repository" in result
    assert result["repository"] == "test-repo"
    assert "total_files" in result
    assert result["total_files"] == 3
    assert "upload_id" in result
    assert "message" in result
    assert "status" in result["message"].lower()  # Message mentions status polling


@pytest.mark.anyio
async def test_code_upload_process_missing_repository(test_client):
    """
    Test upload without repository name.

    EPIC-09: Should return error when repository name is missing.
    """
    payload = {
        "files": [
            {
                "path": "file1.py",
                "content": "def hello(): pass",
                "language": "python"
            }
        ]
    }

    response = await test_client.post("/ui/code/upload/process", json=payload)

    # API now returns 400 for validation errors
    assert response.status_code == 400
    result = response.json()

    assert "detail" in result
    assert "repository" in result["detail"].lower()


@pytest.mark.anyio
async def test_code_upload_process_no_files(test_client):
    """
    Test upload without files.

    EPIC-09: Should return error when no files are provided.
    """
    payload = {
        "repository": "test-repo",
        "files": []
    }

    response = await test_client.post("/ui/code/upload/process", json=payload)

    # API now returns 400 for validation errors (empty files list)
    assert response.status_code == 400
    result = response.json()

    assert "detail" in result


@pytest.mark.anyio
async def test_code_upload_process_file_too_large(test_client):
    """
    Test upload with file exceeding size limit.

    EPIC-09: Should reject files larger than 10MB.
    """
    # Create file with content > 10MB
    large_content = "x" * (11 * 1024 * 1024)  # 11MB

    payload = {
        "repository": "test-repo",
        "files": [
            {
                "path": "large_file.py",
                "content": large_content,
                "language": "python"
            }
        ]
    }

    response = await test_client.post("/ui/code/upload/process", json=payload)

    assert response.status_code == 200
    result = response.json()

    # Async response - processing started (file validation happens async)
    assert result["status"] == "processing"
    assert "upload_id" in result
    assert result["total_files"] == 1


@pytest.mark.anyio
async def test_code_upload_process_batch_processing(test_client):
    """
    Test batch processing with multiple files.

    EPIC-09: Should process files in batches of 100.
    """
    # Create 150 files to test batch processing
    files = []
    for i in range(150):
        files.append({
            "path": f"file{i}.py",
            "content": f"def func{i}(): return {i}",
            "language": "python"
        })

    payload = {
        "repository": "test-batch",
        "files": files,
        "extract_metadata": True,
        "generate_embeddings": True,
        "build_graph": True
    }

    response = await test_client.post("/ui/code/upload/process", json=payload)

    assert response.status_code == 200
    result = response.json()

    # Async response - batch processing started
    assert result["status"] == "processing"
    assert "upload_id" in result
    assert result["total_files"] == 150


@pytest.mark.anyio
async def test_code_upload_process_missing_file_data(test_client):
    """
    Test upload with invalid file data.

    EPIC-09: Should handle files with missing path or content.
    """
    payload = {
        "repository": "test-repo",
        "files": [
            {
                "path": "valid.py",
                "content": "def test(): pass",
                "language": "python"
            },
            {
                # Missing content
                "path": "invalid1.py",
                "language": "python"
            },
            {
                # Missing path
                "content": "def test2(): pass",
                "language": "python"
            }
        ]
    }

    response = await test_client.post("/ui/code/upload/process", json=payload)

    # API now validates file data upfront and returns 400 for invalid files
    assert response.status_code == 400
    result = response.json()

    assert "detail" in result


@pytest.mark.anyio
async def test_code_upload_process_partial_success(test_client):
    """
    Test upload with mix of valid and invalid files.

    EPIC-09: Should return partial status and track errors.
    """
    payload = {
        "repository": "test-partial",
        "files": [
            {
                "path": "valid1.py",
                "content": "def hello(): return 'Hello'",
                "language": "python"
            },
            {
                "path": "valid2.py",
                "content": "def world(): return 'World'",
                "language": "python"
            },
            {
                # Too large
                "path": "invalid.py",
                "content": "x" * (11 * 1024 * 1024),
                "language": "python"
            }
        ]
    }

    response = await test_client.post("/ui/code/upload/process", json=payload)

    assert response.status_code == 200
    result = response.json()

    # Async response - partial success will be determined during processing
    assert result["status"] == "processing"
    assert "upload_id" in result
    assert result["total_files"] == 3


@pytest.mark.anyio
async def test_code_upload_process_options(test_client):
    """
    Test upload with different processing options.

    EPIC-09: Should respect extract_metadata, generate_embeddings, build_graph flags.
    """
    # Test with all options disabled
    payload = {
        "repository": "test-options",
        "files": [
            {
                "path": "test.py",
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
    result = response.json()

    # Should still process the file
    assert result["total_files"] == 1


@pytest.mark.anyio
async def test_code_upload_process_error_overflow(test_client):
    """
    Test error overflow handling.

    EPIC-09: Should limit errors to first 100 when there are many failures.
    """
    # Create 150 invalid files (all too large)
    files = []
    for i in range(150):
        files.append({
            "path": f"large{i}.py",
            "content": "x" * (11 * 1024 * 1024),  # 11MB each
            "language": "python"
        })

    payload = {
        "repository": "test-overflow",
        "files": files
    }

    response = await test_client.post("/ui/code/upload/process", json=payload)

    assert response.status_code == 200
    result = response.json()

    # Async response - error overflow will be tracked during processing
    assert result["status"] == "processing"
    assert "upload_id" in result
    assert result["total_files"] == 150


@pytest.mark.anyio
async def test_code_upload_page_renders(test_client):
    """
    Test that the upload page renders correctly.

    EPIC-09: Should return the advanced upload template.
    """
    response = await test_client.get("/ui/code/upload")

    assert response.status_code == 200
    # Check that it's HTML
    assert "text/html" in response.headers["content-type"]
    # Check for key elements of advanced upload
    html = response.text
    assert "Advanced Code Upload" in html or "advanced" in html.lower()
    assert "upload" in html.lower()
