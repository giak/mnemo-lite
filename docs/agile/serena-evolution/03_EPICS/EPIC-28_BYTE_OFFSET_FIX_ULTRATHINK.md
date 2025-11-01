# EPIC-28: Byte Offset Fix - Deep Analysis & Solution Design

**Date**: 2025-11-01
**Status**: 🎯 READY TO IMPLEMENT
**Context**: EPIC-27 Phase 2 revealed critical byte offset bug preventing 50%+ edge ratio

---

## 🎯 Executive Summary

**Problem**: Tree-sitter byte offsets don't align with chunk source code, causing 80% of extracted call names to be corrupted.

**Impact**:
- Current: 186 edges (32% ratio)
- Potential: 290-350 edges (50-60% ratio)
- **Blocked improvement**: +100-150 edges

**Solution**: Pass full file source to metadata extractors instead of chunk source.

**Effort**: 4-6 hours (2-3 stories)

**Risk**: Low (well-isolated change, backward compatible)

---

## 📊 Problem Analysis

### Current Architecture (Broken)

```
1. File Indexing
   ├─> Parse full file with tree-sitter
   ├─> Extract chunks using byte offsets
   └─> Each chunk stores: chunk.source_code = file_source[node.start_byte:node.end_byte]

2. Metadata Extraction (PER CHUNK)
   ├─> Re-parse CHUNK source with tree-sitter
   ├─> Get byte offsets (relative to chunk, not file!)
   └─> Slice chunk_source[offset_start:offset_end]  ← MISALIGNMENT!

Result: Byte offsets don't match source code boundaries
```

### Why Byte Offsets Misalign

**Example**:

Full file (`result.utils.ts`):
```typescript
// Line 1: Comments (20 bytes)
// Line 2: Imports (50 bytes)
// Line 3: Empty line
export function createSuccess<T>(value: T) {  ← CHUNK STARTS HERE (Line 4, byte 70)
  return new Success<T>(value);
}
```

**Chunking**:
```python
# Chunk created from lines 4-6
chunk.source_code = "export function createSuccess<T>(value: T) {\n  return new Success<T>(value);\n}"
# This is byte 70-130 of FULL FILE
# But stored as standalone string starting at byte 0
```

**Metadata Extraction**:
```python
# Parse chunk source (starts at byte 0 in chunk)
tree = parser.parse(bytes(chunk.source_code, "utf8"))

# Tree-sitter returns offsets relative to chunk
# But if tree-sitter has any UTF-8 issues or BOM markers,
# offsets can be WRONG

# Example: Extract "createSuccess"
call_node_start = 15  # Tree-sitter says start at byte 15
call_text = chunk.source_code[15:28]  # Slices "teSuccess" instead of "createSuccess"
```

**Root Causes**:
1. **UTF-8 encoding mismatches**: Multi-byte characters shift byte positions
2. **BOM markers**: Invisible characters at file start
3. **Newline normalization**: `\n` vs `\r\n` differences
4. **Re-parsing overhead**: Parsing twice (full file, then chunk) introduces errors

---

### Evidence of Corruption

From database analysis (EPIC-27 Phase 2):

| Full File Function | Extracted Call | Bytes Lost | Corruption Type |
|-------------------|----------------|------------|-----------------|
| `createSuccess` | `teSuccess` | 4 | Prefix truncation |
| `createFailure` | `eFailure` | 7 | Prefix truncation |
| `SuccessWithWarnings` | `ccessWithWarnings` | 2 | Prefix truncation |
| `filter` | `ilter` | 1 | Prefix truncation |
| `suggestionForZodError` | `uggestionForZodError` | 1 | Prefix truncation |

**Pattern**: Consistent prefix truncation of 1-7 bytes

**Hypothesis**: UTF-8 multi-byte characters (é, à, etc.) in comments/docstrings before chunk cause byte offset shifts.

---

## 🔬 Deep Dive: Current Code Flow

### File: `api/services/code_chunking_service.py`

**Line 65**: Parse full file
```python
def parse(self, source_code: str) -> Tree:
    """Parse source code to AST tree."""
    return self.parser.parse(bytes(source_code, "utf8"))
```

