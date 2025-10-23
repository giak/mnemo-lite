"""
Pyright LSP Client - JSON-RPC over stdio.

Story: EPIC-13 Story 13.1 - Pyright LSP Wrapper
Author: Claude Code
Date: 2025-10-22

Based on LSP specification: https://microsoft.github.io/language-server-protocol/
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import structlog

from .lsp_errors import (
    LSPError,
    LSPInitializationError,
    LSPCommunicationError,
    LSPTimeoutError,
    LSPServerCrashedError,
)

logger = structlog.get_logger()


@dataclass
class LSPResponse:
    """LSP JSON-RPC response."""
    id: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None


class PyrightLSPClient:
    """
    Pyright LSP client (JSON-RPC over stdio).

    Implements Language Server Protocol communication with Pyright language server.
    All communication is asynchronous and non-blocking.

    Lifecycle:
    1. start() - Spawn pyright-langserver subprocess
    2. _initialize() - Send LSP initialize request
    3. hover() / get_document_symbols() - Query methods
    4. shutdown() - Graceful shutdown

    Example:
        client = PyrightLSPClient()
        await client.start()

        hover_text = await client.hover("/tmp/test.py", source_code, line=1, character=4)

        await client.shutdown()
    """

    def __init__(self, workspace_root: str = "/tmp/lsp_workspace"):
        """
        Initialize LSP client.

        Args:
            workspace_root: Workspace root directory for LSP server
        """
        self.workspace_root = workspace_root
        self.process: Optional[asyncio.subprocess.Process] = None
        self.request_id = 0
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self.initialized = False
        self._reader_task: Optional[asyncio.Task] = None
        self._stderr_task: Optional[asyncio.Task] = None  # EPIC-16: Prevent PIPE deadlock

    async def start(self):
        """
        Start Pyright LSP server.

        Raises:
            LSPInitializationError: If server fails to start or initialize
        """
        if self.process:
            logger.warning("LSP server already running")
            return

        try:
            # Spawn pyright-langserver subprocess
            logger.info("Starting Pyright LSP server...")

            self.process = await asyncio.create_subprocess_exec(
                "pyright-langserver", "--stdio",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            logger.info("Pyright LSP server started", pid=self.process.pid)

            # Start response reader task
            self._reader_task = asyncio.create_task(self._read_responses())

            # EPIC-16: Start stderr drain task to prevent PIPE deadlock
            self._stderr_task = asyncio.create_task(self._drain_stderr())

            # Initialize server
            await self._initialize()

        except FileNotFoundError:
            logger.error("pyright-langserver not found in PATH")
            raise LSPInitializationError(
                "pyright-langserver not found. Install with: pip install pyright"
            )
        except Exception as e:
            logger.error("Failed to start LSP server", error=str(e))
            raise LSPInitializationError(f"LSP server startup failed: {e}")

    async def _initialize(self):
        """
        Send LSP initialize request.

        Raises:
            LSPInitializationError: If initialization fails
        """
        logger.info("Initializing LSP server...")

        init_params = {
            "processId": None,
            "rootUri": f"file://{self.workspace_root}",
            "capabilities": {
                "textDocument": {
                    "hover": {
                        "contentFormat": ["plaintext", "markdown"]
                    },
                    "definition": {
                        "linkSupport": False
                    },
                    "documentSymbol": {
                        "hierarchicalDocumentSymbolSupport": True
                    }
                }
            },
            "initializationOptions": {},
            "workspaceFolders": None
        }

        response = await self._send_request("initialize", init_params, timeout=10.0)

        if response.error:
            raise LSPInitializationError(f"Initialization failed: {response.error}")

        # Send initialized notification
        await self._send_notification("initialized", {})

        self.initialized = True
        logger.info("LSP server initialized successfully")

    async def hover(
        self,
        file_path: str,
        source_code: str,
        line: int,
        character: int
    ) -> Optional[str]:
        """
        Get hover information (type, docstring) for a position.

        LSP method: textDocument/hover

        Args:
            file_path: File path (used as document URI)
            source_code: Complete source code of file
            line: Line number (0-indexed)
            character: Character position (0-indexed)

        Returns:
            Hover text content (type information, docstring) or None if no hover info

        Raises:
            LSPError: If server not initialized or communication fails
            LSPTimeoutError: If request times out
        """
        if not self.initialized:
            raise LSPError("LSP server not initialized")

        # Open document
        await self._open_document(file_path, source_code)

        try:
            # Send hover request
            params = {
                "textDocument": {"uri": f"file://{file_path}"},
                "position": {"line": line, "character": character}
            }

            response = await self._send_request(
                "textDocument/hover",
                params,
                timeout=3.0
            )

            if response.error or not response.result:
                return None

            # Extract hover text
            hover_content = response.result.get("contents")

            if not hover_content:
                return None

            # Parse hover content (can be string, dict, or list)
            if isinstance(hover_content, str):
                return hover_content
            elif isinstance(hover_content, dict):
                # MarkupContent format
                if "value" in hover_content:
                    return hover_content["value"]
                elif "kind" in hover_content and "value" in hover_content:
                    return hover_content["value"]
            elif isinstance(hover_content, list) and hover_content:
                # Array of MarkedString
                parts = []
                for item in hover_content:
                    if isinstance(item, str):
                        parts.append(item)
                    elif isinstance(item, dict) and "value" in item:
                        parts.append(item["value"])
                return "\n".join(parts)

            return None

        finally:
            # Close document
            await self._close_document(file_path)

    async def get_document_symbols(
        self,
        file_path: str,
        source_code: str
    ) -> List[Dict[str, Any]]:
        """
        Get all symbols in document.

        LSP method: textDocument/documentSymbol

        Args:
            file_path: File path (used as document URI)
            source_code: Complete source code of file

        Returns:
            List of document symbols with name, kind, range, etc.

        Raises:
            LSPError: If server not initialized or communication fails
            LSPTimeoutError: If request times out
        """
        if not self.initialized:
            raise LSPError("LSP server not initialized")

        await self._open_document(file_path, source_code)

        try:
            params = {
                "textDocument": {"uri": f"file://{file_path}"}
            }

            response = await self._send_request(
                "textDocument/documentSymbol",
                params,
                timeout=3.0
            )

            if response.error or not response.result:
                return []

            return response.result

        finally:
            await self._close_document(file_path)

    async def _send_request(
        self,
        method: str,
        params: Dict[str, Any],
        timeout: float = 5.0
    ) -> LSPResponse:
        """
        Send JSON-RPC request with timeout.

        Args:
            method: LSP method name
            params: Method parameters
            timeout: Request timeout in seconds

        Returns:
            LSP response

        Raises:
            LSPServerCrashedError: If server process crashed
            LSPTimeoutError: If request times out
            LSPCommunicationError: If communication fails
        """
        if not self.process or not self.process.stdin:
            raise LSPServerCrashedError("LSP server not running")

        # Check if process crashed
        if self.process.returncode is not None:
            raise LSPServerCrashedError(
                f"LSP server crashed with code {self.process.returncode}"
            )

        # Generate request ID
        request_id = str(self.request_id)
        self.request_id += 1

        # Create JSON-RPC request
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }

        # Serialize with Content-Length header
        content = json.dumps(request)
        message = f"Content-Length: {len(content)}\r\n\r\n{content}"

        try:
            # Send request
            self.process.stdin.write(message.encode('utf-8'))
            await self.process.stdin.drain()

            # Wait for response (with timeout)
            future: asyncio.Future = asyncio.Future()
            self.pending_requests[request_id] = future

            try:
                response = await asyncio.wait_for(future, timeout=timeout)
                return response

            except asyncio.TimeoutError:
                logger.warning("LSP request timed out", method=method, timeout=timeout)
                self.pending_requests.pop(request_id, None)
                raise LSPTimeoutError(f"LSP request {method} timed out after {timeout}s")

        except Exception as e:
            if isinstance(e, (LSPTimeoutError, LSPServerCrashedError)):
                raise
            logger.error("LSP communication error", method=method, error=str(e))
            raise LSPCommunicationError(f"Communication error: {e}")

    async def _send_notification(self, method: str, params: Dict[str, Any]):
        """
        Send JSON-RPC notification (no response expected).

        Args:
            method: LSP method name
            params: Method parameters
        """
        if not self.process or not self.process.stdin:
            return

        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }

        content = json.dumps(notification)
        message = f"Content-Length: {len(content)}\r\n\r\n{content}"

        try:
            self.process.stdin.write(message.encode('utf-8'))
            await self.process.stdin.drain()
        except Exception as e:
            logger.warning("Failed to send notification", method=method, error=str(e))

    async def _read_responses(self):
        """
        Read responses from LSP server (background task).

        Parses JSON-RPC messages from stdout and resolves pending request futures.
        """
        if not self.process or not self.process.stdout:
            return

        buffer = b""

        try:
            while True:
                chunk = await self.process.stdout.read(1024)
                if not chunk:
                    logger.info("LSP server stdout closed")
                    break

                buffer += chunk

                # Parse complete messages
                while b"\r\n\r\n" in buffer:
                    # Split header and content
                    header_bytes, rest = buffer.split(b"\r\n\r\n", 1)

                    # Extract Content-Length
                    content_length = None
                    for line in header_bytes.split(b"\r\n"):
                        if line.startswith(b"Content-Length:"):
                            content_length = int(line.split(b":")[1].strip())
                            break

                    if content_length is None:
                        logger.warning("Invalid LSP message (no Content-Length)")
                        buffer = rest
                        continue

                    # Check if full message received
                    if len(rest) < content_length:
                        # Incomplete message, wait for more data
                        buffer = b"\r\n\r\n".join([header_bytes, rest])
                        break

                    # Extract message
                    message_bytes = rest[:content_length]
                    buffer = rest[content_length:]

                    # Parse JSON
                    try:
                        message = json.loads(message_bytes.decode('utf-8'))
                        self._handle_message(message)
                    except json.JSONDecodeError as e:
                        logger.warning("Invalid JSON from LSP", error=str(e))

        except Exception as e:
            logger.error("LSP response reader crashed", error=str(e))

    def _handle_message(self, message: Dict[str, Any]):
        """
        Handle JSON-RPC message (response or notification).

        Args:
            message: Parsed JSON-RPC message
        """
        # Check if response (has 'id') or notification
        if "id" not in message:
            # Notification (e.g., diagnostics, logs)
            # Log and ignore for now
            if "method" in message:
                logger.debug("LSP notification received",
                            method=message.get("method"))
            return

        request_id = str(message["id"])

        # Find pending request
        future = self.pending_requests.pop(request_id, None)
        if not future or future.done():
            return

        # Create response object
        response = LSPResponse(
            id=request_id,
            result=message.get("result"),
            error=message.get("error")
        )

        # Resolve future
        future.set_result(response)

    async def _open_document(self, file_path: str, source_code: str):
        """
        Open document in LSP server (required before queries).

        Args:
            file_path: File path for document URI
            source_code: Complete source code
        """
        await self._send_notification("textDocument/didOpen", {
            "textDocument": {
                "uri": f"file://{file_path}",
                "languageId": "python",
                "version": 1,
                "text": source_code
            }
        })

    async def _close_document(self, file_path: str):
        """
        Close document in LSP server.

        Args:
            file_path: File path for document URI
        """
        await self._send_notification("textDocument/didClose", {
            "textDocument": {"uri": f"file://{file_path}"}
        })

    async def _drain_stderr(self):
        """
        Drain stderr to prevent PIPE buffer deadlock.

        EPIC-16 Critical Fix: Pyright LSP writes logs to stderr. If we don't
        actively read stderr, the OS pipe buffer (4KB-64KB) fills up, causing
        the LSP process to block on write, leading to deadlock.

        This method runs as a background task, continuously reading and logging
        stderr output to keep the pipe drained.

        Reference: https://docs.python.org/3/library/asyncio-subprocess.html
        "This will deadlock when using stdout=PIPE or stderr=PIPE and the child
        process generates enough output to block waiting for the OS pipe buffer."
        """
        if not self.process or not self.process.stderr:
            return

        try:
            while True:
                # Read stderr in chunks to prevent blocking
                chunk = await self.process.stderr.read(1024)

                if not chunk:
                    logger.debug("Pyright LSP stderr closed")
                    break

                # Log stderr for debugging (decode with error handling)
                stderr_text = chunk.decode('utf-8', errors='ignore').strip()
                if stderr_text:
                    logger.debug("Pyright LSP stderr", message=stderr_text[:200])

        except asyncio.CancelledError:
            logger.debug("Pyright LSP stderr drain task cancelled")
            raise
        except Exception as e:
            logger.warning("Error draining Pyright LSP stderr", error=str(e))

    async def shutdown(self):
        """
        Shutdown LSP server gracefully.

        Sends shutdown request, exit notification, and waits for process to exit.
        Falls back to kill() if graceful shutdown fails.
        """
        if not self.process:
            return

        try:
            logger.info("Shutting down LSP server...")

            # Send shutdown request
            await self._send_request("shutdown", {}, timeout=5.0)

            # Send exit notification
            await self._send_notification("exit", {})

            # EPIC-16 Critical Fix: Use communicate() instead of wait() to prevent deadlock
            # communicate() automatically drains stdout/stderr buffers, preventing PIPE deadlock
            # Reference: https://docs.python.org/3/library/asyncio-subprocess.html
            await asyncio.wait_for(self.process.communicate(), timeout=5.0)

            logger.info("LSP server shut down gracefully")

        except Exception as e:
            logger.warning("LSP server shutdown error, killing", error=str(e))
            if self.process:
                self.process.kill()
                await self.process.wait()

        finally:
            self.process = None
            self.initialized = False
            self.pending_requests.clear()

            # Cancel reader task
            if self._reader_task and not self._reader_task.done():
                self._reader_task.cancel()
                try:
                    await self._reader_task
                except asyncio.CancelledError:
                    pass

            # EPIC-16: Cancel stderr drain task
            if self._stderr_task and not self._stderr_task.done():
                self._stderr_task.cancel()
                try:
                    await self._stderr_task
                except asyncio.CancelledError:
                    pass

    def is_alive(self) -> bool:
        """
        Check if LSP server process is alive.

        Returns:
            True if process is running, False otherwise
        """
        return (
            self.process is not None
            and self.process.returncode is None
        )
