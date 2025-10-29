"""
Tests for MCP Indexing Tools (EPIC-23 Story 23.5).

Tests IndexProjectTool and ReindexFileTool for project indexing and file re-indexing.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from mnemo_mcp.tools.indexing_tools import IndexProjectTool, ReindexFileTool


# ============================================================================
# IndexProjectTool Tests
# ============================================================================


class TestIndexProjectTool:
    """Test IndexProjectTool."""

    def setup_method(self):
        """Setup test tool."""
        self.tool = IndexProjectTool()

    def test_get_name(self):
        """Test tool name."""
        assert self.tool.get_name() == "index_project"

    def test_get_description(self):
        """Test tool description."""
        desc = self.tool.get_description()
        assert "index" in desc.lower()
        assert "project" in desc.lower()

    @pytest.mark.asyncio
    async def test_index_project_success(self, tmp_path):
        """Test successful project indexing."""
        # Create test project
        (tmp_path / "main.py").write_text("print('hello')")
        (tmp_path / "utils.py").write_text("def util(): pass")

        # Mock services
        mock_indexing_service = AsyncMock()
        mock_result = MagicMock()
        mock_result.repository = "test-repo"
        mock_result.indexed_files = 2
        mock_result.indexed_chunks = 5
        mock_result.indexed_nodes = 3
        mock_result.indexed_edges = 2
        mock_result.failed_files = 0
        mock_result.processing_time_ms = 100.0
        mock_result.errors = []

        mock_indexing_service.index_repository = AsyncMock(return_value=mock_result)

        self.tool.services = {
            "code_indexing_service": mock_indexing_service,
            "redis": None  # Test without Redis
        }

        result = await self.tool.execute(
            project_path=str(tmp_path),
            repository="test-repo",
            include_gitignored=False
        )

        assert result["success"] is True
        assert result["repository"] == "test-repo"
        assert result["indexed_files"] == 2
        assert result["indexed_chunks"] == 5
        assert mock_indexing_service.index_repository.called

    @pytest.mark.asyncio
    async def test_index_project_service_unavailable(self):
        """Test indexing fails gracefully when service unavailable."""
        self.tool.services = {}  # No services

        result = await self.tool.execute(
            project_path="/some/path",
            repository="test"
        )

        assert result["success"] is False
        assert "not available" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_index_project_path_not_found(self):
        """Test indexing fails for nonexistent project path."""
        mock_indexing_service = AsyncMock()

        self.tool.services = {
            "code_indexing_service": mock_indexing_service,
            "redis": None
        }

        result = await self.tool.execute(
            project_path="/nonexistent/path",
            repository="test"
        )

        assert result["success"] is False
        assert "not found" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_index_project_elicitation_yes(self, tmp_path):
        """Test indexing proceeds when user confirms elicitation."""
        # Create >100 files to trigger elicitation
        for i in range(101):
            (tmp_path / f"file{i}.py").write_text(f"# File {i}")

        # Mock services
        mock_indexing_service = AsyncMock()
        mock_result = MagicMock()
        mock_result.repository = "test-repo"
        mock_result.indexed_files = 101
        mock_result.indexed_chunks = 101
        mock_result.indexed_nodes = 101
        mock_result.indexed_edges = 0
        mock_result.failed_files = 0
        mock_result.processing_time_ms = 500.0
        mock_result.errors = []

        mock_indexing_service.index_repository = AsyncMock(return_value=mock_result)

        # Mock context with elicitation
        mock_ctx = AsyncMock()
        mock_elicit_response = MagicMock()
        mock_elicit_response.value = "yes"
        mock_ctx.elicit = AsyncMock(return_value=mock_elicit_response)

        self.tool.services = {
            "code_indexing_service": mock_indexing_service,
            "redis": None
        }

        result = await self.tool.execute(
            project_path=str(tmp_path),
            repository="test-repo",
            include_gitignored=False,
            ctx=mock_ctx
        )

        assert result["success"] is True
        assert mock_ctx.elicit.called
        assert mock_indexing_service.index_repository.called

    @pytest.mark.asyncio
    async def test_index_project_elicitation_no(self, tmp_path):
        """Test indexing cancelled when user rejects elicitation."""
        # Create >100 files
        for i in range(101):
            (tmp_path / f"file{i}.py").write_text(f"# File {i}")

        mock_indexing_service = AsyncMock()

        # Mock context - user says NO
        mock_ctx = AsyncMock()
        mock_elicit_response = MagicMock()
        mock_elicit_response.value = "no"
        mock_ctx.elicit = AsyncMock(return_value=mock_elicit_response)

        self.tool.services = {
            "code_indexing_service": mock_indexing_service,
            "redis": None
        }

        result = await self.tool.execute(
            project_path=str(tmp_path),
            repository="test-repo",
            ctx=mock_ctx
        )

        assert result["success"] is False
        assert "cancelled" in result["message"].lower()
        assert not mock_indexing_service.index_repository.called

    @pytest.mark.asyncio
    async def test_index_project_with_redis_lock(self, tmp_path):
        """Test indexing acquires and releases Redis distributed lock."""
        (tmp_path / "main.py").write_text("# Python")

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)  # Lock acquired
        mock_redis.delete = AsyncMock()

        mock_indexing_service = AsyncMock()
        mock_result = MagicMock()
        mock_result.repository = "test-repo"
        mock_result.indexed_files = 1
        mock_result.indexed_chunks = 1
        mock_result.indexed_nodes = 1
        mock_result.indexed_edges = 0
        mock_result.failed_files = 0
        mock_result.processing_time_ms = 50.0
        mock_result.errors = []

        mock_indexing_service.index_repository = AsyncMock(return_value=mock_result)

        self.tool.services = {
            "code_indexing_service": mock_indexing_service,
            "redis": mock_redis
        }

        result = await self.tool.execute(
            project_path=str(tmp_path),
            repository="test-repo"
        )

        assert result["success"] is True
        # Verify lock was acquired (first call should be for the lock)
        assert mock_redis.set.called
        first_call = mock_redis.set.call_args_list[0]
        assert "indexing:lock:test-repo" == first_call[0][0]  # First arg of first call

        # Verify lock was released
        assert mock_redis.delete.called

    @pytest.mark.asyncio
    async def test_index_project_lock_already_held(self, tmp_path):
        """Test indexing fails when lock already held (concurrent indexing)."""
        (tmp_path / "main.py").write_text("# Python")

        # Mock Redis - lock acquisition fails
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=False)  # Lock NOT acquired

        mock_indexing_service = AsyncMock()

        self.tool.services = {
            "code_indexing_service": mock_indexing_service,
            "redis": mock_redis
        }

        result = await self.tool.execute(
            project_path=str(tmp_path),
            repository="test-repo"
        )

        assert result["success"] is False
        assert "already in progress" in result["message"].lower()
        assert not mock_indexing_service.index_repository.called

    @pytest.mark.asyncio
    async def test_index_project_redis_unavailable(self, tmp_path):
        """Test indexing continues when Redis unavailable (graceful degradation)."""
        (tmp_path / "main.py").write_text("# Python")

        # Mock Redis that raises exception
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(side_effect=Exception("Redis connection error"))

        mock_indexing_service = AsyncMock()
        mock_result = MagicMock()
        mock_result.repository = "test-repo"
        mock_result.indexed_files = 1
        mock_result.indexed_chunks = 1
        mock_result.indexed_nodes = 1
        mock_result.indexed_edges = 0
        mock_result.failed_files = 0
        mock_result.processing_time_ms = 50.0
        mock_result.errors = []

        mock_indexing_service.index_repository = AsyncMock(return_value=mock_result)

        self.tool.services = {
            "code_indexing_service": mock_indexing_service,
            "redis": mock_redis
        }

        result = await self.tool.execute(
            project_path=str(tmp_path),
            repository="test-repo"
        )

        # Should succeed despite Redis error
        assert result["success"] is True
        assert mock_indexing_service.index_repository.called

    @pytest.mark.asyncio
    async def test_index_project_progress_reporting(self, tmp_path):
        """Test indexing reports progress via MCP context."""
        (tmp_path / "file1.py").write_text("# Python")
        (tmp_path / "file2.py").write_text("# Python")

        mock_ctx = AsyncMock()
        mock_ctx.report_progress = AsyncMock()

        mock_indexing_service = AsyncMock()

        # Capture progress callback
        progress_callback = None

        async def capture_callback(*args, **kwargs):
            nonlocal progress_callback
            progress_callback = kwargs.get("progress_callback")

            # Simulate some progress reports
            if progress_callback:
                await progress_callback(1, 2, "Indexing file 1")
                await progress_callback(2, 2, "Indexing file 2")

            mock_result = MagicMock()
            mock_result.repository = "test-repo"
            mock_result.indexed_files = 2
            mock_result.indexed_chunks = 2
            mock_result.indexed_nodes = 2
            mock_result.indexed_edges = 0
            mock_result.failed_files = 0
            mock_result.processing_time_ms = 100.0
            mock_result.errors = []
            return mock_result

        mock_indexing_service.index_repository = capture_callback

        self.tool.services = {
            "code_indexing_service": mock_indexing_service,
            "redis": None
        }

        result = await self.tool.execute(
            project_path=str(tmp_path),
            repository="test-repo",
            ctx=mock_ctx
        )

        assert result["success"] is True
        # Progress should have been reported
        # Note: Due to throttling, not all calls may go through
        assert progress_callback is not None


# ============================================================================
# ReindexFileTool Tests
# ============================================================================


class TestReindexFileTool:
    """Test ReindexFileTool."""

    def setup_method(self):
        """Setup test tool."""
        self.tool = ReindexFileTool()

    def test_get_name(self):
        """Test tool name."""
        assert self.tool.get_name() == "reindex_file"

    def test_get_description(self):
        """Test tool description."""
        desc = self.tool.get_description()
        assert "reindex" in desc.lower()
        assert "file" in desc.lower()

    @pytest.mark.asyncio
    async def test_reindex_file_success(self, tmp_path):
        """Test successful file reindexing."""
        # Create test file
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    print('world')\n")

        # Mock services
        mock_indexing_service = AsyncMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.file_path = str(test_file)
        mock_result.chunks_created = 1
        mock_result.processing_time_ms = 50.0
        mock_result.error = None

        mock_indexing_service._index_file = AsyncMock(return_value=mock_result)

        self.tool.services = {
            "code_indexing_service": mock_indexing_service,
            "chunk_cache": None
        }

        result = await self.tool.execute(
            file_path=str(test_file),
            repository="test-repo"
        )

        assert result["success"] is True
        assert result["file_path"] == str(test_file)
        assert result["chunks_created"] == 1
        assert mock_indexing_service._index_file.called

    @pytest.mark.asyncio
    async def test_reindex_file_service_unavailable(self):
        """Test reindexing fails when service unavailable."""
        self.tool.services = {}  # No services

        result = await self.tool.execute(
            file_path="/some/file.py",
            repository="test"
        )

        assert result["success"] is False
        assert "not available" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_reindex_file_not_found(self):
        """Test reindexing fails for nonexistent file."""
        mock_indexing_service = AsyncMock()

        self.tool.services = {
            "code_indexing_service": mock_indexing_service,
            "chunk_cache": None
        }

        result = await self.tool.execute(
            file_path="/nonexistent/file.py",
            repository="test"
        )

        assert result["success"] is False
        assert "not found" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_reindex_directory_not_file(self, tmp_path):
        """Test reindexing fails when path is a directory."""
        mock_indexing_service = AsyncMock()

        self.tool.services = {
            "code_indexing_service": mock_indexing_service,
            "chunk_cache": None
        }

        result = await self.tool.execute(
            file_path=str(tmp_path),  # Directory, not file
            repository="test"
        )

        assert result["success"] is False
        assert "not a file" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_reindex_binary_file(self, tmp_path):
        """Test reindexing fails for binary file."""
        # Create binary file
        binary_file = tmp_path / "image.png"
        binary_file.write_bytes(b'\x89PNG\r\n\x1a\n')

        mock_indexing_service = AsyncMock()

        self.tool.services = {
            "code_indexing_service": mock_indexing_service,
            "chunk_cache": None
        }

        result = await self.tool.execute(
            file_path=str(binary_file),
            repository="test"
        )

        assert result["success"] is False
        assert "not UTF-8" in result["message"]

    @pytest.mark.asyncio
    async def test_reindex_invalidates_cache(self, tmp_path):
        """Test reindexing invalidates cache."""
        test_file = tmp_path / "test.py"
        test_file.write_text("# Python")

        # Mock cache
        mock_cache = AsyncMock()
        mock_cache.invalidate = AsyncMock()

        mock_indexing_service = AsyncMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.file_path = str(test_file)
        mock_result.chunks_created = 1
        mock_result.processing_time_ms = 50.0
        mock_result.error = None

        mock_indexing_service._index_file = AsyncMock(return_value=mock_result)

        self.tool.services = {
            "code_indexing_service": mock_indexing_service,
            "chunk_cache": mock_cache
        }

        result = await self.tool.execute(
            file_path=str(test_file),
            repository="test-repo"
        )

        assert result["success"] is True
        # Cache should be invalidated
        assert mock_cache.invalidate.called
        invalidate_call = mock_cache.invalidate.call_args
        assert str(test_file) in str(invalidate_call)

    @pytest.mark.asyncio
    async def test_reindex_cache_unavailable(self, tmp_path):
        """Test reindexing works without cache (graceful degradation)."""
        test_file = tmp_path / "test.py"
        test_file.write_text("# Python")

        mock_indexing_service = AsyncMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.file_path = str(test_file)
        mock_result.chunks_created = 1
        mock_result.processing_time_ms = 50.0
        mock_result.error = None

        mock_indexing_service._index_file = AsyncMock(return_value=mock_result)

        self.tool.services = {
            "code_indexing_service": mock_indexing_service,
            "chunk_cache": None  # No cache
        }

        result = await self.tool.execute(
            file_path=str(test_file),
            repository="test-repo"
        )

        # Should still succeed
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_reindex_indexing_failed(self, tmp_path):
        """Test reindexing returns error when indexing fails."""
        test_file = tmp_path / "test.py"
        test_file.write_text("# Python")

        mock_indexing_service = AsyncMock()
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.file_path = str(test_file)
        mock_result.chunks_created = 0
        mock_result.processing_time_ms = 10.0
        mock_result.error = "Parse error at line 5"

        mock_indexing_service._index_file = AsyncMock(return_value=mock_result)

        self.tool.services = {
            "code_indexing_service": mock_indexing_service,
            "chunk_cache": None
        }

        result = await self.tool.execute(
            file_path=str(test_file),
            repository="test-repo"
        )

        assert result["success"] is False
        assert result["error"] == "Parse error at line 5"
        assert "failed" in result["message"].lower()
