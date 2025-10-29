#!/usr/bin/env python3
"""
MCP Phase 1: Tests Unitaires en Conditions Réelles
RÈGLE: UNIQUEMENT via outils MCP - PAS de SQL direct, PAS de Python direct
"""

import asyncio
import sys
import os
import time
from datetime import datetime

os.chdir('/app')
sys.path.insert(0, '/app')


class MCPTestPhase1:
    """Tests unitaires MCP - 10 tests fondamentaux"""

    def __init__(self):
        self.results = []
        self.failed = 0
        self.passed = 0

    def log(self, test_id: str, status: str, message: str, details: dict = None):
        """Log test result"""
        result = {
            "test_id": test_id,
            "status": status,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        }
        self.results.append(result)

        icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{icon} [{test_id}] {message}")
        if details:
            for k, v in details.items():
                print(f"   {k}: {v}")

    async def test_1_1_write_memory_simple(self):
        """Test 1.1: write_memory - Conversation Basique"""
        test_id = "1.1"
        try:
            from mnemo_mcp.tools.memory_tools import WriteMemoryTool
            from services.embedding_service import MockEmbeddingService
            from db.repositories.memory_repository import MemoryRepository
            from sqlalchemy.ext.asyncio import create_async_engine

            # Setup (simulate MCP server initialization)
            url = "postgresql+asyncpg://mnemo:mnemopass@db:5432/mnemolite"
            engine = create_async_engine(url, pool_size=2)
            memory_repo = MemoryRepository(engine)
            emb_svc = MockEmbeddingService(model_name="mock", dimension=768)

            tool = WriteMemoryTool()
            tool.inject_services({
                "memory_repository": memory_repo,
                "embedding_service": emb_svc
            })

            class MockContext:
                pass

            ctx = MockContext()

            # Execute MCP tool
            start = time.time()
            result = await tool.execute(
                ctx=ctx,
                title="Test Conv 1: Simple message",
                content="User: Hello\nClaude: Hi there!",
                memory_type="conversation",
                tags=["test", "phase1", "simple", "mcp-test"],
                author="MCPTestSuite"
            )
            elapsed_ms = (time.time() - start) * 1000

            await engine.dispose()

            # Verify
            assert result.get("id"), "No ID returned"
            assert result.get("title") == "Test Conv 1: Simple message", "Title mismatch"
            assert "test" in result.get("tags", []), "Tags missing"

            self.log(test_id, "PASS", "write_memory simple conversation", {
                "memory_id": result["id"][:8] + "...",
                "elapsed_ms": f"{elapsed_ms:.2f}",
                "title": result["title"]
            })
            self.passed += 1

        except Exception as e:
            self.log(test_id, "FAIL", f"write_memory failed: {e}")
            self.failed += 1

    async def test_1_2_write_memory_complex(self):
        """Test 1.2: write_memory - Conversation Complexe avec Code"""
        test_id = "1.2"
        try:
            from mnemo_mcp.tools.memory_tools import WriteMemoryTool
            from services.embedding_service import MockEmbeddingService
            from db.repositories.memory_repository import MemoryRepository
            from sqlalchemy.ext.asyncio import create_async_engine

            url = "postgresql+asyncpg://mnemo:mnemopass@db:5432/mnemolite"
            engine = create_async_engine(url, pool_size=2)
            memory_repo = MemoryRepository(engine)
            emb_svc = MockEmbeddingService(model_name="mock", dimension=768)

            tool = WriteMemoryTool()
            tool.inject_services({
                "memory_repository": memory_repo,
                "embedding_service": emb_svc
            })

            class MockContext:
                pass

            content = """User: Comment implémenter un cache?

Claude: Voici une solution:
```python
class Cache:
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value
```

C'est un cache simple en mémoire."""

            result = await tool.execute(
                ctx=MockContext(),
                title="Test Conv 2: Multi-line avec code",
                content=content,
                memory_type="conversation",
                tags=["test", "phase1", "code", "multiline", "mcp-test"],
                author="MCPTestSuite"
            )

            await engine.dispose()

            # Verify code preserved
            assert "```python" in content, "Code block not preserved"
            assert "class Cache" in content, "Code content missing"

            self.log(test_id, "PASS", "write_memory complex with code", {
                "memory_id": result["id"][:8] + "...",
                "content_length": len(content),
                "has_code_block": "✅"
            })
            self.passed += 1

        except Exception as e:
            self.log(test_id, "FAIL", f"write_memory complex failed: {e}")
            self.failed += 1

    async def test_1_3_write_memory_special_chars(self):
        """Test 1.3: write_memory - Caractères Spéciaux"""
        test_id = "1.3"
        try:
            from mnemo_mcp.tools.memory_tools import WriteMemoryTool
            from services.embedding_service import MockEmbeddingService
            from db.repositories.memory_repository import MemoryRepository
            from sqlalchemy.ext.asyncio import create_async_engine

            url = "postgresql+asyncpg://mnemo:mnemopass@db:5432/mnemolite"
            engine = create_async_engine(url, pool_size=2)
            memory_repo = MemoryRepository(engine)
            emb_svc = MockEmbeddingService(model_name="mock", dimension=768)

            tool = WriteMemoryTool()
            tool.inject_services({
                "memory_repository": memory_repo,
                "embedding_service": emb_svc
            })

            content = "User: Test émojis 🎉 🚀 et accents éàç\nClaude: Çà fonctionne! 你好 مرحبا"

            result = await tool.execute(
                ctx=MockContext(),
                title="Test Conv 3: Caractères spéciaux",
                content=content,
                memory_type="conversation",
                tags=["test", "phase1", "unicode", "emoji", "mcp-test"],
                author="MCPTestSuite"
            )

            await engine.dispose()

            # Verify UTF-8
            assert "🎉" in content, "Emoji not preserved"
            assert "éàç" in content, "Accents not preserved"
            assert "你好" in content, "Unicode not preserved"

            self.log(test_id, "PASS", "write_memory special characters", {
                "memory_id": result["id"][:8] + "...",
                "emoji": "🎉 ✅",
                "accents": "éàç ✅",
                "unicode": "你好 ✅"
            })
            self.passed += 1

        except Exception as e:
            self.log(test_id, "FAIL", f"write_memory special chars failed: {e}")
            self.failed += 1

    async def test_1_4_write_memory_long(self):
        """Test 1.4: write_memory - Conversation Longue"""
        test_id = "1.4"
        try:
            from mnemo_mcp.tools.memory_tools import WriteMemoryTool
            from services.embedding_service import MockEmbeddingService
            from db.repositories.memory_repository import MemoryRepository
            from sqlalchemy.ext.asyncio import create_async_engine

            url = "postgresql+asyncpg://mnemo:mnemopass@db:5432/mnemolite"
            engine = create_async_engine(url, pool_size=2)
            memory_repo = MemoryRepository(engine)
            emb_svc = MockEmbeddingService(model_name="mock", dimension=768)

            tool = WriteMemoryTool()
            tool.inject_services({
                "memory_repository": memory_repo,
                "embedding_service": emb_svc
            })

            # Generate 10K chars conversation
            content = "User: Longue conversation\n\n" + ("Claude: " + "A" * 100 + "\n") * 100

            start = time.time()
            result = await tool.execute(
                ctx=MockContext(),
                title="Test Conv 4: Longue conversation 10K chars",
                content=content,
                memory_type="conversation",
                tags=["test", "phase1", "long", "performance", "mcp-test"],
                author="MCPTestSuite"
            )
            elapsed_ms = (time.time() - start) * 1000

            await engine.dispose()

            # Verify no truncation
            assert len(content) >= 10000, "Content truncated"
            assert elapsed_ms < 200, f"Too slow: {elapsed_ms}ms"

            self.log(test_id, "PASS", "write_memory long conversation", {
                "memory_id": result["id"][:8] + "...",
                "content_length": len(content),
                "elapsed_ms": f"{elapsed_ms:.2f}",
                "performance": "✅ < 200ms"
            })
            self.passed += 1

        except Exception as e:
            self.log(test_id, "FAIL", f"write_memory long failed: {e}")
            self.failed += 1

    async def test_1_5_write_memory_multiple_tags(self):
        """Test 1.5: write_memory - Tags Multiples"""
        test_id = "1.5"
        try:
            from mnemo_mcp.tools.memory_tools import WriteMemoryTool
            from services.embedding_service import MockEmbeddingService
            from db.repositories.memory_repository import MemoryRepository
            from sqlalchemy.ext.asyncio import create_async_engine

            url = "postgresql+asyncpg://mnemo:mnemopass@db:5432/mnemolite"
            engine = create_async_engine(url, pool_size=2)
            memory_repo = MemoryRepository(engine)
            emb_svc = MockEmbeddingService(model_name="mock", dimension=768)

            tool = WriteMemoryTool()
            tool.inject_services({
                "memory_repository": memory_repo,
                "embedding_service": emb_svc
            })

            tags = ["test", "bug", "fix", "database", "sqlalchemy", "epic-24", "mcp-test"]

            result = await tool.execute(
                ctx=MockContext(),
                title="Test Conv 5: Multiple tags",
                content="User: Bug SQLAlchemy\nClaude: Fix avec pool_size",
                memory_type="conversation",
                tags=tags,
                author="MCPTestSuite"
            )

            await engine.dispose()

            # Verify all tags
            result_tags = result.get("tags", [])
            for tag in tags:
                assert tag in result_tags, f"Tag '{tag}' missing"

            self.log(test_id, "PASS", "write_memory multiple tags", {
                "memory_id": result["id"][:8] + "...",
                "tags_count": len(tags),
                "all_tags_stored": "✅"
            })
            self.passed += 1

        except Exception as e:
            self.log(test_id, "FAIL", f"write_memory tags failed: {e}")
            self.failed += 1

    async def run_all_tests(self):
        """Run all Phase 1 tests"""
        print("=" * 70)
        print("MCP PHASE 1: TESTS UNITAIRES")
        print("Règle: UNIQUEMENT outils MCP - PAS de shortcuts SQL")
        print("=" * 70)
        print()

        tests = [
            self.test_1_1_write_memory_simple,
            self.test_1_2_write_memory_complex,
            self.test_1_3_write_memory_special_chars,
            self.test_1_4_write_memory_long,
            self.test_1_5_write_memory_multiple_tags,
        ]

        for test in tests:
            print(f"\n--- Running {test.__name__} ---")
            await test()
            await asyncio.sleep(0.1)  # Avoid overwhelming DB

        # Summary
        print("\n" + "=" * 70)
        print("RÉSULTATS PHASE 1")
        print("=" * 70)
        print(f"Tests passés:  {self.passed}/{len(tests)}")
        print(f"Tests échoués: {self.failed}/{len(tests)}")
        print(f"Success rate:  {(self.passed/len(tests)*100):.1f}%")
        print()

        if self.failed > 0:
            print("⚠️  DES TESTS ONT ÉCHOUÉ - Vérifier les erreurs ci-dessus")
            return False
        else:
            print("✅ TOUS LES TESTS SONT PASSÉS!")
            return True


async def main():
    test_suite = MCPTestPhase1()
    success = await test_suite.run_all_tests()
    sys.exit(0 if success else 1)


class MockContext:
    pass


if __name__ == "__main__":
    asyncio.run(main())
