"""Tests for EPIC-30: Consolidation Suggestion Service."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
import uuid

from services.consolidation_suggestion_service import (
    ConsolidationSuggestionService,
    ConsolidationGroup,
)


class TestConsolidationSuggestionService:
    """Tests for ConsolidationSuggestionService."""

    def test_compute_similarity_shared_entities(self):
        """Test TF-IDF similarity with shared entities."""
        mem_a = {
            "entities": [{"name": "Redis"}, {"name": "PostgreSQL"}],
            "concepts": ["cache layer", "data store"],
        }
        mem_b = {
            "entities": [{"name": "Redis"}, {"name": "MongoDB"}],
            "concepts": ["cache layer", "document store"],
        }

        service = ConsolidationSuggestionService(engine=MagicMock())
        score, shared_e, shared_c = service._compute_similarity(
            mem_a, mem_b,
            entity_freq={"redis": 10, "postgresql": 5, "mongodb": 3},
            total_memories=100,
        )

        assert score > 0
        assert "redis" in shared_e
        assert "cache layer" in shared_c

    def test_compute_similarity_no_shared_entities(self):
        """Test returns 0 when no shared entities."""
        mem_a = {"entities": [{"name": "Redis"}], "concepts": ["cache"]}
        mem_b = {"entities": [{"name": "MongoDB"}], "concepts": ["documents"]}

        service = ConsolidationSuggestionService(engine=MagicMock())
        score, shared_e, shared_c = service._compute_similarity(
            mem_a, mem_b,
            entity_freq={"redis": 10},
            total_memories=100,
        )

        assert score == 0.0
        assert shared_e == set()

    def test_compute_similarity_rare_entity_weights_more(self):
        """Test that rare entities contribute more to similarity."""
        mem_common = {
            "entities": [{"name": "Redis"}],
            "concepts": ["cache"],
        }
        mem_rare = {
            "entities": [{"name": "ADR-001"}],
            "concepts": ["architecture"],
        }
        mem_shared_common = {
            "entities": [{"name": "Redis"}],
            "concepts": ["cache"],
        }
        mem_shared_rare = {
            "entities": [{"name": "ADR-001"}],
            "concepts": ["architecture"],
        }

        service = ConsolidationSuggestionService(engine=MagicMock())

        score_common, _, _ = service._compute_similarity(
            mem_common, mem_shared_common,
            entity_freq={"redis": 50},
            total_memories=100,
        )
        score_rare, _, _ = service._compute_similarity(
            mem_rare, mem_shared_rare,
            entity_freq={"adr-001": 1},
            total_memories=100,
        )

        assert score_rare > score_common

    def test_cluster_groups_strict_intersection(self):
        """Test that groups with no shared entities are not merged."""
        pairs = [
            ("a", "b", 0.9, {"redis"}, {"cache"}),
            ("b", "c", 0.9, {"redis"}, {"cache"}),
            ("d", "e", 0.9, {"postgres"}, {"migration"}),
            ("c", "d", 0.8, set(), set()),
        ]

        service = ConsolidationSuggestionService(engine=MagicMock())
        groups = service._cluster_groups(pairs, min_group_size=2)

        assert len(groups) == 2
        group_a = next(g for g in groups if "a" in g["memory_ids"])
        group_d = next(g for g in groups if "d" in g["memory_ids"])
        assert group_a is not group_d

    def test_deduplicate_groups(self):
        """Test that overlapping groups are deduplicated."""
        groups = [
            {"memory_ids": ["a", "b", "c"], "avg_score": 0.8, "shared_entities": {"redis"}, "shared_concepts": {"cache"}},
            {"memory_ids": ["a", "b", "d"], "avg_score": 0.7, "shared_entities": {"redis"}, "shared_concepts": {"cache"}},
            {"memory_ids": ["x", "y", "z"], "avg_score": 0.6, "shared_entities": {"postgres"}, "shared_concepts": {"migration"}},
        ]

        service = ConsolidationSuggestionService(engine=MagicMock())
        result = service._deduplicate_groups(groups, overlap_threshold=0.5)

        assert len(result) == 2
        assert any("x" in g["memory_ids"] for g in result)

    def test_suggest_title_with_entity_and_concept(self):
        """Test title generation with shared entity and concept."""
        group = ConsolidationGroup(
            shared_entities={"redis", "cache"},
            shared_concepts={"cache layer", "ttl"},
        )
        title = ConsolidationSuggestionService.suggest_title(group)
        assert "Redis" in title or "Cache" in title

    def test_suggest_hint(self):
        """Test summary hint generation."""
        group = ConsolidationGroup(
            memory_ids=["1", "2", "3"],
            shared_entities={"redis", "cache"},
            shared_concepts={"cache layer"},
        )
        hint = ConsolidationSuggestionService.suggest_hint(group)
        assert "3 memories" in hint
        assert "redis" in hint.lower() or "cache" in hint.lower()

    @pytest.mark.asyncio
    async def test_fetch_candidate_error(self):
        """Test returns empty list on DB error."""
        mock_engine = MagicMock()
        mock_engine.begin = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(side_effect=Exception("DB error"))
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_engine.begin.return_value = mock_ctx

        service = ConsolidationSuggestionService(engine=mock_engine)
        memories = await service._fetch_candidate_memories(["note"], ["sys:history"], 30)

        assert memories == []

    @pytest.mark.asyncio
    async def test_get_entity_frequencies_cache_hit(self):
        """Test returns cached frequencies."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value='{"redis": 10}')

        service = ConsolidationSuggestionService(engine=MagicMock(), redis_client=mock_redis)
        freq = await service._get_entity_frequencies()

        assert freq == {"redis": 10}
        mock_redis.get.assert_called_once_with("entity_freq")

    @pytest.mark.asyncio
    async def test_get_entity_frequencies_cache_miss(self):
        """Test computes and caches frequencies on miss."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()

        mock_engine = MagicMock()
        mock_engine.begin = MagicMock()
        mock_ctx = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("redis", 10), ("postgres", 5)]
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([("redis", 10), ("postgres", 5)]))
        mock_ctx.execute = AsyncMock(return_value=mock_result)
        mock_engine.begin.return_value = mock_ctx

        service = ConsolidationSuggestionService(engine=mock_engine, redis_client=mock_redis)
        freq = await service._get_entity_frequencies()

        assert freq == {"redis": 10, "postgres": 5}
        mock_redis.setex.assert_called_once()
