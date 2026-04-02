# EPIC-28: Fix Byte Offset Bug in Metadata Extraction

**Created**: 2025-11-01
**Status**: 🎯 READY TO IMPLEMENT
**Priority**: HIGH
**Estimated Time**: 6-7 hours

---

## 🎯 Goal

Fix critical byte offset misalignment bug that corrupts 80% of extracted function call names, preventing graph from reaching 50%+ edge ratio.

---

## 📊 Current State → Target State

| Metric | Current (EPIC-27) | After EPIC-28 | Improvement |
|--------|-------------------|---------------|-------------|
| **Edge Ratio** | 32% (186 edges) | 50-60% (290-350 edges) | +18-28 pts |
| **Call Corruption** | 80% | 0% | -80 pts |
| **Example** | `teSuccess` ❌ | `createSuccess` ✅ | Fixed |

---

## 🔍 Problem Summary

**Root Cause**: Metadata extractors re-parse chunk source code, creating misaligned byte offsets that corrupt function call names.

**Example**:
- Full file function: `createSuccess`
- Extracted from chunk: `teSuccess` (missing 4 bytes)

**Impact**: Only 20% of function calls match graph nodes, limiting edges to 186 (32% ratio).

---

## 🎨 Solution Overview

**Pass full file source to metadata extractors** instead of re-parsing chunk source.

**Benefits**:
- ✅ Correct byte offsets (use original parse tree)
- ✅ No re-parsing (performance improvement)
- ✅ Enables cross-chunk analysis (future)
- ✅ Simple implementation (well-isolated change)

---

## 📋 Stories

### Story 28.1: Update Metadata Extraction API Signatures

**Objective**: Modify TypeScript extractor to accept full file source.

**Changes**:

**File**: `api/services/metadata_extractors/typescript_extractor.py`

**Current signature**:
```python
async def extract_metadata(
    self,
    source_code: str,  # Chunk source
    node: Node,
    tree: Tree
) -> dict[str, Any]:
    # Re-parses chunk source ← PROBLEM!
    tree = parser.parse(bytes(source_code, "utf8"))
    ...
```

**New signature**:
```python
async def extract_metadata(
    self,
    source_code: str,          # FULL FILE source (not chunk!)
    node: Node,                # Chunk node
    tree: Tree,                # Full file tree (already parsed)
    chunk_source: str | None = None  # Optional: for backward compat
) -> dict[str, Any]:
    """
    Extract metadata from TypeScript/JavaScript code.

    EPIC-28: Now uses full file source for correct byte offsets.

    Args:
        source_code: FULL file source code (ensures correct byte offsets)
        node: Chunk node (function/class/method definition)
        tree: Full file AST tree (already parsed, no re-parsing!)
        chunk_source: Optional chunk source for backward compatibility

    Returns:
        Metadata dict with imports and calls
    """
    # NO RE-PARSING! Use provided tree
    # Byte offsets are relative to FULL FILE → CORRECT!
```

**Key Changes**:
1. Remove `parser.parse()` call (no re-parsing)
2. Document that `source_code` is FULL file, not chunk
3. Use `source_code[node.start_byte:node.end_byte]` for correct slicing
4. Add backward compat parameter (optional)

**Acceptance Criteria**:
- [ ] Signature updated
- [ ] Re-parsing logic removed
- [ ] Byte slicing uses full file source
- [ ] Tests pass

**Effort**: 2 hours

---

### Story 28.2: Update Python Metadata Extraction

**Objective**: Apply same fix to Python metadata extraction.

**Changes**:

**File**: `api/services/metadata_extractor_service.py`

**Current**: Python uses `ast.get_source_segment()` which works correctly, but we can optimize by removing re-parsing.

**Changes**:
```python
async def _extract_python_metadata(
    self,
    source_code: str,  # Now FULL file source
    node: ast.AST,
    tree: ast.AST,
    module_imports: dict[str, str] | None = None
) -> dict[str, Any]:
    """
    Extract metadata from Python code using ast module.

    EPIC-28: Uses full file source for consistency.
    """
    # Ensure ast.get_source_segment uses full file
    # Update self._extract_calls() and other methods
```

**Acceptance Criteria**:
- [ ] Signature documented
- [ ] Methods use full file source
- [ ] Tests pass
- [ ] No regressions

**Effort**: 1 hour

---

### Story 28.3: Update Code Indexing Pipeline

**Objective**: Pass full file source through chunking → metadata extraction pipeline.

**Changes**:

**File**: Look for where chunks are created and metadata extracted (likely `code_chunking_service.py` or `code_indexing_service.py`)

**Pattern to find**:
```python
# OLD: Pass chunk source
metadata = await extractor.extract_metadata(
    source_code=chunk.source_code,  # ← Wrong!
    node=chunk_node,
    tree=chunk_tree
)
```

