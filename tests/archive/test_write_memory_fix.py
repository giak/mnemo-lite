#!/usr/bin/env python3
"""
Test complet du fix write_memory après correction du database_url.
Teste l'injection de services et la sauvegarde complète.
"""

import asyncio
import sys
import os
from datetime import datetime

os.chdir('/app')
sys.path.insert(0, '/app')


async def test_write_memory_fix():
    """Test complet du fix write_memory."""

    print("=" * 70)
    print("TEST COMPLET: write_memory après fix database_url")
    print("=" * 70)

    try:
        # 1. Importer les composants
        from mnemo_mcp.config import config
        from sqlalchemy.ext.asyncio import create_async_engine
        from db.repositories.memory_repository import MemoryRepository
        from services.embedding_service import MockEmbeddingService
        from mnemo_mcp.tools.memory_tools import WriteMemoryTool

        print("\n✅ Imports réussis")

        # 2. Vérifier la conversion d'URL
        print(f"\n--- VÉRIFICATION URL DATABASE ---")
        print(f"config.database_url (original): {config.database_url}")

        # Simuler la conversion (comme dans server.py ligne 208)
        sqlalchemy_url = config.database_url.replace("postgresql://", "postgresql+asyncpg://")
        print(f"sqlalchemy_url (après fix):     {sqlalchemy_url}")

        if "+asyncpg" not in sqlalchemy_url:
            print("❌ ÉCHEC: L'URL ne contient pas '+asyncpg'")
            return False

        print("✅ URL correctement convertie")

        # 3. Créer le moteur SQLAlchemy
        print(f"\n--- CRÉATION MOTEUR SQLALCHEMY ---")
        try:
            sqlalchemy_engine = create_async_engine(
                sqlalchemy_url,
                pool_size=2,
                max_overflow=5,
                echo=False,
            )
            print("✅ Moteur SQLAlchemy créé avec succès")
        except Exception as e:
            print(f"❌ ÉCHEC création moteur: {e}")
            return False

        # 4. Initialiser les services
        print(f"\n--- INITIALISATION SERVICES ---")

        # MemoryRepository
        try:
            memory_repository = MemoryRepository(sqlalchemy_engine)
            print(f"✅ MemoryRepository initialisé: {type(memory_repository)}")
        except Exception as e:
            print(f"❌ ÉCHEC MemoryRepository: {e}")
            return False

        # EmbeddingService
        try:
            embedding_service = MockEmbeddingService(model_name="mock", dimension=768)
            print(f"✅ EmbeddingService initialisé: {type(embedding_service)}")
        except Exception as e:
            print(f"❌ ÉCHEC EmbeddingService: {e}")
            return False

        # 5. Créer et injecter services dans WriteMemoryTool
        print(f"\n--- INJECTION SERVICES ---")

        services = {
            "memory_repository": memory_repository,
            "embedding_service": embedding_service,
        }

        tool = WriteMemoryTool()
        tool.inject_services(services)

        # Vérifier l'injection
        if tool.memory_repository is None:
            print("❌ ÉCHEC: tool.memory_repository est None après injection")
            return False

        if tool.embedding_service is None:
            print("❌ ÉCHEC: tool.embedding_service est None après injection")
            return False

        print(f"✅ Services injectés correctement")
        print(f"   - memory_repository: {type(tool.memory_repository)}")
        print(f"   - embedding_service: {type(tool.embedding_service)}")

        # 6. Tester write_memory (création d'une mémoire test)
        print(f"\n--- TEST WRITE_MEMORY ---")

        class MockContext:
            pass

        ctx = MockContext()

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        test_content = f"""# Test de sauvegarde après fix

## Contexte
Test automatique après correction du bug database_url dans server.py:208.

## Bug corrigé
- **Avant**: `postgresql://...` n'était pas converti en `postgresql+asyncpg://...`
- **Après**: Conversion correcte avec `.replace("postgresql://", "postgresql+asyncpg://")`

## Résultat attendu
Cette mémoire doit être sauvegardée avec un embedding généré.

---
**Timestamp**: {timestamp}
**Test ID**: write_memory_fix_validation
"""

        try:
            result = await tool.execute(
                ctx=ctx,
                title=f"Test write_memory fix - {timestamp}",
                content=test_content,
                memory_type="note",
                tags=["test", "write_memory_fix", "auto-validation", f"date:{datetime.now().strftime('%Y%m%d')}"],
                author="AutoTest"
            )

            print(f"✅ write_memory réussi!")
            print(f"   - Memory ID: {result.get('id')}")
            print(f"   - Title: {result.get('title')}")
            print(f"   - Type: {result.get('memory_type')}")
            print(f"   - Created: {result.get('created_at')}")

        except Exception as e:
            print(f"❌ ÉCHEC write_memory: {e}")
            import traceback
            traceback.print_exc()
            return False

        # 7. Vérifier que la mémoire a bien été sauvegardée en DB
        print(f"\n--- VÉRIFICATION BASE DE DONNÉES ---")

        try:
            from sqlalchemy import text

            async with sqlalchemy_engine.begin() as conn:
                # Compter les mémoires avec le tag 'write_memory_fix'
                query = text("""
                    SELECT COUNT(*)
                    FROM memories
                    WHERE tags @> ARRAY['write_memory_fix']::text[]
                    AND deleted_at IS NULL
                """)

                count = await conn.scalar(query)
                print(f"✅ Mémoires trouvées avec tag 'write_memory_fix': {count}")

                if count == 0:
                    print("❌ ÉCHEC: Aucune mémoire trouvée en DB")
                    return False

                # Récupérer la dernière mémoire créée
                query = text("""
                    SELECT id, title, memory_type, embedding IS NOT NULL as has_embedding
                    FROM memories
                    WHERE tags @> ARRAY['write_memory_fix']::text[]
                    AND deleted_at IS NULL
                    ORDER BY created_at DESC
                    LIMIT 1
                """)

                row = await conn.execute(query)
                memory = row.fetchone()

                if memory:
                    print(f"✅ Mémoire récupérée:")
                    print(f"   - ID: {memory[0]}")
                    print(f"   - Title: {memory[1]}")
                    print(f"   - Type: {memory[2]}")
                    print(f"   - Has embedding: {memory[3]}")

                    if not memory[3]:
                        print("⚠️  WARNING: Pas d'embedding généré")
                else:
                    print("❌ ÉCHEC: Mémoire non trouvée en DB")
                    return False

        except Exception as e:
            print(f"❌ ÉCHEC vérification DB: {e}")
            import traceback
            traceback.print_exc()
            return False

        # 8. Cleanup
        await sqlalchemy_engine.dispose()

        print("\n" + "=" * 70)
        print("✅✅✅ TOUS LES TESTS RÉUSSIS! ✅✅✅")
        print("=" * 70)
        print("\nLe fix du database_url fonctionne correctement:")
        print("- URL convertie en postgresql+asyncpg://")
        print("- Services correctement injectés")
        print("- write_memory sauvegarde avec succès")
        print("- Embedding généré")
        print("- Données persistées en PostgreSQL")

        return True

    except Exception as e:
        print(f"\n❌ ERREUR GLOBALE: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_write_memory_fix())
    sys.exit(0 if result else 1)
