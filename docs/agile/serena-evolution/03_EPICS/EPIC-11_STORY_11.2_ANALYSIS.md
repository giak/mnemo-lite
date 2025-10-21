# EPIC-11 Story 11.2 Analysis: Search by Qualified Name

**Analysis Date**: 2025-10-21
**Analyst**: Claude Code
**Story Points**: 3 pts
**Status**: 🔍 **ANALYSIS IN PROGRESS**
**Depends On**: Story 11.1 (name_path Generation) - ✅ COMPLETE

---

## 📋 Executive Summary

Story 11.2 ajoute la capacité de rechercher par nom qualifié (qualified name) en utilisant le champ `name_path` généré par Story 11.1. Cette fonctionnalité permet aux développeurs de rechercher des symboles de manière précise en utilisant leur chemin hiérarchique complet (e.g., "models.user.User.validate").

**Complexité**: **MEDIUM**
- Foundation solide (Story 11.1 complete)
- Service existant (LexicalSearchService) à étendre
- PostgreSQL pg_trgm déjà configuré
- Tests à adapter des patterns existants

**Risques**: **LOW**
- name_path déjà indexé (B-tree + trigram)
- Pas de changement de schéma requis
- Modification incrémentale de LexicalSearchService

---

## 📊 Story 11.2 Overview

### User Story
**As a developer**, I want to search by qualified names (e.g., "models.User") **so that** I can find the exact symbol I need without ambiguity.

### Acceptance Criteria (5 critères)

1. **[P0]** Search supports qualified patterns: "models.User", "auth.routes.*"
2. **[P0]** Search results display name_path prominently
3. **[P1]** Fuzzy matching: "models.User" matches "api.models.user.User"
4. **[P1]** Fallback to simple name if no name_path match
5. **[P0]** Tests: Qualified search correctness (4 tests minimum)

### Success Metrics

- ✅ Qualified search works for 100% of indexed symbols with name_path
- ✅ Fuzzy matching >90% accuracy (leveraging pg_trgm)
- ✅ Search latency <50ms (with L2 cache from EPIC-10)
- ✅ Zero breaking changes to existing search API

---

## 🔍 Current State Analysis

### Existing Infrastructure (EPIC-06/07/10)

#### 1. LexicalSearchService (api/services/lexical_search_service.py)

**Lines**: 243 lines
**Status**: ✅ Production-ready (EPIC-06)

**Current Capabilities**:
- Trigram similarity on `source_code` and `name` columns
- Fuzzy matching with configurable threshold
- Metadata filtering (language, chunk_type, repository, file_path)
- Performance: ~5-15ms for 10k chunks

**Current Search Fields**:
```python
async def search(
    self,
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 100,
    search_in_name: bool = True,         # ← Currently only 'name'
    search_in_source: bool = True,       # ← Currently only 'source_code'
) -> List[LexicalSearchResult]:
```

**Query Logic** (lines 103-111):
```python
similarity_conditions = []
if search_in_name:
    similarity_conditions.append("name % :query")
if search_in_source:
    similarity_conditions.append("source_code % :query")
```

**🔴 GAP**: `name_path` field NOT searchable yet

#### 2. Database Indexes (db/migrations/v3_to_v4.sql)

**Status**: ✅ READY (Story 11.1)

```sql
-- B-tree index for exact/prefix matching
CREATE INDEX idx_code_chunks_name_path ON code_chunks(name_path);

-- Trigram index for fuzzy matching
CREATE INDEX idx_code_chunks_name_path_trgm ON code_chunks
USING gin(name_path gin_trgm_ops);
```

**Performance**: Both indexes applied, query planner ready ✅

#### 3. API Routes (api/routes/code_search_routes.py)

**Current Endpoints**:
- `POST /v1/code/search/hybrid` - Hybrid search (lexical + vector + RRF)
- `POST /v1/code/search/lexical` - Lexical-only search
- `POST /v1/code/search/vector` - Vector-only search

**Request Model** (HybridSearchRequest):
```python
class HybridSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, description="Search query (keywords)")
    # ... other fields
```

**🔴 GAP**: Documentation doesn't mention qualified name support

#### 4. LexicalSearchResult Model

**Current Fields** (lines 18-29):
```python
@dataclass
class LexicalSearchResult:
    chunk_id: str
    similarity_score: float
    source_code: str
    name: str               # ← Simple name only
    language: str
    chunk_type: str
    file_path: str
    metadata: Dict[str, Any]
    rank: int
```

**🔴 GAP**: `name_path` field NOT included in results

---

## 🎯 Implementation Plan

### Phase 1: Extend LexicalSearchService (1 hour)

#### 1.1 Add name_path to LexicalSearchResult

