"""
MCP Health Resource - Server Health Status

Read-only resource for checking MCP server health and connectivity.
"""

from datetime import datetime
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field
from typing import Optional

from mnemo_mcp.base import BaseMCPComponent
import structlog

logger = structlog.get_logger()


class HealthStatus(BaseModel):
    """Health status response."""
    status: str = Field(description="Overall status (healthy, degraded, unhealthy)")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Health check timestamp"
    )
    database_connected: bool = Field(description="PostgreSQL connection status")
    redis_connected: bool = Field(description="Redis connection status")
    uptime_seconds: float = Field(default=0.0, description="Server uptime in seconds")
    version: str = Field(default="1.0.0", description="MCP server version")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2025-01-15T10:00:00Z",
                "database_connected": True,
                "redis_connected": True,
                "uptime_seconds": 123.4,
                "version": "1.0.0"
            }
        }


class HealthStatusResource(BaseMCPComponent):
    """
    Health status resource.

    URI: health://status
    Returns: HealthStatus with DB, Redis, uptime info

    Usage in Claude Desktop:
        Access the "health://status" resource to check server health
        Expected: {"status": "healthy", "database_connected": true, ...}

    This resource is useful for:
    - Monitoring server health
    - Debugging connectivity issues
    - Verifying service availability
    """

    def __init__(self):
        super().__init__()
        self._start_time = datetime.utcnow()

    def get_name(self) -> str:
        return "health://status"

    async def get(self, ctx: Context) -> HealthStatus:
        """
        Get server health status.

        Args:
            ctx: MCP context

        Returns:
            HealthStatus with connection status and uptime

        Example:
            >>> await health_resource.get(ctx)
            HealthStatus(
                status="healthy",
                database_connected=True,
                redis_connected=True,
                uptime_seconds=123.4
            )
        """
        logger.info("health.check.start")

        # Check database connectivity
        db_connected = False
        if self._services and self._services.get("db"):
            try:
                db_pool = self._services["db"]
                async with db_pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                db_connected = True
                logger.debug("health.db.connected")
            except Exception as e:
                logger.error("health.db.failed", error=str(e))

        # Check Redis connectivity
        redis_connected = False
        if self._services and self._services.get("redis"):
            try:
                redis = self._services["redis"]
                if redis:
                    await redis.ping()
                    redis_connected = True
                    logger.debug("health.redis.connected")
            except Exception as e:
                logger.error("health.redis.failed", error=str(e))

        # Calculate uptime
        uptime = (datetime.utcnow() - self._start_time).total_seconds()

        # Determine overall status
        if db_connected and redis_connected:
            overall_status = "healthy"
        elif db_connected:
            overall_status = "degraded"  # Redis optional
        else:
            overall_status = "unhealthy"

        logger.info(
            "health.check.complete",
            status=overall_status,
            db=db_connected,
            redis=redis_connected,
            uptime=uptime
        )

        return HealthStatus(
            status=overall_status,
            timestamp=datetime.utcnow(),
            database_connected=db_connected,
            redis_connected=redis_connected,
            uptime_seconds=uptime,
            version="1.0.0"
        )


# Singleton instance for registration
health_resource = HealthStatusResource()
