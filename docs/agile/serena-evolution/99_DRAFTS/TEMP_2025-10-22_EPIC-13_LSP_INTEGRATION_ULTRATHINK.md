# EPIC-13: LSP Integration - ULTRATHINK Analysis

**Date**: 2025-10-22
**Author**: Claude Code (Ultrathink Mode)
**Epic**: EPIC-13 (21 pts) - LSP Integration (Analysis Only)
**Status**: PRE-IMPLEMENTATION ANALYSIS

---

## 🎯 Executive Summary

EPIC-13 integrates Pyright LSP server for **read-only semantic analysis** to enhance MnemoLite's code intelligence from structural (tree-sitter) to semantic (type-aware) understanding.

**Key Transformation**:
```
v2.0: Syntax Analysis (tree-sitter)
  → Chunks with structure but NO types
  → Call resolution: 70% (heuristic-based)

v3.0: Semantic Analysis (LSP + tree-sitter)
  → Chunks with types, signatures, resolved imports
  → Call resolution: 95%+ (LSP-verified)
```

**Critical Success Factors**:
1. ✅ Graceful degradation (LSP failures → tree-sitter fallback)
2. ✅ Performance (caching + timeouts)
3. ✅ Stability (auto-restart + circuit breakers)

---

## 📊 Epic Breakdown & Points Validation

### Story Points Analysis

| Story | Points | Complexity | Justification |
|-------|--------|------------|---------------|
| 13.1: Pyright LSP Wrapper | 8 pts | HIGH | JSON-RPC protocol, subprocess management, async I/O, response parsing |
| 13.2: Type Metadata Extraction | 5 pts | MEDIUM | LSP integration in indexing pipeline, signature parsing, merge logic |
| 13.3: LSP Lifecycle Management | 3 pts | MEDIUM | Auto-restart, health checks, exponential backoff |
| 13.4: LSP Result Caching | 3 pts | LOW | Redis integration (existing infrastructure) |
| 13.5: Enhanced Call Resolution | 2 pts | LOW | Use existing name_path + LSP metadata |
| **TOTAL** | **21 pts** | - | Reasonable for 1 week with senior dev |

**Points Distribution**: 38% infrastructure (8 pts), 24% core feature (5 pts), 38% quality/optimization (8 pts)

**Verdict**: ✅ Points allocation is reasonable and well-balanced

---

## 🔍 Deep Technical Analysis

### 1. LSP Protocol & Communication Layer

#### JSON-RPC 2.0 over stdio

**Protocol Structure**:
```
Message Format:
Content-Length: <bytes>\r\n
\r\n
<JSON payload>
```

**Critical Implementation Details**:

1. **Header Parsing**
   - MUST handle `Content-Length` header correctly
   - MUST handle optional `Content-Type` header
   - MUST split on `\r\n\r\n` (not `\n\n`)

2. **Buffering Strategy**
   ```python
   buffer = b""
   while True:
       chunk = await process.stdout.read(1024)
       buffer += chunk

       # Parse complete messages
       while b"\r\n\r\n" in buffer:
           header, rest = buffer.split(b"\r\n\r\n", 1)
           content_length = extract_content_length(header)

           if len(rest) < content_length:
               break  # Incomplete message

           message = rest[:content_length]
           buffer = rest[content_length:]

           handle_message(json.loads(message))
   ```

3. **Request-Response Correlation**
   - Use `id` field to match responses to requests
   - Store pending requests in `Dict[str, asyncio.Future]`
   - Timeout handling with `asyncio.wait_for()`

**Gotchas Identified**:
- ❌ **Edge case**: Message split across read chunks (MUST handle partial reads)
- ❌ **Edge case**: Multiple messages in single read (MUST loop until buffer empty)
- ❌ **Edge case**: Pyright sends notifications (no `id`) → MUST distinguish from responses
- ❌ **Edge case**: Pyright may send diagnostics unsolicited → MUST ignore or log

