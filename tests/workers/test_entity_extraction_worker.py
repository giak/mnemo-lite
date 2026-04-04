"""
Tests for EPIC-28: Entity Extraction Worker Integration.

Tests the Redis Stream → Worker → API endpoint flow.
"""

import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import uuid

from workers.conversation_worker import ConversationWorker


# ============================================================================
# Worker Entity Extraction Tests
# ============================================================================

class TestWorkerEntityExtraction:
    """Tests for entity extraction in the conversation worker."""

    @pytest.mark.asyncio
    async def test_handle_entity_extraction_success(self):
        """Test successful entity extraction message handling."""
        mock_redis = MagicMock()

        worker = ConversationWorker(
            redis_client=mock_redis,
            api_url="http://api:8000",
        )
        worker._http_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        worker._http_client.post = AsyncMock(return_value=mock_response)

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

        # Verify API was called
        worker._http_client.post.assert_called_once()
        call_url = worker._http_client.post.call_args[0][0]
        assert "extract-entities" in call_url
        assert "test-id" in call_url

        # Verify message was acknowledged
        mock_redis.xack.assert_called_once_with(
            "entity:extraction", "workers", "12345-0"
        )

    @pytest.mark.asyncio
    async def test_handle_entity_extraction_api_error(self):
        """Test API 5xx errors don't ack the message."""
        mock_redis = MagicMock()

        worker = ConversationWorker(
            redis_client=mock_redis,
            api_url="http://api:8000",
        )
        worker._http_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 500
        worker._http_client.post = AsyncMock(return_value=mock_response)

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
        worker._http_client = AsyncMock()

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
        """Test successful entity extraction via API."""
        worker = ConversationWorker(
            redis_client=MagicMock(),
            api_url="http://api:8000",
        )
        worker._http_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        worker._http_client.post = AsyncMock(return_value=mock_response)

        result = await worker._process_entity_extraction({
            "memory_id": "test-id",
            "title": "Test",
            "content": "Test content",
            "memory_type": "decision",
            "tags": ["test"],
        })

        assert result is True
        worker._http_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_entity_extraction_404(self):
        """Test entity extraction with 404 response."""
        worker = ConversationWorker(
            redis_client=MagicMock(),
            api_url="http://api:8000",
        )
        worker._http_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 404
        worker._http_client.post = AsyncMock(return_value=mock_response)

        result = await worker._process_entity_extraction({
            "memory_id": "nonexistent",
            "title": "Test",
            "content": "Test",
            "memory_type": "decision",
            "tags": [],
        })

        assert result is False

    @pytest.mark.asyncio
    async def test_process_entity_extraction_api_url(self):
        """Test that the correct API URL is used."""
        worker = ConversationWorker(
            redis_client=MagicMock(),
            api_url="http://api:8000",
        )
        worker._http_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        worker._http_client.post = AsyncMock(return_value=mock_response)

        await worker._process_entity_extraction({
            "memory_id": "test-id",
            "title": "Test",
            "content": "Test",
            "memory_type": "decision",
            "tags": [],
        })

        call_url = worker._http_client.post.call_args[0][0]
        assert "http://api:8000" in call_url
        assert "test-id" in call_url
        assert "extract-entities" in call_url

    @pytest.mark.asyncio
    async def test_process_entity_extraction_request_error(self):
        """Test that network errors are raised for retry."""
        import httpx

        worker = ConversationWorker(
            redis_client=MagicMock(),
            api_url="http://api:8000",
        )
        worker._http_client = AsyncMock()
        worker._http_client.post = AsyncMock(
            side_effect=httpx.RequestError("Connection refused")
        )

        with pytest.raises(httpx.RequestError):
            await worker._process_entity_extraction({
                "memory_id": "test-id",
                "title": "Test",
                "content": "Test",
                "memory_type": "decision",
                "tags": [],
            })
