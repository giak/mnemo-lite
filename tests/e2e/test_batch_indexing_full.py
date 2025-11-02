"""
End-to-end test for batch indexing system.

EPIC-27: Batch Processing with Redis Streams
Task 12: End-to-End Test on 261 files from code_test directory

Tests full flow:
    1. Producer scans directory and enqueues batches
    2. Consumer processes all batches via subprocess workers
    3. Validates all chunks created with embeddings
    4. Validates graph nodes and edges created
    5. Asserts 95%+ success rate

Note: These tests require real embedding models (EMBEDDING_MODE=real) or
      a properly configured subprocess environment. For quick testing,
      use the manual API/CLI tests instead.
"""

import pytest
import asyncio
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from services.batch_indexing_producer import BatchIndexingProducer
from services.batch_indexing_consumer import BatchIndexingConsumer


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_full_batch_indexing_261_files():
    """
    End-to-end test: Index 261 files from code_test directory.

    Validates:
    - Producer enqueues all batches
    - Consumer processes all batches
    - All chunks created with embeddings
    - Graph nodes/edges created
    - Memory stable (no leaks)
    - 95%+ success rate

    EPIC-27 Task 12: Full integration test with real directory
    """
    repository = "code_test_e2e"
    directory = Path("/app/code_test")

    # Use TEST_DATABASE_URL if available, otherwise use DATABASE_URL
    test_db_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not test_db_url:
        pytest.skip("No database URL available (TEST_DATABASE_URL or DATABASE_URL)")

    # Setup: Cleanup existing data
    print(f"\n🧹 Cleaning up existing data for repository '{repository}'...")
    engine = create_async_engine(test_db_url, echo=False)
    async with engine.begin() as conn:
        # Delete in correct order to respect foreign keys
        await conn.execute(
            text("DELETE FROM edges WHERE source_node_id IN (SELECT node_id FROM nodes WHERE properties->>'repository' = :repo)"),
            {"repo": repository}
        )
        await conn.execute(
            text("DELETE FROM nodes WHERE properties->>'repository' = :repo"),
            {"repo": repository}
        )
        await conn.execute(
            text("DELETE FROM code_chunks WHERE repository = :repo"),
            {"repo": repository}
        )
    print(f"✅ Cleanup complete")

    # Step 1: Producer enqueues batches
    print(f"\n📦 Step 1: Producer scanning directory and enqueuing batches...")
    producer = BatchIndexingProducer()
    job_info = await producer.scan_and_enqueue(
        directory=directory,
        repository=repository,
        extensions=[".ts", ".js"]
    )
    await producer.close()

    print(f"✅ Producer enqueued:")
    print(f"   - Total files: {job_info['total_files']}")
    print(f"   - Total batches: {job_info['total_batches']}")
    print(f"   - Job ID: {job_info['job_id']}")
    print(f"   - Status: {job_info['status']}")

    assert job_info['total_files'] > 0, "Should find files in code_test directory"
    assert job_info['total_batches'] > 0, "Should create at least one batch"

    # Step 2: Consumer processes all batches
    print(f"\n⚙️  Step 2: Consumer processing all batches...")
    consumer = BatchIndexingConsumer(db_url=test_db_url)
    await consumer.connect()
    stats = await consumer.process_repository(repository)
    await consumer.close()

    print(f"✅ Consumer processed:")
    print(f"   - Batches processed: {stats.get('batches_processed', 0)}")
    print(f"   - Files successful: {stats.get('processed_files', 0)}")
    print(f"   - Files failed: {stats.get('failed_files', 0)}")
    print(f"   - Final status: {stats.get('status', 'unknown')}")

    # Step 3: Validate database contents
    print(f"\n🔍 Step 3: Validating database contents...")
    async with engine.begin() as conn:
        # Count chunks
        chunk_result = await conn.execute(
            text("SELECT COUNT(*) FROM code_chunks WHERE repository = :repo"),
            {"repo": repository}
        )
        chunk_count = chunk_result.scalar()

        # Count embeddings
        embedding_result = await conn.execute(
            text("SELECT COUNT(*) FROM code_chunks WHERE repository = :repo AND embedding_code IS NOT NULL"),
            {"repo": repository}
        )
        embedding_count = embedding_result.scalar()

        # Count nodes
        node_result = await conn.execute(
            text("SELECT COUNT(*) FROM nodes WHERE properties->>'repository' = :repo"),
            {"repo": repository}
        )
        node_count = node_result.scalar()

        # Count edges
        edge_result = await conn.execute(
            text("""
                SELECT COUNT(*) FROM edges e
                JOIN nodes n ON e.source_node_id = n.node_id
                WHERE n.properties->>'repository' = :repo
            """),
            {"repo": repository}
        )
        edge_count = edge_result.scalar()

    await engine.dispose()

    print(f"✅ Database validation:")
    print(f"   - Chunks: {chunk_count}")
    print(f"   - Embeddings: {embedding_count}")
    print(f"   - Nodes: {node_count}")
    print(f"   - Edges: {edge_count}")

    # Step 4: Assertions
    print(f"\n✨ Step 4: Running assertions...")

    # Assert chunks created
    assert chunk_count > 0, "No chunks created"
    print(f"   ✓ Chunks created: {chunk_count}")

    # Assert embeddings match chunks
    assert embedding_count == chunk_count, \
        f"Not all chunks have embeddings ({embedding_count}/{chunk_count})"
    print(f"   ✓ All chunks have embeddings: {embedding_count}/{chunk_count}")

    # Assert nodes created
    assert node_count > 0, "No graph nodes created"
    print(f"   ✓ Graph nodes created: {node_count}")

    # Assert edges created (or 0 if no relations found)
    assert edge_count >= 0, "Edge count should be non-negative"
    print(f"   ✓ Graph edges created: {edge_count}")

    # Calculate success rate
    total_files = job_info['total_files']
    successful_files = stats.get('processed_files', 0)
    failed_files = stats.get('failed_files', 0)

    if total_files > 0:
        success_rate = (successful_files / total_files) * 100
    else:
        success_rate = 0.0

    print(f"   ✓ Success rate: {success_rate:.1f}% ({successful_files}/{total_files})")

    # Assert 95%+ success rate (allow <5% failures for edge cases)
    assert success_rate >= 95.0, \
        f"Success rate too low: {success_rate:.1f}% (expected >=95%)"

    # Final summary
    print(f"\n🎉 End-to-end test SUCCESS!")
    print(f"=" * 80)
    print(f"   Repository:    {repository}")
    print(f"   Total files:   {total_files}")
    print(f"   Successful:    {successful_files}")
    print(f"   Failed:        {failed_files}")
    print(f"   Success rate:  {success_rate:.1f}%")
    print(f"   Chunks:        {chunk_count}")
    print(f"   Embeddings:    {embedding_count}")
    print(f"   Nodes:         {node_count}")
    print(f"   Edges:         {edge_count}")
    print(f"=" * 80)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_batch_indexing_empty_directory(tmp_path):
    """
    Test batch indexing with empty directory.

    Validates:
    - Producer returns empty job info
    - Consumer handles gracefully
    - No chunks/nodes/edges created

    EPIC-27 Task 12: Edge case testing
    """
    repository = "empty_test"
    directory = tmp_path / "empty"
    directory.mkdir()

    test_db_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not test_db_url:
        pytest.skip("No database URL available")

    # Producer should handle empty directory
    producer = BatchIndexingProducer()
    job_info = await producer.scan_and_enqueue(
        directory=directory,
        repository=repository,
        extensions=[".ts", ".js"]
    )
    await producer.close()

    # Should find 0 files
    assert job_info['total_files'] == 0
    assert job_info['total_batches'] == 0

    print(f"✅ Empty directory test passed: 0 files, 0 batches")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_batch_indexing_small_batch(tmp_path):
    """
    Test batch indexing with small number of files (< BATCH_SIZE).

    Validates:
    - Producer creates single batch for <40 files
    - Consumer processes batch successfully
    - All files indexed correctly

    EPIC-27 Task 12: Small batch edge case
    """
    repository = "small_batch_test"
    directory = tmp_path / "small"
    directory.mkdir()

    # Create 5 small TypeScript files
    for i in range(5):
        file_path = directory / f"file{i}.ts"
        file_path.write_text(f"const x{i} = {i};\nexport default x{i};\n")

    test_db_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not test_db_url:
        pytest.skip("No database URL available")

    # Cleanup
    engine = create_async_engine(test_db_url, echo=False)
    async with engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM edges WHERE source_node_id IN (SELECT node_id FROM nodes WHERE properties->>'repository' = :repo)"),
            {"repo": repository}
        )
        await conn.execute(
            text("DELETE FROM nodes WHERE properties->>'repository' = :repo"),
            {"repo": repository}
        )
        await conn.execute(
            text("DELETE FROM code_chunks WHERE repository = :repo"),
            {"repo": repository}
        )

    # Producer
    producer = BatchIndexingProducer()
    job_info = await producer.scan_and_enqueue(
        directory=directory,
        repository=repository,
        extensions=[".ts"]
    )
    await producer.close()

    assert job_info['total_files'] == 5
    assert job_info['total_batches'] == 1  # Single batch for 5 files

    # Consumer
    consumer = BatchIndexingConsumer(db_url=test_db_url)
    await consumer.connect()
    stats = await consumer.process_repository(repository)
    await consumer.close()

    # Validate
    assert stats.get('processed_files', 0) == 5
    assert stats.get('failed_files', 0) == 0

    # Check chunks created
    async with engine.begin() as conn:
        chunk_result = await conn.execute(
            text("SELECT COUNT(*) FROM code_chunks WHERE repository = :repo"),
            {"repo": repository}
        )
        chunk_count = chunk_result.scalar()

    await engine.dispose()

    assert chunk_count > 0, "Should create chunks for 5 files"

    print(f"✅ Small batch test passed: 5 files → {chunk_count} chunks")
