#!/usr/bin/env python3
"""
POC: Backfill embeddings for a small batch of memories.

Usage (inside Docker container):
    docker compose exec api python scripts/backfill_memory_embeddings.py [--limit N]

Default: Process 10 memories only (POC mode)
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime

# Add api directory to path
sys.path.insert(0, '/app')

import asyncpg


async def get_memories_without_embeddings(pool: asyncpg.Pool, limit: int = 10):
    """Fetch memories that don't have embeddings yet."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, title, content
            FROM memories
            WHERE embedding IS NULL
              AND deleted_at IS NULL
            ORDER BY created_at DESC
            LIMIT $1
        """, limit)
        return rows


async def count_memories_without_embeddings(pool: asyncpg.Pool) -> int:
    """Count total memories needing embeddings."""
    async with pool.acquire() as conn:
        return await conn.fetchval("""
            SELECT COUNT(*) FROM memories
            WHERE embedding IS NULL AND deleted_at IS NULL
        """)


async def update_memory_embedding(pool: asyncpg.Pool, memory_id: str, embedding: list):
    """Update a single memory with its embedding."""
    async with pool.acquire() as conn:
        embedding_str = f"[{','.join(map(str, embedding))}]"
        await conn.execute("""
            UPDATE memories
            SET embedding = $1::vector,
                embedding_model = 'nomic-embed-text-v1.5',
                updated_at = NOW()
            WHERE id = $2
        """, embedding_str, memory_id)


async def test_search(pool: asyncpg.Pool, query: str = "agriculture Mercosur"):
    """Test semantic search after backfill."""
    from services.sentence_transformer_embedding_service import SentenceTransformerEmbeddingService

    svc = SentenceTransformerEmbeddingService()
    query_embedding = await svc.generate_embedding(query)
    vector_str = f"[{','.join(map(str, query_embedding))}]"

    async with pool.acquire() as conn:
        rows = await conn.fetch(f"""
            SELECT id, title,
                   (1 - (embedding <=> '{vector_str}'::vector)) as similarity
            FROM memories
            WHERE embedding IS NOT NULL
              AND deleted_at IS NULL
            ORDER BY embedding <=> '{vector_str}'::vector
            LIMIT 5
        """)
        return rows


async def main():
    parser = argparse.ArgumentParser(description='POC: Backfill memory embeddings')
    parser.add_argument('--limit', type=int, default=10, help='Number of memories to process (default: 10)')
    parser.add_argument('--test-query', type=str, default='agriculture Mercosur', help='Query to test after backfill')
    args = parser.parse_args()

    print("=" * 60)
    print(f"POC: Memory Embedding Backfill (limit={args.limit})")
    print("=" * 60)

    database_url = os.getenv("DATABASE_URL", "postgresql://mnemo:mnemo@db:5432/mnemolite")
    # Handle SQLAlchemy-style URLs (postgresql+asyncpg://)
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)

    print("Connecting to database...")
    pool = await asyncpg.create_pool(database_url, min_size=2, max_size=5, command_timeout=60)

    total_null = await count_memories_without_embeddings(pool)
    print(f"Total memories without embeddings: {total_null:,}")
    print()

    print("Loading embedding model...")
    from services.sentence_transformer_embedding_service import SentenceTransformerEmbeddingService
    embedding_service = SentenceTransformerEmbeddingService()
    print("Model loaded!")
    print()

    # Fetch batch
    memories = await get_memories_without_embeddings(pool, args.limit)
    print(f"Processing {len(memories)} memories...")
    print()

    start_time = datetime.now()
    processed = 0
    for row in memories:
        memory_id = str(row['id'])
        title = row['title'] or ""
        content = row['content'] or ""

        print(f"  [{processed+1}/{len(memories)}] {memory_id[:8]}... ", end="")

        try:
            embedding = await embedding_service.generate_embedding(f"{title}\n\n{content}")
            await update_memory_embedding(pool, memory_id, embedding)
            print(f"OK (dim={len(embedding)})")
            processed += 1
        except Exception as e:
            print(f"ERROR: {e}")

    elapsed_seconds = (datetime.now() - start_time).total_seconds()

    print()
    print("=" * 60)
    print(f"RESULT: {processed}/{len(memories)} memories updated")
    print(f"TIME: {elapsed_seconds:.2f} seconds")

    # Calculate rate and estimate total time
    if processed > 0 and elapsed_seconds > 0:
        rate = processed / elapsed_seconds
        print(f"RATE: {rate:.2f} memories/second")

        # Estimate for all memories
        estimated_total_seconds = total_null / rate
        estimated_minutes = estimated_total_seconds / 60
        estimated_hours = estimated_minutes / 60

        print()
        print(f"📊 ESTIMATION pour {total_null:,} memories:")
        if estimated_hours >= 1:
            print(f"   → {estimated_hours:.1f} heures ({estimated_minutes:.0f} minutes)")
        else:
            print(f"   → {estimated_minutes:.1f} minutes")
    print("=" * 60)
    print()

    # Test search
    print(f"Testing search: '{args.test_query}'")
    results = await test_search(pool, args.test_query)

    if results:
        print(f"Found {len(results)} results:")
        for r in results:
            print(f"  - {r['title'][:50]}... (similarity: {r['similarity']:.3f})")
    else:
        print("No results found (need more embeddings)")

    print()
    remaining = await count_memories_without_embeddings(pool)
    print(f"Remaining without embeddings: {remaining:,}")

    await pool.close()
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
