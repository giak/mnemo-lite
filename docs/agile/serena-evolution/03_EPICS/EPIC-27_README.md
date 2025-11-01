# EPIC-27: TypeScript Metadata Extraction Quality Improvement

**Status**: PLANNED
**Priority**: HIGH
**Start Date**: 2025-11-01
**Target Date**: TBD
**Owner**: Development Team

---

## 📋 Overview

Improve TypeScript call extraction quality to achieve 40-60% edge-to-node ratio in code graphs, up from current 9.3%.

**Current State** (CVGenerator, 240 TS files):
- ✅ 934 chunks indexed
- ✅ 581 nodes created
- ✅ 906 chunks (97%) have metadata
- ❌ Only 54 edges (9.3% ratio)

**Target State**:
- 🎯 40-60% edge ratio (230-350 edges)
- 🎯 50%+ call resolution rate
- 🎯 <30% framework noise
- 🎯 Clean, accurate function call extraction

---

## 🎯 Goals

1. **Fix Node Matching**: Add `name` field to node properties for proper resolution
2. **Clean Call Extraction**: Extract function names, not code fragments
3. **Reduce Noise**: Filter out test framework functions
4. **Improve Resolution**: Scope-aware symbol matching

---

## 📊 Success Metrics

| Metric | Baseline | Phase 1 Target | Phase 2 Target | Phase 3 Target |
|--------|----------|----------------|----------------|----------------|
| Edge Ratio | 9.3% (54/581) | 30% (174/581) | 50% (290/581) | 60% (348/581) |
| Call Resolution | ~1.5% | 20% | 50% | 70% |
| Clean Calls | 22% | 60% | 80% | 90% |
| Framework Noise | 78% | 50% | 30% | 20% |

---

## 📦 Stories Breakdown

### Phase 1: Quick Wins (Priority: HIGH, Est: 4h)

#### Story 27.1: Add `name` Field to Node Properties
**Priority**: CRITICAL
**Estimate**: 2h
**Dependencies**: None

**Acceptance Criteria**:
- [ ] Node creation adds `name` field to `properties` JSONB
- [ ] `name` field contains the same value as `label` (but not truncated)
- [ ] Index created on `properties->>'name'` for fast lookups
- [ ] Unit tests verify field is populated

**Technical Details**:
```python
# In graph_construction_service.py
node_properties = {
    "name": chunk.name,  # ← Add this
    "node_type": chunk.chunk_type,
    # ...
}
```

**Files to Modify**:
- `api/services/graph_construction_service.py`
- Add unit tests in `api/tests/services/test_graph_construction_service.py`

---

#### Story 27.2: Backfill Existing Nodes with Name Field
**Priority**: CRITICAL
**Estimate**: 1h
**Dependencies**: Story 27.1

**Acceptance Criteria**:
- [ ] Migration script created: `db/migrations/v8_to_v9_add_node_name_field.sql`
- [ ] All existing nodes updated with `name` from `label`
- [ ] Index created: `idx_nodes_name`
- [ ] Verification query shows 100% nodes have `name` field

**Migration Script**:
```sql
-- Backfill name from label
UPDATE nodes
SET properties = properties || jsonb_build_object('name', label)
WHERE properties->>'name' IS NULL;

-- Create index
CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes ((properties->>'name'));

-- Verify
SELECT COUNT(*) as total,
       COUNT(properties->>'name') as with_name
FROM nodes;
```

---

#### Story 27.3: Post-Processing Call Name Cleanup
**Priority**: HIGH
**Estimate**: 1h
**Dependencies**: None

**Acceptance Criteria**:
- [ ] `clean_call_name()` function implemented
- [ ] Handles chained calls: `"obj.method()"` → `"method"`
- [ ] Filters incomplete fragments: `"e('valid"` → `None`
- [ ] Applied to all extracted calls before storage
- [ ] Unit tests with 20+ examples

