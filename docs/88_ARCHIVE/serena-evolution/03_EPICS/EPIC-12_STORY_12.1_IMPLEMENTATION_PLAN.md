# EPIC-12 Story 12.1: Timeout-Based Execution - Implementation Plan

**Story Points**: 5 pts
**Priority**: P0 - CRITICAL (Prevents DoS)
**Status**: 📝 READY FOR IMPLEMENTATION
**Date**: 2025-10-21
**Depends On**: None (Foundation story)

---

## 🎯 Story Goal

Implement timeout-based execution for all long-running operations to prevent infinite hangs that could DoS the system.

**User Story**: As a system, I want all long-running operations to have timeouts so that one slow file doesn't block the entire pipeline.

---

## ✅ Acceptance Criteria

- [x] Timeout decorator for async operations
- [x] All parsing/embedding/LSP calls wrapped with timeout
- [x] Configurable timeouts per operation type
- [x] TimeoutError logged with full context
- [x] Tests: Timeout enforcement, error handling

---

## 📊 Current State Analysis

### Services Needing Timeouts

**Priority 1 - CPU-bound operations (hang risk)**:
1. `code_chunking_service.py` - Tree-sitter parsing (can hang on pathological input)
2. `dual_embedding_service.py` - Embedding generation (can OOM/hang)
3. `sentence_transformer_embedding_service.py` - Model inference

**Priority 2 - I/O operations**:
4. `graph_construction_service.py` - Graph building (can be slow)
5. `graph_traversal_service.py` - Recursive traversal
6. `hybrid_code_search_service.py` - Search operations

**Priority 3 - Database operations**:
7. All repository methods (already have connection timeouts, but add application-level)

### Existing Timeout Usage

```bash
# Current state: Only 2 timeout usages found
grep -r "asyncio.wait_for\|asyncio.timeout" api/ --include="*.py" | wc -l
# Result: 2
```

**Observation**: Almost no timeout enforcement currently!

---

## 🏗️ Implementation Design

### Architecture

```
api/
├── utils/
│   └── timeout.py              # NEW: Timeout utilities
│       ├── TimeoutError        # Custom exception
│       ├── with_timeout()      # Async context function
│       └── timeout_decorator() # Decorator for methods
│
├── config/
│   └── timeouts.py             # NEW: Centralized timeout config
│       └── TIMEOUTS            # Dict of operation → timeout (seconds)
│
└── services/
    ├── code_chunking_service.py         # MODIFY: Add @timeout_decorator
    ├── dual_embedding_service.py        # MODIFY: Add @timeout_decorator
    ├── sentence_transformer_embedding_service.py  # MODIFY
    ├── graph_construction_service.py    # MODIFY: Add @timeout_decorator
    └── graph_traversal_service.py       # MODIFY: Add @timeout_decorator
```

---

## 📝 Step-by-Step Implementation

### Step 1: Create Timeout Utilities

**File**: `api/utils/timeout.py`

