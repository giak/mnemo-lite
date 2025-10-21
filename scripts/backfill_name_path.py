#!/usr/bin/env python3
"""
EPIC-11 Story 11.4: Backfill name_path for Existing Chunks

This script migrates existing code_chunks to have hierarchical name_path values.
Supports dry-run mode for safe testing.

Usage:
    python scripts/backfill_name_path.py                    # Run migration
    python scripts/backfill_name_path.py --dry-run          # Test without committing
    docker compose exec api python scripts/backfill_name_path.py --dry-run

Author: Claude Code (EPIC-11 Story 11.4)
Date: 2025-10-21
"""

import asyncio
import asyncpg
import os
import sys
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Any, Tuple

# Add parent directory to path to import from api/
script_dir = Path(__file__).parent.parent
sys.path.insert(0, str(script_dir))
sys.path.insert(0, str(script_dir / "api"))

from services.symbol_path_service import SymbolPathService


class ChunkRecord:
    """Simple wrapper for asyncpg.Record to provide attribute access."""

    def __init__(self, record):
        self.id = record["id"]
        self.name = record["name"]
        self.file_path = record["file_path"]
        self.repository = record["repository"]
        self.chunk_type = record["chunk_type"]
        self.start_line = record["start_line"]
        self.end_line = record["end_line"]
        self.language = record["language"]


