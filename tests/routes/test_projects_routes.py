"""
Tests for Projects Management API endpoints.
"""
import pytest
from datetime import datetime, timezone
from sqlalchemy import text


@pytest.mark.anyio
async def test_list_projects_returns_all_repositories(test_client):
    """Test GET /api/v1/projects returns list of indexed repositories."""
    # Insert test data - need to add some code_chunks with repository field
    async with test_client._transport.app.state.db_engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO code_chunks (file_path, language, chunk_type, source_code, repository, metadata)
                VALUES
                    ('/test/repo1/file1.py', 'python', 'function', 'def test(): pass', 'test_repo', '{"loc": 100}'),
                    ('/test/repo1/file2.py', 'python', 'class', 'class Test: pass', 'test_repo', '{"loc": 50}'),
                    ('/test/repo2/file1.ts', 'typescript', 'function', 'function test() {}', 'other_repo', '{"loc": 75}')
            """)
        )

    response = await test_client.get("/api/v1/projects")

    assert response.status_code == 200
    data = response.json()

    assert "projects" in data
    assert isinstance(data["projects"], list)
    assert len(data["projects"]) > 0

    # Check first project structure
    project = data["projects"][0]
    assert "repository" in project
    assert "files_count" in project
    assert "chunks_count" in project
    assert "languages" in project
    assert "last_indexed" in project
    assert "status" in project