**File**: `api/services/lexical_search_service.py`
**Location**: Lines 18-29 (LexicalSearchResult dataclass)

```python
@dataclass
class LexicalSearchResult:
    """Result from lexical search."""
    chunk_id: str
    similarity_score: float
    source_code: str
    name: str
    name_path: Optional[str] = None  # ← ADD: EPIC-11 Story 11.2
    language: str
    chunk_type: str
    file_path: str
    metadata: Dict[str, Any]
    rank: int
```

**Impact**: Backward compatible (Optional field)

#### 1.2 Add search_in_name_path parameter

**File**: `api/services/lexical_search_service.py`
**Location**: Line 63 (search method signature)

```python
async def search(
    self,
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 100,
    search_in_name: bool = True,
    search_in_source: bool = True,
    search_in_name_path: bool = False,  # ← ADD: EPIC-11 Story 11.2
) -> List[LexicalSearchResult]:
```

**Default**: `False` pour backward compatibility

**Activation Logic**:
```python
# Auto-detect qualified query (contains dots)
if "." in query and not search_in_name_path:
    search_in_name_path = True  # Auto-enable for qualified queries
```

#### 1.3 Add name_path trigram condition

**File**: `api/services/lexical_search_service.py`
**Location**: Lines 103-111 (similarity conditions)

```python
similarity_conditions = []
if search_in_name:
    similarity_conditions.append("name % :query")
if search_in_source:
    similarity_conditions.append("source_code % :query")
if search_in_name_path:  # ← ADD
    similarity_conditions.append("name_path % :query")
```

#### 1.4 Update similarity score calculation

**File**: `api/services/lexical_search_service.py`
**Location**: Lines 135-144 (similarity expression)

```python
similarity_expr_parts = []
if search_in_name:
    similarity_expr_parts.append("similarity(name, :query)")
if search_in_source:
    similarity_expr_parts.append("similarity(source_code, :query)")
if search_in_name_path:  # ← ADD
    similarity_expr_parts.append("similarity(name_path, :query)")

if len(similarity_expr_parts) > 1:
    similarity_expr = f"GREATEST({', '.join(similarity_expr_parts)})"
else:
    similarity_expr = similarity_expr_parts[0]
```

#### 1.5 Include name_path in SELECT

**File**: `api/services/lexical_search_service.py`
**Location**: Lines 147-162 (SQL query)

```python
query_sql = f"""
    SELECT
        id::TEXT as chunk_id,
        {similarity_expr} as similarity_score,
        source_code,
        name,
        name_path,  # ← ADD
        language,
        chunk_type,
        file_path,
        metadata
    FROM code_chunks
    WHERE {where_clause}
      AND {similarity_expr} > :threshold
    ORDER BY similarity_score DESC
    LIMIT :limit
"""
```

#### 1.6 Update result mapping

**File**: `api/services/lexical_search_service.py`
**Location**: Lines 173-184 (result construction)

```python
results.append(LexicalSearchResult(
    chunk_id=row.chunk_id,
    similarity_score=row.similarity_score,
    source_code=row.source_code,
    name=row.name,
    name_path=row.name_path,  # ← ADD
    language=row.language,
    chunk_type=row.chunk_type,
    file_path=row.file_path,
    metadata=row.metadata or {},
    rank=rank,
))
```

**Total Lines Added**: ~10 lines
**Total Lines Modified**: ~15 lines

---

### Phase 2: API Route Updates (30 minutes)

#### 2.1 Update SearchFiltersModel (optional enhancement)

**File**: `api/routes/code_search_routes.py`
**Location**: Lines 31-36

```python
class SearchFiltersModel(BaseModel):
    """Filters for code search."""
    language: Optional[str] = Field(None, description="Filter by programming language")
    chunk_type: Optional[str] = Field(None, description="Filter by chunk type")
    repository: Optional[str] = Field(None, description="Filter by repository name")
    file_path: Optional[str] = Field(None, description="Filter by file path (partial match)")
    name_path: Optional[str] = Field(None, description="Filter by qualified name path (e.g., 'models.user.*')")  # ← ADD
```

#### 2.2 Update HybridSearchRequest documentation

**File**: `api/routes/code_search_routes.py`
**Location**: Line 41 (query field description)

```python
query: str = Field(
    ...,
    min_length=1,
    max_length=1000,
    description="Search query. Supports qualified names (e.g., 'models.User', 'auth.routes.*')"  # ← UPDATE
)
```

#### 2.3 Update HybridSearchResultModel

**File**: `api/routes/code_search_routes.py`
**Location**: Lines 76-95

