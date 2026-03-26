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
from db.repositories.code_chunk_repository import CodeChunkRepository


@pytest_asyncio.fixture
async def code_indexing_service(engine: AsyncEngine, test_repository: str):
    """Create CodeIndexingService with all required dependencies."""
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
    
    chunk_repo = CodeChunkRepository(engine=engine)
    
    all_chunks = await chunk_repo.get_by_repository(test_repository)
    assert len(all_chunks) > 0, "Expected to find indexed chunks"
    
    file_path_chunks = [c for c in all_chunks if c.file_path == str(sample_file)]
    assert len(file_path_chunks) > 0, f"Expected chunks by file path, got {len(file_path_chunks)}"
    
    python_chunks = [c for c in all_chunks if c.language == "python"]
    assert len(python_chunks) > 0, f"Expected python chunks, got {len(python_chunks)}"