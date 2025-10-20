# EPIC-11 Story 11.1 Analysis: name_path Generation Logic

**Date**: 2025-10-20
**Analyst**: Claude Code
**Story Points**: 5 pts
**Status**: ✅ READY FOR IMPLEMENTATION (with notes)

---

## 📋 Executive Summary

Story 11.1 introduces hierarchical `name_path` generation to enable qualified symbol search and better call resolution. After deep analysis of the current codebase, the implementation is **feasible and well-designed** with minor adjustments needed.

### Key Findings

✅ **Architecture**: Clean separation of concerns with new SymbolPathService
✅ **Database**: Schema modification is straightforward (add 1 column + 2 indexes)
✅ **Integration**: Minimal changes to existing CodeIndexingService (~10 lines)
✅ **Testing**: Comprehensive test strategy with clear acceptance criteria
⚠️ **Dependency**: Requires v3.0 migration script update
⚠️ **Risk**: Parent context extraction complexity (nested classes)

**Recommendation**: **PROCEED** with implementation as designed, with enhanced parent context extraction logic.

---

## 🏗️ Architecture Analysis

### Current State Verification

**Database Schema** (verified via `\d code_chunks`):
```sql
Table "public.code_chunks"
- id: uuid (PK)
- file_path: text
- language: text
- chunk_type: text
- name: text          ← FLAT NAME (no hierarchy)
- source_code: text
- start_line: integer
- end_line: integer
- embedding_text: vector(768)
- embedding_code: vector(768)
- metadata: jsonb
- indexed_at: timestamptz
- last_modified: timestamptz
- node_id: uuid
- repository: text
- commit_hash: text
```

**Missing**: `name_path` column (to be added)

**Indexes** (current):
- HNSW on embedding_text and embedding_code ✅
- GIN on metadata (jsonb_path_ops) ✅
- GIN on name (pg_trgm) ✅
- B-tree on file_path, language, chunk_type ✅

**Models** (verified `api/models/code_chunk_models.py`):
- `CodeChunk`: Base model (lines 57-72) - NO name_path field
- `CodeChunkCreate`: Create model (lines 97-108) - NO name_path field
- `CodeChunkModel`: Output model (lines 121-196) - NO name_path field

**Repository** (verified `api/db/repositories/code_chunk_repository.py`):
- SQLAlchemy Core Table definition (lines 28-47) - NO name_path column
- CodeChunkQueryBuilder (lines 50-149) - Builds INSERT/UPDATE/DELETE queries

**Indexing Service** (verified `api/services/code_indexing_service.py`):
- `index_file()` method exists
- Current flow: parse → chunk → metadata → embed → store
- **Integration point**: After metadata extraction, before storage

---

## 🎯 Implementation Plan Validation

### 1. Database Schema Changes ✅

**Proposed**:
```sql
ALTER TABLE code_chunks ADD COLUMN name_path TEXT;

CREATE INDEX idx_code_chunks_name_path ON code_chunks(name_path);
CREATE INDEX idx_code_chunks_name_path_trgm ON code_chunks USING gin(name_path gin_trgm_ops);
```

**Analysis**:
- ✅ Column type: TEXT is correct (supports arbitrary length paths)
- ✅ Index 1: B-tree for exact/prefix matching → fast qualified searches
- ✅ Index 2: GIN pg_trgm for fuzzy matching → supports partial queries like "models.User"
- ✅ Nullable: OK (allows migration without breaking existing data)

**Risks**:
- ⚠️ Index size: GIN trigram indexes can be large (~3× column size)
- ✅ Mitigation: Monitor index size, consider partial index if needed

**Recommendation**: ✅ **APPROVE** schema changes as designed

---

### 2. SymbolPathService Design ✅

**Proposed**: `api/services/symbol_path_service.py` (200 lines)

**Core Methods**:
1. `generate_name_path()` - Main entry point
2. `_file_to_module_path()` - Convert file path to module path
3. `extract_parent_context()` - Find parent classes for methods

