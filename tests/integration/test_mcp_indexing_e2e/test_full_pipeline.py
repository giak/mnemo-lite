"""
End-to-end integration tests for full MCP indexing pipeline.

Tests verify:
1. Index Python file -> chunks stored in PostgreSQL
2. Index Markdown file -> markdown chunks created
3. Indexed chunks are searchable via repository queries
"""

import pytest
import pytest_asyncio
import os
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from api.services.code_indexing_service import CodeIndexingService, FileInput, IndexingOptions
from api.services.code_chunking_service import CodeChunkingService
from api.services.metadata_extractor_service import MetadataExtractorService
from api.services.dual_embedding_service import DualEmbeddingService, EmbeddingDomain
from api.services.graph_construction_service import GraphConstructionService
from api.services.caches.cascade_cache import CascadeCache
from api.services.caches.code_chunk_cache import CodeChunkCache
from api.services.caches.redis_cache import RedisCache


@pytest_asyncio.fixture
async def code_indexing_service(engine: AsyncEngine, test_repository: str):
    """Create CodeIndexingService with all required dependencies."""
    from db.repositories.code_chunk_repository import CodeChunkRepository
    
    chunking_service = CodeChunkingService()
    metadata_service = MetadataExtractorService()
    
    embedding_service = DualEmbeddingService(
        device="cpu",
        dimension=768
    )
    
    graph_service = GraphConstructionService(engine=engine)
    chunk_repository = CodeChunkRepository(engine=engine)
    
    service = CodeIndexingService(
        engine=engine,
        chunking_service=chunking_service,
        metadata_service=metadata_service,
        embedding_service=embedding_service,
        graph_service=graph_service,
        chunk_repository=chunk_repository,
        chunk_cache=None,
    )
    
    yield service
    
    async with engine.connect() as conn:
        await conn.execute(
            text("DELETE FROM code_chunks WHERE repository = :repo"),
            {"repo": test_repository}
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_index_project_stores_chunks_in_db(
    code_indexing_service,
    engine: AsyncEngine,
    test_fixtures_dir: str,
    test_repository: str
):
    """Test: Index sample.py, verify chunks are stored in PostgreSQL."""
    sample_file = Path(test_fixtures_dir) / "sample.py"
    assert sample_file.exists(), f"Sample file not found: {sample_file}"
    
    content = sample_file.read_text()
    
    files = [
        FileInput(
            path=str(sample_file),
            content=content,
            language="python"
        )
    ]
    
    options = IndexingOptions(
        extract_metadata=True,
        generate_embeddings=True,
        build_graph=False,
        repository=test_repository,
        repository_root=str(Path(test_fixtures_dir).parent)
    )
    
    summary = await code_indexing_service.index_repository(files, options)
    
    assert summary.indexed_files == 1, f"Expected 1 file indexed, got {summary.indexed_files}"
    assert summary.indexed_chunks > 0, f"Expected chunks created, got {summary.indexed_chunks}"
    assert summary.failed_files == 0, f"Expected no failures, got {summary.failed_files}"
    
    from db.repositories.code_chunk_repository import CodeChunkRepository
    chunk_repo = CodeChunkRepository(engine=engine)
    stored_chunks = await chunk_repo.get_by_repository(test_repository)
    
    assert len(stored_chunks) == summary.indexed_chunks, \
        f"Expected {summary.indexed_chunks} chunks in DB, got {len(stored_chunks)}"
    
    for chunk in stored_chunks:
        assert chunk.file_path == str(sample_file)
        assert chunk.language == "python"
        assert chunk.repository == test_repository
        assert chunk.source_code is not None


@pytest.mark.asyncio
async def test_index_markdown_file(
    code_indexing_service,
    engine: AsyncEngine,
    test_fixtures_dir: str,
    test_repository: str
):
    """Test: Index sample.md, verify markdown chunks."""
    sample_file = Path(test_fixtures_dir) / "sample.md"
    assert sample_file.exists(), f"Sample file not found: {sample_file}"
    
    content = sample_file.read_text()
    
    files = [
        FileInput(
            path=str(sample_file),
            content=content,
            language="markdown"
        )
    ]
    
    options = IndexingOptions(
        extract_metadata=True,
        generate_embeddings=True,
        build_graph=False,
        repository=test_repository,
        repository_root=str(Path(test_fixtures_dir).parent)
    )
    
    summary = await code_indexing_service.index_repository(files, options)
    
    assert summary.indexed_files == 1, f"Expected 1 file indexed, got {summary.indexed_files}"
    assert summary.indexed_chunks > 0, f"Expected markdown chunks, got {summary.indexed_chunks}"
    
    from db.repositories.code_chunk_repository import CodeChunkRepository
    chunk_repo = CodeChunkRepository(engine=engine)
    stored_chunks = await chunk_repo.get_by_repository(test_repository)
    
    assert len(stored_chunks) > 0, "Expected at least one markdown chunk stored"
    
    md_chunks = [c for c in stored_chunks if c.language == "markdown"]
    assert len(md_chunks) > 0, f"Expected markdown language chunks, got {len(md_chunks)}"


@pytest.mark.asyncio
async def test_indexed_chunks_are_searchable(
    code_indexing_service,
    engine: AsyncEngine,
    test_fixtures_dir: str,
    test_repository: str
):
    """Test: After indexing, verify chunks are findable via repository query."""
    sample_file = Path(test_fixtures_dir) / "sample.py"
    content = sample_file.read_text()
    
    files = [
        FileInput(
            path=str(sample_file),
            content=content,
            language="python"
        )
    ]
    
    options = IndexingOptions(
        extract_metadata=True,
        generate_embeddings=False,
        build_graph=False,
        repository=test_repository,
        repository_root=str(Path(test_fixtures_dir).parent)
    )
    
    summary = await code_indexing_service.index_repository(files, options)
    assert summary.indexed_chunks > 0, "Expected chunks created"
    
    from db.repositories.code_chunk_repository import CodeChunkRepository
    chunk_repo = CodeChunkRepository(engine=engine)
    
    all_chunks = await chunk_repo.get_by_repository(test_repository)
    assert len(all_chunks) > 0, "Expected to find indexed chunks"
    
    file_path_chunks = [c for c in all_chunks if c.file_path == str(sample_file)]
    assert len(file_path_chunks) > 0, f"Expected chunks by file path, got {len(file_path_chunks)}"
    
    python_chunks = [c for c in all_chunks if c.language == "python"]
    assert len(python_chunks) > 0, f"Expected python chunks, got {len(python_chunks)}"


@pytest_asyncio.fixture
async def code_indexing_service_with_cache(engine: AsyncEngine, test_repository: str):
    """Create CodeIndexingService with cache enabled."""
    from db.repositories.code_chunk_repository import CodeChunkRepository
    
    chunking_service = CodeChunkingService()
    metadata_service = MetadataExtractorService()
    
    embedding_service = DualEmbeddingService(
        device="cpu",
        dimension=768
    )
    
    graph_service = GraphConstructionService(engine=engine)
    chunk_repository = CodeChunkRepository(engine=engine)
    
    l1_cache = CodeChunkCache(max_size_mb=10)
    l2_cache = RedisCache(redis_url="redis://redis:6379/0")
    chunk_cache = CascadeCache(l1_cache=l1_cache, l2_cache=l2_cache)
    
    service = CodeIndexingService(
        engine=engine,
        chunking_service=chunking_service,
        metadata_service=metadata_service,
        embedding_service=embedding_service,
        graph_service=graph_service,
        chunk_repository=chunk_repository,
        chunk_cache=chunk_cache,
    )
    
    yield service
    
    if chunk_cache.l1:
        chunk_cache.l1.clear()
    
    async with engine.connect() as conn:
        await conn.execute(
            text("DELETE FROM code_chunks WHERE repository = :repo"),
            {"repo": test_repository}
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_cache_population(
    code_indexing_service_with_cache,
    engine: AsyncEngine,
    test_fixtures_dir: str,
    test_repository: str
):
    """Test: After indexing, chunks are cached in cascade cache (L1/L2)."""
    sample_file = Path(test_fixtures_dir) / "sample.py"
    assert sample_file.exists(), f"Sample file not found: {sample_file}"
    
    content = sample_file.read_text()
    
    files = [
        FileInput(
            path=str(sample_file),
            content=content,
            language="python"
        )
    ]
    
    options = IndexingOptions(
        extract_metadata=True,
        generate_embeddings=False,
        build_graph=False,
        repository=test_repository,
        repository_root=str(Path(test_fixtures_dir).parent)
    )
    
    summary = await code_indexing_service_with_cache.index_repository(files, options)
    
    assert summary.indexed_chunks > 0, f"Expected chunks created, got {summary.indexed_chunks}"
    
    cache = code_indexing_service_with_cache.chunk_cache
    assert cache is not None, "Expected cascade cache to be configured"
    
    cached_chunks = await cache.get_chunks(str(sample_file), content)
    assert cached_chunks is not None, "Expected chunks to be cached after indexing"
    assert len(cached_chunks) == summary.indexed_chunks, \
        f"Expected {summary.indexed_chunks} cached chunks, got {len(cached_chunks)}"


@pytest_asyncio.fixture
async def code_indexing_service_with_graph(engine: AsyncEngine, test_repository: str):
    """Create CodeIndexingService with graph building enabled."""
    from db.repositories.code_chunk_repository import CodeChunkRepository
    
    chunking_service = CodeChunkingService()
    metadata_service = MetadataExtractorService()
    
    embedding_service = DualEmbeddingService(
        device="cpu",
        dimension=768
    )
    
    graph_service = GraphConstructionService(engine=engine)
    chunk_repository = CodeChunkRepository(engine=engine)
    
    service = CodeIndexingService(
        engine=engine,
        chunking_service=chunking_service,
        metadata_service=metadata_service,
        embedding_service=embedding_service,
        graph_service=graph_service,
        chunk_repository=chunk_repository,
        chunk_cache=None,
    )
    
    yield service
    
    async with engine.connect() as conn:
        await conn.execute(
            text("DELETE FROM code_chunks WHERE repository = :repo"),
            {"repo": test_repository}
        )
        await conn.execute(
            text("DELETE FROM nodes WHERE properties->>'file_path' LIKE :pattern"),
            {"pattern": f"{test_repository}/%"}
        )
        await conn.execute(
            text("DELETE FROM edges WHERE properties->>'file_path' LIKE :pattern"),
            {"pattern": f"{test_repository}/%"}
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_graph_construction(
    code_indexing_service_with_graph,
    engine: AsyncEngine,
    test_fixtures_dir: str,
    test_repository: str
):
    """Test: After indexing with graph build, graph nodes are created."""
    sample_file = Path(test_fixtures_dir) / "sample.py"
    assert sample_file.exists(), f"Sample file not found: {sample_file}"
    
    content = sample_file.read_text()
    
    files = [
        FileInput(
            path=str(sample_file),
            content=content,
            language="python"
        )
    ]
    
    options = IndexingOptions(
        extract_metadata=True,
        generate_embeddings=False,
        build_graph=True,
        repository=test_repository,
        repository_root=str(Path(test_fixtures_dir).parent)
    )
    
    summary = await code_indexing_service_with_graph.index_repository(files, options)
    
    assert summary.indexed_chunks > 0, f"Expected chunks created, got {summary.indexed_chunks}"
    assert summary.indexed_nodes > 0, f"Expected graph nodes created, got {summary.indexed_nodes}"
    
    from db.repositories.node_repository import NodeRepository
    node_repo = NodeRepository(engine=engine)
    nodes = await node_repo.get_by_repository(test_repository)
    
    assert len(nodes) > 0, f"Expected graph nodes created for repository, got {len(nodes)}"