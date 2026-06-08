"""
Integration tests for GET /api/v1/memories/export endpoint.

Tests the JSON export of memories with:
- All memories export (no filter)
- Project-scoped export
- Include deleted option
- Response structure validation
- Content-Disposition header for download
"""
import pytest
import uuid
from sqlalchemy import text


@pytest.mark.anyio
async def test_export_memories_empty_database(test_client):
    """GET /api/v1/memories/export on empty DB returns envelope with 0 memories."""
    response = await test_client.get("/api/v1/memories/export")

    assert response.status_code == 200
    # Should be downloadable JSON
    assert "attachment" in response.headers.get("content-disposition", "")
    data = response.json()
    assert data["export_format"] == "mnemolite-memories-v1"
    assert data["count"] == 0
    assert data["memories"] == []
    assert "exported_at" in data
    assert data["filters"]["include_deleted"] is False


@pytest.mark.anyio
async def test_export_memories_returns_all(clean_db, test_client):
    """GET /api/v1/memories/export returns all non-deleted memories."""
    id1 = str(uuid.uuid4())
    id2 = str(uuid.uuid4())
    async with clean_db.begin() as conn:
        await conn.execute(text("""
            INSERT INTO memories (id, title, content, memory_type, tags, created_at, author)
            VALUES
                ('{id1}'::uuid, 'Export Note 1', 'Content 1', 'note', ARRAY['test'], NOW(), 'TestAuthor'),
                ('{id2}'::uuid, 'Export Note 2', 'Content 2', 'decision', ARRAY['test'], NOW(), 'TestAuthor')
        """.format(id1=id1, id2=id2)))

    response = await test_client.get("/api/v1/memories/export")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert len(data["memories"]) == 2


@pytest.mark.anyio
async def test_export_memories_excludes_deleted(clean_db, test_client):
    """GET /api/v1/memories/export excludes soft-deleted memories by default."""
    id1 = str(uuid.uuid4())
    id2 = str(uuid.uuid4())
    async with clean_db.begin() as conn:
        await conn.execute(text("""
            INSERT INTO memories (id, title, content, memory_type, tags, created_at, deleted_at)
            VALUES
                ('{id1}'::uuid, 'Active Memory', 'Content active', 'note', ARRAY['test'], NOW(), NULL),
                ('{id2}'::uuid, 'Deleted Memory', 'Content deleted', 'note', ARRAY['test'], NOW(), NOW())
        """.format(id1=id1, id2=id2)))

    # Default: exclude deleted
    response = await test_client.get("/api/v1/memories/export")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["memories"][0]["title"] == "Active Memory"

    # With include_deleted=True
    response = await test_client.get("/api/v1/memories/export?include_deleted=true")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2


@pytest.mark.anyio
async def test_export_memories_project_scoped(clean_db, test_client):
    """GET /api/v1/memories/export?project_id=... scopes to a project."""
    # Use UUID-suffixed names to guarantee uniqueness across test runs
    project_id = str(uuid.uuid4())
    other_project_id = str(uuid.uuid4())
    project_name = f"export-test-{project_id[:8]}"
    other_name = f"other-export-{other_project_id[:8]}"

    async with clean_db.begin() as conn:
        # Create projects for FK
        await conn.execute(text("""
            INSERT INTO projects (id, name, display_name) VALUES
                (:pid, :pname, 'Export Test'),
                (:oid, :oname, 'Other Project')
        """), {"pid": project_id, "oid": other_project_id, "pname": project_name, "oname": other_name})

        # Create memories in both projects
        id1 = str(uuid.uuid4())
        id2 = str(uuid.uuid4())
        await conn.execute(text("""
            INSERT INTO memories (id, title, content, memory_type, tags, created_at, project_id)
            VALUES
                ('{id1}'::uuid, 'Project Memory', 'Content A', 'note', ARRAY['test'], NOW(), '{pid}'::uuid),
                ('{id2}'::uuid, 'Other Memory', 'Content B', 'note', ARRAY['test'], NOW(), '{oid}'::uuid)
        """.format(id1=id1, id2=id2, pid=project_id, oid=other_project_id)))

    # Export scoped to first project
    response = await test_client.get(f"/api/v1/memories/export?project_id={project_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["memories"][0]["title"] == "Project Memory"
    assert data["filters"]["project_id"] == project_id


@pytest.mark.anyio
async def test_export_memories_structure(clean_db, test_client):
    """GET /api/v1/memories/export returns correct structure for each memory."""
    memory_id = str(uuid.uuid4())
    async with clean_db.begin() as conn:
        await conn.execute(text("""
            INSERT INTO memories (id, title, content, memory_type, tags, created_at, author)
            VALUES (
                '{mid}'::uuid,
                'Structure Test',
                'Full content here',
                'decision',
                ARRAY['test', 'export'],
                NOW(),
                'TestBot'
            )
        """.format(mid=memory_id)))

    response = await test_client.get("/api/v1/memories/export")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 1

    # Find our memory
    mem = next(m for m in data["memories"] if m["title"] == "Structure Test")
    assert mem["id"] == memory_id
    assert mem["content"] == "Full content here"
    assert mem["memory_type"] == "decision"
    assert "test" in mem["tags"]
    assert "export" in mem["tags"]
    assert mem["author"] == "TestBot"
    assert "embedding" not in mem  # Embedding excluded
    assert "created_at" in mem
    assert "updated_at" in mem
    assert "embedding_model" in mem
    assert "entities" in mem
    assert "concepts" in mem
    assert "auto_tags" in mem


@pytest.mark.anyio
async def test_export_memories_content_disposition(test_client):
    """GET /api/v1/memories/export has Content-Disposition: attachment."""
    response = await test_client.get("/api/v1/memories/export")
    assert response.status_code == 200

    cd = response.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert ".json" in cd

    # With project_id, filename includes project prefix
    response = await test_client.get("/api/v1/memories/export?project_id=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    cd = response.headers.get("content-disposition", "")
    assert "aaaaaaaa" in cd


@pytest.mark.anyio
async def test_export_memories_ordering(clean_db, test_client):
    """GET /api/v1/memories/export returns memories ordered by created_at ASC."""
    id1 = str(uuid.uuid4())
    id2 = str(uuid.uuid4())
    async with clean_db.begin() as conn:
        await conn.execute(text("""
            INSERT INTO memories (id, title, content, memory_type, tags, created_at)
            VALUES
                ('{id1}'::uuid, 'First', 'Older', 'note', ARRAY['test'], NOW() - INTERVAL '2 days'),
                ('{id2}'::uuid, 'Second', 'Newer', 'note', ARRAY['test'], NOW())
        """.format(id1=id1, id2=id2)))

    response = await test_client.get("/api/v1/memories/export")
    assert response.status_code == 200
    data = response.json()
    titles = [m["title"] for m in data["memories"]]
    assert titles.index("First") < titles.index("Second")
