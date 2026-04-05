"""
Tests for EPIC-32: Entity Extraction Worker with GLiNER.

Tests the Redis Stream → Worker → GLiNER → DB flow.
"""

import sys
import pytest
import json
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone
import uuid

# Pre-import modules so patches work with lazy imports in worker
import gliner
import sqlalchemy

from workers.conversation_worker import ConversationWorker


# ============================================================================
# Worker Entity Extraction Tests (GLiNER-based)
# ============================================================================

class TestWorkerEntityExtraction:
    """Tests for entity extraction in the conversation worker using GLiNER."""

    @pytest.mark.asyncio
    async def test_handle_entity_extraction_success(self):
        """Test successful entity extraction message handling with GLiNER."""
        mock_redis = MagicMock()

        worker = ConversationWorker(
            redis_client=mock_redis,
            api_url="http://api:8000",
        )

        with patch.object(worker, '_process_entity_extraction', return_value=True):
            await worker._handle_entity_extraction_message(
                b"12345-0",
                {b"payload": json.dumps({
                    "memory_id": "test-id",
                    "title": "Test Memory",
                    "content": "Test content",
                    "memory_type": "decision",
                    "tags": ["test"],
                }).encode()},
                "entity:extraction"
            )

        # Verify message was acknowledged
        mock_redis.xack.assert_called_once_with(
            "entity:extraction", "workers", "12345-0"
        )

    @pytest.mark.asyncio
    async def test_handle_entity_extraction_failure_no_ack(self):
        """Test that failed extraction doesn't ack the message."""
        mock_redis = MagicMock()

        worker = ConversationWorker(
            redis_client=mock_redis,
            api_url="http://api:8000",
        )

        with patch.object(worker, '_process_entity_extraction', return_value=False):
            await worker._handle_entity_extraction_message(
                b"12345-0",
                {b"payload": json.dumps({
                    "memory_id": "test-id",
                    "title": "Test",
                    "content": "Test",
                    "memory_type": "decision",
                    "tags": [],
                }).encode()},
                "entity:extraction"
            )

        # Message should NOT be acked (extraction failed)
        mock_redis.xack.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_entity_extraction_invalid_json(self):
        """Test handling of invalid JSON payload."""
        mock_redis = MagicMock()

        worker = ConversationWorker(
            redis_client=mock_redis,
            api_url="http://api:8000",
        )

        # Should not raise, should ack the message (discard invalid)
        await worker._handle_entity_extraction_message(
            b"12345-0",
            {b"payload": b"not valid json"},
            "entity:extraction"
        )

        # Message should be acked (invalid payloads are discarded)
        mock_redis.xack.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_entity_extraction_success(self):
        """Test successful entity extraction via GLiNER."""
        # Create mock model
        mock_model = MagicMock()
        mock_model.predict_entities.return_value = [
            {"text": "Redis", "label": "technology", "start": 0, "end": 5},
            {"text": "FastAPI", "label": "technology", "start": 10, "end": 17},
        ]

        # Create mock GLiNER class
        mock_gliner_class = MagicMock()
        mock_gliner_class.from_pretrained.return_value = mock_model

        # Mock DB engine with proper context manager
        mock_conn = MagicMock()
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_conn)
        mock_cm.__exit__ = MagicMock(return_value=False)
        mock_engine = MagicMock()
        mock_engine.begin.return_value = mock_cm

        worker = ConversationWorker(
            redis_client=MagicMock(),
            api_url="http://api:8000",
        )

        # Patch both gliner.GLiNER and sqlalchemy.create_engine at source
        with patch("gliner.GLiNER", mock_gliner_class):
            with patch("sqlalchemy.create_engine", return_value=mock_engine):
                result = await worker._process_entity_extraction({
                    "memory_id": "test-id",
                    "title": "Test",
                    "content": "We use Redis and FastAPI",
                    "memory_type": "decision",
                    "tags": ["test"],
                })

        assert result is True
        mock_gliner_class.from_pretrained.assert_called_once()
        mock_model.predict_entities.assert_called_once()
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_entity_extraction_gliner_error(self):
        """Test entity extraction when GLiNER fails."""
        mock_gliner_class = MagicMock()
        mock_gliner_class.from_pretrained.side_effect = Exception("Model load failed")

        worker = ConversationWorker(
            redis_client=MagicMock(),
            api_url="http://api:8000",
        )

        with patch("gliner.GLiNER", mock_gliner_class):
            result = await worker._process_entity_extraction({
                "memory_id": "test-id",
                "title": "Test",
                "content": "Test content",
                "memory_type": "decision",
                "tags": [],
            })

        assert result is False

    @pytest.mark.asyncio
    async def test_process_entity_extraction_db_error(self):
        """Test entity extraction when DB save fails."""
        mock_model = MagicMock()
        mock_model.predict_entities.return_value = [
            {"text": "Redis", "label": "technology", "start": 0, "end": 5},
        ]
        mock_gliner_class = MagicMock()
        mock_gliner_class.from_pretrained.return_value = mock_model

        worker = ConversationWorker(
            redis_client=MagicMock(),
            api_url="http://api:8000",
        )

        with patch("gliner.GLiNER", mock_gliner_class):
            with patch("sqlalchemy.create_engine", side_effect=Exception("DB connection failed")):
                result = await worker._process_entity_extraction({
                    "memory_id": "test-id",
                    "title": "Test",
                    "content": "We use Redis",
                    "memory_type": "decision",
                    "tags": [],
                })

        assert result is False

    @pytest.mark.asyncio
    async def test_process_entity_extraction_deduplication(self):
        """Test that duplicate entities are deduplicated."""
        mock_model = MagicMock()
        mock_model.predict_entities.return_value = [
            {"text": "Redis", "label": "technology", "start": 0, "end": 5},
            {"text": "redis", "label": "technology", "start": 20, "end": 25},
            {"text": "Redis", "label": "tech", "start": 40, "end": 45},
        ]
        mock_gliner_class = MagicMock()
        mock_gliner_class.from_pretrained.return_value = mock_model

        mock_conn = MagicMock()
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_conn)
        mock_cm.__exit__ = MagicMock(return_value=False)
        mock_engine = MagicMock()
        mock_engine.begin.return_value = mock_cm

        worker = ConversationWorker(
            redis_client=MagicMock(),
            api_url="http://api:8000",
        )

        with patch("gliner.GLiNER", mock_gliner_class):
            with patch("sqlalchemy.create_engine", return_value=mock_engine):
                result = await worker._process_entity_extraction({
                    "memory_id": "test-id",
                    "title": "Test",
                    "content": "Redis is great. redis is fast. Redis is cool.",
                    "memory_type": "decision",
                    "tags": [],
                })

        assert result is True
        # Verify only one entity was saved (deduplicated)
        call_args = mock_conn.execute.call_args
        params = call_args[0][1]
        entities = json.loads(params["entities"])
        assert len(entities) == 1
        assert entities[0]["name"] == "Redis"
