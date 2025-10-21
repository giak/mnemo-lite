# EPIC-11: Symbol Enhancement (name_path)

**Status**: ✅ **COMPLETE** (All Stories 11.1-11.4 COMPLETE ✅ - 13/13 pts)
**Priority**: P1 (High - Improves Search & Call Resolution)
**Epic Points**: 13 pts (13 pts completed, 0 pts remaining)
**Timeline**: Week 3 (Phase 2)
**Depends On**: EPIC-10 (Cache layer must be ready)
**Related**: ADR-003 (Breaking Changes - name_path approved)
**Last Updated**: 2025-10-21 (EPIC-11 COMPLETE - All 1,302 chunks migrated with name_path)

---

## 🎯 Epic Goal

Implement hierarchical `name_path` field (e.g., `auth.routes.login`) to enable:
- **Qualified symbol search**: Search for `auth.routes.login` vs just `login`
- **Better call resolution**: Disambiguate `User` class in `models.py` vs `utils.py`
- **Improved graph accuracy**: Resolve cross-file calls with qualified names
- **Enhanced UX**: Display fully qualified names in UI for clarity

This epic transforms MnemoLite from flat symbol names to hierarchical navigation.

---

## 📊 Current State (v2.0.0)

**Pain Points**:
```python
# code_chunks table (v2.0)
{
  "name": "login",  # AMBIGUOUS! Which login?
  "file_path": "api/routes/auth.py",
  "chunk_type": "function"
}

# Call resolution problem:
# File A: from utils import User
# File B: from models import User
# Which User is called? → Current system guesses (70% accuracy)
```

**Search Problems**:
```python
# User searches: "User"
# Results: 47 chunks ALL named "User"
# How to distinguish User class in models vs utils vs tests?
# → Poor UX, requires manual filtering
```

**Graph Problems**:
```python
# auth.routes.login() calls validators.check_password()
# Current: "login" → "check_password" (loses context)
# Desired: "auth.routes.login" → "auth.validators.check_password"
```

---

## 🚀 Target State (v3.0.0)

**Schema Change**:
```sql
ALTER TABLE code_chunks ADD COLUMN name_path TEXT;

-- Examples:
INSERT INTO code_chunks (name, name_path, file_path) VALUES
  ('login', 'auth.routes.login', 'api/routes/auth.py'),
  ('User', 'models.user.User', 'api/models/user.py'),
  ('User', 'utils.helpers.User', 'api/utils/helpers.py');  -- Different User!
```

**Search Enhancement**:
```python
# User searches: "User"
# Results show qualified paths:
#   1. models.user.User (api/models/user.py) ← Primary model
#   2. utils.helpers.User (api/utils/helpers.py) ← Helper class
#   3. tests.fixtures.User (tests/conftest.py) ← Test fixture

# User can search qualified: "models.User" → exact match
```

**Call Resolution**:
```python
# Now resolves with context:
# auth.routes.login() calls auth.validators.check_password()
# Graph edge: auth.routes.login → auth.validators.check_password
# Accuracy: 70% → 95%+ (with name_path + LSP)
```

---

## 📝 Stories Breakdown

### **Story 11.1: name_path Generation Logic** (5 pts) ✅ COMPLETE

**Status**: ✅ **COMPLETE** (2025-10-21)
**Completion Report**: [EPIC-11_STORY_11.1_COMPLETION_REPORT.md](EPIC-11_STORY_11.1_COMPLETION_REPORT.md)
**User Story**: As a code indexer, I want to generate hierarchical name_path from file structure so that symbols have unique qualified names.

**Acceptance Criteria** (6/6 COMPLETE):
- [x] `name_path` computed during chunking ✅ (integrated into CodeIndexingService)
- [x] Format: `{module}.{submodule}.{class}.{function}` ✅
- [x] Nested classes handled: `api.models.user.User.validate` ✅ (with reverse=True fix)
- [x] Module path derived from file path (relative to repository root) ✅
- [x] Stored in `code_chunks.name_path` column ✅ (migration v3→v4 applied)
- [x] Integration tests: 5 tests passing (100% success) ✅

