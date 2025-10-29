"""
Tests for MCP test tool (ping).
"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime

from mnemo_mcp.tools.test_tool import PingTool, PingResponse


class TestPingTool:
    """Tests for ping tool."""

    def test_get_name(self):
        """Test tool name."""
        tool = PingTool()
        assert tool.get_name() == "ping"

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test ping returns pong."""
        tool = PingTool()

        # Mock context
        ctx = MagicMock()

        # Execute
        response = await tool.execute(ctx)

        # Verify
        assert isinstance(response, PingResponse)
        assert response.success is True
        assert response.message == "pong"
        assert isinstance(response.timestamp, datetime)
        assert response.latency_ms >= 0.0
        assert "server_name" in response.metadata
        assert response.metadata["server_name"] == "mnemolite"
        assert response.metadata["mcp_spec"] == "2025-06-18"

    @pytest.mark.asyncio
    async def test_ping_response_serialization(self):
        """Test PingResponse can be serialized to dict."""
        tool = PingTool()
        ctx = MagicMock()

        response = await tool.execute(ctx)
        response_dict = response.model_dump()

        assert isinstance(response_dict, dict)
        assert response_dict["success"] is True
        assert response_dict["message"] == "pong"
        assert "timestamp" in response_dict