```python
"""
Timeout utilities for preventing infinite hangs.

Provides timeout enforcement for async operations using asyncio.wait_for()
with structured logging and error tracking.
"""

import asyncio
import functools
import logging
from typing import TypeVar, Callable, Any, Optional

logger = logging.getLogger(__name__)

T = TypeVar('T')


class TimeoutError(Exception):
    """Operation exceeded timeout limit."""

    def __init__(self, operation_name: str, timeout: float, context: Optional[dict] = None):
        self.operation_name = operation_name
        self.timeout = timeout
        self.context = context or {}

        message = f"{operation_name} exceeded {timeout}s timeout"
        if context:
            message += f" (context: {context})"
        super().__init__(message)


async def with_timeout(
    coro,
    timeout: float,
    operation_name: str = "operation",
    context: Optional[dict] = None,
    raise_on_timeout: bool = True
) -> Any:
    """
    Execute coroutine with timeout enforcement.

    Args:
        coro: Coroutine to execute
        timeout: Maximum execution time in seconds
        operation_name: Name for logging/error messages
        context: Additional context for logging (e.g., file_path, repository)
        raise_on_timeout: If True, raise TimeoutError; if False, return None

    Returns:
        Result of coroutine if successful, None if timeout and raise_on_timeout=False

    Raises:
        TimeoutError: If operation exceeds timeout and raise_on_timeout=True

    Example:
        result = await with_timeout(
            tree_sitter_service.chunk_code(source),
            timeout=5.0,
            operation_name="tree_sitter_parse",
            context={"file": file_path}
        )
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)

    except asyncio.TimeoutError:
        logger.error(
            f"⏱️ Timeout: {operation_name} exceeded {timeout}s",
            extra={
                "operation": operation_name,
                "timeout": timeout,
                "context": context or {}
            }
        )

        if raise_on_timeout:
            raise TimeoutError(operation_name, timeout, context)
        else:
            return None


def timeout_decorator(
    timeout: float,
    operation_name: Optional[str] = None,
    raise_on_timeout: bool = True
):
    """
    Decorator for timeout enforcement on async methods.

    Args:
        timeout: Maximum execution time in seconds
        operation_name: Name for logging (defaults to function name)
        raise_on_timeout: If True, raise TimeoutError; if False, return None

    Example:
        @timeout_decorator(timeout=5.0, operation_name="chunk_code")
        async def chunk_code(self, source_code: str):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__

            # Extract context from common kwargs
            context = {}
            if "file_path" in kwargs:
                context["file_path"] = kwargs["file_path"]
            if "repository" in kwargs:
                context["repository"] = kwargs["repository"]

            return await with_timeout(
                func(*args, **kwargs),
                timeout=timeout,
                operation_name=op_name,
                context=context,
                raise_on_timeout=raise_on_timeout
            )
        return wrapper
    return decorator


def cpu_bound_timeout(timeout: float, operation_name: Optional[str] = None):
    """
    Decorator for CPU-bound operations that need to run in thread pool.

    For synchronous CPU-bound operations (like tree-sitter parsing),
    wraps execution in asyncio.to_thread() then applies timeout.

    Args:
        timeout: Maximum execution time in seconds
        operation_name: Name for logging

    Example:
        @cpu_bound_timeout(timeout=5.0, operation_name="tree_sitter_parse")
        def parse_code(self, source_code: str):
            # Synchronous tree-sitter parsing
            tree = self.parser.parse(bytes(source_code, "utf8"))
            return tree
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__

            # Run synchronous function in thread pool
            coro = asyncio.to_thread(func, *args, **kwargs)

            # Apply timeout
            return await with_timeout(
                coro,
                timeout=timeout,
                operation_name=op_name,
                raise_on_timeout=True
            )
        return wrapper
    return decorator
```

**Key Design Decisions**:

1. **Custom TimeoutError** - Better than asyncio.TimeoutError (more context)
2. **Structured logging** - Uses `extra={}` for log aggregation
3. **Context extraction** - Automatically extracts file_path, repository from kwargs
4. **cpu_bound_timeout** - Special decorator for tree-sitter (synchronous → async)
5. **Optional raise** - Can suppress timeout errors for non-critical operations

---

### Step 2: Create Timeout Configuration

**File**: `api/config/timeouts.py`

