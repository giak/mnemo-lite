"""Tests for Knowledge Explorer endpoints (EPIC-78).

Couvre : GET /memories/explorer/stats, GET /memories/explorer/tree,
GET /memories/{id}/related-by-tags, et la régression GET /memories/graph
(T0 : le conflit de routes avec GET /{memory_id} a été corrigé).
"""
import pytest
import uuid
from sqlalchemy import text


@pytest.mark.anyio
async def test_explorer_stats_structure(test_client, clean_db):
    """GET /explorer/stats retourne la structure attendue (vide ou peuplée)."""
    response = await test_client.get("/api/v1/memories/explorer/stats")

    assert response.status_code == 200
    data = response.json()
    assert "by_type" in data
    assert "status" in data
    assert "top_subjects" in data
    assert "timeline" in data
    assert isinstance(data["by_type"], dict)
    assert isinstance(data["top_subjects"], list)
    assert isinstance(data["timeline"], list)
    assert {"confirmed", "fact_checked", "total"} <= set(data["status"].keys())


@pytest.mark.anyio
async def test_explorer_stats_excludes_conversations_by_default(test_client, clean_db):
    """Les conversations (bruit) sont exclues par défaut du socle."""
    embedding_vector = f"[{','.join(['0.1'] * 768)}]"
    async with clean_db.begin() as conn:
        await conn.execute(text(f"""
            INSERT INTO memories (id, title, content, memory_type, tags, embedding, created_at)
            VALUES
                ('{uuid.uuid4()}'::uuid, 'Conv test', 'conversation content', 'conversation',
                 ARRAY['session:x', 'claude-code'], '{embedding_vector}'::vector, NOW()),
                ('{uuid.uuid4()}'::uuid, 'Investigation test', 'investigation content', 'investigation',
                 ARRAY['14-juillet-2026'], '{embedding_vector}'::vector, NOW())
        """))

    response = await test_client.get("/api/v1/memories/explorer/stats")

    assert response.status_code == 200
    data = response.json()
    # La conversation insérée ne doit pas apparaître dans by_type (bruit)
    assert data["by_type"].get("conversation", 0) == 0
    assert data["by_type"].get("investigation", 0) >= 1


@pytest.mark.anyio
async def test_explorer_stats_with_conversations_flag(test_client, clean_db):
    """include_conversations=true inclut les conversations."""
    embedding_vector = f"[{','.join(['0.1'] * 768)}]"
    async with clean_db.begin() as conn:
        await conn.execute(text(f"""
            INSERT INTO memories (id, title, content, memory_type, tags, embedding, created_at)
            VALUES ('{uuid.uuid4()}'::uuid, 'Conv test', 'conversation content', 'conversation',
                    ARRAY['session:x'], '{embedding_vector}'::vector, NOW())
        """))

    response = await test_client.get(
        "/api/v1/memories/explorer/stats?include_conversations=true"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["by_type"].get("conversation", 0) >= 1


@pytest.mark.anyio
async def test_explorer_tree_by_subject(test_client, clean_db):
    """GET /explorer/tree?subject=X renvoie l'arborescence du sujet."""
    embedding_vector = f"[{','.join(['0.1'] * 768)}]"
    async with clean_db.begin() as conn:
        await conn.execute(text(f"""
            INSERT INTO memories (id, title, content, memory_type, tags, embedding, created_at)
            VALUES ('{uuid.uuid4()}'::uuid, 'Enquête défilé', 'content', 'investigation',
                    ARRAY['defile-privatisation'], '{embedding_vector}'::vector, NOW())
        """))

    response = await test_client.get(
        "/api/v1/memories/explorer/tree?subject=defile-privatisation"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["subject"] == "defile-privatisation"
    assert data["total"] >= 1
    assert "investigations" in data
    assert "facts" in data
    assert "others" in data
    # L'enquête insérée est bien classée
    assert any(i["title"] == "Enquête défilé" for i in data["investigations"])


@pytest.mark.anyio
async def test_explorer_tree_missing_subject_returns_422(test_client):
    """subject est requis : 422 sans paramètre."""
    response = await test_client.get("/api/v1/memories/explorer/tree")
    assert response.status_code == 422


@pytest.mark.anyio
async def test_related_by_tags_shared_score(test_client, clean_db):
    """related-by-tags : la mémoire partageant un tag de sujet est trouvée."""
    embedding_vector = f"[{','.join(['0.1'] * 768)}]"
    id_source = str(uuid.uuid4())
    id_related = str(uuid.uuid4())
    id_unrelated = str(uuid.uuid4())
    async with clean_db.begin() as conn:
        await conn.execute(text(f"""
            INSERT INTO memories (id, title, content, memory_type, tags, embedding, created_at)
            VALUES
                ('{id_source}'::uuid, 'Fait source', 'content', 'investigation',
                 ARRAY['arcom', 'status:CONFIRME', 'project:truth-engine'],
                 '{embedding_vector}'::vector, NOW()),
                ('{id_related}'::uuid, 'Fait lié', 'content', 'note',
                 ARRAY['arcom', 'status:CONFIRME'],
                 '{embedding_vector}'::vector, NOW()),
                ('{id_unrelated}'::uuid, 'Fait sans lien', 'content', 'note',
                 ARRAY['autre-sujet'],
                 '{embedding_vector}'::vector, NOW())
        """))

    response = await test_client.get(
        f"/api/v1/memories/{id_source}/related-by-tags?limit=10"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["memory_id"] == id_source
    related_ids = [r["id"] for r in data["related"]]
    assert id_related in related_ids
    assert id_unrelated not in related_ids
    # Le score reflète les tags partagés
    for r in data["related"]:
        assert r["score"] >= 1
        assert "shared_tags" in r
        assert "memory_type" in r


@pytest.mark.anyio
async def test_related_by_tags_not_found(test_client, clean_db):
    """related-by-tags sur une mémoire inexistante : 404."""
    response = await test_client.get(
        f"/api/v1/memories/{uuid.uuid4()}/related-by-tags"
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_memory_graph_route_no_conflict(test_client, clean_db):
    """Régression T0 : GET /memories/graph doit répondre (pas capturé par GET /{id})."""
    response = await test_client.get("/api/v1/memories/graph?limit=5")

    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
    assert isinstance(data["nodes"], list)
    assert isinstance(data["edges"], list)
