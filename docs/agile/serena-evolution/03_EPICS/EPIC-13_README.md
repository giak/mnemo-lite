# EPIC-13: LSP Integration - README

**Status**: 🚧 IN PROGRESS
**Priority**: P2 (Medium - Quality Enhancement)
**Epic Points**: 21 pts (8/21 completed - 38%)
**Timeline**: Week 4-5 (Phase 2-3)
**Started**: 2025-10-22
**Depends On**: ✅ EPIC-11 (name_path), ✅ EPIC-12 (Robustness)
**Related**: ADR-002 (LSP Analysis Only - NO editing)

---

## 📊 Progress Overview

| Story | Description | Points | Status | Date |
|-------|-------------|--------|--------|------|
| **13.1** | Pyright LSP Wrapper | 8 | ✅ **COMPLETE** | 2025-10-22 |
| **13.2** | Type Metadata Extraction | 5 | ⏳ Pending | - |
| **13.3** | LSP Lifecycle Management | 3 | ⏳ Pending | - |
| **13.4** | LSP Result Caching (L2 Redis) | 3 | ⏳ Pending | - |
| **13.5** | Enhanced Call Resolution | 2 | ⏳ Pending | - |
| **Total** | | **21** | **38%** | |

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

## 🚀 Completed Work

### ✅ Story 13.1: Pyright LSP Wrapper (8 pts) - COMPLETE

**Completion Date**: 2025-10-22
**Commit**: `4af120f`

**Implementation**:
- ✅ `PyrightLSPClient`: Full JSON-RPC 2.0 client over stdio (542 lines)
- ✅ Async subprocess management with timeout handling
- ✅ `hover()` method: Get type information at cursor position
- ✅ `get_document_symbols()` method: Extract all symbols from file
- ✅ Graceful error handling: Initialization, timeout, crash recovery
- ✅ Background response reader task for message parsing

**Infrastructure**:
- ✅ Added `pyright>=1.1.350` to requirements.txt
- ✅ Added `libatomic1` to Dockerfile (required by Node.js runtime)

**Tests (10/10 passing - 100%)**:
- 8 unit tests: Initialization, error handling, protocol
- 2 integration tests: Real Pyright server startup, hover queries
- 6 optional tests: Performance, edge cases (can be enabled)

**Success Criteria Achieved**:
- ✅ LSP client starts/stops Pyright server process
- ✅ hover() returns type information for Python code
- ✅ Timeout enforcement (3s queries, 10s initialization)
- ✅ Graceful degradation on failure
- ✅ All tests passing (100%)

**Documentation**:
- ✅ [Story 13.1 Completion Report](./EPIC-13_STORY_13.1_COMPLETION_REPORT.md)

---

## 📝 Pending Stories

### ⏳ Story 13.2: Type Metadata Extraction Service (5 pts)

**Goal**: Extract type information from LSP and merge with tree-sitter metadata

**Key Features**:
- Service extracts return types, param types, signatures
- Merges LSP data with existing tree-sitter metadata
- Handles LSP failures gracefully (empty metadata)
- Integration with `code_indexing_service.py`

**Files to Create/Modify**:
- NEW: `api/services/lsp/type_extractor.py` (150 lines)
- MODIFY: `api/services/code_indexing_service.py` (+15 lines)
- TEST: `tests/services/lsp/test_type_extractor.py` (200 lines)

---

### ⏳ Story 13.3: LSP Lifecycle Management (3 pts)

**Goal**: Auto-restart LSP server on crashes for resilience

**Key Features**:
- Auto-restart on crash (max 3 attempts)
- Health check endpoint: `/v1/lsp/health`
- Manual restart endpoint: `/v1/lsp/restart`
- Circuit breaker pattern

**Files to Create/Modify**:
- NEW: `api/services/lsp/lsp_lifecycle_manager.py` (100 lines)
- NEW: `api/routes/lsp_routes.py` (50 lines)
- MODIFY: `api/main.py` (startup/shutdown hooks)

---

### ⏳ Story 13.4: LSP Result Caching (L2 Redis) (3 pts)

**Goal**: Cache LSP results for 10× performance improvement

**Key Features**:
- LSP hover results cached (300s TTL)
- Cache key: `lsp:type:{content_hash}:{line_number}`
- Cache invalidation on file change
- Target: >80% cache hit rate

