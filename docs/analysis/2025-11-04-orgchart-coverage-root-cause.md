# Orgchart Graph Coverage Issue - Root Cause Analysis

**Date**: 2025-11-04
**Status**: ⚠️ HYPOTHESIS INVALIDATED - Further Investigation Required
**Previous Session**: 2025-11-03 (OUTDATED - used old data)
**Update**: 2025-11-04 07:00 UTC - Type import fix didn't resolve issue

---

## Executive Summary

Investigation reveals a **backend graph construction bug** causing 40% of nodes to be isolated (no edges). This is NOT a frontend traversal issue, but rather a fundamental problem with edge creation during graph construction, particularly for TypeScript interfaces, types, and classes.

**Key Findings:**
- **Isolated Nodes**: 110/278 (40%) have NO edges
- **Root Cause**: TypeScript extractor creates nodes but fails to create import/export/usage edges
- **Impact**: CRITICAL - Renders orgchart visualization unusable
- **Previous Session**: Obsolete (used 500 nodes dataset that no longer exists)

---

## Data Comparison

### Old Data (2025-11-03 Session - No Longer Exists)
- **Repository**: CVgenerator (not CVgenerator_FIXED)
- **Nodes**: 500
- **Edges**: 607
- **Modules**: 15
- **Coverage Issue**: 37/500 visible (7.4%)

### Current Data (2025-11-04 - CVgenerator_FIXED)
- **Repository**: CVgenerator_FIXED
- **Nodes**: 278
- **Edges**: 216
- **Modules**: 2
- **Coverage Issue**: 110/278 isolated (40%)

**Conclusion**: The database was re-indexed. Previous session analysis is obsolete. Current state is WORSE (40% isolated vs 7.4% coverage).

---

## Node Connectivity Breakdown

### By Type

| Node Type | Total | Isolated | Source Only | Sink Only | Fully Connected | Isolation Rate |
|-----------|-------|----------|-------------|-----------|-----------------|----------------|
| **Class** | 184 | 47 | 105 | 21 | 11 | 26% |
| **Function** | 85 | 56 | 28 | 0 | 1 | 66% |
| **Config** | 7 | 7 | 0 | 0 | 0 | 100% |
| **Module** | 2 | 0 | 2 | 0 | 0 | 0% |
| **TOTAL** | **278** | **110** | **135** | **21** | **12** | **40%** |

### Edge Distribution

| Edge Type | Count | Percentage |
|-----------|-------|------------|
| imports | 201 | 93% |
| calls | 9 | 4% |
| re_exports | 6 | 3% |
| **Total** | **216** | **100%** |

---

## Root Cause Analysis

### Problem: Missing Edges for TypeScript Types/Interfaces

**Sample Isolated Nodes:**
```
Class: Assertion                        (test setup)
Class: CollectionFieldOptions           (composable interface)
Class: ValidationCatalogueOptions       (validation interface)
Class: FormErrors                       (form interface)
Class: ErrorMapping                     (error mapper interface)
Config: All 7 config files             (100% isolated)
Function: 56/85 functions              (66% isolated)
```

**Pattern Identified:**
- TypeScript **interfaces** and **type aliases** are extracted as nodes
- BUT: No edges are created for:
  - Import statements (`import type { Foo } from './bar'`)
  - Export statements (`export type { Foo }`)
  - Usage in function signatures (`function foo(bar: Bar)`)
  - Class implements/extends (`class Foo implements Bar`)

### Why This Happens

Looking at the graph construction pipeline:

1. **Code Chunking**: [code_chunking_service.py](../../api/services/code_chunking_service.py)
   - Extracts TypeScript nodes using tree-sitter
   - Creates chunks for interfaces, types, classes, functions ✅

2. **Graph Construction**: [graph_construction_service.py](../../api/services/graph_construction_service.py)
   - Creates nodes from chunks ✅
   - **Resolves edges** using regex/AST analysis ❌ **FAILS FOR TYPES**

**Hypothesis**: The edge resolution logic in `graph_construction_service.py` likely:
- ✅ Handles `import { Foo }` (value imports)
- ✅ Handles `export { Foo }` (value exports)
- ❌ **MISSES** `import type { Foo }` (type-only imports)
- ❌ **MISSES** type usage in signatures
- ❌ **MISSES** interface implements/extends relationships

---

## Database Query Evidence