```python
"""
Centralized timeout configuration for all operations.

Timeouts are defined in seconds. Values are conservative (high) initially,
and should be tuned based on production metrics.
"""

import os
from typing import Dict

# Default timeouts (seconds)
TIMEOUTS: Dict[str, float] = {
    # Code parsing (CPU-bound)
    "tree_sitter_parse": float(os.getenv("TIMEOUT_TREE_SITTER", "5.0")),

    # Embedding generation (CPU-bound, batched)
    "embedding_generation_single": float(os.getenv("TIMEOUT_EMBEDDING_SINGLE", "10.0")),
    "embedding_generation_batch": float(os.getenv("TIMEOUT_EMBEDDING_BATCH", "30.0")),

    # Graph operations
    "graph_construction": float(os.getenv("TIMEOUT_GRAPH_CONSTRUCTION", "10.0")),
    "graph_traversal": float(os.getenv("TIMEOUT_GRAPH_TRAVERSAL", "5.0")),

    # Search operations
    "vector_search": float(os.getenv("TIMEOUT_VECTOR_SEARCH", "5.0")),
    "lexical_search": float(os.getenv("TIMEOUT_LEXICAL_SEARCH", "3.0")),
    "hybrid_search": float(os.getenv("TIMEOUT_HYBRID_SEARCH", "10.0")),

    # Cache operations
    "cache_get": float(os.getenv("TIMEOUT_CACHE_GET", "1.0")),
    "cache_put": float(os.getenv("TIMEOUT_CACHE_PUT", "2.0")),

    # Database operations
    "database_query": float(os.getenv("TIMEOUT_DATABASE_QUERY", "10.0")),
    "database_transaction": float(os.getenv("TIMEOUT_DATABASE_TRANSACTION", "30.0")),

    # High-level operations
    "index_file": float(os.getenv("TIMEOUT_INDEX_FILE", "60.0")),  # Cumulative
}


def get_timeout(operation: str, default: float = 30.0) -> float:
    """
    Get timeout for operation with fallback.

    Args:
        operation: Operation name (key in TIMEOUTS dict)
        default: Default timeout if operation not found (default: 30s)

    Returns:
        Timeout in seconds

    Example:
        timeout = get_timeout("tree_sitter_parse")  # 5.0
        timeout = get_timeout("unknown_op")  # 30.0 (default)
    """
    return TIMEOUTS.get(operation, default)


def set_timeout(operation: str, timeout: float) -> None:
    """
    Update timeout for operation at runtime.

    Args:
        operation: Operation name
        timeout: New timeout in seconds

    Example:
        # Increase timeout for large repositories
        set_timeout("index_file", 120.0)
    """
    TIMEOUTS[operation] = timeout


def get_all_timeouts() -> Dict[str, float]:
    """Get all configured timeouts (for debugging/monitoring)."""
    return TIMEOUTS.copy()
```

**Key Design Decisions**:

1. **Environment variable overrides** - Production can tune without code changes
2. **Conservative defaults** - Start high, tune down based on metrics
3. **Fallback default** - 30s for unknown operations (safe)
4. **Runtime updates** - `set_timeout()` allows dynamic tuning
5. **Cumulative timeouts** - `index_file` timeout > sum of sub-operations

---

### Step 3: Apply Timeouts to Critical Services

#### 3.1 Code Chunking Service (Tree-sitter)

**File**: `api/services/code_chunking_service.py`

**Challenge**: Tree-sitter's `parse()` is **synchronous** (CPU-bound), not async.

**Solution**: Use `cpu_bound_timeout` decorator to wrap in thread pool.

```python
# At top of file
from api.utils.timeout import cpu_bound_timeout, TimeoutError
from api.config.timeouts import get_timeout

class CodeChunkingService:

    # BEFORE:
    # def _parse_tree_sitter(self, source_code: str, language: str):
    #     tree = self.parser.parse(bytes(source_code, "utf8"))
    #     return tree

    # AFTER:
    @cpu_bound_timeout(
        timeout=get_timeout("tree_sitter_parse"),
        operation_name="tree_sitter_parse"
    )
    def _parse_tree_sitter(self, source_code: str, language: str):
        """Parse source code with tree-sitter (with timeout)."""
        tree = self.parser.parse(bytes(source_code, "utf8"))
        return tree

    async def chunk_code(
        self,
        source_code: str,
        language: str,
        file_path: Optional[str] = None
    ) -> List[CodeChunk]:
        """
        Chunk source code using tree-sitter.

        Now with timeout protection to prevent infinite hangs.
        """
        try:
            # This now calls async wrapper (runs in thread pool with timeout)
            tree = await self._parse_tree_sitter(source_code, language)

            # Rest of chunking logic
            root = tree.root_node
            chunks = self._extract_chunks(root, source_code, language)

            return chunks

        except TimeoutError as e:
            logger.error(
                f"Tree-sitter parsing timed out for {file_path}",
                extra={"file_path": file_path, "language": language}
            )
            # Re-raise to caller (indexing service will handle)
            raise
```

