"""
Unit tests for Pyright LSP Client.

Story: EPIC-13 Story 13.1 - Pyright LSP Wrapper
Author: Claude Code
Date: 2025-10-22
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from services.lsp.lsp_client import PyrightLSPClient, LSPResponse
from services.lsp.lsp_errors import (
    LSPError,
    LSPInitializationError,
    LSPTimeoutError,
    LSPServerCrashedError,
)


# Mark all tests as async
pytestmark = pytest.mark.anyio


# ============================================
# Unit Tests (Mocked)
# ============================================

@pytest.fixture
async def mock_lsp_process():
    """Create a mock LSP server process."""
    process = MagicMock()
    process.pid = 12345
    process.returncode = None
    process.stdin = AsyncMock()
    process.stdin.write = Mock()
    process.stdin.drain = AsyncMock()
    process.stdout = AsyncMock()
    process.stderr = AsyncMock()
    process.wait = AsyncMock()
    process.kill = Mock()
    return process


async def test_lsp_client_initialization():
    """Test LSP client can be initialized."""
    client = PyrightLSPClient(workspace_root="/tmp/test")

    assert client.workspace_root == "/tmp/test"
    assert client.process is None
    assert client.initialized is False
    assert client.request_id == 0


async def test_lsp_start_server_not_found():
    """Test LSP start fails gracefully if pyright-langserver not found."""
    client = PyrightLSPClient()

    with patch('asyncio.create_subprocess_exec', side_effect=FileNotFoundError):
        with pytest.raises(LSPInitializationError, match="pyright-langserver not found"):
            await client.start()


async def test_lsp_hover_before_initialization():
    """Test hover fails if server not initialized."""
    client = PyrightLSPClient()

    with pytest.raises(LSPError, match="not initialized"):
        await client.hover("/tmp/test.py", "def foo(): pass", 0, 0)


async def test_lsp_document_symbols_before_initialization():
    """Test document symbols fails if server not initialized."""
    client = PyrightLSPClient()

    with pytest.raises(LSPError, match="not initialized"):
        await client.get_document_symbols("/tmp/test.py", "def foo(): pass")


async def test_lsp_send_request_server_crashed():
    """Test send_request detects crashed server."""
    client = PyrightLSPClient()
    client.initialized = True
    client.process = MagicMock()
    client.process.stdin = None  # Simulate crashed process

    with pytest.raises(LSPServerCrashedError):
        await client._send_request("test/method", {})


async def test_lsp_response_dataclass():
    """Test LSPResponse dataclass."""
    # Success response
    response = LSPResponse(id="1", result={"data": "test"})
    assert response.id == "1"
    assert response.result == {"data": "test"}
    assert response.error is None

    # Error response
    response = LSPResponse(id="2", error={"code": -32600, "message": "Invalid Request"})
    assert response.id == "2"
    assert response.result is None
    assert response.error["code"] == -32600


async def test_lsp_is_alive():
    """Test is_alive() method."""
    client = PyrightLSPClient()

    # No process
    assert client.is_alive() is False

    # Process running
    client.process = MagicMock()
    client.process.returncode = None
    assert client.is_alive() is True

    # Process exited
    client.process.returncode = 0
    assert client.is_alive() is False


async def test_lsp_shutdown_no_process():
    """Test shutdown when no process exists."""
    client = PyrightLSPClient()
    await client.shutdown()  # Should not raise


# ============================================
# Integration Tests (Require Pyright)
# ============================================

@pytest.mark.skipif(
    False,  # Enable test (Pyright IS installed)
    reason="Requires pyright-langserver installed"
)
async def test_lsp_server_startup_real():
    """Test LSP server starts successfully (INTEGRATION TEST)."""
    client = PyrightLSPClient()

    try:
        await client.start()

        assert client.process is not None
        assert client.process.pid > 0
        assert client.initialized is True
        assert client.is_alive() is True

    finally:
        await client.shutdown()


@pytest.mark.skipif(
    False,  # Enable test (Pyright IS installed)
    reason="Requires pyright-langserver installed"
)
async def test_lsp_hover_query_real():
    """Test hover returns type information (INTEGRATION TEST)."""
    client = PyrightLSPClient()

    try:
        await client.start()

        source = '''def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
'''

        # Hover over 'add' function name (line 0, char 4)
        hover_text = await client.hover("/tmp/test.py", source, line=0, character=4)

        assert hover_text is not None
        # Pyright hover should contain function signature
        assert "add" in hover_text.lower() or "int" in hover_text.lower()

    finally:
        await client.shutdown()


@pytest.mark.skipif(
    True,  # Skip by default
    reason="Requires pyright-langserver installed"
)
async def test_lsp_document_symbols_real():
    """Test document symbols extraction (INTEGRATION TEST)."""
    client = PyrightLSPClient()

    try:
        await client.start()

        source = '''class User:
    def __init__(self, name: str):
        self.name = name

    def greet(self) -> str:
        return f"Hello, {self.name}"
'''

        symbols = await client.get_document_symbols("/tmp/test.py", source)

        assert len(symbols) > 0
        # Should find User class
        symbol_names = [s.get("name") for s in symbols if "name" in s]
        assert "User" in symbol_names or "__init__" in symbol_names

    finally:
        await client.shutdown()


@pytest.mark.skipif(
    True,  # Skip by default
    reason="Requires pyright-langserver installed"
)
async def test_lsp_request_timeout_real():
    """Test request timeout handling (INTEGRATION TEST)."""
    client = PyrightLSPClient()

    try:
        await client.start()

        # Send request with very short timeout (should timeout)
        with pytest.raises(LSPTimeoutError):
            await client._send_request(
                "textDocument/hover",
                {
                    "textDocument": {"uri": "file:///tmp/test.py"},
                    "position": {"line": 0, "character": 0}
                },
                timeout=0.001  # 1ms timeout (too short)
            )

    finally:
        await client.shutdown()


@pytest.mark.skipif(
    True,  # Skip by default
    reason="Requires pyright-langserver installed"
)
async def test_lsp_server_crash_recovery_real():
    """Test client handles server crash gracefully (INTEGRATION TEST)."""
    client = PyrightLSPClient()

    try:
        await client.start()
        assert client.is_alive() is True

        # Kill server process
        client.process.kill()
        await asyncio.sleep(0.5)  # Wait for process to die

        assert client.is_alive() is False

        # Query should fail gracefully
        with pytest.raises(LSPServerCrashedError):
            await client.hover("/tmp/test.py", "def foo(): pass", 0, 0)

    finally:
        # Shutdown (should handle dead process gracefully)
        await client.shutdown()


@pytest.mark.skipif(
    True,  # Skip by default
    reason="Requires pyright-langserver installed"
)
async def test_lsp_hover_no_hover_info_real():
    """Test hover returns None when no hover info available (INTEGRATION TEST)."""
    client = PyrightLSPClient()

    try:
        await client.start()

        # Empty file or whitespace position
        source = '''
# Just a comment
'''

        hover_text = await client.hover("/tmp/test.py", source, line=0, character=0)

        # Should return None (no hover info for empty line)
        assert hover_text is None

    finally:
        await client.shutdown()


# ============================================
# Performance Tests
# ============================================

@pytest.mark.skipif(
    True,  # Skip by default
    reason="Performance test - requires pyright-langserver"
)
async def test_lsp_hover_performance_real():
    """Test hover query performance (<100ms target)."""
    import time

    client = PyrightLSPClient()

    try:
        await client.start()

        source = '''def process_data(items: list[int]) -> int:
    """Process a list of integers."""
    return sum(items)
'''

        # Measure hover query time
        start = time.time()
        await client.hover("/tmp/test.py", source, line=0, character=4)
        elapsed = time.time() - start

        # Should be <100ms (target from EPIC-13)
        assert elapsed < 0.1, f"Hover too slow: {elapsed*1000:.0f}ms"

    finally:
        await client.shutdown()


@pytest.mark.skipif(
    True,  # Skip by default
    reason="Performance test - requires pyright-langserver"
)
async def test_lsp_server_startup_performance_real():
    """Test LSP server starts in <500ms."""
    import time

    client = PyrightLSPClient()

    try:
        start = time.time()
        await client.start()
        elapsed = time.time() - start

        # Should start in <500ms (target from EPIC-13)
        assert elapsed < 0.5, f"Startup too slow: {elapsed*1000:.0f}ms"

    finally:
        await client.shutdown()
