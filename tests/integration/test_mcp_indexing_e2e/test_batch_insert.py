"""
Test for batch insert fallback behavior.

Tests verify:
- When batch insert fails, fallback to sequential insert works
- Uses mock to simulate batch failure
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text

from api.services.code_indexing_service import CodeIndexingService, FileInput, IndexingOptions
from api.services.code_chunking_service import CodeChunkingService
from api.services.metadata_extractor_service import MetadataExtractorService
from api.services.dual_embedding_service import DualEmbeddingService
from api.services.graph_construction_service import GraphConstructionService
from db.repositories.base import RepositoryError


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
async def test_batch_insert_fallback_on_failure(
    code_indexing_service,
    engine: AsyncEngine,
    test_fixtures_dir: str,
    test_repository: str,
    tmp_path
):
    """Test: When batch insert fails, fallback to sequential insert works."""
    import os
    sample_file = os.path.join(test_fixtures_dir, "sample.py")
    assert os.path.exists(sample_file), f"Sample file not found: {sample_file}"
    
    content = open(sample_file).read()
    
    files = [
        FileInput(
            path=sample_file,
            content=content,
            language="python"
        )
    ]
    
    options = IndexingOptions(
        extract_metadata=True,
        generate_embeddings=False,
        build_graph=False,
        repository=test_repository,
        repository_root=test_fixtures_dir
    )
    
    original_add_batch = code_indexing_service.chunk_repository.add_batch
    
    async def mock_add_batch_failure(chunks_data, connection=None):
        raise RepositoryError("Simulated batch insert failure")
    
    code_indexing_service.chunk_repository.add_batch = mock_add_batch_failure
    
    summary = await code_indexing_service.index_repository(files, options)
    
    code_indexing_service.chunk_repository.add_batch = original_add_batch
    
    assert summary.indexed_chunks > 0, \
        f"Expected chunks created via fallback, got {summary.indexed_chunks}"
    assert summary.failed_files == 0, \
        f"Expected no failed files (fallback worked), got {summary.failed_files}"
    
    from db.repositories.code_chunk_repository import CodeChunkRepository
    chunk_repo = CodeChunkRepository(engine=engine)
    stored_chunks = await chunk_repo.get_by_repository(test_repository)
    
    assert len(stored_chunks) > 0, "Expected chunks stored via fallback sequential inserts"


@pytest.mark.asyncio
async def test_batch_insert_success(
    code_indexing_service,
    engine: AsyncEngine,
    test_fixtures_dir: str,
    test_repository: str
):
    """Test: Normal batch insert works when no failure occurs."""
    import os
    sample_file = os.path.join(test_fixtures_dir, "sample.py")
    assert os.path.exists(sample_file), f"Sample file not found: {sample_file}"
    
    content = open(sample_file).read()
    
    files = [
        FileInput(
            path=sample_file,
            content=content,
            language="python"
        )
    ]
    
    options = IndexingOptions(
        extract_metadata=True,
        generate_embeddings=False,
        build_graph=False,
        repository=test_repository,
        repository_root=test_fixtures_dir
    )
    
    summary = await code_indexing_service.index_repository(files, options)
    
    assert summary.indexed_chunks > 0, f"Expected chunks created, got {summary.indexed_chunks}"
    assert summary.failed_files == 0, f"Expected no failures, got {summary.failed_files}"
    
    from db.repositories.code_chunk_repository import CodeChunkRepository
    chunk_repo = CodeChunkRepository(engine=engine)
    stored_chunks = await chunk_repo.get_by_repository(test_repository)
    
    assert len(stored_chunks) == summary.indexed_chunks, \
        f"Expected {summary.indexed_chunks} chunks, got {len(stored_chunks)}"