**Foundation Completed** (not counted toward 5 pts):
- ✅ SymbolPathService implemented (227 lines, 20 tests)
- ✅ Database migration v3→v4 (name_path + 2 indexes)
- ✅ Repository updates (INSERT/UPDATE queries)
- ✅ Models updated (CodeChunk, CodeChunkUpdate)
- ✅ Fix #1: Parent context ordering (reverse=True)
- ✅ Fix #2: Repository integration (missing from spec)
- ✅ Fix #3: Strict containment checks (< and >)

**Implementation Details**:

```sql
-- MODIFY: db/init/01-init.sql

ALTER TABLE code_chunks ADD COLUMN name_path TEXT;

CREATE INDEX idx_code_chunks_name_path ON code_chunks(name_path);
CREATE INDEX idx_code_chunks_name_path_trgm ON code_chunks USING gin(name_path gin_trgm_ops);
```

```python
# NEW: api/services/symbol_path_service.py

from pathlib import Path
from typing import Optional

class SymbolPathService:
    """Generate hierarchical name_path for code symbols."""

    def generate_name_path(
        self,
        chunk_name: str,
        file_path: str,
        repository_root: str,
        parent_context: Optional[list[str]] = None
    ) -> str:
        """
        Generate qualified name_path.

        Examples:
        - Function: api/routes/auth.py::login → auth.routes.login
        - Method: api/models/user.py::User.validate → models.user.User.validate
        - Nested: api/services/cache.py::RedisCache.connect → services.cache.RedisCache.connect
        """

        # 1. Extract module path from file path
        module_path = self._file_to_module_path(file_path, repository_root)

        # 2. Combine with parent context (for nested classes/methods)
        if parent_context:
            # Parent context: ['User', 'Profile'] for nested class
            full_path = f"{module_path}.{'.'.join(parent_context)}.{chunk_name}"
        else:
            full_path = f"{module_path}.{chunk_name}"

        return full_path

    def _file_to_module_path(self, file_path: str, repository_root: str) -> str:
        """
        Convert file path to Python module path.

        Examples:
        - api/routes/auth.py → routes.auth
        - api/models/user.py → models.user
        - api/services/caches/redis_cache.py → services.caches.redis_cache
        """

        # Make relative to repository root
        rel_path = Path(file_path).relative_to(repository_root)

        # Remove api/ prefix if present
        parts = list(rel_path.parts)
        if parts and parts[0] == "api":
            parts = parts[1:]

        # Remove .py extension
        if parts and parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]

        # Remove __init__ (represents package itself)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]

        # Join with dots
        module_path = ".".join(parts)

        return module_path

    def extract_parent_context(self, chunk, all_chunks) -> list[str]:
        """
        Extract parent class names for methods.

        Example:
        - Method 'validate' in class 'User' → parent_context = ['User']
        - Method 'save' in nested class 'User.Profile' → parent_context = ['User', 'Profile']
        """

        if chunk.chunk_type not in ["method", "function"]:
            return []

        # Find parent class (chunk with smallest line range containing this chunk)
        parent_classes = []

        for potential_parent in all_chunks:
            if potential_parent.chunk_type == "class":
                # Check if method is inside this class
                if (potential_parent.start_line <= chunk.start_line and
                    potential_parent.end_line >= chunk.end_line):
                    parent_classes.append(potential_parent)

        # Sort by line range (smallest first = most immediate parent)
        parent_classes.sort(key=lambda c: (c.end_line - c.start_line))

        # Return names of parent classes (innermost to outermost)
        return [c.name for c in parent_classes]
```

```python
# MODIFY: api/services/code_indexing_service.py

class CodeIndexingService:
    def __init__(
        self,
        # ... existing
        symbol_path_service: SymbolPathService = None  # NEW
    ):
        self.symbol_path_service = symbol_path_service or SymbolPathService()

    async def index_file(
        self,
        file_path: str,
        source_code: str,
        language: str,
        repository: str,
        commit_hash: Optional[str] = None
    ) -> List[CodeChunkModel]:
        """Index file with name_path generation."""

        # ... existing cache lookup, chunking, metadata extraction

        # NEW: Generate name_path for each chunk
        for chunk in chunks:
            parent_context = self.symbol_path_service.extract_parent_context(chunk, chunks)
            chunk.name_path = self.symbol_path_service.generate_name_path(
                chunk_name=chunk.name,
                file_path=file_path,
                repository_root=repository,  # Assumes repository path passed
                parent_context=parent_context
            )

        # ... continue with embeddings, storage
```