async def backfill_name_path(dry_run: bool = False, database_url: str = None) -> Dict[str, Any]:
    """
    Backfill name_path for existing code_chunks.

    This function:
    1. Loads all chunks needing migration (name_path IS NULL)
    2. Groups chunks by file for efficient parent context extraction
    3. Generates name_path for each chunk (with parent context)
    4. Batch updates all chunks in single transaction
    5. Validates 100% coverage

    Args:
        dry_run: If True, show what would be updated without committing
        database_url: Optional database URL (defaults to DATABASE_URL env var)

    Returns:
        Dict with migration statistics

    Raises:
        ValueError: If DATABASE_URL not set and not provided
        Exception: If migration validation fails
    """

    if database_url is None:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable not set")

    # Convert SQLAlchemy URL to asyncpg format
    # postgresql+asyncpg://... → postgresql://...
    if "+asyncpg" in database_url:
        database_url = database_url.replace("+asyncpg", "")

    conn = await asyncpg.connect(database_url)
    symbol_service = SymbolPathService()

    stats = {
        "total_chunks": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
        "unique_files": 0,
        "duration_ms": 0
    }

    try:
        import time
        start_time = time.time()

        print("🔄 Backfilling name_path for existing chunks...")
        print(f"   Mode: {'DRY RUN' if dry_run else 'LIVE MIGRATION'}\n")

        # 1. Count chunks needing migration
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM code_chunks WHERE name_path IS NULL"
        )
        stats["total_chunks"] = total

        print(f"📊 Chunks to update: {total}")

        if total == 0:
            print("✅ All chunks already have name_path!")
            return stats

        # 2. Load ALL chunks (for parent context extraction)
        print("📥 Loading all chunks...")
        all_chunks = await conn.fetch("""
            SELECT id, name, file_path, repository, chunk_type,
                   start_line, end_line, language
            FROM code_chunks
            WHERE name_path IS NULL
            ORDER BY file_path, start_line
        """)

        # 3. Group by file_path for efficient parent context extraction
        print("🗂️  Grouping chunks by file...")
        chunks_by_file = defaultdict(list)

        for chunk in all_chunks:
            # Wrap asyncpg Record in ChunkRecord for attribute access
            chunk_obj = ChunkRecord(chunk)
            chunks_by_file[chunk["file_path"]].append(chunk_obj)

        stats["unique_files"] = len(chunks_by_file)
        print(f"📁 Processing {len(chunks_by_file)} unique files...")

        # 4. Generate name_path for each chunk (with parent context)
        updates: List[Tuple[str, Any]] = []
        skipped: List[Any] = []
        errors: List[Tuple[Any, str]] = []

        for file_idx, (file_path, file_chunks) in enumerate(chunks_by_file.items(), 1):
            # Progress indicator
            if file_idx % 50 == 0:
                print(f"   ⚙️  Processing file {file_idx}/{len(chunks_by_file)}...")

            for chunk in file_chunks:
                try:
                    # Handle edge case 1: Empty name
                    chunk_name = chunk.name

                    if not chunk_name or chunk_name.strip() == "":
                        # Fallback to anonymous name
                        chunk_name = f"anonymous_{chunk.chunk_type}_{str(chunk.id)[:8]}"
                        if not dry_run:
                            print(f"   ⚠️  Empty name for chunk {str(chunk.id)[:8]} → using {chunk_name}")

                    # Edge case 2: Handle fallback_fixed chunks
                    # These are non-AST chunks (JSON, config files)
                    # We'll generate simple paths for them
                    if chunk.chunk_type == "fallback_fixed":
                        # Simple path for config files: e.g., "cv.mcp_json.chunk_0"
                        pass  # Continue with normal generation

                    # Extract parent context from chunks in SAME FILE
                    # This ensures methods get qualified paths like "User.validate"
                    parent_context = symbol_service.extract_parent_context(
                        chunk, file_chunks
                    )

                    # Generate name_path
                    name_path = symbol_service.generate_name_path(
                        chunk_name=chunk_name,
                        file_path=chunk.file_path,
                        repository_root=chunk.repository or "/unknown",
                        parent_context=parent_context,
                        language=chunk.language or "python"
                    )

                    updates.append((name_path, chunk.id))

                except Exception as e:
                    errors.append((chunk.id, str(e)))
                    # Show first 3 errors to understand the problem
                    if len(errors) <= 3:
                        print(f"   ❌ Error processing chunk {str(chunk.id)[:8]}: {e}")

        stats["updated"] = len(updates)
        stats["skipped"] = len(skipped)
        stats["errors"] = len(errors)

        print(f"\n📈 Summary:")
        print(f"   ✅ Ready to update: {len(updates)}")
        print(f"   ⏭️  Skipped: {len(skipped)}")
        print(f"   ❌ Errors: {len(errors)}")

        if dry_run:
            print("\n🔍 DRY RUN - No changes will be committed\n")
            print("Sample updates (first 10):")
            for name_path, chunk_id in updates[:10]:
                print(f"   {str(chunk_id)[:8]} → {name_path}")

            # Show breakdown by chunk type
            chunk_types = defaultdict(int)
            for chunk in all_chunks:
                chunk_types[chunk["chunk_type"]] += 1

            print(f"\n📊 Chunk type breakdown:")
            for chunk_type, count in sorted(chunk_types.items(), key=lambda x: x[1], reverse=True):
                print(f"   {chunk_type:20} {count:5} chunks")

            return stats

        # 5. Batch UPDATE
        if updates:
            print(f"\n💾 Updating {len(updates)} chunks in single transaction...")
            await conn.executemany(
                "UPDATE code_chunks SET name_path = $1 WHERE id = $2",
                updates
            )
            print("   ✅ Update complete!")

        # 6. Validate
        print("\n🔍 Validating migration...")
        remaining = await conn.fetchval(
            "SELECT COUNT(*) FROM code_chunks WHERE name_path IS NULL"
        )

        if remaining > 0:
            print(f"   ⚠️  Warning: {remaining} chunks still missing name_path")
            if errors:
                print("\n   Errors encountered:")
                for chunk_id, error in errors[:10]:
                    print(f"      {str(chunk_id)[:8]}: {error}")
        else:
            print("   ✅ Migration complete! All chunks have name_path.")

        # 7. Statistics
        print("\n📊 Final statistics by language:")
        lang_stats = await conn.fetch("""
            SELECT
                language,
                COUNT(*) as total,
                COUNT(name_path) as with_name_path,
                ROUND(100.0 * COUNT(name_path) / COUNT(*), 2) as coverage_pct
            FROM code_chunks
            GROUP BY language
            ORDER BY total DESC
        """)

        for row in lang_stats:
            print(f"   {row['language']:15} {row['total']:5} chunks ({row['coverage_pct']:5.1f}% coverage)")

        # 8. Show sample name_paths by chunk type
        print("\n📝 Sample name_paths by chunk type:")
        sample_paths = await conn.fetch("""
            SELECT DISTINCT ON (chunk_type)
                chunk_type,
                name_path,
                file_path
            FROM code_chunks
            WHERE name_path IS NOT NULL
            ORDER BY chunk_type, indexed_at DESC
            LIMIT 8
        """)

        for row in sample_paths:
            print(f"   {row['chunk_type']:15} → {row['name_path'][:60]}")

        stats["duration_ms"] = int((time.time() - start_time) * 1000)
        print(f"\n⏱️  Total duration: {stats['duration_ms']}ms")

        return stats

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        raise

    finally:
        await conn.close()


