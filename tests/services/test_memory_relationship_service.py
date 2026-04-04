"""Tests for EPIC-29: Memory Relationship Service."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import uuid

from services.memory_relationship_service import (
    MemoryRelationshipService,
    RelationshipCandidate,
    Relationship,
)


class TestMemoryRelationshipService:
    """Tests for MemoryRelationshipService."""

    def test_compute_tfidf_score_shared_entities(self):
        """Test TF-IDF scoring with shared entities."""
        service = MemoryRelationshipService(engine=MagicMock())

        candidate = RelationshipCandidate(
            id="cand-1",
            entities=[{"name": "Redis"}, {"name": "PostgreSQL"}],
            concepts=["cache layer", "data store"],
            tags=["architecture"],
            auto_tags=["redis", "postgres"],
        )

        rel = service._compute_tfidf_score(
            source_id="src-1",
            source_entities=["redis", "postgresql"],
            source_concepts=["cache layer", "data store"],
            source_tags=["architecture"],
            source_auto_tags=["redis", "postgres"],
            candidate=candidate,
            entity_freq={"redis": 10, "postgresql": 5},
            total_memories=100,
        )

        assert rel is not None
        assert rel.source_id == "src-1"
        assert rel.target_id == "cand-1"
        assert rel.score > 0
        assert "shared_entity" in rel.relationship_types
        assert "shared_concept" in rel.relationship_types
        assert "shared_tag" in rel.relationship_types

    def test_compute_tfidf_score_no_shared(self):
        """Test returns None when no shared entities/concepts/tags."""
        service = MemoryRelationshipService(engine=MagicMock())

        candidate = RelationshipCandidate(
            id="cand-1",
            entities=[{"name": "MongoDB"}],
            concepts=["document store"],
            tags=["nosql"],
            auto_tags=["mongo"],
        )

        rel = service._compute_tfidf_score(
            source_id="src-1",
            source_entities=["redis", "postgresql"],
            source_concepts=["cache layer", "data store"],
            source_tags=["architecture"],
            source_auto_tags=["redis", "postgres"],
            candidate=candidate,
            entity_freq={"redis": 10, "postgresql": 5},
            total_memories=100,
        )

        assert rel is None

    def test_compute_tfidf_score_rare_entity(self):
        """Test that rare entities contribute more to score."""
        service = MemoryRelationshipService(engine=MagicMock())

        # Common entity (high freq = low IDF)
        candidate_common = RelationshipCandidate(
            id="cand-1",
            entities=[{"name": "Redis"}],
            concepts=[],
            tags=[],
            auto_tags=[],
        )

        # Rare entity (low freq = high IDF)
        candidate_rare = RelationshipCandidate(
            id="cand-2",
            entities=[{"name": "ADR-001"}],
            concepts=[],
            tags=[],
            auto_tags=[],
        )

        rel_common = service._compute_tfidf_score(
            source_id="src-1",
            source_entities=["redis"],
            source_concepts=[],
            source_tags=[],
            source_auto_tags=[],
            candidate=candidate_common,
            entity_freq={"redis": 50},  # Common
            total_memories=100,
        )

        rel_rare = service._compute_tfidf_score(
            source_id="src-1",
            source_entities=["adr-001"],
            source_concepts=[],
            source_tags=[],
            source_auto_tags=[],
            candidate=candidate_rare,
            entity_freq={"adr-001": 1},  # Rare
            total_memories=100,
        )

        assert rel_rare.score > rel_common.score

    @pytest.mark.asyncio
    async def test_find_candidates_empty(self):
        """Test returns empty list on DB error."""
        mock_engine = MagicMock()
        mock_engine.begin = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(side_effect=Exception("DB error"))
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_engine.begin.return_value = mock_ctx

        service = MemoryRelationshipService(engine=mock_engine)
        candidates = await service._find_candidates(
            "mem-1", ["redis"], ["cache"], ["architecture"], []
        )

        assert candidates == []

    @pytest.mark.asyncio
    async def test_get_entity_frequencies_error(self):
        """Test returns empty dict on DB error."""
        mock_engine = MagicMock()
        mock_engine.begin = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(side_effect=Exception("DB error"))
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_engine.begin.return_value = mock_ctx

        service = MemoryRelationshipService(engine=mock_engine)
        freq = await service._get_entity_frequencies()

        assert freq == {}

    @pytest.mark.asyncio
    async def test_get_total_memory_count_error(self):
        """Test returns 0 on DB error."""
        mock_engine = MagicMock()
        mock_engine.begin = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(side_effect=Exception("DB error"))
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_engine.begin.return_value = mock_ctx

        service = MemoryRelationshipService(engine=mock_engine)
        count = await service._get_total_memory_count()

        assert count == 0
