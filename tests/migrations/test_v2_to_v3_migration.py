"""
Unit tests for v2.0 → v3.0 Migration (EPIC-10 Story 10.6).

Tests content_hash migration correctness, idempotency, and validation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import asyncpg

# Import the migration module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from migrate_v2_to_v3 import MigrationV2ToV3


class TestMigrationV2ToV3:
    """Test suite for v2→v3 migration."""

    @pytest.mark.anyio
    async def test_migration_initialization(self):
        """Test migration initializes correctly."""
        migration = MigrationV2ToV3("postgresql://test", dry_run=False)

        assert migration.database_url == "postgresql://test"
        assert migration.dry_run is False
        assert migration.conn is None

    @pytest.mark.anyio
    async def test_get_chunk_counts(self):
        """Test getting chunk counts."""
        # Mock connection
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=[1000, 500])  # total, with_hash

        migration = MigrationV2ToV3("postgresql://test")
        migration.conn = mock_conn

        total, with_hash = await migration.get_chunk_counts()

        assert total == 1000
        assert with_hash == 500
        assert mock_conn.fetchval.call_count == 2

    @pytest.mark.anyio
    async def test_migration_already_complete(self):
        """Test migration skips when all chunks have hash."""
        # Mock connection
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=[
            1000,  # total chunks
            1000   # chunks with hash (100%)
        ])

        migration = MigrationV2ToV3("postgresql://test")
        migration.conn = mock_conn

        result = await migration.run_migration()

        assert result["status"] == "skipped"
        assert result["reason"] == "already_migrated"
        assert result["total_chunks"] == 1000
        assert result["migrated"] == 0

    @pytest.mark.anyio
    async def test_migration_dry_run(self):
        """Test dry-run mode doesn't modify database."""
        # Mock connection
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=[
            1000,  # total chunks
            500    # chunks with hash (50%)
        ])
        mock_conn.fetch = AsyncMock(return_value=[
            {"id": "uuid1", "file_path": "test1.py", "source_preview": "def foo():"},
            {"id": "uuid2", "file_path": "test2.py", "source_preview": "class Bar:"},
        ])

        migration = MigrationV2ToV3("postgresql://test", dry_run=True)
        migration.conn = mock_conn

        result = await migration.run_migration()

        assert result["status"] == "dry_run"
        assert result["total_chunks"] == 1000
        assert result["would_migrate"] == 500

        # Verify execute was NOT called
        mock_conn.execute.assert_not_called()

    @pytest.mark.anyio
    async def test_migration_success(self):
        """Test successful migration execution."""
        # Mock connection
        mock_conn = AsyncMock()

        # get_chunk_counts called twice (before, after)
        mock_conn.fetchval = AsyncMock(side_effect=[
            1000, 500,  # Before: total=1000, with_hash=500
            1000, 1000  # After: total=1000, with_hash=1000
        ])

        # Mock transaction
        mock_transaction = AsyncMock()
        mock_transaction.__aenter__ = AsyncMock()
        mock_transaction.__aexit__ = AsyncMock()
        mock_conn.transaction = MagicMock(return_value=mock_transaction)

        migration = MigrationV2ToV3("postgresql://test", dry_run=False)
        migration.conn = mock_conn

        # Mock migration file
        with patch.object(Path, "read_text", return_value="-- Migration SQL\nUPDATE code_chunks SET metadata = ..."):
            result = await migration.run_migration()

        assert result["status"] == "success"
        assert result["total_chunks"] == 1000
        assert result["migrated"] == 500  # 1000 - 500
        assert "duration_seconds" in result

        # Verify execute was called
        mock_conn.execute.assert_called_once()

    @pytest.mark.anyio
    async def test_migration_incomplete_raises_error(self):
        """Test migration raises error if incomplete."""
        # Mock connection
        mock_conn = AsyncMock()

        # After migration: total=1000, with_hash=990 (10 missing)
        mock_conn.fetchval = AsyncMock(side_effect=[
            1000, 500,  # Before
            1000, 990   # After (incomplete!)
        ])

        # Mock transaction
        mock_transaction = AsyncMock()
        mock_transaction.__aenter__ = AsyncMock()
        mock_transaction.__aexit__ = AsyncMock()
        mock_conn.transaction = MagicMock(return_value=mock_transaction)

        migration = MigrationV2ToV3("postgresql://test", dry_run=False)
        migration.conn = mock_conn

        # Mock migration file
        with patch.object(Path, "read_text", return_value="-- SQL"):
            with pytest.raises(RuntimeError, match="Migration incomplete"):
                await migration.run_migration()

    @pytest.mark.anyio
    async def test_validation_all_chunks_have_hash(self):
        """Test validation passes when all chunks have hash."""
        # Mock connection
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=[
            1000,  # total chunks
            1000,  # chunks with hash
            0      # chunks with invalid hash format
        ])
        mock_conn.fetch = AsyncMock(return_value=[
            {
                "file_path": "test1.py",
                "source_preview": "def foo():",
                "content_hash": "abc123def456" * 2 + "abcd1234"  # 32 chars
            }
        ])

        migration = MigrationV2ToV3("postgresql://test")
        migration.conn = mock_conn

        is_valid = await migration.validate()

        assert is_valid is True

    @pytest.mark.anyio
    async def test_validation_fails_missing_hash(self):
        """Test validation fails when chunks missing hash."""
        # Mock connection
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=[
            1000,  # total chunks
            990    # chunks with hash (10 missing)
        ])

        migration = MigrationV2ToV3("postgresql://test")
        migration.conn = mock_conn

        is_valid = await migration.validate()

        assert is_valid is False

    @pytest.mark.anyio
    async def test_validation_fails_invalid_format(self):
        """Test validation fails when hash format invalid."""
        # Mock connection
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=[
            1000,  # total chunks
            1000,  # chunks with hash
            5      # chunks with invalid hash format
        ])

        migration = MigrationV2ToV3("postgresql://test")
        migration.conn = mock_conn

        is_valid = await migration.validate()

        assert is_valid is False

    @pytest.mark.anyio
    async def test_idempotency(self):
        """Test migration is idempotent (can run multiple times safely)."""
        # Mock connection
        mock_conn = AsyncMock()

        # First run: 500 chunks migrated
        # Second run: already complete (skipped)
        mock_conn.fetchval = AsyncMock(side_effect=[
            # First run
            1000, 500,  # Before: 500 need migration
            1000, 1000, # After: all migrated
            # Second run
            1000, 1000  # Already complete
        ])

        # Mock transaction
        mock_transaction = AsyncMock()
        mock_transaction.__aenter__ = AsyncMock()
        mock_transaction.__aexit__ = AsyncMock()
        mock_conn.transaction = MagicMock(return_value=mock_transaction)

        migration = MigrationV2ToV3("postgresql://test")
        migration.conn = mock_conn

        # First run
        with patch.object(Path, "read_text", return_value="-- SQL"):
            result1 = await migration.run_migration()

        assert result1["status"] == "success"
        assert result1["migrated"] == 500

        # Second run (idempotent)
        result2 = await migration.run_migration()

        assert result2["status"] == "skipped"
        assert result2["reason"] == "already_migrated"
        assert result2["migrated"] == 0

    @pytest.mark.anyio
    async def test_connect_database_success(self):
        """Test database connection success."""
        with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = AsyncMock()

            migration = MigrationV2ToV3("postgresql://test")
            await migration.connect()

            assert migration.conn is not None
            mock_connect.assert_called_once_with("postgresql://test")

    @pytest.mark.anyio
    async def test_connect_database_failure(self):
        """Test database connection failure exits."""
        with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = Exception("Connection refused")

            migration = MigrationV2ToV3("postgresql://test")

            with pytest.raises(SystemExit):
                await migration.connect()

    @pytest.mark.anyio
    async def test_disconnect(self):
        """Test database disconnect."""
        mock_conn = AsyncMock()

        migration = MigrationV2ToV3("postgresql://test")
        migration.conn = mock_conn

        await migration.disconnect()

        mock_conn.close.assert_called_once()