```python
# MODIFY: api/models/code_chunk.py

class CodeChunkCreate(BaseModel):
    # ... existing fields
    name_path: Optional[str] = None  # NEW

class CodeChunkModel(BaseModel):
    # ... existing fields
    name_path: Optional[str] = None  # NEW
```

**Files to Create/Modify**:
```
MODIFY: db/init/01-init.sql (+3 lines - ALTER TABLE, indexes)
NEW: api/services/symbol_path_service.py (200 lines)
MODIFY: api/services/code_indexing_service.py (+10 lines)
MODIFY: api/models/code_chunk.py (+2 lines)
TEST: tests/services/test_symbol_path_service.py (300 lines)
```

**Testing Strategy**:
```python
# tests/services/test_symbol_path_service.py

def test_function_name_path():
    """Top-level function."""
    service = SymbolPathService()

    name_path = service.generate_name_path(
        chunk_name="login",
        file_path="api/routes/auth.py",
        repository_root="/app",
        parent_context=None
    )

    assert name_path == "routes.auth.login"

def test_method_name_path():
    """Class method."""
    service = SymbolPathService()

    # Simulate User.validate method
    name_path = service.generate_name_path(
        chunk_name="validate",
        file_path="api/models/user.py",
        repository_root="/app",
        parent_context=["User"]  # Parent class
    )

    assert name_path == "models.user.User.validate"

def test_nested_class_method():
    """Nested class method."""
    service = SymbolPathService()

    # Simulate User.Profile.save method
    name_path = service.generate_name_path(
        chunk_name="save",
        file_path="api/models/user.py",
        repository_root="/app",
        parent_context=["User", "Profile"]  # Nested
    )

    assert name_path == "models.user.User.Profile.save"

def test_package_init():
    """Package __init__.py."""
    service = SymbolPathService()

    name_path = service.generate_name_path(
        chunk_name="setup",
        file_path="api/models/__init__.py",
        repository_root="/app",
        parent_context=None
    )

    # __init__ removed from path
    assert name_path == "models.setup"

def test_deep_nested_file():
    """Deep directory structure."""
    service = SymbolPathService()

    name_path = service.generate_name_path(
        chunk_name="flush_pattern",
        file_path="api/services/caches/redis_cache.py",
        repository_root="/app",
        parent_context=["RedisCache"]
    )

    assert name_path == "services.caches.redis_cache.RedisCache.flush_pattern"
```

**Success Metrics**:
- 100% chunks have non-null name_path
- Name paths unique for 95%+ of chunks
- Correct parent context extraction

---

### **Story 11.2: Search by Qualified Name** (3 pts) ✅ COMPLETE

**Status**: ✅ **COMPLETE** (2025-10-21)
**Completion Report**: [EPIC-11_STORY_11.2_COMPLETION_REPORT.md](EPIC-11_STORY_11.2_COMPLETION_REPORT.md)
**User Story**: As a developer, I want to search by qualified names (e.g., "models.User") so that I can find the exact symbol I need.

**Acceptance Criteria** (5/5 COMPLETE):
- [x] Search supports qualified patterns: "models.User", "auth.routes.*" ✅
- [x] Search results display name_path prominently ✅ (in LexicalSearchResult, HybridSearchResultModel)
- [x] Fuzzy matching: "models.User" matches "api.models.user.User" ✅ (pg_trgm trigram similarity)
- [x] Fallback to simple name if no name_path match ✅ (tested in test_fallback_simple_name_if_no_qualified_match)
- [x] Tests: Qualified search correctness ✅ (8 integration tests, 100% passing)

**Implementation Details**:

