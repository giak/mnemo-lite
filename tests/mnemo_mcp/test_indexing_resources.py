"""
Tests for MCP Indexing Resources (EPIC-23 Story 23.5).

Tests IndexStatusResource for querying indexing status and statistics.
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mnemo_mcp.resources.indexing_resources import IndexStatusResource


# ============================================================================
# IndexStatusResource Tests
# ============================================================================


class TestIndexStatusResource:
    """Test IndexStatusResource."""

    def setup_method(self):
        """Setup test resources."""
        self.resource = IndexStatusResource()

    @pytest.mark.asyncio
    async def test_status_not_indexed(self):
        """Test getting status for repository not yet indexed."""
        # Mock services
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # No Redis status

        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_engine.connect = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn)))

        # Mock database queries returning 0 chunks
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_conn.execute = AsyncMock(return_value=mock_result)

        self.resource.services = {
            "redis": mock_redis,
            "sqlalchemy_engine": mock_engine,
            "chunk_cache": None
        }

        result = await self.resource.get(repository="new-repo")

        assert result["success"] is True
        assert result["status"] == "not_indexed"
        assert result["total_chunks"] == 0
        assert result["repository"] == "new-repo"
        assert "not indexed yet" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_status_completed_from_db(self):
        """Test getting completed status from database."""
        # Mock Redis (no status)
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        # Mock database with existing chunks
        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_engine.connect = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn)))

        last_indexed = datetime(2025, 1, 15, 12, 0, 0)

        # Mock different query results
        async def mock_execute(query, params=None):
            result = MagicMock()
            # Detect query type by checking query text
            query_text = str(query).lower()

            if "count(*)" in query_text and "distinct" not in query_text:
                # Total chunks count
                result.scalar.return_value = 500
            elif "count(distinct file_path)" in query_text:
                # Distinct file count
                result.scalar.return_value = 100
            elif "distinct language" in query_text:
                # Languages
                result.__iter__ = lambda self: iter([("python",), ("javascript",)])
            elif "max(created_at)" in query_text:
                # Last indexed timestamp
                result.scalar.return_value = last_indexed
            else:
                result.scalar.return_value = 0

            return result

        mock_conn.execute = mock_execute

        self.resource.services = {
            "redis": mock_redis,
            "sqlalchemy_engine": mock_engine,
            "chunk_cache": None
        }

        result = await self.resource.get(repository="test-repo")

        assert result["success"] is True
        assert result["status"] == "completed"
        assert result["total_chunks"] == 500
        assert result["total_files"] == 100
        assert "python" in result["languages"]
        assert "javascript" in result["languages"]
        assert result["last_indexed_at"] is not None

    @pytest.mark.asyncio
    async def test_status_in_progress_from_redis(self):
        """Test getting in-progress status from Redis."""
        # Mock Redis with in-progress status
        mock_redis = AsyncMock()
        redis_status = {
            "status": "in_progress",
            "total_files": 200,
            "indexed_files": 100,
            "started_at": "2025-01-15T10:00:00",
            "repository": "test-repo"
        }
        mock_redis.get.return_value = json.dumps(redis_status)

        # Mock database (some chunks already indexed)
        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_engine.connect = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn)))

        async def mock_execute(query, params=None):
            result = MagicMock()
            query_text = str(query).lower()
            if "max(created_at)" in query_text:
                result.scalar.return_value = None  # No last_indexed_at
            else:
                result.scalar.return_value = 250  # Some chunks
            result.__iter__ = lambda self: iter([])
            return result

        mock_conn.execute = mock_execute

        self.resource.services = {
            "redis": mock_redis,
            "sqlalchemy_engine": mock_engine,
            "chunk_cache": None
        }

        result = await self.resource.get(repository="test-repo")

        assert result["success"] is True
        assert result["status"] == "in_progress"
        assert result["total_files"] == 200
        assert result["indexed_files"] == 100
        assert result["started_at"] is not None
        assert "100/200" in result["message"]

    @pytest.mark.asyncio
    async def test_status_failed_from_redis(self):
        """Test getting failed status from Redis."""
        mock_redis = AsyncMock()
        redis_status = {
            "status": "failed",
            "started_at": "2025-01-15T10:00:00",
            "completed_at": "2025-01-15T10:05:00",
            "repository": "test-repo",
            "error": "Database connection lost"
        }
        mock_redis.get.return_value = json.dumps(redis_status)

        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_engine.connect = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn)))

        async def mock_execute(query, params=None):
            result = MagicMock()
            result.scalar.return_value = 0
            result.__iter__ = lambda self: iter([])
            return result

        mock_conn.execute = mock_execute

        self.resource.services = {
            "redis": mock_redis,
            "sqlalchemy_engine": mock_engine,
            "chunk_cache": None
        }

        result = await self.resource.get(repository="test-repo")

        assert result["success"] is True
        assert result["status"] == "failed"
        assert result["error"] == "Database connection lost"
        assert "failed" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_status_with_cache_stats(self):
        """Test status includes cache statistics."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_engine.connect = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn)))

        async def mock_execute(query, params=None):
            result = MagicMock()
            query_text = str(query).lower()
            if "max(created_at)" in query_text:
                result.scalar.return_value = None
            else:
                result.scalar.return_value = 100
            result.__iter__ = lambda self: iter([])
            return result

        mock_conn.execute = mock_execute

        # Mock chunk cache
        mock_cache = MagicMock()
        mock_cache.get_stats.return_value = {
            "l1_hit_rate": 0.85,
            "l2_hit_rate": 0.92,
            "total_requests": 1000
        }

        self.resource.services = {
            "redis": mock_redis,
            "sqlalchemy_engine": mock_engine,
            "chunk_cache": mock_cache
        }

        result = await self.resource.get(repository="test-repo")

        assert result["success"] is True
        assert "cache_stats" in result
        assert result["cache_stats"]["l1_hit_rate"] == 0.85
        assert result["cache_stats"]["l2_hit_rate"] == 0.92

    @pytest.mark.asyncio
    async def test_status_without_redis(self):
        """Test status works without Redis (graceful degradation)."""
        # No Redis service
        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_engine.connect = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn)))

        async def mock_execute(query, params=None):
            result = MagicMock()
            query_text = str(query).lower()
            if "max(created_at)" in query_text:
                result.scalar.return_value = None
            elif "distinct language" in query_text:
                result.__iter__ = lambda self: iter([("python",)])
            else:
                result.scalar.return_value = 200
            return result

        mock_conn.execute = mock_execute

        self.resource.services = {
            "redis": None,  # No Redis
            "sqlalchemy_engine": mock_engine,
            "chunk_cache": None
        }

        result = await self.resource.get(repository="test-repo")

        # Should still work, using only DB data
        assert result["success"] is True
        assert result["status"] in ("completed", "not_indexed")

    @pytest.mark.asyncio
    async def test_status_database_unavailable(self):
        """Test status returns error when database unavailable."""
        self.resource.services = {
            "redis": None,
            "sqlalchemy_engine": None,  # No database
            "chunk_cache": None
        }

        result = await self.resource.get(repository="test-repo")

        assert result["success"] is False
        assert result["status"] == "unknown"
        assert "not available" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_get_status_message_helper(self):
        """Test _get_status_message helper method."""
        # Test not_indexed
        msg = self.resource._get_status_message("not_indexed", 0, 0, 0, 0)
        assert "not indexed yet" in msg.lower()

        # Test in_progress
        msg = self.resource._get_status_message("in_progress", 0, 0, 50, 100)
        assert "50/100" in msg
        assert "50.0%" in msg

        # Test completed
        msg = self.resource._get_status_message("completed", 100, 500, 0, 0)
        assert "100 files" in msg
        assert "500 chunks" in msg

        # Test failed
        msg = self.resource._get_status_message("failed", 0, 0, 0, 0)
        assert "failed" in msg.lower()

        # Test unknown
        msg = self.resource._get_status_message("unknown", 0, 0, 0, 0)
        assert "unknown" in msg.lower()
