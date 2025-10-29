#!/usr/bin/env python3
"""Test memory semantic search."""

import asyncio
import sys
import os

os.chdir('/app')
sys.path.insert(0, '/app')


async def test_memory_search():
    """Test searching memories."""
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from db.repositories.memory_repository import MemoryRepository
        from services.embedding_service import MockEmbeddingService

        print("=" * 70)
        print("TEST: Recherche Sémantique de Mémoires")
        print("=" * 70)

        # Setup
        database_url = 'postgresql://mnemo:mnemopass@db:5432/mnemolite'
        sqlalchemy_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
        engine = create_async_engine(sqlalchemy_url, pool_size=2, echo=False)

        memory_repo = MemoryRepository(engine)
        embedding_service = MockEmbeddingService(model_name="mock", dimension=768)

        # Test 1: List all memories
        print("\n--- TEST 1: Liste toutes les mémoires ---")

        memories, total = await memory_repo.list_memories(limit=10, offset=0)

        print(f"✅ Trouvé {total} mémoires:")
        for mem in memories:
            print(f"   - [{mem.memory_type.value}] {mem.title[:60]}")
            print(f"     Tags: {mem.tags}")
            print(f"     Author: {mem.author}")
            print()

        # Test 2: Search by tag
        print("\n--- TEST 2: Recherche par tag 'auto-saved' ---")
        from mnemo_mcp.models.memory_models import MemoryFilters

        filters = MemoryFilters(tags=["auto-saved"])
        memories, total = await memory_repo.list_memories(
            filters=filters,
            limit=10,
            offset=0
        )

        print(f"✅ Trouvé {total} mémoires avec tag 'auto-saved':")
        for mem in memories:
            print(f"   - {mem.title}")

        # Test 3: Semantic search
        print("\n--- TEST 3: Recherche sémantique 'hook test' ---")

        # Generate query embedding
        query_embedding = await embedding_service.generate_embedding("hook test conversation")

        # Search with embedding
        memories, total = await memory_repo.search_by_vector(
            vector=query_embedding,
            limit=5,
            distance_threshold=2.0  # Accept all for testing (higher threshold)
        )

        print(f"✅ Trouvé {total} mémoires par similarité:")
        for mem in memories:
            print(f"   - {mem.title[:60]}")
            print(f"     Type: {mem.memory_type.value}, Tags: {mem.tags}")

        # Test 4: Search by memory type
        print("\n--- TEST 4: Recherche par type 'conversation' ---")
        from mnemo_mcp.models.memory_models import MemoryType

        filters = MemoryFilters(memory_type=MemoryType.CONVERSATION)
        memories, total = await memory_repo.list_memories(
            filters=filters,
            limit=10,
            offset=0
        )

        print(f"✅ Trouvé {total} mémoires de type 'conversation':")
        for mem in memories:
            print(f"   - {mem.title}")

        await engine.dispose()

        print("\n" + "=" * 70)
        print("✅ TOUS LES TESTS DE RECHERCHE RÉUSSIS!")
        print("=" * 70)
        return True

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_memory_search())
    sys.exit(0 if result else 1)
