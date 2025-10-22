"""
Unit tests for LSP Lifecycle Manager.

Story: EPIC-13 Story 13.3 - LSP Lifecycle Management
Author: Claude Code
Date: 2025-10-22
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from services.lsp.lsp_lifecycle_manager import LSPLifecycleManager
from services.lsp.lsp_client import PyrightLSPClient
from services.lsp.lsp_errors import LSPError


# Mark all tests as async
pytestmark = pytest.mark.anyio


# ============================================
# Unit Tests (Mocked LSP Client)
# ============================================

@pytest.fixture
def mock_lsp_client():
    """Create a mock LSP client."""
    client = AsyncMock(spec=PyrightLSPClient)
    client.process = MagicMock()
    client.process.pid = 12345
    client.process.returncode = None
    client.initialized = True
    client.start = AsyncMock()
    client.shutdown = AsyncMock()
    return client


async def test_lifecycle_manager_initialization():
    """Test LSPLifecycleManager can be initialized."""
    manager = LSPLifecycleManager(
        workspace_root="/tmp/test",
        max_restart_attempts=3
    )

    assert manager.workspace_root == "/tmp/test"
    assert manager.max_restart_attempts == 3
    assert manager.restart_count == 0
    assert manager.client is None


async def test_lifecycle_manager_start_success():
    """Test LSP server starts successfully on first attempt."""
    manager = LSPLifecycleManager(max_restart_attempts=3)

    with patch('services.lsp.lsp_lifecycle_manager.PyrightLSPClient') as MockClient:
        mock_client = AsyncMock()
        mock_client.process = MagicMock()
        mock_client.process.pid = 12345
        mock_client.start = AsyncMock()
        MockClient.return_value = mock_client

        await manager.start()

        # Verify client was created and started
        MockClient.assert_called_once_with(workspace_root="/tmp/lsp_workspace")
        mock_client.start.assert_called_once()

        # Verify restart count reset
        assert manager.restart_count == 0
        assert manager.client == mock_client


async def test_lifecycle_manager_start_retry_success():
    """Test LSP server starts after retry (2nd attempt succeeds)."""
    manager = LSPLifecycleManager(max_restart_attempts=3)

    with patch('services.lsp.lsp_lifecycle_manager.PyrightLSPClient') as MockClient:
        mock_client = AsyncMock()
        mock_client.process = MagicMock()
        mock_client.process.pid = 12345

        # First attempt fails, second succeeds
        mock_client.start = AsyncMock(side_effect=[
            Exception("Start failed"),
            None  # Success on second attempt
        ])
        MockClient.return_value = mock_client

        # Mock sleep to speed up test
        with patch('asyncio.sleep', new_callable=AsyncMock):
            await manager.start()

        # Verify 2 attempts were made
        assert mock_client.start.call_count == 2
        assert manager.restart_count == 0  # Reset after successful start


async def test_lifecycle_manager_start_max_attempts_exceeded():
    """Test LSP server fails after max restart attempts."""
    manager = LSPLifecycleManager(max_restart_attempts=2)

    with patch('services.lsp.lsp_lifecycle_manager.PyrightLSPClient') as MockClient:
        mock_client = AsyncMock()
        mock_client.start = AsyncMock(side_effect=Exception("Start failed"))
        MockClient.return_value = mock_client

        # Mock sleep to speed up test
        with patch('asyncio.sleep', new_callable=AsyncMock):
            with pytest.raises(LSPError, match="failed after 2 attempts"):
                await manager.start()

        # Verify all attempts were made
        assert mock_client.start.call_count == 2


async def test_lifecycle_manager_ensure_running_already_running():
    """Test ensure_running does nothing if server is already running."""
    manager = LSPLifecycleManager()
    manager.client = AsyncMock()
    manager.client.process = MagicMock()
    manager.client.process.returncode = None  # Not crashed
    manager.client.initialized = True

    # Should not restart
    await manager.ensure_running()

    # Verify no restart occurred
    assert manager.restart_count == 0


async def test_lifecycle_manager_ensure_running_restart_on_crash():
    """Test ensure_running restarts crashed server."""
    manager = LSPLifecycleManager(max_restart_attempts=3)

    # Create initial client (crashed)
    initial_client = AsyncMock()
    initial_client.process = MagicMock()
    initial_client.process.returncode = 1  # Crashed
    manager.client = initial_client

    # Mock start to create new client
    with patch.object(manager, 'start', new_callable=AsyncMock) as mock_start:
        await manager.ensure_running()

        # Verify restart was called
        mock_start.assert_called_once()

        # Verify restart count incremented
        assert manager.restart_count == 1


async def test_lifecycle_manager_ensure_running_max_restarts_exceeded():
    """Test ensure_running raises error after max restarts."""
    manager = LSPLifecycleManager(max_restart_attempts=2)

    # Simulate 3 crashes (exceeds max)
    manager.restart_count = 3
    manager.client = AsyncMock()
    manager.client.process = MagicMock()
    manager.client.process.returncode = 1  # Crashed

    with pytest.raises(LSPError, match="exceeded 2 restarts"):
        await manager.ensure_running()


async def test_lifecycle_manager_health_check_not_started():
    """Test health check when server not started."""
    manager = LSPLifecycleManager()

    health = await manager.health_check()

    assert health["status"] == "not_started"
    assert health["running"] is False
    assert health["initialized"] is False
    assert health["restart_count"] == 0
    assert health["pid"] is None


async def test_lifecycle_manager_health_check_healthy():
    """Test health check when server is healthy."""
    manager = LSPLifecycleManager()
    manager.client = AsyncMock()
    manager.client.process = MagicMock()
    manager.client.process.pid = 12345
    manager.client.process.returncode = None  # Running
    manager.client.initialized = True
    manager.restart_count = 0

    health = await manager.health_check()

    assert health["status"] == "healthy"
    assert health["running"] is True
    assert health["initialized"] is True
    assert health["restart_count"] == 0
    assert health["pid"] == 12345


async def test_lifecycle_manager_health_check_starting():
    """Test health check when server is starting."""
    manager = LSPLifecycleManager()
    manager.client = AsyncMock()
    manager.client.process = MagicMock()
    manager.client.process.pid = 12345
    manager.client.process.returncode = None  # Running
    manager.client.initialized = False  # Not yet initialized

    health = await manager.health_check()

    assert health["status"] == "starting"
    assert health["running"] is True
    assert health["initialized"] is False


async def test_lifecycle_manager_health_check_crashed():
    """Test health check when server crashed."""
    manager = LSPLifecycleManager()
    manager.client = AsyncMock()
    manager.client.process = MagicMock()
    manager.client.process.returncode = 1  # Crashed
    manager.restart_count = 1

    health = await manager.health_check()

    assert health["status"] == "crashed"
    assert health["running"] is False
    assert health["returncode"] == 1
    assert health["restart_count"] == 1


async def test_lifecycle_manager_manual_restart():
    """Test manual restart increments restart count and starts new server."""
    manager = LSPLifecycleManager()

    # Setup initial client
    initial_client = AsyncMock()
    initial_client.shutdown = AsyncMock()
    manager.client = initial_client

    with patch.object(manager, 'start', new_callable=AsyncMock) as mock_start:
        await manager.restart()

        # Verify shutdown was called
        initial_client.shutdown.assert_called_once()

        # Verify start was called
        mock_start.assert_called_once()

        # Verify restart count incremented
        assert manager.restart_count == 1


async def test_lifecycle_manager_shutdown_graceful():
    """Test graceful shutdown."""
    manager = LSPLifecycleManager()
    mock_client = AsyncMock()
    mock_client.shutdown = AsyncMock()
    manager.client = mock_client

    await manager.shutdown()

    # Verify shutdown was called (check mock before manager.client is cleared)
    mock_client.shutdown.assert_called_once()

    # Verify client reference cleared
    assert manager.client is None


async def test_lifecycle_manager_shutdown_no_client():
    """Test shutdown does nothing if no client."""
    manager = LSPLifecycleManager()
    manager.client = None

    # Should not raise
    await manager.shutdown()

    # Verify client is still None
    assert manager.client is None


async def test_lifecycle_manager_is_healthy_true():
    """Test is_healthy returns True when server is healthy."""
    manager = LSPLifecycleManager()
    manager.client = AsyncMock()
    manager.client.process = MagicMock()
    manager.client.process.returncode = None  # Running
    manager.client.initialized = True

    assert manager.is_healthy() is True


async def test_lifecycle_manager_is_healthy_false_no_client():
    """Test is_healthy returns False when no client."""
    manager = LSPLifecycleManager()
    manager.client = None

    assert manager.is_healthy() is False


async def test_lifecycle_manager_is_healthy_false_crashed():
    """Test is_healthy returns False when server crashed."""
    manager = LSPLifecycleManager()
    manager.client = AsyncMock()
    manager.client.process = MagicMock()
    manager.client.process.returncode = 1  # Crashed

    assert manager.is_healthy() is False


async def test_lifecycle_manager_lsp_client_property():
    """Test lsp_client property returns client."""
    manager = LSPLifecycleManager()
    mock_client = AsyncMock()
    manager.client = mock_client

    assert manager.lsp_client == mock_client


# ============================================
# Integration Tests (Optional - Real Pyright)
# ============================================

@pytest.mark.skipif(
    True,  # Skip by default
    reason="Requires pyright-langserver installed (integration test)"
)
async def test_lifecycle_manager_real_start_shutdown():
    """Test real LSP server start and shutdown (INTEGRATION TEST)."""
    manager = LSPLifecycleManager(max_restart_attempts=1)

    try:
        # Start LSP server
        await manager.start()

        # Verify healthy
        health = await manager.health_check()
        assert health["status"] == "healthy"
        assert health["running"] is True
        assert health["initialized"] is True

    finally:
        # Always shutdown
        await manager.shutdown()
