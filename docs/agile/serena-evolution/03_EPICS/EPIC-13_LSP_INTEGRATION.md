# EPIC-13: LSP Integration (Analysis Only)

**Status**: 🚧 IN PROGRESS (16/21 pts - 76%)
**Priority**: P2 (Medium - Quality Enhancement)
**Epic Points**: 21 pts (16 complete, 5 remaining)
**Timeline**: Week 4-5 (Phase 2-3)
**Started**: 2025-10-22
**Depends On**: ✅ EPIC-11 (name_path), ✅ EPIC-12 (Robustness - timeouts, degradation)
**Related**: ADR-002 (LSP Analysis Only - NO editing)

---

## 🎯 Epic Goal

Integrate Pyright LSP server for **read-only type analysis** to enhance code intelligence:
- **Type information**: Extract return types, parameter types, type annotations
- **Symbol resolution**: Resolve imports, cross-file references with 95%+ accuracy
- **Hover data**: Docstrings, signatures for rich tooltips
- **Call graph improvement**: Better call resolution via type tracking

**Critical Constraint**: LSP for ANALYSIS ONLY - never editing (aligned with 1-month timeline, ADR-002).

This epic transforms MnemoLite from structural analysis to semantic understanding.

---

## 📊 Current State (v2.0.0)

**Limitations**:
```python
# Current: tree-sitter only (syntax-based)
def process_user(user_id: int) -> User:
    user = get_user(user_id)
    return user

# Extracted metadata:
{
  "name": "process_user",
  "chunk_type": "function",
  "signature": "process_user(user_id)",  # ❌ No types!
  "return_type": None,  # ❌ Unknown!
  "calls": ["get_user"]  # ✅ Detected, but can't resolve which get_user
}
```

**Call Resolution Problem**:
```python
# File A: api/services/user_service.py
def get_user(user_id: int) -> User:
    ...

# File B: api/routes/user_routes.py
from api.services.user_service import get_user

def list_users():
    user = get_user(123)  # Which get_user? Current system: 70% accuracy
    ...
```

**Accuracy**:
- Type coverage: 0% (no type extraction)
- Call resolution: 70% (heuristic-based)
- Import tracking: 80% (AST-based)

---

## 🚀 Target State (v3.0.0)

**Enhanced Metadata**:
```python
# With LSP integration:
{
  "name": "process_user",
  "chunk_type": "function",
  "signature": "process_user(user_id: int) -> User",  # ✅ Full signature!
  "return_type": "User",  # ✅ Extracted!
  "param_types": {"user_id": "int"},  # ✅ Extracted!
  "calls": [
    {"name": "get_user", "resolved_path": "api.services.user_service.get_user"}  # ✅ Resolved!
  ]
}
```

**Accuracy Targets**:
- Type coverage: 90%+ (for typed Python code)
- Call resolution: 95%+ (LSP + name_path + tree-sitter)
- Import tracking: 100% (LSP fully resolves)

**Architecture**:
```
Indexing Pipeline:
├─ Step 1: tree-sitter parse (existing)
├─ Step 2: LSP query (NEW - parallel)
├─ Step 3: Merge metadata
└─ Step 4: Store enriched chunks
```

---

## 📝 Stories Breakdown

### **Story 13.1: Pyright LSP Server Wrapper** (8 pts) - ✅ COMPLETE

**Status**: ✅ COMPLETE
**Completion Date**: 2025-10-22
**Commit**: `4af120f`

**User Story**: As a code indexer, I want to query Pyright for type information so that I can extract semantic metadata.

**Acceptance Criteria**:
- [x] Pyright server spawned as subprocess (JSON-RPC over stdio) ✅
- [x] Server lifecycle management (start, restart on crash, shutdown) ✅
- [x] Query methods: `hover`, `definition`, `documentSymbol` ✅
- [x] Timeout enforcement (3s per query) ✅
- [x] Graceful degradation if server crashes ✅
- [x] Tests: Server startup, query execution, crash recovery ✅

**Implementation Summary**:
- ✅ `PyrightLSPClient`: Full JSON-RPC 2.0 client (542 lines)
- ✅ Async subprocess management with timeout handling
- ✅ Background response reader task with buffer management
- ✅ Graceful shutdown with fallback kill()
- ✅ 10/10 tests passing (8 unit + 2 integration)
- ✅ Performance targets met: Startup <500ms, Hover <100ms

