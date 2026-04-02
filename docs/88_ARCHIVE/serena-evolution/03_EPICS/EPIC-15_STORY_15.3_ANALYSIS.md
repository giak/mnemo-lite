# EPIC-15 Story 15.3: Multi-Language Graph Construction - Analysis

**Story ID**: EPIC-15.3
**Story Points**: 5 pts
**Status**: 📝 **READY FOR IMPLEMENTATION**
**Priority**: P0 (Critical - Enables multi-language dependency graphs)
**Dependencies**: Story 15.1 (TypeScriptParser), Story 15.2 (JavaScriptParser)
**Related**: EPIC-11 (Symbol Enhancement - name_path helps cross-language resolution)
**Created**: 2025-10-23
**Last Updated**: 2025-10-23

---

## 📝 User Story

**As a** graph builder
**I want to** construct dependency graphs across multiple languages
**So that** mixed Python+TypeScript repositories have complete dependency graphs showing cross-language calls

---

## 🎯 Acceptance Criteria

1. **Multi-Language Parameter** (1 pt)
   - [ ] `build_graph_for_repository()` accepts `languages: Optional[List[str]]` parameter
   - [ ] Default `None` triggers auto-detection
   - [ ] Backward compatible: single language still works

2. **Language Auto-Detection** (1.5 pts)
   - [ ] `_detect_languages_in_repository()` queries distinct languages from chunks
   - [ ] Returns list of unique language names (e.g., `["python", "typescript"]`)
   - [ ] Handles empty repositories (returns empty list)

3. **Multi-Language Query** (1 pt)
   - [ ] Query chunks for ALL languages in list (not just `language='python'`)
   - [ ] Aggregate chunks across languages before graph construction
   - [ ] Preserve existing graph construction logic (nodes, edges, traversal)

4. **API Integration** (1 pt)
   - [ ] `IndexRequest` model supports `graph_languages: Optional[List[str]]`
   - [ ] Code indexing service passes languages to graph service
   - [ ] API route documentation updated

5. **Integration Tests** (0.5 pts)
   - [ ] Test Python-only repository (backward compatibility)
   - [ ] Test TypeScript-only repository
   - [ ] Test mixed Python+TypeScript repository
   - [ ] All tests pass

---

## 🔍 Technical Analysis

### Current Architecture (Python-only)

**Problem Root Cause**:
```python
# api/services/graph_construction_service.py:76-79

async def build_graph_for_repository(
    self,
    repository: str,
    language: str = "python"  # ← HARDCODED DEFAULT
) -> GraphStats:
```

**Query Execution**:
```python
# Line 237
query_str = f"""
    SELECT * FROM code_chunks
    WHERE repository = '{repository}' AND language = '{language}'
"""
```

**Result** (for TypeScript repository `code_test`):
```
INFO: Building graph for repository 'code_test', language 'python'
INFO: Found 0 chunks for repository 'code_test'  ← NO CHUNKS (wrong language filter)
WARNING: No chunks found for repository 'code_test'. Returning empty stats.

Graph Stats:
  nodes: 0
  edges: 0
```

### Target Architecture (Multi-language)

**Solution**:
```python
async def build_graph_for_repository(
    self,
    repository: str,
    languages: Optional[List[str]] = None  # ← CHANGED: Accept multiple languages
) -> GraphStats:
    """
    Build complete graph for a repository (multi-language support).

    Args:
        repository: Repository name
        languages: List of languages to include (default: auto-detect all)

    Returns:
        GraphStats with construction metrics
    """
    start_time = time.time()

    # Auto-detect languages if not specified
    if languages is None:
        languages = await self._detect_languages_in_repository(repository)

    self.logger.info(f"Building graph for repository '{repository}', languages: {languages}")

    # Step 1: Get chunks for ALL specified languages
    all_chunks = []
    for language in languages:
        chunks = await self._get_chunks_for_repository(repository, language)
        all_chunks.extend(chunks)

    self.logger.info(f"Found {len(all_chunks)} chunks across {len(languages)} languages")

    if not all_chunks:
        self.logger.warning(f"No chunks found for repository '{repository}' (languages: {languages})")
        return GraphStats(
            nodes_created=0,
            edges_created=0,
            processing_time_ms=0,
            repository=repository
        )

    # Rest of graph construction logic remains unchanged
    # (Step 2: Create nodes, Step 3: Create edges, Step 4: Return stats)
```

**Auto-Detection Method**:
```python
async def _detect_languages_in_repository(
    self,
    repository: str
) -> List[str]:
    """
    Detect which languages exist in a repository.

    Returns:
        List of unique language names found in chunks
    """
    from sqlalchemy.sql import text

    query_str = """
        SELECT DISTINCT language
        FROM code_chunks
        WHERE repository = :repository
        ORDER BY language
    """

    async with self.engine.connect() as connection:
        result = await connection.execute(
            text(query_str),
            {"repository": repository}
        )
        rows = result.fetchall()

    languages = [row[0] for row in rows if row[0]]

    if not languages:
        self.logger.warning(f"No languages found for repository '{repository}'")
        return []

    self.logger.info(f"Detected languages for repository '{repository}': {languages}")
    return languages
```

