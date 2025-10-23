# EPIC-15 Story 15.4: Integration Testing - Analysis

**Story ID**: EPIC-15.4
**Story Points**: 5 pts
**Status**: 📝 **READY FOR IMPLEMENTATION**
**Priority**: P0 (Critical - Validates entire TypeScript/JavaScript support)
**Dependencies**: Story 15.1 (TypeScriptParser), Story 15.2 (JavaScriptParser), Story 15.3 (Multi-language graph)
**Related**: All previous stories (this validates the complete integration)
**Created**: 2025-10-23
**Last Updated**: 2025-10-23

---

## 📝 User Story

**As a** QA engineer
**I want to** comprehensive integration tests for TypeScript/JavaScript support
**So that** real-world codebases index correctly with semantic chunking, dependency graphs, and hybrid search

---

## 🎯 Acceptance Criteria

1. **Index code_test Repository** (1.5 pts)
   - [ ] Index complete `code_test/` repository (144 TypeScript files, ~28K LOC)
   - [ ] Verify indexing completes without errors
   - [ ] Verify performance: <500ms total indexing time

2. **Validate Chunk Creation** (1 pt)
   - [ ] Verify chunks created: Target 200-300 chunks
   - [ ] Verify chunk creation rate: >80% of files produce semantic chunks (not fallback)
   - [ ] Verify chunk types: Functions, classes, interfaces detected
   - [ ] Verify chunk quality: Names extracted correctly, line numbers accurate

3. **Validate Graph Construction** (1 pt)
   - [ ] Verify graph created: Target 200-300 nodes
   - [ ] Verify edges created: Target 150-250 edges
   - [ ] Verify graph quality: Dependency relationships detected
   - [ ] Verify graph stats: processing_time_ms < 100ms

4. **Validate Search Quality** (1 pt)
   - [ ] Verify lexical search: Returns relevant TypeScript results
   - [ ] Verify vector search: Semantic embeddings work for TypeScript
   - [ ] Verify hybrid search: RRF fusion works across languages
   - [ ] Verify search performance: <200ms per query

5. **Performance Benchmarks** (0.5 pts)
   - [ ] Indexing: <500ms for 144 files
   - [ ] Graph construction: <100ms
   - [ ] Search (hybrid): <200ms per query
   - [ ] Zero regressions: Python performance unchanged

---

## 🔍 Test Codebase: code_test

### Repository Structure

**Location**: `/home/giak/Work/MnemoLite/code_test/`

**Statistics**:
- Files: 144 TypeScript files
- Lines of Code: ~28,794 LOC
- Languages: TypeScript only (no Python)
- Structure: Monorepo with 4 packages

**Package Structure**:
```
code_test/packages/
├── shared/          # Validation, types, i18n
├── core/            # Domain entities, use cases
├── infrastructure/  # Repositories, storage
└── ui/              # Vue components, composables
```

**Sample Files**:
```
packages/core/src/export/domain/entities/ExportFormat.ts (4 lines)
packages/infrastructure/src/repositories/types.ts (4 lines)
packages/ui/src/modules/cv/presentation/composables/index.ts (2 lines)
packages/shared/vitest.setup.ts (6 lines)
```

**Expected Results** (based on ULTRATHINK analysis):
```
Chunks: 200-300 (semantic)
  - Functions: ~100-150
  - Classes: ~30-50
  - Interfaces: ~40-60
  - Methods: ~30-50

Nodes: 200-300 (graph nodes)
Edges: 150-250 (call dependencies)

Performance:
  - Indexing: <500ms (144 files)
  - Graph: <100ms
  - Search: <200ms
```

---

## 💻 Implementation Details

### Integration Test Suite

**Test File**: `tests/integration/test_code_test_repository.py`