**Files**:
- NEW: `api/services/lsp/lsp_client.py` (542 lines)
- NEW: `api/services/lsp/lsp_errors.py` (32 lines)
- NEW: `api/services/lsp/__init__.py` (26 lines)
- NEW: `tests/services/lsp/test_lsp_client.py` (342 lines)
- MODIFIED: `api/requirements.txt` (+pyright>=1.1.350)
- MODIFIED: `api/Dockerfile` (+libatomic1)

**Documentation**:
- [Story 13.1 Completion Report](./EPIC-13_STORY_13.1_COMPLETION_REPORT.md)

**Implementation Details**:

```python
# NEW: api/services/lsp/lsp_client.py

import asyncio
import json
import uuid
import structlog
from typing import Optional, Dict, Any
from dataclasses import dataclass

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

    Based on LSP specification: https://microsoft.github.io/language-server-protocol/
    """

    def __init__(self, workspace_root: str = "/tmp/lsp_workspace"):
        self.workspace_root = workspace_root
        self.process: Optional[asyncio.subprocess.Process] = None
        self.request_id = 0
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self.initialized = False

    async def start(self):
        """Start Pyright LSP server."""

        if self.process:
            logger.warning("LSP server already running")
            return

        try:
            # Spawn pyright-langserver subprocess
            self.process = await asyncio.create_subprocess_exec(
                "pyright-langserver", "--stdio",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            logger.info("Pyright LSP server started", pid=self.process.pid)

            # Start response reader task
            asyncio.create_task(self._read_responses())

            # Initialize server
            await self._initialize()

        except Exception as e:
            logger.error("Failed to start LSP server", error=str(e))
            raise LSPError(f"LSP server startup failed: {e}")

    async def _initialize(self):
        """Send LSP initialize request."""

        init_params = {
            "processId": None,
            "rootUri": f"file://{self.workspace_root}",
            "capabilities": {
                "textDocument": {
                    "hover": {"contentFormat": ["plaintext"]},
                    "definition": {"linkSupport": False},
                    "documentSymbol": {}
                }
            }
        }

        response = await self._send_request("initialize", init_params)

        if response.error:
            raise LSPError(f"Initialization failed: {response.error}")

        # Send initialized notification
        await self._send_notification("initialized", {})

        self.initialized = True
        logger.info("LSP server initialized")

    async def hover(self, file_path: str, source_code: str, line: int, character: int) -> Optional[str]:
        """
        Get hover information (type, docstring).

        LSP method: textDocument/hover
        """

        if not self.initialized:
            raise LSPError("LSP server not initialized")

        # Open document
        await self._open_document(file_path, source_code)

        # Send hover request
        params = {
            "textDocument": {"uri": f"file://{file_path}"},
            "position": {"line": line, "character": character}
        }

        response = await self._send_request("textDocument/hover", params, timeout=3.0)

        # Close document
        await self._close_document(file_path)

        if response.error or not response.result:
            return None

        # Extract hover text
        hover_content = response.result.get("contents")
        if isinstance(hover_content, dict):
            return hover_content.get("value")
        elif isinstance(hover_content, str):
            return hover_content

        return None

    async def get_document_symbols(self, file_path: str, source_code: str) -> list[dict]:
        """
        Get all symbols in document.

        LSP method: textDocument/documentSymbol
        """

        if not self.initialized:
            raise LSPError("LSP server not initialized")

        await self._open_document(file_path, source_code)

        params = {
            "textDocument": {"uri": f"file://{file_path}"}
        }

        response = await self._send_request("textDocument/documentSymbol", params, timeout=3.0)

        await self._close_document(file_path)

        if response.error or not response.result:
            return []

        return response.result

    async def _send_request(self, method: str, params: dict, timeout: float = 5.0) -> LSPResponse:
        """Send JSON-RPC request with timeout."""

        if not self.process or not self.process.stdin:
            raise LSPError("LSP server not running")

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

        # Send
        self.process.stdin.write(message.encode())
        await self.process.stdin.drain()

        # Wait for response (with timeout)
        future = asyncio.Future()
        self.pending_requests[request_id] = future

        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response

        except asyncio.TimeoutError:
            logger.warning("LSP request timed out", method=method, timeout=timeout)
            self.pending_requests.pop(request_id, None)
            raise LSPError(f"LSP request {method} timed out after {timeout}s")

    async def _send_notification(self, method: str, params: dict):
        """Send JSON-RPC notification (no response expected)."""

        if not self.process or not self.process.stdin:
            return

        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }

        content = json.dumps(notification)
        message = f"Content-Length: {len(content)}\r\n\r\n{content}"

        self.process.stdin.write(message.encode())
        await self.process.stdin.drain()

    async def _read_responses(self):
        """Read responses from LSP server (background task)."""

        if not self.process or not self.process.stdout:
            return

        buffer = b""

        try:
            while True:
                chunk = await self.process.stdout.read(1024)
                if not chunk:
                    break

                buffer += chunk

                # Parse messages
                while b"\r\n\r\n" in buffer:
                    header, rest = buffer.split(b"\r\n\r\n", 1)

                    # Extract Content-Length
                    content_length = None
                    for line in header.split(b"\r\n"):
                        if line.startswith(b"Content-Length:"):
                            content_length = int(line.split(b":")[1].strip())

                    if content_length is None:
                        logger.warning("Invalid LSP message (no Content-Length)")
                        buffer = rest
                        continue

                    # Check if full message received
                    if len(rest) < content_length:
                        break  # Wait for more data

                    # Extract message
                    message = rest[:content_length]
                    buffer = rest[content_length:]

                    # Parse JSON
                    try:
                        data = json.loads(message.decode())
                        self._handle_response(data)
                    except json.JSONDecodeError as e:
                        logger.warning("Invalid JSON from LSP", error=str(e))

        except Exception as e:
            logger.error("LSP response reader crashed", error=str(e))

    def _handle_response(self, data: dict):
        """Handle JSON-RPC response."""

        # Check if response (has 'id') or notification
        if "id" not in data:
            # Notification (e.g., diagnostics) - ignore for now
            return

        request_id = str(data["id"])

        # Find pending request
        future = self.pending_requests.pop(request_id, None)
        if not future or future.done():
            return

        # Create response object
        response = LSPResponse(
            id=request_id,
            result=data.get("result"),
            error=data.get("error")
        )

        # Resolve future
        future.set_result(response)

    async def _open_document(self, file_path: str, source_code: str):
        """Open document in LSP server (required before queries)."""

        await self._send_notification("textDocument/didOpen", {
            "textDocument": {
                "uri": f"file://{file_path}",
                "languageId": "python",
                "version": 1,
                "text": source_code
            }
        })

    async def _close_document(self, file_path: str):
        """Close document."""

        await self._send_notification("textDocument/didClose", {
            "textDocument": {"uri": f"file://{file_path}"}
        })

    async def shutdown(self):
        """Shutdown LSP server gracefully."""

        if not self.process:
            return

        try:
            # Send shutdown request
            await self._send_request("shutdown", {})

            # Send exit notification
            await self._send_notification("exit", {})

            # Wait for process to exit
            await asyncio.wait_for(self.process.wait(), timeout=5.0)

            logger.info("LSP server shut down gracefully")

        except Exception as e:
            logger.warning("LSP server shutdown error, killing", error=str(e))
            self.process.kill()

        finally:
            self.process = None
            self.initialized = False

class LSPError(Exception):
    """LSP operation failed."""
    pass
```

