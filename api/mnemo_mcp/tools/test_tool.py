"""
MCP Test Tool - Ping

Simple ping/pong tool for testing MCP server connectivity.
"""

from datetime import datetime
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from mnemo_mcp.base import BaseMCPComponent, MCPBaseResponse
import structlog

logger = structlog.get_logger()


class PingResponse(MCPBaseResponse):
    """Response from ping tool."""
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Server timestamp"
    )
    message: str = Field(
        default="pong",
        description="Response message"
    )
    latency_ms: float = Field(
        default=0.0,
        description="Simulated latency in milliseconds"
    )


class PingTool(BaseMCPComponent):
    """
    Ping tool for testing MCP server connectivity.

    Usage:
        In Claude Desktop: Use the "ping" tool with no arguments
        Expected response: {"success": true, "message": "pong", "timestamp": "..."}

    This tool is useful for:
    - Verifying MCP server is running
    - Testing tool registration
    - Debugging connection issues
    """

    def get_name(self) -> str:
        return "ping"

    async def execute(self, ctx: Context) -> PingResponse:
        """
        Execute ping tool - return pong.

        Args:
            ctx: MCP context (contains session, progress reporting, etc.)

        Returns:
            PingResponse with timestamp and message

        Example:
            >>> await ping_tool.execute(ctx)
            PingResponse(success=True, message="pong", timestamp="2025-01-15T10:00:00Z")
        """
        logger.info("ping.execute")

        return PingResponse(
            success=True,
            message="pong",
            timestamp=datetime.utcnow(),
            latency_ms=0.1,  # Simulated latency
            metadata={
                "server_name": "mnemolite",
                "mcp_spec": "2025-06-18"
            }
        )


# Singleton instance for registration
ping_tool = PingTool()