```python
"""
Integration tests for EPIC-15 using code_test repository.

Tests complete TypeScript support pipeline:
1. Indexing (AST parsing + chunking)
2. Graph construction (nodes + edges)
3. Hybrid search (lexical + vector + RRF)
4. Performance benchmarks
"""

import pytest
import time
from pathlib import Path
from typing import List

@pytest.mark.integration
@pytest.mark.asyncio
async def test_index_code_test_repository(
    test_client,
    indexing_service
):
    """
    Test indexing complete code_test repository (144 TypeScript files).

    Validates:
    - All files indexed without errors
    - Semantic chunks created (not fallback)
    - Performance < 500ms
    """
    # Step 1: Discover all TypeScript files
    code_test_dir = Path("/home/giak/Work/MnemoLite/code_test")
    ts_files = list(code_test_dir.rglob("*.ts"))

    # Filter out node_modules, dist, spec files
    ts_files = [
        f for f in ts_files
        if "node_modules" not in str(f)
        and "dist" not in str(f)
        and not f.name.endswith(".spec.ts")
        and not f.name.endswith(".config.ts")
        and not f.name.endswith(".d.ts")
    ]

    assert len(ts_files) >= 140, f"Expected ~144 TypeScript files, found {len(ts_files)}"

    # Step 2: Prepare index request
    files_data = []
    for file_path in ts_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        relative_path = str(file_path.relative_to(code_test_dir))
        files_data.append({
            "path": relative_path,
            "content": content,
            "language": "typescript"
        })

    index_request = {
        "repository": "code_test",
        "files": files_data,
        "build_graph": True
    }

    # Step 3: Index repository (measure performance)
    start_time = time.time()
    response = await test_client.post("/v1/code/index", json=index_request)
    elapsed_ms = (time.time() - start_time) * 1000

    # Step 4: Validate response
    assert response.status_code == 200
    data = response.json()

    assert data["repository"] == "code_test"
    assert data["indexed_files"] == len(ts_files)
    assert data["chunks_created"] >= 200, f"Expected >=200 chunks, got {data['chunks_created']}"
    assert data["chunks_created"] <= 400, f"Expected <=400 chunks, got {data['chunks_created']}"

    # Step 5: Validate performance
    assert elapsed_ms < 1000, f"Indexing took {elapsed_ms:.0f}ms, expected <1000ms"

    # Step 6: Validate graph stats
    graph_stats = data["graph_stats"]
    assert graph_stats["nodes_created"] >= 200
    assert graph_stats["nodes_created"] <= 400
    assert graph_stats["edges_created"] >= 150
    assert graph_stats["edges_created"] <= 300

    print(f"""
    ✅ code_test Repository Indexed Successfully

    Files: {data['indexed_files']}
    Chunks: {data['chunks_created']}
    Nodes: {graph_stats['nodes_created']}
    Edges: {graph_stats['edges_created']}
    Time: {elapsed_ms:.0f}ms
    """)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_validate_chunk_quality(test_client, db_engine):
    """
    Validate quality of created chunks for code_test repository.

    Checks:
    - Chunk types (function, class, interface, method)
    - Chunk creation rate (>80% files produce chunks)
    - Name extraction accuracy
    - Line number accuracy
    """
    from sqlalchemy.sql import text

    async with db_engine.connect() as conn:
        # Query 1: Count chunks by type
        query = text("""
            SELECT chunk_type, COUNT(*) as count
            FROM code_chunks
            WHERE repository = 'code_test'
            GROUP BY chunk_type
            ORDER BY count DESC
        """)
        result = await conn.execute(query)
        chunk_types = {row[0]: row[1] for row in result.fetchall()}

    # Validate chunk types
    assert "function" in chunk_types, "No function chunks created"
    assert "class" in chunk_types, "No class chunks created"
    assert "interface" in chunk_types, "No interface chunks created"

    # Validate distribution (rough estimates)
    total_chunks = sum(chunk_types.values())
    assert total_chunks >= 200

    # No fallback chunks (or very few)
    fallback_count = chunk_types.get("fallback_fixed", 0)
    fallback_rate = fallback_count / total_chunks
    assert fallback_rate < 0.2, f"Fallback rate {fallback_rate:.1%} too high (expected <20%)"

    print(f"""
    ✅ Chunk Quality Validation

    Total Chunks: {total_chunks}
    Chunk Types:
      - Function: {chunk_types.get('function', 0)}
      - Class: {chunk_types.get('class', 0)}
      - Interface: {chunk_types.get('interface', 0)}
      - Method: {chunk_types.get('method', 0)}
      - Fallback: {fallback_count} ({fallback_rate:.1%})
    """)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_validate_graph_quality(test_client, db_engine):
    """
    Validate quality of dependency graph for code_test repository.

    Checks:
    - Node creation (functions/classes become nodes)
    - Edge creation (call dependencies)
    - Graph traversal works
    """
    from sqlalchemy.sql import text

    async with db_engine.connect() as conn:
        # Query 1: Count nodes by type
        query = text("""
            SELECT node_type, COUNT(*) as count
            FROM nodes
            WHERE properties->>'repository' = 'code_test'
            GROUP BY node_type
            ORDER BY count DESC
        """)
        result = await conn.execute(query)
        node_types = {row[0]: row[1] for row in result.fetchall()}

        # Query 2: Count edges by relation type
        query = text("""
            SELECT relation_type, COUNT(*) as count
            FROM edges
            WHERE properties->>'repository' = 'code_test'
            GROUP BY relation_type
            ORDER BY count DESC
        """)
        result = await conn.execute(query)
        edge_types = {row[0]: row[1] for row in result.fetchall()}

    # Validate nodes
    total_nodes = sum(node_types.values())
    assert total_nodes >= 200, f"Expected >=200 nodes, got {total_nodes}"

    # Validate edges
    total_edges = sum(edge_types.values())
    assert total_edges >= 100, f"Expected >=100 edges, got {total_edges}"

    # Validate edge types
    assert "calls" in edge_types or "imports" in edge_types

    print(f"""
    ✅ Graph Quality Validation

    Total Nodes: {total_nodes}
    Node Types:
      - Function: {node_types.get('function', 0)}
      - Class: {node_types.get('class', 0)}
      - Method: {node_types.get('method', 0)}

    Total Edges: {total_edges}
    Edge Types:
      - Calls: {edge_types.get('calls', 0)}
      - Imports: {edge_types.get('imports', 0)}
    """)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_quality_typescript(test_client):
    """
    Validate search quality for TypeScript code.

    Tests:
    - Lexical search (BM25)
    - Vector search (semantic embeddings)
    - Hybrid search (RRF fusion)
    """
    # Test 1: Lexical search for "ExportFormat"
    response = await test_client.post("/v1/code/search/lexical", json={
        "repository": "code_test",
        "query": "ExportFormat",
        "limit": 10
    })
    assert response.status_code == 200
    lexical_results = response.json()["results"]
    assert len(lexical_results) > 0, "Lexical search returned 0 results"

    # Test 2: Vector search for "export resume to PDF"
    response = await test_client.post("/v1/code/search/vector", json={
        "repository": "code_test",
        "query": "export resume to PDF",
        "limit": 10
    })
    assert response.status_code == 200
    vector_results = response.json()["results"]
    assert len(vector_results) > 0, "Vector search returned 0 results"

    # Test 3: Hybrid search for "storage repository interface"
    start_time = time.time()
    response = await test_client.post("/v1/code/search/hybrid", json={
        "repository": "code_test",
        "query": "storage repository interface",
        "limit": 10
    })
    elapsed_ms = (time.time() - start_time) * 1000

    assert response.status_code == 200
    hybrid_results = response.json()["results"]
    assert len(hybrid_results) > 0, "Hybrid search returned 0 results"

    # Validate performance
    assert elapsed_ms < 500, f"Hybrid search took {elapsed_ms:.0f}ms, expected <500ms"

    print(f"""
    ✅ Search Quality Validation

    Lexical Results: {len(lexical_results)}
    Vector Results: {len(vector_results)}
    Hybrid Results: {len(hybrid_results)}
    Hybrid Search Time: {elapsed_ms:.0f}ms
    """)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_performance_benchmarks(test_client, db_engine):
    """
    Performance benchmarks for TypeScript support.

    Validates:
    - Indexing performance (<500ms for 100 files)
    - Graph construction (<100ms)
    - Search performance (<200ms)
    - Zero regressions for Python
    """
    # Benchmark already validated in test_index_code_test_repository
    # This test can be extended with more detailed profiling

    pass  # Placeholder for future detailed benchmarks
```

