#!/usr/bin/env python3
"""
MCP Phase 2: Tests d'Intégration
Test cycles complets: Write → Read, Write → Search, etc.
"""

import asyncio
import sys
import os
import time
from datetime import datetime

os.chdir('/app')
sys.path.insert(0, '/app')


class MCPTestPhase2:
    """Tests d'intégration MCP - 5 scénarios"""

    def __init__(self):
        self.results = []
        self.failed = 0
        self.passed = 0
        self.created_ids = []  # Track created memories

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

    async def test_2_1_write_read_cycle(self):
        """Test 2.1: Write → Read Cycle"""
        test_id = "2.1"
        try:
            from mnemo_mcp.tools.memory_tools import WriteMemoryTool
            from services.embedding_service import MockEmbeddingService
            from db.repositories.memory_repository import MemoryRepository
            from sqlalchemy.ext.asyncio import create_async_engine

            # Setup
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

            # Step 1: Write
            write_result = await tool.execute(
                ctx=MockContext(),
                title="Test Integration 2.1: Write-Read",
                content="User: Test content\nClaude: Response content",
                memory_type="conversation",
                tags=["test", "phase2", "integration", "write-read"],
                author="Phase2TestSuite"
            )

            memory_id = write_result["id"]
            self.created_ids.append(memory_id)

            # Step 2: Read
            memory = await memory_repo.get_by_id(str(memory_id))

            # Verify
            assert memory is not None, "Memory not found after write"
            assert memory.title == "Test Integration 2.1: Write-Read", "Title mismatch"
            assert "test" in memory.tags, "Tags not preserved"
            assert memory.author == "Phase2TestSuite", "Author not preserved"
            assert "Test content" in memory.content, "Content not preserved"

            await engine.dispose()

            self.log(test_id, "PASS", "Write → Read cycle", {
                "memory_id": str(memory_id)[:8] + "...",
                "title_match": "✅",
                "tags_preserved": "✅",
                "author_preserved": "✅",
                "content_preserved": "✅"
            })
            self.passed += 1

        except Exception as e:
            self.log(test_id, "FAIL", f"Write-Read cycle failed: {e}")
            self.failed += 1

    async def test_2_2_write_search_read(self):
        """Test 2.2: Write → Search → Read"""
        test_id = "2.2"
        try:
            from mnemo_mcp.tools.memory_tools import WriteMemoryTool
            from services.embedding_service import MockEmbeddingService
            from db.repositories.memory_repository import MemoryRepository
            from mnemo_mcp.models.memory_models import MemoryFilters, MemoryType
            from sqlalchemy.ext.asyncio import create_async_engine

            # Setup
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

            # Step 1: Write avec keyword unique
            unique_keyword = f"UNIQUE_TEST_KEYWORD_{int(time.time())}"
            title = "Test Integration 2.2: Search Test"
            content = f"User: Test with {unique_keyword}\nClaude: Found keyword!"

            write_result = await tool.execute(
                ctx=MockContext(),
                title=title,
                content=content,
                memory_type="conversation",
                tags=["test", "phase2", "search", unique_keyword],
                author="Phase2TestSuite"
            )

            memory_id = write_result["id"]
            self.created_ids.append(memory_id)

            # Step 2: Search by vector (using same text that was embedded)
            # MockEmbeddingService is hash-based, so we need exact/similar text
            query_embedding = await emb_svc.generate_embedding(f"{title}\n\n{content}")
            search_results, total = await memory_repo.search_by_vector(
                vector=query_embedding,
                filters=MemoryFilters(memory_type=MemoryType.CONVERSATION),
                limit=10,
                distance_threshold=2.0
            )

            # Find our memory
            found = False
            for mem in search_results:
                if str(mem.id) == str(memory_id):
                    found = True
                    break

            assert found, f"Memory not found in search results (searched {total} results)"

            # Step 3: Verify found memory
            assert mem.title == "Test Integration 2.2: Search Test", "Title mismatch"
            # Tags are normalized to lowercase
            assert unique_keyword.lower() in mem.tags, "Keyword tag not found"

            await engine.dispose()

            self.log(test_id, "PASS", "Write → Search → Verify", {
                "memory_id": str(memory_id)[:8] + "...",
                "search_found": "✅",
                "semantic_search": "✅",
                "unique_keyword": unique_keyword[:20] + "..."
            })
            self.passed += 1

        except Exception as e:
            self.log(test_id, "FAIL", f"Write-Search-Read failed: {e}")
            self.failed += 1

    async def test_2_3_write_multiple_list_filtered(self):
        """Test 2.3: Write Multiple → List Filtered"""
        test_id = "2.3"
        try:
            from mnemo_mcp.tools.memory_tools import WriteMemoryTool
            from services.embedding_service import MockEmbeddingService
            from db.repositories.memory_repository import MemoryRepository
            from mnemo_mcp.models.memory_models import MemoryFilters
            from sqlalchemy.ext.asyncio import create_async_engine

            # Setup
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

            # Step 1: Write 3 memories with different tags
            unique_tag = f"test_2_3_{int(time.time())}"

            mem1 = await tool.execute(
                ctx=MockContext(),
                title="Test 2.3 Memory 1",
                content="Content 1",
                memory_type="conversation",
                tags=["test", unique_tag, "group-A"],
                author="Phase2TestSuite"
            )
            self.created_ids.append(mem1["id"])

            mem2 = await tool.execute(
                ctx=MockContext(),
                title="Test 2.3 Memory 2",
                content="Content 2",
                memory_type="conversation",
                tags=["test", unique_tag, "group-B"],
                author="Phase2TestSuite"
            )
            self.created_ids.append(mem2["id"])

            mem3 = await tool.execute(
                ctx=MockContext(),
                title="Test 2.3 Memory 3",
                content="Content 3",
                memory_type="conversation",
                tags=["test", unique_tag, "group-A"],
                author="Phase2TestSuite"
            )
            self.created_ids.append(mem3["id"])

            # Step 2: List filtered by unique_tag
            filters = MemoryFilters(tags=[unique_tag])
            memories, total = await memory_repo.list_memories(
                filters=filters,
                limit=10,
                offset=0
            )

            # Verify: Should find 3
            assert total >= 3, f"Expected >= 3 memories, got {total}"

            # Verify IDs present
            found_ids = {str(m.id) for m in memories}
            assert str(mem1["id"]) in found_ids, "Memory 1 not found"
            assert str(mem2["id"]) in found_ids, "Memory 2 not found"
            assert str(mem3["id"]) in found_ids, "Memory 3 not found"

            # Step 3: List filtered by group-A only
            filters_a = MemoryFilters(tags=["group-A"])
            memories_a, total_a = await memory_repo.list_memories(
                filters=filters_a,
                limit=10,
                offset=0
            )

            # Verify: Should find mem1 and mem3
            found_ids_a = {str(m.id) for m in memories_a}
            assert str(mem1["id"]) in found_ids_a, "Memory 1 not in group-A"
            assert str(mem3["id"]) in found_ids_a, "Memory 3 not in group-A"

            await engine.dispose()

            self.log(test_id, "PASS", "Write Multiple → List Filtered", {
                "created": "3 memories",
                "filtered_all": f"{total} found",
                "filtered_group_a": f"{total_a} found",
                "tag_filtering": "✅"
            })
            self.passed += 1

        except Exception as e:
            self.log(test_id, "FAIL", f"Write Multiple failed: {e}")
            self.failed += 1

    async def test_2_4_write_read_performance(self):
        """Test 2.4: Write → Read Performance (10x rapid)"""
        test_id = "2.4"
        try:
            from mnemo_mcp.tools.memory_tools import WriteMemoryTool
            from services.embedding_service import MockEmbeddingService
            from db.repositories.memory_repository import MemoryRepository
            from sqlalchemy.ext.asyncio import create_async_engine

            # Setup
            url = "postgresql+asyncpg://mnemo:mnemopass@db:5432/mnemolite"
            engine = create_async_engine(url, pool_size=5)
            memory_repo = MemoryRepository(engine)
            emb_svc = MockEmbeddingService(model_name="mock", dimension=768)

            tool = WriteMemoryTool()
            tool.inject_services({
                "memory_repository": memory_repo,
                "embedding_service": emb_svc
            })

            class MockContext:
                pass

            # Rapid write/read cycle
            start_time = time.time()
            ids = []

            for i in range(10):
                result = await tool.execute(
                    ctx=MockContext(),
                    title=f"Perf Test 2.4 #{i+1}",
                    content=f"Performance test iteration {i+1}",
                    memory_type="conversation",
                    tags=["test", "phase2", "performance", f"iter-{i+1}"],
                    author="Phase2TestSuite"
                )
                ids.append(result["id"])
                self.created_ids.append(result["id"])

                # Immediate read
                memory = await memory_repo.get_by_id(str(result["id"]))
                assert memory is not None, f"Memory {i+1} not readable immediately"

            total_time = (time.time() - start_time) * 1000  # ms
            avg_time = total_time / 10

            assert avg_time < 100, f"Average too slow: {avg_time:.2f}ms"

            await engine.dispose()

            self.log(test_id, "PASS", "Write → Read Performance (10x)", {
                "total_time_ms": f"{total_time:.2f}",
                "avg_time_ms": f"{avg_time:.2f}",
                "performance": f"✅ < 100ms avg",
                "created": "10 memories"
            })
            self.passed += 1

        except Exception as e:
            self.log(test_id, "FAIL", f"Performance test failed: {e}")
            self.failed += 1

    async def test_2_5_concurrent_writes(self):
        """Test 2.5: Concurrent Writes (5 parallel)"""
        test_id = "2.5"
        try:
            from mnemo_mcp.tools.memory_tools import WriteMemoryTool
            from services.embedding_service import MockEmbeddingService
            from db.repositories.memory_repository import MemoryRepository
            from sqlalchemy.ext.asyncio import create_async_engine

            # Setup
            url = "postgresql+asyncpg://mnemo:mnemopass@db:5432/mnemolite"
            engine = create_async_engine(url, pool_size=5)
            memory_repo = MemoryRepository(engine)
            emb_svc = MockEmbeddingService(model_name="mock", dimension=768)

            tool = WriteMemoryTool()
            tool.inject_services({
                "memory_repository": memory_repo,
                "embedding_service": emb_svc
            })

            class MockContext:
                pass

            # Concurrent writes
            async def write_one(i):
                result = await tool.execute(
                    ctx=MockContext(),
                    title=f"Concurrent Test 2.5 #{i+1}",
                    content=f"Concurrent write {i+1}",
                    memory_type="conversation",
                    tags=["test", "phase2", "concurrent", f"thread-{i+1}"],
                    author="Phase2TestSuite"
                )
                self.created_ids.append(result["id"])
                return result["id"]

            start_time = time.time()
            ids = await asyncio.gather(*[write_one(i) for i in range(5)])
            total_time = (time.time() - start_time) * 1000

            # Verify all created
            assert len(ids) == 5, f"Expected 5 IDs, got {len(ids)}"
            assert len(set(str(id) for id in ids)) == 5, "Duplicate IDs detected"

            # Verify all readable
            for memory_id in ids:
                memory = await memory_repo.get_by_id(str(memory_id))
                assert memory is not None, f"Memory {memory_id} not found"

            await engine.dispose()

            self.log(test_id, "PASS", "Concurrent Writes (5 parallel)", {
                "total_time_ms": f"{total_time:.2f}",
                "all_created": "✅",
                "all_readable": "✅",
                "no_duplicates": "✅"
            })
            self.passed += 1

        except Exception as e:
            self.log(test_id, "FAIL", f"Concurrent writes failed: {e}")
            self.failed += 1

    async def run_all_tests(self):
        """Run all Phase 2 tests"""
        print("=" * 70)
        print("MCP PHASE 2: TESTS D'INTÉGRATION")
        print("Test cycles: Write → Read → Search → Verify")
        print("=" * 70)
        print()

        tests = [
            self.test_2_1_write_read_cycle,
            self.test_2_2_write_search_read,
            self.test_2_3_write_multiple_list_filtered,
            self.test_2_4_write_read_performance,
            self.test_2_5_concurrent_writes,
        ]

        for test in tests:
            print(f"\n--- Running {test.__name__} ---")
            await test()
            await asyncio.sleep(0.2)  # Avoid overwhelming DB

        # Summary
        print("\n" + "=" * 70)
        print("RÉSULTATS PHASE 2")
        print("=" * 70)
        print(f"Tests passés:  {self.passed}/{len(tests)}")
        print(f"Tests échoués: {self.failed}/{len(tests)}")
        print(f"Success rate:  {(self.passed/len(tests)*100):.1f}%")
        print(f"Memories créées: {len(self.created_ids)}")
        print()

        if self.failed > 0:
            print("⚠️  DES TESTS ONT ÉCHOUÉ - Vérifier les erreurs ci-dessus")
            return False
        else:
            print("✅ TOUS LES TESTS SONT PASSÉS!")
            return True


async def main():
    test_suite = MCPTestPhase2()
    success = await test_suite.run_all_tests()
    sys.exit(0 if success else 1)


class MockContext:
    pass


if __name__ == "__main__":
    asyncio.run(main())
