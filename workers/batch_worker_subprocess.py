#!/usr/bin/env python3
"""
Subprocess worker: Processes 1 batch of files in isolated process.

EPIC-27: Batch Processing with Redis Streams
Architecture: subprocess.Popen → load PyTorch → process batch → exit (auto cleanup)

Isolation guarantees:
    - Separate Python process (subprocess, not multiprocessing)
    - PyTorch models loaded in this process only
    - Exit subprocess → complete memory cleanup
    - No shared tensor memory (unlike torch.multiprocessing)
"""

import asyncio
import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine

# Add api to path
sys.path.insert(0, "/app")

from services.dual_embedding_service import DualEmbeddingService, EmbeddingDomain
from services.code_chunking_service import CodeChunkingService
from services.indexing_error_service import IndexingErrorService
from models.indexing_error_models import IndexingErrorCreate


async def log_file_error(
    error_service: IndexingErrorService,
    repository: str,
    file_path: Path,
    error_message: str,
    error_type: str,
    language: Optional[str] = None,
    error_traceback: Optional[str] = None
):
    """
    Log file processing error to database.

    Args:
        error_service: IndexingErrorService instance
        repository: Repository name
        file_path: Path to file that failed
        error_message: Short error message
        error_type: Type of error (parsing_error, chunking_error, etc.)
        language: Optional programming language
        error_traceback: Optional full stack trace
    """
    try:
        error = IndexingErrorCreate(
            repository=repository,
            file_path=str(file_path),
            error_type=error_type,
            error_message=error_message[:500],  # Truncate if very long
            error_traceback=error_traceback[:10000] if error_traceback else None,
            language=language
        )

        await error_service.log_error(error)
    except Exception as log_err:
        # Don't fail batch if error logging fails
        print(f"Failed to log error: {log_err}", file=sys.stderr)


async def process_batch(repository: str, db_url: str, files: list) -> dict:
    """
    Process batch of files atomically.

    Args:
        repository: Repository name
        db_url: Database connection URL
        files: List of file paths to process

    Returns:
        {"success_count": 38, "error_count": 2}
    """
    # Load services (in this subprocess only)
    print(f"Loading embedding models...", file=sys.stderr)
    embedding_service = DualEmbeddingService()

    # EPIC-26: Inject metadata extractor service for TypeScript/JavaScript metadata extraction
    print(f"Initializing metadata extractor...", file=sys.stderr)
    from services.metadata_extractor_service import get_metadata_extractor_service
    metadata_service = get_metadata_extractor_service()

    print(f"Initializing chunking service...", file=sys.stderr)
    chunking_service = CodeChunkingService(metadata_service=metadata_service)

    # Create DB engine
    engine = create_async_engine(db_url, echo=False, pool_size=2, max_overflow=0)

    # Initialize error tracking service
    error_service = IndexingErrorService(engine)

    success_count = 0
    error_count = 0

    try:
        print(f"Processing {len(files)} files...", file=sys.stderr)

        for file_path_str in files:
            file_path = Path(file_path_str)

            try:
                # Process file atomically (chunking + embeddings + persist)
                result = await process_file_atomically(
                    file_path,
                    repository,
                    chunking_service,
                    embedding_service,
                    engine
                )

                if result.get("success", False):
                    success_count += 1
                    print(f"✓ {file_path.name}", file=sys.stderr)
                else:
                    error_count += 1
                    error_msg = result.get('error', 'unknown')
                    print(f"✗ {file_path.name}: {error_msg}", file=sys.stderr)

                    # Log error to database
                    await log_file_error(
                        error_service,
                        repository,
                        file_path,
                        error_msg,
                        result.get('error_type', 'chunking_error'),
                        result.get('language', None)
                    )

            except Exception as e:
                error_count += 1
                error_msg = str(e)
                error_traceback = traceback.format_exc()
                print(f"✗ {file_path.name}: {error_msg}", file=sys.stderr)

                # Log unexpected error to database (classify as chunking_error by default)
                await log_file_error(
                    error_service,
                    repository,
                    file_path,
                    error_msg,
                    'chunking_error',
                    None,
                    error_traceback
                )

        return {"success_count": success_count, "error_count": error_count}

    finally:
        # Cleanup
        await engine.dispose()
        del embedding_service
        del chunking_service
        del error_service


