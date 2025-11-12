"""
Tests for conversation worker.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from workers.conversation_worker import ConversationWorker, ConversationMessage


@pytest.mark.asyncio
async def test_process_message_success():
    """Worker should call API and return success."""
    # Setup
    worker = ConversationWorker(redis_client=MagicMock(), api_url="http://test:8001")
    message = ConversationMessage(
        id="1234-0",
        user_message="Test user",
        assistant_message="Test assistant",
        project_name="test-project",
        session_id="test-session",
        timestamp="2025-01-12T10:00:00Z"
    )

    # Mock API response
    worker._http_client = AsyncMock()
    worker._http_client.post = AsyncMock(return_value=MagicMock(
        status_code=200,
        json=lambda: {"success": True, "memory_id": "abc-123"}
    ))

    # Execute
    result = await worker.process_message(message)

    # Assert
    assert result is True
    worker._http_client.post.assert_called_once()
    call_args = worker._http_client.post.call_args
    assert call_args[0][0] == "http://test:8001/v1/conversations/save"
    assert call_args[1]["json"]["user_message"] == "Test user"


@pytest.mark.asyncio
async def test_process_message_retry_on_failure():
    """Worker should retry on API failure."""
    worker = ConversationWorker(redis_client=MagicMock(), api_url="http://test:8001")
    message = ConversationMessage(
        id="1234-0",
        user_message="Test",
        assistant_message="Response",
        project_name="test",
        session_id="sess",
        timestamp="2025-01-12T10:00:00Z"
    )

    # Mock API to fail twice, then succeed
    worker._http_client = AsyncMock()
    worker._http_client.post = AsyncMock(side_effect=[
        MagicMock(status_code=500),  # Fail
        MagicMock(status_code=502),  # Fail
        MagicMock(status_code=200, json=lambda: {"success": True})  # Success
    ])

    # Execute with retries
    result = await worker.process_message(message, max_retries=3)

    # Assert
    assert result is True
    assert worker._http_client.post.call_count == 3