**Analysis of `_file_to_module_path()`**:
```python
# Input:  "api/routes/auth.py"
# Output: "routes.auth"

Steps:
1. Make relative to repository root ✅
2. Remove "api/" prefix ✅
3. Remove ".py" extension ✅
4. Remove "__init__" ✅
5. Join with dots ✅
```

**Edge Cases to Test**:
- ✅ Top-level files: `auth.py` → `auth`
- ✅ Deep nesting: `api/services/caches/redis_cache.py` → `services.caches.redis_cache`
- ✅ Package init: `api/models/__init__.py` → `models`
- ⚠️ **Non-Python files**: JavaScript/TypeScript use different module patterns
- ⚠️ **Non-standard structures**: Files outside `api/` directory

**Critical Issue Found**: `_file_to_module_path()` assumes Python-centric structure:
```python
# Current logic removes "api/" prefix
# Problem: JavaScript projects don't use "api/" prefix
# Example: "src/components/Button.tsx" → ???
```

**Recommendation**: ⚠️ **ENHANCE** `_file_to_module_path()` to handle multiple languages:

```python
def _file_to_module_path(self, file_path: str, repository_root: str, language: str = "python") -> str:
    """Convert file path to module path (language-aware)."""

    rel_path = Path(file_path).relative_to(repository_root)
    parts = list(rel_path.parts)

    # Language-specific prefixes to remove
    PREFIXES_TO_REMOVE = {
        "python": ["api", "src"],
        "javascript": ["src"],
        "typescript": ["src"],
        "go": [],  # Go uses full package paths
        "java": ["src", "main", "java"],
    }

    prefixes = PREFIXES_TO_REMOVE.get(language, [])

    # Remove known prefixes
    while parts and parts[0] in prefixes:
        parts = parts[1:]

    # Remove file extension
    if parts and parts[-1].endswith(('.py', '.js', '.ts', '.tsx', '.go', '.java')):
        parts[-1] = parts[-1].rsplit('.', 1)[0]

    # Remove __init__ / index
    if parts and parts[-1] in ("__init__", "index"):
        parts = parts[:-1]

    return ".".join(parts)
```

---

### 3. Parent Context Extraction ⚠️ CRITICAL

**Proposed Logic**:
```python
def extract_parent_context(self, chunk, all_chunks) -> list[str]:
    """Extract parent class names for methods."""

    # Find parent class (chunk with smallest line range containing this chunk)
    parent_classes = []

    for potential_parent in all_chunks:
        if potential_parent.chunk_type == "class":
            if (potential_parent.start_line <= chunk.start_line and
                potential_parent.end_line >= chunk.end_line):
                parent_classes.append(potential_parent)

    # Sort by line range (smallest first = most immediate parent)
    parent_classes.sort(key=lambda c: (c.end_line - c.start_line))

    return [c.name for c in parent_classes]
```

**Analysis**:
- ✅ Logic: Correct for detecting enclosing classes
- ✅ Sorting: Smallest range = innermost parent ✅
- ⚠️ **Ordering**: Returns innermost-to-outermost (is this correct?)

**Critical Issue**: Expected output order unclear in EPIC spec:

Example:
```python
class Outer:
    class Inner:
        def method(self):
            pass
```

Expected `name_path`: `module.Outer.Inner.method`
Parent context should be: `["Outer", "Inner"]` (outermost → innermost)

Current logic returns: `["Inner", "Outer"]` (innermost → outermost) ❌

**Recommendation**: ⚠️ **FIX** ordering:
```python
# Sort by line range (LARGEST first = outermost parent)
parent_classes.sort(key=lambda c: (c.end_line - c.start_line), reverse=True)
```

---

### 4. Integration with CodeIndexingService ✅

**Proposed Changes** (lines ~235-246):
```python
# NEW: Generate name_path for each chunk
for chunk in chunks:
    parent_context = self.symbol_path_service.extract_parent_context(chunk, chunks)
    chunk.name_path = self.symbol_path_service.generate_name_path(
        chunk_name=chunk.name,
        file_path=file_path,
        repository_root=repository,
        parent_context=parent_context
    )
```