#### Pyright-Specific Behavior

**Initialization Sequence**:
```
1. Client → initialize(rootUri, capabilities)
2. Server → initialize response (serverCapabilities)
3. Client → initialized notification
4. Server ready for requests
```

**Document Lifecycle**:
```
1. textDocument/didOpen (required before queries)
2. textDocument/hover (or other queries)
3. textDocument/didClose (cleanup)
```

**Critical**: Pyright maintains an in-memory workspace. Documents MUST be opened before querying.

**Gotchas**:
- ❌ Pyright may cache document state → use `version` field
- ❌ Pyright workspace config (pyrightconfig.json) may affect behavior
- ❌ Pyright requires Python environment resolution → may fail without venv

---

### 2. Type Extraction & Signature Parsing

#### Hover Response Format

**Example Responses**:
```python
# Function hover
{
  "contents": {
    "kind": "markdown",
    "value": "```python\n(function) add(a: int, b: int) -> int\n```\nAdd two numbers."
  },
  "range": {...}
}

# Method hover
{
  "contents": "(method) User.validate(self) -> bool"
}

# Variable hover
{
  "contents": "(variable) user_count: int"
}
```

**Parsing Strategy**:

1. **Extract Signature Line**
   ```python
   # Input: "(function) add(a: int, b: int) -> int\nDocstring..."
   # Output: "add(a: int, b: int) -> int"

   signature = hover_text.split("\n")[0]
   signature = signature.split(")", 1)[1].strip()  # Remove "(function)"
   ```

2. **Parse Return Type**
   ```python
   if "->" in signature:
       return_type = signature.split("->")[1].strip()
   ```

3. **Parse Parameters**
   ```python
   params_str = signature.split("(")[1].split(")")[0]
   for param in params_str.split(","):
       name, type_ = param.split(":")
       param_types[name.strip()] = type_.strip()
   ```

**Edge Cases**:
- ❌ **Optional parameters**: `name: str = 'default'` → Remove `= 'default'`
- ❌ **Complex types**: `List[Dict[str, Any]]` → Keep as-is (no parsing)
- ❌ **Union types**: `int | str` → Keep verbatim
- ❌ **Generic types**: `TypeVar("T")` → May need special handling
- ❌ **Ellipsis**: `def foo(...): pass` → May not have hover info

**Fallback Strategy**:
```python
try:
    return_type = parse_return_type(hover_text)
except Exception:
    return_type = None  # Graceful degradation
```

---

### 3. Performance Analysis & Caching Strategy

#### Latency Breakdown

**Without LSP**:
```
Indexing Pipeline (current):
├─ Parse (tree-sitter):      50ms/file
├─ Chunk:                     10ms/file
├─ Metadata extraction:       5ms/file
├─ Embeddings:               100ms/file (cached)
└─ Store:                     20ms/file
TOTAL:                       ~185ms/file
```

**With LSP (worst case)**:
```
Indexing Pipeline (LSP enabled):
├─ Parse (tree-sitter):      50ms/file
├─ Chunk:                     10ms/file
├─ Metadata extraction:       5ms/file
├─ LSP queries (NEW):        ~500ms/file (10 chunks × 50ms)
├─ Embeddings:               100ms/file (cached)
└─ Store:                     20ms/file
TOTAL:                       ~685ms/file (3.7× slower)
```

**With LSP + L2 Caching (typical)**:
```
Indexing Pipeline (LSP + cache):
├─ Parse (tree-sitter):      50ms/file
├─ Chunk:                     10ms/file
├─ Metadata extraction:       5ms/file
├─ LSP queries (cached):     ~10ms/file (10 chunks × 1ms)
├─ Embeddings:               100ms/file (cached)
└─ Store:                     20ms/file
TOTAL:                       ~195ms/file (5% overhead)
```

