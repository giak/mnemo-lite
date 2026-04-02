# EPIC-16 Story 16.1 Analysis: TypeScript LSP Client

**Story ID**: EPIC-16 Story 16.1
**Story Points**: 8 pts
**Status**: 📝 **READY FOR IMPLEMENTATION**
**Depends On**: EPIC-15 (TypeScript parsers)
**Reference**: EPIC-13 Story 13.1 (Python LSP Client - similar pattern)
**Created**: 2025-10-23

---

## 🎯 User Story

**As a** code indexer
**I want** a TypeScript Language Server client
**So that** I can query type information from tsserver for accurate type extraction

---

## 📋 Acceptance Criteria

- [ ] **AC1**: Node.js + TypeScript installed in Docker image
- [ ] **AC2**: `TypeScriptLSPClient` class created with LSP protocol support
- [ ] **AC3**: LSP communication via JSON-RPC over stdio
- [ ] **AC4**: `start()` method launches tsserver subprocess
- [ ] **AC5**: `stop()` method stops tsserver gracefully
- [ ] **AC6**: `get_hover()` retrieves type info at position
- [ ] **AC7**: `get_definition()` retrieves definition location
- [ ] **AC8**: Circuit breaker pattern for error handling
- [ ] **AC9**: Unit tests: 10+ test cases covering all methods

---

## 🔍 Technical Analysis

### What is tsserver?

**TypeScript Language Server (tsserver)**:
- Official TypeScript compiler API from Microsoft
- Used by VS Code, WebStorm, Sublime Text, Neovim, etc.
- Provides type checking, auto-completion, go-to-definition, hover info
- Communicates via LSP (Language Server Protocol)
- Supports TypeScript + JavaScript (including JSX/TSX)

**Installation**:
```bash
npm install -g typescript typescript-language-server
```

**Size**: ~50 MB (Node.js + TypeScript)

**Why tsserver?**:
- ✅ Official TypeScript tooling (100% accurate type info)
- ✅ Battle-tested (millions of users via VS Code)
- ✅ Supports all TypeScript features (generics, decorators, etc.)
- ✅ LSP protocol (standardized communication)
- ✅ No configuration needed (works without tsconfig.json)

---

### LSP Protocol Overview

**Language Server Protocol (LSP)**:
- JSON-RPC 2.0 protocol
- Communication via stdin/stdout
- Request/response model
- Notifications (one-way messages)

**Lifecycle**:
1. Initialize: `initialize` request → server capabilities
2. Initialized: `initialized` notification
3. Operations: `textDocument/hover`, `textDocument/definition`, etc.
4. Shutdown: `shutdown` request → `exit` notification

**Example: textDocument/hover Request**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "textDocument/hover",
  "params": {
    "textDocument": {
      "uri": "file:///project/test.ts"
    },
    "position": {
      "line": 5,
      "character": 10
    }
  }
}
```

**Example: textDocument/hover Response**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "contents": {
      "kind": "markdown",
      "value": "```typescript\n(method) UserService.getUser(id: string): Promise<User>\n```"
    },
    "range": {
      "start": { "line": 5, "character": 10 },
      "end": { "line": 5, "character": 17 }
    }
  }
}
```

---

### Architecture Design

**Component: TypeScriptLSPClient**

