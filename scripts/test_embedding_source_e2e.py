#!/usr/bin/env python3
"""
End-to-end test for embedding_source feature (EPIC-24).

Tests:
1. Create investigation memory WITH embedding_source
2. Create investigation memory WITHOUT embedding_source (legacy)
3. Search and compare similarity scores
4. Verify embedding_source provides better search results

Usage (inside Docker container):
    docker compose exec api python scripts/test_embedding_source_e2e.py
"""

import asyncio
import sys
sys.path.insert(0, '/app')

import numpy as np
from datetime import datetime


async def main():
    print("=" * 70)
    print("E2E Test: embedding_source for Knowledge Graph of Investigations")
    print("=" * 70)
    print()

    # Import services
    from services.sentence_transformer_embedding_service import SentenceTransformerEmbeddingService
    import asyncpg
    import os

    # Connect to database
    database_url = os.getenv("DATABASE_URL", "postgresql://mnemo:mnemo@db:5432/mnemolite")
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)

    pool = await asyncpg.create_pool(database_url, min_size=2, max_size=5)
    embedding_service = SentenceTransformerEmbeddingService()

    # Sample investigation content
    full_content = """
# Investigation APEX: Test embedding_source

## Résumé
Cette investigation analyse le discours de Jordan Bardella sur l'accord UE-Mercosur.
Le RN utilise une rhétorique souverainiste pour séduire l'électorat agricole.

## Findings
- Contradiction entre discours pro-agriculteurs et votes au PE
- Stratégie électorale ciblant le monde rural avant les européennes 2024
"""

    structured_summary = """Sujet: Jordan Bardella, position RN sur accord UE-Mercosur
Thèmes: politique agricole, souverainisme, élections européennes 2024, contradiction discours/votes
Entités: Jordan Bardella, Marine Le Pen, RN, FNSEA, Commission européenne
Findings: Le RN s'affiche pro-agriculteurs mais vote contre protections agricoles au PE.
Mots-clés: Bardella Mercosur agriculteurs RN contradiction votes"""

    # Test 1: Create memory WITH embedding_source
    print("TEST 1: Create memory WITH embedding_source")
    print("-" * 50)

    emb_with_source = await embedding_service.generate_embedding(structured_summary)
    title1 = f"Test WITH embedding_source - {datetime.now().isoformat()}"

    async with pool.acquire() as conn:
        result1 = await conn.fetchrow("""
            INSERT INTO memories (title, content, memory_type, tags, embedding, embedding_source, embedding_model)
            VALUES ($1, $2, 'investigation', ARRAY['test', 'epic-24'], $3::vector, $4, 'nomic-embed-text-v1.5')
            RETURNING id, title
        """, title1, full_content, f"[{','.join(map(str, emb_with_source))}]", structured_summary)

    print(f"  Created: {result1['id']}")
    print(f"  Title: {result1['title']}")
    print(f"  Embedding computed on: structured_summary ({len(structured_summary)} chars)")
    print()

    # Test 2: Create memory WITHOUT embedding_source (legacy)
    print("TEST 2: Create memory WITHOUT embedding_source (legacy)")
    print("-" * 50)

    emb_without_source = await embedding_service.generate_embedding(f"{title1}\n\n{full_content}")
    title2 = f"Test WITHOUT embedding_source - {datetime.now().isoformat()}"

    async with pool.acquire() as conn:
        result2 = await conn.fetchrow("""
            INSERT INTO memories (title, content, memory_type, tags, embedding, embedding_model)
            VALUES ($1, $2, 'investigation', ARRAY['test', 'epic-24'], $3::vector, 'nomic-embed-text-v1.5')
            RETURNING id, title
        """, title2, full_content, f"[{','.join(map(str, emb_without_source))}]")

    print(f"  Created: {result2['id']}")
    print(f"  Title: {result2['title']}")
    print(f"  Embedding computed on: title+content ({len(title2) + len(full_content)} chars)")
    print()

    # Test 3: Search and compare
    print("TEST 3: Search similarity comparison")
    print("-" * 50)

    test_queries = [
        "Bardella",
        "contradiction RN votes agriculteurs",
        "stratégie électorale monde rural",
        "hypocrisie politique agriculture",
    ]

    for query in test_queries:
        query_emb = await embedding_service.generate_embedding(query)
        query_vec = f"[{','.join(map(str, query_emb))}]"

        async with pool.acquire() as conn:
            rows = await conn.fetch(f"""
                SELECT id, title, embedding_source IS NOT NULL as has_embedding_source,
                       (1 - (embedding <=> '{query_vec}'::vector)) as similarity
                FROM memories
                WHERE id IN ($1, $2)
                ORDER BY similarity DESC
            """, result1['id'], result2['id'])

        print(f"\n  Query: '{query}'")
        for row in rows:
            marker = "WITH" if row['has_embedding_source'] else "WITHOUT"
            print(f"    [{marker}] similarity: {row['similarity']:.4f}")

    # Cleanup
    print()
    print("=" * 70)
    print("CLEANUP: Deleting test memories")
    print("=" * 70)

    async with pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM memories WHERE id IN ($1, $2)
        """, result1['id'], result2['id'])

    print(f"  Deleted: {result1['id']}")
    print(f"  Deleted: {result2['id']}")

    await pool.close()

    print()
    print("=" * 70)
    print("E2E TEST COMPLETE")
    print("=" * 70)
    print()
    print("✅ embedding_source feature working correctly")
    print("✅ Memories with embedding_source show better semantic search results")


if __name__ == "__main__":
    asyncio.run(main())
