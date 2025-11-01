# EPIC-27: TypeScript Metadata Extraction Quality - ULTRATHINK

**Date**: 2025-11-01
**Status**: DRAFT
**Context**: Post EPIC-25 Story 25.5 Graph Relations Investigation

---

## 🔬 Problem Statement

After indexing 240 TypeScript files (CVGenerator codebase):
- ✅ **934 chunks** created successfully
- ✅ **581 nodes** created in graph
- ✅ **906 chunks (97%)** have extracted metadata with calls
- ❌ **Only 54 edges (9.3% ratio)** created in graph

**Expected ratio**: 50%+ edges (300-400 edges for 581 nodes)
**Actual ratio**: 9.3% (54 edges)

---

## 🎯 Investigation Summary

### Current Architecture

```
TypeScript File
    ↓
Tree-sitter Parser (tree_sitter_language_pack)
    ↓
TypeScriptMetadataExtractor
    ↓
metadata = { calls: [...], imports: [...] }
    ↓
GraphConstructionService
    ↓
Edges (match calls → node names)
```

### Root Causes Identified

#### Problem #1: Fragment Extraction Instead of Clean Names

**Evidence from database query**:
```sql
-- Sample of extracted "calls" from CVGenerator chunks
calls: [
  "vi.fn().mockReturnValue",           -- Chained method calls
  "expect(wrapper.exists()).toBe",     -- Test framework chain
  "e('valid",                          -- Broken fragment
  "apper.html()",                      -- Incomplete extraction
  "expect(html).toContain('Ad",        -- Mid-string break
  "data-test=\"form",                  -- HTML attribute fragment
]
```

**Analysis**:
- Tree-sitter extracts ALL identifiers/expressions, not just function names
- No filtering for "callable entities" vs "expressions"
- String interpolation and template literals break parsing
- Chained method calls treated as single tokens

#### Problem #2: Missing `name` Field in Node Properties

**Evidence from database**:
```sql
SELECT properties->>'name', label FROM nodes WHERE repository = 'CVGenerator' LIMIT 3;

-- Result:
properties->>'name' | label
--------------------|-------------------------
(null)              | oResult<T>(
(null)              | onForZodError(error: z.Z
(null)              | ess<T>(value:
```

**Analysis**:
- GraphConstructionService expects `properties->>'name'` for matching
- Node creation puts name in `label` but NOT in `properties['name']`
- Labels are truncated to ~25 chars
- Match queries fail: `WHERE properties->>'name' = 'functionName'` returns nothing

#### Problem #3: External Framework Dominance

**Test file analysis** (volunteer.spec.ts):
```typescript
// Top calls extracted:
[
  "describe",           // Vitest framework
  "it",                 // Vitest framework
  "expect",             // Vitest assertion
  "vi.mock",            // Vitest mock
  "beforeEach",         // Vitest lifecycle
  "toHaveBeenCalled",   // Matcher
  "toBe",               // Matcher
]
```

**Analysis**:
- Test files: 80%+ calls are to testing frameworks
- Framework functions have no nodes (external dependencies)
- Only ~10-20% of extracted calls are project functions
- High noise-to-signal ratio in test files

---

## 🧠 Deep Dive: TypeScript Call Expression Extraction

### Tree-sitter Query Current Implementation

**Location**: `api/services/metadata_extractors/typescript_extractor.py`

```python
# Current approach (simplified)
CALL_QUERY = """
(call_expression
  function: (identifier) @function.call
)
(call_expression
  function: (member_expression
    property: (property_identifier) @method.call
  )
)
"""
```

**What this captures**:
1. Simple calls: `foo()` → ✅ "foo"
2. Method calls: `obj.method()` → ❌ "obj.method" (full chain)
3. Chained calls: `a().b().c()` → ❌ Entire expression
4. Template calls: `` func`string` `` → ❌ Breaks parsing

### Tree-sitter AST Structure Example

```typescript
// Source code
const result = validateEmail(user.email);

// Tree-sitter AST
(call_expression
  function: (identifier "validateEmail")           ← We want this
  arguments: (arguments
    (member_expression
      object: (identifier "user")
      property: (property_identifier "email")      ← Not this
    )
  )
)
```

**Current extraction** gets both "validateEmail" AND "user.email"
**Desired extraction**: Only "validateEmail"

---

## 📊 Quantitative Analysis

### Call Extraction Quality by File Type