---

## 💻 Implementation Details

### File Changes

**1. Graph Construction Service** (Primary Changes):
```python
# api/services/graph_construction_service.py

# CHANGE 1: Update method signature
async def build_graph_for_repository(
    self,
    repository: str,
    languages: Optional[List[str]] = None  # ← CHANGED
) -> GraphStats:

# CHANGE 2: Add language auto-detection
async def _detect_languages_in_repository(
    self,
    repository: str
) -> List[str]:
    # Implementation above

# CHANGE 3: Update chunk retrieval loop
all_chunks = []
for language in languages:
    chunks = await self._get_chunks_for_repository(repository, language)
    all_chunks.extend(chunks)
```

**2. API Models** (Add Optional Parameter):
```python
# api/routes/code_indexing_routes.py

class IndexRequest(BaseModel):
    repository: str
    files: List[FileInputModel]
    build_graph: bool = Field(True, description="Build dependency graph after indexing")
    graph_languages: Optional[List[str]] = Field(
        None,
        description="Languages to include in graph (default: auto-detect all languages)"
    )
```

**3. Code Indexing Service** (Pass Parameter):
```python
# api/services/code_indexing_service.py

# Build graph if requested
if request.build_graph:
    graph_stats = await self.graph_service.build_graph_for_repository(
        repository=request.repository,
        languages=request.graph_languages  # ← Pass languages (None for auto-detect)
    )
```

**4. API Route** (Update Documentation):
```python
# api/routes/code_indexing_routes.py

@router.post("/v1/code/index", response_model=IndexResponse)
async def index_code(
    request: IndexRequest,
    indexing_service: CodeIndexingService = Depends(get_code_indexing_service),
) -> IndexResponse:
    """
    Index code files and optionally build dependency graph.

    **Multi-Language Support**:
    - Auto-detects languages from indexed files
    - Builds unified graph across all languages
    - Use `graph_languages` to filter specific languages

    **Example** (Auto-detect):
    ```json
    {
      "repository": "my-app",
      "files": [...],
      "build_graph": true
    }
    ```

    **Example** (Explicit languages):
    ```json
    {
      "repository": "my-app",
      "files": [...],
      "build_graph": true,
      "graph_languages": ["python", "typescript"]
    }
    ```
    """
```

---

## 🧪 Testing Strategy

### Integration Tests (3+ test cases)

**Test 1: Python-Only Repository** (Backward Compatibility):
```python
@pytest.mark.asyncio
async def test_graph_python_only_repository():
    """Test graph construction for Python-only repository."""
    # Index 5 Python files
    # Build graph with languages=None (auto-detect)
    # Assert: Detects ["python"]
    # Assert: Graph created with nodes/edges
    # Assert: Backward compatible (existing behavior unchanged)
```

**Test 2: TypeScript-Only Repository**:
```python
@pytest.mark.asyncio
async def test_graph_typescript_only_repository():
    """Test graph construction for TypeScript-only repository."""
    # Index 5 TypeScript files
    # Build graph with languages=None (auto-detect)
    # Assert: Detects ["typescript"]
    # Assert: Graph created with nodes/edges
    # Assert: No Python chunks included
```

**Test 3: Mixed Python+TypeScript Repository**:
```python
@pytest.mark.asyncio
async def test_graph_mixed_language_repository():
    """Test graph construction for mixed Python+TypeScript repository."""
    # Index 3 Python files + 3 TypeScript files
    # Build graph with languages=None (auto-detect)
    # Assert: Detects ["python", "typescript"]
    # Assert: Graph includes chunks from BOTH languages
    # Assert: Nodes created for both Python and TypeScript symbols
    # Assert: Edges created (may include cross-language if imports detected)
```

**Test 4: Explicit Language Filter**:
```python
@pytest.mark.asyncio
async def test_graph_explicit_language_filter():
    """Test graph construction with explicit language filter."""
    # Index 3 Python files + 3 TypeScript files
    # Build graph with languages=["typescript"] (explicit filter)
    # Assert: Graph includes ONLY TypeScript chunks
    # Assert: Python chunks excluded
```

**Test 5: Empty Repository**:
```python
@pytest.mark.asyncio
async def test_graph_empty_repository():
    """Test graph construction for empty repository."""
    # Create empty repository (no chunks)
    # Build graph with languages=None
    # Assert: Detects [] (empty list)
    # Assert: Returns empty GraphStats (0 nodes, 0 edges)
    # Assert: No errors
```

**Test 6: No Matching Language**:
```python
@pytest.mark.asyncio
async def test_graph_no_matching_language():
    """Test graph construction when language filter matches nothing."""
    # Index 3 Python files
    # Build graph with languages=["typescript"] (no TypeScript chunks)
    # Assert: Returns empty GraphStats (0 nodes, 0 edges)
    # Assert: Warning logged
```

---

## 📊 Cross-Language Resolution

### Current Limitation (Story 15.3)