### Query 1: Node Distribution
```sql
SELECT
  properties->>'repository' as repository,
  COUNT(DISTINCT node_id) as total_nodes,
  COUNT(DISTINCT node_id) FILTER (WHERE node_type = 'Module') as modules,
  COUNT(DISTINCT node_id) FILTER (WHERE node_type = 'Function') as functions,
  COUNT(DISTINCT node_id) FILTER (WHERE node_type = 'Class') as classes,
  COUNT(DISTINCT node_id) FILTER (WHERE node_type = 'Config') as configs
FROM nodes
WHERE properties->>'repository' = 'CVgenerator_FIXED'
GROUP BY properties->>'repository';
```

**Result:**
```
repository        | total_nodes | modules | functions | classes | configs
------------------+-------------+---------+-----------+---------+---------
CVgenerator_FIXED |         278 |       2 |        85 |     184 |       7
```

### Query 2: Edge Distribution
```sql
SELECT
  properties->>'repository' as repository,
  COUNT(*) as total_edges,
  COUNT(*) FILTER (WHERE relation_type = 'calls') as calls,
  COUNT(*) FILTER (WHERE relation_type = 'imports') as imports,
  COUNT(*) FILTER (WHERE relation_type = 're_exports') as re_exports
FROM edges e
JOIN nodes n ON e.source_node_id = n.node_id
WHERE n.properties->>'repository' = 'CVgenerator_FIXED'
GROUP BY n.properties->>'repository';
```

**Result:**
```
repository | total_edges | calls | imports | re_exports
-----------+-------------+-------+---------+------------
           |         216 |     9 |     201 |          6
```

### Query 3: Node Connectivity Analysis
```sql
WITH node_edges AS (
  SELECT
    n.node_id,
    n.node_type,
    COUNT(DISTINCT e_out.edge_id) as outgoing_edges,
    COUNT(DISTINCT e_in.edge_id) as incoming_edges
  FROM nodes n
  LEFT JOIN edges e_out ON n.node_id = e_out.source_node_id
  LEFT JOIN edges e_in ON n.node_id = e_in.target_node_id
  WHERE n.properties->>'repository' = 'CVgenerator_FIXED'
  GROUP BY n.node_id, n.node_type
)
SELECT
  node_type,
  COUNT(*) FILTER (WHERE incoming_edges = 0 AND outgoing_edges = 0) as isolated,
  COUNT(*) FILTER (WHERE incoming_edges = 0 AND outgoing_edges > 0) as source_only,
  COUNT(*) FILTER (WHERE incoming_edges > 0 AND outgoing_edges = 0) as sink_only,
  COUNT(*) FILTER (WHERE incoming_edges > 0 AND outgoing_edges > 0) as connected,
  COUNT(*) as total
FROM node_edges
GROUP BY node_type;
```

**Result:** See "Node Connectivity Breakdown" table above.

---

## Impact on Orgchart Visualization

### Frontend Behavior (Confirmed)

The [OrgchartGraph.vue](../../frontend/src/components/OrgchartGraph.vue) component:

1. **Fetches Data** from `/v1/code/graph/data/CVgenerator_FIXED` ✅
   - Receives 278 nodes, 216 edges

2. **Applies Semantic Zoom Filter** (lines 134-187) ✅
   - At 100% zoom, includes ALL 278 nodes

3. **Builds Tree from Modules** (lines 228-277) ✅
   - Starts with 2 Module nodes (entry points)
   - Traverses via `childrenMap` (built from edges)
   - Only reaches nodes connected via edges

4. **Result**: Only 168/278 nodes visible (60%) ❌
   - 110 isolated nodes never visited by tree traversal
   - Frontend working as designed - bug is in backend data

### Diagnostic Logging (Already in Place)

Lines 204, 319-336 in OrgchartGraph.vue:
```typescript
console.log('[Orgchart] Nodes appearing in edges:', nodesInEdges.size, '/', filteredNodes.length)

console.warn('[Orgchart] Unvisited nodes (not connected to tree):', {
  count: unvisitedNodes.length,
  withEdges: unvisitedWithEdges.length,
  withoutEdges: unvisitedNodes.length - unvisitedWithEdges.length,
  types: /* ... */,
  sample: /* first 5 nodes with edge counts */
})
```

