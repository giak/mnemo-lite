#!/usr/bin/env python3
"""
POC: Compare Vector-Only vs Hybrid Search for Memories

EPIC-24 P0: Demonstrates the improvement from hybrid search
(lexical pg_trgm + vector pgvector + RRF fusion) over vector-only search.

Tests the "Bardella problem": exact proper noun queries that vector search
handles poorly due to embedding dilution.

Usage (inside Docker container):
    docker compose exec api python scripts/poc_hybrid_vs_vector_memory_search.py
"""

import asyncio
import sys
sys.path.insert(0, '/app')

import time
from typing import List, Dict, Any

from sqlalchemy.ext.asyncio import create_async_engine


# Test queries demonstrating different search scenarios
TEST_QUERIES = [
    # Exact match queries (lexical should boost these)
    "Bardella",
    "Mercosur",
    "FNSEA",
    "Jordan Bardella",

    # Semantic queries (vector should handle these)
    "contradiction discours votes agriculteurs",
    "stratégie électorale monde rural",
    "accord commercial Europe Amérique du Sud",

    # Mixed queries (hybrid should excel)
    "Bardella hypocrisie agriculteurs",
    "RN position agriculture européenne",
    "analyse politique élections",
]


async def test_vector_only_search(
    memory_repository,
    embedding_service,
    query: str,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """Execute vector-only search (original behavior)."""
    start_time = time.time()

    # Generate embedding
    embedding = await embedding_service.generate_embedding(query)

    # Vector search
    memories, total = await memory_repository.search_by_vector(
        vector=embedding,
        filters=None,
        limit=limit,
        offset=0,
        distance_threshold=0.0  # No threshold, get all
    )

    elapsed_ms = (time.time() - start_time) * 1000

    results = []
    for i, mem in enumerate(memories, start=1):
        results.append({
            "rank": i,
            "title": mem.title[:50],
            "similarity": mem.similarity_score if hasattr(mem, 'similarity_score') else None,
            "memory_id": str(mem.id),
        })

    return results, elapsed_ms


async def test_hybrid_search(
    hybrid_service,
    embedding_service,
    query: str,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """Execute hybrid search (lexical + vector + RRF)."""
    start_time = time.time()

    # Generate embedding
    embedding = await embedding_service.generate_embedding(query)

    # Hybrid search
    response = await hybrid_service.search(
        query=query,
        embedding=embedding,
        filters=None,
        limit=limit,
        offset=0,
        enable_lexical=True,
        enable_vector=True,
        lexical_weight=0.4,
        vector_weight=0.6,
    )

    elapsed_ms = response.metadata.execution_time_ms

    results = []
    for hr in response.results:
        results.append({
            "rank": hr.rank,
            "title": hr.title[:50],
            "rrf_score": hr.rrf_score,
            "lexical_score": hr.lexical_score,
            "vector_similarity": hr.vector_similarity,
            "memory_id": hr.memory_id,
        })

    return results, elapsed_ms, response.metadata


async def test_lexical_only_search(
    hybrid_service,
    query: str,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """Execute lexical-only search (pg_trgm)."""
    start_time = time.time()

    # Lexical-only search (no embedding needed)
    response = await hybrid_service.search(
        query=query,
        embedding=None,  # No embedding
        filters=None,
        limit=limit,
        offset=0,
        enable_lexical=True,
        enable_vector=False,
    )

    elapsed_ms = response.metadata.execution_time_ms

    results = []
    for hr in response.results:
        results.append({
            "rank": hr.rank,
            "title": hr.title[:50],
            "rrf_score": hr.rrf_score,
            "lexical_score": hr.lexical_score,
            "memory_id": hr.memory_id,
        })

    return results, elapsed_ms


async def main():
    print("=" * 80)
    print("POC: Vector-Only vs Hybrid Search for Memories")
    print("EPIC-24 P0: Demonstrating improvement from lexical + vector + RRF fusion")
    print("=" * 80)
    print()

    # Initialize services
    import os
    from services.sentence_transformer_embedding_service import SentenceTransformerEmbeddingService
    from services.hybrid_memory_search_service import HybridMemorySearchService
    from services.rrf_fusion_service import RRFFusionService
    from db.repositories.memory_repository import MemoryRepository

    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://mnemo:mnemo@db:5432/mnemolite")
    engine = create_async_engine(database_url, echo=False)

    embedding_service = SentenceTransformerEmbeddingService()
    memory_repository = MemoryRepository(engine)
    hybrid_service = HybridMemorySearchService(
        engine=engine,
        fusion_service=RRFFusionService(k=60),
        default_lexical_weight=0.4,
        default_vector_weight=0.6,
    )

    print("Services initialized")
    print()

    # Check if we have any memories to search
    from sqlalchemy.sql import text
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT COUNT(*) FROM memories WHERE deleted_at IS NULL"))
        memory_count = result.scalar()

    print(f"Total memories in database: {memory_count}")

    if memory_count == 0:
        print()
        print("No memories found! Please create some test memories first.")
        print("Run: docker compose exec api python scripts/test_embedding_source_e2e.py")
        await engine.dispose()
        return

    print()
    print("=" * 80)
    print("COMPARISON: Vector-Only vs Hybrid vs Lexical-Only")
    print("=" * 80)
    print()

    for query in TEST_QUERIES:
        print(f"Query: '{query}'")
        print("-" * 60)

        # Vector-only search
        try:
            vector_results, vector_ms = await test_vector_only_search(
                memory_repository, embedding_service, query, limit=3
            )
            print(f"  VECTOR-ONLY ({vector_ms:.1f}ms):")
            if vector_results:
                for r in vector_results[:3]:
                    score = r.get('similarity', 'N/A')
                    if isinstance(score, float):
                        print(f"    #{r['rank']}: {r['title']} (sim={score:.3f})")
                    else:
                        print(f"    #{r['rank']}: {r['title']}")
            else:
                print("    (no results)")
        except Exception as e:
            print(f"    ERROR: {e}")

        # Hybrid search
        try:
            hybrid_results, hybrid_ms, hybrid_meta = await test_hybrid_search(
                hybrid_service, embedding_service, query, limit=3
            )
            print(f"  HYBRID ({hybrid_ms:.1f}ms) [lex:{hybrid_meta.lexical_count}, vec:{hybrid_meta.vector_count}]:")
            if hybrid_results:
                for r in hybrid_results[:3]:
                    lex = r.get('lexical_score')
                    vec = r.get('vector_similarity')
                    lex_str = f"lex={lex:.3f}" if lex else "lex=N/A"
                    vec_str = f"vec={vec:.3f}" if vec else "vec=N/A"
                    print(f"    #{r['rank']}: {r['title']} (rrf={r['rrf_score']:.4f}, {lex_str}, {vec_str})")
            else:
                print("    (no results)")
        except Exception as e:
            print(f"    ERROR: {e}")

        # Lexical-only search
        try:
            lexical_results, lexical_ms = await test_lexical_only_search(
                hybrid_service, query, limit=3
            )
            print(f"  LEXICAL-ONLY ({lexical_ms:.1f}ms):")
            if lexical_results:
                for r in lexical_results[:3]:
                    lex = r.get('lexical_score')
                    lex_str = f"trgm={lex:.3f}" if lex else "trgm=N/A"
                    print(f"    #{r['rank']}: {r['title']} ({lex_str})")
            else:
                print("    (no results)")
        except Exception as e:
            print(f"    ERROR: {e}")

        print()

    print("=" * 80)
    print("ANALYSIS")
    print("=" * 80)
    print()
    print("Key observations:")
    print("  1. VECTOR-ONLY: Good for semantic queries, poor for exact matches")
    print("  2. LEXICAL-ONLY: Good for exact matches (Bardella), poor for paraphrases")
    print("  3. HYBRID: Combines both strengths via RRF fusion")
    print()
    print("Expected improvements from hybrid search:")
    print("  - Exact proper nouns (Bardella): +20-40% recall")
    print("  - Semantic queries: Maintained quality from vector")
    print("  - Mixed queries: Best of both worlds")
    print()
    print("=" * 80)
    print("POC COMPLETE")
    print("=" * 80)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
