"""
Tests for EPIC-28: Entity Extraction & Query Understanding.

Tests for LMStudioClient, EntityExtractionService, QueryUnderstandingService,
and entity extraction MCP tools.
"""

import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import uuid

from services.lm_studio_client import LMStudioClient
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
# LMStudioClient Tests
# ============================================================================

class TestLMStudioClientInit:
    """Tests for LMStudioClient initialization."""

    def test_default_values(self):
        """Test default configuration."""
        client = LMStudioClient()
        assert client.base_url == "http://host.docker.internal:1234/v1"
        assert client.model == "qwen2.5-7b-instruct"
        assert client.timeout == 30.0
        assert client._client is None
        assert client._available is None

    def test_custom_values(self):
        """Test custom configuration."""
        client = LMStudioClient(
            base_url="http://custom:1234/v1",
            model="custom-model",
            timeout=60.0,
        )
        assert client.base_url == "http://custom:1234/v1"
        assert client.model == "custom-model"
        assert client.timeout == 60.0

    def test_env_var_overrides(self, monkeypatch):
        """Test environment variable overrides."""
        monkeypatch.setenv("LM_STUDIO_URL", "http://env:1234/v1")
        monkeypatch.setenv("LM_STUDIO_MODEL", "env-model")
        client = LMStudioClient()
        assert client.base_url == "http://env:1234/v1"
        assert client.model == "env-model"

    def test_base_url_trailing_slash_stripped(self):
        """Test trailing slash is stripped from base URL."""
        client = LMStudioClient(base_url="http://test:1234/v1/")
        assert client.base_url == "http://test:1234/v1"


class TestLMStudioClientIsAvailable:
    """Tests for LMStudioClient.is_available()."""

    @pytest.mark.asyncio
    async def test_available_returns_true(self):
        """Test returns True when models are loaded."""
        client = LMStudioClient()
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": "qwen2.5-7b-instruct"}]}
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(client, "_get_client", return_value=mock_client):
            result = await client.is_available()

        assert result is True
        assert client._available is True

    @pytest.mark.asyncio
    async def test_available_returns_false_no_models(self):
        """Test returns False when no models loaded."""
        client = LMStudioClient()
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(client, "_get_client", return_value=mock_client):
            result = await client.is_available()

        assert result is False

    @pytest.mark.asyncio
    async def test_available_returns_false_on_error(self):
        """Test returns False on connection error."""
        client = LMStudioClient()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=ConnectionError("refused"))

        with patch.object(client, "_get_client", return_value=mock_client):
            result = await client.is_available()

        assert result is False

    @pytest.mark.asyncio
    async def test_available_caches_result(self):
        """Test result is cached after first call."""
        client = LMStudioClient()
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": "model"}]}
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(client, "_get_client", return_value=mock_client):
            await client.is_available()
            await client.is_available()
            await client.is_available()

        # Should only call get once (cached)
        assert mock_client.get.call_count == 1


class TestLMStudioClientExtractJson:
    """Tests for LMStudioClient.extract_json()."""

    @pytest.mark.asyncio
    async def test_extract_json_success(self):
        """Test successful JSON extraction."""
        client = LMStudioClient()
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"key": "value"}'}}]
        }
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(client, "_get_client", return_value=mock_client):
            result = await client.extract_json(
                system_prompt="test",
                user_content="test",
                json_schema={"type": "object"},
            )

        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_extract_json_returns_none_on_error(self):
        """Test returns None on HTTP error."""
        client = LMStudioClient()
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(client, "_get_client", return_value=mock_client):
            result = await client.extract_json(
                system_prompt="test",
                user_content="test",
                json_schema={"type": "object"},
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_extract_json_handles_malformed_json(self):
        """Test handles malformed JSON gracefully."""
        client = LMStudioClient()
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "not json at all"}}]
        }
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(client, "_get_client", return_value=mock_client):
            result = await client.extract_json(
                system_prompt="test",
                user_content="test",
                json_schema={"type": "object"},
            )

        # json_repair might return something or None depending on content
        # The important thing is it doesn't crash
        assert result is None or isinstance(result, dict)


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
        """Test regular tags don't trigger extraction."""
        assert EntityExtractionService.should_extract("note", ["python", "async"]) is True  # note is extractable
        assert EntityExtractionService.should_extract("conversation", ["python"]) is False