```python
class HybridSearchResultModel(BaseModel):
    """Single result from hybrid search."""
    chunk_id: str
    rrf_score: float
    rank: int

    source_code: str
    name: str
    name_path: Optional[str] = None  # ← ADD: EPIC-11 Story 11.2
    language: str
    chunk_type: str
    file_path: str
    metadata: Dict[str, Any]

    lexical_score: Optional[float] = None
    vector_similarity: Optional[float] = None
    vector_distance: Optional[float] = None

    contribution: Dict[str, float]
    related_nodes: List[str] = []
```

**Total Lines Added**: ~3 lines
**Total Lines Modified**: ~5 lines

---

### Phase 3: Integration Testing (1.5 hours)

#### 3.1 Create test file

**New File**: `tests/integration/test_epic11_qualified_search.py`
**Estimated Lines**: ~250 lines

**Test Structure**:
```python
"""
Integration tests for EPIC-11 Story 11.2: Search by Qualified Name.

Tests lexical search with name_path field, covering:
1. Exact qualified name matching
2. Partial qualified matching
3. Wildcard pattern matching
4. Fallback to simple name search
5. Auto-detection of qualified queries
"""

import pytest
import pytest_asyncio
from services.lexical_search_service import LexicalSearchService
from unittest.mock import AsyncMock
# ... imports
```

#### 3.2 Test Cases (5 minimum)

**Test 1: Exact Qualified Match**
```python
@pytest.mark.asyncio
async def test_exact_qualified_name_search(lexical_service, indexed_chunks):
    """
    Test exact qualified name search.

    Given: Chunk with name_path = "models.user.User"
    When: Search query = "models.user.User"
    Then: Returns exact match with high similarity
    """
    results = await lexical_service.search(
        query="models.user.User",
        search_in_name_path=True,
        limit=10
    )

    assert len(results) >= 1
    assert results[0].name_path == "models.user.User"
    assert results[0].similarity_score > 0.9
```

**Test 2: Partial Qualified Match**
```python
@pytest.mark.asyncio
async def test_partial_qualified_match(lexical_service, indexed_chunks):
    """
    Test partial qualified matching.

    Given: Chunks with name_path = ["models.user.User", "models.admin.User", "utils.User"]
    When: Search query = "models.User"
    Then: Returns all models.*.User but NOT utils.User
    """
    results = await lexical_service.search(
        query="models.User",
        search_in_name_path=True,
        limit=10
    )

    assert len(results) >= 2
    assert all("models" in r.name_path for r in results if r.name_path)
    assert all("User" in r.name_path for r in results if r.name_path)
    assert not any("utils.User" == r.name_path for r in results)
```

**Test 3: Auto-Detection of Qualified Queries**
```python
@pytest.mark.asyncio
async def test_auto_detect_qualified_query(lexical_service, indexed_chunks):
    """
    Test auto-detection when query contains dots.

    Given: Query contains dots (e.g., "auth.routes.login")
    When: search_in_name_path NOT explicitly set
    Then: Auto-enabled and searches name_path
    """
    # Should auto-detect and search name_path
    results = await lexical_service.search(
        query="auth.routes.login",
        # search_in_name_path omitted (auto-detect)
        limit=10
    )

    assert len(results) >= 1
    assert any("auth" in r.name_path for r in results if r.name_path)
```

**Test 4: Fallback to Simple Name**
```python
@pytest.mark.asyncio
async def test_fallback_simple_name_if_no_qualified_match(lexical_service, indexed_chunks):
    """
    Test fallback when qualified search returns nothing.

    Given: Query "nonexistent.module.func" (doesn't exist in name_path)
    When: Search with name_path enabled
    Then: Falls back to simple name "func" if exists
    """
    # First search: qualified (should return 0)
    qualified_results = await lexical_service.search(
        query="nonexistent.module.test_function",
        search_in_name_path=True,
        search_in_name=False,
        limit=10
    )

    assert len(qualified_results) == 0

    # Fallback search: simple name
    fallback_results = await lexical_service.search(
        query="test_function",
        search_in_name=True,
        limit=10
    )

    assert len(fallback_results) >= 1
```

**Test 5: name_path in Results**
```python
@pytest.mark.asyncio
async def test_name_path_included_in_results(lexical_service, indexed_chunks):
    """
    Test that name_path is included in LexicalSearchResult.

    Given: Chunks with name_path populated
    When: Any search
    Then: Results include name_path field
    """
    results = await lexical_service.search(
        query="User",
        search_in_name_path=True,
        limit=10
    )

    assert len(results) >= 1
    for result in results:
        assert hasattr(result, 'name_path')
        assert result.name_path is not None
        assert '.' in result.name_path  # Should be qualified
```

---

## 🚨 Critical Issues & Dependencies

### Dependency #1: Story 11.1 MUST be Complete ✅