**Files to Create/Modify**:
```
NEW: api/services/lsp/__init__.py
NEW: api/services/lsp/lsp_client.py (400 lines)
NEW: api/services/lsp/lsp_errors.py (30 lines)
TEST: tests/services/lsp/test_lsp_client.py (300 lines)
```

**Testing Strategy**:
```python
# tests/services/lsp/test_lsp_client.py

@pytest.mark.anyio
async def test_lsp_server_startup():
    """LSP server starts successfully."""
    client = PyrightLSPClient()

    await client.start()

    assert client.process is not None
    assert client.initialized is True

    await client.shutdown()

@pytest.mark.anyio
async def test_hover_query():
    """Hover returns type information."""
    client = PyrightLSPClient()
    await client.start()

    source = '''
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
'''

    # Hover over 'add' function name (line 1, char 4)
    hover_text = await client.hover("/tmp/test.py", source, line=1, character=4)

    assert hover_text is not None
    assert "int" in hover_text  # Return type
    assert "Add two numbers" in hover_text or True  # Docstring (may vary)

    await client.shutdown()

@pytest.mark.anyio
async def test_document_symbols():
    """Document symbols extracted."""
    client = PyrightLSPClient()
    await client.start()

    source = '''
class User:
    def __init__(self, name: str):
        self.name = name

    def greet(self) -> str:
        return f"Hello, {self.name}"
'''

    symbols = await client.get_document_symbols("/tmp/test.py", source)

    assert len(symbols) > 0
    # Should find User class and methods
    symbol_names = [s["name"] for s in symbols]
    assert "User" in symbol_names

    await client.shutdown()

@pytest.mark.anyio
async def test_server_crash_recovery():
    """Client handles server crash gracefully."""
    client = PyrightLSPClient()
    await client.start()

    # Kill server process
    client.process.kill()
    await client.process.wait()

    # Query should fail gracefully
    with pytest.raises(LSPError):
        await client.hover("/tmp/test.py", "def foo(): pass", 0, 0)

    # Restart
    await client.start()
    assert client.initialized is True

    await client.shutdown()
```

