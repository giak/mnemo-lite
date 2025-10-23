# EPIC-16 Story 16.3 Analysis: Integration & Performance

**Story ID**: EPIC-16 Story 16.3
**Story Points**: 3 pts
**Status**: 📝 **READY FOR IMPLEMENTATION**
**Depends On**:
- EPIC-16 Story 16.1 (TypeScriptLSPClient)
- EPIC-16 Story 16.2 (TypeExtractorService extension)
**Created**: 2025-10-23

---

## 🎯 User Story

**As a** system integrator
**I want** TypeScript LSP integrated into the indexing pipeline
**So that** type metadata is automatically extracted during code indexing

---

## 📋 Acceptance Criteria

- [ ] **AC1**: Initialize TypeScriptLSPClient in app startup (main.py lifespan)
- [ ] **AC2**: Pass typescript_lsp to TypeExtractorService via DI (dependencies.py)
- [ ] **AC3**: Graceful degradation if LSP fails (fallback to heuristic)
- [ ] **AC4**: Performance: <10s per file (with LSP + caching)
- [ ] **AC5**: Circuit breaker metrics exposed (Prometheus/health endpoint)
- [ ] **AC6**: Integration tests: 3+ scenarios (success, timeout, failure)

---

## 🔍 Integration Points

### 1. Application Startup (main.py)

**Current State** (EPIC-13 - Python LSP only):
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan (startup/shutdown)."""
    logger = logging.getLogger("api.main")

    # Startup
    logger.info("Starting MnemoLite API...")

    # Initialize database engine
    app.state.db_engine = create_async_engine(
        settings.DATABASE_URL,
        poolclass=NullPool if settings.ENVIRONMENT == "test" else AsyncAdaptedQueuePool,
        pool_size=20,
        max_overflow=10
    )

    # Initialize Python LSP (EPIC-13)
    pyright_circuit_breaker = get_pyright_lsp_circuit_breaker()
    app.state.pyright_lsp = PyrightLSPClient(circuit_breaker=pyright_circuit_breaker)
    await app.state.pyright_lsp.start()
    logger.info("Pyright LSP started")

    yield

    # Shutdown
    logger.info("Shutting down MnemoLite API...")

    # Stop Python LSP
    await app.state.pyright_lsp.stop()
    logger.info("Pyright LSP stopped")

    # Dispose database engine
    await app.state.db_engine.dispose()
```

---

**Target State** (EPIC-16 - Python + TypeScript LSP):
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan (startup/shutdown)."""
    logger = logging.getLogger("api.main")

    # Startup
    logger.info("Starting MnemoLite API...")

    # Initialize database engine
    app.state.db_engine = create_async_engine(
        settings.DATABASE_URL,
        poolclass=NullPool if settings.ENVIRONMENT == "test" else AsyncAdaptedQueuePool,
        pool_size=20,
        max_overflow=10
    )

    # Initialize Python LSP (EPIC-13)
    pyright_circuit_breaker = get_pyright_lsp_circuit_breaker()
    app.state.pyright_lsp = PyrightLSPClient(circuit_breaker=pyright_circuit_breaker)
    await app.state.pyright_lsp.start()
    logger.info("Pyright LSP started")

    # Initialize TypeScript LSP (EPIC-16) ← NEW
    typescript_circuit_breaker = get_typescript_lsp_circuit_breaker()
    app.state.typescript_lsp = TypeScriptLSPClient(circuit_breaker=typescript_circuit_breaker)

    try:
        await app.state.typescript_lsp.start()
        logger.info("TypeScript LSP started")
    except RuntimeError as e:
        logger.error(f"TypeScript LSP startup failed: {e}")
        logger.warning("Continuing without TypeScript LSP (graceful degradation)")
        app.state.typescript_lsp = None  # Disable LSP

    yield

    # Shutdown
    logger.info("Shutting down MnemoLite API...")

    # Stop TypeScript LSP ← NEW
    if app.state.typescript_lsp:
        await app.state.typescript_lsp.stop()
        logger.info("TypeScript LSP stopped")

    # Stop Python LSP
    await app.state.pyright_lsp.stop()
    logger.info("Pyright LSP stopped")

    # Dispose database engine
    await app.state.db_engine.dispose()