**Cache Hit Rate Assumptions**:
- First index: 0% hit rate → 685ms/file
- Re-index (same code): 100% hit rate → 195ms/file
- Re-index (10% changes): 90% hit rate → ~245ms/file

**Mitigation Strategies**:

1. **Parallel LSP Queries** (Future optimization)
   ```python
   tasks = [lsp.hover(...) for chunk in chunks]
   results = await asyncio.gather(*tasks)
   # Reduces 500ms → ~100ms (limited by LSP server concurrency)
   ```

2. **Batch Document Opening** (Current approach)
   ```python
   await lsp.open_document(file_path, source_code)
   for chunk in chunks:
       await lsp.hover(file_path, chunk.line, 0)
   await lsp.close_document(file_path)
   # Avoids repeated open/close overhead
   ```

3. **Timeout Enforcement** (Critical)
   ```python
   await asyncio.wait_for(lsp.hover(...), timeout=3.0)
   # Prevents runaway queries
   ```

**Performance Targets**:
- ✅ LSP server startup: <500ms
- ✅ Hover query (uncached): <100ms
- ✅ Hover query (cached): <1ms
- ✅ Cache hit rate: >80% (re-indexing)

---

### 4. Graceful Degradation Architecture

#### Failure Modes & Responses

| Failure Scenario | Detection | Response | User Impact |
|------------------|-----------|----------|-------------|
| LSP server not installed | Startup error | Disable LSP, log warning | No type info (tree-sitter only) |
| LSP server crashes during init | Process exit code | Retry 3×, then disable | No type info (tree-sitter only) |
| LSP query timeout (>3s) | `asyncio.TimeoutError` | Skip chunk, continue | Partial type info |
| LSP query error (e.g., syntax error) | JSON-RPC error response | Skip chunk, log warning | Partial type info |
| Pyright not compatible with Python version | Initialization error | Disable LSP, log error | No type info |
| LSP workspace setup fails | File I/O error | Disable LSP, log error | No type info |

**Graceful Degradation Principle**:
```python
# CORRECT: LSP as enhancement, not requirement
try:
    type_metadata = await lsp.extract_types(chunk)
    chunk.metadata.update(type_metadata)
except (LSPError, TimeoutError) as e:
    logger.warning("LSP failed, continuing without types", error=str(e))
    # chunk.metadata remains tree-sitter-only
```

**WRONG**:
```python
# WRONG: LSP as requirement
type_metadata = await lsp.extract_types(chunk)  # Raises exception
chunk.metadata.update(type_metadata)  # Never reached on error
```

**Circuit Breaker Integration** (from EPIC-12):
```python
if lsp_circuit_breaker.can_execute():
    try:
        type_metadata = await lsp.extract_types(chunk)
        lsp_circuit_breaker.record_success()
    except Exception as e:
        lsp_circuit_breaker.record_failure()
        logger.warning("LSP failed", error=str(e))
else:
    logger.info("LSP circuit open, skipping type extraction")
```

**Failure Rate Targets**:
- ✅ LSP availability: >99% (with auto-restart)
- ✅ Graceful degradation: 100% (no pipeline crashes)
- ✅ Type coverage: 90%+ (for typed code with healthy LSP)

---

### 5. Lifecycle Management & Auto-Restart

#### Restart Strategies

**Exponential Backoff**:
```python
for attempt in range(1, max_attempts + 1):
    try:
        await lsp_client.start()
        return
    except Exception as e:
        delay = 2 ** attempt  # 2s, 4s, 8s
        await asyncio.sleep(delay)
```

**Crash Detection**:
```python
# Poll subprocess returncode
if lsp_client.process.returncode is not None:
    logger.warning("LSP crashed", returncode=returncode)
    await restart_lsp()
```

**Health Checks**:
```json
GET /v1/lsp/health

{
  "status": "healthy",  // healthy, crashed, not_started, starting
  "running": true,
  "initialized": true,
  "restart_count": 0,
  "last_restart": null,
  "uptime_seconds": 3600
}
```