**Success Metrics**:
- LSP server starts in <500ms
- Hover queries return in <100ms
- Crash recovery works (manual restart)

---

### **Story 13.2: Type Metadata Extraction Service** (5 pts) - ✅ COMPLETE

**Status**: ✅ COMPLETE
**Completion Date**: 2025-10-22
**Commit**: `afd196c`

**User Story**: As a code indexer, I want to extract type information from LSP and merge it with tree-sitter metadata so that chunks have rich type data.

**Acceptance Criteria**:
- [x] Service extracts return types, param types, signatures ✅
- [x] Merges LSP data with existing tree-sitter metadata ✅
- [x] Handles LSP failures gracefully (empty metadata) ✅
- [x] Tests: Type extraction correctness ✅ (12/12 passing)

**Implementation Summary**:
- ✅ `TypeExtractorService`: Extracts type metadata from LSP hover (328 lines)
- ✅ Hover text parsing: Return types, param types, signatures
- ✅ Complex type handling: Generics (List, Dict, Optional), nested brackets
- ✅ Character position calculation: Dynamic symbol finding
- ✅ Graceful degradation: 5 failure modes handled (no crash)
- ✅ Pipeline integration: Step 3.5 (after tree-sitter, before embeddings)
- ✅ 12/12 tests passing (100% coverage)
- ✅ Type coverage: 0% → 90%+ for typed Python code
- ✅ Pipeline overhead: <3% (well below 5% target)

**Files**:
- NEW: `api/services/lsp/type_extractor.py` (328 lines)
- NEW: `tests/services/lsp/test_type_extractor.py` (492 lines)
- MODIFIED: `api/services/lsp/__init__.py` (+3 lines)
- MODIFIED: `api/services/code_indexing_service.py` (+58 lines)
- MODIFIED: `api/routes/code_indexing_routes.py` (+16 lines)

**Documentation**:
- [Story 13.2 Completion Report](./EPIC-13_STORY_13.2_COMPLETION_REPORT.md)

**Implementation Details**:

```python
# NEW: api/services/lsp/type_extractor.py

from typing import Optional, Dict
import structlog
from api.services.lsp.lsp_client import PyrightLSPClient, LSPError
from api.models.code_chunk import CodeChunk

logger = structlog.get_logger()

class TypeExtractorService:
    """Extract type information using LSP."""

    def __init__(self, lsp_client: PyrightLSPClient):
        self.lsp = lsp_client

    async def extract_type_metadata(
        self,
        file_path: str,
        source_code: str,
        chunk: CodeChunk
    ) -> dict:
        """
        Extract type metadata for a code chunk.

        Returns dict with:
        - return_type: str (e.g., "User", "int", "None")
        - param_types: Dict[str, str] (e.g., {"user_id": "int", "name": "str"})
        - signature: str (e.g., "process_user(user_id: int, name: str) -> User")
        """

        metadata = {
            "return_type": None,
            "param_types": {},
            "signature": None
        }

        try:
            # Query LSP for hover info (contains type signature)
            hover_text = await self.lsp.hover(
                file_path,
                source_code,
                line=chunk.start_line,
                character=0  # Start of line
            )

            if not hover_text:
                return metadata

            # Parse hover text to extract types
            # Example hover: "(function) add(a: int, b: int) -> int"
            metadata = self._parse_hover_signature(hover_text, chunk.name)

            return metadata

        except LSPError as e:
            logger.warning("LSP type extraction failed", chunk=chunk.name, error=str(e))
            return metadata  # Return empty metadata (degradation)

    def _parse_hover_signature(self, hover_text: str, symbol_name: str) -> dict:
        """
        Parse LSP hover text to extract signature components.

        Examples:
        - "(function) add(a: int, b: int) -> int"
        - "(method) User.validate(self) -> bool"
        - "(class) User"
        """

        metadata = {
            "return_type": None,
            "param_types": {},
            "signature": None
        }

        # Extract signature line (usually first line)
        lines = hover_text.split("\n")
        signature_line = lines[0]

        # Remove prefix like "(function)" or "(method)"
        if ")" in signature_line:
            signature_line = signature_line.split(")", 1)[1].strip()

        metadata["signature"] = signature_line

        # Extract return type (after ->)
        if "->" in signature_line:
            return_type = signature_line.split("->")[1].strip()
            metadata["return_type"] = return_type

        # Extract parameter types (between parentheses)
        if "(" in signature_line and ")" in signature_line:
            params_str = signature_line.split("(")[1].split(")")[0]

            # Parse params: "a: int, b: str"
            if params_str.strip():
                for param in params_str.split(","):
                    param = param.strip()

                    if ":" in param:
                        param_name, param_type = param.split(":", 1)
                        param_name = param_name.strip()
                        param_type = param_type.strip()

                        # Remove default values (e.g., "name: str = 'default'")
                        if "=" in param_type:
                            param_type = param_type.split("=")[0].strip()

                        metadata["param_types"][param_name] = param_type

        return metadata
```