```

**Key Changes**:
- ✅ Start TypeScript LSP during startup
- ✅ Graceful degradation if startup fails (log warning, continue without LSP)
- ✅ Stop TypeScript LSP during shutdown (if started)

---

### 2. Dependency Injection (dependencies.py)

**Current State** (EPIC-13 - Python LSP only):
```python
def get_pyright_lsp_client(request: Request) -> PyrightLSPClient:
    """Get Pyright LSP client from app state."""
    return request.app.state.pyright_lsp


def get_type_extractor_service(
    pyright_lsp: PyrightLSPClient = Depends(get_pyright_lsp_client),
    redis_client: Redis = Depends(get_redis_client)
) -> TypeExtractorService:
    """Get type extractor service."""
    return TypeExtractorService(
        pyright_lsp=pyright_lsp,
        redis_client=redis_client,
        cache_ttl=3600
    )
```

---

**Target State** (EPIC-16 - Python + TypeScript LSP):
```python
def get_pyright_lsp_client(request: Request) -> PyrightLSPClient:
    """Get Pyright LSP client from app state."""
    return request.app.state.pyright_lsp


def get_typescript_lsp_client(request: Request) -> Optional[TypeScriptLSPClient]:  # ← NEW
    """Get TypeScript LSP client from app state.

    Returns:
        TypeScriptLSPClient or None if LSP failed to start
    """
    return getattr(request.app.state, "typescript_lsp", None)


def get_type_extractor_service(
    pyright_lsp: PyrightLSPClient = Depends(get_pyright_lsp_client),
    typescript_lsp: Optional[TypeScriptLSPClient] = Depends(get_typescript_lsp_client),  # ← NEW
    redis_client: Redis = Depends(get_redis_client)
) -> TypeExtractorService:
    """Get type extractor service."""
    return TypeExtractorService(
        pyright_lsp=pyright_lsp,
        typescript_lsp=typescript_lsp,  # ← NEW (may be None)
        redis_client=redis_client,
        cache_ttl=3600
    )
```

**Key Changes**:
- ✅ Add `get_typescript_lsp_client()` dependency
- ✅ Return `Optional[TypeScriptLSPClient]` (may be None if startup failed)
- ✅ Inject into TypeExtractorService

---

### 3. TypeExtractorService Graceful Degradation

**Update**: Handle None typescript_lsp (Story 16.2 extension)

```python
class TypeExtractorService:
    def __init__(
        self,
        pyright_lsp: PyrightLSPClient,
        typescript_lsp: Optional[TypeScriptLSPClient],  # ← May be None
        redis_client: Redis,
        cache_ttl: int = 3600
    ):
        self.pyright_lsp = pyright_lsp
        self.typescript_lsp = typescript_lsp
        self.redis_client = redis_client
        self.cache_ttl = cache_ttl
        self.logger = logging.getLogger(__name__)

        # Log LSP status
        if self.typescript_lsp is None:
            self.logger.warning(
                "TypeScript LSP not available, falling back to heuristic extraction"
            )


    async def _extract_typescript_types(
        self,
        chunk: CodeChunk
    ) -> Dict[str, Any]:
        """Extract TypeScript types using LSP (or heuristic fallback)."""

        # Check if LSP is available ← NEW
        if self.typescript_lsp is None:
            self.logger.debug("TypeScript LSP not available, using heuristic")
            return await self._extract_typescript_heuristic(chunk)

        # Check cache first (L2)
        cache_key = f"ts-types:{chunk.id}"
        cached = await self._get_from_cache(cache_key)
        if cached:
            return cached

        try:
            # Create temporary workspace
            workspace_dir = await self._create_typescript_workspace(chunk)

            # Get hover info
            hover = await self.typescript_lsp.get_hover(
                file_path=workspace_dir / "temp.ts",
                line=0,
                character=0
            )

            if not hover:
                self.logger.warning(f"No hover info for chunk {chunk.id}, using heuristic")
                return await self._extract_typescript_heuristic(chunk)

            # Parse hover → metadata
            metadata = self._parse_typescript_hover(hover, chunk)
            metadata["imports"] = self._extract_typescript_imports(chunk.source_code)

            # Cache result
            await self._set_in_cache(cache_key, metadata)

            return metadata

        except Exception as e:
            self.logger.error(f"TypeScript LSP extraction failed: {e}")
            # Fallback to heuristic
            return await self._extract_typescript_heuristic(chunk)