**Line 145**: Extract chunk source
```python
node_source = source_code[node.start_byte:node.end_byte]
```

✅ **This is correct** - byte offsets work because we're slicing the SAME source that was parsed.

### File: `api/services/metadata_extractor_service.py`

**Line 171**: Call TypeScript extractor
```python
metadata = await extractor.extract_metadata(source_code, node, tree)
```

**Problem**: `source_code` here is the CHUNK source, not full file!

Let me trace where this comes from...

### File: `api/services/metadata_extractors/typescript_extractor.py`

**Line 388-430**: `extract_metadata()` signature
```python
async def extract_metadata(
    self,
    source_code: str,  # ← This is CHUNK source!
    node: Node,
    tree: Tree
) -> dict[str, Any]:
    # Parse chunk source
    tree = parser.parse(bytes(source_code, "utf8"))  # ← RE-PARSING!

    # Extract calls using byte offsets
    call_text = source_code[start_byte:end_byte]  # ← MISALIGNMENT!
```

**Root Issue**: We're re-parsing chunk source, getting NEW byte offsets that don't match the chunk boundaries.

---

## 🎨 Solution Design

### ✅ Option A: Pass Full File Source (RECOMMENDED)

**Approach**: Modify metadata extraction to use full file source + chunk boundaries.

**Architecture**:
```
1. File Indexing
   ├─> Parse full file ONCE with tree-sitter
   ├─> Keep full file source in memory
   └─> For each chunk:
       ├─> Store chunk.source_code (for display)
       ├─> Store chunk.start_line, chunk.end_line
       └─> Pass FULL_FILE_SOURCE + chunk_node to metadata extractor

2. Metadata Extraction
   ├─> Receive full file source
   ├─> Use existing parsed tree (NO re-parsing!)
   ├─> Extract metadata using byte offsets from FULL FILE
   └─> Byte offsets are CORRECT!
```

**Benefits**:
- ✅ Correct byte offsets guaranteed
- ✅ No re-parsing (performance improvement!)
- ✅ Enables cross-chunk analysis (imports, types)
- ✅ Simpler code (single source of truth)

**Trade-offs**:
- ❌ Higher memory usage (full file in memory per chunk)
- ❌ API signature changes (backward incompatible)

**Implementation Complexity**: **LOW**

---

### ❌ Option B: Adjust Byte Offsets (NOT RECOMMENDED)

**Approach**: Calculate offset adjustment between chunk and full file.

**Formula**:
```python
chunk_start_offset = len(full_file_source[:chunk.start_line].encode('utf-8'))
adjusted_offset = tree_sitter_offset + chunk_start_offset
```

**Problems**:
1. UTF-8 encoding is non-trivial (multi-byte chars, BOM, newlines)
2. Requires both full file AND chunk source in memory
3. Error-prone with edge cases (tabs, Unicode, mixed encodings)
4. Doesn't fix re-parsing overhead

**Verdict**: ❌ **DO NOT IMPLEMENT** - Too complex, error-prone

---

### ❌ Option C: Re-chunk at Full-File Level (NOT RECOMMENDED)

**Approach**: Extract metadata before chunking, assign to chunks afterward.

**Problems**:
1. Breaks current architecture (major refactoring)
2. Loses chunk-specific context
3. Doesn't solve fundamental byte offset issue

**Verdict**: ❌ **DO NOT IMPLEMENT** - Too invasive

---

## 🎯 Recommended Solution: Option A

### Implementation Plan

#### Story 28.1: Refactor CodeChunk to Include File Source Reference

**Goal**: Store reference to full file source alongside chunk source.

**Changes**:

**File**: `api/models/code_chunk_models.py`
```python
class CodeChunk(Base):
    # Existing fields...
    source_code: str  # Chunk source (for display)

    # EPIC-28: Add full file source reference
    full_file_source: str | None = None  # Full file source (for metadata extraction)

    # OR: Store file_id and retrieve from cache
    file_id: str | None = None  # Hash of file path for cache lookup
```

