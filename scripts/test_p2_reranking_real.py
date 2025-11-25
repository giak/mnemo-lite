#!/usr/bin/env python3
"""
Test RÉEL P2: Cross-encoder Reranking sur données MnemoLite.

Compare les résultats de recherche avec et sans reranking
sur les vraies memories de la base de données.

Usage (inside Docker container):
    docker compose exec api python scripts/test_p2_reranking_real.py
"""

import asyncio
import sys
import os
import time

sys.path.insert(0, '/app')

# Test queries (French - relevant to MnemoLite content)
TEST_QUERIES = [
    "embedding model configuration",
    "Jordan Bardella politique",
    "search service hybrid",
    "authentication token JWT",
    "database migration postgresql",
]


async def main():
    from sqlalchemy.ext.asyncio import create_async_engine
    from services.hybrid_memory_search_service import HybridMemorySearchService
    from services.sentence_transformer_embedding_service import SentenceTransformerEmbeddingService

    print("=" * 70)
    print("Test RÉEL P2: Cross-encoder Reranking")
    print("=" * 70)

    # Initialize database
    url = os.getenv('DATABASE_URL', 'postgresql+asyncpg://mnemo:mnemopass@db:5432/mnemolite')
    engine = create_async_engine(url)

    # Initialize services
    embedding_service = SentenceTransformerEmbeddingService()
    search_service = HybridMemorySearchService(engine=engine)

    # Warm up embedding model
    print("\nLoading embedding model...")
    await embedding_service.embed_query("warmup")
    print(f"Model: {embedding_service.model_name}")

    # Count memories
    from sqlalchemy import text
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT COUNT(*) FROM memories WHERE deleted_at IS NULL"))
        total_memories = result.scalar()
    print(f"Total memories in database: {total_memories}")

    if total_memories == 0:
        print("\n⚠️  No memories found. Please index some data first.")
        return

    print("\n" + "=" * 70)
    print("COMPARISON: Without vs With Reranking")
    print("=" * 70)

    for query in TEST_QUERIES:
        print(f"\n{'─' * 70}")
        print(f"Query: '{query}'")
        print("─" * 70)

        # Generate query embedding
        query_embedding = await embedding_service.embed_query(query)

        # Search WITHOUT reranking
        start = time.time()
        results_no_rerank = await search_service.search(
            query=query,
            embedding=query_embedding,
            limit=5,
            enable_reranking=False,
        )
        time_no_rerank = (time.time() - start) * 1000

        # Search WITH reranking
        start = time.time()
        results_with_rerank = await search_service.search(
            query=query,
            embedding=query_embedding,
            limit=5,
            enable_reranking=True,
            rerank_pool_size=20,
        )
        time_with_rerank = (time.time() - start) * 1000

        # Display results side by side
        print(f"\n  WITHOUT Reranking ({time_no_rerank:.0f}ms):")
        for i, r in enumerate(results_no_rerank.results[:3], 1):
            title = r.title[:50] if r.title else "(no title)"
            vec_sim = f"{r.vector_similarity:.3f}" if r.vector_similarity else "N/A"
            print(f"    {i}. [{vec_sim}] {title}...")

        print(f"\n  WITH Reranking ({time_with_rerank:.0f}ms):")
        for i, r in enumerate(results_with_rerank.results[:3], 1):
            title = r.title[:50] if r.title else "(no title)"
            rerank = f"{r.rerank_score:+.2f}" if r.rerank_score else "N/A"
            print(f"    {i}. [{rerank}] {title}...")

        # Check if order changed
        ids_no_rerank = [r.memory_id for r in results_no_rerank.results[:5]]
        ids_with_rerank = [r.memory_id for r in results_with_rerank.results[:5]]

        if ids_no_rerank != ids_with_rerank:
            print(f"\n  ✅ Reranking changed order!")
            # Find position changes
            for i, mid in enumerate(ids_with_rerank[:3]):
                if mid in ids_no_rerank:
                    old_pos = ids_no_rerank.index(mid) + 1
                    new_pos = i + 1
                    if old_pos != new_pos:
                        print(f"     Doc moved: #{old_pos} → #{new_pos}")
        else:
            print(f"\n  ≈ Same order (reranking agreed with RRF)")

        # Timing comparison
        overhead = time_with_rerank - time_no_rerank
        print(f"\n  Timing: +{overhead:.0f}ms overhead ({overhead/time_no_rerank*100:.0f}% slower)")

    # Summary
    print("\n" + "=" * 70)
    print("METADATA")
    print("=" * 70)
    print(f"  Embedding model: {embedding_service.model_name}")
    print(f"  Reranker model: cross-encoder/ms-marco-MiniLM-L-6-v2 (default)")
    print(f"  Total memories: {total_memories}")

    print("\n" + "=" * 70)
    print("✅ P2 Cross-encoder Reranking Test Complete")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
