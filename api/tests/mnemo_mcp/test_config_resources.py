"""
Unit tests for Configuration Resources (EPIC-23 Story 23.7).

Tests cover:
- projects://list resource functionality
- config://languages resource functionality
- Active project marker
- Language metadata exposure
- Error handling for no engine
"""
import pytest
from unittest.mock import AsyncMock, Mock
from datetime import datetime

from mnemo_mcp.resources.config_resources import (
    ListProjectsResource,
    SupportedLanguagesResource,
    list_projects_resource,
    supported_languages_resource,
)


@pytest.fixture
def mock_context_with_active():
    """Create mock MCP Context with active repository in session."""
    mock_ctx = Mock()
    mock_ctx.session = Mock()
    mock_ctx.session.get = Mock(return_value="project_alpha")  # Active project
    return mock_ctx


@pytest.fixture
def mock_context_no_active():
    """Create mock MCP Context without active repository."""
    mock_ctx = Mock()
    mock_ctx.session = Mock()
    mock_ctx.session.get = Mock(return_value=None)  # No active project
    return mock_ctx


@pytest.fixture
def mock_db_engine_multiple_projects():
    """Create mock engine with multiple projects."""
    # Mock result rows
    mock_rows = [
        Mock(
            repository="project_alpha",
            indexed_files=10,
            total_chunks=50,
            last_indexed=datetime(2025, 10, 28, 12, 0, 0),
            languages=["Python", "JavaScript"]
        ),
        Mock(
            repository="project_beta",
            indexed_files=5,
            total_chunks=25,
            last_indexed=datetime(2025, 10, 27, 10, 0, 0),
            languages=["Go", "Rust"]
        ),
        Mock(
            repository="project_gamma",
            indexed_files=15,
            total_chunks=75,
            last_indexed=datetime(2025, 10, 26, 8, 0, 0),
            languages=["TypeScript"]
        ),
    ]

    # Mock result
    mock_result = Mock()
    mock_result.fetchall = Mock(return_value=mock_rows)

    # Mock connection
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_result)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)

    # Mock engine
    mock_engine = Mock()
    mock_engine.connect = Mock(return_value=mock_conn)

    return mock_engine


@pytest.fixture
def mock_db_engine_empty():
    """Create mock engine with no projects."""
    mock_result = Mock()
    mock_result.fetchall = Mock(return_value=[])

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_result)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)

    mock_engine = Mock()
    mock_engine.connect = Mock(return_value=mock_conn)

    return mock_engine


# ============================================================================
# ListProjectsResource Tests
# ============================================================================


@pytest.mark.asyncio
async def test_list_projects_multiple_with_active(
    mock_context_with_active,
    mock_db_engine_multiple_projects
):
    """Test listing multiple projects with active marker."""
    resource = ListProjectsResource()
    resource.engine = mock_db_engine_multiple_projects

    response = await resource.get(ctx=mock_context_with_active)

    assert response.total == 3
    assert len(response.projects) == 3
    assert response.active_repository == "project_alpha"

    # Verify active marker on correct project
    project_alpha = next(p for p in response.projects if p.repository == "project_alpha")
    assert project_alpha.is_active is True
    assert project_alpha.indexed_files == 10
    assert project_alpha.total_chunks == 50
    assert project_alpha.languages == ["Python", "JavaScript"]

    # Verify other projects are not active
    project_beta = next(p for p in response.projects if p.repository == "project_beta")
    assert project_beta.is_active is False

    project_gamma = next(p for p in response.projects if p.repository == "project_gamma")
    assert project_gamma.is_active is False


@pytest.mark.asyncio
async def test_list_projects_no_active_session(
    mock_context_no_active,
    mock_db_engine_multiple_projects
):
    """Test listing projects without active repository in session."""
    resource = ListProjectsResource()
    resource.engine = mock_db_engine_multiple_projects

    response = await resource.get(ctx=mock_context_no_active)

    assert response.total == 3
    assert response.active_repository is None

    # Verify no projects are marked as active
    for project in response.projects:
        assert project.is_active is False


@pytest.mark.asyncio
async def test_list_projects_empty_database(
    mock_context_with_active,
    mock_db_engine_empty
):
    """Test listing projects when database is empty."""
    resource = ListProjectsResource()
    resource.engine = mock_db_engine_empty

    response = await resource.get(ctx=mock_context_with_active)

    assert response.total == 0
    assert len(response.projects) == 0
    assert response.active_repository == "project_alpha"