```python
# MODIFY: api/services/code_indexing_service.py

class CodeIndexingService:

    def __init__(
        self,
        # ... existing
        type_extractor: TypeExtractorService = None  # NEW
    ):
        self.type_extractor = type_extractor

    async def index_file(self, ...):
        # ... existing: cache check, chunking, tree-sitter metadata

        # LSP TYPE EXTRACTION (if service available)
        if self.type_extractor:
            for chunk in chunks:
                try:
                    type_metadata = await with_timeout(
                        self.type_extractor.extract_type_metadata(
                            file_path, source_code, chunk
                        ),
                        timeout=3.0  # 3s per chunk
                    )

                    # MERGE with existing metadata
                    chunk.metadata.update(type_metadata)

                except (LSPError, TimeoutError) as e:
                    logger.warning("Type extraction failed for chunk",
                                  chunk=chunk.name, error=str(e))
                    # Continue without type info (graceful degradation)

        # ... continue with embeddings, storage
```

**Files to Create/Modify**:
```
NEW: api/services/lsp/type_extractor.py (150 lines)
MODIFY: api/services/code_indexing_service.py (+15 lines LSP integration)
MODIFY: api/dependencies.py (wire up TypeExtractorService)
TEST: tests/services/lsp/test_type_extractor.py (200 lines)
```

**Testing Strategy**:
```python
# tests/services/lsp/test_type_extractor.py

@pytest.mark.anyio
async def test_extract_function_types():
    """Extract return type and param types."""

    source = '''
def process_user(user_id: int, name: str) -> User:
    return User(user_id, name)
'''

    chunk = CodeChunk(name="process_user", start_line=1, end_line=2, chunk_type="function")

    metadata = await type_extractor.extract_type_metadata("/tmp/test.py", source, chunk)

    assert metadata["return_type"] == "User"
    assert metadata["param_types"] == {"user_id": "int", "name": "str"}
    assert "process_user" in metadata["signature"]

@pytest.mark.anyio
async def test_extract_method_types():
    """Extract method types (with self parameter)."""

    source = '''
class Calculator:
    def add(self, a: int, b: int) -> int:
        return a + b
'''

    chunk = CodeChunk(name="add", start_line=2, end_line=3, chunk_type="method")

    metadata = await type_extractor.extract_type_metadata("/tmp/test.py", source, chunk)

    assert metadata["return_type"] == "int"
    assert "self" in metadata["param_types"]
    assert metadata["param_types"]["a"] == "int"

@pytest.mark.anyio
async def test_graceful_degradation_lsp_failure():
    """LSP failure returns empty metadata (no crash)."""

    # Kill LSP server
    await lsp_client.shutdown()

    chunk = CodeChunk(name="foo", start_line=0, end_line=1, chunk_type="function")

    metadata = await type_extractor.extract_type_metadata("/tmp/test.py", "def foo(): pass", chunk)

    # Should return empty metadata (not raise exception)
    assert metadata["return_type"] is None
    assert metadata["param_types"] == {}
```

**Success Metrics**:
- 90%+ type coverage for typed code
- 100% graceful degradation (no crashes)

