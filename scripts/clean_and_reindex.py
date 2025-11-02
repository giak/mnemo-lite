"""
Clean database and re-index code_test with fixes applied.

Usage:
    python scripts/clean_and_reindex.py --repository code_test_clean
"""

import asyncio
import argparse
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import sys

# Add api to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))


async def clean_repository(repository: str, db_url: str):
    """Remove all data for a repository."""
    engine = create_async_engine(db_url)

    print(f"🧹 Cleaning repository '{repository}'...")

    async with engine.begin() as conn:
        # Delete chunks
        result = await conn.execute(
            text("DELETE FROM code_chunks WHERE repository = :repo"),
            {"repo": repository}
        )
        chunks_deleted = result.rowcount

        # Delete nodes
        result = await conn.execute(
            text("DELETE FROM nodes WHERE properties->>'repo' = :repo"),
            {"repo": repository}
        )
        nodes_deleted = result.rowcount

        # Edges cascade delete automatically

        print(f"  ✓ Deleted {chunks_deleted} chunks")
        print(f"  ✓ Deleted {nodes_deleted} nodes")

    await engine.dispose()
    print(f"✅ Cleanup complete for '{repository}'")


async def verify_clean(repository: str, db_url: str):
    """Verify repository is clean."""
    engine = create_async_engine(db_url)

    async with engine.begin() as conn:
        chunks = await conn.execute(
            text("SELECT COUNT(*) FROM code_chunks WHERE repository = :repo"),
            {"repo": repository}
        )
        chunk_count = chunks.scalar()

        nodes = await conn.execute(
            text("SELECT COUNT(*) FROM nodes WHERE properties->>'repo' = :repo"),
            {"repo": repository}
        )
        node_count = nodes.scalar()

    await engine.dispose()

    assert chunk_count == 0, f"Expected 0 chunks, found {chunk_count}"
    assert node_count == 0, f"Expected 0 nodes, found {node_count}"

    print(f"✅ Verified: '{repository}' is clean (0 chunks, 0 nodes)")


def main():
    parser = argparse.ArgumentParser(description="Clean repository data")
    parser.add_argument("--repository", required=True, help="Repository name to clean")
    parser.add_argument("--db-url", help="Database URL (default: from env)")
    args = parser.parse_args()

    db_url = args.db_url or os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ ERROR: DATABASE_URL not set")
        sys.exit(1)

    # Run cleanup
    asyncio.run(clean_repository(args.repository, db_url))
    asyncio.run(verify_clean(args.repository, db_url))

    print(f"""
✅ Repository cleaned successfully!

Next steps:
1. Start batch indexing:
   curl -X POST http://localhost:8001/api/v1/indexing/batch/start \\
     -H "Content-Type: application/json" \\
     -d '{{"directory": "/app/code_test", "repository": "{args.repository}", "extensions": [".ts", ".js"]}}'

2. Start consumer:
   docker exec -d mnemo-api python /app/scripts/batch_index_consumer.py \\
     --repository {args.repository} --verbose

3. Monitor progress:
   curl http://localhost:8001/api/v1/indexing/batch/status/{args.repository} | jq
""")


if __name__ == "__main__":
    main()
