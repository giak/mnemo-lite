"""
Tests for outcome feedback feature.

Tests:
1. compute_outcome_factor in MemoryDecayService
2. rate_memory tool validation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

# Import from the service layer (same as other tests)
from api.services.memory_decay_service import MemoryDecayService

# Import the tool
from mnemo_mcp.tools.memory_tools import RateMemoryTool


# ============================================================================
# Tests for compute_outcome_factor (MemoryDecayService)
# ============================================================================

class TestComputeOutcomeFactor:
    """Tests for MemoryDecayService.compute_outcome_factor."""

    def test_no_feedback_returns_1_0(self):
        """No feedback should return neutral factor of 1.0."""
        result = MemoryDecayService.compute_outcome_factor(0, 0)
        assert result == 1.0

    def test_positive_feedback_increases_factor(self):
        """Positive feedback should increase factor.
        
        Formula: 1 + 0.5 * (pos - neg) / (pos + neg + 1)
        For (5, 0): ratio = 5/6 = 0.8333, factor = 1.4167
        """
        result = MemoryDecayService.compute_outcome_factor(5, 0)
        assert 1.4 < result < 1.42

    def test_negative_feedback_decreases_factor(self):
        """Negative feedback should decrease factor.
        
        Formula: 1 + 0.5 * (pos - neg) / (pos + neg + 1)
        For (0, 5): ratio = -5/6 = -0.8333, factor = 0.5833
        """
        result = MemoryDecayService.compute_outcome_factor(0, 5)
        assert 0.58 < result < 0.6

    def test_mixed_feedback_balanced(self):
        """Mixed feedback should result in slightly positive factor.
        
        Formula: 1 + 0.5 * (pos - neg) / (pos + neg + 1)
        For (3, 2): ratio = 1/6 = 0.1667, factor = 1.0833
        """
        result = MemoryDecayService.compute_outcome_factor(3, 2)
        assert 1.08 < result < 1.1

    def test_factor_bounds(self):
        """Factor should stay within bounds (0.5 to 1.5) at extremes."""
        # Maximum positive
        result = MemoryDecayService.compute_outcome_factor(100, 0)
        assert result < 1.5
        
        # Maximum negative
        result = MemoryDecayService.compute_outcome_factor(0, 100)
        assert result > 0.5


# ============================================================================
# Tests for rate_memory tool
# ============================================================================

@pytest.fixture
def mock_ctx():
    """Mock MCP Context."""
    ctx = MagicMock()
    ctx.elicit = AsyncMock(return_value=MagicMock(value="yes"))
    return ctx


@pytest.fixture
def mock_memory_repository():
    """Mock MemoryRepository."""
    repo = AsyncMock()
    repo.rate_memory = AsyncMock(return_value={
        "id": "test-id",
        "outcome_positive": 1,
        "outcome_negative": 0,
        "outcome_score": 1.0,
        "last_outcome_at": "2026-04-10T00:00:00Z"
    })
    return repo


class TestRateMemoryToolValidation:
    """Tests for rate_memory tool validation."""

    @pytest.mark.asyncio
    async def test_missing_id_raises_error(self, mock_ctx, mock_memory_repository):
        """Missing id should raise ValueError."""
        tool = RateMemoryTool()
        tool.inject_services({
            "memory_repository": mock_memory_repository
        })

        with pytest.raises(ValueError) as exc_info:
            await tool.execute(ctx=mock_ctx, helpful=True)
        
        assert "id" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_missing_helpful_raises_error(self, mock_ctx, mock_memory_repository):
        """Missing helpful should raise ValueError."""
        tool = RateMemoryTool()
        tool.inject_services({
            "memory_repository": mock_memory_repository
        })

        with pytest.raises(ValueError) as exc_info:
            await tool.execute(ctx=mock_ctx, id="test-id")
        
        assert "helpful" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_invalid_score_below_range_raises_error(self, mock_ctx, mock_memory_repository):
        """Score below -1.0 should raise ValueError."""
        tool = RateMemoryTool()
        tool.inject_services({
            "memory_repository": mock_memory_repository
        })

        with pytest.raises(ValueError) as exc_info:
            await tool.execute(
                ctx=mock_ctx,
                id="test-id",
                helpful=True,
                score=-1.5
            )
        
        assert "score" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_invalid_score_above_range_raises_error(self, mock_ctx, mock_memory_repository):
        """Score above 1.0 should raise ValueError."""
        tool = RateMemoryTool()
        tool.inject_services({
            "memory_repository": mock_memory_repository
        })

        with pytest.raises(ValueError) as exc_info:
            await tool.execute(
                ctx=mock_ctx,
                id="test-id",
                helpful=True,
                score=1.5
            )
        
        assert "score" in str(exc_info.value).lower()


class TestRateMemoryToolExecute:
    """Tests for rate_memory tool execution."""

    @pytest.mark.asyncio
    async def test_execute_positive_rating(self, mock_ctx, mock_memory_repository):
        """Positive rating should call repository with helpful=True."""
        tool = RateMemoryTool()
        tool.inject_services({
            "memory_repository": mock_memory_repository
        })

        result = await tool.execute(
            ctx=mock_ctx,
            id="test-id",
            helpful=True
        )

        # Verify the call was made with correct parameters
        mock_memory_repository.rate_memory.assert_called_once_with(
            memory_id="test-id",
            helpful=True,
            score=None
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_execute_negative_rating(self, mock_ctx, mock_memory_repository):
        """Negative rating should call repository with helpful=False."""
        tool = RateMemoryTool()
        tool.inject_services({
            "memory_repository": mock_memory_repository
        })

        result = await tool.execute(
            ctx=mock_ctx,
            id="test-id",
            helpful=False
        )

        # Verify the call was made with correct parameters
        mock_memory_repository.rate_memory.assert_called_once_with(
            memory_id="test-id",
            helpful=False,
            score=None
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_execute_with_explicit_score(self, mock_ctx, mock_memory_repository):
        """Explicit score should be passed to repository."""
        tool = RateMemoryTool()
        tool.inject_services({
            "memory_repository": mock_memory_repository
        })

        result = await tool.execute(
            ctx=mock_ctx,
            id="test-id",
            helpful=True,
            score=0.8
        )

        mock_memory_repository.rate_memory.assert_called_once_with(
            memory_id="test-id",
            helpful=True,
            score=0.8
        )
        assert result is not None
