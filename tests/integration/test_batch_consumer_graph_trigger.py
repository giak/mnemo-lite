# tests/integration/test_batch_consumer_graph_trigger.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from services.batch_indexing_consumer import BatchIndexingConsumer
from services.batch_indexing_producer import BatchIndexingProducer
from pathlib import Path
import os
import asyncio
import shutil


@pytest.mark.asyncio
async def test_consumer_triggers_graph_with_correct_languages():
    """Test that consumer triggers graph construction with typescript/javascript."""
    # Setup
    db_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    redis_url = "redis://redis:6379/0"
    test_repo = "test_graph_trigger"

    # Create test directory with TypeScript file
    test_dir = Path("/tmp/test_graph_trigger")
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(exist_ok=True)

    # Create a non-trivial TypeScript file that will generate chunks
    (test_dir / "calculator.ts").write_text("""
export class Calculator {
    add(a: number, b: number): number {
        return a + b;
    }

    subtract(a: number, b: number): number {
        return a - b;
    }

    multiply(a: number, b: number): number {
        return a * b;
    }
}

export function createCalculator(): Calculator {
    return new Calculator();
}
""")

    try:
        # Cleanup existing data
        engine = create_async_engine(db_url)
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM code_chunks WHERE repository = :repo"), {"repo": test_repo})
            await conn.execute(text("DELETE FROM nodes WHERE properties->>'repo' = :repo"), {"repo": test_repo})
        await engine.dispose()

        # Start producer
        producer = BatchIndexingProducer(redis_url=redis_url)
        await producer.connect()
        job_info = await producer.scan_and_enqueue(test_dir, test_repo, [".ts", ".js"])
        await producer.close()

        assert job_info["total_files"] == 1, f"Expected 1 file, got {job_info['total_files']}"

        # Run consumer (will trigger graph)
        consumer = BatchIndexingConsumer(redis_url=redis_url, db_url=db_url)
        await consumer.connect()
        stats = await consumer.process_repository(test_repo)
        await consumer.close()

        # Small delay to ensure all async transactions complete
        await asyncio.sleep(0.5)

        # Verify: Chunks were created
        engine = create_async_engine(db_url)
        async with engine.begin() as conn:
            chunk_count = await conn.execute(
                text("SELECT COUNT(*) FROM code_chunks WHERE repository = :repo"),
                {"repo": test_repo}
            )
            chunks = chunk_count.scalar()

            # Verify languages detected
            lang_result = await conn.execute(
                text("SELECT DISTINCT language FROM code_chunks WHERE repository = :repo"),
                {"repo": test_repo}
            )
            languages = [row.language for row in lang_result]

            # Verify graph nodes created
            node_count = await conn.execute(
                text("SELECT COUNT(*) FROM nodes WHERE properties->>'repository' = :repo"),
                {"repo": test_repo}
            )
            nodes = node_count.scalar()

        await engine.dispose()

        # Assertions
        assert chunks > 0, f"Expected chunks to be created, got {chunks}"
        assert "typescript" in languages, f"Expected typescript in languages, got {languages}"
        assert nodes > 0, f"Graph should be created automatically, got {nodes} nodes"

    finally:
        # Cleanup
        shutil.rmtree(test_dir, ignore_errors=True)