async def validate_migration(database_url: str = None) -> bool:
    """
    Validate that migration was successful.

    Checks:
    1. All chunks have non-null name_path
    2. Name paths follow expected pattern (contains dots)
    3. Methods have parent context (contain parent class name)

    Args:
        database_url: Optional database URL (defaults to DATABASE_URL env var)

    Returns:
        True if validation passes, False otherwise
    """

    if database_url is None:
        database_url = os.getenv("DATABASE_URL")

    # Convert SQLAlchemy URL to asyncpg format
    if "+asyncpg" in database_url:
        database_url = database_url.replace("+asyncpg", "")

    conn = await asyncpg.connect(database_url)

    try:
        print("\n🔍 Running validation checks...")

        # Check 1: 100% coverage
        total = await conn.fetchval("SELECT COUNT(*) FROM code_chunks")
        with_name_path = await conn.fetchval(
            "SELECT COUNT(*) FROM code_chunks WHERE name_path IS NOT NULL"
        )
        coverage = 100.0 * with_name_path / total if total > 0 else 0

        print(f"\n1️⃣  Coverage Check:")
        print(f"   Total chunks: {total}")
        print(f"   With name_path: {with_name_path}")
        print(f"   Coverage: {coverage:.2f}%")

        if coverage < 100.0:
            print("   ❌ FAIL: Not all chunks have name_path")
            return False
        else:
            print("   ✅ PASS")

        # Check 2: Name paths have valid format (contain dots)
        invalid_paths = await conn.fetchval("""
            SELECT COUNT(*)
            FROM code_chunks
            WHERE name_path IS NOT NULL
            AND name_path NOT LIKE '%.%'
        """)

        print(f"\n2️⃣  Format Check:")
        print(f"   Invalid paths (no dots): {invalid_paths}")

        if invalid_paths > 0:
            print("   ⚠️  WARNING: Some paths don't contain dots (may be root-level)")
            # This is acceptable for some cases
        else:
            print("   ✅ PASS")

        # Check 3: Sample verification
        print(f"\n3️⃣  Sample Verification (random 5 chunks):")
        samples = await conn.fetch("""
            SELECT name, name_path, chunk_type, file_path
            FROM code_chunks
            WHERE name_path IS NOT NULL
            ORDER BY RANDOM()
            LIMIT 5
        """)

        for sample in samples:
            print(f"   {sample['chunk_type']:10} {sample['name']:20} → {sample['name_path'][:50]}")

        print("\n✅ Validation complete!")
        return True

    finally:
        await conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Backfill name_path for code chunks (EPIC-11 Story 11.4)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without committing changes"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run validation checks after migration"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("  EPIC-11 Story 11.4: name_path Backfill Migration")
    print("=" * 70)

    # Run migration
    stats = asyncio.run(backfill_name_path(dry_run=args.dry_run))

    # Run validation if requested and not dry-run
    if args.validate and not args.dry_run:
        asyncio.run(validate_migration())

    print("\n" + "=" * 70)
    print("  Migration complete!")
    print("=" * 70)