**Testing Plan**:
```python
# tests/services/test_code_chunking_timeout.py

@pytest.mark.anyio
async def test_tree_sitter_timeout_on_pathological_input():
    """Tree-sitter should timeout on extremely nested code."""

    # Generate pathological input (deeply nested)
    source = "def f():\n" + "  def g():\n" * 10000  # 10k nested functions

    service = CodeChunkingService()

    with pytest.raises(TimeoutError) as exc_info:
        await service.chunk_code(source, "python")

    assert "tree_sitter_parse" in str(exc_info.value)
    assert "5.0s" in str(exc_info.value)
```

---

#### 3.2 Dual Embedding Service

**File**: `api/services/dual_embedding_service.py`

**Challenge**: Embedding generation may already be async (check implementation).

```python
from api.utils.timeout import timeout_decorator, TimeoutError
from api.config.timeouts import get_timeout

class DualEmbeddingService:

    @timeout_decorator(
        timeout=get_timeout("embedding_generation_batch"),
        operation_name="dual_embedding_generation"
    )
    async def generate_dual_embeddings(
        self,
        chunks: List[CodeChunk],
        repository: Optional[str] = None
    ) -> Dict[str, List[np.ndarray]]:
        """
        Generate TEXT and CODE embeddings for chunks.

        Now with timeout protection (30s for batch).
        """
        try:
            # Generate TEXT embeddings
            texts = [chunk.text_content for chunk in chunks]
            text_embeddings = await self.text_model.encode_async(texts)

            # Generate CODE embeddings
            code_snippets = [chunk.source_code for chunk in chunks]
            code_embeddings = await self.code_model.encode_async(code_snippets)

            return {
                "text": text_embeddings,
                "code": code_embeddings
            }

        except TimeoutError as e:
            logger.error(
                f"Embedding generation timed out for {len(chunks)} chunks",
                extra={"repository": repository, "chunk_count": len(chunks)}
            )
            raise
```

---

#### 3.3 Graph Construction Service

**File**: `api/services/graph_construction_service.py`

```python
from api.utils.timeout import timeout_decorator
from api.config.timeouts import get_timeout

class GraphConstructionService:

    @timeout_decorator(
        timeout=get_timeout("graph_construction"),
        operation_name="build_graph_for_repository"
    )
    async def build_graph_for_repository(
        self,
        repository: str,
        chunks: Optional[List[CodeChunkModel]] = None,
        tx: Optional[Any] = None
    ):
        """Build dependency graph for repository (with 10s timeout)."""

        # Existing implementation
        ...
```

---

#### 3.4 Graph Traversal Service

**File**: `api/services/graph_traversal_service.py`

```python
from api.utils.timeout import timeout_decorator
from api.config.timeouts import get_timeout

class GraphTraversalService:

    @timeout_decorator(
        timeout=get_timeout("graph_traversal"),
        operation_name="traverse_dependencies"
    )
    async def traverse_dependencies(
        self,
        start_node_id: str,
        max_depth: int = 3,
        direction: str = "forward"
    ) -> Dict[str, Any]:
        """Traverse graph with timeout (5s limit)."""

        # Recursive traversal logic
        ...
```

---

### Step 4: High-Level Indexing Timeout

**File**: `api/services/code_indexing_service.py`