**Trade-off Decision**:
- **Option 1**: Store `full_file_source` directly → Simple but memory-heavy
- **Option 2**: Store `file_id` + use LRU cache → Memory-efficient but complex

**Recommendation**: Start with Option 1 (simple), optimize later if needed.

**Effort**: 1 hour

---

#### Story 28.2: Update Metadata Extraction API

**Goal**: Modify metadata extractors to accept full file source.

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
```

**New signature**:
```python
async def extract_metadata(
    self,
    source_code: str,          # FULL FILE source
    node: Node,                # Chunk node (for scoping)
    tree: Tree,                # Full file tree
    chunk_source: str | None = None  # Optional: chunk source for backward compat
) -> dict[str, Any]:
    """
    Extract metadata from TypeScript/JavaScript code.

    Args:
        source_code: FULL file source code (EPIC-28: ensures correct byte offsets)
        node: Chunk node (function/class/method definition)
        tree: Full file AST tree
        chunk_source: (Optional) Chunk source for display (backward compatibility)

    Returns:
        Metadata dict with imports and calls
    """
    # NO RE-PARSING! Use existing tree
    # Extract calls using byte offsets from FULL FILE
    # Byte offsets are correct!
```

**Key Changes**:
1. Remove `parser.parse()` call (use provided tree)
2. Update byte slicing to use `source_code` (full file)
3. Add backward compatibility parameter (optional)

**Effort**: 2 hours

---

#### Story 28.3: Update Python Extractor Similarly

**Goal**: Apply same fix to Python metadata extraction.

**File**: `api/services/metadata_extractor_service.py`

**Current**: Uses `ast.get_source_segment()` which handles offsets correctly, BUT we can still improve by avoiding re-parsing.

**Changes**:
- Update `_extract_python_metadata()` to use full file source
- Ensure `ast.get_source_segment()` uses full file tree

**Effort**: 1 hour

---

#### Story 28.4: Update Code Indexing Pipeline

**Goal**: Pass full file source through indexing pipeline.

**File**: `api/services/code_indexing_service.py` (or wherever chunks are created)

**Changes**:
```python
# When creating chunks
for chunk_node in chunk_nodes:
    chunk = CodeChunk(
        source_code=chunk_source,       # Chunk source (for display)
        full_file_source=full_file_source,  # EPIC-28: Full file source
        # ... other fields
    )

    # Extract metadata with full file source
    metadata = await metadata_service.extract_metadata(
        source_code=full_file_source,  # ← Full file!
        node=chunk_node,
        tree=full_tree
    )