```

**Graceful Degradation Flow**:
1. LSP startup fails → `app.state.typescript_lsp = None`
2. TypeExtractorService receives `None` → Log warning
3. `_extract_typescript_types()` checks if LSP is None → Use heuristic
4. Heuristic extraction succeeds with 70% accuracy (acceptable fallback)

---

## 📊 Performance Analysis

### Performance Targets

| Metric | Target | Expected | Notes |
|--------|--------|----------|-------|
| **LSP Startup** | <2s | ~1.5s | Acceptable (one-time cost) |
| **LSP Shutdown** | <2s | ~0.5s | Acceptable (one-time cost) |
| **Type Extraction (LSP)** | <500ms | ~200ms | Per chunk (with caching) |
| **Type Extraction (Heuristic)** | <50ms | ~10ms | Fallback performance |
| **Full File Indexing** | <10s | ~5s | 100 lines, 10 chunks, cached |
| **Cache Hit Rate** | >80% | ~85% | L2 Redis cache |

---

### Performance Optimization Strategies

#### 1. Redis Caching (L2)

**Strategy**: Cache LSP responses to avoid repeated queries

**Implementation** (Story 16.2):
```python
# Cache key: ts-types:{chunk_id}
cache_key = f"ts-types:{chunk.id}"

# Check cache first
cached = await self._get_from_cache(cache_key)
if cached:
    return cached  # Hit: ~0ms

# Cache miss: query LSP
hover = await self.typescript_lsp.get_hover(...)
metadata = self._parse_typescript_hover(hover, chunk)

# Store in cache (TTL: 1h)
await self._set_in_cache(cache_key, metadata)
```

**Expected Impact**:
- Cache hit: ~0ms (instant)
- Cache miss: ~200ms (LSP query)
- Hit rate: ~85% (files rarely change)

---

#### 2. Circuit Breaker Protection

**Strategy**: Prevent cascading failures from LSP timeouts

**Implementation** (Story 16.1):
```python
# Circuit breaker configuration
TYPESCRIPT_LSP_CIRCUIT_BREAKER_CONFIG = {
    "failure_threshold": 3,  # Open after 3 failures
    "recovery_timeout": 60.0,  # Try recovery after 60s
    "expected_exception": Exception
}

# Usage in get_hover()
async def get_hover(...):
    async def _execute():
        return await self._send_request(...)

    try:
        result = await self.circuit_breaker.execute(_execute)
        return result
    except Exception as e:
        self.logger.error(f"get_hover failed: {e}")
        return None  # Graceful degradation
```

**Expected Impact**:
- Prevents cascading failures
- Automatic fallback to heuristic
- Recovery after timeout

---

#### 3. Timeout Protection

**Strategy**: Limit LSP request time to 5s max

**Implementation** (Story 16.1):
```python
async def _send_request(...):
    # Wait for response with timeout
    try:
        response = await asyncio.wait_for(
            self._read_response(request_id),
            timeout=5.0  # 5s max
        )
        return response
    except asyncio.TimeoutError:
        self.logger.error("LSP request timeout")
        raise TimeoutError("LSP request timed out")
