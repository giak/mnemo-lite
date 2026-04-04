"""Tests for EPIC-30: Consolidation MCP Tools."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from mnemo_mcp.tools.consolidation_tools import SuggestConsolidationTool


class TestSuggestConsolidationTool:
    """Tests for SuggestConsolidationTool."""

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful consolidation suggestion."""
        mock_engine = MagicMock()
        mock_redis = AsyncMock()

        tool = SuggestConsolidationTool(engine=mock_engine, redis_client=mock_redis)

        with patch("services.consolidation_suggestion_service.ConsolidationSuggestionService") as mock_service_cls:
            mock_service = MagicMock()
            mock_group = MagicMock()
            mock_group.memory_ids = ["uuid1", "uuid2", "uuid3"]
            mock_group.titles = ["Redis cache", "Redis TTL", "Redis persistence"]
            mock_group.content_previews = ["preview1", "preview2", "preview3"]
            mock_group.shared_entities = {"redis", "cache"}
            mock_group.shared_concepts = {"cache layer"}
            mock_group.avg_similarity = 0.72
            mock_service.suggest_consolidation = AsyncMock(return_value=[mock_group])
            mock_service.suggest_title.return_value = "Redis cache configuration"
            mock_service.suggest_hint.return_value = "3 memories about redis, cache: cache layer"
            mock_service_cls.return_value = mock_service

            result = await tool.execute()

            assert result["total_groups_found"] == 1
            assert len(result["groups"]) == 1
            assert result["groups"][0]["source_ids"] == ["uuid1", "uuid2", "uuid3"]
            assert result["groups"][0]["suggested_title"] == "Redis cache configuration"

    @pytest.mark.asyncio
    async def test_execute_no_groups(self):
        """Test returns empty groups when no similarities found."""
        mock_engine = MagicMock()
        mock_redis = AsyncMock()

        tool = SuggestConsolidationTool(engine=mock_engine, redis_client=mock_redis)

        with patch("services.consolidation_suggestion_service.ConsolidationSuggestionService") as mock_service_cls:
            mock_service = AsyncMock()
            mock_service.suggest_consolidation = AsyncMock(return_value=[])
            mock_service_cls.return_value = mock_service

            result = await tool.execute()

            assert result["total_groups_found"] == 0
            assert result["groups"] == []

    @pytest.mark.asyncio
    async def test_execute_error(self):
        """Test returns error dict on exception."""
        mock_engine = MagicMock()
        mock_redis = AsyncMock()

        tool = SuggestConsolidationTool(engine=mock_engine, redis_client=mock_redis)

        with patch("services.consolidation_suggestion_service.ConsolidationSuggestionService") as mock_service_cls:
            mock_service_cls.side_effect = Exception("DB error")

            result = await tool.execute()

            assert "error" in result
            assert result["groups"] == []