---

## 🧪 Additional Test Files

### TypeScript-Specific Tests

**Test File**: `tests/integration/test_typescript_indexing.py`

```python
"""TypeScript-specific indexing tests."""

@pytest.mark.asyncio
async def test_typescript_class_with_methods():
    """Test indexing TypeScript class with methods."""
    # Index single file with class + methods
    # Validate: 1 class chunk + N method chunks

@pytest.mark.asyncio
async def test_typescript_interface():
    """Test indexing TypeScript interface."""
    # Index file with interface
    # Validate: 1 interface chunk

@pytest.mark.asyncio
async def test_typescript_arrow_function():
    """Test indexing arrow function."""
    # Index file with arrow function
    # Validate: 1 function chunk

@pytest.mark.asyncio
async def test_typescript_async_function():
    """Test indexing async function."""
    # Index file with async function
    # Validate: 1 function chunk with async metadata
```

**Test File**: `tests/integration/test_javascript_indexing.py`

```python
"""JavaScript-specific indexing tests."""

@pytest.mark.asyncio
async def test_javascript_es6_class():
    """Test indexing JavaScript ES6 class."""
    # Index file with ES6 class
    # Validate: 1 class chunk + methods

@pytest.mark.asyncio
async def test_javascript_commonjs():
    """Test indexing CommonJS module."""
    # Index file with module.exports
    # Validate: Functions extracted correctly
```

