# tests/routes/test_indexing_error_routes.py
import pytest
from sqlalchemy import text


@pytest.mark.anyio
async def test_get_errors_endpoint_empty_repository(test_client):
    """Test endpoint returns empty list for repository with no errors."""
    response = await test_client.get("/api/v1/indexing/batch/errors/nonexistent_repo")

    assert response.status_code == 200
    data = response.json()
    assert data["repository"] == "nonexistent_repo"
    assert data["total"] == 0
    assert data["errors"] == []


@pytest.mark.anyio
async def test_get_errors_endpoint_with_data(clean_db, test_client):
    """Test endpoint returns errors for repository."""
    test_repo = "test_api_errors"

    # Cleanup
    async with clean_db.begin() as conn:
        await conn.execute(text("DELETE FROM indexing_errors WHERE repository = :repo"), {"repo": test_repo})

    # Insert test error
    async with clean_db.begin() as conn:
        await conn.execute(text("""
            INSERT INTO indexing_errors (repository, file_path, error_type, error_message)
            VALUES (:repo, :path, :type, :msg)
        """), {
            "repo": test_repo,
            "path": "/test/file.ts",
            "type": "parsing_error",
            "msg": "Test error"
        })

    # Test endpoint
    response = await test_client.get(f"/api/v1/indexing/batch/errors/{test_repo}")

    assert response.status_code == 200
    data = response.json()
    assert data["repository"] == test_repo
    assert data["total"] == 1
    assert len(data["errors"]) == 1
    assert data["errors"][0]["file_path"] == "/test/file.ts"


@pytest.mark.anyio
async def test_get_errors_filtered_by_type(clean_db, test_client):
    """Test endpoint filters by error_type query param."""
    test_repo = "test_api_filter"

    # Cleanup
    async with clean_db.begin() as conn:
        await conn.execute(text("DELETE FROM indexing_errors WHERE repository = :repo"), {"repo": test_repo})

    # Insert 2 errors of different types
    async with clean_db.begin() as conn:
        await conn.execute(text("""
            INSERT INTO indexing_errors (repository, file_path, error_type, error_message)
            VALUES
                (:repo, '/test/file1.ts', 'parsing_error', 'Parse error'),
                (:repo, '/test/file2.ts', 'chunking_error', 'Chunk error')
        """), {"repo": test_repo})

    # Test filtered endpoint
    response = await test_client.get(f"/api/v1/indexing/batch/errors/{test_repo}?error_type=parsing_error")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["errors"][0]["error_type"] == "parsing_error"


@pytest.mark.anyio
async def test_get_errors_pagination(clean_db, test_client):
    """Test endpoint pagination with limit and offset."""
    test_repo = "test_api_pagination"

    # Cleanup
    async with clean_db.begin() as conn:
        await conn.execute(text("DELETE FROM indexing_errors WHERE repository = :repo"), {"repo": test_repo})

    # Insert 10 errors
    async with clean_db.begin() as conn:
        for i in range(10):
            await conn.execute(text("""
                INSERT INTO indexing_errors (repository, file_path, error_type, error_message)
                VALUES (:repo, :path, 'parsing_error', :msg)
            """), {
                "repo": test_repo,
                "path": f"/test/file{i}.ts",
                "msg": f"Error {i}"
            })

    # Test page 1
    response = await test_client.get(f"/api/v1/indexing/batch/errors/{test_repo}?limit=5&offset=0")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 10
    assert len(data["errors"]) == 5

    # Test page 2
    response2 = await test_client.get(f"/api/v1/indexing/batch/errors/{test_repo}?limit=5&offset=5")
    data2 = response2.json()
    assert len(data2["errors"]) == 5

    # Verify no overlap
    ids_page1 = {e["error_id"] for e in data["errors"]}
    ids_page2 = {e["error_id"] for e in data2["errors"]}
    assert len(ids_page1 & ids_page2) == 0