class TestEntityExtractionServiceExtract:
    """Tests for EntityExtractionService.extract_entities()."""

    @pytest.mark.asyncio
    async def test_skip_when_disabled(self):
        """Test skips extraction when disabled."""
        mock_engine = AsyncMock()
        mock_lm_client = AsyncMock()
        mock_lm_client.is_available = AsyncMock(return_value=True)

        service = EntityExtractionService(engine=mock_engine, lm_client=mock_lm_client)
        service.enabled = False

        result = await service.extract_entities(
            memory_id="test-id",
            title="Test",
            content="Test content",
            memory_type="decision",
            tags=[],
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_skip_when_lm_unavailable(self):
        """Test skips extraction when LM Studio unavailable."""
        mock_engine = AsyncMock()
        mock_lm_client = AsyncMock()
        mock_lm_client.is_available = AsyncMock(return_value=False)

        service = EntityExtractionService(engine=mock_engine, lm_client=mock_lm_client)

        result = await service.extract_entities(
            memory_id="test-id",
            title="Test",
            content="Test content",
            memory_type="decision",
            tags=[],
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_skip_non_extractable_type(self):
        """Test skips extraction for non-extractable types."""
        mock_engine = AsyncMock()
        mock_lm_client = AsyncMock()
        mock_lm_client.is_available = AsyncMock(return_value=True)

        service = EntityExtractionService(engine=mock_engine, lm_client=mock_lm_client)

        result = await service.extract_entities(
            memory_id="test-id",
            title="Test",
            content="Test content",
            memory_type="conversation",
            tags=[],
        )

        assert result is False
        mock_lm_client.extract_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_successful_extraction(self):
        """Test successful entity extraction."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.begin = MagicMock(return_value=mock_ctx)

        mock_lm_client = AsyncMock()
        mock_lm_client.is_available = AsyncMock(return_value=True)
        mock_lm_client.extract_json = AsyncMock(return_value={
            "entities": [{"name": "Redis", "type": "technology"}],
            "concepts": ["cache layer"],
            "tags": ["redis", "cache"],
        })

        service = EntityExtractionService(engine=mock_engine, lm_client=mock_lm_client)

        result = await service.extract_entities(
            memory_id="test-id",
            title="Decision: Use Redis",
            content="We use Redis for caching.",
            memory_type="decision",
            tags=["architecture"],
        )

        assert result is True
        mock_lm_client.extract_json.assert_called_once()


# ============================================================================
# QueryUnderstandingService Tests
# ============================================================================

class TestQueryUnderstandingService:
    """Tests for QueryUnderstandingService."""

    @pytest.mark.asyncio
    async def test_skip_when_disabled(self):
        """Test returns empty keywords when disabled."""
        mock_lm_client = AsyncMock()
        mock_lm_client.is_available = AsyncMock(return_value=True)

        service = QueryUnderstandingService(lm_client=mock_lm_client)
        service.enabled = False

        result = await service.extract_keywords("test query")

        assert result.hl_keywords == []
        assert result.ll_keywords == []

    @pytest.mark.asyncio
    async def test_skip_when_lm_unavailable(self):
        """Test returns empty keywords when LM Studio unavailable."""
        mock_lm_client = AsyncMock()
        mock_lm_client.is_available = AsyncMock(return_value=False)

        service = QueryUnderstandingService(lm_client=mock_lm_client)

        result = await service.extract_keywords("test query")

        assert result.hl_keywords == []
        assert result.ll_keywords == []

    @pytest.mark.asyncio
    async def test_successful_extraction(self):
        """Test successful keyword extraction."""
        mock_lm_client = AsyncMock()
        mock_lm_client.is_available = AsyncMock(return_value=True)
        mock_lm_client.extract_json = AsyncMock(return_value={
            "hl_keywords": ["memory consolidation", "lifecycle"],
            "ll_keywords": ["sys:history", "consolidate_memory"],
        })

        service = QueryUnderstandingService(lm_client=mock_lm_client)

        result = await service.extract_keywords("how do we consolidate memories?")

        assert result.hl_keywords == ["memory consolidation", "lifecycle"]
        assert result.ll_keywords == ["sys:history", "consolidate_memory"]

    @pytest.mark.asyncio
    async def test_filters_non_string_keywords(self):
        """Test filters out non-string keywords."""
        mock_lm_client = AsyncMock()
        mock_lm_client.is_available = AsyncMock(return_value=True)
        mock_lm_client.extract_json = AsyncMock(return_value={
            "hl_keywords": ["valid", 123, None, ""],
            "ll_keywords": ["redis", {"nested": "dict"}],
        })

        service = QueryUnderstandingService(lm_client=mock_lm_client)

        result = await service.extract_keywords("test")

        assert result.hl_keywords == ["valid"]
        assert result.ll_keywords == ["redis"]


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
