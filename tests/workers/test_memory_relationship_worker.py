"""Tests for EPIC-29: Memory Relationship Worker Integration."""

import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from workers.conversation_worker import ConversationWorker


class TestMemoryRelationshipWorker:
    """Tests for memory relationship processing in the worker."""

    @pytest.mark.asyncio
    async def test_handle_relationship_message_success(self):
        """Test successful relationship computation."""
        mock_redis = MagicMock()

        worker = ConversationWorker(
            redis_client=mock_redis,
            api_url="http://api:8000",
        )
        worker._http_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        worker._http_client.post = AsyncMock(return_value=mock_response)

        await worker._handle_relationship_message(
            b"12345-0",
            {b"payload": json.dumps({
                "memory_id": "test-id",
                "entities": ["redis", "postgresql"],
                "concepts": ["cache layer"],
                "tags": ["architecture"],
                "auto_tags": ["redis", "postgres"],
            }).encode()},
            "memory:relationships"
        )

        worker._http_client.post.assert_called_once()
        mock_redis.xack.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_relationship_message_api_error(self):
        """Test API error doesn't ack the message."""
        mock_redis = MagicMock()

        worker = ConversationWorker(
            redis_client=mock_redis,
            api_url="http://api:8000",
        )
        worker._http_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 500
        worker._http_client.post = AsyncMock(return_value=mock_response)

        await worker._handle_relationship_message(
            b"12345-0",
            {b"payload": json.dumps({
                "memory_id": "test-id",
                "entities": ["redis"],
                "concepts": [],
                "tags": [],
                "auto_tags": [],
            }).encode()},
            "memory:relationships"
        )

        mock_redis.xack.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_relationship_message_invalid_json(self):
        """Test invalid JSON is acked (discarded)."""
        mock_redis = MagicMock()

        worker = ConversationWorker(
            redis_client=mock_redis,
            api_url="http://api:8000",
        )
        worker._http_client = AsyncMock()

        await worker._handle_relationship_message(
            b"12345-0",
            {b"payload": b"not valid json"},
            "memory:relationships"
        )

        mock_redis.xack.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_relationship_message_no_memory_id(self):
        """Test missing memory_id is acked (discarded)."""
        mock_redis = MagicMock()

        worker = ConversationWorker(
            redis_client=mock_redis,
            api_url="http://api:8000",
        )
        worker._http_client = AsyncMock()

        await worker._handle_relationship_message(
            b"12345-0",
            {b"payload": json.dumps({"entities": ["redis"]}).encode()},
            "memory:relationships"
        )

        mock_redis.xack.assert_called_once()