async def process_file_atomically(
    file_path: Path,
    repository: str,
    chunking_service,
    embedding_service,
    engine
):
    """
    Process 1 file: chunking + embeddings + persist.

    Implementation reuses existing logic from scripts/index_directory.py
    using repository pattern (EPIC-27 code review fix).
    """
    from db.repositories.code_chunk_repository import CodeChunkRepository
    from models.code_chunk_models import CodeChunkCreate

    try:
        # Read file
        content = file_path.read_text(encoding="utf-8")

        # Determine language
        language = "typescript" if file_path.suffix == ".ts" else "javascript"

        # Chunk code (with metadata extraction via injected metadata_service)
        chunks = await chunking_service.chunk_code(
            source_code=content,
            language=language,
            file_path=str(file_path)
        )

        if not chunks:
            return {
                "success": False,
                "error": "no chunks generated",
                "error_type": "chunking_error",
                "language": language
            }

        # Generate embeddings for all chunks
        chunk_creates = []
        for chunk in chunks:
            # Generate CODE embedding
            embedding_result = await embedding_service.generate_embedding(
                chunk.source_code,
                domain=EmbeddingDomain.CODE
            )

            # Create chunk model with embedding
            chunk_create = CodeChunkCreate(
                file_path=chunk.file_path,
                language=chunk.language,
                chunk_type=chunk.chunk_type,
                name=chunk.name,
                source_code=chunk.source_code,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                repository=repository,
                metadata=chunk.metadata,  # Already contains calls, imports from chunking
                embedding_text=None,
                embedding_code=embedding_result['code']
            )

            chunk_creates.append(chunk_create)

        # Persist to DB using repository pattern (single transaction)
        async with engine.begin() as conn:
            chunk_repo = CodeChunkRepository(engine, connection=conn)

            # Delete existing chunks for this file (simple upsert strategy)
            await chunk_repo.delete_by_file_path(str(file_path), connection=conn)

            # Insert new chunks
            for chunk_create in chunk_creates:
                await chunk_repo.add(chunk_create, connection=conn)

        return {"success": True, "chunks": len(chunks)}

    except UnicodeDecodeError as e:
        return {
            "success": False,
            "error": f"Encoding error: {str(e)}",
            "error_type": "encoding_error"
        }
    except Exception as e:
        # Classify error type based on where it failed
        error_str = str(e).lower()

        if "tree-sitter" in error_str or "parse" in error_str or "syntax" in error_str:
            error_type = "parsing_error"
        elif "chunk" in error_str:
            error_type = "chunking_error"
        elif "embedding" in error_str:
            error_type = "embedding_error"
        elif "database" in error_str or "sqlalchemy" in error_str:
            error_type = "persistence_error"
        else:
            # Default to chunking_error for unclassified errors
            error_type = "chunking_error"

        return {
            "success": False,
            "error": str(e),
            "error_type": error_type,
            "language": language if 'language' in locals() else None
        }


def main():
    """Entry point for subprocess worker."""
    parser = argparse.ArgumentParser(description="Batch worker subprocess")
    parser.add_argument("--repository", required=True, help="Repository name")
    parser.add_argument("--db-url", required=True, help="Database URL")
    parser.add_argument("--files", required=True, help="Comma-separated file paths")
    args = parser.parse_args()

    # Parse files
    files = args.files.split(",")

    # Process batch
    result = asyncio.run(process_batch(args.repository, args.db_url, files))

    # Print result as JSON (last line of stdout)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