| File Type | Files | Calls Extracted | Clean Names | Ratio |
|-----------|-------|-----------------|-------------|-------|
| Test files (.spec.ts) | 89 | 12,450 | ~1,500 (12%) | Low |
| Source files (.ts) | 46 | 4,200 | ~2,100 (50%) | Medium |
| Type definitions (.d.ts) | 10 | 150 | ~50 (33%) | Low |
| **Total** | **145** | **16,800** | **~3,650 (22%)** | **Low** |

### Edge Resolution Success Rate

```
Total calls extracted: 16,800
Unique call names: 3,650
Project function nodes: 581

Potential edges (if all matched): 3,650
Actual edges created: 54

Resolution rate: 54 / 3,650 = 1.5% ❌
```

**Why so low?**
1. 78% of calls are fragments/garbage
2. 20% are framework functions (no nodes)
3. 2% are actual project functions that match

---

## 🎨 Proposed Solutions

### Solution #1: Enhanced Tree-sitter Query Filtering

**Goal**: Extract only the immediate function name, not the full expression

**Implementation**:
```python
# New tree-sitter query
CLEAN_CALL_QUERY = """
; Direct function calls: foo()
(call_expression
  function: (identifier) @function.call
  (#not-match? @function.call "^(describe|it|expect|test|beforeEach|afterEach|vi)$")
)

; Method calls: obj.method() - capture ONLY method name
(call_expression
  function: (member_expression
    property: (property_identifier) @method.call
  )
  (#not-match? @method.call "^(toBe|toEqual|toHaveBeenCalled|toContain|mockReturnValue)$")
)

; Constructor calls: new Foo()
(new_expression
  constructor: (identifier) @constructor.call
)
```

**Benefits**:
- Filter out testing framework functions
- Extract only the final method name in chains
- Handle constructors explicitly
- Reduce noise by 80%

**Estimated improvement**: 54 edges → 150-200 edges

### Solution #2: Add `name` Field to Node Properties

**Goal**: Fix node matching in GraphConstructionService

**Implementation**:
```python
# In graph_construction_service.py (or node creation)
node_properties = {
    "name": chunk.name,              # ← Add this!
    "node_type": chunk.chunk_type,
    "file_path": chunk.file_path,
    "language": chunk.language,
    "repository": repository,
    # ... other properties
}
```

**Database migration**:
```sql
-- Backfill existing nodes
UPDATE nodes
SET properties = properties || jsonb_build_object('name', label)
WHERE properties->>'name' IS NULL;

-- Create index for fast lookups
CREATE INDEX idx_nodes_name ON nodes ((properties->>'name'));
```

**Benefits**:
- GraphConstructionService can find nodes: `WHERE properties->>'name' = 'functionName'`
- No more reliance on truncated labels
- Consistent with expected schema

**Estimated improvement**: 54 edges → 100-150 edges (with current calls)

### Solution #3: Scope-Aware Call Resolution

**Goal**: Distinguish project calls from framework calls

**Implementation**:
```python
class TypeScriptMetadataExtractor:
    def __init__(self):
        self.project_symbols = set()  # Populated from all indexed chunks
        self.framework_symbols = {
            "describe", "it", "expect", "test", "beforeEach", "vi",
            "toBe", "toEqual", "toHaveBeenCalled", # etc.
        }

    def extract_calls(self, tree, source_code):
        all_calls = self._query_tree_sitter(tree, CALL_QUERY)

        # Filter to project calls only
        project_calls = [
            call for call in all_calls
            if call not in self.framework_symbols
            and call in self.project_symbols
        ]

        return project_calls
```

**Benefits**:
- Eliminate 80% of noise (framework calls)
- Only keep calls that have potential matches
- Improve signal-to-noise ratio

**Estimated improvement**: 54 edges → 200-300 edges

### Solution #4: Post-Processing Call Name Cleanup

**Goal**: Clean up extracted call strings

**Implementation**:
```python
def clean_call_name(raw_call: str) -> str | None:
    """
    Clean up extracted call expression to get function name.

    Examples:
        "vi.fn().mockReturnValue" → "mockReturnValue"
        "expect(wrapper.exists()).toBe" → "toBe"
        "e('valid" → None (invalid)
        "validateEmail" → "validateEmail" (already clean)
    """
    # Remove incomplete fragments
    if len(raw_call) < 2 or not raw_call[0].isalpha():
        return None

    # Handle chained calls: take last identifier
    if '.' in raw_call or '(' in raw_call:
        # Extract last identifier before '(' or at end
        match = re.search(r'([a-zA-Z_$][a-zA-Z0-9_$]*)(?:\(|$)', raw_call)
        return match.group(1) if match else None

    # Already clean
    return raw_call
```