```

**Expected Impact**:
- No hanging requests
- Fast fallback to heuristic (after 5s)

---

## 🧪 Integration Testing

### Test Scenarios

**File**: `tests/integration/test_typescript_lsp_integration.py`

#### Test 1: Successful TypeScript Indexing (Happy Path)

```python
@pytest.mark.asyncio
async def test_typescript_indexing_success(test_client):
    """Test successful TypeScript file indexing with LSP."""
    # Arrange
    typescript_code = """
    export interface User {
        id: string;
        name: string;
    }

    export async function getUser(id: string): Promise<User> {
        return { id, name: 'Test' };
    }
    """

    # Act
    response = await test_client.post(
        "/v1/code/index",
        json={
            "repository": "test-repo",
            "files": [
                {
                    "path": "user.ts",
                    "content": typescript_code,
                    "language": "typescript"
                }
            ]
        }
    )

    # Assert
    assert response.status_code == 200
    data = response.json()

    # Verify chunks created
    assert data["chunks_indexed"] == 2  # interface + function

    # Verify type metadata extracted
    chunks = await get_chunks_from_db("test-repo")
    function_chunk = next(c for c in chunks if c.name == "getUser")

    assert function_chunk.metadata["parameters"][0]["type"] == "string"
    assert "Promise<User>" in function_chunk.metadata["return_type"]["type"]
    assert function_chunk.metadata["extraction_method"] == "lsp"  # LSP used


@pytest.mark.asyncio
async def test_typescript_lsp_timeout_fallback(test_client, monkeypatch):
    """Test graceful degradation when LSP times out."""
    # Arrange
    async def mock_get_hover_timeout(*args, **kwargs):
        raise TimeoutError("LSP timeout")

    # Mock LSP to timeout
    monkeypatch.setattr(
        "api.services.typescript_lsp_client.TypeScriptLSPClient.get_hover",
        mock_get_hover_timeout
    )

    typescript_code = "export function test(x: number): string { return ''; }"

    # Act
    response = await test_client.post(
        "/v1/code/index",
        json={
            "repository": "test-repo",
            "files": [{"path": "test.ts", "content": typescript_code, "language": "typescript"}]
        }
    )

    # Assert
    assert response.status_code == 200  # Still succeeds

    # Verify fallback to heuristic
    chunks = await get_chunks_from_db("test-repo")
    assert len(chunks) == 1
    assert chunks[0].metadata["extraction_method"] == "heuristic"  # Fallback used


@pytest.mark.asyncio
async def test_typescript_lsp_startup_failure(test_client, monkeypatch):
    """Test app continues if TypeScript LSP fails to start."""
    # Arrange
    async def mock_lsp_start_failure(self):
        raise RuntimeError("Node.js not found")

    # Mock LSP startup failure
    monkeypatch.setattr(
        "api.services.typescript_lsp_client.TypeScriptLSPClient.start",
        mock_lsp_start_failure
    )

    # Act: Restart app (simulate startup)
    # (In practice, this would be tested by restarting the FastAPI app)

    # Assert: App should start successfully despite LSP failure
    response = await test_client.get("/health")
    assert response.status_code == 200

    # TypeScript indexing should still work (heuristic fallback)
    response = await test_client.post(
        "/v1/code/index",
        json={
            "repository": "test-repo",
            "files": [{"path": "test.ts", "content": "export function test() {}", "language": "typescript"}]
        }
    )
    assert response.status_code == 200
```

---

## 📊 Circuit Breaker Metrics

### Health Endpoint Integration

**File**: `api/routes/health.py`

**Update**: Add TypeScript LSP status to health check

```python
@router.get("/health")
async def health_check(request: Request) -> Dict[str, Any]:
    """Health check endpoint."""

    # Check TypeScript LSP status
    typescript_lsp = getattr(request.app.state, "typescript_lsp", None)
    typescript_lsp_status = "healthy" if typescript_lsp else "disabled"

    # Check circuit breaker state
    if typescript_lsp:
        circuit_breaker = typescript_lsp.circuit_breaker
        if circuit_breaker.state == CircuitBreakerState.OPEN:
            typescript_lsp_status = "circuit_open"
        elif circuit_breaker.state == CircuitBreakerState.HALF_OPEN:
            typescript_lsp_status = "circuit_half_open"

    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "database": "healthy",
            "redis": "healthy",
            "pyright_lsp": "healthy",
            "typescript_lsp": typescript_lsp_status  # ← NEW
        },
        "circuit_breakers": {
            "pyright_lsp": _get_circuit_breaker_metrics(request.app.state.pyright_lsp.circuit_breaker),
            "typescript_lsp": _get_circuit_breaker_metrics(typescript_lsp.circuit_breaker) if typescript_lsp else None
        }
    }


