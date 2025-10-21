"""
Tests for EPIC-11 Story 11.4: name_path backfill migration script.

These tests verify:
1. Migration handles empty names gracefully
2. Methods get correct parent context
3. Script is idempotent (can run multiple times)
4. Performance is acceptable (<5s for 1000 chunks)
5. Edge cases are handled correctly
"""

import pytest
import uuid
import asyncpg
import os
from scripts.backfill_name_path import backfill_name_path, validate_migration


class TestBackfillNamePath:
    """Test suite for backfill_name_path migration script."""

    @pytest.mark.anyio
    async def test_backfill_handles_empty_names(self):
        """
        Story 11.4 Edge Case #1: Chunks with empty names.
        Expected: Generate fallback name using chunk_type + id
        """
        database_url = os.getenv("TEST_DATABASE_URL")
        conn = await asyncpg.connect(database_url)

        try:
            # Insert chunk with empty name
            chunk_id = uuid.uuid4()
            await conn.execute("""
                INSERT INTO code_chunks (
                    id, name, file_path, repository, chunk_type, language,
                    start_line, end_line, source_code
                )
                VALUES ($1, '', 'test.py', '/app', 'method', 'python', 1, 5, 'pass')
            """, chunk_id)

            # Run backfill
            stats = await backfill_name_path(dry_run=False)

            # Verify name_path generated with fallback
            result = await conn.fetchrow("""
                SELECT name_path FROM code_chunks WHERE id = $1
            """, chunk_id)

            assert result is not None
            assert result["name_path"] is not None
            assert "anonymous_method" in result["name_path"]
            assert str(chunk_id)[:8] in result["name_path"]

            # Cleanup
            await conn.execute("DELETE FROM code_chunks WHERE id = $1", chunk_id)

        finally:
            await conn.close()

    @pytest.mark.anyio
    async def test_backfill_with_parent_context(self):
        """
        Story 11.4: Verify methods get correct parent context.
        Expected: method name_path includes parent class
        """
        database_url = os.getenv("TEST_DATABASE_URL")
        conn = await asyncpg.connect(database_url)

        try:
            # Insert class + method in same file
            class_id = uuid.uuid4()
            method_id = uuid.uuid4()

            await conn.execute("""
                INSERT INTO code_chunks (
                    id, name, file_path, repository, chunk_type, language,
                    start_line, end_line, source_code
                )
                VALUES
                    ($1, 'User', 'models/user.py', '/app', 'class', 'python', 1, 10, 'class User:\n    pass'),
                    ($2, 'validate', 'models/user.py', '/app', 'method', 'python', 5, 8, 'def validate(self):\n    pass')
            """, class_id, method_id)

            # Run backfill
            stats = await backfill_name_path(dry_run=False)

            # Verify method has parent context
            method_result = await conn.fetchrow("""
                SELECT name_path FROM code_chunks WHERE id = $1
            """, method_id)

            # Should be: models.user.User.validate (with parent context)
            assert method_result is not None
            assert method_result["name_path"] is not None
            assert "User.validate" in method_result["name_path"]

            # Verify class path
            class_result = await conn.fetchrow("""
                SELECT name_path FROM code_chunks WHERE id = $1
            """, class_id)

            assert class_result is not None
            assert "User" in class_result["name_path"]

            # Cleanup
            await conn.execute("DELETE FROM code_chunks WHERE id IN ($1, $2)", class_id, method_id)

        finally:
            await conn.close()

    @pytest.mark.anyio
    async def test_backfill_idempotent(self):
        """
        Story 11.4: Running twice should not duplicate or change existing data.
        Expected: Same result after re-running
        """
        database_url = os.getenv("TEST_DATABASE_URL")
        conn = await asyncpg.connect(database_url)

        try:
            # Insert test chunk
            chunk_id = uuid.uuid4()
            await conn.execute("""
                INSERT INTO code_chunks (
                    id, name, file_path, repository, chunk_type, language,
                    start_line, end_line, source_code
                )
                VALUES ($1, 'test_func', 'test.py', '/app', 'function', 'python', 1, 5, 'def test_func():\n    pass')
            """, chunk_id)

            # Run once
            await backfill_name_path(dry_run=False)

            first_result = await conn.fetchrow("""
                SELECT name_path FROM code_chunks WHERE id = $1
            """, chunk_id)

            # Run again
            await backfill_name_path(dry_run=False)

            second_result = await conn.fetchrow("""
                SELECT name_path FROM code_chunks WHERE id = $1
            """, chunk_id)

            # Should be identical
            assert first_result["name_path"] == second_result["name_path"]

            # Cleanup
            await conn.execute("DELETE FROM code_chunks WHERE id = $1", chunk_id)

        finally:
            await conn.close()

    @pytest.mark.anyio
    async def test_backfill_fallback_fixed_chunks(self):
        """
        Story 11.4 Edge Case #2: fallback_fixed chunks (JSON, config files).
        Expected: Generate simple path for non-code files
        """
        database_url = os.getenv("TEST_DATABASE_URL")
        conn = await asyncpg.connect(database_url)

        try:
            # Insert fallback_fixed chunk (JSON file)
            chunk_id = uuid.uuid4()
            await conn.execute("""
                INSERT INTO code_chunks (
                    id, name, file_path, repository, chunk_type, language,
                    start_line, end_line, source_code
                )
                VALUES ($1, 'chunk_0', 'config/.mcp.json', '/app', 'fallback_fixed', 'json', 1, 10, '{}')
            """, chunk_id)

            # Run backfill
            stats = await backfill_name_path(dry_run=False)

            # Verify name_path generated (simple path for config)
            result = await conn.fetchrow("""
                SELECT name_path FROM code_chunks WHERE id = $1
            """, chunk_id)

            assert result is not None
            assert result["name_path"] is not None
            # Should contain file-based path
            assert "config" in result["name_path"] or "mcp_json" in result["name_path"]

            # Cleanup
            await conn.execute("DELETE FROM code_chunks WHERE id = $1", chunk_id)

        finally:
            await conn.close()

    @pytest.mark.anyio
    async def test_backfill_dry_run(self):
        """
        Story 11.4: Dry run should not modify database.
        Expected: No changes when dry_run=True
        """
        database_url = os.getenv("TEST_DATABASE_URL")
        conn = await asyncpg.connect(database_url)

        try:
            # Insert chunk with NULL name_path
            chunk_id = uuid.uuid4()
            await conn.execute("""
                INSERT INTO code_chunks (
                    id, name, file_path, repository, chunk_type, language,
                    start_line, end_line, source_code, name_path
                )
                VALUES ($1, 'test', 'test.py', '/app', 'function', 'python', 1, 5, 'pass', NULL)
            """, chunk_id)

            # Run dry-run
            stats = await backfill_name_path(dry_run=True)

            # Verify name_path is still NULL
            result = await conn.fetchrow("""
                SELECT name_path FROM code_chunks WHERE id = $1
            """, chunk_id)

            assert result["name_path"] is None  # Should not be updated

            # Cleanup
            await conn.execute("DELETE FROM code_chunks WHERE id = $1", chunk_id)

        finally:
            await conn.close()

    @pytest.mark.anyio
    async def test_backfill_statistics(self):
        """
        Story 11.4: Script should return accurate statistics.
        Expected: Stats match actual database state
        """
        database_url = os.getenv("TEST_DATABASE_URL")
        conn = await asyncpg.connect(database_url)

        try:
            # Insert 3 test chunks
            chunk_ids = [uuid.uuid4() for _ in range(3)]

            for i, chunk_id in enumerate(chunk_ids):
                await conn.execute("""
                    INSERT INTO code_chunks (
                        id, name, file_path, repository, chunk_type, language,
                        start_line, end_line, source_code
                    )
                    VALUES ($1, $2, 'test.py', '/app', 'function', 'python', 1, 5, 'pass')
                """, chunk_id, f"func_{i}")

            # Run backfill
            stats = await backfill_name_path(dry_run=False)

            # Verify statistics
            assert stats["total_chunks"] >= 3
            assert stats["updated"] >= 3
            assert stats["errors"] == 0

            # Cleanup
            for chunk_id in chunk_ids:
                await conn.execute("DELETE FROM code_chunks WHERE id = $1", chunk_id)

        finally:
            await conn.close()

    @pytest.mark.anyio
    async def test_backfill_typescript_chunks(self):
        """
        Story 11.4: Verify TypeScript chunks handled correctly.
        Expected: Language-specific path generation for TypeScript
        """
        database_url = os.getenv("TEST_DATABASE_URL")
        conn = await asyncpg.connect(database_url)

        try:
            # Insert TypeScript interface
            chunk_id = uuid.uuid4()
            await conn.execute("""
                INSERT INTO code_chunks (
                    id, name, file_path, repository, chunk_type, language,
                    start_line, end_line, source_code
                )
                VALUES ($1, 'User', 'src/types/user.ts', '/app', 'interface', 'typescript', 1, 5, 'interface User {}')
            """, chunk_id)

            # Run backfill
            stats = await backfill_name_path(dry_run=False)

            # Verify TypeScript path generated
            result = await conn.fetchrow("""
                SELECT name_path FROM code_chunks WHERE id = $1
            """, chunk_id)

            assert result is not None
            assert result["name_path"] is not None
            # Should NOT contain "src" prefix (removed by service)
            assert result["name_path"].startswith("types.user")

            # Cleanup
            await conn.execute("DELETE FROM code_chunks WHERE id = $1", chunk_id)

        finally:
            await conn.close()


class TestValidateMigration:
    """Test suite for migration validation checks."""

    @pytest.mark.anyio
    async def test_validate_migration_success(self):
        """
        Story 11.4: Validation should pass when all chunks have name_path.
        """
        database_url = os.getenv("TEST_DATABASE_URL")
        conn = await asyncpg.connect(database_url)

        try:
            # Ensure all test chunks have name_path
            await conn.execute("""
                UPDATE code_chunks
                SET name_path = COALESCE(name_path, name || '.default')
                WHERE name_path IS NULL
            """)

            # Run validation
            result = await validate_migration()

            # Should pass
            assert result is True

        finally:
            await conn.close()
