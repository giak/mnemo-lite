"""
Unit tests for Indexing Tools (EPIC-23 Story 23.5).

Tests cover:
- index_project tool functionality
- reindex_file tool functionality
- Progress reporting integration
- Elicitation flows
- Distributed locking
- Error handling and edge cases
"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime

from mnemo_mcp.tools.indexing_tools import (
    IndexProjectTool,
    ReindexFileTool,
    index_project_tool,
    reindex_file_tool,
)


@pytest.fixture
def mock_services():
    """Create mock services for testing."""
    # Mock CodeIndexingService
    mock_indexing_service = AsyncMock()
    mock_indexing_service.index_repository = AsyncMock(return_value=Mock(
        repository="test_repo",
        indexed_files=5,
        indexed_chunks=50,
        indexed_nodes=20,
        indexed_edges=15,
        failed_files=0,
        processing_time_ms=500,
        errors=[]
    ))
    mock_indexing_service._index_file = AsyncMock(return_value=Mock(
        success=True,
        file_path="/test/file.py",
        chunks_created=10,
        processing_time_ms=50,
        error=None
    ))

    # Mock Redis client
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.delete = AsyncMock()

    # Mock ChunkCache
    mock_cache = AsyncMock()
    mock_cache.invalidate = AsyncMock()

    return {
        "code_indexing_service": mock_indexing_service,
        "redis": mock_redis,
        "chunk_cache": mock_cache,
    }


@pytest.fixture
def temp_project_small():
    """Create small temporary project (5 files)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Create 5 code files
        for i in range(5):
            (project_root / f"file_{i}.py").write_text(f"# File {i}\nprint('test')")

        yield str(project_root)


@pytest.fixture
def temp_project_large():
    """Create large temporary project (150 files) for elicitation test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Create 150 code files (triggers elicitation at >100)
        for i in range(150):
            (project_root / f"file_{i}.py").write_text(f"# File {i}")

        yield str(project_root)


@pytest.mark.asyncio
async def test_index_project_success(mock_services, temp_project_small):
    """Test successful project indexing."""
    tool = IndexProjectTool()
    tool.inject_services(mock_services)

    result = await tool.execute(
        project_path=temp_project_small,
        repository="test_repo",
        include_gitignored=False,
        ctx=None,
    )

    assert result["success"] is True
    assert result["repository"] == "test_repo"
    assert result["indexed_files"] == 5
    assert result["indexed_chunks"] == 50
    assert result["indexed_nodes"] == 20
    assert result["indexed_edges"] == 15
    assert result["failed_files"] == 0

    # Verify lock was acquired and released
    mock_redis = mock_services["redis"]
    assert mock_redis.set.called
    assert mock_redis.delete.called


@pytest.mark.asyncio
async def test_index_project_with_progress_callback(mock_services, temp_project_small):
    """Test progress callback is called during indexing."""
    tool = IndexProjectTool()
    tool.inject_services(mock_services)

    # Mock MCP context
    mock_ctx = AsyncMock()
    mock_ctx.report_progress = AsyncMock()

    result = await tool.execute(
        project_path=temp_project_small,
        repository="test_repo",
        include_gitignored=False,
        ctx=mock_ctx,
    )

    assert result["success"] is True

    # Verify progress_callback was passed to indexing service
    indexing_service = mock_services["code_indexing_service"]
    assert indexing_service.index_repository.called
    call_kwargs = indexing_service.index_repository.call_args[1]
    assert "progress_callback" in call_kwargs
    assert callable(call_kwargs["progress_callback"])


@pytest.mark.asyncio
async def test_index_project_elicitation_yes(mock_services, temp_project_large):
    """Test elicitation flow when user confirms (>100 files)."""
    tool = IndexProjectTool()
    tool.inject_services(mock_services)

    # Mock MCP context with elicitation
    mock_ctx = AsyncMock()
    mock_ctx.elicit = AsyncMock(return_value=Mock(value="yes"))
    mock_ctx.report_progress = AsyncMock()

    result = await tool.execute(
        project_path=temp_project_large,
        repository="test_repo",
        include_gitignored=False,
        ctx=mock_ctx,
    )

    # Should proceed with indexing
    assert result["success"] is True
    assert mock_ctx.elicit.called

    # Verify elicitation prompt
    elicit_call_args = mock_ctx.elicit.call_args
    assert "150 files" in elicit_call_args[1]["prompt"]


@pytest.mark.asyncio
async def test_index_project_elicitation_no(mock_services, temp_project_large):
    """Test elicitation flow when user cancels (>100 files)."""
    tool = IndexProjectTool()
    tool.inject_services(mock_services)

    # Mock MCP context - user says no
    mock_ctx = AsyncMock()
    mock_ctx.elicit = AsyncMock(return_value=Mock(value="no"))

    result = await tool.execute(
        project_path=temp_project_large,
        repository="test_repo",
        include_gitignored=False,
        ctx=mock_ctx,
    )

    # Should cancel indexing
    assert result["success"] is False
    assert "cancelled by user" in result["message"].lower()

    # Indexing service should NOT be called
    indexing_service = mock_services["code_indexing_service"]
    assert not indexing_service.index_repository.called


@pytest.mark.asyncio
async def test_index_project_concurrent_prevention(mock_services, temp_project_small):
    """Test distributed lock prevents concurrent indexing."""
    tool = IndexProjectTool()
    tool.inject_services(mock_services)

    # Mock Redis lock already acquired (returns False)
    mock_redis = mock_services["redis"]
    mock_redis.set = AsyncMock(return_value=False)

    result = await tool.execute(
        project_path=temp_project_small,
        repository="test_repo",
        include_gitignored=False,
        ctx=None,
    )

    # Should reject due to lock
    assert result["success"] is False
    assert "already in progress" in result["message"].lower()

    # Indexing service should NOT be called
    indexing_service = mock_services["code_indexing_service"]
    assert not indexing_service.index_repository.called


@pytest.mark.asyncio
async def test_index_project_redis_unavailable_graceful(temp_project_small):
    """Test graceful degradation when Redis is unavailable."""
    # Services without Redis
    services_no_redis = {
        "code_indexing_service": AsyncMock(),
        "redis": None,  # Redis unavailable
        "chunk_cache": None,
    }

    services_no_redis["code_indexing_service"].index_repository = AsyncMock(
        return_value=Mock(
            repository="test_repo",
            indexed_files=5,
            indexed_chunks=50,
            indexed_nodes=20,
            indexed_edges=15,
            failed_files=0,
            processing_time_ms=500,
            errors=[]
        )
    )

    tool = IndexProjectTool()
    tool.inject_services(services_no_redis)

    # Should work without Redis (no lock, no status updates)
    result = await tool.execute(
        project_path=temp_project_small,
        repository="test_repo",
        include_gitignored=False,
        ctx=None,
    )

    assert result["success"] is True
    assert result["indexed_files"] == 5


@pytest.mark.asyncio
async def test_index_project_invalid_path(mock_services):
    """Test error handling for invalid project path."""
    tool = IndexProjectTool()
    tool.inject_services(mock_services)

    result = await tool.execute(
        project_path="/nonexistent/path",
        repository="test_repo",
        include_gitignored=False,
        ctx=None,
    )

    assert result["success"] is False
    assert "not found" in result["message"].lower()


@pytest.mark.asyncio
async def test_index_project_service_unavailable():
    """Test error when CodeIndexingService is unavailable."""
    services = {
        "code_indexing_service": None,  # Service not available
        "redis": AsyncMock(),
        "chunk_cache": None,
    }

    tool = IndexProjectTool()
    tool.inject_services(services)

    with tempfile.TemporaryDirectory() as tmpdir:
        result = await tool.execute(
            project_path=tmpdir,
            repository="test_repo",
            include_gitignored=False,
            ctx=None,
        )

    assert result["success"] is False
    assert "not available" in result["message"].lower()


@pytest.mark.asyncio
async def test_reindex_file_success(mock_services):
    """Test successful file reindexing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmpfile:
        tmpfile.write("# Test file\nprint('hello')")
        tmpfile.flush()

        tool = ReindexFileTool()
        tool.inject_services(mock_services)

        result = await tool.execute(
            file_path=tmpfile.name,
            repository="test_repo",
            ctx=None,
        )

        assert result["success"] is True
        assert result["file_path"] == tmpfile.name
        assert result["chunks_created"] == 10
        assert result["processing_time_ms"] == 50

        # Verify cache was invalidated
        mock_cache = mock_services["chunk_cache"]
        assert mock_cache.invalidate.called

        # Cleanup
        Path(tmpfile.name).unlink()


