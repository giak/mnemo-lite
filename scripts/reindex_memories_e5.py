#!/usr/bin/env python3
"""
Re-index memories with E5-base embeddings.

EPIC-24: Regenerate memory embeddings after switching from Nomic v1.5 to E5-base.
Only affects TEXT embeddings (memories), NOT code chunks.

Usage (inside Docker container):
    docker compose exec api python scripts/reindex_memories_e5.py

    # Dry run (show counts only):
    docker compose exec api python scripts/reindex_memories_e5.py --dry-run

    # Limit for testing:
    docker compose exec api python scripts/reindex_memories_e5.py --limit 100
"""

import asyncio
import sys
import os
import time
import argparse

sys.path.insert(0, '/app')


async def reindex_memories(dry_run: bool = False, limit: int = None, batch_size: int = 32):
    """Re-generate embeddings for all memories using current EMBEDDING_MODEL."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    from services.sentence_transformer_embedding_service import (
        SentenceTransformerEmbeddingService,
        TextType,
    )

    # Initialize
    url = os.getenv('DATABASE_URL', 'postgresql+asyncpg://mnemo:mnemopass@db:5432/mnemolite')
    engine = create_async_engine(url)
    service = SentenceTransformerEmbeddingService()

    print("=" * 70)
    print("Re-indexing Memories with E5-base")
    print("=" * 70)
    print(f"Model: {service.model_name}")
    print(f"Dimension: {service.dimension}")
    print(f"Uses prefix: {service.model_config.get('uses_prefix', False)}")
    print(f"Batch size: {batch_size}")
    if limit:
        print(f"Limit: {limit}")
    print()

    # Count memories
    async with engine.begin() as conn:
        result = await conn.execute(text(
            "SELECT COUNT(*) FROM memories WHERE deleted_at IS NULL"
        ))
        total = result.scalar()

    print(f"Total memories to process: {total}")

    if dry_run:
        print("\n[DRY RUN] No changes will be made.")
        return

    # Warm up model
    print("\nLoading model...")
    start = time.time()
    await service.embed_document("warmup")
    print(f"Model loaded in {time.time() - start:.1f}s")

    # Process in batches
    processed = 0
    errors = 0
    offset = 0
    total_to_process = limit if limit else total

    start_time = time.time()

    while processed < total_to_process:
        # Fetch batch
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT id, title, content
                FROM memories
                WHERE deleted_at IS NULL
                ORDER BY created_at
                LIMIT :batch_size OFFSET :offset
            """), {"batch_size": batch_size, "offset": offset})
            rows = result.fetchall()

        if not rows:
            break

        # Generate embeddings for batch
        texts = []
        ids = []
        for row in rows:
            memory_id, title, content = row
            # Build embedding source from title + content
            text_for_embedding = f"{title or ''}\n\n{content or ''}"[:8000]  # Limit length
            if text_for_embedding.strip():
                texts.append(text_for_embedding)
                ids.append(str(memory_id))

        if texts:
            try:
                # Batch encode with DOCUMENT type (passage: prefix for E5)
                embeddings = await service.generate_embeddings_batch(
                    texts,
                    text_type=TextType.DOCUMENT
                )

                # Update database
                async with engine.begin() as conn:
                    for memory_id, embedding in zip(ids, embeddings):
                        await conn.execute(text("""
                            UPDATE memories
                            SET embedding = :embedding
                            WHERE id = :id
                        """), {
                            "id": memory_id,
                            "embedding": str(embedding)
                        })

                processed += len(texts)

            except Exception as e:
                print(f"\n  ERROR: {e}")
                errors += len(texts)
                processed += len(texts)

        offset += batch_size

        # Progress
        elapsed = time.time() - start_time
        rate = processed / elapsed if elapsed > 0 else 0
        eta = (total_to_process - processed) / rate if rate > 0 else 0

        print(f"\r  Progress: {processed}/{total_to_process} ({processed*100/total_to_process:.1f}%) "
              f"| Rate: {rate:.1f}/s | ETA: {eta/60:.1f}min", end="", flush=True)

    elapsed = time.time() - start_time

    print(f"\n\n{'=' * 70}")
    print("COMPLETED")
    print("=" * 70)
    print(f"Processed: {processed}")
    print(f"Errors: {errors}")
    print(f"Time: {elapsed/60:.1f} minutes")
    print(f"Rate: {processed/elapsed:.1f} memories/second")


def main():
    parser = argparse.ArgumentParser(description="Re-index memories with E5-base")
    parser.add_argument("--dry-run", action="store_true", help="Show counts only")
    parser.add_argument("--limit", type=int, help="Limit number of memories to process")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size (default: 32)")
    args = parser.parse_args()

    asyncio.run(reindex_memories(
        dry_run=args.dry_run,
        limit=args.limit,
        batch_size=args.batch_size
    ))


if __name__ == "__main__":
    main()