**New pattern**:
```python
# NEW: Pass full file source
metadata = await extractor.extract_metadata(
    source_code=full_file_source,  # ← Correct!
    node=chunk_node,
    tree=full_file_tree  # Parsed once at file level
)
```

**Key Implementation**:
1. Keep full file source in memory during indexing
2. Parse full file ONCE, reuse tree for all chunks
3. Pass full source + parsed tree to each chunk's metadata extraction

**Acceptance Criteria**:
- [ ] Indexing pipeline passes full file source
- [ ] Tree is parsed once per file (not per chunk)
- [ ] All chunks receive correct full source
- [ ] No memory leaks

**Effort**: 2-3 hours

---

### Story 28.4: Add Unit Tests for Byte Offset Fix

**Objective**: Verify byte offsets work correctly with full file source.

**Test Cases**:

**File**: `tests/services/metadata_extractors/test_typescript_extractor.py`

```python
import pytest
from api.services.metadata_extractors.typescript_extractor import TypeScriptMetadataExtractor
from tree_sitter_language_pack import get_parser

@pytest.mark.asyncio
async def test_byte_offset_with_full_file_source():
    """EPIC-28: Verify byte offsets use full file source correctly."""
    # Full file with UTF-8 characters and comments
    full_file_source = '''// Comment avec caractères spéciaux: é à ù
// Line 2
export function createSuccess<T>(value: T): Result<T> {
  return new Success<T>(value);
}

export function createFailure<T>(errors: Error[]): Result<T> {
  return new Failure<T>(errors);
}
'''

    # Parse full file
    parser = get_parser("typescript")
    tree = parser.parse(bytes(full_file_source, "utf8"))

    # Get first function node (createSuccess)
    query = tree.root_node.query("(function_declaration) @func")
    func_nodes = [capture[0] for capture in query.captures(tree.root_node)]
    create_success_node = func_nodes[0]

    # Extract metadata with FULL file source
    extractor = TypeScriptMetadataExtractor("typescript")
    metadata = await extractor.extract_metadata(
        source_code=full_file_source,  # Full file!
        node=create_success_node,
        tree=tree
    )

    # Verify: Should extract "Success" constructor, NOT truncated "cess"
    assert "Success" in metadata["calls"]
    assert "createSuccess" in str(metadata)

    # Verify: No truncated names
    for call in metadata["calls"]:
        assert len(call) > 2  # No single-char fragments
        assert call[0].isupper() or call[0].islower()  # Valid identifier start


@pytest.mark.asyncio
async def test_utf8_handling():
    """EPIC-28: Verify UTF-8 multi-byte characters don't break offsets."""
    full_file_source = '''export function créateSuccès() {
  return "Succès!";
}
'''

    parser = get_parser("typescript")
    tree = parser.parse(bytes(full_file_source, "utf8"))

    # Extract function node
    query = tree.root_node.query("(function_declaration) @func")
    func_node = list(query.captures(tree.root_node))[0][0]

    extractor = TypeScriptMetadataExtractor("typescript")
    metadata = await extractor.extract_metadata(
        source_code=full_file_source,
        node=func_node,
        tree=tree
    )

    # Should not crash or produce garbage
    assert metadata is not None
    assert isinstance(metadata.get("calls", []), list)


@pytest.mark.asyncio
async def test_multiple_chunks_same_file():
    """EPIC-28: Verify multiple chunks from same file use same full source."""
    full_file_source = '''export function first() { return second(); }
export function second() { return third(); }
export function third() { return "done"; }
'''

    parser = get_parser("typescript")
    tree = parser.parse(bytes(full_file_source, "utf8"))

    query = tree.root_node.query("(function_declaration) @func")
    func_nodes = [capture[0] for capture in query.captures(tree.root_node)]

    extractor = TypeScriptMetadataExtractor("typescript")

    # Extract metadata for all 3 functions with SAME full source
    all_metadata = []
    for func_node in func_nodes:
        metadata = await extractor.extract_metadata(
            source_code=full_file_source,  # Same full source!
            node=func_node,
            tree=tree
        )
        all_metadata.append(metadata)

    # Verify cross-function calls detected
    first_calls = all_metadata[0]["calls"]
    assert "second" in first_calls  # first() calls second()

    second_calls = all_metadata[1]["calls"]
    assert "third" in second_calls  # second() calls third()
```

**Acceptance Criteria**:
- [ ] All tests pass
- [ ] UTF-8 handling verified
- [ ] Multi-chunk scenario tested
- [ ] No truncated call names

**Effort**: 1 hour

---

### Story 28.5: Re-index CVGenerator and Validate

**Objective**: Re-index CVGenerator with byte offset fix, validate 50%+ edge ratio.

**Steps**:

1. **Delete old CVGenerator data**:
```sql
DELETE FROM edges WHERE source_node_id IN (SELECT node_id FROM nodes WHERE properties->>'repository' = 'CVGenerator');
DELETE FROM nodes WHERE properties->>'repository' = 'CVGenerator';
DELETE FROM code_chunks WHERE repository = 'CVGenerator';
```

2. **Re-index with updated code**:
```bash
python3 /tmp/index_code_test.py
```

3. **Validate results**:
```sql
-- Check edge count
SELECT COUNT(*) FROM edges e
JOIN nodes n ON e.source_node_id = n.node_id
WHERE n.properties->>'repository' = 'CVGenerator';

-- Check call quality (sample)
SELECT
  metadata->'calls' as calls,
  jsonb_array_length(metadata->'calls') as call_count
FROM code_chunks
WHERE repository = 'CVGenerator'
  AND metadata->'calls' IS NOT NULL
ORDER BY call_count DESC
LIMIT 10;

-- Verify no truncated names
SELECT DISTINCT jsonb_array_elements_text(metadata->'calls') as call_name
FROM code_chunks
WHERE repository = 'CVGenerator'
  AND metadata->'calls' IS NOT NULL
ORDER BY call_name
LIMIT 50;
```

**Success Criteria**:
- [ ] Edge ratio: **50-60%** (290-350 edges)
- [ ] Call names are clean (no truncation like `"teSuccess"`)
- [ ] Top called functions are legitimate project code
- [ ] No framework noise in top 10 calls

**Expected Results**:

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| **Edges** | 186 | 290-350 | 290+ ✅ |
| **Ratio** | 32% | 50-60% | 50%+ ✅ |
| **Corruption** | 80% | 0% | 0% ✅ |

**Effort**: 1 hour

---

## 📈 Estimated Impact

### Quantitative

- **+100-150 edges** (from 186 to 290-350)
- **+18-28 percentage points** in edge ratio
- **-80% call corruption** (from 80% to 0%)

### Qualitative

- ✅ Eliminates major bug in metadata extraction
- ✅ Unlocks future enhancements (cross-chunk analysis)
- ✅ Improves code quality and maintainability
- ✅ Reduces re-parsing overhead (performance gain)

---

## 🛡️ Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| API breaking changes | Medium | Medium | Add backward compat parameters |
| Memory usage increase | Low | Low | File source already in memory during indexing |
| Implementation complexity | Low | Low | Well-isolated change, clear scope |
| Testing coverage gaps | Low | High | Comprehensive unit + integration tests |

**Overall Risk**: ✅ **LOW**

---

## 📚 Dependencies

### Blocked By
- None (can start immediately)

### Blocks
- EPIC-27 Phase 3 (scope-aware extraction)
- Future: Cross-file dependency analysis
- Future: Type-based call resolution

---

## 🎯 Acceptance Criteria

### Technical
- [ ] TypeScript extractor uses full file source
- [ ] Python extractor uses full file source
- [ ] Indexing pipeline passes full source
- [ ] No re-parsing of chunks
- [ ] All tests pass

### Business
- [ ] Edge ratio: 50%+ (target: 290+ edges)
- [ ] Call corruption: 0% (no truncated names)
- [ ] Top calls are project functions (not framework)
- [ ] Performance: No degradation (or improvement)

---

## 📖 Documentation

### Created
- [x] EPIC-28 ULTRATHINK (deep analysis)
- [x] EPIC-28 README (this document)

### To Create
- [ ] Story 28.1-28.5 completion reports
- [ ] EPIC-28 final completion report
- [ ] Update NEXT_STEPS.md with results

---

## 🚀 Implementation Order

**Recommended sequence**:

1. **Story 28.1** (2h) - Update TypeScript extractor API
2. **Story 28.4** (1h) - Add unit tests (TDD approach)
3. **Story 28.3** (2-3h) - Update indexing pipeline
4. **Story 28.2** (1h) - Update Python extractor
5. **Story 28.5** (1h) - Re-index and validate

**Total**: 6-7 hours

**Parallelization**: Stories 28.1 and 28.2 can be done in parallel.

---

## 💡 Future Enhancements

After EPIC-28 succeeds:

1. **LRU Cache for File Sources**: Reduce memory usage
2. **Cross-Chunk Analysis**: Detect file-level dependencies
3. **Type Inference**: Use full file for better type resolution
4. **Import Resolution**: Resolve cross-file imports correctly

---

## 📞 Support

**Questions?** Check:
- `EPIC-28_BYTE_OFFSET_FIX_ULTRATHINK.md` for deep technical analysis
- `EPIC-27_PHASE_2_FINDINGS.md` for problem discovery
- `EPIC-27_PHASE_1_COMPLETION_REPORT.md` for Phase 1 context

---

**Status**: 🎯 READY TO IMPLEMENT
**Estimated Completion**: 6-7 hours
**Expected Outcome**: 50-60% edge ratio (290-350 edges)