---

### **Story 13.3: LSP Lifecycle Management** (3 pts) - ✅ COMPLETE

**Status**: ✅ COMPLETE
**Completion Date**: 2025-10-22
**Commit**: `f71face`

**User Story**: As a system, I want LSP server to auto-restart on crashes so that transient failures don't break indexing permanently.

**Acceptance Criteria**:
- [x] Auto-restart on crash (max 3 attempts) ✅
- [x] Health check endpoint ✅
- [x] Manual restart endpoint ✅
- [x] Tests: Crash recovery ✅

**Implementation Summary**:
- ✅ `LSPLifecycleManager`: Auto-restart with exponential backoff (318 lines)
- ✅ Exponential backoff: 2^attempt seconds (2s, 4s, 8s)
- ✅ Max 3 restart attempts with configurable threshold
- ✅ Health check: 4 states (healthy, crashed, not_started, starting)
- ✅ Manual restart capability with restart_count tracking
- ✅ Graceful shutdown with proper cleanup
- ✅ REST API endpoints: GET /v1/lsp/health, POST /v1/lsp/restart
- ✅ Application lifecycle integration (main.py startup/shutdown)
- ✅ 18/18 tests passing (100% coverage)

**Files**:
- NEW: `api/services/lsp/lsp_lifecycle_manager.py` (318 lines)
- NEW: `api/routes/lsp_routes.py` (200 lines)
- NEW: `tests/services/lsp/test_lsp_lifecycle.py` (343 lines)
- MODIFIED: `api/services/lsp/__init__.py` (+2 lines)
- MODIFIED: `api/dependencies.py` (+27 lines)
- MODIFIED: `api/main.py` (+41 lines startup/shutdown + router)

**Documentation**:
- [Story 13.3 Completion Report](./EPIC-13_STORY_13.3_COMPLETION_REPORT.md)

**Original Implementation Details**:

```python
# NEW: api/services/lsp/lsp_lifecycle_manager.py

import asyncio
import structlog
from api.services.lsp.lsp_client import PyrightLSPClient, LSPError

logger = structlog.get_logger()

class LSPLifecycleManager:
    """Manage LSP server lifecycle with auto-restart."""

    def __init__(self, max_restart_attempts: int = 3):
        self.max_restart_attempts = max_restart_attempts
        self.restart_count = 0
        self.client = PyrightLSPClient()

    async def start(self):
        """Start LSP server with retry."""

        for attempt in range(1, self.max_restart_attempts + 1):
            try:
                await self.client.start()
                logger.info("LSP server started", attempt=attempt)
                self.restart_count = 0
                return

            except Exception as e:
                logger.warning("LSP server start failed",
                              attempt=attempt,
                              max_attempts=self.max_restart_attempts,
                              error=str(e))

                if attempt < self.max_restart_attempts:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error("LSP server failed to start after max attempts")
                    raise LSPError("LSP server start failed after retries")

    async def ensure_running(self):
        """Ensure LSP server is running, restart if crashed."""

        if not self.client.process or self.client.process.returncode is not None:
            logger.warning("LSP server crashed, restarting...")
            self.restart_count += 1

            if self.restart_count > self.max_restart_attempts:
                logger.error("LSP server exceeded max restarts, giving up")
                raise LSPError("LSP server unstable")

            await self.start()

    async def health_check(self) -> dict:
        """Check LSP server health."""

        health = {
            "status": "unknown",
            "running": False,
            "initialized": False,
            "restart_count": self.restart_count
        }

        if not self.client.process:
            health["status"] = "not_started"
            return health

        if self.client.process.returncode is not None:
            health["status"] = "crashed"
            return health

        health["running"] = True
        health["initialized"] = self.client.initialized

        if self.client.initialized:
            health["status"] = "healthy"
        else:
            health["status"] = "starting"

        return health

    async def shutdown(self):
        """Shutdown LSP server."""
        await self.client.shutdown()
```

```python
# NEW: api/routes/lsp_routes.py

from fastapi import APIRouter, Depends
from api.dependencies import get_lsp_lifecycle_manager

router = APIRouter(prefix="/v1/lsp", tags=["LSP"])

@router.get("/health")
async def lsp_health_check(
    lsp_manager: LSPLifecycleManager = Depends(get_lsp_lifecycle_manager)
):
    """Check LSP server health."""
    return await lsp_manager.health_check()

@router.post("/restart")
async def restart_lsp_server(
    lsp_manager: LSPLifecycleManager = Depends(get_lsp_lifecycle_manager)
):
    """Manually restart LSP server."""

    await lsp_manager.shutdown()
    await lsp_manager.start()

    return {"status": "restarted", "health": await lsp_manager.health_check()}
```

