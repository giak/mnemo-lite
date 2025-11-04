# Orgchart Isolated Nodes - Investigation Round 2

**Date**: 2025-11-04
**Status**: 🔴 INVESTIGATION REQUIRED
**Previous Session**: [2025-11-04-type-import-fix-implementation.md](./2025-11-04-type-import-fix-implementation.md)

---

## Executive Summary

Round 1 investigation hypothesized that missing `import type` / `export type` extraction caused 40% isolated nodes. This was **incorrect**. Production testing showed zero improvement despite successful code implementation.

**New Hypothesis**: The problem is in **node extraction/naming**, not edge creation.

---

## Evidence from Round 1

### What We Know Works ✅
- TypeScript type import/export extraction (unit tested)
- Regular import/export extraction (confirmed working)
- Graph construction pipeline (creates nodes and edges)

### What's Broken ❌
- **40% of nodes have zero edges** (110/278 in CVgenerator_FIXED)
- **Many nodes have truncated/malformed names**:
  - "tatus { id:" (incomplete)
  - "ionOptions { /" (incomplete)
  - "ess<T>(value:" (incomplete)

### Critical Observations

| Finding | Implication |
|---------|-------------|
| Edge count unchanged (216 before/after fix) | Type imports weren't the problem |
| Node names are truncated | Node extraction has bugs |
| 100% of Config files isolated | Specific node types affected |
| 66% of Functions isolated | Function extraction may be broken |
| Many test files in results | Test filtering not working |

---

## Data Analysis

### Isolated Nodes Breakdown (CVgenerator_FIXED)

```sql
-- Sample isolated nodes
SELECT node_type, node_name, filename
FROM node_edges
WHERE incoming_edges = 0 AND outgoing_edges = 0
LIMIT 20;
```

**Results**:
```
node_type | node_name                     | filename
----------|-------------------------------|---------------------------
Function  | ComponentInMultipleLanguages(+| language-testing.ts
Function  | serLanguage(): Suppor         | language-detection.ts
Class     | I18nValidationOptions         | i18n-validation.ts
Class     | TextSelector                  | i18n-e2e-test.ts
Function  | upportedLocale) {            +| setup.ts
Class     | tatus {   id:                 | useFormProgress.ts
Config    | vitest.config                 | vitest.config.ts
Class     | ValidationOptions             | useZodFieldValidation.ts
Function  | ess<T>(value:                 | result.utils.ts
```

**Patterns Identified**:
1. **Test files**: Many isolated nodes from `*.test.ts`, `*.e2e-test.ts`, `setup.ts`
2. **Truncated names**: Names cut off mid-word or mid-syntax
3. **Config files**: 100% isolated (vitest.config, vite.config)
4. **Utility functions**: result.utils.ts, error handlers

---

## Investigation Plan

### Phase 1: Node Name Extraction Analysis
**Goal**: Understand why node names are truncated

**Tasks**:
- [ ] Read `code_chunking_service.py` node name extraction logic
- [ ] Find where node names come from (tree-sitter identifier nodes?)
- [ ] Test with problematic files (i18n-validation.ts, useFormProgress.ts)
- [ ] Check if byte offsets are causing truncation

**Hypothesis**: Tree-sitter identifier extraction has a character limit or encoding issue

---

### Phase 2: Test File Filtering
**Goal**: Determine if test files should be indexed

**Tasks**:
- [ ] Check `index_directory.py` file filtering logic
- [ ] Verify if `*.test.ts`, `*.spec.ts` are being excluded
- [ ] Review if test utilities should have edges to production code
- [ ] Consider separate "test" vs "production" graph indexing

**Hypothesis**: Test files create noise in dependency graph and should be excluded

---

### Phase 3: Config File Edge Creation
**Goal**: Understand why 100% of config files are isolated

**Tasks**:
- [ ] Examine vitest.config.ts, vite.config.ts structure
- [ ] Check if config files export configurations that get imported
- [ ] Verify if tree-sitter correctly parses config file exports
- [ ] Test edge creation for `export default { ... }` patterns

**Hypothesis**: Config files use export patterns not captured by current extraction

---

### Phase 4: Interface/Type Alias Node Creation
**Goal**: Verify if TypeScript interfaces and type aliases are being extracted as nodes

**Tasks**:
- [ ] Check if `TypeScriptMetadataExtractor` extracts interface_declaration
- [ ] Check if type_alias_declaration nodes are created
- [ ] Verify these declarations create graph nodes
- [ ] Test if interfaces have correct node names

**Hypothesis**: Interfaces/types are extracted but without proper names or edges

---

