# ADR-002: LSP for Analysis Only (No Code Editing)

**Status**: 🟢 ACCEPTED
**Date**: 2025-10-19
**Deciders**: Architecture team
**Related**: EPIC-13 (LSP Analysis Integration)

---

## Context & Problem Statement

MnemoLite v2.0.0 uses **tree-sitter** for code parsing and chunking. This provides:
- ✅ Syntax tree (AST)
- ✅ Function/class boundaries
- ✅ Fast parsing (<50ms/file)

**However, tree-sitter is fundamentally limited:**

**Missing Critical Metadata** (v2.0.0 gaps):
1. **Type Information**: No type resolution
   - `def calculate(x, y) -> ???` - Cannot infer return type without executing
   - `user = User(...)` - Cannot resolve `User` class definition
   - Generic types: `List[Dict[str, Any]]` - Parsed as string, not structured

2. **Import Resolution**: No cross-file analysis
   - `from utils import calculate_total` - Cannot find `calculate_total` definition
   - Relative imports: `from ..models import User` - No path resolution
   - Ambiguous names: `User` could be local class or imported

3. **Symbol Definitions**: No go-to-definition
   - Function calls: `foo()` - Which `foo`? (local, imported, builtin?)
   - Method calls: `obj.method()` - Which class is `obj`?
   - No hover documentation (docstrings, signatures)

**Business Impact**:
- **Search precision**: Cannot filter by return type (e.g., "find functions returning List[User]")
- **Dependency accuracy**: graph_construction_service.py resolution ~70% (many false negatives)
- **Developer UX**: No type-aware code intelligence
- **Maintenance**: Manual metadata extraction (brittle heuristics)

**Measured Pain Points** (v2.0.0 benchmarks):
- Call resolution accuracy: ~70% (30% of calls unresolved due to import ambiguity)
- Type metadata: 0% (completely missing)
- Cross-file symbol linking: Manual heuristics (fragile)

**Question**: How do we get precise type information and symbol resolution without re-implementing a type checker?

---

## Decision

Use **LSP (Language Server Protocol) for ANALYSIS ONLY** - Extract type metadata, DO NOT implement code editing.

### Scope: IN vs OUT

**✅ IN SCOPE (Analysis)**:
1. **Type Information Extraction**
   ```python
   # Query LSP for:
   - Function signatures: def foo(x: int) -> str
   - Return types: inferred from type checker
   - Variable types: x: User = get_user()
   - Generic parameters: List[Dict[str, Any]]
   ```

2. **Symbol Resolution**
   ```python
   # Query LSP for:
   - Go-to-definition: foo() → /path/to/file.py:42
   - Find references: User class → all usage locations
   - Import resolution: from utils import X → /utils.py:X
   - Hover documentation: docstrings, type hints
   ```

3. **Workspace Indexing**
   ```python
   # Query LSP for:
   - Document symbols: All functions/classes in file
   - Workspace symbols: Global symbol search
   - Diagnostics: Type errors, unused imports (optional)
   ```

**❌ OUT OF SCOPE (Editing)**:
1. **Code Modifications** (Serena territory)
   ```python
   # NOT IMPLEMENTED:
   - replace_body(): Modify function implementation
   - rename_symbol(): Rename across workspace
   - apply_fix(): Auto-fix type errors
   - format_code(): Code formatting
   ```

2. **Interactive Editing**
   ```python
   # NOT IMPLEMENTED:
   - Completion: Auto-complete suggestions
   - Code actions: Quick fixes, refactorings
   - Signature help: Live parameter hints
   - Incremental updates: didChange notifications
   ```

**Rationale for Analysis-Only**:
- **Timeline**: Editing = 3+ months complexity vs Analysis = 3-4 weeks
- **Maintenance**: Editing requires tracking file changes, conflict resolution, undo/redo
- **Scope**: MnemoLite = "code memory", NOT "code editor" (that's Serena's job)
- **Risk**: Editing introduces breaking changes, data corruption risks
- **Value**: 80% of value (type info, resolution) with 20% of complexity

### LSP Server: Pyright (Primary)

**Choice**: Pyright LSP server for Python

**Why Pyright**:
1. **Fast**: 10-50ms for type checking (vs 200-500ms for mypy)
2. **Accurate**: Microsoft's official Python type checker (powers VS Code)
3. **Standalone**: Runs as subprocess, no IDE dependency
4. **Well-documented**: LSP protocol compliance, stable API
5. **Widely used**: Battle-tested (millions of VS Code users)

