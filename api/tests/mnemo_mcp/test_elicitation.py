"""
Unit tests for Elicitation Helpers (EPIC-23 Story 23.11).

Tests cover:
- request_confirmation() with user confirmation
- request_confirmation() with user cancellation
- request_confirmation() with dangerous flag
- request_confirmation() with error handling
- request_choice() with user selection
- request_choice() with user cancellation
- request_choice() with error handling
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from mnemo_mcp.elicitation import (
    request_confirmation,
    request_choice,
    ElicitationResult,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_context_confirm():
    """Mock MCP context that confirms action (user selects 'yes')."""
    ctx = MagicMock()
    ctx.elicit = AsyncMock(return_value=MagicMock(value="yes"))
    return ctx


@pytest.fixture
def mock_context_cancel():
    """Mock MCP context that cancels action (user selects 'no')."""
    ctx = MagicMock()
    ctx.elicit = AsyncMock(return_value=MagicMock(value="no"))
    return ctx


@pytest.fixture
def mock_context_choice():
    """Mock MCP context that selects an option."""
    ctx = MagicMock()
    ctx.elicit = AsyncMock(return_value=MagicMock(value="Option B"))
    return ctx


@pytest.fixture
def mock_context_error():
    """Mock MCP context that raises an error."""
    ctx = MagicMock()
    ctx.elicit = AsyncMock(side_effect=RuntimeError("Elicitation failed"))
    return ctx


# ============================================================================
# request_confirmation() Tests
# ============================================================================

@pytest.mark.asyncio
async def test_request_confirmation_confirmed(mock_context_confirm):
    """Test user confirms action (selects 'yes')."""
    result = await request_confirmation(
        mock_context_confirm,
        action="Test Action",
        details="Test details for confirmation"
    )

    # Verify result
    assert result.confirmed is True
    assert result.cancelled is False
    assert result.selected_option == "yes"

    # Verify elicit was called
    mock_context_confirm.elicit.assert_called_once()
    call_args = mock_context_confirm.elicit.call_args
    assert "Test Action" in call_args.kwargs["prompt"]
    assert "Test details" in call_args.kwargs["prompt"]


@pytest.mark.asyncio
async def test_request_confirmation_cancelled(mock_context_cancel):
    """Test user cancels action (selects 'no')."""
    result = await request_confirmation(
        mock_context_cancel,
        action="Test Action",
        details="Test details for cancellation"
    )

    # Verify result
    assert result.confirmed is False
    assert result.cancelled is True
    assert result.selected_option == "no"

    # Verify elicit was called
    mock_context_cancel.elicit.assert_called_once()


@pytest.mark.asyncio
async def test_request_confirmation_dangerous_flag(mock_context_confirm):
    """Test dangerous flag adds warning icon to prompt."""
    result = await request_confirmation(
        mock_context_confirm,
        action="Delete Memory",
        details="This will permanently delete memory",
        dangerous=True
    )

    # Verify result (still confirms)
    assert result.confirmed is True

    # Verify prompt includes warning icon
    call_args = mock_context_confirm.elicit.call_args
    assert "⚠️" in call_args.kwargs["prompt"]
    assert "Delete Memory" in call_args.kwargs["prompt"]


@pytest.mark.asyncio
async def test_request_confirmation_error_handling(mock_context_error):
    """Test error handling returns safe default (cancelled)."""
    result = await request_confirmation(
        mock_context_error,
        action="Test Action",
        details="Test details"
    )

    # On error, should return cancelled (safe default)
    assert result.confirmed is False
    assert result.cancelled is True
    assert result.selected_option is None


# ============================================================================
# request_choice() Tests
# ============================================================================

@pytest.mark.asyncio
async def test_request_choice_selected(mock_context_choice):
    """Test user selects an option."""
    choice = await request_choice(
        mock_context_choice,
        question="Pick one:",
        choices=["Option A", "Option B", "Option C"]
    )

    # Verify result
    assert choice == "Option B"

    # Verify elicit was called with Cancel added
    call_args = mock_context_choice.elicit.call_args
    assert "Pick one:" in call_args.kwargs["prompt"]
    schema = call_args.kwargs["schema"]
    assert "Cancel" in schema["enum"]
    assert "Option A" in schema["enum"]
    assert "Option B" in schema["enum"]
    assert "Option C" in schema["enum"]


@pytest.mark.asyncio
async def test_request_choice_cancelled():
    """Test user cancels choice (raises ValueError)."""
    ctx = MagicMock()
    ctx.elicit = AsyncMock(return_value=MagicMock(value="Cancel"))

    with pytest.raises(ValueError) as exc_info:
        await request_choice(
            ctx,
            question="Pick one:",
            choices=["Option A", "Option B"]
        )

    assert "cancelled" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_request_choice_error_handling(mock_context_error):
    """Test error handling raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        await request_choice(
            mock_context_error,
            question="Pick one:",
            choices=["Option A", "Option B"]
        )

    # Error should be wrapped in ValueError
    assert "failed" in str(exc_info.value).lower() or "cancelled" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_request_choice_with_default(mock_context_choice):
    """Test request_choice with default option (for future use)."""
    choice = await request_choice(
        mock_context_choice,
        question="Pick one:",
        choices=["Option A", "Option B", "Option C"],
        default="Option A"
    )

    # Should still return selected option (default param currently unused)
    assert choice == "Option B"

    # Verify elicit was called
    mock_context_choice.elicit.assert_called_once()


# ============================================================================
# ElicitationResult Model Tests
# ============================================================================

def test_elicitation_result_model():
    """Test ElicitationResult Pydantic model."""
    # Test with all fields
    result = ElicitationResult(
        confirmed=True,
        selected_option="yes",
        cancelled=False
    )

    assert result.confirmed is True
    assert result.selected_option == "yes"
    assert result.cancelled is False

    # Test with defaults
    result_defaults = ElicitationResult(confirmed=False)
    assert result_defaults.confirmed is False
    assert result_defaults.selected_option is None
    assert result_defaults.cancelled is False


def test_elicitation_result_model_dump():
    """Test ElicitationResult serialization."""
    result = ElicitationResult(
        confirmed=True,
        selected_option="yes",
        cancelled=False
    )

    dumped = result.model_dump()

    assert dumped["confirmed"] is True
    assert dumped["selected_option"] == "yes"
    assert dumped["cancelled"] is False