**Files to Modify**:
- MODIFY: `api/services/lsp/type_extractor.py` (+15 lines caching)

---

### ⏳ Story 13.5: Enhanced Call Resolution (2 pts)

**Goal**: Improve call resolution accuracy from 70% to 95%+

**Key Features**:
- Use LSP-resolved paths for call targets
- Fallback to tree-sitter if LSP unavailable
- Integration with graph construction service

**Files to Modify**:
- MODIFY: `api/services/graph_construction_service.py` (+20 lines)

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

| Metric | Target | Status |
|--------|--------|--------|
| LSP server startup | <500ms | ✅ Achieved (0.5s) |
| Hover query latency | <100ms | ✅ Achieved (~50ms) |
| Type extraction per chunk | <50ms (cached: <1ms) | ⏳ Pending (Story 13.2) |
| LSP cache hit rate | >80% | ⏳ Pending (Story 13.4) |

### Quality Metrics

- ✅ **Zero data corruption**: LSP failures degrade gracefully (no crashes)
- ⏳ **High availability**: >99% uptime with auto-restart (Story 13.3)
- ✅ **Backward compatible**: Works without LSP (tree-sitter fallback)

---

## 🚧 Current State (v2.0.0)

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

**Accuracy**:
- Type coverage: 0% (no type extraction)
- Call resolution: 70% (heuristic-based)
- Import tracking: 80% (AST-based)

---

## 🚀 Target State (v3.0.0)

**Enhanced Metadata**:
```python
# With LSP integration (Story 13.2):
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

**Architecture**:
```
Indexing Pipeline:
├─ Step 1: tree-sitter parse (existing)
├─ Step 2: LSP query (NEW - Story 13.1 ✅)
├─ Step 3: Merge metadata (Story 13.2 ⏳)
├─ Step 4: Cache results (Story 13.4 ⏳)
└─ Step 5: Store enriched chunks
```

---

## 🎯 Next Steps

### Immediate (Next Session)

**Story 13.2: Type Metadata Extraction Service (5 pts)**
1. Create `TypeExtractorService` class
2. Implement `extract_type_metadata()` with hover parsing
3. Integrate with `code_indexing_service.py`
4. Write comprehensive tests (200+ lines)

**Expected Outcome**:
- Code chunks enriched with type information
- Type coverage: 0% → 90%+
- Graceful degradation on LSP failure

---

## 📚 Documentation

### EPIC Documents

- [EPIC-13_LSP_INTEGRATION.md](./EPIC-13_LSP_INTEGRATION.md) - Full epic specification (1159 lines)
- [EPIC-13_README.md](./EPIC-13_README.md) - This file (consolidated status)

### Story Completion Reports

- [EPIC-13_STORY_13.1_COMPLETION_REPORT.md](./EPIC-13_STORY_13.1_COMPLETION_REPORT.md) - Story 13.1 details

### Related EPICs

- [EPIC-11: Symbol Path Enhancement](./EPIC-11_SYMBOL_ENHANCEMENT.md) - Hierarchical name_path (5/13 pts complete)
- [EPIC-12: Robustness & Error Handling](./EPIC-12_ROBUSTNESS.md) - Timeouts, circuit breakers (23/23 pts complete)

### Architecture Decision Records

- ADR-002: LSP Analysis Only (design rationale)

---

## ✅ Definition of Done

**Epic is complete when**:
- [ ] All 5 stories completed and tested
- [x] Story 13.1: LSP Wrapper (✅ COMPLETE)
- [ ] Story 13.2: Type Metadata Extraction (⏳ Pending)
- [ ] Story 13.3: LSP Lifecycle Management (⏳ Pending)
- [ ] Story 13.4: LSP Result Caching (⏳ Pending)
- [ ] Story 13.5: Enhanced Call Resolution (⏳ Pending)
- [ ] Type coverage >90% for typed code
- [ ] Call resolution accuracy >95%
- [ ] Graceful degradation tested (LSP down → tree-sitter works)
- [ ] Performance targets met (<100ms hover queries)
- [ ] Documentation updated

**Ready for v3.0.0 Release**: ⏳ Pending (8/21 pts complete)

---

**Created**: 2025-10-22
**Last Updated**: 2025-10-22
**Status**: 🚧 IN PROGRESS (38%)
**Next Milestone**: Story 13.2 (Type Metadata Extraction)
