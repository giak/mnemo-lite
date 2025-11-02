import pytest
import uuid
from sqlalchemy.sql import text
from db.repositories.detailed_metadata_repository import DetailedMetadataRepository
from models.metadata_models import DetailedMetadata


@pytest.mark.asyncio
async def test_create_detailed_metadata(clean_db):
    """Test creating detailed metadata for a node."""
    repo = DetailedMetadataRepository(clean_db)

    # Create sample node and chunk IDs
    sample_node_id = uuid.uuid4()
    sample_chunk_id = uuid.uuid4()

    # Create prerequisite node and chunk in database
    async with clean_db.begin() as conn:
        # Create node
        await conn.execute(text("""
            INSERT INTO nodes (node_id, label, node_type, properties)
            VALUES (:node_id, 'testFunc', 'function', '{"repository": "test"}'::jsonb)
        """), {"node_id": str(sample_node_id)})

        # Create chunk
        await conn.execute(text("""
            INSERT INTO code_chunks (id, file_path, language, chunk_type, source_code, metadata, indexed_at)
            VALUES (:chunk_id, '/test.ts', 'typescript', 'function', 'test code', '{}'::jsonb, NOW())
        """), {"chunk_id": str(sample_chunk_id)})

    metadata_payload = {
        "calls": ["validateEmail", "createUser"],
        "imports": ["./utils.validator", "express"],
        "signature": {
            "parameters": [{"name": "email", "type": "string"}],
            "return_type": "Promise<User>"
        },
        "context": {
            "is_async": True,
            "decorators": ["@Injectable()"]
        }
    }

    metadata = await repo.create(
        node_id=sample_node_id,
        chunk_id=sample_chunk_id,
        metadata=metadata_payload,
        version=1
    )

    assert metadata.node_id == sample_node_id
    assert metadata.metadata["calls"] == ["validateEmail", "createUser"]
    assert metadata.metadata["signature"]["return_type"] == "Promise<User>"
    assert metadata.version == 1


@pytest.mark.asyncio
async def test_get_latest_metadata_by_node(clean_db):
    """Test retrieving latest version of metadata."""
    repo = DetailedMetadataRepository(clean_db)

    # Create sample node and chunk IDs
    sample_node_id = uuid.uuid4()
    sample_chunk_id = uuid.uuid4()

    # Create prerequisite node and chunk in database
    async with clean_db.begin() as conn:
        # Create node
        await conn.execute(text("""
            INSERT INTO nodes (node_id, label, node_type, properties)
            VALUES (:node_id, 'testFunc', 'function', '{"repository": "test"}'::jsonb)
        """), {"node_id": str(sample_node_id)})

        # Create chunk
        await conn.execute(text("""
            INSERT INTO code_chunks (id, file_path, language, chunk_type, source_code, metadata, indexed_at)
            VALUES (:chunk_id, '/test.ts', 'typescript', 'function', 'test code', '{}'::jsonb, NOW())
        """), {"chunk_id": str(sample_chunk_id)})

    # Create v1
    await repo.create(sample_node_id, sample_chunk_id, {"calls": ["old"]}, version=1)

    # Create v2
    metadata_v2 = await repo.create(sample_node_id, sample_chunk_id, {"calls": ["new"]}, version=2)

    # Get latest
    latest = await repo.get_latest_by_node(sample_node_id)

    assert latest.version == 2
    assert latest.metadata["calls"] == ["new"]


@pytest.mark.asyncio
async def test_get_by_repository(clean_db):
    """Test retrieving all metadata entries for a repository."""
    repo = DetailedMetadataRepository(clean_db)

    # Create two nodes in same repository
    node_id_1 = uuid.uuid4()
    node_id_2 = uuid.uuid4()
    chunk_id_1 = uuid.uuid4()
    chunk_id_2 = uuid.uuid4()

    async with clean_db.begin() as conn:
        # Create nodes
        await conn.execute(text("""
            INSERT INTO nodes (node_id, label, node_type, properties)
            VALUES (:node_id, 'func1', 'function', '{"repository": "my-repo"}'::jsonb)
        """), {"node_id": str(node_id_1)})

        await conn.execute(text("""
            INSERT INTO nodes (node_id, label, node_type, properties)
            VALUES (:node_id, 'func2', 'function', '{"repository": "my-repo"}'::jsonb)
        """), {"node_id": str(node_id_2)})

        # Create chunks
        await conn.execute(text("""
            INSERT INTO code_chunks (id, file_path, language, chunk_type, source_code, metadata, indexed_at)
            VALUES (:chunk_id, '/test1.ts', 'typescript', 'function', 'code1', '{}'::jsonb, NOW())
        """), {"chunk_id": str(chunk_id_1)})

        await conn.execute(text("""
            INSERT INTO code_chunks (id, file_path, language, chunk_type, source_code, metadata, indexed_at)
            VALUES (:chunk_id, '/test2.ts', 'typescript', 'function', 'code2', '{}'::jsonb, NOW())
        """), {"chunk_id": str(chunk_id_2)})

    # Create metadata for both nodes
    await repo.create(node_id_1, chunk_id_1, {"calls": ["helper1"]}, version=1)
    await repo.create(node_id_2, chunk_id_2, {"calls": ["helper2"]}, version=1)

    # Get all metadata for repository
    results = await repo.get_by_repository("my-repo", version=1)

    assert len(results) == 2
    assert all(m.version == 1 for m in results)
    node_ids = {m.node_id for m in results}
    assert node_ids == {node_id_1, node_id_2}
