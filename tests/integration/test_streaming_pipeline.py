"""
Integration test for streaming pipeline with atomic file processing.
"""
import pytest
import asyncio
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine
from scripts.index_directory import process_file_atomically
from services.dual_embedding_service import DualEmbeddingService
from db.repositories.code_chunk_repository import CodeChunkRepository


@pytest.mark.asyncio
async def test_process_file_atomically_creates_chunks_with_embeddings(tmp_path, clean_db):
    """Test that process_file_atomically creates chunks with embeddings in single transaction."""
    # Create test TypeScript file
    test_file = tmp_path / "user.ts"
    test_file.write_text("""
    export function validateUser(email: string): boolean {
        if (!email) return false;
        return email.includes("@");
    }

    export function logError(message: string): void {
        console.error(message);
    }
    """)

    # Setup
    repository = "test_streaming"
    embedding_service = DualEmbeddingService()
    chunk_repo = CodeChunkRepository(clean_db)

    # Process file atomically
    result = await process_file_atomically(
        file_path=test_file,
        repository=repository,
        embedding_service=embedding_service,
        engine=clean_db
    )

    # Verify chunks created
    assert result.chunks_created == 2  # validateUser + logError
    assert result.success is True

    # Verify chunks in database with embeddings
    chunks = await chunk_repo.get_by_repository(repository)
    assert len(chunks) == 2

    for chunk in chunks:
        assert chunk.embedding_code is not None
        assert len(chunk.embedding_code) == 768  # jinaai dimension
        assert chunk.repository == repository


@pytest.mark.asyncio
async def test_process_file_atomically_rollback_on_error(tmp_path, clean_db):
    """Test that transaction rolls back if processing fails mid-way."""
    # Create a mock scenario where embedding fails after chunks are created
    # We'll test this by creating valid chunks but injecting a failure
    test_file = tmp_path / "valid.ts"
    test_file.write_text("""
    export function testFunc(): void {
        console.log("test");
    }
    """)

    repository = "test_rollback"

    # Create a mock embedding service that fails
    class FailingEmbeddingService:
        async def generate_embedding(self, text, domain):
            raise RuntimeError("Embedding generation failed")

    embedding_service = FailingEmbeddingService()
    chunk_repo = CodeChunkRepository(clean_db)

    # Process should fail but not crash
    result = await process_file_atomically(
        file_path=test_file,
        repository=repository,
        embedding_service=embedding_service,
        engine=clean_db
    )

    # Verify failure recorded
    assert result.success is False
    assert result.chunks_created == 0
    assert "error" in result.error_message.lower() or "failed" in result.error_message.lower()

    # Verify NO chunks in database (transaction rolled back)
    chunks = await chunk_repo.get_by_repository(repository)
    assert len(chunks) == 0


@pytest.mark.asyncio
async def test_streaming_pipeline_processes_all_files(tmp_path, clean_db):
    """Test that streaming pipeline processes multiple files sequentially."""
    # Create 3 test files
    files = []
    for i in range(3):
        test_file = tmp_path / f"file{i}.ts"
        test_file.write_text(f"export function func{i}() {{ return {i}; }}")
        files.append(test_file)

    # Run streaming pipeline
    from scripts.index_directory import run_streaming_pipeline

    stats = await run_streaming_pipeline(
        directory=tmp_path,
        repository="test_multi",
        verbose=False,
        engine=clean_db
    )

    # Verify all files processed
    assert stats['total_files'] == 3
    assert stats['success_files'] == 3
    assert stats['error_files'] == 0
    assert stats['total_chunks'] == 3

    # Verify chunks in database
    from db.repositories.code_chunk_repository import CodeChunkRepository
    chunk_repo = CodeChunkRepository(clean_db)
    chunks = await chunk_repo.get_by_repository("test_multi")
    assert len(chunks) == 3


@pytest.mark.asyncio
async def test_streaming_pipeline_continues_on_error(tmp_path, clean_db):
    """Test that pipeline continues if one file produces no chunks."""
    # Create 2 valid + 1 file with no chunks
    valid1 = tmp_path / "valid1.ts"
    valid1.write_text("export function good1() { return 1; }")

    nochunks = tmp_path / "nochunks.ts"
    nochunks.write_text("this is garbage {{{")

    valid2 = tmp_path / "valid2.ts"
    valid2.write_text("export function good2() { return 2; }")

    # Run pipeline
    from scripts.index_directory import run_streaming_pipeline

    stats = await run_streaming_pipeline(
        directory=tmp_path,
        repository="test_errors",
        verbose=False,
        engine=clean_db
    )

    # Verify: 3 files processed successfully, but only 2 produced chunks
    assert stats['total_files'] == 3
    assert stats['success_files'] == 3  # All files processed successfully
    assert stats['error_files'] == 0  # No errors (0 chunks is not an error)
    assert stats['total_chunks'] == 2  # Only 2 chunks created


@pytest.mark.asyncio
async def test_graph_construction_after_streaming(tmp_path, clean_db):
    """Test that graph construction works after streaming pipeline."""
    # Create test files with function calls
    file1 = tmp_path / "utils.ts"
    file1.write_text("""
    export function helper() {
        return "help";
    }
    """)

    file2 = tmp_path / "main.ts"
    file2.write_text("""
    import { helper } from './utils';

    export function main() {
        const result = helper();
        return result;
    }
    """)

    # Run streaming pipeline (creates chunks)
    from scripts.index_directory import run_streaming_pipeline
    await run_streaming_pipeline(tmp_path, "test_graph", verbose=False, engine=clean_db)

    # Run graph construction
    from scripts.index_directory import build_graph_phase
    graph_stats = await build_graph_phase("test_graph", clean_db)

    # Verify nodes created
    assert graph_stats['total_nodes'] == 2  # helper + main
    assert graph_stats['total_edges'] >= 1  # main calls helper

    # Verify in database
    from db.repositories.node_repository import NodeRepository
    node_repo = NodeRepository(clean_db)
    nodes = await node_repo.get_by_repository("test_graph")
    assert len(nodes) == 2