**Manual Restart Endpoint**:
```json
POST /v1/lsp/restart

{
  "status": "restarted",
  "health": {...}
}
```

**Gotchas**:
- ❌ **Race condition**: Crash during query → response reader may hang
- ❌ **Zombie processes**: Ensure process.kill() if graceful shutdown fails
- ❌ **Max restart limit**: Prevent infinite restart loop (max 3 attempts)

---

### 6. Integration Points & Dependencies

#### EPIC-12 Dependencies (Robustness)

**Required from EPIC-12**:
1. ✅ **Timeout utilities** (Story 12.1)
   - `with_timeout()` for LSP queries (3s timeout)
   - Graceful timeout handling

2. ✅ **Circuit breakers** (Story 12.3)
   - LSP circuit breaker (5 failures → open)
   - Automatic recovery

3. ✅ **Error tracking** (Story 12.4)
   - Log LSP failures to error_logs table
   - Alert on repeated failures

4. ✅ **Retry logic** (Story 12.5)
   - Retry LSP server startup (3 attempts)
   - Exponential backoff

**Status**: ✅ All EPIC-12 dependencies satisfied (23/23 pts complete)

#### EPIC-11 Dependencies (Symbol Enhancement)

**Required from EPIC-11**:
1. ✅ **name_path** (Story 11.1)
   - Hierarchical qualified names (e.g., "models.user.User.validate")
   - Enables call resolution with LSP-resolved paths

2. ✅ **name_path indexes** (Story 11.1)
   - Btree + trgm indexes for efficient lookup
   - Fast resolution of "api.services.user_service.get_user"

**Status**: ✅ All EPIC-11 dependencies satisfied (13/13 pts complete)

#### New Dependencies Required

**Python Packages**:
```txt
# Add to requirements.txt
pyright==1.1.350  # Pyright language server
```

**System Dependencies**:
```dockerfile
# Add to Dockerfile (api/)
RUN npm install -g pyright@1.1.350
# OR
RUN pip install pyright==1.1.350  # Includes pyright-langserver
```

**Configuration**:
```json
// pyrightconfig.json (workspace root)
{
  "pythonVersion": "3.12",
  "typeCheckingMode": "basic",
  "useLibraryCodeForTypes": true
}
```

---

## 🚨 Critical Risks & Mitigations

### Risk 1: Pyright Availability & Compatibility

**Risk**: Pyright not installed or incompatible with Python 3.12

**Probability**: MEDIUM (Docker build may fail)

**Impact**: HIGH (blocks entire EPIC)

**Mitigation**:
1. **Verification step**: Add `which pyright-langserver` to Dockerfile
2. **Fallback**: Make LSP optional (env var `ENABLE_LSP=true`)
3. **Testing**: Test Pyright startup in CI before merging

**Action Items**:
- [ ] Add Pyright to Dockerfile
- [ ] Test Pyright installation in Docker
- [ ] Add `ENABLE_LSP` environment variable

---

### Risk 2: JSON-RPC Protocol Complexity

**Risk**: JSON-RPC parsing bugs (incomplete messages, malformed JSON)

**Probability**: MEDIUM (protocol is complex)

**Impact**: HIGH (LSP crashes or hangs)

**Mitigation**:
1. **Robust parsing**: Handle edge cases (incomplete messages, multiple messages in buffer)
2. **Logging**: Log all raw messages (debug mode) for troubleshooting
3. **Testing**: Unit tests with malformed inputs

**Test Cases**:
```python
def test_incomplete_message():
    # Message split across two reads
    pass

def test_multiple_messages_in_buffer():
    # Two complete messages in single read
    pass

def test_malformed_json():
    # Invalid JSON in message body
    pass
```

---

### Risk 3: LSP Server Crashes Under Load

