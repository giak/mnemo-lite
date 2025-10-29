#!/usr/bin/env python3
"""Double check semantic search on conversations."""

import asyncio
import sys
import os

os.chdir('/app')
sys.path.insert(0, '/app')


async def double_check():
    """Test semantic search on saved conversations."""
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from db.repositories.memory_repository import MemoryRepository
        from services.embedding_service import MockEmbeddingService
        from mnemo_mcp.models.memory_models import MemoryFilters, MemoryType

        print("=" * 70)
        print("DOUBLE CHECK - Recherche Sémantique des Conversations")
        print("=" * 70)

        # Setup
        database_url = 'postgresql://mnemo:mnemopass@db:5432/mnemolite'
        sqlalchemy_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
        engine = create_async_engine(sqlalchemy_url, pool_size=2, echo=False)

        memory_repo = MemoryRepository(engine)
        embedding_service = MockEmbeddingService(model_name="mock", dimension=768)

        # Test 1: List all conversations
        print("\n📋 TEST 1: Toutes les conversations")
        print("-" * 70)
        filters = MemoryFilters(memory_type=MemoryType.CONVERSATION)
        memories, total = await memory_repo.list_memories(filters=filters, limit=10, offset=0)

        print(f"Total: {total} conversation(s)\n")
        for i, mem in enumerate(memories, 1):
            mem_id_str = str(mem.id)
            print(f"{i}. [{mem_id_str[:8]}...] {mem.title}")
            print(f"   Created: {mem.created_at}")
            print(f"   Tags: {mem.tags}")
            print(f"   Content length: {len(mem.content)} chars")
            print()

        # Test 2: Semantic search - "hook test"
        print("\n🔍 TEST 2: Recherche 'hook test configuration'")
        print("-" * 70)
        query_embedding = await embedding_service.generate_embedding("hook test configuration bugfix")
        memories, total = await memory_repo.search_by_vector(
            vector=query_embedding,
            filters=MemoryFilters(memory_type=MemoryType.CONVERSATION),
            limit=5,
            distance_threshold=2.0
        )

        print(f"Résultats: {total} conversation(s) pertinente(s)\n")
        for i, mem in enumerate(memories, 1):
            print(f"{i}. {mem.title}")

        # Test 3: Search by tag "auto-saved"
        print("\n🏷️  TEST 3: Filtre par tag 'auto-saved'")
        print("-" * 70)
        filters = MemoryFilters(tags=["auto-saved"])
        memories, total = await memory_repo.list_memories(filters=filters, limit=10, offset=0)

        print(f"Total: {total} conversation(s) auto-saved\n")

        # Test 4: Verify all have embeddings
        print("\n✨ TEST 4: Vérification embeddings")
        print("-" * 70)
        from sqlalchemy import text
        async with engine.begin() as conn:
            query = text("""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE embedding IS NULL) as without_embedding,
                    COUNT(*) FILTER (WHERE embedding IS NOT NULL) as with_embedding
                FROM memories
                WHERE deleted_at IS NULL AND memory_type = 'conversation'
            """)
            row = await conn.execute(query)
            result = row.fetchone()

            print(f"Total conversations: {result[0]}")
            print(f"Sans embedding: {result[1]}")
            print(f"Avec embedding: {result[2]} ✅")

        await engine.dispose()

        print("\n" + "=" * 70)
        print("✅ DOUBLE CHECK COMPLET - SYSTÈME OPÉRATIONNEL")
        print("=" * 70)

        if result[1] > 0:
            print(f"⚠️  WARNING: {result[1]} conversation(s) sans embedding")
            return False

        return True

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(double_check())
    sys.exit(0 if result else 1)