class TestSQLMigrationFile:
    """Test the SQL migration file itself."""

    def test_migration_file_exists(self):
        """Test migration SQL file exists."""
        migration_file = Path(__file__).parent.parent.parent / "db" / "migrations" / "v2_to_v3.sql"
        assert migration_file.exists(), "Migration file v2_to_v3.sql not found"

    def test_migration_file_has_update_statement(self):
        """Test migration file contains UPDATE statement."""
        migration_file = Path(__file__).parent.parent.parent / "db" / "migrations" / "v2_to_v3.sql"
        content = migration_file.read_text()

        assert "UPDATE code_chunks" in content
        assert "metadata" in content
        assert "content_hash" in content
        assert "md5(source_code)" in content

    def test_migration_file_has_validation(self):
        """Test migration file contains validation logic."""
        migration_file = Path(__file__).parent.parent.parent / "db" / "migrations" / "v2_to_v3.sql"
        content = migration_file.read_text()

        assert "DO $$" in content  # PL/pgSQL block
        assert "RAISE EXCEPTION" in content  # Error handling
        assert "RAISE NOTICE" in content  # Success message

    def test_migration_file_is_idempotent(self):
        """Test migration file has WHERE clause for idempotency."""
        migration_file = Path(__file__).parent.parent.parent / "db" / "migrations" / "v2_to_v3.sql"
        content = migration_file.read_text()

        # Should have WHERE clause to avoid updating already-migrated chunks
        assert "WHERE metadata->>'content_hash' IS NULL" in content