**⚠️ Version Pinning Required** (2024 performance regression):

Pyright v316+ has known performance degradation (50-200% slower on large codebases):

```bash
# ❌ AVOID: Pyright v316+ (performance regression)
npm install -g pyright@latest

# ✅ RECOMMENDED: Pin to Pyright v315 (last stable before regression)
npm install -g pyright@1.1.315

# ✅ ALTERNATIVE: Basedpyright (community fork, regression fixed)
npm install -g basedpyright
```

**Performance Comparison** (2024):

| Tool | Speed vs mypy | Memory (100k LOC) | Version | Status |
|------|---------------|-------------------|---------|--------|
| Pyright v315 | 3-5× faster | 500MB | 1.1.315 | ✅ Stable |
| Pyright v316+ | 1.5-2× faster | 2GB | Latest | ⚠️ Regression |
| Basedpyright | 3-5× faster | 500MB | Latest | ✅ Stable |
| mypy | 1× (baseline) | 300MB | Latest | ✅ Stable |

**Recommended Installation** (Dockerfile):

```dockerfile
# Pin to Pyright v315 (avoid regression)
RUN npm install -g pyright@1.1.315

# Optimize cold start with --createstubs flag
CMD ["pyright-langserver", "--stdio", "--createstubs"]
```

**Memory Requirements** (2024 benchmarks):
- Small codebase (<10k LOC): 200-300MB RAM
- Medium codebase (10k-100k LOC): 500MB-1GB RAM
- Large codebase (100k+ LOC): 1-2GB RAM

**Mitigation Strategy**:
1. Pin to Pyright v315 (primary approach)
2. Basedpyright as fallback (if v315 has issues)
3. Use `--createstubs` flag (50% faster cold starts)
4. Cache LSP results in Redis (EPIC-13.4) → 90%+ cache hit rate

**Alternatives considered**:
- **mypy**: Slower (200-500ms), less LSP-native
- **Jedi**: No type inference (only completion)
- **Pylance**: Proprietary (VS Code extension, not standalone)
- **Basedpyright**: Community fork (faster issue resolution, 100% compatible)

### Integration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   MnemoLite v3.0                            │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Code Indexing Service                               │  │
│  │                                                      │  │
│  │  ┌────────────┐   ┌────────────┐   ┌────────────┐  │  │
│  │  │tree-sitter │ → │  LSP Query │ → │  Metadata  │  │  │
│  │  │   Parse    │   │   Service  │   │ Extractor  │  │  │
│  │  │            │   │            │   │            │  │  │
│  │  │  AST       │   │  Types     │   │  Merged    │  │  │
│  │  │  Chunks    │   │  Symbols   │   │  Metadata  │  │  │
│  │  │  Bounds    │   │  Imports   │   │            │  │  │
│  │  └────────────┘   └────────────┘   └────────────┘  │  │
│  │         │                 │                 │       │  │
│  │         └─────────────────┴─────────────────┘       │  │
│  │                          ↓                          │  │
│  │                 ┌──────────────────┐                │  │
│  │                 │  CodeChunkModel  │                │  │
│  │                 │  with Types      │                │  │
│  │                 └──────────────────┘                │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  LSP Query Service (NEW)                             │  │
│  │                                                      │  │
│  │  ┌────────────────────────────────────────────────┐ │  │
│  │  │  Pyright LSP Server (subprocess)               │ │  │
│  │  │  - Type inference                              │ │  │
│  │  │  - Symbol resolution                           │ │  │
│  │  │  - Import tracking                             │ │  │
│  │  └────────────────────────────────────────────────┘ │  │
│  │         ↑                                            │  │
│  │         │ JSON-RPC (stdio)                           │  │
│  │         ↓                                            │  │
│  │  ┌────────────────────────────────────────────────┐ │  │
│  │  │  LSP Client (Python)                           │ │  │
│  │  │  - Request manager                             │ │  │
│  │  │  - Response cache (MD5-based, ADR-001)        │ │  │
│  │  │  - Error handling (graceful degradation)      │ │  │
│  │  └────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Query Flow (Read-Only)