**Implementation**:
```python
def clean_call_name(raw_call: str) -> str | None:
    """Clean up extracted call expression."""
    if len(raw_call) < 2 or not raw_call[0].isalpha():
        return None

    # Handle chained calls
    if '.' in raw_call or '(' in raw_call:
        match = re.search(r'([a-zA-Z_$][a-zA-Z0-9_$]*)(?:\(|$)', raw_call)
        return match.group(1) if match else None

    return raw_call
```

**Files to Modify**:
- `api/services/metadata_extractors/typescript_extractor.py`
- Add tests in `api/tests/services/metadata_extractors/test_typescript_extractor.py`

---

### Phase 2: Enhanced Extraction (Priority: MEDIUM, Est: 2 days)

#### Story 27.4: Framework Function Blacklist
**Priority**: MEDIUM
**Estimate**: 4h
**Dependencies**: None

**Acceptance Criteria**:
- [ ] Blacklist of common test framework functions
- [ ] Vitest: `describe`, `it`, `expect`, `test`, `beforeEach`, `afterEach`, `vi`
- [ ] Matchers: `toBe`, `toEqual`, `toHaveBeenCalled`, `toContain`, etc.
- [ ] Configurable via config file
- [ ] Applied during extraction (not post-processing)
- [ ] Reduces extracted calls by 60-80%

**Blacklist File**: `api/config/framework_symbols.py`
```python
TYPESCRIPT_FRAMEWORK_SYMBOLS = {
    # Testing frameworks
    "describe", "it", "test", "expect", "beforeEach", "afterEach",
    "beforeAll", "afterAll", "vi", "jest", "mock",

    # Matchers
    "toBe", "toEqual", "toHaveBeenCalled", "toContain",
    "toHaveLength", "toBeDefined", "toBeTruthy", "toBeFalsy",

    # Common libraries (optional)
    "console.log", "console.error", "console.warn",
}
```

---

#### Story 27.5: Enhanced Tree-sitter Call Query
**Priority**: MEDIUM
**Estimate**: 6h
**Dependencies**: Story 27.4

**Acceptance Criteria**:
- [ ] New tree-sitter query extracts ONLY function names (not full expressions)
- [ ] Handles member expressions: `obj.method()` → `"method"`
- [ ] Handles constructor calls: `new Foo()` → `"Foo"`
- [ ] Integrates with blacklist filter
- [ ] Unit tests with 30+ TypeScript patterns
- [ ] Improves clean call rate from 22% to 60%+

**Query Structure**:
```python
ENHANCED_CALL_QUERY = """
; Direct function calls
(call_expression
  function: (identifier) @function.call
)

; Method calls - capture property only
(call_expression
  function: (member_expression
    property: (property_identifier) @method.call
  )
)

; Constructor calls
(new_expression
  constructor: (identifier) @constructor.call
)
"""
```

**Files to Modify**:
- `api/services/metadata_extractors/typescript_extractor.py`
- Add comprehensive tests

---

#### Story 27.6: Re-index CVGenerator and Validate
**Priority**: MEDIUM
**Estimate**: 2h
**Dependencies**: Stories 27.1-27.5

**Acceptance Criteria**:
- [ ] CVGenerator fully re-indexed with new extraction
- [ ] Graph stats show 30-50% edge ratio
- [ ] Validation report created comparing before/after
- [ ] Sample edges manually verified for correctness
- [ ] No regression in Python extraction

**Validation Script**: Create `scripts/validate_graph_quality.py`
```python
async def validate_graph_quality(repository: str):
    """Generate quality report for repository graph."""
    stats = await get_graph_stats(repository)

    return {
        "nodes": stats.total_nodes,
        "edges": stats.total_edges,
        "ratio": stats.total_edges / stats.total_nodes,
        "nodes_by_type": stats.nodes_by_type,
        "edges_by_type": stats.edges_by_type,
        "quality_score": calculate_quality_score(stats),
    }
```

---

### Phase 3: Scope-Aware Resolution (Priority: LOW, Est: 3 days)

