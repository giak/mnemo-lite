"""
LSP Management Routes - Health check and manual restart.

Story: EPIC-13 Story 13.3 - LSP Lifecycle Management
Author: Claude Code
Date: 2025-10-22

Provides endpoints for monitoring and managing LSP server lifecycle.
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/lsp", tags=["lsp"])


# ============================================================================
# Response Models
# ============================================================================


class LSPHealthResponse(BaseModel):
    """LSP server health status."""

    status: str = Field(..., description="Health status (healthy, crashed, not_started, starting)")
    running: bool = Field(..., description="Process is running")
    initialized: bool = Field(..., description="LSP server is initialized")
    restart_count: int = Field(..., description="Number of restarts")
    pid: int | None = Field(None, description="Process ID (if running)")
    returncode: int | None = Field(None, description="Process return code (if crashed)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "healthy",
                "running": True,
                "initialized": True,
                "restart_count": 0,
                "pid": 1234,
                "returncode": None
            }
        }
    }


class LSPRestartResponse(BaseModel):
    """LSP server restart response."""

    status: str = Field(..., description="Restart status")
    message: str = Field(..., description="Human-readable message")
    health: LSPHealthResponse = Field(..., description="Health status after restart")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "restarted",
                "message": "LSP server restarted successfully",
                "health": {
                    "status": "healthy",
                    "running": True,
                    "initialized": True,
                    "restart_count": 1,
                    "pid": 5678,
                    "returncode": None
                }
            }
        }
    }


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "/health",
    response_model=LSPHealthResponse,
    summary="LSP server health check",
    description="""
    Check the health status of the Pyright LSP server.

    **Status values**:
    - `healthy`: Server running and initialized
    - `starting`: Server running but not yet initialized
    - `crashed`: Server process terminated with error
    - `not_started`: Server has not been started yet

    **Use cases**:
    - Monitoring: Check server availability before indexing operations
    - Debugging: Diagnose LSP server issues
    - Automation: Auto-restart on crash detection

    **Story 13.3**: LSP Lifecycle Management
    """,
)
async def lsp_health_check():
    """
    Get LSP server health status.

    Returns:
        LSPHealthResponse: Server health and status information
    """
    try:
        # Import here to avoid circular dependency
        from dependencies import get_lsp_lifecycle_manager

        lsp_manager = get_lsp_lifecycle_manager()

        if not lsp_manager:
            return LSPHealthResponse(
                status="not_started",
                running=False,
                initialized=False,
                restart_count=0,
                pid=None
            )

        health = await lsp_manager.health_check()

        return LSPHealthResponse(**health)

    except Exception as e:
        logger.error(f"LSP health check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}",
        )


@router.post(
    "/restart",
    response_model=LSPRestartResponse,
    status_code=status.HTTP_200_OK,
    summary="Manually restart LSP server",
    description="""
    Manually restart the Pyright LSP server.

    **Workflow**:
    1. Gracefully shutdown current LSP server
    2. Start new LSP server instance
    3. Return health status

    **Use cases**:
    - Recovery: Manual restart after crash
    - Configuration: Apply new LSP settings
    - Debugging: Clear LSP server state

    **Warning**: Restart increments restart_count. Excessive restarts may indicate
    instability (max 3 restarts allowed by lifecycle manager).

    **Story 13.3**: LSP Lifecycle Management
    """,
)
async def restart_lsp_server():
    """
    Manually restart LSP server.

    Returns:
        LSPRestartResponse: Restart status and new health information

    Raises:
        HTTPException: If restart fails
    """
    try:
        # Import here to avoid circular dependency
        from dependencies import get_lsp_lifecycle_manager

        lsp_manager = get_lsp_lifecycle_manager()

        if not lsp_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LSP lifecycle manager not initialized",
            )

        # Perform restart
        logger.info("Manual LSP server restart requested via API")
        await lsp_manager.restart()

        # Get new health status
        health = await lsp_manager.health_check()

        return LSPRestartResponse(
            status="restarted",
            message="LSP server restarted successfully",
            health=LSPHealthResponse(**health)
        )

    except Exception as e:
        logger.error(f"LSP restart failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Restart failed: {str(e)}",
        )
