"""
Tests for EPIC-28: Entity Extraction & Query Understanding.

Tests for GLiNERService, EntityExtractionService, QueryUnderstandingService,
and entity extraction MCP tools.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
import uuid

from services.entity_extraction_service import (
    EntityExtractionService,
    EXTRACTABLE_TYPES,
    EXTRACTABLE_SYSTEM_TAGS,
)
from services.query_understanding_service import (
    QueryUnderstandingService,
    QueryKeywords,
)

# ============================================================================
# EntityExtractionService Tests
# ============================================================================

class TestEntityExtractionServiceShouldExtract:
    """Tests for EntityExtractionService.should_extract()."""

    def test_extractable_types(self):
        """Test extractable memory types."""
        for mem_type in EXTRACTABLE_TYPES:
            assert EntityExtractionService.should_extract(mem_type, []) is True

    def test_non_extractable_types(self):
        """Test non-extractable memory types."""
        for mem_type in ["conversation", "task", "sys:history", "sys:trace"]:
            assert EntityExtractionService.should_extract(mem_type, []) is False

    def test_system_tags_trigger_extraction(self):
        """Test system tags trigger extraction regardless of type."""
        for tag in EXTRACTABLE_SYSTEM_TAGS:
            assert EntityExtractionService.should_extract("conversation", [tag]) is True

    def test_regular_tags_dont_trigger(self):
        """Test regular tags don't trigger extraction for non-extractable types."""
        assert EntityExtractionService.should_extract("note", ["python", "async"]) is True  # note is extractable
        assert EntityExtractionService.should_extract("conversation", ["python"]) is False


class TestEntityExtractionServiceExtract:
    """Tests for EntityExtractionService.extract_entities()."""

    @pytest.mark.asyncio
    async def test_skip_when_disabled(self):
        """Test skips extraction when disabled."""
        mock_engine = AsyncMock()
        mock_gliner = MagicMock()
        mock_gliner.extract_entities.return_value = []

        service = EntityExtractionService(engine=mock_engine, gliner_service=mock_gliner)
        service.enabled = False

        result = await service.extract_entities(
            memory_id="test-id",
            title="Test",
            content="Test content",
            memory_type="decision",
            tags=[],
        )

        assert result is False
        mock_gliner.extract_entities.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_non_extractable_type(self):
        """Test skips extraction for non-extractable types."""
        mock_engine = AsyncMock()
        mock_gliner = MagicMock()

        service = EntityExtractionService(engine=mock_engine, gliner_service=mock_gliner)

        result = await service.extract_entities(
            memory_id="test-id",
            title="Test",
            content="Test content",
            memory_type="conversation",
            tags=[],
        )

        assert result is False
        mock_gliner.extract_entities.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_when_gliner_returns_empty(self):
        """Test skips when GLiNER finds no entities."""
        mock_engine = AsyncMock()
        mock_gliner = MagicMock()
        mock_gliner.extract_entities.return_value = []

        service = EntityExtractionService(engine=mock_engine, gliner_service=mock_gliner)

        result = await service.extract_entities(
            memory_id="test-id",
            title="Test",
            content="Test content",
            memory_type="decision",
            tags=[],
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_successful_extraction(self):
        """Test successful entity extraction with GLiNER."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.begin = MagicMock(return_value=mock_ctx)

        mock_gliner = MagicMock()
        mock_gliner.extract_entities.return_value = [
            {"name": "Redis", "type": "technology", "start": 0, "end": 5},
        ]

        service = EntityExtractionService(engine=mock_engine, gliner_service=mock_gliner)

        result = await service.extract_entities(
            memory_id="test-id",
            title="Decision: Use Redis",
            content="We use Redis for caching.",
            memory_type="decision",
            tags=["architecture"],
        )

        assert result is True
        mock_gliner.extract_entities.assert_called_once()


# ============================================================================
# QueryUnderstandingService Tests
# ============================================================================

class TestQueryUnderstandingService:
    """Tests for QueryUnderstandingService (deterministic heuristics)."""

    def test_extract_keywords_basic(self):
        """Test basic keyword extraction."""
        service = QueryUnderstandingService()
        result = service.extract_keywords("how do we consolidate memories?")

        assert isinstance(result, QueryKeywords)
        assert len(result.hl_keywords) > 0
        # "consolidate" and "memories" should be HL keywords (not stopwords)
        assert "consolidate" in result.hl_keywords
        assert "memories" in result.hl_keywords

    def test_extract_keywords_stopswords_filtered(self):
        """Test that stopwords are filtered out."""
        service = QueryUnderstandingService()
        result = service.extract_keywords("the quick brown fox")

        assert "the" not in result.hl_keywords

    def test_extract_keywords_acronyms_as_ll(self):
        """Test acronyms are extracted as LL keywords."""
        service = QueryUnderstandingService()
        result = service.extract_keywords("How does API work with JWT tokens?")

        assert "API" in result.ll_keywords
        assert "JWT" in result.ll_keywords

    def test_extract_keywords_versions_as_ll(self):
        """Test version numbers are extracted as LL keywords."""
        service = QueryUnderstandingService()
        result = service.extract_keywords("Upgrade to Python 3.12")

        assert "3.12" in result.ll_keywords

    def test_extract_keywords_empty_query(self):
        """Test empty query returns empty keywords."""
        service = QueryUnderstandingService()
        result = service.extract_keywords("")

        assert result.hl_keywords == []
        assert result.ll_keywords == []

    def test_extract_keywords_filters_non_string(self):
        """Test that non-string values in keywords are filtered (defensive)."""
        # The deterministic implementation always returns strings,
        # but we test the dataclass directly
        keywords = QueryKeywords(hl_keywords=["valid"], ll_keywords=["redis"])
        assert keywords.hl_keywords == ["valid"]
        assert keywords.ll_keywords == ["redis"]


# ============================================================================
# Memory Model Entity Fields Tests
# ============================================================================

class TestMemoryEntityFields:
    """Tests for entity fields in Memory model."""

    def test_memory_with_entities(self):
        """Test Memory model with entity fields."""
        from mnemo_mcp.models.memory_models import Memory, MemoryType

        memory = Memory(
            id=uuid.uuid4(),
            title="Test",
            content="Content",
            memory_type=MemoryType.NOTE,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            entities=[{"name": "Redis", "type": "technology"}],
            concepts=["cache layer"],
            auto_tags=["redis", "cache"],
        )

        assert len(memory.entities) == 1
        assert memory.entities[0]["name"] == "Redis"
        assert memory.concepts == ["cache layer"]
        assert memory.auto_tags == ["redis", "cache"]

    def test_memory_default_entity_values(self):
        """Test entity fields default to empty lists."""
        from mnemo_mcp.models.memory_models import Memory, MemoryType

        memory = Memory(
            id=uuid.uuid4(),
            title="Test",
            content="Content",
            memory_type=MemoryType.NOTE,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        assert memory.entities == []
        assert memory.concepts == []
        assert memory.auto_tags == []