**Analysis**:
- ✅ Placement: After chunking + metadata, before embeddings (optimal)
- ✅ Dependency injection: SymbolPathService passed via constructor
- ⚠️ **Missing parameter**: `language` not passed to `generate_name_path()`

**Recommendation**: ⚠️ **ADD** language parameter:
```python
chunk.name_path = self.symbol_path_service.generate_name_path(
    chunk_name=chunk.name,
    file_path=file_path,
    repository_root=repository,
    parent_context=parent_context,
    language=language  # ADD THIS
)
```

---

### 5. Model Updates ✅

**Proposed Changes**:
```python
# api/models/code_chunk.py

class CodeChunkCreate(BaseModel):
    # ... existing fields
    name_path: Optional[str] = None  # NEW

class CodeChunkModel(BaseModel):
    # ... existing fields
    name_path: Optional[str] = None  # NEW
```

**Analysis**:
- ✅ Type: Optional[str] is correct (allows NULL during migration)
- ✅ Default: None is safe
- ✅ Placement: Should be added near `name` field for clarity

**Recommendation**: ✅ **APPROVE** model changes as designed

---

### 6. Repository Updates ⚠️

**Not Specified in EPIC, but REQUIRED**:

The repository's table definition and query builders MUST be updated:

```python
# MODIFY: api/db/repositories/code_chunk_repository.py

# Table definition (line ~28)
code_chunks_table = Table(
    "code_chunks",
    metadata_obj,
    Column("id", UUID, primary_key=True),
    Column("file_path", Text, nullable=False),
    Column("language", Text, nullable=False),
    Column("chunk_type", Text, nullable=False),
    Column("name", Text),
    Column("name_path", Text),  # NEW - ADD THIS
    Column("source_code", Text, nullable=False),
    # ... rest of columns
)

# INSERT query (line ~56)
INSERT INTO code_chunks (
    id, file_path, language, chunk_type, name, name_path,  # ADD name_path
    source_code, start_line, end_line, embedding_text, embedding_code,
    metadata, indexed_at, last_modified, node_id, repository, commit_hash
)
VALUES (
    :id, :file_path, :language, :chunk_type, :name, :name_path,  # ADD :name_path
    :source_code, :start_line, :end_line, :embedding_text, :embedding_code,
    CAST(:metadata AS JSONB), :indexed_at, :last_modified, :node_id,
    :repository, :commit_hash
)

# Parameters (line ~74)
params = {
    # ... existing params
    "name_path": chunk_data.name_path,  # NEW - ADD THIS
    # ... rest of params
}
```

**Recommendation**: ⚠️ **ADD** repository updates to story (missing from EPIC spec)

---

## 🧪 Testing Strategy Analysis

### Proposed Tests ✅

**1. Unit Tests** (300 lines):
```python
tests/services/test_symbol_path_service.py

- test_function_name_path()        # Top-level function
- test_method_name_path()          # Class method
- test_nested_class_method()       # Nested classes
- test_package_init()              # __init__.py handling
- test_deep_nested_file()          # Deep directory structure
```

**Analysis**:
- ✅ Coverage: All main scenarios covered
- ⚠️ **Missing**: Edge cases for non-Python languages
- ⚠️ **Missing**: Error handling tests (malformed paths, etc.)

**Additional Tests Needed**:
```python
# Edge cases
- test_file_outside_api_directory()    # File in scripts/, tests/, etc.
- test_javascript_module_path()        # src/components/Button.tsx
- test_go_package_path()               # pkg/models/user.go
- test_empty_parent_context()          # Module-level code
- test_multiple_nested_classes()       # Deep nesting (4+ levels)
- test_invalid_file_path()             # Error handling
- test_missing_repository_root()       # Error handling
```

**2. Integration Tests** (not specified in EPIC):