```python
# Example: Index a Python file
async def index_file(file_path: str, source_code: str):
    # STEP 1: tree-sitter parse (existing)
    chunks = await tree_sitter_service.chunk_code(source_code, "python")
    # Result: [{type: "function", name: "calculate", start: 10, end: 20}, ...]

    # STEP 2: LSP query for types (NEW)
    lsp_metadata = await lsp_query_service.get_file_metadata(file_path, source_code)
    # Result: {
    #   "calculate": {
    #     "signature": "def calculate(x: int, y: int) -> float",
    #     "return_type": "float",
    #     "param_types": {"x": "int", "y": "int"},
    #     "docstring": "Calculate the sum..."
    #   }
    # }

    # STEP 3: Merge metadata (existing + enhanced)
    for chunk in chunks:
        if chunk.name in lsp_metadata:
            chunk.metadata.update({
                "signature": lsp_metadata[chunk.name]["signature"],
                "return_type": lsp_metadata[chunk.name]["return_type"],
                "param_types": lsp_metadata[chunk.name]["param_types"],
                "docstring": lsp_metadata[chunk.name]["docstring"],
            })

    # STEP 4: Store (existing)
    await code_chunk_repository.create_many(chunks)
```

**Key Design Decisions**:
1. **Read-only LSP**: Only `textDocument/*` requests (hover, definition, symbols)
2. **No `didChange`**: LSP sees files as immutable snapshots (no incremental updates)
3. **Stateless**: Each file processed independently (no workspace state)
4. **Cache-friendly**: MD5 hash → skip LSP query if file unchanged (ADR-001)

---

## Alternatives Considered

### Alternative 1: Full LSP Integration (Editing + Analysis)

**Approach**: Implement complete LSP client with editing capabilities (Serena-style)

**Pros**:
- Complete feature parity with IDEs
- Could offer rename, refactor, auto-fix
- Single source of truth for code modifications

**Cons**:
- ❌ **Timeline**: 3-4 months vs 3-4 weeks (10× longer)
- ❌ **Complexity**: Incremental updates, conflict resolution, undo/redo
- ❌ **Maintenance**: Breaking changes, LSP spec evolution (new versions)
- ❌ **Risk**: Data corruption (modifying user code)
- ❌ **Out of scope**: MnemoLite = memory, NOT editor

**Verdict**: **REJECTED** - Timeline and complexity unacceptable (user requirement: 1 month)

---

### Alternative 2: tree-sitter Only (Status Quo)

**Approach**: Continue using tree-sitter AST parsing without type information

**Pros**:
- Simple (already implemented)
- Fast (<50ms/file)
- No external dependencies
- Zero maintenance

**Cons**:
- ❌ **No type info**: Cannot infer return types, parameter types
- ❌ **Weak resolution**: 70% call resolution accuracy (30% false negatives)
- ❌ **No cross-file analysis**: Cannot resolve imports
- ❌ **Poor search**: Cannot filter by type (e.g., "functions returning User")

**Verdict**: **REJECTED** - Insufficient for code intelligence goals (target: 95%+ resolution)

---

### Alternative 3: Static Analysis (mypy, pytype)

**Approach**: Run mypy/pytype as subprocess, parse output for type info

**Pros**:
- Accurate type inference
- Mature tools (mypy = de facto standard)
- No LSP complexity

**Cons**:
- ⚠️ **Slow**: mypy = 200-500ms/file (vs Pyright 10-50ms)
- ⚠️ **Output parsing**: Fragile (CLI output format changes)
- ⚠️ **No symbol resolution**: mypy doesn't expose go-to-definition
- ⚠️ **Limited API**: CLI-only, no programmatic access to type graph

**Verdict**: **REJECTED** - Slower and less featureful than Pyright LSP

---

### Alternative 4: AST + Type Hint Extraction (Heuristic)

**Approach**: Parse type hints from AST using `ast.parse()`, resolve manually

**Example**:
```python
import ast

def extract_return_type(func_node: ast.FunctionDef) -> str:
    if func_node.returns:
        return ast.unparse(func_node.returns)  # "List[Dict[str, Any]]"
    return "Unknown"
```

**Pros**:
- Fast (same as tree-sitter, <50ms)
- No external dependencies
- Simple implementation

**Cons**:
- ❌ **Incomplete**: Only works for explicit type hints (misses inferred types)
- ❌ **No resolution**: `User` could be `models.User` or `utils.User` (ambiguous)
- ❌ **Generic types**: `List[User]` parsed as string, not structured
- ❌ **No validation**: Cannot detect type errors

**Example failure**:
```python
# Heuristic approach:
def calculate(x, y):  # No type hints → "Unknown" return type
    return x + y  # Could be int, float, str, ...

# LSP approach:
# Pyright infers: def calculate(x: int, y: int) -> int
```