```

**Effort**: 1-2 hours

---

#### Story 28.5: Re-index and Validate

**Goal**: Re-index CVGenerator and validate edge ratio improvement.

**Steps**:
1. Delete existing CVGenerator data
2. Re-index with updated code
3. Validate metadata quality:
   - Check extracted calls (should be clean names, no truncation)
   - Verify edge count: expect 250-350 edges (50-60% ratio)

**Success Criteria**:
- ✅ No truncated call names in database
- ✅ Edge ratio: 50-60% (target: 290-350 edges)
- ✅ Top called functions are legitimate project code

**Effort**: 1 hour

---

### Total Effort: 5-7 hours

| Story | Effort | Priority |
|-------|--------|----------|
| 28.1: CodeChunk model update | 1h | Critical |
| 28.2: TypeScript extractor update | 2h | Critical |
| 28.3: Python extractor update | 1h | High |
| 28.4: Indexing pipeline update | 1-2h | Critical |
| 28.5: Re-index and validate | 1h | Critical |
| **Total** | **6-7h** | |

---

## 📈 Expected Impact

### Before EPIC-28
- **186 edges (32% ratio)**
- Corrupted call names: 80%
- Example: `createSuccess` → `teSuccess`

### After EPIC-28
- **250-350 edges (50-60% ratio)**
- Corrupted call names: 0%
- Example: `createSuccess` → `createSuccess` ✅

### Breakdown of New Edges

| Category | Current | After Fix | Improvement |
|----------|---------|-----------|-------------|
| **Constructor calls** | 50 | 50 | +0 (already work) |
| **Method calls** | 136 | 180-220 | +44-84 |
| **Function calls** | 0 | 20-50 | +20-50 |
| **Chained calls** | 0 | 0-30 | +0-30 |
| **Total** | **186** | **250-350** | **+64-164** |

**Conservative estimate**: +100 edges → 286 edges (49% ratio)
**Optimistic estimate**: +150 edges → 336 edges (58% ratio)

---

## 🛡️ Risk Assessment

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Memory usage spike | Medium | Low | Use file_id + LRU cache if needed |
| API breaking changes | High | Medium | Add backward compat parameter |
| Python extraction breaks | Low | High | Test thoroughly, Python uses ast (safer) |
| Performance degradation | Low | Low | Avoid re-parsing (performance gain!) |

### Business Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Implementation takes longer | Medium | Low | Phased rollout (TypeScript first) |
| Edge quality doesn't improve | Low | High | Validate with sample files first |
| Breaks existing functionality | Low | High | Comprehensive testing |

**Overall Risk**: ✅ **LOW** - Well-isolated change with clear benefits

---

## 🧪 Validation Strategy

### Phase 1: Unit Tests

**File**: `tests/test_typescript_extractor.py`

```python
def test_byte_offset_with_full_file():
    """Verify byte offsets work with full file source."""
    full_file = '''// Comment (20 bytes)
export function createSuccess<T>(value: T) {
  return new Success<T>(value);
}'''

    # Parse full file
    tree = parser.parse(bytes(full_file, "utf8"))
    chunk_node = get_function_node(tree, "createSuccess")

    # Extract metadata with FULL file source
    metadata = await extractor.extract_metadata(full_file, chunk_node, tree)

    # Validate calls
    assert "Success" in metadata["calls"]  # Constructor call
    assert "createSuccess" in str(metadata)  # NOT "teSuccess"!
```

### Phase 2: Integration Tests

**Test**: Re-index 10 sample TypeScript files, verify:
- ✅ No truncated call names
- ✅ Edge ratio > 45%
- ✅ No framework noise in top calls

### Phase 3: Full Re-index

**Test**: Re-index CVGenerator (240 files, 934 chunks)
- ✅ Edge ratio: 50-60%
- ✅ Total edges: 250-350
- ✅ Top calls are project functions

---

## 🎯 Success Metrics

### Quantitative

| Metric | Before | Target | Stretch Goal |
|--------|--------|--------|--------------|
| **Edge ratio** | 32% | 50%+ | 60%+ |
| **Total edges** | 186 | 290+ | 350+ |
| **Call corruption rate** | 80% | 0% | 0% |
| **Re-parsing count** | 2x | 1x | 1x |

### Qualitative

- ✅ Clean call names in database (no truncation)
- ✅ Framework noise < 20% (vs 40% current)
- ✅ Top called functions are project code
- ✅ No performance degradation

---

## 📚 Technical Deep Dive

### Why Tree-Sitter Byte Offsets Break

Tree-sitter uses **byte positions**, not character positions. This is critical for performance but fragile with UTF-8.

**Example**:

```typescript
// Fichier avec caractères UTF-8
export function créateSuccess() {  // 'é' = 2 bytes in UTF-8
  return new Success();
}
```

**Full file parsing**:
- `créateSuccess` starts at byte 20 (accounting for 2-byte `é`)
- Tree-sitter returns: `start_byte=20, end_byte=34`
- Slice `full_source[20:34]` → `"créateSuccess"` ✅

**Chunk parsing** (current, broken):
```python
chunk_source = "export function créateSuccess() { ... }"
tree_chunk = parser.parse(bytes(chunk_source, "utf8"))
# Parser sees chunk starting at byte 0, ignores previous 20 bytes
# Returns: start_byte=16, end_byte=30 (WRONG!)
# Slice: chunk_source[16:30] → "téateSuccess" ❌
```

**Fix**: Use full file source with original byte offsets → correct slicing.

---

### Alternative: Use Character Offsets

Tree-sitter provides `row` and `column` (line/character offsets) instead of byte offsets.

**API**:
```python
node.start_point  # (row, column)
node.end_point    # (row, column)
```

**Approach**:
```python
# Convert to line:column instead of bytes
start_line, start_col = node.start_point
end_line, end_col = node.end_point