## Diagnostic Queries

### Query 1: Find all truncated node names
```sql
SELECT node_type, properties->>'name' as node_name, properties->>'file_path' as file_path
FROM nodes
WHERE properties->>'repository' = 'CVgenerator_FIXED'
  AND length(properties->>'name') < 30
  AND (properties->>'name' LIKE '%{%'
    OR properties->>'name' LIKE '%(%'
    OR properties->>'name' LIKE '%:%')
ORDER BY length(properties->>'name')
LIMIT 50;
```

### Query 2: Test file isolation rate
```sql
WITH node_edges AS (
  SELECT
    n.node_id,
    n.properties->>'file_path' as file_path,
    COUNT(DISTINCT e_out.edge_id) as outgoing_edges,
    COUNT(DISTINCT e_in.edge_id) as incoming_edges
  FROM nodes n
  LEFT JOIN edges e_out ON n.node_id = e_out.source_node_id
  LEFT JOIN edges e_in ON n.node_id = e_in.target_node_id
  WHERE n.properties->>'repository' = 'CVgenerator_FIXED'
  GROUP BY n.node_id, n.properties
)
SELECT
  CASE
    WHEN file_path LIKE '%.test.%' THEN 'test'
    WHEN file_path LIKE '%.spec.%' THEN 'spec'
    WHEN file_path LIKE '%__tests__%' THEN 'tests_dir'
    ELSE 'production'
  END as file_category,
  COUNT(*) as total_nodes,
  COUNT(*) FILTER (WHERE incoming_edges = 0 AND outgoing_edges = 0) as isolated,
  ROUND(100.0 * COUNT(*) FILTER (WHERE incoming_edges = 0 AND outgoing_edges = 0) / COUNT(*), 1) as isolation_rate
FROM node_edges
GROUP BY file_category;
```

### Query 3: Node type distribution for isolated nodes
```sql
WITH node_edges AS (
  SELECT
    n.node_id,
    n.node_type,
    n.properties->>'name' as node_name,
    COUNT(DISTINCT e_out.edge_id) as outgoing_edges,
    COUNT(DISTINCT e_in.edge_id) as incoming_edges
  FROM nodes n
  LEFT JOIN edges e_out ON n.node_id = e_out.source_node_id
  LEFT JOIN edges e_in ON n.node_id = e_in.target_node_id
  WHERE n.properties->>'repository' = 'CVgenerator_FIXED'
  GROUP BY n.node_id, n.node_type, n.properties
)
SELECT
  node_type,
  COUNT(*) as total,
  COUNT(*) FILTER (WHERE node_name LIKE '%{%' OR node_name LIKE '%(%') as truncated_names,
  COUNT(*) FILTER (WHERE incoming_edges = 0 AND outgoing_edges = 0) as isolated
FROM node_edges
GROUP BY node_type;
```

---

## Files to Investigate

### Backend (Code Chunking & Node Extraction)
1. **[code_chunking_service.py](../../api/services/code_chunking_service.py)**
   - Method: `_extract_typescript_info()` - TypeScript AST extraction
   - Method: `_create_chunk_from_node()` - Chunk creation from tree-sitter nodes
   - **Focus**: How are node names extracted? Why truncation?

2. **[index_directory.py](../../scripts/index_directory.py)**
   - Method: `scan_files()` - File filtering logic
   - **Focus**: Are test files being filtered out? Should they be?

3. **[typescript_extractor.py](../../api/services/metadata_extractors/typescript_extractor.py)**
   - Method: `extract_metadata()` - Metadata extraction
   - **Focus**: Are interfaces/type aliases extracted as nodes?

---

## Next Steps

1. **Run diagnostic queries** to understand data patterns
2. **Investigate code_chunking_service.py** node name extraction
3. **Test with specific problematic files** to reproduce truncation
4. **Determine test file handling policy** (exclude or include with edges?)
5. **Fix identified root causes** and re-index
6. **Validate** isolated nodes < 10%

---

## Related Documents

- [2025-11-04-orgchart-coverage-root-cause.md](./2025-11-04-orgchart-coverage-root-cause.md) - Original root cause analysis
- [2025-11-04-type-import-fix-implementation.md](./2025-11-04-type-import-fix-implementation.md) - Round 1 implementation (failed)
- [2025-11-03-orgchart-semantic-zoom-debugging.md](../sessions/2025-11-03-orgchart-semantic-zoom-debugging.md) - Frontend debugging session

---

**Created**: 2025-11-04 07:15 UTC
**Status**: Ready for investigation
**Priority**: P0 - Blocks orgchart visualization