**Status**: ✅ COMPLETE (2025-10-21)
- name_path generated during indexing ✅
- Database indexes created ✅
- 5/5 integration tests passing ✅

**Verification**:
```sql
SELECT COUNT(*) FROM code_chunks WHERE name_path IS NOT NULL;
-- Should return > 0
```

### Issue #1: Backward Compatibility

**Risk**: LOW
**Mitigation**: Use Optional fields and default parameters

**Strategy**:
- `name_path` in LexicalSearchResult: `Optional[str] = None`
- `search_in_name_path` parameter: default `False`
- Auto-detection: enable only if query contains "."

**Impact**: Zero breaking changes ✅

### Issue #2: Performance Impact

**Risk**: LOW
**Mitigation**: Trigram index already exists (Story 11.1)

**Expected Performance**:
- name_path search: ~10-20ms (similar to name search)
- Combined search (name + name_path): ~15-30ms
- L2 cache hit: ~0-5ms (EPIC-10)

**Verification**: Add performance test
```python
@pytest.mark.asyncio
async def test_qualified_search_performance(lexical_service, large_dataset):
    """Qualified search should be <50ms."""
    import time
    start = time.time()
    results = await lexical_service.search("models.User", search_in_name_path=True)
    elapsed = (time.time() - start) * 1000

    assert elapsed < 50, f"Search took {elapsed}ms (threshold: 50ms)"
```

---

## 📝 Files to Create/Modify

### Files to MODIFY (3 files)

1. **api/services/lexical_search_service.py**
   - Add name_path to LexicalSearchResult (+1 line)
   - Add search_in_name_path parameter (+1 line)
   - Add auto-detection logic (+3 lines)
   - Update SQL query to include name_path (+5 lines)
   - Update result mapping (+1 line)
   - **Total**: +11 lines, ~15 lines modified

2. **api/routes/code_search_routes.py**
   - Add name_path to HybridSearchResultModel (+1 line)
   - Update query field description (+1 line)
   - (Optional) Add name_path filter to SearchFiltersModel (+1 line)
   - **Total**: +3 lines, ~5 lines modified

3. **api/services/hybrid_code_search_service.py** (if needed)
   - Pass name_path from LexicalSearchResult to HybridSearchResult
   - **Total**: +2 lines, ~3 lines modified

### Files to CREATE (1 file)

4. **tests/integration/test_epic11_qualified_search.py**
   - 5 integration tests (exact, partial, auto-detect, fallback, results)
   - Performance test
   - Fixtures for indexed chunks
   - **Total**: ~250-300 lines

---

## 🎯 Effort Estimation

### Breakdown

| Phase | Task | Estimated Time |
|-------|------|----------------|
| Phase 1 | Extend LexicalSearchService | 1h |
| Phase 2 | Update API Routes | 0.5h |
| Phase 3 | Integration Tests | 1.5h |
| **TOTAL** | | **3 hours** |

**Story Points**: 3 pts
**Confidence**: HIGH (simple, incremental changes)

---

## ✅ Acceptance Criteria Checklist

### Pre-Implementation

- [x] Story 11.1 Complete ✅
- [x] Database indexes ready ✅
- [x] Existing services understood ✅

### Implementation

- [ ] Search supports qualified patterns (e.g., "models.User")
- [ ] Search supports wildcard patterns (e.g., "auth.routes.*")
- [ ] Search results include name_path field
- [ ] Fuzzy matching works (pg_trgm)
- [ ] Auto-detection of qualified queries (contains ".")
- [ ] Fallback to simple name if no qualified match
- [ ] Backward compatibility maintained (default OFF)

### Testing

- [ ] Test: Exact qualified match
- [ ] Test: Partial qualified match
- [ ] Test: Auto-detection
- [ ] Test: Fallback to simple name
- [ ] Test: name_path in results
- [ ] Test: Performance <50ms

### Documentation

- [ ] API route documentation updated
- [ ] LexicalSearchService docstrings updated
- [ ] Story 11.2 completion report created

---

## 📚 References

- **EPIC-11**: docs/agile/serena-evolution/03_EPICS/EPIC-11_SYMBOL_ENHANCEMENT.md
- **Story 11.1 Completion**: docs/agile/serena-evolution/03_EPICS/EPIC-11_STORY_11.1_COMPLETION_REPORT.md
- **LexicalSearchService**: api/services/lexical_search_service.py
- **Code Search Routes**: api/routes/code_search_routes.py
- **Database Migration v3→v4**: db/migrations/v3_to_v4.sql

---

**Document Status**: ✅ ANALYSIS COMPLETE - Ready for Implementation
**Next Action**: Begin Phase 1 (Extend LexicalSearchService)