```
┌─────────────────────────────────────────┐
│      TypeScriptLSPClient                │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ Lifecycle Management              │ │
│  │ - start() → launch tsserver       │ │
│  │ - stop() → graceful shutdown      │ │
│  │ - _initialize() → LSP handshake   │ │
│  └───────────────────────────────────┘ │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ LSP Operations                    │ │
│  │ - get_hover() → type info         │ │
│  │ - get_definition() → location     │ │
│  │ - _send_request() → JSON-RPC      │ │
│  │ - _read_response() → parse result │ │
│  └───────────────────────────────────┘ │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ Circuit Breaker (EPIC-12)         │ │
│  │ - threshold: 3 failures           │ │
│  │ - timeout: 60s recovery           │ │
│  │ - state: CLOSED → OPEN → HALF_OPEN│ │
│  └───────────────────────────────────┘ │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ Subprocess (tsserver)             │ │
│  │ - stdin: send requests            │ │
│  │ - stdout: receive responses       │ │
│  │ - stderr: capture errors          │ │
│  └───────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

**Flow**:
1. `start()` → Launch `typescript-language-server --stdio`
2. `_initialize()` → Send `initialize` request
3. LSP ready → Store process handle
4. `get_hover(file, line, char)` → Send `textDocument/hover`
5. Parse response → Extract type info
6. Circuit breaker → Protect from failures
7. `stop()` → Send `shutdown` + `exit`

---

## 💻 Code Skeleton

### File: `api/services/typescript_lsp_client.py`

```python
"""TypeScript Language Server client for type extraction."""

import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

from api.interfaces.services import CircuitBreakerProtocol


