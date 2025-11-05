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


@pytest.mark.anyio
async def test_get_active_project_returns_current(test_client):
    """Test GET /api/v1/projects/active returns currently active project."""
    response = await test_client.get("/api/v1/projects/active")

    assert response.status_code == 200
    data = response.json()

    assert "repository" in data
    assert isinstance(data["repository"], str)


@pytest.mark.anyio
async def test_set_active_project_changes_context(test_client):
    """Test POST /api/v1/projects/active switches active project."""
    # First insert test data
    async with test_client._transport.app.state.db_engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO code_chunks (file_path, language, chunk_type, source_code, repository, metadata)
                VALUES ('/test/file.py', 'python', 'function', 'def test(): pass', 'test_project', '{}')
            """)
        )

    response = await test_client.post(
        "/api/v1/projects/active",
        json={"repository": "test_project"}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["repository"] == "test_project"
    assert "message" in data


@pytest.mark.anyio
async def test_reindex_project_triggers_indexing(test_client):
    """Test POST /api/v1/projects/{repository}/reindex triggers reindexing."""
    # First insert test data for code_test repository
    async with test_client._transport.app.state.db_engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO code_chunks (file_path, language, chunk_type, source_code, repository, metadata)
                VALUES ('/test/code_test/src/file.py', 'python', 'function', 'def test(): pass', 'code_test', '{}')
            """)
        )

    response = await test_client.post("/api/v1/projects/code_test/reindex")

    assert response.status_code == 200
    data = response.json()

    assert "repository" in data
    assert "status" in data
    assert data["status"] == "reindexing"


@pytest.mark.anyio
async def test_delete_project_removes_all_data(test_client):
    """Test DELETE /api/v1/projects/{repository} removes all project data."""
    # Create a separate 'test_delete' project to avoid affecting other tests
    async with test_client._transport.app.state.db_engine.begin() as conn:
        # Insert code chunks for test_delete project
        await conn.execute(
            text("""
                INSERT INTO code_chunks (file_path, language, chunk_type, source_code, repository, metadata)
                VALUES
                    ('/test/test_delete/file1.py', 'python', 'function', 'def foo(): pass', 'test_delete', '{"loc": 10}'),
                    ('/test/test_delete/file2.py', 'python', 'class', 'class Bar: pass', 'test_delete', '{"loc": 20}')
            """)
        )

        # Insert nodes for test_delete project (using UUIDs)
        await conn.execute(
            text("""
                INSERT INTO nodes (node_id, node_type, label, properties)
                VALUES
                    ('00000000-0000-0000-0000-000000000001'::uuid, 'Module', 'test_module', '{"repository": "test_delete", "file_path": "/test/test_delete/file1.py"}'),
                    ('00000000-0000-0000-0000-000000000002'::uuid, 'Module', 'test_class', '{"repository": "test_delete", "file_path": "/test/test_delete/file2.py"}')
            """)
        )

    # Delete the project
    response = await test_client.delete("/api/v1/projects/test_delete")

    assert response.status_code == 200
    data = response.json()

    assert "repository" in data
    assert data["repository"] == "test_delete"
    assert "deleted_chunks" in data
    assert "deleted_nodes" in data
    assert data["deleted_chunks"] == 2
    assert data["deleted_nodes"] == 2