**Risk**: Pyright crashes or becomes unresponsive during heavy indexing

**Probability**: LOW-MEDIUM (Pyright is mature but may have memory limits)

**Impact**: MEDIUM (indexing slows but doesn't fail)

**Mitigation**:
1. **Auto-restart**: Restart on crash (max 3 attempts)
2. **Circuit breaker**: Disable after 5 consecutive failures
3. **Resource limits**: Set subprocess memory limit (optional)

**Monitoring**:
```python
# Log LSP metrics
logger.info("LSP stats",
    queries_total=lsp_query_count,
    queries_failed=lsp_failure_count,
    restart_count=lsp_restart_count,
    uptime_seconds=lsp_uptime
)
```

---

### Risk 4: Type Extraction Accuracy

**Risk**: Parsed type metadata is incorrect (wrong return types, param types)

**Probability**: LOW (Pyright is accurate, but parsing may have bugs)

**Impact**: MEDIUM (wrong metadata stored, affects search quality)

**Mitigation**:
1. **Validation tests**: Test type extraction on 100+ known functions
2. **Manual review**: Review top 100 indexed chunks for accuracy
3. **User feedback**: Allow users to report incorrect metadata

**Validation Dataset**:
```python
# tests/datasets/type_extraction_validation.py

VALIDATION_CASES = [
    {
        "source": "def add(a: int, b: int) -> int: return a + b",
        "expected": {
            "return_type": "int",
            "param_types": {"a": "int", "b": "int"}
        }
    },
    # ... 100+ cases
]
```

---

### Risk 5: Performance Degradation

**Risk**: LSP queries slow down indexing by 3-5×

**Probability**: HIGH (without caching)

**Impact**: HIGH (unacceptable UX for large codebases)

**Mitigation**:
1. **L2 Redis caching**: 80%+ hit rate on re-indexing
2. **Timeout enforcement**: Max 3s per query
3. **Parallel queries**: Batch LSP queries (future optimization)
4. **Skip heuristic**: Skip LSP for files >1000 lines (optional)

**Performance Testing**:
```python
# tests/performance/test_lsp_indexing_performance.py

async def test_indexing_performance_with_lsp():
    # Index 100 Python files
    start = time.time()
    await index_repository(repo, lsp_enabled=True)
    elapsed = time.time() - start

    # Should be <5× slower than without LSP
    baseline = 18.5  # seconds (100 files × 185ms)
    assert elapsed < baseline * 5, f"Too slow: {elapsed}s"
```

---

## 📋 Implementation Plan (Detailed)

### Phase 1: Infrastructure (Story 13.1) - 8 pts

**Duration**: 2-3 days

**Tasks**:
1. **Add Pyright to Dockerfile** (30 min)
   ```dockerfile
   # api/Dockerfile
   RUN pip install pyright==1.1.350
   ```

2. **Create LSP client skeleton** (2 hours)
   - `api/services/lsp/__init__.py`
   - `api/services/lsp/lsp_client.py` (PyrightLSPClient class)
   - `api/services/lsp/lsp_errors.py` (LSPError exception)

3. **Implement JSON-RPC communication** (4 hours)
   - `_send_request()` with timeout
   - `_send_notification()`
   - `_read_responses()` background task
   - `_handle_response()` response correlation

4. **Implement LSP initialization** (2 hours)
   - `start()` spawn subprocess
   - `_initialize()` send initialize request
   - `initialized` notification

5. **Implement hover query** (2 hours)
   - `hover()` method
   - `_open_document()` helper
   - `_close_document()` helper

6. **Implement shutdown** (1 hour)
   - `shutdown()` graceful exit
   - Process cleanup

7. **Unit tests** (4 hours)
   - `test_lsp_server_startup()`
   - `test_hover_query()`
   - `test_document_symbols()`
   - `test_server_crash_recovery()`
   - `test_timeout_handling()`

8. **Integration test** (2 hours)
   - End-to-end LSP query test
   - Verify Pyright responses

**Deliverables**:
- ✅ Working LSP client (400 lines)
- ✅ 8 unit tests passing
- ✅ LSP server starts and responds to queries

---

### Phase 2: Type Extraction (Story 13.2) - 5 pts

**Duration**: 1-2 days

**Tasks**:
1. **Create TypeExtractorService** (3 hours)
   - `api/services/lsp/type_extractor.py`
   - `extract_type_metadata()` method
   - `_parse_hover_signature()` parser

2. **Integrate into CodeIndexingService** (2 hours)
   - Add `type_extractor` parameter
   - Call `extract_type_metadata()` per chunk
   - Merge metadata with tree-sitter data
   - Handle LSP failures gracefully

3. **Wire up dependencies** (1 hour)
   - Update `api/dependencies.py`
   - Add `get_lsp_client()`, `get_type_extractor()`

4. **Unit tests** (3 hours)
   - `test_extract_function_types()`
   - `test_extract_method_types()`
   - `test_extract_class_types()`
   - `test_graceful_degradation_lsp_failure()`
   - `test_parse_hover_signature_edge_cases()`

5. **Integration test** (2 hours)
   - Index file with LSP enabled
   - Verify type metadata stored in chunks

**Deliverables**:
- ✅ TypeExtractorService (150 lines)
- ✅ CodeIndexingService integration
- ✅ 5 unit tests passing

---

### Phase 3: Lifecycle Management (Story 13.3) - 3 pts

**Duration**: 1 day

**Tasks**:
1. **Create LSPLifecycleManager** (2 hours)
   - `api/services/lsp/lsp_lifecycle_manager.py`
   - `start()` with retry
   - `ensure_running()` crash detection
   - `health_check()` status

2. **Create health/restart endpoints** (1 hour)
   - `api/routes/lsp_routes.py`
   - `GET /v1/lsp/health`
   - `POST /v1/lsp/restart`

3. **Integrate into main.py** (1 hour)
   - Start LSP in lifespan
   - Shutdown LSP on exit

4. **Tests** (2 hours)
   - `test_auto_restart()`
   - `test_health_check()`
   - `test_manual_restart_endpoint()`

**Deliverables**:
- ✅ LSPLifecycleManager (100 lines)
- ✅ Health/restart endpoints
- ✅ 3 tests passing

---

### Phase 4: Caching (Story 13.4) - 3 pts

**Duration**: 0.5 day

**Tasks**:
1. **Add caching to TypeExtractorService** (2 hours)
   - Cache key: `lsp:type:{file_hash}:{line}`
   - TTL: 300s
   - Redis integration (reuse existing RedisCache)

2. **Tests** (1 hour)
   - `test_cache_hit()`
   - `test_cache_miss()`
   - `test_cache_invalidation()`

**Deliverables**:
- ✅ Cached type extraction
- ✅ 3 tests passing

---

### Phase 5: Call Resolution (Story 13.5) - 2 pts

**Duration**: 0.5 day

**Tasks**:
1. **Enhance GraphConstructionService** (2 hours)
   - Update `_resolve_call_target()`
   - Add LSP-resolved path priority
   - Fallback to name_path + tree-sitter

2. **Tests** (1 hour)
   - `test_lsp_call_resolution()`
   - `test_fallback_to_name_path()`

**Deliverables**:
- ✅ Enhanced call resolution
- ✅ 2 tests passing

---

### Total Implementation Time

**Estimated**: 5-6 days (senior developer)

**Breakdown**:
- Phase 1 (Infrastructure): 2-3 days
- Phase 2 (Type Extraction): 1-2 days
- Phase 3 (Lifecycle): 1 day
- Phase 4 (Caching): 0.5 day
- Phase 5 (Call Resolution): 0.5 day

**Buffer**: Add 20% for unexpected issues (1 day) → **6-7 days total**

---

## ✅ Pre-Implementation Checklist

### Environment Setup
- [ ] Add Pyright to Dockerfile
- [ ] Test Pyright installation in Docker
- [ ] Verify Pyright version compatibility (1.1.350)
- [ ] Add `ENABLE_LSP` environment variable

### Architecture Validation
- [ ] Review JSON-RPC protocol implementation
- [ ] Validate timeout strategy (3s per query)
- [ ] Confirm graceful degradation approach
- [ ] Review circuit breaker integration

### Testing Strategy
- [ ] Define validation dataset (100+ type extraction cases)
- [ ] Plan performance benchmarks (indexing speed)
- [ ] Design crash recovery tests
- [ ] Create accuracy measurement tests

### Documentation
- [ ] Update CLAUDE.md with LSP integration notes
- [ ] Document LSP configuration (pyrightconfig.json)
- [ ] Add troubleshooting guide for LSP failures
- [ ] Update API documentation (new /v1/lsp endpoints)

### Risk Mitigation
- [ ] Implement LSP circuit breaker (reuse EPIC-12)
- [ ] Add LSP failure logging to error_logs
- [ ] Create LSP health monitoring dashboard
- [ ] Define LSP SLA targets (>99% availability)

---

## 🎯 Success Criteria (Validation)

### Functional Requirements
- ✅ LSP server starts successfully (<500ms)
- ✅ Hover queries return type information
- ✅ Type metadata merged into chunks
- ✅ LSP failures degrade gracefully (no pipeline crashes)
- ✅ Auto-restart works after crashes
- ✅ Health endpoint returns accurate status
- ✅ Caching reduces query latency (10×)

### Performance Requirements
- ✅ LSP query latency: <100ms (uncached)
- ✅ LSP query latency: <1ms (cached)
- ✅ Cache hit rate: >80% (re-indexing)
- ✅ Indexing overhead: <2× (with caching)
- ✅ LSP server startup: <500ms

### Accuracy Requirements
- ✅ Type coverage: >90% (for typed Python code)
- ✅ Call resolution accuracy: >95% (from 70%)
- ✅ Import tracking: 100% (LSP-verified)
- ✅ Signature parsing accuracy: >95%

### Reliability Requirements
- ✅ LSP availability: >99% (with auto-restart)
- ✅ Graceful degradation: 100% (no crashes)
- ✅ Auto-restart success rate: >90%
- ✅ Circuit breaker prevents cascading failures

---

## 🚀 Go/No-Go Decision

### ✅ GO - Proceed with Implementation

**Rationale**:
1. ✅ **Dependencies satisfied**: EPIC-11 + EPIC-12 complete (36/36 pts)
2. ✅ **Architecture validated**: JSON-RPC protocol well-understood
3. ✅ **Risks mitigated**: Graceful degradation + circuit breakers + auto-restart
4. ✅ **Scope reasonable**: 21 pts for 6-7 days work (senior dev)
5. ✅ **High value**: Transforms MnemoLite from syntax to semantic analysis

**Recommendation**: **START IMPLEMENTATION** with Phase 1 (LSP client infrastructure)

**Critical Success Factors**:
1. Implement graceful degradation FIRST (Story 13.1)
2. Test with real Pyright server early (don't mock)
3. Monitor performance metrics continuously
4. Validate accuracy with test dataset

---

## 📝 Next Steps (Immediate Actions)

1. **Add Pyright to Dockerfile** (5 min)
2. **Test Pyright installation** (5 min)
3. **Create Story 13.1 branch** (`feature/epic-13-story-13.1-lsp-client`)
4. **Start implementation** of PyrightLSPClient

---

**Prepared by**: Claude Code (Ultrathink Mode)
**Date**: 2025-10-22
**Status**: ✅ READY FOR IMPLEMENTATION

🤖 Generated with [Claude Code](https://claude.com/claude-code)