**Expected Console Output** (when visiting http://localhost:3000/orgchart with CVgenerator_FIXED):
```
[Orgchart] Nodes appearing in edges: 168 / 278
[Orgchart] Unvisited nodes: {count: 110, withoutEdges: 110, ...}
```

---

## Fix Plan

### Phase 1: Investigation (CURRENT)
- [x] Analyze database node/edge data ✅
- [x] Confirm isolated nodes count (110/278) ✅
- [x] Identify affected node types ✅
- [ ] Read [graph_construction_service.py](../../api/services/graph_construction_service.py) edge resolution logic
- [ ] Find TypeScript type import/export handling

### Phase 2: Backend Fix
- [ ] Add support for `import type { }` statements
- [ ] Add support for `export type { }` statements
- [ ] Add edges for type usage in signatures
- [ ] Add edges for interface implements/extends
- [ ] Add edges for type aliases
- [ ] Add unit tests for TypeScript edge resolution

### Phase 3: Re-Index & Validate
- [ ] Re-index CVgenerator with fixed graph construction
- [ ] Verify isolated node count < 5%
- [ ] Verify orgchart shows 90%+ nodes at 100% zoom
- [ ] Test with multiple repositories (code_test, MnemoLite)

### Phase 4: Documentation
- [ ] Update session document with fix details
- [ ] Document TypeScript edge resolution patterns
- [ ] Add architecture diagram for graph construction

---

## Files to Investigate

### Backend (Graph Construction)
1. [api/services/graph_construction_service.py](../../api/services/graph_construction_service.py) (1307 lines)
   - Method: `_resolve_edges_for_chunk()` - Edge resolution logic
   - Method: `_parse_imports()` - Import statement parsing
   - Method: `_parse_exports()` - Export statement parsing
   - **Look for**: TypeScript-specific handling

2. [api/services/code_chunking_service.py](../../api/services/code_chunking_service.py)
   - Method: `_extract_typescript_info()` - TypeScript AST extraction
   - **Verify**: Are type nodes being extracted correctly?

### Frontend (Diagnostic)
3. [frontend/src/components/OrgchartGraph.vue](../../frontend/src/components/OrgchartGraph.vue) (806 lines)
   - Lines 204, 319-336: Diagnostic logging ✅ (already in place)
   - No changes needed - frontend works correctly

---

## Related Documents

- [2025-11-03-orgchart-semantic-zoom-debugging.md](../sessions/2025-11-03-orgchart-semantic-zoom-debugging.md) - **OBSOLETE** (used 500-node dataset)
- [2025-11-04-oom-root-cause-analysis-and-fix.md](./2025-11-04-oom-root-cause-analysis-and-fix.md) - OOM fix (build directories)

---

## Recommendations

### Immediate (P0)
1. **Investigate `graph_construction_service.py`** edge resolution
2. **Add TypeScript type edge support** (import type, export type, usage)
3. **Re-index CVgenerator** and validate fix

### Short-Term (P1)
4. Add comprehensive unit tests for TypeScript edge cases
5. Add integration test: "all non-Module nodes should have at least 1 edge"
6. Add metrics: "% isolated nodes" to graph stats endpoint

### Long-Term (P2)
7. Consider using TypeScript Compiler API for precise type resolution
8. Add support for other languages (Go, Rust, Java)
9. Implement "orphan node detection" in indexing pipeline

---

## Update: 2025-11-04 07:00 UTC - Hypothesis Invalidated

### Implementation Result: ❌ FAILED

TypeScript type import/export fix was implemented and tested:
- ✅ Code implementation successful (manual AST traversal)
- ✅ Unit tests passing (6/6 imports extracted)
- ❌ **Production impact: ZERO**
  - Edge count unchanged: 216 → 216
  - Isolated nodes worse: 110 (40%) → 113 (41%)

### Why the Hypothesis Was Wrong

1. **CVgenerator HAS type imports** - Source files contain `import type` statements
2. **Edge count didn't change** - Would expect +60-85% increase if fix worked
3. **Different symptom observed** - Many nodes have **truncated/malformed names**
4. **Test files included** - Many isolated nodes are from test utilities

### New Evidence

**Isolated node characteristics**:
- Truncated names: "tatus { id:", "ionOptions { /", "ess<T>(value:"
- Test files: `*.test.ts`, `*.e2e-test.ts`, `setup.ts`
- 100% of config files isolated
- 66% of functions isolated

**Real problem appears to be**:
- Node name extraction bugs (truncation)
- Test file filtering not working
- Different issue than edge creation

---

## Conclusion

**Original Root Cause**: ❌ INCORRECT - TypeScript type imports/exports were NOT the issue

**Current Status**: 🔴 UNKNOWN - Further investigation required

**Evidence**: Fix implementation proved the hypothesis wrong through empirical testing.

**Next Investigation**: See [2025-11-04-isolated-nodes-investigation-v2.md](./2025-11-04-isolated-nodes-investigation-v2.md)

---

**Investigation Log:**
- 2025-11-04 15:30: Database analysis completed
- 2025-11-04 15:45: Root cause identified (TypeScript type imports)
- 2025-11-04 16:00: Root cause document created
- 2025-11-04 16:30: Fix implemented (manual AST traversal)
- 2025-11-04 17:30: Production validation completed
- **2025-11-04 07:00: Hypothesis invalidated - different root cause exists**