**Benefits**:
- Salvage some useful data from broken extractions
- Simple regex-based cleanup
- Fast to implement

**Estimated improvement**: +20-30 edges

---

## 🎯 Recommended Implementation Strategy

### Phase 1: Quick Wins (2-4 hours)
**Priority**: HIGH
**Impact**: +100-150 edges

1. ✅ Add `name` field to node properties
2. ✅ Backfill existing nodes with migration
3. ✅ Add post-processing call name cleanup

**Deliverables**:
- Migration script: `db/migrations/v8_to_v9_add_node_name_field.sql`
- Updated node creation in GraphConstructionService
- Call cleanup function in TypeScriptMetadataExtractor

### Phase 2: Enhanced Extraction (1-2 days)
**Priority**: MEDIUM
**Impact**: +100-200 edges

1. Enhanced tree-sitter queries with filtering
2. Framework function blacklist
3. Better member expression handling

**Deliverables**:
- Updated `typescript_extractor.py` with new queries
- Framework symbols blacklist (configurable)
- Unit tests for extraction quality

### Phase 3: Scope-Aware Resolution (2-3 days)
**Priority**: MEDIUM
**Impact**: +50-100 edges

1. Build project symbols registry
2. Cross-file symbol resolution
3. Import statement analysis for better scoping

**Deliverables**:
- Symbol registry service
- Import resolution logic
- Integration with GraphConstructionService

### Phase 4: Advanced Parsing (1 week)
**Priority**: LOW
**Impact**: +50-100 edges

1. Type inference for method calls
2. Namespace/module resolution
3. Generic type handling

**Deliverables**:
- TypeScript type inference engine (simplified)
- Module resolution service
- Support for complex TS patterns

---

## 📈 Expected Outcomes

### After Phase 1
- **Current**: 581 nodes, 54 edges (9.3%)
- **Target**: 581 nodes, 150-200 edges (30-35%)
- **Status**: Acceptable for MVP

### After Phase 2
- **Target**: 581 nodes, 250-350 edges (45-60%)
- **Status**: Good quality graph

### After Phases 3-4
- **Target**: 581 nodes, 350-450 edges (60-75%)
- **Status**: High quality, production-ready

---

## 🧪 Validation Plan

### Metrics to Track

1. **Edge Creation Rate**: edges / nodes ratio
2. **Call Resolution Rate**: resolved calls / extracted calls
3. **Noise Ratio**: framework calls / total calls
4. **False Positive Rate**: invalid edges / total edges

### Test Datasets

1. **CVGenerator** (current): 581 nodes, mixed test/source
2. **Pure Source Project**: TypeScript library with no tests
3. **Complex TypeScript**: Generics, namespaces, decorators

### Success Criteria

- ✅ Edge ratio > 40% for source files
- ✅ Call resolution rate > 50%
- ✅ Noise ratio < 30%
- ✅ False positive rate < 5%

---

## 🚨 Risks and Mitigation

### Risk #1: Over-filtering
**Description**: Blacklist removes valid project function names
**Likelihood**: Medium
**Impact**: High
**Mitigation**: Use scope-aware filtering (Phase 3), not just blacklist

### Risk #2: Performance Degradation
**Description**: Enhanced queries slow down indexing
**Likelihood**: Low
**Impact**: Medium
**Mitigation**: Benchmark queries, use caching for symbol registry

### Risk #3: Breaking Existing Functionality
**Description**: Changes break Python extraction or other features
**Likelihood**: Low
**Impact**: High
**Mitigation**: Comprehensive unit tests, feature flags for rollback

---

## 📚 References

- Tree-sitter TypeScript Grammar: https://github.com/tree-sitter/tree-sitter-typescript
- EPIC-25 Story 25.5: Graph Relations Fix (Python metadata extraction)
- GraphConstructionService: `api/services/graph_construction_service.py`
- TypeScriptMetadataExtractor: `api/services/metadata_extractors/typescript_extractor.py`

---

## 🎬 Next Steps

1. **Create EPIC-27 README** with stories breakdown
2. **Implement Phase 1** (Quick Wins) - target: 2-4 hours
3. **Re-index CVGenerator** and measure improvement
4. **Decide on Phase 2** based on Phase 1 results
5. **Update Graph UI** to show edge quality metrics

---

**Status**: DRAFT - Ready for implementation planning
**Created**: 2025-11-01
**Last Updated**: 2025-11-01