def _get_circuit_breaker_metrics(circuit_breaker: CircuitBreaker) -> Dict[str, Any]:
    """Get circuit breaker metrics."""
    return {
        "state": circuit_breaker.state.value,
        "failure_count": circuit_breaker.failure_count,
        "success_count": circuit_breaker.success_count,
        "last_failure_time": circuit_breaker.last_failure_time.isoformat() if circuit_breaker.last_failure_time else None
    }
```

**Example Health Response**:
```json
{
  "status": "healthy",
  "services": {
    "typescript_lsp": "healthy"
  },
  "circuit_breakers": {
    "typescript_lsp": {
      "state": "CLOSED",
      "failure_count": 0,
      "success_count": 42,
      "last_failure_time": null
    }
  }
}
```

---

## 🚦 Environment Configuration

### Environment Variables

**File**: `.env` or `docker-compose.yml`

```bash
# TypeScript LSP Configuration (EPIC-16)
TYPESCRIPT_LSP_ENABLED=true          # Enable/disable TypeScript LSP
TYPESCRIPT_LSP_TIMEOUT=5.0           # Request timeout (seconds)
TYPESCRIPT_LSP_CACHE_TTL=3600        # Cache TTL (seconds)

# Circuit Breaker Configuration
TYPESCRIPT_LSP_FAILURE_THRESHOLD=3   # Open after N failures
TYPESCRIPT_LSP_RECOVERY_TIMEOUT=60.0 # Recovery timeout (seconds)
```

**Usage in Code**:
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # ... existing settings ...

    # TypeScript LSP (EPIC-16)
    TYPESCRIPT_LSP_ENABLED: bool = True
    TYPESCRIPT_LSP_TIMEOUT: float = 5.0
    TYPESCRIPT_LSP_CACHE_TTL: int = 3600
    TYPESCRIPT_LSP_FAILURE_THRESHOLD: int = 3
    TYPESCRIPT_LSP_RECOVERY_TIMEOUT: float = 60.0

settings = Settings()
```

**Graceful Degradation via Env Var**:
```python
# In main.py lifespan
if settings.TYPESCRIPT_LSP_ENABLED:
    try:
        await app.state.typescript_lsp.start()
        logger.info("TypeScript LSP started")
    except RuntimeError as e:
        logger.error(f"TypeScript LSP startup failed: {e}")
        app.state.typescript_lsp = None
else:
    logger.info("TypeScript LSP disabled via TYPESCRIPT_LSP_ENABLED=false")
    app.state.typescript_lsp = None
```

---

## 📝 Implementation Checklist

- [ ] Update `main.py` lifespan to start/stop TypeScript LSP
- [ ] Add graceful degradation for LSP startup failure
- [ ] Update `dependencies.py` with `get_typescript_lsp_client()`
- [ ] Update `TypeExtractorService.__init__()` to handle `typescript_lsp=None`
- [ ] Update `_extract_typescript_types()` to check if LSP is available
- [ ] Add environment variables for TypeScript LSP configuration
- [ ] Update health endpoint with TypeScript LSP status
- [ ] Add circuit breaker metrics to health endpoint
- [ ] Create integration tests (3+ scenarios)
- [ ] Test with real TypeScript repository (code_test/)
- [ ] Validate performance: <10s per file
- [ ] Document configuration options

---

## 🎯 Success Criteria

**Story 16.3 is complete when**:

1. ✅ TypeScript LSP integrated into main.py lifespan
2. ✅ Dependency injection working (DI via dependencies.py)
3. ✅ Graceful degradation implemented (LSP failure → heuristic fallback)
4. ✅ Performance target met: <10s per file (with caching)
5. ✅ Circuit breaker metrics exposed via health endpoint
6. ✅ Integration tests passing (3+ scenarios: success, timeout, failure)
7. ✅ Environment variables documented
8. ✅ Zero regressions in existing functionality (Python LSP unchanged)

---

**Last Updated**: 2025-10-23
**Status**: 📝 **READY FOR IMPLEMENTATION** (3 pts)
**Next Story**: [EPIC-16 Story 16.4: Documentation & Testing](EPIC-16_STORY_16.4_ANALYSIS.md)
