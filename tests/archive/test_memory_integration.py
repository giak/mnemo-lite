"""
Quick integration test for Memory Tools & Resources.
Tests write_memory, get_memory, list_memories, search_memories.
"""

import asyncio
import sys
sys.path.insert(0, 'api')

from sqlalchemy.ext.asyncio import create_async_engine
from db.repositories.memory_repository import MemoryRepository
from mnemo_mcp.models.memory_models import MemoryCreate, MemoryType
from services.embedding_service import MockEmbeddingService


async def test_memory_crud():
    """Test basic CRUD operations on memories."""

    # Setup
    DATABASE_URL = "postgresql+asyncpg://mnemo:mnemopass@localhost:5432/mnemolite"
    engine = create_async_engine(DATABASE_URL)
    repository = MemoryRepository(engine)
    embedding_service = MockEmbeddingService(model_name="mock-model", dimension=768)

    print("🧪 Testing Memory CRUD Operations...\n")

    # Test 1: Create memory
    print("1️⃣ Creating memory...")
    memory_create = MemoryCreate(
        title="Test memory: User prefers async/await",
        content="User mentioned preferring async/await over callbacks for Python async code",
        memory_type=MemoryType.NOTE,
        tags=["test", "python", "async"],
        author="Claude Test"
    )

    embedding = await embedding_service.generate_embedding(
        f"{memory_create.title}\n\n{memory_create.content}"
    )

    created_memory = await repository.create(memory_create, embedding)
    print(f"   ✅ Created: {created_memory.id} - '{created_memory.title}'")
    print(f"   ✅ Tags: {created_memory.tags}")
    print(f"   ✅ Embedding: {len(created_memory.embedding) if created_memory.embedding else 0}D")

    # Test 2: Get by ID
    print("\n2️⃣ Getting memory by ID...")
    fetched_memory = await repository.get_by_id(str(created_memory.id))
    assert fetched_memory is not None
    assert fetched_memory.title == created_memory.title
    print(f"   ✅ Fetched: '{fetched_memory.title}'")

    # Test 3: List memories
    print("\n3️⃣ Listing memories...")
    memories, total = await repository.list_memories(limit=10, offset=0)
    print(f"   ✅ Found {len(memories)} memories (total: {total})")
    for mem in memories[:3]:
        print(f"      - {mem.id}: {mem.title}")

    # Test 4: Vector search
    print("\n4️⃣ Searching memories by vector...")
    search_query = "async patterns"
    search_embedding = await embedding_service.generate_embedding(search_query)
    search_results, search_total = await repository.search_by_vector(
        vector=search_embedding,
        limit=5,
        distance_threshold=1.0
    )
    print(f"   ✅ Found {len(search_results)} results for '{search_query}'")
    for result in search_results:
        print(f"      - {result.title} (similarity: {result.similarity_score:.3f})")

    # Test 5: Update memory
    print("\n5️⃣ Updating memory...")
    from mnemo_mcp.models.memory_models import MemoryUpdate
    memory_update = MemoryUpdate(tags=["test", "python", "async", "updated"])
    updated_memory = await repository.update(
        str(created_memory.id),
        memory_update,
        regenerate_embedding=False
    )
    assert updated_memory is not None
    print(f"   ✅ Updated tags: {updated_memory.tags}")

    # Test 6: Soft delete
    print("\n6️⃣ Soft deleting memory...")
    success = await repository.soft_delete(str(created_memory.id))
    assert success
    print(f"   ✅ Soft deleted: {created_memory.id}")

    # Test 7: Verify soft delete
    print("\n7️⃣ Verifying soft delete...")
    deleted_memory = await repository.get_by_id(str(created_memory.id))
    assert deleted_memory is None  # Should not be found (deleted_at is set)
    print(f"   ✅ Memory no longer accessible (soft deleted)")

    # Test 8: Permanent delete
    print("\n8️⃣ Permanently deleting memory...")
    success = await repository.delete_permanently(str(created_memory.id))
    assert success
    print(f"   ✅ Permanently deleted: {created_memory.id}")

    print("\n✅ All tests passed!")

    # Cleanup
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(test_memory_crud())