#### Story 27.7: Project Symbol Registry
**Priority**: LOW
**Estimate**: 1 day
**Dependencies**: Story 27.6

**Acceptance Criteria**:
- [ ] Service maintains registry of all project function/class names
- [ ] Registry updated during indexing
- [ ] Used to validate extracted calls (is this a project symbol?)
- [ ] Persisted to Redis for fast lookup
- [ ] API endpoint to query registry

**Implementation**: `api/services/symbol_registry_service.py`

---

#### Story 27.8: Import Statement Analysis
**Priority**: LOW
**Estimate**: 1 day
**Dependencies**: Story 27.7

**Acceptance Criteria**:
- [ ] Parse import statements from TypeScript files
- [ ] Map imported names to source files
- [ ] Resolve calls to imports (cross-file resolution)
- [ ] Handle aliased imports: `import { Foo as Bar }`
- [ ] Improves edge resolution by 20-30%

---

#### Story 27.9: Advanced Type Inference
**Priority**: LOW
**Estimate**: 1 day
**Dependencies**: Story 27.8

**Acceptance Criteria**:
- [ ] Infer types for method calls: `user.save()` → `User.save`
- [ ] Handle generics: `Array<T>.map` → `map`
- [ ] Namespace resolution: `Utils.formatDate` → `formatDate`
- [ ] Improves edge resolution by 10-20%

---

## 🧪 Testing Strategy

### Unit Tests
- Call name cleanup (20+ cases)
- Tree-sitter query patterns (30+ cases)
- Blacklist filtering
- Symbol registry operations

### Integration Tests
- Full indexing pipeline with test TypeScript files
- Graph construction with cleaned calls
- Edge creation and validation
- Before/after metrics comparison

### Validation
- Re-index CVGenerator after each phase
- Measure metrics: edge ratio, resolution rate, noise
- Manual verification of sample edges
- Performance benchmarks (indexing speed)

---

## 📅 Timeline

### Phase 1: Quick Wins (Week 1)
- **Day 1**: Stories 27.1-27.2 (Add name field + migration)
- **Day 2**: Story 27.3 (Call cleanup) + Re-index
- **Target**: 30% edge ratio

### Phase 2: Enhanced Extraction (Week 2)
- **Day 3-4**: Stories 27.4-27.5 (Blacklist + Enhanced queries)
- **Day 5**: Story 27.6 (Re-index + Validate)
- **Target**: 50% edge ratio

### Phase 3: Scope-Aware (Week 3-4) [Optional]
- **Week 3**: Stories 27.7-27.8 (Symbol registry + Imports)
- **Week 4**: Story 27.9 (Type inference)
- **Target**: 60%+ edge ratio

---

## 🚨 Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Over-filtering valid calls | Medium | High | Scope-aware filtering (Phase 3) |
| Performance degradation | Low | Medium | Benchmark, use caching |
| Breaking Python extraction | Low | High | Comprehensive tests, feature flags |
| Migration fails on large DBs | Low | Medium | Test on staging, add rollback |

---

## 📚 Resources

- **ULTRATHINK**: `EPIC-27_TYPESCRIPT_METADATA_EXTRACTION_ULTRATHINK.md`
- **Current Code**: `api/services/metadata_extractors/typescript_extractor.py`
- **Graph Service**: `api/services/graph_construction_service.py`
- **Tree-sitter Docs**: https://tree-sitter.github.io/tree-sitter/

---

## ✅ Definition of Done

- [ ] Phase 1 complete: 30%+ edge ratio
- [ ] Phase 2 complete: 50%+ edge ratio
- [ ] All unit tests passing
- [ ] Integration tests passing
- [ ] CVGenerator re-indexed successfully
- [ ] Validation report shows improvements
- [ ] No regression in Python extraction
- [ ] Documentation updated
- [ ] Completion report written

---

**Status**: PLANNED - Ready to start Story 27.1
**Next Action**: Implement Story 27.1 (Add name field to nodes)