class TypeScriptLSPClient:
    """Client for communicating with TypeScript Language Server (tsserver).

    Based on LSP (Language Server Protocol) JSON-RPC 2.0.
    Reference: EPIC-13 Story 13.1 (PyrightLSPClient)
    """

    def __init__(
        self,
        circuit_breaker: CircuitBreakerProtocol,
        workspace_dir: Optional[Path] = None,
        timeout: float = 5.0
    ):
        """Initialize TypeScript LSP client.

        Args:
            circuit_breaker: Circuit breaker for error handling
            workspace_dir: Optional workspace directory (defaults to /tmp/ts-workspace)
            timeout: Request timeout in seconds (default: 5s)
        """
        self.logger = logging.getLogger(__name__)
        self.circuit_breaker = circuit_breaker
        self.workspace_dir = workspace_dir or Path("/tmp/ts-workspace")
        self.timeout = timeout

        self._process: Optional[subprocess.Popen] = None
        self._request_id = 0
        self._initialized = False

    async def start(self) -> None:
        """Launch tsserver subprocess and initialize LSP session.

        Raises:
            RuntimeError: If tsserver fails to start
        """
        if self._process is not None:
            self.logger.warning("TypeScript LSP already running")
            return

        try:
            # Ensure workspace exists
            self.workspace_dir.mkdir(parents=True, exist_ok=True)

            # Launch typescript-language-server
            self.logger.info(f"Starting TypeScript LSP in {self.workspace_dir}")
            self._process = subprocess.Popen(
                ["typescript-language-server", "--stdio"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.workspace_dir),
                text=False  # Binary mode for proper buffering
            )

            # Initialize LSP session
            await self._initialize()
            self._initialized = True

            self.logger.info("TypeScript LSP started successfully")

        except Exception as e:
            self.logger.error(f"Failed to start TypeScript LSP: {e}")
            await self.stop()
            raise RuntimeError(f"TypeScript LSP startup failed: {e}")

    async def stop(self) -> None:
        """Stop tsserver gracefully using LSP shutdown protocol."""
        if self._process is None:
            return

        try:
            if self._initialized:
                # Send LSP shutdown request
                await self._send_notification("shutdown")
                await self._send_notification("exit")

                # Wait for graceful shutdown (max 2s)
                try:
                    self._process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    self.logger.warning("TypeScript LSP did not shut down gracefully, terminating")
                    self._process.terminate()
                    self._process.wait(timeout=1.0)

            else:
                # Force termination if not initialized
                self._process.terminate()
                self._process.wait(timeout=1.0)

        except Exception as e:
            self.logger.error(f"Error stopping TypeScript LSP: {e}")

        finally:
            self._process = None
            self._initialized = False
            self.logger.info("TypeScript LSP stopped")

    async def get_hover(
        self,
        file_path: Path,
        line: int,
        character: int
    ) -> Optional[Dict[str, Any]]:
        """Get hover information (type info) at a specific position.

        Args:
            file_path: Absolute path to TypeScript file
            line: Line number (0-indexed)
            character: Character position (0-indexed)

        Returns:
            Dictionary with hover info:
            {
                "contents": "async getUser(id: string): Promise<User>",
                "range": {"start": {...}, "end": {...}}
            }

        Raises:
            RuntimeError: If LSP not initialized or request fails
        """
        if not self._initialized:
            raise RuntimeError("TypeScript LSP not initialized")

        # Use circuit breaker to protect from failures
        async def _execute():
            return await self._send_request(
                method="textDocument/hover",
                params={
                    "textDocument": {
                        "uri": f"file://{file_path}"
                    },
                    "position": {
                        "line": line,
                        "character": character
                    }
                }
            )

        try:
            result = await self.circuit_breaker.execute(_execute)

            # Parse hover response
            if result and "contents" in result:
                return self._parse_hover_response(result)

            return None

        except Exception as e:
            self.logger.error(f"get_hover failed: {e}")
            return None

    async def get_definition(
        self,
        file_path: Path,
        line: int,
        character: int
    ) -> Optional[Dict[str, Any]]:
        """Get definition location for a symbol.

        Args:
            file_path: Absolute path to TypeScript file
            line: Line number (0-indexed)
            character: Character position (0-indexed)

        Returns:
            Dictionary with definition location:
            {
                "uri": "file:///project/types.ts",
                "range": {"start": {"line": 1, "character": 0}, ...}
            }

        Raises:
            RuntimeError: If LSP not initialized or request fails
        """
        if not self._initialized:
            raise RuntimeError("TypeScript LSP not initialized")

        async def _execute():
            return await self._send_request(
                method="textDocument/definition",
                params={
                    "textDocument": {
                        "uri": f"file://{file_path}"
                    },
                    "position": {
                        "line": line,
                        "character": character
                    }
                }
            )

        try:
            result = await self.circuit_breaker.execute(_execute)

            # Parse definition response (may be array or single location)
            if result:
                if isinstance(result, list) and len(result) > 0:
                    return result[0]  # Return first definition
                elif isinstance(result, dict):
                    return result

            return None

        except Exception as e:
            self.logger.error(f"get_definition failed: {e}")
            return None

    # -------------------------------------------------------------------------
    # Private Methods
    # -------------------------------------------------------------------------

    async def _initialize(self) -> None:
        """Send LSP initialize request and wait for response."""
        response = await self._send_request(
            method="initialize",
            params={
                "processId": None,
                "rootUri": f"file://{self.workspace_dir}",
                "capabilities": {
                    "textDocument": {
                        "hover": {"contentFormat": ["markdown", "plaintext"]},
                        "definition": {"linkSupport": False}
                    }
                }
            }
        )

        if not response or "capabilities" not in response:
            raise RuntimeError("LSP initialize failed: no server capabilities")

        # Send initialized notification
        await self._send_notification("initialized", params={})

        self.logger.info(f"LSP initialized with capabilities: {response['capabilities']}")

    async def _send_request(
        self,
        method: str,
        params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Send LSP request and wait for response.

        Args:
            method: LSP method name (e.g., "textDocument/hover")
            params: Request parameters

        Returns:
            Response result or None

        Raises:
            TimeoutError: If request times out
            RuntimeError: If LSP process crashed
        """
        if self._process is None:
            raise RuntimeError("TypeScript LSP not running")

        self._request_id += 1
        request_id = self._request_id

        # Build JSON-RPC request
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }

        # Send request
        self._send_message(request)

        # Read response (with timeout)
        try:
            response = await asyncio.wait_for(
                self._read_response(request_id),
                timeout=self.timeout
            )

            # Check for LSP errors
            if "error" in response:
                error = response["error"]
                self.logger.error(f"LSP error: {error}")
                return None

            return response.get("result")

        except asyncio.TimeoutError:
            self.logger.error(f"LSP request timeout after {self.timeout}s")
            raise TimeoutError(f"LSP request {method} timed out")

    async def _send_notification(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send LSP notification (no response expected).

        Args:
            method: LSP method name (e.g., "initialized")
            params: Optional notification parameters
        """
        notification = {
            "jsonrpc": "2.0",
            "method": method
        }

        if params is not None:
            notification["params"] = params

        self._send_message(notification)

    def _send_message(self, message: Dict[str, Any]) -> None:
        """Send JSON-RPC message to tsserver via stdin.

        LSP uses Content-Length header format:
        Content-Length: 123\r\n\r\n
        {"jsonrpc":"2.0",...}
        """
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("TypeScript LSP not running")

        # Serialize message
        content = json.dumps(message, ensure_ascii=False)
        content_bytes = content.encode("utf-8")

        # Build LSP message with Content-Length header
        header = f"Content-Length: {len(content_bytes)}\r\n\r\n"
        header_bytes = header.encode("ascii")

        # Write to stdin
        self._process.stdin.write(header_bytes + content_bytes)
        self._process.stdin.flush()

    async def _read_response(self, request_id: int) -> Dict[str, Any]:
        """Read JSON-RPC response from tsserver stdout.

        Args:
            request_id: Expected request ID

        Returns:
            Response dictionary

        Raises:
            RuntimeError: If response parsing fails
        """
        if self._process is None or self._process.stdout is None:
            raise RuntimeError("TypeScript LSP not running")

        while True:
            # Read Content-Length header
            header_line = await self._read_line()

            if not header_line.startswith("Content-Length:"):
                continue  # Skip unknown headers

            # Parse content length
            content_length = int(header_line.split(":")[1].strip())

            # Read empty line separator
            await self._read_line()

            # Read message content
            content_bytes = self._process.stdout.read(content_length)
            content = content_bytes.decode("utf-8")

            # Parse JSON
            message = json.loads(content)

            # Check if this is our response
            if message.get("id") == request_id:
                return message

            # Otherwise, skip (could be notification or other response)
            self.logger.debug(f"Skipping LSP message: {message}")

    async def _read_line(self) -> str:
        """Read a single line from tsserver stdout.

        Returns:
            Line content (without newline)
        """
        if self._process is None or self._process.stdout is None:
            raise RuntimeError("TypeScript LSP not running")

        line_bytes = b""
        while True:
            char = self._process.stdout.read(1)
            if char == b"\n":
                break
            line_bytes += char

        return line_bytes.decode("ascii").strip()

    def _parse_hover_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Parse LSP hover response into structured format.

        Args:
            result: Raw LSP hover result

        Returns:
            Parsed hover info:
            {
                "contents": "async getUser(id: string): Promise<User>",
                "range": {...}
            }
        """
        contents = result.get("contents", {})

        # Extract markdown content
        if isinstance(contents, dict):
            value = contents.get("value", "")
        elif isinstance(contents, str):
            value = contents
        else:
            value = str(contents)

        # Clean up markdown code blocks
        if "```typescript" in value:
            # Extract code between ```typescript and ```
            parts = value.split("```typescript")
            if len(parts) > 1:
                code_part = parts[1].split("```")[0].strip()
                value = code_part

        return {
            "contents": value,
            "range": result.get("range")
        }


# Circuit Breaker Configuration
TYPESCRIPT_LSP_CIRCUIT_BREAKER_CONFIG = {
    "failure_threshold": 3,
    "recovery_timeout": 60.0,
    "expected_exception": Exception
}
```

**Estimated Size**: ~250 lines

---

## 🐳 Docker Configuration

### Dockerfile Changes

**File**: `db/Dockerfile` or `api/Dockerfile` (TBD based on architecture)

```dockerfile
# Install Node.js + TypeScript
RUN apt-get update && apt-get install -y \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install TypeScript Language Server
RUN npm install -g typescript typescript-language-server

# Verify installation
RUN typescript-language-server --version && \
    tsc --version
```

**Alternative: Multi-stage build** (recommended for smaller image size):

```dockerfile
# Stage 1: Node.js tools
FROM node:20-slim AS typescript-tools
RUN npm install -g typescript typescript-language-server

# Stage 2: MnemoLite API
FROM python:3.11-slim
COPY --from=typescript-tools /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=typescript-tools /usr/local/bin/typescript-language-server /usr/local/bin/
COPY --from=typescript-tools /usr/local/bin/tsc /usr/local/bin/
```

**Size Impact**: +80 MB (Node.js + TypeScript)

---

## 🧪 Testing Strategy

### Unit Tests

**File**: `tests/services/test_typescript_lsp_client.py`

**Test Cases** (10+ tests):

1. **test_start_success**: Verify LSP starts and initializes
2. **test_start_already_running**: Handle duplicate start calls
3. **test_stop_graceful**: Verify graceful shutdown
4. **test_stop_force**: Verify forced termination if shutdown fails
5. **test_get_hover_success**: Extract type info from hover
6. **test_get_hover_not_initialized**: Raise error if not started
7. **test_get_hover_timeout**: Handle request timeout
8. **test_get_definition_success**: Get symbol definition location
9. **test_circuit_breaker_open**: Verify circuit breaker protection
10. **test_parse_hover_response_markdown**: Parse markdown hover content
11. **test_parse_hover_response_plain**: Parse plain text hover content
12. **test_request_id_increment**: Verify unique request IDs

**Example Test**:

```python
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from api.services.typescript_lsp_client import TypeScriptLSPClient


@pytest.mark.asyncio
async def test_get_hover_success():
    """Test successful hover request."""
    # Arrange
    circuit_breaker = Mock()
    circuit_breaker.execute = AsyncMock(return_value={
        "contents": {
            "kind": "markdown",
            "value": "```typescript\nfunction getUser(id: string): Promise<User>\n```"
        }
    })

    client = TypeScriptLSPClient(circuit_breaker=circuit_breaker)
    client._initialized = True  # Mock initialization

    # Act
    result = await client.get_hover(
        file_path=Path("/tmp/test.ts"),
        line=5,
        character=10
    )

    # Assert
    assert result is not None
    assert "contents" in result
    assert "function getUser" in result["contents"]


@pytest.mark.asyncio
async def test_circuit_breaker_protection():
    """Test circuit breaker protects from repeated failures."""
    # Arrange
    circuit_breaker = Mock()
    circuit_breaker.execute = AsyncMock(side_effect=Exception("LSP error"))

    client = TypeScriptLSPClient(circuit_breaker=circuit_breaker)
    client._initialized = True

    # Act
    result = await client.get_hover(
        file_path=Path("/tmp/test.ts"),
        line=5,
        character=10
    )

    # Assert
    assert result is None  # Graceful degradation
    circuit_breaker.execute.assert_called_once()
```

**Coverage Target**: >90% for TypeScriptLSPClient

---

## 🔗 Integration Points

### 1. Circuit Breaker (EPIC-12)

**Reference**: `api/services/circuit_breaker.py`

**Usage**:
```python
# In dependencies.py
from api.services.circuit_breaker import CircuitBreaker

def get_typescript_lsp_circuit_breaker() -> CircuitBreaker:
    return CircuitBreaker(
        failure_threshold=3,
        recovery_timeout=60.0,
        expected_exception=Exception
    )

def get_typescript_lsp_client(
    circuit_breaker: CircuitBreaker = Depends(get_typescript_lsp_circuit_breaker)
) -> TypeScriptLSPClient:
    return TypeScriptLSPClient(circuit_breaker=circuit_breaker)
```

---

### 2. Lifecycle Management (main.py)

**Startup**:
```python
# In main.py lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing startup code ...

    # Start TypeScript LSP
    typescript_lsp = get_typescript_lsp_client()
    await typescript_lsp.start()
    app.state.typescript_lsp = typescript_lsp

    yield

    # Shutdown TypeScript LSP
    await typescript_lsp.stop()
```

---

### 3. TypeExtractorService (Story 16.2)

**Usage**:
```python
# In TypeExtractorService
async def extract_typescript_types(
    self,
    file_path: Path,
    chunk: CodeChunk
) -> Dict[str, Any]:
    """Extract TypeScript types using LSP."""

    # Get hover info for function signature
    hover = await self.typescript_lsp.get_hover(
        file_path=file_path,
        line=chunk.start_line,
        character=0
    )

    if hover:
        return self._parse_hover_to_metadata(hover)

    return {}  # Fallback to heuristic
```

---

## 📊 Performance Expectations

### Latency

| Operation | Target | Expected |
|-----------|--------|----------|
| LSP startup | <2s | ~1.5s |
| LSP shutdown | <2s | ~0.5s |
| get_hover() | <500ms | ~200ms |
| get_definition() | <500ms | ~150ms |
| Timeout protection | 5s | Configurable |

### Resource Usage

| Resource | Expected |
|----------|----------|
| Memory | +50 MB (tsserver process) |
| CPU | <5% idle, <20% during requests |
| Disk | +80 MB (Node.js + TypeScript) |

---

## 🚦 Error Handling

### 1. Startup Failures

**Scenario**: Node.js or TypeScript not installed

**Handling**:
```python
try:
    await typescript_lsp.start()
except RuntimeError as e:
    logger.error(f"TypeScript LSP startup failed: {e}")
    logger.warning("Falling back to heuristic type extraction")
    # Continue without LSP (graceful degradation)
```

### 2. Request Timeouts

**Scenario**: LSP request takes >5s

**Handling**: Circuit breaker catches TimeoutError → open circuit → fallback to heuristic

### 3. LSP Crashes

**Scenario**: tsserver subprocess crashes

**Handling**: Circuit breaker detects failures → open circuit → fallback to heuristic

---

## 📝 Implementation Checklist

- [ ] Create `api/services/typescript_lsp_client.py`
- [ ] Implement `TypeScriptLSPClient` class
- [ ] Implement LSP lifecycle (start, stop, initialize)
- [ ] Implement `get_hover()` method
- [ ] Implement `get_definition()` method
- [ ] Implement JSON-RPC communication (stdin/stdout)
- [ ] Integrate circuit breaker (EPIC-12)
- [ ] Update Docker configuration (Node.js + TypeScript)
- [ ] Create unit tests (10+ test cases)
- [ ] Update `dependencies.py` with DI
- [ ] Update `main.py` lifespan for LSP startup/shutdown
- [ ] Test with real TypeScript file
- [ ] Document configuration options

---

## 🔍 References

### LSP Specification
- [Language Server Protocol](https://microsoft.github.io/language-server-protocol/)
- [TypeScript Language Server](https://github.com/typescript-language-server/typescript-language-server)
- [LSP JSON-RPC](https://www.jsonrpc.org/specification)

### MnemoLite References
- [EPIC-13 Story 13.1: Python LSP Client](EPIC-13_STORY_13.1_COMPLETION_REPORT.md) - Similar implementation
- [EPIC-12: Circuit Breaker](../../EPIC-12_CIRCUIT_BREAKER.md) - Error handling pattern
- [EPIC-15: TypeScript Parsers](EPIC-15_TYPESCRIPT_JAVASCRIPT_SUPPORT.md) - AST parsing foundation

---

## 🎯 Success Criteria

**Story 16.1 is complete when**:

1. ✅ TypeScriptLSPClient class implemented (~250 lines)
2. ✅ All LSP methods working (start, stop, get_hover, get_definition)
3. ✅ Circuit breaker integrated (EPIC-12)
4. ✅ Docker image includes Node.js + TypeScript
5. ✅ Unit tests passing (10+ test cases, >90% coverage)
6. ✅ Manual testing with real TypeScript file successful
7. ✅ No regressions in existing functionality
8. ✅ Code follows MnemoLite patterns (DIP, async-first, EXTEND>REBUILD)

---

**Last Updated**: 2025-10-23
**Status**: 📝 **READY FOR IMPLEMENTATION** (8 pts)
**Next Story**: [EPIC-16 Story 16.2: TypeExtractorService Extension](EPIC-16_STORY_16.2_ANALYSIS.md)