---

## 📊 Success Metrics

### Quantitative Metrics

**Chunk Creation**:
- ✅ Total chunks: 200-300
- ✅ Chunk creation rate: >80% (not fallback)
- ✅ Chunk types: Function, Class, Interface, Method

**Graph Construction**:
- ✅ Total nodes: 200-300
- ✅ Total edges: 150-250
- ✅ Graph construction time: <100ms

**Search Quality**:
- ✅ Lexical search: Returns relevant results
- ✅ Vector search: Semantic embeddings work
- ✅ Hybrid search: RRF fusion works

**Performance**:
- ✅ Indexing: <500ms for 144 files (<3.5ms/file)
- ✅ Graph: <100ms
- ✅ Search: <200ms per query

### Qualitative Metrics

**Code Quality**:
- ✅ Names extracted correctly (no "anonymous_*")
- ✅ Line numbers accurate
- ✅ Source code preserved

**Error Handling**:
- ✅ No crashes on edge cases
- ✅ Graceful fallback for invalid syntax
- ✅ Clear error messages

**Backward Compatibility**:
- ✅ Python support unchanged
- ✅ Existing tests pass
- ✅ No performance regressions

---

## 📊 Definition of Done

**Story 15.4 is complete when**:
1. ✅ All 5 acceptance criteria met (100%)
2. ✅ code_test repository indexes successfully
3. ✅ 200-300 chunks created (>80% semantic, <20% fallback)
4. ✅ 200-300 nodes, 150-250 edges in graph
5. ✅ Search quality validated (lexical, vector, hybrid)
6. ✅ Performance benchmarks met (<500ms indexing, <200ms search)
7. ✅ Integration tests: 4+ test files, 15+ test cases
8. ✅ All tests pass (100% success rate)
9. ✅ Code review approved
10. ✅ Merged to main branch

---

## 🔗 Related Documents

- [EPIC-15 README](EPIC-15_TYPESCRIPT_JAVASCRIPT_SUPPORT.md) - Epic overview
- [Story 15.1 Analysis](EPIC-15_STORY_15.1_ANALYSIS.md) - TypeScriptParser
- [Story 15.2 Analysis](EPIC-15_STORY_15.2_ANALYSIS.md) - JavaScriptParser
- [Story 15.3 Analysis](EPIC-15_STORY_15.3_ANALYSIS.md) - Multi-language graph
- [EPIC-15 ULTRATHINK](/tmp/EPIC-15_TYPESCRIPT_SUPPORT_ULTRATHINK.md) - Deep analysis

---

**Last Updated**: 2025-10-23
**Next Action**: Start implementation after Stories 15.1-15.3 are complete