**Verdict**: **REJECTED** - Insufficient type coverage (<30% of real-world code has explicit hints)

---

### Alternative 5: Jedi (Python Completion Library)

**Approach**: Use Jedi for type inference and completion

**Pros**:
- Python library (no subprocess)
- Fast (50-100ms)
- Good for completion

**Cons**:
- ⚠️ **Weak type inference**: No type checker (just heuristics)
- ⚠️ **No LSP**: Not LSP-compliant (custom API)
- ⚠️ **Maintenance**: Jedi development slowed (vs Pyright active)

**Verdict**: **REJECTED** - Pyright LSP more accurate and future-proof

---

## Consequences

### Positive

**Type-Aware Code Intelligence** (estimated from Pyright benchmarks):
1. **Enhanced Metadata**: 100% type coverage (vs 0% in v2.0.0)
   ```python
   # Before (v2.0.0):
   {
     "name": "calculate",
     "signature": "calculate(x, y)",  # No types
     "return_type": null
   }

   # After (v3.0):
   {
     "name": "calculate",
     "signature": "def calculate(x: int, y: int) -> float",
     "return_type": "float",
     "param_types": {"x": "int", "y": "int"},
     "docstring": "Calculate the weighted sum..."
   }
   ```

2. **Improved Search Precision**: Type-based filtering
   ```python
   # Query: "Find all functions returning List[User]"
   # v2.0.0: Cannot filter by return type (returns all functions)
   # v3.0: Precise filtering → 10× fewer false positives
   ```

3. **Better Call Resolution**: 95%+ accuracy (vs 70% in v2.0.0)
   ```python
   # Before: Ambiguous call resolution
   foo()  # Which foo? Local or imported? (70% accuracy)

   # After: LSP go-to-definition
   foo() → /utils.py:calculate_total (95% accuracy)
   ```

4. **Cross-Repository Intelligence**:
   - Resolve imports across repositories
   - Track dependency chains with type info
   - Detect breaking changes (type signature changes)

**Performance** (Pyright benchmarks):
- Type checking: 10-50ms/file (acceptable overhead)
- Cached queries: ~1ms (MD5 hash hit, ADR-001)
- Batch processing: 100 files in 1-5 seconds

**Scalability**:
- Pyright handles 10k+ file repositories
- LSP server can be reused across multiple files (workspace mode)
- Cache hit rate expected: 90%+ (files rarely change types)

**Developer Experience**:
- IDE-quality metadata without IDE dependency
- Consistent type info across tools (same Pyright used in VS Code)
- Future-proof (LSP protocol stable, widely adopted)

### Negative

**Complexity Added**:
- New dependency: Pyright LSP server (requires Node.js/npm or binary)
- LSP protocol implementation (JSON-RPC over stdio)
- Process management (start/stop Pyright server)
- Error handling (LSP server crashes, timeouts)

**Operational Overhead**:
- Pyright installation (Docker image size +50MB)
- LSP server startup time (~500ms cold start, 250ms with --createstubs)
- Memory overhead (500MB-2GB RAM depending on codebase size)
  - Small codebase (<10k LOC): 200-300MB
  - Medium codebase (10k-100k LOC): 500MB-1GB
  - Large codebase (100k+ LOC): 1-2GB

**Limitations** (Read-Only LSP):
- Cannot modify code (by design)
- No incremental updates (each file processed independently)
- No workspace state (stateless queries only)
- No diagnostics aggregation (no "workspace errors" view)

**Risk Mitigation**:
1. **LSP server failure** → Graceful degradation to tree-sitter only
   ```python
   try:
       lsp_metadata = await lsp_query_service.get_metadata(file_path)
   except LSPError:
       logger.warning("LSP unavailable, falling back to tree-sitter only")
       lsp_metadata = {}  # Continue without type info
   ```

2. **Slow LSP response** → Timeout + cache
   ```python
   @timeout(5.0)  # 5s max (from Serena thread.py pattern)
   async def query_lsp(file_path: str):
       return await lsp_client.request("textDocument/hover", ...)
   ```

3. **Type errors in user code** → Skip type info for that symbol
   ```python
   # If Pyright reports type error, store error in metadata
   {
     "name": "buggy_function",
     "type_error": "Cannot infer return type: incompatible types"
   }
   ```

**Cost**:
- Docker image size: +50MB (Pyright binary)
- Memory: +100-200MB (LSP server process)
- Indexing time: +10-50ms/file (acceptable for v3.0 targets)

---

## Implementation Plan