@pytest.mark.asyncio
async def test_list_projects_no_engine(mock_context_with_active):
    """Test listing projects when engine is unavailable."""
    resource = ListProjectsResource()
    resource.engine = None  # No engine

    response = await resource.get(ctx=mock_context_with_active)

    # Should return empty list gracefully
    assert response.total == 0
    assert len(response.projects) == 0
    assert response.active_repository == "project_alpha"


@pytest.mark.asyncio
async def test_list_projects_null_languages(mock_context_with_active):
    """Test project with NULL languages in database."""
    # Mock result with NULL languages
    mock_row = Mock(
        repository="project_no_lang",
        indexed_files=1,
        total_chunks=5,
        last_indexed=datetime(2025, 10, 28, 12, 0, 0),
        languages=None  # NULL in database
    )

    mock_result = Mock()
    mock_result.fetchall = Mock(return_value=[mock_row])

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_result)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)

    mock_engine = Mock()
    mock_engine.connect = Mock(return_value=mock_conn)

    resource = ListProjectsResource()
    resource.engine = mock_engine

    response = await resource.get(ctx=mock_context_with_active)

    assert response.total == 1
    # Should convert None to []
    assert response.projects[0].languages == []


# ============================================================================
# SupportedLanguagesResource Tests
# ============================================================================


@pytest.mark.asyncio
async def test_supported_languages_list(mock_context_with_active):
    """Test listing supported languages."""
    resource = SupportedLanguagesResource()

    response = await resource.get(ctx=mock_context_with_active)

    # Should have all 15 languages from config/languages.py
    assert response.total == 15
    assert len(response.languages) == 15

    # Verify Python is present
    python = next(lang for lang in response.languages if lang.name == "Python")
    assert python.name == "Python"
    assert ".py" in python.extensions
    assert ".pyi" in python.extensions
    assert python.tree_sitter_grammar == "tree-sitter-python"
    assert python.embedding_model == "nomic-embed-text-v1.5"


@pytest.mark.asyncio
async def test_supported_languages_javascript(mock_context_with_active):
    """Test JavaScript language metadata."""
    resource = SupportedLanguagesResource()

    response = await resource.get(ctx=mock_context_with_active)

    javascript = next(lang for lang in response.languages if lang.name == "JavaScript")
    assert javascript.name == "JavaScript"
    assert ".js" in javascript.extensions
    assert ".jsx" in javascript.extensions
    assert ".mjs" in javascript.extensions
    assert ".cjs" in javascript.extensions
    assert javascript.tree_sitter_grammar == "tree-sitter-javascript"


@pytest.mark.asyncio
async def test_supported_languages_all_have_metadata(mock_context_with_active):
    """Test all languages have required metadata fields."""
    resource = SupportedLanguagesResource()

    response = await resource.get(ctx=mock_context_with_active)

    for lang in response.languages:
        assert lang.name  # Non-empty
        assert len(lang.extensions) > 0  # At least one extension
        assert lang.tree_sitter_grammar.startswith("tree-sitter-")
        assert lang.embedding_model == "nomic-embed-text-v1.5"


@pytest.mark.asyncio
async def test_supported_languages_specific_count(mock_context_with_active):
    """Test expected language count matches configuration."""
    resource = SupportedLanguagesResource()

    response = await resource.get(ctx=mock_context_with_active)

    # Expected languages from config/languages.py
    expected_languages = {
        "Python", "JavaScript", "TypeScript", "Go", "Rust",
        "Java", "C#", "Ruby", "PHP", "C", "C++",
        "Swift", "Kotlin", "Scala", "Bash"
    }

    language_names = {lang.name for lang in response.languages}
    assert language_names == expected_languages


@pytest.mark.asyncio
async def test_supported_languages_no_engine_required(mock_context_with_active):
    """Test that languages resource doesn't require database engine."""
    resource = SupportedLanguagesResource()
    resource.engine = None  # No engine needed for static config

    response = await resource.get(ctx=mock_context_with_active)

    # Should still work (config is static)
    assert response.total == 15
    assert len(response.languages) == 15


# ============================================================================
# Singleton Instance Tests
# ============================================================================


@pytest.mark.asyncio
async def test_singleton_instances_available():
    """Test that singleton resource instances are available for registration."""
    assert list_projects_resource is not None
    assert isinstance(list_projects_resource, ListProjectsResource)
    assert list_projects_resource.get_name() == "projects://list"

    assert supported_languages_resource is not None
    assert isinstance(supported_languages_resource, SupportedLanguagesResource)
    assert supported_languages_resource.get_name() == "config://languages"