@pytest.mark.asyncio
async def test_reindex_file_invalid_path(mock_services):
    """Test reindexing with invalid file path."""
    tool = ReindexFileTool()
    tool.inject_services(mock_services)

    result = await tool.execute(
        file_path="/nonexistent/file.py",
        repository="test_repo",
        ctx=None,
    )

    assert result["success"] is False
    assert "not found" in result["message"].lower()


@pytest.mark.asyncio
async def test_reindex_file_not_a_file(mock_services):
    """Test reindexing with directory path instead of file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tool = ReindexFileTool()
        tool.inject_services(mock_services)

        result = await tool.execute(
            file_path=tmpdir,
            repository="test_repo",
            ctx=None,
        )

        assert result["success"] is False
        assert "not a file" in result["message"].lower()


@pytest.mark.asyncio
async def test_reindex_file_non_utf8(mock_services):
    """Test reindexing with non-UTF-8 file."""
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".py", delete=False) as tmpfile:
        tmpfile.write(b"\xff\xfe\x00Invalid UTF-8")
        tmpfile.flush()

        tool = ReindexFileTool()
        tool.inject_services(mock_services)

        result = await tool.execute(
            file_path=tmpfile.name,
            repository="test_repo",
            ctx=None,
        )

        assert result["success"] is False
        assert "utf-8" in result["message"].lower()

        # Cleanup
        Path(tmpfile.name).unlink()


@pytest.mark.asyncio
async def test_reindex_file_service_unavailable():
    """Test reindexing when service is unavailable."""
    services = {
        "code_indexing_service": None,
        "redis": None,
        "chunk_cache": None,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmpfile:
        tmpfile.write("# Test")
        tmpfile.flush()

        tool = ReindexFileTool()
        tool.inject_services(services)

        result = await tool.execute(
            file_path=tmpfile.name,
            repository="test_repo",
            ctx=None,
        )

        assert result["success"] is False
        assert "not available" in result["message"].lower()

        # Cleanup
        Path(tmpfile.name).unlink()


@pytest.mark.asyncio
async def test_singleton_instances_available():
    """Test that singleton tool instances are available for registration."""
    assert index_project_tool is not None
    assert isinstance(index_project_tool, IndexProjectTool)

    assert reindex_file_tool is not None
    assert isinstance(reindex_file_tool, ReindexFileTool)