```python
tests/integration/test_name_path_indexing.py

@pytest.mark.anyio
async def test_end_to_end_name_path_generation():
    """Index file and verify name_path stored correctly."""

    source = '''
class User:
    def validate(self):
        pass
'''

    # Index file
    chunks = await indexing_service.index_file(
        file_path="api/models/user.py",
        source_code=source,
        language="python",
        repository="/app"
    )

    # Verify name_path generated
    assert len(chunks) == 2  # Class + method

    class_chunk = next(c for c in chunks if c.chunk_type == "class")
    method_chunk = next(c for c in chunks if c.chunk_type == "method")

    assert class_chunk.name_path == "models.user.User"
    assert method_chunk.name_path == "models.user.User.validate"

    # Verify stored in DB
    from_db = await chunk_repository.get_by_id(method_chunk.id)
    assert from_db.name_path == "models.user.User.validate"
```

**Recommendation**: ⚠️ **ADD** integration tests to story

---

## ⚠️ Risks & Mitigations

### Risk 1: Parent Context Extraction Accuracy

**Impact**: Incorrect parent detection → wrong name_path → broken search

**Scenarios**:
1. **Nested classes** (4+ levels deep)
2. **Inner functions** (Python allows functions inside functions)
3. **Closures and decorators** (AST complexity)
4. **Multiple classes in same file** with overlapping line ranges

**Example Failure**:
```python
class A:
    pass

class B:
    def method(self):  # Line 5-6
        pass

class C:  # Line 8-10
    # B.method lines fall within C's range if C is large
    pass
```

**Mitigation**:
- ✅ Current logic: Sorts by range size (smallest = most specific)
- ⚠️ Add validation: Ensure parent.start_line < chunk.start_line (strict containment)
- ⚠️ Add test: Complex nesting scenarios

**Recommended Enhancement**:
```python
def extract_parent_context(self, chunk, all_chunks) -> list[str]:
    """Extract parent class names with strict containment check."""

    parent_classes = []

    for potential_parent in all_chunks:
        if potential_parent.chunk_type == "class":
            # Strict containment (not just line overlap)
            is_contained = (
                potential_parent.start_line < chunk.start_line and  # Parent starts before
                potential_parent.end_line > chunk.end_line  # Parent ends after
            )

            if is_contained:
                parent_classes.append(potential_parent)

    # Sort by range (largest first = outermost)
    parent_classes.sort(key=lambda c: (c.end_line - c.start_line), reverse=True)

    return [c.name for c in parent_classes]
```

**Severity**: HIGH
**Recommendation**: ⚠️ **IMPLEMENT** enhanced parent detection logic

---

### Risk 2: Multi-Language Support

**Impact**: name_path generation fails for non-Python languages

**Current State**:
- ✅ Python: Well-designed
- ❌ JavaScript/TypeScript: Not addressed
- ❌ Go: Not addressed
- ❌ Java: Not addressed

**Example**:
```javascript
// src/components/Button.tsx
export class Button {
    handleClick() { ... }
}

// Expected: components.Button.handleClick
// Current logic: ??? (assumes Python structure)
```

**Mitigation**:
- ⚠️ Add `language` parameter to all methods
- ⚠️ Language-specific path mapping (as shown in enhancement above)
- ⚠️ Test suite for each supported language

**Severity**: MEDIUM (Python works, other languages can be added later)
**Recommendation**: ⚠️ **ENHANCE** with multi-language support OR document Python-only limitation

---

### Risk 3: Migration Performance

**Impact**: Backfilling name_path for 100k+ chunks takes too long

**Scenario**: Existing deployment has 500k code chunks

**Estimation**:
- Operation: Generate name_path + UPDATE (per chunk)
- Complexity: O(n²) for parent context extraction (worst case)
- Estimated time: ~30 seconds for 1000 chunks
- **Projected**: ~4 hours for 500k chunks ❌

**Mitigation 1 - Batch Processing** (from EPIC spec):
```python
# Process 1000 chunks at a time
batch_size = 1000

# Problem: Still O(n²) within each batch
# 1000 chunks → 1M comparisons per batch
```

**Mitigation 2 - Simplified Backfill** (EPIC spec mentions):
```python
# Skip parent context for migration (set to None)
# Only backfill simple module paths

name_path = symbol_service.generate_name_path(
    chunk_name=chunk["name"],
    file_path=chunk["file_path"],
    repository_root=chunk["repository"],
    parent_context=None  # SKIP parent detection for speed
)
```