### Phase 1: LSP Client Foundation (Week 1 - Story 13.1)

**Story 13.1**: Pyright LSP client wrapper (13 pts)
- Setup Pyright as subprocess (stdio transport)
- Implement JSON-RPC protocol (initialize, textDocument/* requests)
- Add timeout execution (from Serena thread.py pattern)
- Add graceful error handling (fallback to tree-sitter)

**Files to create/modify**:
```
NEW: api/services/lsp/lsp_client.py
NEW: api/services/lsp/lsp_protocol.py (JSON-RPC types)
NEW: api/services/lsp/pyright_service.py (Pyright-specific)
NEW: api/utils/timeout.py (from Serena thread.py)
MODIFY: docker-compose.yml (add Pyright installation)
MODIFY: Dockerfile (install Node.js + Pyright)
TEST: tests/services/lsp/test_lsp_client.py
```

**Expected impact**: Pyright LSP queries working (foundation for type extraction)

---

### Phase 2: Type Metadata Extraction (Week 2 - Story 13.2)

**Story 13.2**: Extract type info from LSP (8 pts)
- Query `textDocument/hover` for type signatures
- Query `textDocument/definition` for symbol resolution
- Query `textDocument/documentSymbol` for all symbols in file
- Merge LSP metadata with tree-sitter chunks

**Files to create/modify**:
```
NEW: api/services/lsp/type_extractor.py
MODIFY: api/services/metadata_extractor_service.py (integrate LSP)
MODIFY: api/models/code_chunk_models.py (add type fields)
TEST: tests/services/lsp/test_type_extractor.py
```

**Expected impact**: Type signatures in code_chunks.metadata

---

### Phase 3: Import Resolution (Week 3 - Story 13.3)

**Story 13.3**: Resolve imports via LSP (8 pts)
- Use `textDocument/definition` for import resolution
- Track cross-file dependencies
- Update graph_construction_service.py (use LSP-resolved imports)
- Improve call resolution accuracy (target: 95%+)

**Files to create/modify**:
```
MODIFY: api/services/graph_construction_service.py (use LSP data)
MODIFY: api/services/lsp/type_extractor.py (add import resolution)
TEST: tests/services/test_graph_construction_enhanced.py
```

**Expected impact**: Call resolution 70% → 95%+

---

### Phase 4: Cache Integration (Week 4 - Story 13.4)

**Story 13.4**: MD5-based LSP cache (5 pts)
- Cache LSP responses by file content hash (ADR-001)
- Skip LSP query if file unchanged (cache hit)
- Invalidate on file modification
- Monitor cache hit rate

**Files to create/modify**:
```
MODIFY: api/services/lsp/lsp_client.py (add cache layer)
MODIFY: api/services/caches/code_chunk_cache.py (integrate LSP cache)
TEST: tests/services/lsp/test_lsp_cache.py
```

**Expected impact**: 90%+ cache hit rate, 10-50ms → 1ms for cached files

---

### Phase 5: Monitoring & Metrics (Week 5 - Story 13.5)

**Story 13.5**: LSP performance monitoring (3 pts)
- Add metrics (LSP query latency, cache hit rate, errors)
- Add health check (LSP server status)
- Add fallback metrics (graceful degradation rate)

**Files to create/modify**:
```
NEW: api/services/lsp/lsp_metrics.py
MODIFY: api/routes/health.py (add LSP health check)
NEW: templates/partials/lsp_metrics.html
```

---

## Validation & Success Metrics

**KPIs** (must achieve to consider ADR successful):

| Metric | Current (v2.0) | Target (v3.0) | Measurement |
|--------|----------------|---------------|-------------|
| Type coverage | 0% | 100% | % of functions with return_type |
| Call resolution accuracy | 70% | 95%+ | % of calls correctly resolved |
| LSP query latency (cold) | N/A | <50ms | P95 latency |
| LSP query latency (cached) | N/A | <1ms | Median latency |
| LSP cache hit rate | N/A | >90% | Percentage |
| Search precision (type-filtered) | N/A | 10× fewer false positives | Query result count |
| Graceful degradation | N/A | <5% fallback rate | % of queries using fallback |

**Measurement Plan**:
1. Baseline benchmarks on v2.0.0 (current resolution accuracy)
2. Incremental benchmarks after each phase
3. A/B comparison (tree-sitter only vs tree-sitter + LSP)
4. Real-world repo testing (MnemoLite itself, 10k+ files repos)

**Rollback Plan**:
- If LSP overhead > 100ms/file → Disable LSP, fallback to tree-sitter
- If cache hit rate < 80% → Review cache key design
- If LSP server crashes > 1%/hour → Use tree-sitter only mode

---

## References

### External Resources

1. **LSP Specification**
   - https://microsoft.github.io/language-server-protocol/
   - https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/

2. **Pyright LSP Server**
   - https://github.com/microsoft/pyright
   - https://github.com/microsoft/pyright/blob/main/docs/command-line.md

3. **LSP Client Examples (Python)**
   - python-lsp-server: https://github.com/python-lsp/python-lsp-server
   - pygls (generic LSP library): https://github.com/openlawlibrary/pygls

4. **Type Inference Best Practices**
   - PEP 484 (Type Hints): https://peps.python.org/pep-0484/
   - Pyright Type Checking: https://github.com/microsoft/pyright/blob/main/docs/type-concepts.md

### Internal References

1. **Serena Analysis**
   - `/docs/agile/serena-evolution/02_RESEARCH/serena_deep_dive.md`
   - Pattern: LSP client with fine-grained locks (ls_handler.py:50-80)
   - Pattern: Process tree termination (ls.py:180-200)
   - Pattern: Timeout execution (thread.py:20-60)

2. **MnemoLite Current State**
   - `/CLAUDE.md` - v2.0.0 architecture (tree-sitter only)
   - `/api/services/metadata_extractor_service.py` - Current metadata extraction
   - `/api/services/graph_construction_service.py` - Call resolution (70% accuracy)

3. **Related ADRs**
   - ADR-001: Triple-Layer Cache Strategy (LSP cache integration)
   - ADR-003: Breaking Changes Approach - TBD
   - ADR-004: Symbol Name Path Strategy - TBD

---

## Notes

**Key Insights from Serena**:
1. LSP queries can be **cached by content hash** (same pattern as Serena ls.py:240-250)
2. **Timeout execution** prevents LSP server hangs on malformed files (thread.py)
3. **Fine-grained locks** for LSP requests prevent contention (ls_handler.py:50-80)
4. **Process tree termination** ensures LSP server cleanup on shutdown (ls.py:180-200)

**Key Differences from Serena**:
- **Serena**: Full LSP editing (replace_body, rename, apply_fix)
- **MnemoLite**: Analysis ONLY (hover, definition, symbols)
- **Why**: Timeline (1 month vs 3+ months), Scope (memory vs editor)

**Future Enhancements** (out of scope for v3.0):
- Multi-language support (TypeScript, Go, Rust LSP servers)
- Workspace-wide diagnostics (global type error tracking)
- LSP-based refactoring suggestions (read-only, no execution)
- Incremental LSP updates (didChange notifications for faster re-indexing)

**Critical Non-Goal**:
- ❌ **Code editing**: MnemoLite will NEVER modify user code via LSP
- ❌ **IDE replacement**: MnemoLite = code memory, NOT code editor
- ❌ **Serena competition**: Different scope (memory vs editing agent)

**Circuit Breaker Library** (2024 asyncio native):

For graceful LSP degradation (EPIC-12 Story 12.3), use **aiobreaker** (native asyncio support):

```python
from aiobreaker import CircuitBreaker

# Configure circuit breaker for LSP
lsp_breaker = CircuitBreaker(
    fail_max=5,              # Open after 5 consecutive failures
    timeout_duration=30,     # Stay open for 30s before retry
    exclude=[TimeoutError]   # Don't count timeouts as failures
)

@lsp_breaker
async def query_lsp_with_protection(file_path: str, line: int, char: int):
    """LSP query with circuit breaker protection."""
    try:
        return await asyncio.wait_for(
            lsp_client.hover(file_path, line, char),
            timeout=3.0
        )
    except asyncio.TimeoutError:
        logger.warning("LSP timeout, using fallback", file=file_path)
        return None  # Graceful degradation to tree-sitter only
```

**Why aiobreaker**:
- Native asyncio support (vs pybreaker's Tornado-based approach)
- Active development (2024-08 last release)
- Drop-in decorator pattern
- Installation: `pip install aiobreaker==1.4.1`

---

**Decision Date**: 2025-10-19
**Review Date**: 2025-11-19 (after implementation)
**Last Updated**: 2025-10-19 (added 2024 industry validation - Pyright v315 pinning, Basedpyright, --createstubs, aiobreaker)
**Status**: 🟢 ACCEPTED (ready for implementation)