**In-Language Resolution**: Graph construction will work for:
- ✅ Python → Python calls
- ✅ TypeScript → TypeScript calls
- ✅ JavaScript → JavaScript calls

**Cross-Language Resolution**: Limited support:
- ⚠️ Python → TypeScript calls (NOT resolved in Story 15.3)
- ⚠️ TypeScript → Python calls (NOT resolved in Story 15.3)

**Why Limited?**
- Call resolution uses imports + symbol names
- Cross-language imports have different syntax:
  - Python: `from api.routes import login` (Python module)
  - TypeScript: `import { login } from './api/routes'` (file path)
- No cross-language import tracking in Story 15.3

**Future Enhancement** (EPIC-17 or later):
- Implement cross-language import mapping
- Map Python module paths to TypeScript file paths
- Resolve cross-language calls accurately

**Acceptable for EPIC-15**:
- Goal: Enable multi-language graph construction (foundation)
- Cross-language call resolution: Future enhancement
- In-language resolution: Works perfectly

---

## 📊 Expected Results

### Before (Current State)

**Test Case**: Index `code_test/` (144 TypeScript files)

```
API Logs:
  INFO: Building graph for repository 'code_test', language 'python'
  INFO: Found 0 chunks for repository 'code_test'
  WARNING: No chunks found for repository 'code_test'

Result:
  nodes: 0
  edges: 0
  processing_time_ms: 0
```

### After (With Story 15.3)

**Test Case**: Index `code_test/` (144 TypeScript files)

```
API Logs:
  INFO: Building graph for repository 'code_test', languages: None
  INFO: Detecting languages for repository 'code_test'
  INFO: Detected languages for repository 'code_test': ['typescript']
  INFO: Building graph for repository 'code_test', languages: ['typescript']
  INFO: Found 250 chunks across 1 languages
  INFO: Created 250 nodes for repository 'code_test'
  INFO: Created 180 edges for repository 'code_test'

Result:
  nodes: 250
  edges: 180
  processing_time_ms: 45
```

**Test Case**: Index mixed repository (10 Python + 10 TypeScript files)

```
API Logs:
  INFO: Detecting languages for repository 'mixed-app'
  INFO: Detected languages for repository 'mixed-app': ['python', 'typescript']
  INFO: Building graph for repository 'mixed-app', languages: ['python', 'typescript']
  INFO: Found 85 chunks across 2 languages (45 Python + 40 TypeScript)
  INFO: Created 85 nodes for repository 'mixed-app'
  INFO: Created 67 edges for repository 'mixed-app'

Result:
  nodes: 85
  edges: 67
  processing_time_ms: 32
```

---

## 🔗 Backward Compatibility

### Existing Python-Only Repositories

**Scenario**: User has existing Python-only repository indexed before EPIC-15

**Behavior After EPIC-15**:
1. Rebuild graph: `POST /v1/code/graph/build {"repository": "my-app"}`
2. Auto-detection: Detects `["python"]`
3. Query: `WHERE repository = 'my-app' AND language = 'python'`
4. Result: **Identical to before** (same nodes, same edges)

**Migration**: ✅ **Zero migration required** - backward compatible

### Explicit Language Parameter (Deprecated)

**Old Signature** (Story 15.3 removes):
```python
async def build_graph_for_repository(
    repository: str,
    language: str = "python"  # ← REMOVED
)
```

**New Signature**:
```python
async def build_graph_for_repository(
    repository: str,
    languages: Optional[List[str]] = None  # ← CHANGED
)
```

**Breaking Change**: Yes, but internal API only (not exposed to users)

**Callers to Update**:
- `api/services/code_indexing_service.py` (already updated in Story 15.3)
- No other callers (graph service is internal)

---

## 📊 Definition of Done

**Story 15.3 is complete when**:
1. ✅ All 5 acceptance criteria met (100%)
2. ✅ `build_graph_for_repository()` accepts `languages: Optional[List[str]]`
3. ✅ `_detect_languages_in_repository()` implemented
4. ✅ `IndexRequest` supports `graph_languages` parameter
5. ✅ Integration tests: 3+ test cases (Python-only, TypeScript-only, Mixed)
6. ✅ All tests pass (100% success rate)
7. ✅ Backward compatibility verified (existing Python repos unchanged)
8. ✅ Code review approved
9. ✅ Merged to main branch

---

## 🔗 Related Documents

- [EPIC-15 README](EPIC-15_TYPESCRIPT_JAVASCRIPT_SUPPORT.md) - Epic overview
- [Story 15.1 Analysis](EPIC-15_STORY_15.1_ANALYSIS.md) - TypeScriptParser (dependency)
- [Story 15.2 Analysis](EPIC-15_STORY_15.2_ANALYSIS.md) - JavaScriptParser (dependency)
- [EPIC-15 ULTRATHINK](/tmp/EPIC-15_TYPESCRIPT_SUPPORT_ULTRATHINK.md) - Deep analysis

---

**Last Updated**: 2025-10-23
**Next Action**: Start implementation after Stories 15.1 and 15.2 are complete