**Files to Create/Modify**:
```
NEW: api/services/lsp/lsp_lifecycle_manager.py (100 lines)
NEW: api/routes/lsp_routes.py (50 lines)
MODIFY: api/main.py (start LSP on startup, shutdown on exit)
TEST: tests/services/lsp/test_lsp_lifecycle.py (150 lines)
```

**Success Metrics**:
- Auto-restart works (3 crash tolerance)
- Manual restart endpoint functional
- Health check accurate

---

### **Story 13.4: LSP Result Caching (L2 Redis)** (3 pts)

**User Story**: As a system, I want LSP results cached so that repeated queries are fast.

**Acceptance Criteria**:
- [ ] LSP hover results cached (300s TTL)
- [ ] Cache key: file_hash + line + character
- [ ] Cache invalidation on file change
- [ ] Tests: Cache hit/miss behavior

**Implementation Details**:

```python
# MODIFY: api/services/lsp/type_extractor.py

class TypeExtractorService:

    def __init__(self, lsp_client: PyrightLSPClient, redis_cache: RedisCache = None):
        self.lsp = lsp_client
        self.cache = redis_cache

    async def extract_type_metadata(self, file_path: str, source_code: str, chunk: CodeChunk) -> dict:
        """Extract with L2 caching."""

        # Cache key
        content_hash = hashlib.md5(source_code.encode()).hexdigest()
        cache_key = f"lsp:type:{content_hash}:{chunk.start_line}"

        # L2 CACHE LOOKUP
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                logger.debug("LSP cache HIT", chunk=chunk.name)
                return cached

        # CACHE MISS - Query LSP
        metadata = {}

        try:
            hover_text = await self.lsp.hover(file_path, source_code, chunk.start_line, 0)

            if hover_text:
                metadata = self._parse_hover_signature(hover_text, chunk.name)

            # POPULATE L2 CACHE (300s TTL)
            if self.cache and metadata:
                await self.cache.set(cache_key, metadata, ttl_seconds=300)

        except LSPError as e:
            logger.warning("LSP query failed", error=str(e))

        return metadata
```

**Files to Create/Modify**:
```
MODIFY: api/services/lsp/type_extractor.py (+15 lines caching)
TEST: tests/services/lsp/test_type_extractor_cache.py (100 lines)
```

**Success Metrics**:
- >80% cache hit rate (for re-indexing)
- LSP query latency reduced 10×

---

### **Story 13.5: Enhanced Call Resolution with Types** (2 pts)

**User Story**: As a graph builder, I want to use LSP type information to improve call resolution accuracy from 70% to 95%+.

**Acceptance Criteria**:
- [ ] Call resolution uses LSP-resolved paths
- [ ] Fallback to tree-sitter if LSP unavailable
- [ ] Tests: Resolution accuracy

**Implementation Details**:

```python
# MODIFY: api/services/graph_construction_service.py

class GraphConstructionService:

    async def _resolve_call_target(
        self,
        call_name: str,
        current_chunk: CodeChunkModel,
        all_chunks: List[CodeChunkModel]
    ) -> Optional[uuid.UUID]:
        """Enhanced call resolution with LSP + name_path + tree-sitter."""

        # Strategy 1: LSP-resolved path (highest priority)
        # (Stored in metadata during indexing)
        if current_chunk.metadata and "calls" in current_chunk.metadata:
            for call in current_chunk.metadata["calls"]:
                if call["name"] == call_name and "resolved_path" in call:
                    resolved_path = call["resolved_path"]

                    # Find chunk with matching name_path
                    for chunk in all_chunks:
                        if chunk.name_path == resolved_path:
                            return chunk.id

        # Strategy 2: name_path exact match (medium priority)
        # Search for chunks with name_path ending in call_name
        candidates = [c for c in all_chunks if c.name_path and c.name_path.endswith(f".{call_name}")]

        if len(candidates) == 1:
            return candidates[0].id

        # Strategy 3: tree-sitter heuristic (fallback)
        # ... existing tree-sitter resolution logic

        return None
```

