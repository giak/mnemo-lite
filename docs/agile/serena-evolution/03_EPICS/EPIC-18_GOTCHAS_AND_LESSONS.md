# EPIC-18: Gotchas and Lessons Learned

**Date**: 2025-10-23
**Status**: Documented
**Related**: EPIC-18 Stories 18.1-18.5 (TypeScript LSP Stability)

---

## 🎯 Purpose

Document critical gotchas discovered during EPIC-18 implementation to prevent future issues and maintain knowledge for the team.

---

## 🔴 Critical Gotchas Discovered

### GOTCHA-18.1: FastAPI Depends() Creates New LSP Processes Per Request

**Category**: Code Intelligence - LSP Integration
**Severity**: CRITICAL (causes system crash)

**Problem**:
```python
# ❌ WRONG: Creates NEW LSP process for EVERY request
def get_indexing_service(
    lsp_client: PyrightLSPClient = Depends(lambda: PyrightLSPClient()),  # NEW process!
    ts_lsp: TypeScriptLSPClient = Depends(lambda: TypeScriptLSPClient())  # NEW process!
):
    pass
```

**Impact**:
- After 10 requests: 20 LSP processes created, never closed
- File descriptors: 60+ (3 per process: stdin, stdout, stderr)
- Result: System resource exhaustion → API crash

**Solution** (Singleton Pattern):
```python
# ✅ CORRECT: Global singleton reused across ALL requests
_global_pyright_lsp: Optional[PyrightLSPClient] = None
_global_typescript_lsp: Optional[TypeScriptLSPClient] = None
_lsp_lock = asyncio.Lock()

async def get_or_create_global_lsp():
    global _global_pyright_lsp, _global_typescript_lsp

    async with _lsp_lock:  # Thread-safe
        if _global_pyright_lsp is None or not _global_pyright_lsp.is_alive():
            logger.info("🔧 Creating global Pyright LSP client (singleton)")
            _global_pyright_lsp = PyrightLSPClient()
            await _global_pyright_lsp.start()

        if _global_typescript_lsp is None or not _global_typescript_lsp.is_alive():
            logger.info("🔧 Creating global TypeScript LSP client (singleton)")
            _global_typescript_lsp = TypeScriptLSPClient(workspace_root="/tmp/lsp_workspace")
            await _global_typescript_lsp.start()

    return _global_pyright_lsp, _global_typescript_lsp
```

