#!/usr/bin/env python3
"""Test semantic search on saved conversations."""

import asyncio
import sys
import os

os.chdir('/app')
sys.path.insert(0, '/app')


async def search_conversations():
    """Search for conversations using semantic search."""
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from db.repositories.memory_repository import MemoryRepository
        from services.embedding_service import MockEmbeddingService
        from mnemo_mcp.models.memory_models import MemoryFilters, MemoryType

        print("=" * 70)
        print("RECHERCHE DE CONVERSATIONS SAUVEGARDÉES")
        print("=" * 70)

        # Setup
        database_url = 'postgresql://mnemo:mnemopass@db:5432/mnemolite'
        sqlalchemy_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
        engine = create_async_engine(sqlalchemy_url, pool_size=2, echo=False)

        memory_repo = MemoryRepository(engine)
        embedding_service = MockEmbeddingService(model_name="mock", dimension=768)

        # 1. List all conversations
        print("\n--- TOUTES LES CONVERSATIONS ---")
        filters = MemoryFilters(memory_type=MemoryType.CONVERSATION)
        memories, total = await memory_repo.list_memories(filters=filters, limit=10, offset=0)

        print(f"\n✅ Trouvé {total} conversation(s):\n")
        for mem in memories:
            print(f"📝 [{mem.id}]")
            print(f"   Titre: {mem.title}")
            print(f"   Tags: {mem.tags}")
            print(f"   Auteur: {mem.author}")
            print(f"   Créé: {mem.created_at}")
            print(f"\n   Contenu:")
            print("   " + "\n   ".join(mem.content.split('\n')[:10]))
            if len(mem.content.split('\n')) > 10:
                print(f"   ... ({len(mem.content.split('\n')) - 10} lignes supplémentaires)")
            print()

        # 2. Search by tag "auto-saved"
        print("\n--- CONVERSATIONS AUTO-SAVED ---")
        filters = MemoryFilters(tags=["auto-saved"])
        memories, total = await memory_repo.list_memories(filters=filters, limit=10, offset=0)

        print(f"✅ Trouvé {total} conversation(s) auto-saved\n")

        # 3. Semantic search: "hook test"
        print("\n--- RECHERCHE SÉMANTIQUE: 'hook test' ---")
        query_text = "hook test validation"
        query_embedding = await embedding_service.generate_embedding(query_text)

        memories, total = await memory_repo.search_by_vector(
            vector=query_embedding,
            filters=MemoryFilters(memory_type=MemoryType.CONVERSATION),
            limit=5,
            distance_threshold=2.0
        )

        print(f"✅ Trouvé {total} conversation(s) similaire(s) à '{query_text}':\n")
        for mem in memories:
            print(f"   - {mem.title}")

        # 4. Semantic search: "bugfix database"
        print("\n--- RECHERCHE SÉMANTIQUE: 'bugfix database' ---")
        query_text = "bugfix database sqlalchemy"
        query_embedding = await embedding_service.generate_embedding(query_text)

        memories, total = await memory_repo.search_by_vector(
            vector=query_embedding,
            limit=5,
            distance_threshold=2.0
        )

        print(f"✅ Trouvé {total} mémoire(s) similaire(s) à '{query_text}':\n")
        for mem in memories:
            print(f"   - [{mem.memory_type.value}] {mem.title}")

        await engine.dispose()

        print("\n" + "=" * 70)
        print("✅ RECHERCHE COMPLÈTE")
        print("=" * 70)
        return True

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(search_conversations())
    sys.exit(0 if result else 1)