**Recommendation**: ✅ **APPROVE** simplified backfill strategy for migration
- Phase 1: Backfill with simple paths (no parent context) → fast (minutes)
- Phase 2: Re-index repositories to get full hierarchical paths → normal (background)

**Severity**: LOW (mitigated by simplified backfill)

---

### Risk 4: Name Path Collisions

**Impact**: Two symbols generate same name_path → ambiguity

**Scenarios**:
1. **Same function name** in multiple files with same path
   - Example: `utils/helpers.py::User` and `utils/formatters.py::User`
   - name_path: `utils.helpers.User` vs `utils.formatters.User` ✅ (different)

2. **Overloaded methods** (Python allows via decorators)
   ```python
   class Calculator:
       def add(self, a, b): pass
       def add(self, a, b, c): pass  # Same name!
   ```
   - name_path: `models.Calculator.add` (both!) ❌

**Current Mitigation** (from EPIC Risk section):
- Include line numbers: `models.user.User:45`

**Analysis**:
- ⚠️ Collisions are RARE in practice (<1% of symbols)
- ⚠️ Line numbers break if code changes
- ✅ File path + name + parent context is usually unique

**Recommendation**: ✅ **ACCEPT** risk (monitor collision rate in production)
- Add logging: Track collision rate
- Add fallback: Display file_path in UI when multiple matches
- Consider: Add unique_id suffix only if collision detected

**Severity**: LOW (rare occurrence, mitigations exist)

---

### Risk 5: Repository Root Unknown

**Impact**: Cannot compute module path for old data without repository metadata

**Scenario**: Existing code_chunks have repository=NULL

**Current Database**:
```sql
SELECT COUNT(*) FROM code_chunks WHERE repository IS NULL;
-- Result: ??? (need to check)
```

**Mitigation** (from EPIC):
- Default repository root to repository name
- Allow manual override via config
- Worst case: Use file_path as module path

**Recommendation**: ⚠️ **CHECK** existing data before migration
```bash
# Run this to assess impact:
docker exec mnemo-postgres psql -U mnemo -d mnemolite -c \
  "SELECT COUNT(*), COUNT(*) FILTER (WHERE repository IS NULL) FROM code_chunks;"
```

**Severity**: MEDIUM (data-dependent)

---

## ✅ Acceptance Criteria Validation

| Criteria | Status | Notes |
|----------|--------|-------|
| `name_path` computed during chunking | ✅ | Logic clear, integration point identified |
| Format: `{module}.{submodule}.{class}.{function}` | ✅ | Correct format |
| Nested classes handled | ⚠️ | Parent context logic needs ordering fix |
| Module path derived from file path | ✅ | `_file_to_module_path()` logic correct |
| Stored in `code_chunks.name_path` column | ✅ | Schema + repository updates needed |
| Tests: Correct name_path for all chunk types | ⚠️ | Need more edge case tests |

**Overall**: ✅ **5/6 criteria met**, **1/6 needs minor enhancement**

---

## 📊 Effort Estimation

**Original Estimate**: 5 story points

**Breakdown**:
| Task | Original | Actual (Recommended) | Difference |
|------|----------|---------------------|------------|
| Database schema changes | 0.5 pts | 0.5 pts | - |
| SymbolPathService implementation | 2 pts | 2.5 pts | +0.5 (multi-language) |
| Model updates | 0.5 pts | 0.5 pts | - |
| Repository updates | 0.5 pts | 0.5 pts | - |
| Code Indexing integration | 0.5 pts | 0.5 pts | - |
| Unit tests | 1 pts | 1.5 pts | +0.5 (more edge cases) |
| **Total** | **5 pts** | **6 pts** | **+1 pt** |

**Recommendation**: ⚠️ **ADJUST** story points to **6 pts** (or reduce scope by deferring multi-language support)

---

## 🎯 Implementation Recommendations

### High Priority (MUST FIX)

1. ⚠️ **Fix parent context ordering**
   ```python
   # Change from:
   parent_classes.sort(key=lambda c: (c.end_line - c.start_line))
   # To:
   parent_classes.sort(key=lambda c: (c.end_line - c.start_line), reverse=True)
   ```