**Key Principles**:
1. **Global module-level variables** for singleton storage
2. **asyncio.Lock** for thread-safe initialization
3. **Lazy initialization** (created on first use)
4. **Auto-recovery** with `is_alive()` checks
5. **Graceful degradation** (TypeScript LSP failure doesn't crash API)

**Files Modified**:
- `api/routes/code_indexing_routes.py` (lines 51-97)

**Reference**: Story 18.1, 18.2, 18.3 in EPIC-18_STORY_18.2_TO_18.5_COMPLETION_REPORT.md

---

### GOTCHA-18.2: DualEmbeddingService Ignores EMBEDDING_MODE=mock

**Category**: Testing - Embedding Services
**Severity**: CRITICAL (breaks tests, causes timeouts)

**Problem**:
```python
# ❌ WRONG: DualEmbeddingService always loads real models (2.5GB, ~30s load)
embedding_service = DualEmbeddingService()  # Ignores EMBEDDING_MODE env var!
# → Even with EMBEDDING_MODE=mock, loads jinaai/jina-embeddings-v2-base-code
# → Test timeout after 30s
```

**Impact**:
- Tests take 413s for 100 files (vs 5.2s with mock)
- Loads 2.5GB HuggingFace models unnecessarily
- Frequent timeouts during indexing
- Stress tests fail due to resource exhaustion

**Solution**:
```python
# ✅ CORRECT: Check EMBEDDING_MODE and skip model loading
class DualEmbeddingService:
    def __init__(self, ...):
        self._embedding_mode = os.getenv("EMBEDDING_MODE", "real").lower()
        self._mock_mode = (self._embedding_mode == "mock")

        if self._mock_mode:
            logger.warning("🔶 DUAL EMBEDDING SERVICE: MOCK MODE 🔶")

    async def _ensure_text_model(self):
        if self._mock_mode:
            return  # Skip loading
        # ... real model loading

    async def _ensure_code_model(self):
        if self._mock_mode:
            return  # Skip loading
        # ... real model loading

    def _generate_mock_embedding(self, text: str) -> List[float]:
        # Deterministic hash-based mock embeddings
        import hashlib
        text_hash = int(hashlib.md5(text.encode()).hexdigest(), 16)
        rng = np.random.default_rng(text_hash % (2**32))
        mock_emb = rng.random(self.dimension).astype(np.float32)
        # Normalize to unit vector
        norm = np.linalg.norm(mock_emb)
        return (mock_emb / norm).tolist() if norm > 0 else mock_emb.tolist()

    async def generate_embedding(self, text: str, domain: EmbeddingDomain):
        if self._mock_mode:
            result = {}
            if domain in (EmbeddingDomain.TEXT, EmbeddingDomain.HYBRID):
                result['text'] = self._generate_mock_embedding(text + "_text")
            if domain in (EmbeddingDomain.CODE, EmbeddingDomain.HYBRID):
                result['code'] = self._generate_mock_embedding(text + "_code")
            return result
        # ... real embedding generation
```

**Key Principles**:
1. **Check EMBEDDING_MODE** in `__init__`
2. **Skip model loading** when `mock=true`
3. **Deterministic mock embeddings** (hash-based, reproducible)
4. **Support both single and batch** generation

**Results**:
- Test time: 413s → 5.2s (-98.7%, 80x faster)
- No timeouts
- No model loading in tests

**Files Modified**:
- `api/services/dual_embedding_service.py` (lines 111-164, 230-232, 285-287, 339-364, 378-381, 458-464, 571-590)

**Reference**: Discovered during Story 18.5 stress testing

---

### GOTCHA-18.3: asyncio.subprocess PIPE Buffer Deadlock

**Category**: Code Intelligence - LSP Integration
**Severity**: HIGH (preventive - didn't occur but could)

**Problem**:
```python
# ❌ RISKY: LSP process writes to stderr, buffer can fill up
self.process = await asyncio.create_subprocess_exec(
    "typescript-language-server", "--stdio",
    stdin=asyncio.subprocess.PIPE,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE  # ⚠️ Buffer can fill, causing deadlock!
)
# If stderr buffer fills and we never read it → process hangs forever
```

**Impact** (Potential):
- LSP process hangs when stderr buffer fills (32KB typical)
- API becomes unresponsive for TypeScript indexing
- Silent failure (no error, just hang)

**Solution** (Stderr Drain):
```python
# ✅ CORRECT: Drain stderr continuously
class TypeScriptLSPClient:
    def __init__(self):
        self._stderr_task: Optional[asyncio.Task] = None  # Track drain task

    async def start(self):
        self.process = await asyncio.create_subprocess_exec(...)

        # Start background task to drain stderr
        self._stderr_task = asyncio.create_task(self._drain_stderr())

    async def _drain_stderr(self):
        """Drain stderr to prevent PIPE buffer deadlock."""
        if not self.process or not self.process.stderr:
            return
        try:
            while True:
                chunk = await self.process.stderr.read(1024)
                if not chunk:
                    break
                stderr_text = chunk.decode('utf-8', errors='ignore').strip()
                if stderr_text:
                    logger.debug("TypeScript LSP stderr", message=stderr_text[:200])
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("Error draining TypeScript LSP stderr", error=str(e))

    async def shutdown(self):
        # Cancel stderr drain task
        if self._stderr_task and not self._stderr_task.done():
            self._stderr_task.cancel()
            try:
                await self._stderr_task
            except asyncio.CancelledError:
                pass

        # Use communicate() instead of wait() to flush pipes
        await asyncio.wait_for(self.process.communicate(), timeout=5.0)
```

**Key Principles**:
1. **Always drain stderr** for subprocess with PIPE
2. **Background asyncio.Task** for continuous drainage
3. **Use communicate()** instead of wait() during shutdown
4. **Cancel drain task** in shutdown to prevent resource leak

**Files Modified**:
- `api/services/lsp/typescript_lsp_client.py` (lines 74, 104, 596-632, 653-656, 679-685)
- `api/services/lsp/lsp_client.py` (similar changes for Pyright)

**Reference**: Story 18.4 (preventive fix)

---

## 📊 Impact Summary

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Files Indexed (success rate) | 26.7% | 100% | +274% |
| LSP Processes | 16+ (leak) | 2 (singleton) | -87.5% |
| Test Time (100 files) | 413s | 5.2s | -98.7% (80x) |
| API Crashes | After 10 files | Never | Eliminated |
| Timeouts | Frequent | None | Eliminated |

---

## 🎓 Lessons Learned

### 1. **FastAPI Dependency Injection is NOT Singleton by Default**

FastAPI's `Depends()` creates a **new instance** for each request unless you explicitly manage lifecycle. For expensive resources (LSP processes, DB connections), use:
- Global module-level variables
- Application lifespan events (`@app.on_event("startup")`)
- Manual singleton pattern with locks

**Don't assume**: `Depends(MyService)` is NOT equivalent to Spring's `@Singleton` or Angular's `@Injectable({ providedIn: 'root' })`

---

### 2. **EMBEDDING_MODE=mock Must Be Universally Supported**

Any service that loads ML models MUST check `EMBEDDING_MODE`:
- Legacy `EmbeddingService` (sentence-transformers) ✅ Supports mock
- New `DualEmbeddingService` (TEXT+CODE) ❌ Didn't support mock (FIXED in EPIC-18)

**Testing impact**: Without mock mode, tests become 80x slower and consume 2.5GB RAM.

**Pattern to follow**:
```python
def __init__(self):
    self._mock_mode = os.getenv("EMBEDDING_MODE", "real").lower() == "mock"
    if self._mock_mode:
        return  # Skip expensive initialization
```

---

### 3. **Subprocess PIPE Buffers Are Limited (32KB)**

When using `asyncio.subprocess` with PIPE:
- **Always drain stderr/stdout** if subprocess writes to them
- **Use communicate()** instead of wait() during shutdown
- **Background task** for continuous drainage

**Why it matters**:
- Pyright LSP writes progress to stderr
- TypeScript LSP writes logs to stderr
- Buffer fills → subprocess blocks forever

---

### 4. **Progressive Validation is Essential for Complex Changes**

EPIC-18 validation strategy that uncovered issues:
1. ✅ Manual testing (30 files) - Found LSP singleton working
2. ✅ Integration tests (Story 11.3) - Passed 10/10
3. ✅ Stress test (100 files) - **UNCOVERED DualEmbedding mock issue**

**Lesson**: Don't stop at unit tests. Real-world stress testing reveals integration issues.

---

### 5. **Deterministic Mock Data Enables Reproducible Tests**

Mock embeddings using **hash-based seeds** ensure:
- Same input → same embedding (every time)
- Tests are reproducible
- Debugging is easier (no random failures)

**Implementation**:
```python
text_hash = int(hashlib.md5(text.encode()).hexdigest(), 16)
rng = np.random.default_rng(text_hash % (2**32))  # Deterministic
mock_emb = rng.random(dimension)
```

---

## 🔗 References

- **EPIC-18 README**: `docs/agile/EPIC-18_README.md`
- **Technical Deep-Dive**: `docs/agile/serena-evolution/03_EPICS/EPIC-18_TYPESCRIPT_LSP_STABILITY.md`
- **Story Reports**:
  - `docs/agile/serena-evolution/03_EPICS/EPIC-18_STORY_18.1_COMPLETION_REPORT.md`
  - `docs/agile/serena-evolution/03_EPICS/EPIC-18_STORY_18.2_TO_18.5_COMPLETION_REPORT.md`
- **Commit**: `3891d5b` - "feat(EPIC-18): Fix LSP process leak + Add EMBEDDING_MODE=mock support"

---

## 📝 Integration with Existing Gotchas

These gotchas should eventually be integrated into:
- `skill:mnemolite-gotchas` → Code Intelligence section
  - Add **CODE-07**: LSP Singleton Pattern (FastAPI Depends)
  - Add **CODE-08**: DualEmbedding Mock Mode Support
  - Add **CODE-09**: Subprocess PIPE Stderr Drainage
- Update **Quick Reference by Symptom** table with:
  - "LSP process leak" → CODE-07
  - "Tests timeout on embeddings" → CODE-08
  - "LSP hangs indefinitely" → CODE-09

**Note**: Skill integration deferred to avoid modifying 1212-line file during EPIC completion.

---

**Document Version**: 1.0.0
**Author**: Claude Code (EPIC-18 Completion)
**Date**: 2025-10-23