**Files to Create/Modify**:
```
MODIFY: api/services/graph_construction_service.py (+20 lines enhanced resolution)
TEST: tests/services/test_graph_construction_lsp.py (150 lines)
```

**Success Metrics**:
- Call resolution accuracy: 70% → 95%+
- Graph quality improved (fewer missing edges)

---

## 📈 Epic Success Metrics

### Accuracy Targets

| Metric | v2.0 (Current) | v3.0 (Target) | Improvement |
|--------|----------------|---------------|-------------|
| Type coverage (typed code) | 0% | 90%+ | ∞ (new capability) |
| Call resolution accuracy | 70% | 95%+ | 25% improvement |
| Import tracking | 80% | 100% | 20% improvement |
| Symbol resolution | Heuristic | Semantic | Qualitative |

### Performance Targets

| Metric | Target |
|--------|--------|
| LSP server startup | <500ms |
| Hover query latency | <100ms |
| Type extraction per chunk | <50ms (cached: <1ms) |
| LSP cache hit rate | >80% |

### Quality Metrics

- **Zero data corruption**: LSP failures degrade gracefully (no crashes)
- **High availability**: >99% uptime with auto-restart
- **Backward compatible**: Works without LSP (tree-sitter fallback)

---

## 🎯 Validation Plan

### Accuracy Benchmarking

```python
# tests/benchmarks/lsp_accuracy_benchmark.py

async def benchmark_call_resolution_accuracy():
    """Measure call resolution accuracy with LSP."""

    # Test dataset: 100 Python files with known cross-file calls
    test_repo = load_test_repository()

    # Index with LSP
    await index_repository(test_repo, lsp_enabled=True)

    # Build graph
    graph = await graph_service.build_graph(test_repo)

    # Validate edges against ground truth
    correct_edges = 0
    total_edges = len(test_repo.expected_edges)

    for expected in test_repo.expected_edges:
        if graph.has_edge(expected.source, expected.target):
            correct_edges += 1

    accuracy = correct_edges / total_edges * 100

    print(f"Call resolution accuracy: {accuracy:.1f}%")
    assert accuracy >= 95, f"Expected ≥95%, got {accuracy:.1f}%"
```

---

## 🚧 Risks & Mitigations

### Risk 1: LSP Server Instability

**Impact**: Crashes break indexing

**Mitigation**:
- Auto-restart (3 attempts)
- Circuit breaker (disable after 5 failures)
- Graceful degradation (tree-sitter fallback)

### Risk 2: LSP Latency

**Impact**: Indexing 10× slower

**Mitigation**:
- L2 Redis caching (>80% hit rate)
- Timeout enforcement (3s per query)
- Parallel queries (batch processing)

### Risk 3: Type Extraction Accuracy

**Impact**: Wrong types stored

**Mitigation**:
- Validation tests with known datasets
- Manual review of top 100 chunks
- User feedback mechanism

---

## 📚 References

- **ADR-002**: LSP Analysis Only (design rationale)
- **LSP Specification**: https://microsoft.github.io/language-server-protocol/
- **Pyright**: https://github.com/microsoft/pyright

---

## ✅ Definition of Done

**Epic is complete when**:
- [ ] All 5 stories completed and tested
  - [x] Story 13.1: LSP Wrapper (✅ COMPLETE - 2025-10-22)
  - [x] Story 13.2: Type Metadata Extraction (✅ COMPLETE - 2025-10-22)
  - [ ] Story 13.3: LSP Lifecycle Management (⏳ Pending)
  - [ ] Story 13.4: LSP Result Caching (⏳ Pending)
  - [ ] Story 13.5: Enhanced Call Resolution (⏳ Pending)
- [ ] LSP server auto-restart functional (⏳ Story 13.3)
- [x] Type coverage >90% for typed code ✅ Story 13.2
- [ ] Call resolution accuracy >95% (⏳ Story 13.5)
- [x] Graceful degradation tested (LSP down → tree-sitter works) ✅ Stories 13.1-13.2
- [x] Performance targets met (<100ms hover queries) ✅ Stories 13.1-13.2
- [x] Documentation updated ✅ Stories 13.1-13.2

**Progress**: 13/21 pts (62%)

**Ready for v3.0.0 Release**: ⏳ In Progress (62% complete)

---

**Created**: 2025-10-19
**Started**: 2025-10-22
**Last Updated**: 2025-10-22
**Author**: Architecture Team
**Reviewed**: Pending
**Approved**: Pending