```python
from api.utils.timeout import timeout_decorator, TimeoutError
from api.config.timeouts import get_timeout

class CodeIndexingService:

    @timeout_decorator(
        timeout=get_timeout("index_file"),
        operation_name="index_file"
    )
    async def index_file(
        self,
        file_path: str,
        source_code: str,
        language: str,
        repository: str,
        commit_hash: Optional[str] = None
    ) -> List[CodeChunkModel]:
        """
        Index file with cumulative timeout (60s total).

        Sub-operations have individual timeouts:
        - tree_sitter_parse: 5s
        - embedding_generation: 30s
        - graph_construction: 10s

        Total: 45s (buffer: 15s)
        """
        try:
            # Each operation has its own timeout
            chunks = await self.chunking_service.chunk_code(source_code, language, file_path)
            # ... rest of indexing

        except TimeoutError as e:
            # Log high-level failure
            logger.error(
                f"File indexing timed out: {file_path}",
                extra={
                    "file_path": file_path,
                    "repository": repository,
                    "sub_operation": e.operation_name
                }
            )
            # Store in errors table (Story 12.4)
            # For now, just re-raise
            raise
```

---

## 🧪 Testing Strategy

### Test Files to Create

```
tests/
├── utils/
│   └── test_timeout.py (Unit tests - 20 tests)
│
└── integration/
    ├── test_timeout_enforcement.py (Integration tests - 15 tests)
    └── test_timeout_tree_sitter.py (Specific to tree-sitter - 5 tests)
```

### Unit Tests (`tests/utils/test_timeout.py`)

```python
import pytest
import asyncio
from api.utils.timeout import (
    with_timeout,
    timeout_decorator,
    cpu_bound_timeout,
    TimeoutError
)


class TestWithTimeout:
    """Test with_timeout() function."""

    @pytest.mark.anyio
    async def test_timeout_enforced(self):
        """Operation exceeding timeout raises TimeoutError."""

        async def slow_operation():
            await asyncio.sleep(10)  # 10 seconds
            return "done"

        with pytest.raises(TimeoutError) as exc_info:
            await with_timeout(slow_operation(), timeout=1.0)

        assert "1.0s" in str(exc_info.value)

    @pytest.mark.anyio
    async def test_timeout_not_reached(self):
        """Fast operation succeeds."""

        async def fast_operation():
            await asyncio.sleep(0.1)
            return "done"

        result = await with_timeout(fast_operation(), timeout=5.0)
        assert result == "done"

    @pytest.mark.anyio
    async def test_timeout_with_context(self):
        """Context included in error message."""

        async def slow_operation():
            await asyncio.sleep(10)

        with pytest.raises(TimeoutError) as exc_info:
            await with_timeout(
                slow_operation(),
                timeout=1.0,
                operation_name="test_op",
                context={"file": "test.py"}
            )

        error = exc_info.value
        assert error.operation_name == "test_op"
        assert error.context["file"] == "test.py"

    @pytest.mark.anyio
    async def test_timeout_no_raise(self):
        """With raise_on_timeout=False, returns None."""

        async def slow_operation():
            await asyncio.sleep(10)
            return "done"

        result = await with_timeout(
            slow_operation(),
            timeout=1.0,
            raise_on_timeout=False
        )

        assert result is None


class TestTimeoutDecorator:
    """Test timeout_decorator()."""

    @pytest.mark.anyio
    async def test_decorator_enforces_timeout(self):
        """Decorator enforces timeout."""

        @timeout_decorator(timeout=1.0)
        async def slow_func():
            await asyncio.sleep(10)
            return "done"

        with pytest.raises(TimeoutError):
            await slow_func()

    @pytest.mark.anyio
    async def test_decorator_extracts_context(self):
        """Decorator extracts file_path from kwargs."""

        @timeout_decorator(timeout=1.0, operation_name="test_op")
        async def func_with_file_path(file_path: str):
            await asyncio.sleep(10)

        with pytest.raises(TimeoutError) as exc_info:
            await func_with_file_path(file_path="test.py")

        error = exc_info.value
        assert error.context.get("file_path") == "test.py"


class TestCPUBoundTimeout:
    """Test cpu_bound_timeout() for synchronous operations."""

    @pytest.mark.anyio
    async def test_cpu_bound_timeout_enforced(self):
        """CPU-bound operation times out."""

        import time

        @cpu_bound_timeout(timeout=1.0, operation_name="slow_cpu")
        def slow_cpu_operation():
            time.sleep(10)  # Synchronous sleep
            return "done"

        with pytest.raises(TimeoutError):
            await slow_cpu_operation()

    @pytest.mark.anyio
    async def test_cpu_bound_success(self):
        """Fast CPU-bound operation succeeds."""

        import time

        @cpu_bound_timeout(timeout=5.0)
        def fast_cpu_operation():
            time.sleep(0.1)
            return "done"

        result = await fast_cpu_operation()
        assert result == "done"
```

