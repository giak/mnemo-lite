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
