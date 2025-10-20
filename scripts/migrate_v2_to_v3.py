#!/usr/bin/env python3
"""
Migration Script v2.0 → v3.0: Add content_hash to code_chunks
EPIC-10 Story 10.6: Migration Script for content_hash

Purpose:
- Backfill content_hash (MD5 of source_code) to all existing code chunks
- Enable L1 cache hash validation for chunks indexed before v3.0

Usage:
    python3 scripts/migrate_v2_to_v3.py [--dry-run]

Options:
    --dry-run: Show what would be migrated without making changes

Environment:
    DATABASE_URL: PostgreSQL connection string (required)

Example:
    DATABASE_URL=postgresql://mnemo:password@localhost:5432/mnemolite \\
        python3 scripts/migrate_v2_to_v3.py
"""

import asyncio
import asyncpg
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Tuple


class MigrationV2ToV3:
    """Migration handler for v2.0 → v3.0 content_hash backfill."""

    def __init__(self, database_url: str, dry_run: bool = False):
        """
        Initialize migration.

        Args:
            database_url: PostgreSQL connection string
            dry_run: If True, only show what would be migrated
        """
        self.database_url = database_url
        self.dry_run = dry_run
        self.conn: asyncpg.Connection | None = None

    async def connect(self):
        """Establish database connection."""
        print(f"🔌 Connecting to database...")
        try:
            self.conn = await asyncpg.connect(self.database_url)
            print("✅ Database connection established")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            sys.exit(1)

    async def disconnect(self):
        """Close database connection."""
        if self.conn:
            await self.conn.close()
            print("🔌 Database connection closed")

    async def get_chunk_counts(self) -> Tuple[int, int]:
        """
        Get chunk counts (total, with hash).

        Returns:
            (total_chunks, chunks_with_hash)
        """
        if not self.conn:
            raise RuntimeError("Not connected to database")

        total = await self.conn.fetchval("SELECT COUNT(*) FROM code_chunks")

        with_hash = await self.conn.fetchval(
            "SELECT COUNT(*) FROM code_chunks WHERE metadata->>'content_hash' IS NOT NULL"
        )

        return total, with_hash

    async def run_migration(self) -> dict:
        """
        Execute migration (or dry-run).

        Returns:
            Migration result with statistics
        """
        if not self.conn:
            raise RuntimeError("Not connected to database")

        start_time = datetime.now()

        # Get pre-migration counts
        total_before, with_hash_before = await self.get_chunk_counts()

        print(f"\n📊 Pre-migration state:")
        print(f"   Total chunks: {total_before}")
        print(f"   With content_hash: {with_hash_before}")
        print(f"   Missing content_hash: {total_before - with_hash_before}")

        # Check if migration needed
        if with_hash_before == total_before:
            print("\n✅ All chunks already have content_hash. Migration not needed.")
            return {
                "status": "skipped",
                "reason": "already_migrated",
                "total_chunks": total_before,
                "migrated": 0
            }

        # Dry run: show what would be migrated
        if self.dry_run:
            print(f"\n🔍 DRY RUN MODE - No changes will be made")
            print(f"   Would migrate {total_before - with_hash_before} chunks")

            # Show sample of what would be updated
            samples = await self.conn.fetch(
                """
                SELECT id, file_path, LEFT(source_code, 50) as source_preview
                FROM code_chunks
                WHERE metadata->>'content_hash' IS NULL
                LIMIT 5
                """
            )

            print(f"\n📄 Sample chunks to be migrated:")
            for sample in samples:
                print(f"   - {sample['file_path']}: {sample['source_preview']}...")

            return {
                "status": "dry_run",
                "total_chunks": total_before,
                "would_migrate": total_before - with_hash_before
            }

        # Execute migration SQL
        print(f"\n⚙️  Running migration SQL...")

        # Read migration file
        migration_file = Path(__file__).parent.parent / "db" / "migrations" / "v2_to_v3.sql"

        if not migration_file.exists():
            raise FileNotFoundError(f"Migration file not found: {migration_file}")

        migration_sql = migration_file.read_text()

        try:
            # Execute migration in a transaction
            async with self.conn.transaction():
                # Run the SQL (includes UPDATE + validation)
                await self.conn.execute(migration_sql)

            print("✅ Migration SQL executed successfully")

        except Exception as e:
            print(f"❌ Migration failed: {e}")
            raise

        # Get post-migration counts
        total_after, with_hash_after = await self.get_chunk_counts()

        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()

        # Validate
        if total_after != with_hash_after:
            raise RuntimeError(
                f"Migration incomplete: {total_after - with_hash_after} chunks still missing hash"
            )

        print(f"\n✅ Migration complete!")
        print(f"   Duration: {duration:.2f}s")
        print(f"   Total chunks: {total_after}")
        print(f"   Migrated: {with_hash_after - with_hash_before}")
        print(f"   Coverage: {with_hash_after}/{total_after} (100%)")

        return {
            "status": "success",
            "total_chunks": total_after,
            "migrated": with_hash_after - with_hash_before,
            "duration_seconds": duration
        }

    async def validate(self) -> bool:
        """
        Validate migration success.

        Returns:
            True if all chunks have content_hash
        """
        if not self.conn:
            raise RuntimeError("Not connected to database")

        print(f"\n🔍 Validating migration...")

        total, with_hash = await self.get_chunk_counts()

        if total != with_hash:
            print(f"❌ Validation failed: {total - with_hash} chunks missing hash")
            return False

        # Validate hash format (should be 32 hex chars)
        invalid_hashes = await self.conn.fetchval(
            """
            SELECT COUNT(*)
            FROM code_chunks
            WHERE
                metadata->>'content_hash' IS NOT NULL
                AND LENGTH(metadata->>'content_hash') != 32
            """
        )

        if invalid_hashes > 0:
            print(f"❌ Validation failed: {invalid_hashes} chunks have invalid hash format")
            return False

        print(f"✅ Validation passed:")
        print(f"   All {total} chunks have valid content_hash (32 hex chars)")

        # Show samples
        samples = await self.conn.fetch(
            """
            SELECT
                file_path,
                LEFT(source_code, 40) as source_preview,
                metadata->>'content_hash' as content_hash
            FROM code_chunks
            LIMIT 3
            """
        )

        print(f"\n📄 Sample migrated chunks:")
        for sample in samples:
            print(f"   {sample['file_path']}")
            print(f"   └─ Hash: {sample['content_hash']}")
            print(f"   └─ Source: {sample['source_preview']}...")

        return True


async def main():
    """Main migration entry point."""
    # Parse arguments
    dry_run = "--dry-run" in sys.argv

    # Get database URL
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        print("\nUsage:")
        print("  DATABASE_URL=postgresql://... python3 scripts/migrate_v2_to_v3.py")
        sys.exit(1)

    # Run migration
    print("=" * 70)
    print("🚀 MnemoLite Migration: v2.0 → v3.0")
    print("=" * 70)
    print(f"Purpose: Backfill content_hash to code_chunks.metadata")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE MIGRATION'}")
    print("=" * 70)

    migration = MigrationV2ToV3(database_url, dry_run=dry_run)

    try:
        await migration.connect()
        result = await migration.run_migration()

        # Validate if not dry run
        if result["status"] == "success":
            is_valid = await migration.validate()
            if not is_valid:
                sys.exit(1)

        print("\n" + "=" * 70)
        print(f"✅ Migration v2.0 → v3.0 {'simulated' if dry_run else 'COMPLETED'}")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        sys.exit(1)

    finally:
        await migration.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