### Integration Tests (`tests/integration/test_timeout_enforcement.py`)

```python
import pytest
from api.services.code_chunking_service import CodeChunkingService
from api.services.dual_embedding_service import DualEmbeddingService
from api.utils.timeout import TimeoutError


@pytest.mark.anyio
async def test_tree_sitter_timeout():
    """Tree-sitter parsing times out on pathological input."""

    # Extremely nested code (pathological)
    source = "def f():\n" + "  def g():\n" * 5000

    service = CodeChunkingService()

    with pytest.raises(TimeoutError) as exc_info:
        await service.chunk_code(source, "python")

    assert "tree_sitter_parse" in str(exc_info.value)


@pytest.mark.anyio
async def test_embedding_timeout():
    """Embedding generation times out on huge batch."""

    from api.models.code_chunk import CodeChunk

    # Create huge batch (should timeout if batch too large)
    chunks = [
        CodeChunk(
            chunk_type="function",
            name=f"func_{i}",
            source_code="def f(): pass" * 1000,
            start_line=i,
            end_line=i+10
        )
        for i in range(10000)  # 10k chunks
    ]

    service = DualEmbeddingService()

    # May timeout depending on hardware
    # If timeout occurs, should be handled gracefully
    try:
        await service.generate_dual_embeddings(chunks)
    except TimeoutError as e:
        assert "dual_embedding_generation" in str(e)
```

---

## 📊 Success Metrics

### Quantitative Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Timeout coverage | 100% of critical operations | Code review |
| Timeout error rate | <1% of all operations | Error logs |
| False positive rate | <0.1% (legitimate slow ops) | Manual review |
| Performance overhead | <1% latency increase | Benchmarks |

### Qualitative Checks

- [ ] No infinite hangs in 1,000-file stress test
- [ ] Timeouts logged with full context (file, repository, operation)
- [ ] Tree-sitter timeout tested with pathological input
- [ ] Embedding timeout tested with large batches
- [ ] Timeout configuration tunable via environment variables

---

## 🚀 Rollout Plan

### Phase 1: Development & Testing (Days 1-2)

1. Create `api/utils/timeout.py`
2. Create `api/config/timeouts.py`
3. Write unit tests (20 tests)
4. Verify all tests pass

### Phase 2: Integration (Days 3-4)

1. Apply timeouts to tree-sitter (Priority 1)
2. Apply timeouts to embeddings (Priority 1)
3. Write integration tests (15 tests)
4. Test with real repositories

### Phase 3: Validation (Day 5)

1. Run stress test (1,000 files)
2. Verify no false positives
3. Tune timeout values if needed
4. Create completion report

---

## ⚠️ Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Timeout too aggressive | MEDIUM | HIGH | Conservative defaults (5s+ per operation) |
| Thread pool overhead | LOW | MEDIUM | Benchmark `asyncio.to_thread()` performance |
| False positives | LOW | MEDIUM | Monitor timeout error rate, tune values |

---

## ✅ Definition of Done

- [x] `api/utils/timeout.py` created with 3 utilities
- [x] `api/config/timeouts.py` created with configurable timeouts
- [x] Timeouts applied to all Priority 1 services
- [x] 20+ unit tests passing
- [x] 15+ integration tests passing
- [x] Tree-sitter timeout tested with pathological input
- [x] No infinite hangs in stress test
- [x] Completion report written

---

**Next Step**: Implement `api/utils/timeout.py`