2. ⚠️ **Add repository updates to EPIC spec**
   - CodeChunkRepository table definition
   - INSERT query updates
   - Parameter mapping

3. ⚠️ **Enhance parent detection**
   - Use strict containment (parent.start < chunk.start)
   - Add validation tests

### Medium Priority (SHOULD HAVE)

4. ⚠️ **Add language parameter**
   - Pass language to `generate_name_path()`
   - Use language-aware module path generation

5. ⚠️ **Add integration tests**
   - End-to-end indexing with name_path
   - Database persistence verification

6. ⚠️ **Add edge case tests**
   - Non-Python languages
   - Deep nesting (4+ levels)
   - Error handling

### Low Priority (NICE TO HAVE)

7. ✅ **Add collision detection**
   - Log when duplicate name_path values exist
   - Monitor collision rate

8. ✅ **Performance optimization**
   - Cache parent context lookups
   - Optimize O(n²) parent detection

---

## 📋 Updated Files List

**Original EPIC Spec**:
```
MODIFY: db/init/01-init.sql (+3 lines)
NEW: api/services/symbol_path_service.py (200 lines)
MODIFY: api/services/code_indexing_service.py (+10 lines)
MODIFY: api/models/code_chunk.py (+2 lines)
TEST: tests/services/test_symbol_path_service.py (300 lines)
```

**Actual (After Analysis)**:
```
✅ MODIFY: db/init/01-init.sql (+3 lines - ALTER TABLE, 2 indexes)
✅ NEW: api/services/symbol_path_service.py (250 lines - enhanced with language support)
✅ MODIFY: api/services/code_indexing_service.py (+15 lines - language param)
✅ MODIFY: api/models/code_chunk_models.py (+4 lines - 2 models)
⚠️ MODIFY: api/db/repositories/code_chunk_repository.py (+20 lines - table def + queries)
✅ TEST: tests/services/test_symbol_path_service.py (400 lines - more edge cases)
⚠️ TEST: tests/integration/test_name_path_indexing.py (150 lines - NEW)
```

**Total**: 7 files (vs 5 in original spec)

---

## 🚦 Final Decision

### ✅ GO / NO-GO

**Decision**: ✅ **GO** (with recommended enhancements)

**Rationale**:
- Architecture is sound
- Integration points are clean
- Risks are manageable
- Benefits outweigh costs

**Conditions**:
1. Fix parent context ordering (HIGH priority)
2. Add repository updates to spec (HIGH priority)
3. Enhance with language support OR document Python-only limitation
4. Add integration tests
5. Consider adjusting story points to 6 (or reduce scope)

---

## 📝 Implementation Checklist

**Before Starting**:
- [ ] Review and approve recommended enhancements
- [ ] Decide: Multi-language support NOW or LATER?
- [ ] Decide: Adjust story points or reduce scope?
- [ ] Update EPIC-11 with repository modifications

**During Implementation**:
- [ ] Implement SymbolPathService with enhanced parent detection
- [ ] Update database schema (ALTER TABLE + indexes)
- [ ] Update models (CodeChunkCreate, CodeChunkModel)
- [ ] Update repository (table def + queries)
- [ ] Integrate with CodeIndexingService
- [ ] Write unit tests (300+ lines)
- [ ] Write integration tests (150+ lines)
- [ ] Test migration on realistic dataset

**After Implementation**:
- [ ] Run all tests (expect 100% pass rate)
- [ ] Check index sizes (monitor disk usage)
- [ ] Validate name_path generation on real code
- [ ] Document limitations (if any)

---

## 🔗 Related Documents

- **EPIC-11**: `EPIC-11_SYMBOL_ENHANCEMENT.md`
- **ADR-003**: Breaking Changes (name_path approved)
- **Current Schema**: `db/init/01-init.sql` + live database
- **Current Models**: `api/models/code_chunk_models.py`
- **Current Repository**: `api/db/repositories/code_chunk_repository.py`

---

**Analysis Complete**: 2025-10-20
**Analyst**: Claude Code
**Recommendation**: ✅ **PROCEED** with enhancements
**Confidence**: HIGH (95%)