# Extract by lines
lines = source_code.split('\n')
if start_line == end_line:
    call_text = lines[start_line][start_col:end_col]
else:
    # Multi-line (rare for function names)
    call_text = lines[start_line][start_col:] + ...
```

**Verdict**: ❌ More complex, edge cases with multi-line names

**Stick with full file + byte offsets** (simpler, more reliable)

---

## 🚀 Implementation Checklist

### Pre-Implementation
- [ ] Review current code flow (chunking → metadata extraction)
- [ ] Identify all callers of `extract_metadata()`
- [ ] Design backward-compatible API changes
- [ ] Create test plan

### Story 28.1: CodeChunk Model
- [ ] Add `full_file_source` field to CodeChunk
- [ ] Update database migration if needed
- [ ] Update tests

### Story 28.2: TypeScript Extractor
- [ ] Update `extract_metadata()` signature
- [ ] Remove re-parsing logic
- [ ] Update byte slicing to use full file source
- [ ] Add unit tests
- [ ] Verify backward compatibility

### Story 28.3: Python Extractor
- [ ] Update `_extract_python_metadata()`
- [ ] Ensure ast uses full file tree
- [ ] Add unit tests

### Story 28.4: Indexing Pipeline
- [ ] Update chunk creation to pass full file source
- [ ] Update metadata extraction calls
- [ ] Test with sample files
- [ ] Validate no regressions

### Story 28.5: Validation
- [ ] Delete old CVGenerator data
- [ ] Re-index with updated code
- [ ] Verify edge ratio: 50%+
- [ ] Check call quality (no truncation)
- [ ] Create completion report

---

## 💡 Bonus Optimizations

### After EPIC-28 Success

**Optimization 1: LRU Cache for Full File Sources**
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_full_file_source(file_id: str) -> str:
    """Cache full file sources to reduce memory."""
    return read_file(file_id)
```

**Optimization 2: Stream Processing**
Process files one at a time instead of loading all in memory.

**Optimization 3: Incremental Re-indexing**
Only re-index changed files, preserve old metadata.

---

## 📊 Comparison: Other Approaches

### Approach: Anchor-Based Extraction

**Idea**: Use unique anchor strings to locate calls instead of byte offsets.

**Example**:
```python
# Find "createSuccess" by searching in source
call_position = source_code.find("createSuccess")
```

**Problems**:
- ❌ Ambiguous if function appears multiple times
- ❌ Doesn't handle method chaining
- ❌ Misses calls inside strings/comments

**Verdict**: ❌ Not reliable

### Approach: Regex-Based Extraction

**Idea**: Use regex to extract function calls instead of tree-sitter.

**Problems**:
- ❌ Can't handle nested structures
- ❌ Misses chained calls
- ❌ False positives in strings/comments
- ❌ No type information

**Verdict**: ❌ Inferior to AST-based extraction

### Approach: LSP-Based Extraction

**Idea**: Use Language Server Protocol for call resolution.

**Benefits**:
- ✅ Accurate type information
- ✅ Cross-file resolution
- ✅ Handles complex scenarios

**Problems**:
- ❌ Requires LSP server setup
- ❌ Much slower than tree-sitter
- ❌ Overkill for our use case

**Verdict**: ⚠️ Future enhancement (Phase 3+)

---

## 🎯 Conclusion

**EPIC-28 is a HIGH-IMPACT, LOW-RISK fix that will unlock 50-60% edge ratio.**

**Key Benefits**:
1. ✅ Fixes 80% call corruption
2. ✅ Adds 100-150 new edges
3. ✅ Improves performance (no re-parsing)
4. ✅ Enables future enhancements (cross-chunk analysis)

**Recommended Action**: Implement EPIC-28 immediately (6-7 hours investment).

**ROI**:
- Time investment: 6-7 hours
- Edge improvement: +100-150 edges (+64-164% increase)
- Code quality: Eliminates major bug
- **Value**: ✅ VERY HIGH

---

**Next Step**: Create EPIC-28 stories and begin implementation with Story 28.1.