```python
# MODIFY: api/services/lexical_search_service.py

class LexicalSearchService:
    async def search(
        self,
        query: str,
        repository: Optional[str] = None,
        limit: int = 10
    ) -> List[CodeChunkModel]:
        """Search with name_path support."""

        # Detect if query looks qualified (contains dots)
        is_qualified = "." in query

        if is_qualified:
            # Search name_path field
            results = await self._search_name_path(query, repository, limit)

            # If no results, fallback to simple name search
            if not results:
                results = await self._search_simple_name(query, repository, limit)
        else:
            # Simple name search (existing behavior)
            results = await self._search_simple_name(query, repository, limit)

        return results

    async def _search_name_path(
        self,
        query: str,
        repository: Optional[str],
        limit: int
    ) -> List[CodeChunkModel]:
        """Search by qualified name_path."""

        # Use PostgreSQL similarity (pg_trgm)
        sql = """
        SELECT *
        FROM code_chunks
        WHERE
            name_path ILIKE :pattern
            AND (:repo IS NULL OR repository = :repo)
        ORDER BY
            CASE
                WHEN name_path = :exact THEN 0
                WHEN name_path ILIKE :exact || '%' THEN 1
                WHEN name_path ILIKE '%' || :exact THEN 2
                ELSE 3
            END,
            similarity(name_path, :query) DESC
        LIMIT :limit
        """

        results = await self.db.execute(
            sql,
            {
                "pattern": f"%{query}%",
                "exact": query,
                "query": query,
                "repo": repository,
                "limit": limit
            }
        )

        return [CodeChunkModel(**row) for row in results]

    async def _search_simple_name(
        self,
        query: str,
        repository: Optional[str],
        limit: int
    ) -> List[CodeChunkModel]:
        """Existing simple name search."""
        # ... existing implementation
```

```python
# MODIFY: api/routes/code_search_routes.py

@router.get("/search/hybrid")
async def search_code(
    query: str = Query(..., description="Search query (supports qualified names: models.User)"),
    # ... other parameters
):
    """
    Hybrid code search.

    Supports qualified names:
    - "login" → all chunks named 'login'
    - "auth.routes.login" → specific function in auth.routes
    - "models.User.validate" → specific method
    """
    results = await search_service.search(query, repository, limit)
    return results
```

**Files to Create/Modify**:
```
MODIFY: api/services/lexical_search_service.py (+40 lines)
MODIFY: api/routes/code_search_routes.py (update docs)
TEST: tests/services/test_lexical_search_qualified.py (150 lines)
```

**Testing Strategy**:
```python
# tests/services/test_lexical_search_qualified.py

@pytest.mark.anyio
async def test_exact_qualified_search():
    """Exact qualified name."""
    results = await search_service.search("models.user.User")

    assert len(results) == 1
    assert results[0].name_path == "models.user.User"

@pytest.mark.anyio
async def test_partial_qualified_search():
    """Partial match."""
    results = await search_service.search("models.User")

    # Should match models.user.User, models.admin.User, etc.
    assert len(results) > 0
    assert all("models" in r.name_path for r in results)
    assert all("User" in r.name_path for r in results)

@pytest.mark.anyio
async def test_wildcard_qualified_search():
    """Wildcard pattern."""
    results = await search_service.search("auth.routes.*")

    # All functions/classes in auth.routes module
    assert all(r.name_path.startswith("auth.routes") for r in results)

@pytest.mark.anyio
async def test_fallback_simple_name():
    """Fallback if qualified search fails."""
    results = await search_service.search("nonexistent.module.func")

    # Should fallback to searching simple name "func"
    assert any(r.name == "func" for r in results)
```

**Success Metrics**:
- Qualified search works for 100% of indexed symbols
- Fuzzy matching >90% accuracy
- Search latency <50ms (with L2 cache)

---

### **Story 11.3: UI Display of Qualified Names** (2 pts) ✅ COMPLETE

**Status**: ✅ **COMPLETE** (2025-10-21)
**Completion Report**: [EPIC-11_STORY_11.3_COMPLETION_REPORT.md](EPIC-11_STORY_11.3_COMPLETION_REPORT.md)
**User Story**: As a user, I want to see fully qualified names in search results so that I can distinguish between similar symbols.

**Acceptance Criteria** (4/4 COMPLETE):
- [x] Search results show `name_path` prominently ✅ (3-level fallback: name_path → name → "Unnamed")
- [x] Hover tooltip shows full context ✅ (DOM reuse pattern, 7.5x faster)
- [x] Graph nodes display qualified names ✅ (NULL-safe JOIN, functional index)
- [x] Tests: UI rendering correctness ✅ (10/10 integration tests passing)

**Implementation Details**:

```html
<!-- MODIFY: templates/partials/code_results.html -->

<div class="code-result" data-chunk-id="{{ chunk.id }}">
    <div class="result-header">
        <!-- Show qualified name prominently -->
        <span class="name-path">{{ chunk.name_path }}</span>

        <!-- Simple name as subtitle (if different) -->
        {% if chunk.name_path != chunk.name %}
        <span class="simple-name">({{ chunk.name }})</span>
        {% endif %}
    </div>

    <div class="result-meta">
        <span class="file-path">{{ chunk.file_path }}</span>
        <span class="chunk-type">{{ chunk.chunk_type }}</span>
    </div>

    <div class="result-source">
        <pre><code>{{ chunk.source_code[:200] }}...</code></pre>
    </div>
</div>
```

```css
/* MODIFY: static/css/scada.css */

.name-path {
    font-family: 'SF Mono', monospace;
    font-size: 1.1em;
    color: var(--accent-blue);
    font-weight: 600;
}

.simple-name {
    font-size: 0.9em;
    color: var(--text-secondary);
    margin-left: 8px;
}
```

```javascript
// MODIFY: static/js/components/code_graph.js

function renderGraphNode(node) {
    return {
        data: {
            id: node.id,
            label: node.name_path || node.name,  // Use name_path if available
            type: node.node_type
        },
        classes: node.node_type
    };
}
```

**Files to Create/Modify**:
```
MODIFY: templates/partials/code_results.html (+10 lines)
MODIFY: static/css/scada.css (+15 lines)
MODIFY: static/js/components/code_graph.js (+5 lines)
```

**Success Metrics**:
- UI displays name_path for 100% of chunks
- Graph nodes use qualified names
- User feedback positive (better disambiguation)

---

### **Story 11.4: Migration Script for Existing Data** (3 pts) ✅ COMPLETE

**Status**: ✅ **COMPLETE** (2025-10-21)
**Completion Report**: [EPIC-11_STORY_11.4_COMPLETION_REPORT.md](EPIC-11_STORY_11.4_COMPLETION_REPORT.md)
**Analysis Document**: [EPIC-11_STORY_11.4_ANALYSIS.md](EPIC-11_STORY_11.4_ANALYSIS.md)
**User Story**: As a database admin, I want to backfill name_path for existing chunks so that v2.0 data works in v3.0.

**Acceptance Criteria** (4/4 COMPLETE):
- [x] Migration script computes name_path for all existing chunks ✅ (1,302/1,302 chunks)
- [x] Script handles missing repository root gracefully ✅ (fallback to `/unknown`)
- [x] Script validates 100% chunks have name_path after migration ✅ (100.00% coverage)
- [x] Tests: Migration correctness ✅ (8 integration tests created)

**Implementation Details**:

```python
# NEW: scripts/backfill_name_path.py

import asyncio
import asyncpg
import os
from api.services.symbol_path_service import SymbolPathService

async def backfill_name_path():
    """Backfill name_path for existing code_chunks."""

    database_url = os.getenv("DATABASE_URL")
    conn = await asyncpg.connect(database_url)

    symbol_service = SymbolPathService()

    try:
        print("🔄 Backfilling name_path for existing chunks...")

        # 1. Count chunks
        total = await conn.fetchval("SELECT COUNT(*) FROM code_chunks WHERE name_path IS NULL")
        print(f"📊 Chunks to update: {total}")

        if total == 0:
            print("✅ All chunks already have name_path!")
            return

        # 2. Fetch chunks in batches
        batch_size = 1000
        updated = 0

        while True:
            # Fetch batch
            chunks = await conn.fetch("""
                SELECT id, name, file_path, repository, chunk_type, start_line, end_line
                FROM code_chunks
                WHERE name_path IS NULL
                LIMIT $1
            """, batch_size)

            if not chunks:
                break

            # Update batch
            for chunk in chunks:
                # Generate name_path
                name_path = symbol_service.generate_name_path(
                    chunk_name=chunk["name"],
                    file_path=chunk["file_path"],
                    repository_root=chunk["repository"],
                    parent_context=None  # Simple version (no parent context for backfill)
                )

                # Update
                await conn.execute("""
                    UPDATE code_chunks
                    SET name_path = $1
                    WHERE id = $2
                """, name_path, chunk["id"])

                updated += 1

                if updated % 100 == 0:
                    print(f"⚙️  Updated {updated}/{total} chunks...")

        # 3. Validate
        remaining = await conn.fetchval("SELECT COUNT(*) FROM code_chunks WHERE name_path IS NULL")

        if remaining > 0:
            raise Exception(f"❌ Migration incomplete: {remaining} chunks still missing name_path")

        print(f"✅ Backfill complete! Updated {updated} chunks.")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(backfill_name_path())
```

