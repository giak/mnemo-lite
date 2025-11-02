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
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine

# Add api to path
sys.path.insert(0, "/app")

from services.dual_embedding_service import DualEmbeddingService, EmbeddingDomain
from services.code_chunking_service import CodeChunkingService


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

    print(f"Initializing chunking service...", file=sys.stderr)
    chunking_service = CodeChunkingService()

    # Create DB engine
    engine = create_async_engine(db_url, echo=False, pool_size=2, max_overflow=0)

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
                    print(f"✗ {file_path.name}: {result.get('error', 'unknown')}", file=sys.stderr)

            except Exception as e:
                error_count += 1
                print(f"✗ {file_path.name}: {e}", file=sys.stderr)

        return {"success_count": success_count, "error_count": error_count}

    finally:
        # Cleanup
        await engine.dispose()
        del embedding_service
        del chunking_service


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
    """
    from sqlalchemy import text

    try:
        # Read file
        content = file_path.read_text(encoding="utf-8")

        # Determine language
        language = "typescript" if file_path.suffix == ".ts" else "javascript"

        # Chunk code (without metadata for now - simplified)
        chunks = await chunking_service.chunk_code(
            source_code=content,
            language=language,
            file_path=str(file_path)
        )

        if not chunks:
            return {"success": False, "error": "no chunks generated"}

        # Generate embeddings
        texts = [chunk.source_code for chunk in chunks]
        embedding_results = await embedding_service.generate_embeddings_batch(
            texts,
            domain=EmbeddingDomain.CODE,
            show_progress_bar=False
        )
        # Extract just the code embeddings from the results
        embeddings = [result['code'] for result in embedding_results]

        # Persist to DB
        async with engine.begin() as conn:
            # First delete existing chunks for this file (simple upsert strategy)
            await conn.execute(
                text("DELETE FROM code_chunks WHERE repository = :repository AND file_path = :file_path"),
                {"repository": repository, "file_path": str(file_path)}
            )

            # Then insert new chunks
            for chunk, embedding in zip(chunks, embeddings):
                await conn.execute(
                    text("""
                        INSERT INTO code_chunks (
                            repository, file_path, language, chunk_type,
                            source_code, start_line, end_line,
                            embedding_code, metadata, indexed_at
                        ) VALUES (
                            :repository, :file_path, :language, :chunk_type,
                            :source_code, :start_line, :end_line,
                            :embedding_code, :metadata, NOW()
                        )
                    """),
                    {
                        "repository": repository,
                        "file_path": str(file_path),
                        "language": language,
                        "chunk_type": chunk.chunk_type.value if hasattr(chunk.chunk_type, 'value') else str(chunk.chunk_type),
                        "source_code": chunk.source_code,
                        "start_line": chunk.start_line or 0,
                        "end_line": chunk.end_line or 0,
                        "embedding_code": "[" + ",".join(map(str, embedding)) + "]",
                        "metadata": json.dumps(chunk.metadata)
                    }
                )

        return {"success": True, "chunks": len(chunks)}

    except Exception as e:
        return {"success": False, "error": str(e)}


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
