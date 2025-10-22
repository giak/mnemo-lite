"""
LSP Lifecycle Manager - Auto-restart and health monitoring.

Story: EPIC-13 Story 13.3 - LSP Lifecycle Management
Author: Claude Code
Date: 2025-10-22

Manages Pyright LSP server lifecycle with auto-restart on crashes and health monitoring.
"""

import asyncio
import structlog
from typing import Optional, Dict, Any

from .lsp_client import PyrightLSPClient
from .lsp_errors import LSPError, LSPInitializationError

logger = structlog.get_logger()


class LSPLifecycleManager:
    """
    Manage LSP server lifecycle with auto-restart and health monitoring.

    Features:
    - Auto-restart on crash (configurable max attempts)
    - Exponential backoff for restarts
    - Health status monitoring
    - Manual restart capability
    - Graceful shutdown

    Example:
        manager = LSPLifecycleManager(max_restart_attempts=3)
        await manager.start()

        # Check health
        health = await manager.health_check()

        # Ensure running (auto-restart if needed)
        await manager.ensure_running()

        # Shutdown
        await manager.shutdown()
    """

    def __init__(
        self,
        workspace_root: str = "/tmp/lsp_workspace",
        max_restart_attempts: int = 3
    ):
        """
        Initialize LSP Lifecycle Manager.

        Args:
            workspace_root: Workspace root directory for LSP server
            max_restart_attempts: Maximum number of restart attempts (default: 3)
        """
        self.workspace_root = workspace_root
        self.max_restart_attempts = max_restart_attempts
        self.restart_count = 0
        self.client: Optional[PyrightLSPClient] = None
        self.logger = logger.bind(service="lsp_lifecycle")

    async def start(self):
        """
        Start LSP server with retry and exponential backoff.

        Attempts to start the LSP server up to max_restart_attempts times.
        Uses exponential backoff (2^attempt seconds) between retries.

        Raises:
            LSPError: If server fails to start after all attempts
        """
        for attempt in range(1, self.max_restart_attempts + 1):
            try:
                self.logger.info(
                    "Starting LSP server",
                    attempt=attempt,
                    max_attempts=self.max_restart_attempts
                )

                # Create new client instance
                self.client = PyrightLSPClient(workspace_root=self.workspace_root)

                # Start LSP server
                await self.client.start()

                self.logger.info(
                    "LSP server started successfully",
                    attempt=attempt,
                    pid=self.client.process.pid if self.client.process else None
                )

                # Reset restart count on successful start
                self.restart_count = 0
                return

            except Exception as e:
                self.logger.warning(
                    "LSP server start failed",
                    attempt=attempt,
                    max_attempts=self.max_restart_attempts,
                    error=str(e),
                    error_type=type(e).__name__
                )

                if attempt < self.max_restart_attempts:
                    # Exponential backoff: 2^attempt seconds
                    backoff_seconds = 2 ** attempt
                    self.logger.info(
                        f"Retrying in {backoff_seconds}s...",
                        backoff_seconds=backoff_seconds
                    )
                    await asyncio.sleep(backoff_seconds)
                else:
                    # Max attempts reached
                    self.logger.error(
                        "LSP server failed to start after max attempts",
                        max_attempts=self.max_restart_attempts
                    )
                    raise LSPError(
                        f"LSP server start failed after {self.max_restart_attempts} attempts"
                    )

    async def ensure_running(self):
        """
        Ensure LSP server is running, restart if crashed.

        Checks if the LSP server process is alive. If crashed, attempts to restart
        with respect to max_restart_attempts limit.

        Raises:
            LSPError: If restart count exceeds max_restart_attempts
        """
        # Check if client exists
        if not self.client:
            self.logger.warning("LSP client not initialized, starting...")
            await self.start()
            return

        # Check if process exists
        if not self.client.process:
            self.logger.warning("LSP process not found, restarting...")
            self.restart_count += 1

            if self.restart_count > self.max_restart_attempts:
                self.logger.error(
                    "LSP server exceeded max restarts, giving up",
                    restart_count=self.restart_count,
                    max_attempts=self.max_restart_attempts
                )
                raise LSPError(
                    f"LSP server unstable (exceeded {self.max_restart_attempts} restarts)"
                )

            await self.start()
            return

        # Check if process crashed (returncode is not None)
        if self.client.process.returncode is not None:
            self.logger.warning(
                "LSP server crashed, restarting...",
                returncode=self.client.process.returncode,
                restart_count=self.restart_count
            )
            self.restart_count += 1

            if self.restart_count > self.max_restart_attempts:
                self.logger.error(
                    "LSP server exceeded max restarts, giving up",
                    restart_count=self.restart_count,
                    max_attempts=self.max_restart_attempts
                )
                raise LSPError(
                    f"LSP server unstable (exceeded {self.max_restart_attempts} restarts)"
                )

            # Attempt restart
            await self.start()
            return

        # Server is running - no action needed
        self.logger.debug("LSP server is running")

    async def health_check(self) -> Dict[str, Any]:
        """
        Check LSP server health and return status.

        Returns:
            Dict with health status:
                - status: str (healthy, crashed, not_started, starting, error)
                - running: bool (process exists and alive)
                - initialized: bool (LSP initialized)
                - restart_count: int (number of restarts)
                - pid: int | None (process ID if running)
        """
        health: Dict[str, Any] = {
            "status": "unknown",
            "running": False,
            "initialized": False,
            "restart_count": self.restart_count,
            "pid": None
        }

        # Client not created yet
        if not self.client:
            health["status"] = "not_started"
            return health

        # Process not started
        if not self.client.process:
            health["status"] = "not_started"
            return health

        # Process crashed (returncode is not None)
        if self.client.process.returncode is not None:
            health["status"] = "crashed"
            health["returncode"] = self.client.process.returncode
            return health

        # Process running
        health["running"] = True
        health["pid"] = self.client.process.pid
        health["initialized"] = self.client.initialized

        if self.client.initialized:
            health["status"] = "healthy"
        else:
            health["status"] = "starting"

        return health

    async def restart(self):
        """
        Manually restart LSP server.

        Shuts down the current server and starts a new one.
        Increments restart_count.

        Raises:
            LSPError: If restart fails
        """
        self.logger.info("Manual LSP server restart requested")

        # Shutdown existing server
        if self.client:
            try:
                await self.client.shutdown()
            except Exception as e:
                self.logger.warning(
                    "Error during shutdown, forcing restart",
                    error=str(e)
                )

        # Increment restart count
        self.restart_count += 1

        # Start new server
        await self.start()

        self.logger.info(
            "LSP server restarted successfully",
            restart_count=self.restart_count
        )

    async def shutdown(self):
        """
        Shutdown LSP server gracefully.

        Attempts graceful shutdown. If client doesn't exist, does nothing.
        """
        if not self.client:
            self.logger.debug("LSP client not initialized, nothing to shutdown")
            return

        try:
            self.logger.info("Shutting down LSP server...")
            await self.client.shutdown()
            self.logger.info("LSP server shut down successfully")

        except Exception as e:
            self.logger.error(
                "Error during LSP server shutdown",
                error=str(e),
                error_type=type(e).__name__
            )

        finally:
            # Clear client reference
            self.client = None

    def is_healthy(self) -> bool:
        """
        Quick health check (synchronous).

        Returns:
            bool: True if server is running and initialized, False otherwise
        """
        if not self.client:
            return False

        if not self.client.process:
            return False

        if self.client.process.returncode is not None:
            return False

        return self.client.initialized

    @property
    def lsp_client(self) -> Optional[PyrightLSPClient]:
        """
        Get the underlying LSP client.

        Returns:
            PyrightLSPClient | None: LSP client if available, None otherwise
        """
        return self.client