**Files to Create/Modify**:
```
NEW: scripts/backfill_name_path.py (100 lines)
MODIFY: db/migrations/v2_to_v3.sql (add backfill step)
TEST: tests/migrations/test_name_path_backfill.py (100 lines)
```

**Success Metrics**:
- 100% existing chunks have name_path after migration
- Migration completes in <5 minutes for 100k chunks
- Idempotent (can run multiple times)

---

## 📈 Epic Success Metrics

### Functional Targets

| Metric | v2.0 (Current) | v3.0 (Target) | Improvement |
|--------|----------------|---------------|-------------|
| Symbol disambiguation | Poor (name only) | Excellent (name_path) | Qualitative |
| Search precision (qualified) | N/A | >95% | New capability |
| Call resolution accuracy | 70% | 85%+ | 15%+ improvement |
| Unique symbol paths | N/A | >95% | New capability |

### Quality Metrics

- **100% chunks** have non-null name_path
- **>95% unique** name_path values (minimal collisions)
- **Backward compatible**: Simple name search still works
- **Migration success**: 100% existing data migrated

---

## 🎯 Validation Plan

### Integration Testing

```python
# tests/integration/test_name_path_end_to_end.py

@pytest.mark.anyio
async def test_index_and_search_qualified():
    """End-to-end: Index → Search qualified name."""

    # Index file
    source = '''
class User:
    def validate(self):
        pass
'''
    await indexing_service.index_file(
        file_path="api/models/user.py",
        source_code=source,
        language="python",
        repository="/app"
    )

    # Search qualified
    results = await search_service.search("models.user.User.validate")

    assert len(results) == 1
    assert results[0].name_path == "models.user.User.validate"

@pytest.mark.anyio
async def test_disambiguation():
    """Multiple symbols with same name."""

    # Index two User classes
    await indexing_service.index_file("api/models/user.py", "class User: pass", "python", "/app")
    await indexing_service.index_file("api/utils/helpers.py", "class User: pass", "python", "/app")

    # Search unqualified
    results = await search_service.search("User")
    assert len(results) == 2

    # Search qualified (models)
    results = await search_service.search("models.User")
    assert len(results) == 1
    assert "models" in results[0].name_path

    # Search qualified (utils)
    results = await search_service.search("utils.User")
    assert len(results) == 1
    assert "utils" in results[0].name_path
```

---

## 🚧 Risks & Mitigations

### Risk 1: Name Path Collisions

**Impact**: Multiple chunks with same name_path → ambiguity

**Mitigation**:
- Include line numbers in extreme cases: `models.user.User:45`
- Monitoring: Track collision rate, alert if >5%
- User feedback: Display file_path as tiebreaker

### Risk 2: Migration Performance

**Impact**: Backfilling 100k+ chunks takes too long

**Mitigation**:
- Batch processing (1000 chunks/batch)
- Progress logging every 100 chunks
- Background job (optional): Run migration async

### Risk 3: Repository Root Unknown

**Impact**: Cannot compute module path for old data

**Mitigation**:
- Default repository root to repository name
- Allow manual override via config
- Worst case: Use file_path as module path

---

## 📚 References

- **ADR-003**: Breaking Changes (name_path field approved)
- **Serena Analysis**: Hierarchical naming pattern (inferred from ls.py context tracking)

---

## ✅ Definition of Done

**Epic is complete when**:
- [ ] All 4 stories completed and tested
- [ ] 100% chunks have name_path (including migrated v2.0 data)
- [ ] Qualified search works with >95% precision
- [ ] UI displays name_path prominently
- [ ] Migration tested on production-like dataset (100k+ chunks)
- [ ] Documentation updated
- [ ] Code review passed

**Ready for EPIC-12 (Robustness)**: ✅

---

**Created**: 2025-10-19
**Author**: Architecture Team
**Reviewed**: Pending
**Approved**: Pending
