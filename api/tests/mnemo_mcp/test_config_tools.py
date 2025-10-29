"""
Unit tests for Configuration Tools (EPIC-23 Story 23.7).

Tests cover:
- switch_project tool functionality
- Session state management
- Database query handling
- Case-insensitive repository matching
- Error handling for not found / no engine
"""
import pytest
from unittest.mock import AsyncMock, Mock, MagicMock
from datetime import datetime

from mnemo_mcp.tools.config_tools import (
    SwitchProjectTool,
    switch_project_tool,
)
from mnemo_mcp.models.config_models import SwitchProjectRequest


@pytest.fixture
def mock_context():
    """Create mock MCP Context with session."""
    mock_ctx = Mock()
    mock_session = {}

    def session_get(key):
        return mock_session.get(key)

    def session_set(key, value):
        mock_session[key] = value

    mock_ctx.session = Mock()
    mock_ctx.session.get = Mock(side_effect=session_get)
    mock_ctx.session.set = Mock(side_effect=session_set)

    # Mock elicit for elicitation (Story 23.11) - default to "yes" confirmation
    mock_ctx.elicit = AsyncMock(return_value=MagicMock(value="yes"))

    return mock_ctx


@pytest.fixture
def mock_db_engine():
    """Create mock SQLAlchemy async engine with connection."""
    # Mock result row
    mock_row = Mock()
    mock_row.repository = "test_project"
    mock_row.indexed_files = 10
    mock_row.total_chunks = 50
    mock_row.last_indexed = datetime(2025, 10, 28, 12, 0, 0)
    mock_row.languages = ["Python", "JavaScript"]

    # Mock result
    mock_result = Mock()
    mock_result.fetchone = Mock(return_value=mock_row)

    # Mock connection
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_result)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)

    # Mock engine
    mock_engine = Mock()
    mock_engine.connect = Mock(return_value=mock_conn)

    return mock_engine


@pytest.mark.asyncio
async def test_switch_project_success(mock_context, mock_db_engine):
    """Test successful project switch."""
    tool = SwitchProjectTool()
    tool.engine = mock_db_engine

    request = SwitchProjectRequest(repository="test_project")

    result = await tool.execute(ctx=mock_context, request=request)

    assert result.success is True
    assert result.repository == "test_project"
    assert result.indexed_files == 10
    assert result.total_chunks == 50
    assert result.languages == ["Python", "JavaScript"]
    assert result.last_indexed is not None
    assert "Switched to repository: test_project" in result.message

    # Verify session state was updated
    mock_context.session.set.assert_called_once_with("current_repository", "test_project")


@pytest.mark.asyncio
async def test_switch_project_case_insensitive(mock_context, mock_db_engine):
    """Test case-insensitive repository matching."""
    tool = SwitchProjectTool()
    tool.engine = mock_db_engine

    # Query with different case
    request = SwitchProjectRequest(repository="TEST_PROJECT")

    result = await tool.execute(ctx=mock_context, request=request)

    assert result.success is True
    # Should match "test_project" from mock (case-insensitive)
    assert result.repository == "test_project"


@pytest.mark.asyncio
async def test_switch_project_not_found(mock_context, mock_db_engine):
    """Test switching to non-existent repository."""
    # Mock empty result (repository not found)
    mock_result = Mock()
    mock_result.fetchone = Mock(return_value=None)

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_result)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)

    mock_engine = Mock()
    mock_engine.connect = Mock(return_value=mock_conn)

    tool = SwitchProjectTool()
    tool.engine = mock_engine

    request = SwitchProjectRequest(repository="nonexistent_repo")

    with pytest.raises(ValueError) as exc_info:
        await tool.execute(ctx=mock_context, request=request)

    assert "not found or not indexed" in str(exc_info.value).lower()
    assert "use index_project tool" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_switch_project_no_engine(mock_context):
    """Test error when database engine is unavailable."""
    tool = SwitchProjectTool()
    tool.engine = None  # No engine available

    request = SwitchProjectRequest(repository="test_project")

    with pytest.raises(ValueError) as exc_info:
        await tool.execute(ctx=mock_context, request=request)

    assert "database engine not available" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_switch_project_with_confirm_flag(mock_context, mock_db_engine):
    """Test confirm parameter (for future elicitation bypass)."""
    tool = SwitchProjectTool()
    tool.engine = mock_db_engine

    # Request with confirm=True (for automation)
    request = SwitchProjectRequest(repository="test_project", confirm=True)

    result = await tool.execute(ctx=mock_context, request=request)

    # Should succeed regardless of confirm flag (elicitation not yet implemented)
    assert result.success is True
    assert result.repository == "test_project"


@pytest.mark.asyncio
async def test_switch_project_empty_languages(mock_context, mock_db_engine):
    """Test project with no languages detected."""
    # Mock result with empty languages
    mock_row = Mock()
    mock_row.repository = "empty_project"
    mock_row.indexed_files = 0
    mock_row.total_chunks = 0
    mock_row.last_indexed = None
    mock_row.languages = None  # NULL in database

    mock_result = Mock()
    mock_result.fetchone = Mock(return_value=mock_row)

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_result)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)

    mock_engine = Mock()
    mock_engine.connect = Mock(return_value=mock_conn)

    tool = SwitchProjectTool()
    tool.engine = mock_engine

    request = SwitchProjectRequest(repository="empty_project")

    result = await tool.execute(ctx=mock_context, request=request)

    assert result.success is True
    assert result.languages == []  # Should convert None to []
    assert result.indexed_files == 0


@pytest.mark.asyncio
async def test_singleton_instance_available():
    """Test that singleton tool instance is available for registration."""
    assert switch_project_tool is not None
    assert isinstance(switch_project_tool, SwitchProjectTool)
    assert switch_project_tool.get_name() == "switch_project"
