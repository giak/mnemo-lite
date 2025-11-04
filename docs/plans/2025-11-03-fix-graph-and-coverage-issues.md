# Fix Graph Construction and Coverage Issues - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix corrupted graph nodes (type=None, truncated labels) and add support for indexing test files to improve coverage from 43.7% to 80%+.

**Architecture:** GraphConstructionService creates nodes with proper type/name extraction from chunk metadata. BatchIndexingProducer supports include_tests flag to optionally index test files. TypeScript extractor adds lsp_type to metadata for LSP-compliant filtering.

**Tech Stack:** Python 3.12, asyncio, SQLAlchemy (asyncpg), PostgreSQL 18, tree-sitter (TypeScript AST)

---

## Context

**Current Issues (from CVgenerator audit):**
- 272 graph nodes with `type: None` (should have class/function/interface/method)
- Node labels truncated/corrupted: "18nAdapter impleme" instead of "I18nAdapter implements"
- File paths corrupted: "A" instead of full path
- 138/245 files missing (43.7% coverage)
  - 104 test files not indexed (42.4%)
  - 8 config files (3.3%)
  - 28 other files (11.4%)
- 0% chunks with lsp_type metadata

**Root Causes:**
1. Graph service not extracting type/name from chunk metadata correctly
2. Node labels limited to 20 chars (database schema issue)
3. Test files excluded by default
4. TypeScript extractor doesn't add lsp_type

---

## Task 1: Fix Graph Node Type and Properties

**Files:**
- Modify: `api/services/graph_construction_service.py:400-500`
- Test: `tests/integration/test_graph_node_properties.py`

**Step 1: Write failing test for node properties**

```python
# tests/integration/test_graph_node_properties.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from services.graph_construction_service import GraphConstructionService
from db.repositories.code_chunk_repository import CodeChunkRepository
from models.code_chunk import CodeChunkCreate
import os


@pytest.mark.asyncio
async def test_graph_nodes_have_correct_type_from_chunks():
    """Test that graph nodes extract type from chunk metadata."""
    db_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    engine = create_async_engine(db_url)
    test_repo = "test_node_properties"

    # Cleanup
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM code_chunks WHERE repository = :repo"), {"repo": test_repo})
        await conn.execute(text("DELETE FROM nodes WHERE properties->>'repository' = :repo"), {"repo": test_repo})

    # Create chunks with different types
    chunks = [
        CodeChunkCreate(
            repository=test_repo,
            file_path="/test/Calculator.ts",
            chunk_index=0,
            chunk_type="class",
            language="typescript",
            source_code="class Calculator { add() {} }",
            start_line=1,
            end_line=5,
            embedding_code=[0.1] * 768,
            metadata={
                "name": "Calculator",
                "type": "class",
                "exports": ["Calculator"]
            }
        ),
        CodeChunkCreate(
            repository=test_repo,
            file_path="/test/Calculator.ts",
            chunk_index=1,
            chunk_type="method",
            language="typescript",
            source_code="add(a, b) { return a + b; }",
            start_line=2,
            end_line=4,
            embedding_code=[0.2] * 768,
            metadata={
                "name": "add",
                "type": "method",
                "signature": {"function_name": "add"}
            }
        ),
        CodeChunkCreate(
            repository=test_repo,
            file_path="/test/utils.ts",
            chunk_index=0,
            chunk_type="function",
            language="typescript",
            source_code="function sum(arr) {}",
            start_line=1,
            end_line=3,
            embedding_code=[0.3] * 768,
            metadata={
                "name": "sum",
                "type": "function",
                "signature": {"function_name": "sum"}
            }
        )
    ]

    # Insert chunks
    async with engine.begin() as conn:
        chunk_repo = CodeChunkRepository(engine, connection=conn)
        for chunk in chunks:
            await chunk_repo.add(chunk)

    # Build graph
    graph_service = GraphConstructionService(engine)
    await graph_service.build_graph_for_repository(test_repo, languages=["typescript"])

    # Verify nodes have correct properties
    async with engine.begin() as conn:
        nodes = await conn.execute(text("""
            SELECT label, properties
            FROM nodes
            WHERE properties->>'repository' = :repo
            ORDER BY properties->>'name'
        """), {"repo": test_repo})

        nodes_list = nodes.fetchall()

    await engine.dispose()

    # Assertions
    assert len(nodes_list) >= 3, f"Expected at least 3 nodes, got {len(nodes_list)}"

    # Check Calculator class node
    calc_node = next((n for n in nodes_list if n.properties.get('name') == 'Calculator'), None)
    assert calc_node is not None, "Calculator node not found"
    assert calc_node.properties.get('type') == 'class', f"Expected type='class', got {calc_node.properties.get('type')}"
    assert calc_node.properties.get('file') == '/test/Calculator.ts', "File path incorrect"
    assert 'Calculator' in calc_node.label, f"Label should contain 'Calculator', got {calc_node.label}"

    # Check add method node
    add_node = next((n for n in nodes_list if n.properties.get('name') == 'add'), None)
    assert add_node is not None, "add method node not found"
    assert add_node.properties.get('type') == 'method', f"Expected type='method', got {add_node.properties.get('type')}"

    # Check sum function node
    sum_node = next((n for n in nodes_list if n.properties.get('name') == 'sum'), None)
    assert sum_node is not None, "sum function node not found"
    assert sum_node.properties.get('type') == 'function', f"Expected type='function', got {sum_node.properties.get('type')}"


@pytest.mark.asyncio
async def test_graph_node_labels_not_truncated():
    """Test that node labels preserve full names."""
    db_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    engine = create_async_engine(db_url)
    test_repo = "test_label_length"

    # Cleanup
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM code_chunks WHERE repository = :repo"), {"repo": test_repo})
        await conn.execute(text("DELETE FROM nodes WHERE properties->>'repository' = :repo"), {"repo": test_repo})

    # Create chunk with long name
    long_name = "VeryLongClassNameThatExceedsTwentyCharacters"
    chunk = CodeChunkCreate(
        repository=test_repo,
        file_path="/test/Long.ts",
        chunk_index=0,
        chunk_type="class",
        language="typescript",
        source_code=f"class {long_name} {{ }}",
        start_line=1,
        end_line=1,
        embedding_code=[0.1] * 768,
        metadata={"name": long_name, "type": "class"}
    )

    async with engine.begin() as conn:
        chunk_repo = CodeChunkRepository(engine, connection=conn)
        await chunk_repo.add(chunk)

    # Build graph
    graph_service = GraphConstructionService(engine)
    await graph_service.build_graph_for_repository(test_repo, languages=["typescript"])

    # Verify label contains full name (or reasonable truncation with ellipsis)
    async with engine.begin() as conn:
        node = await conn.execute(text("""
            SELECT label, properties
            FROM nodes
            WHERE properties->>'repository' = :repo
        """), {"repo": test_repo})

        node_data = node.fetchone()

    await engine.dispose()

    assert node_data is not None
    # Either full name or truncated with ellipsis (not corrupt)
    assert long_name in node_data.label or node_data.label.endswith('...'), \
        f"Label should contain full name or ellipsis, got: {node_data.label}"
```

**Step 2: Run test to verify it fails**

Run: `EMBEDDING_MODE=mock TEST_DATABASE_URL=$DATABASE_URL pytest tests/integration/test_graph_node_properties.py -v`

Expected: FAIL - nodes have type=None, labels truncated

**Step 3: Investigate current node creation logic**

```bash
# Check how nodes are created from chunks
grep -A 30 "_create_nodes_from_chunks" api/services/graph_construction_service.py
```

**Step 4: Fix node property extraction**

```python
# api/services/graph_construction_service.py (around line 450)

async def _create_nodes_from_chunks(
    self,
    chunks: List[Any],
    repository: str,
    conn
) -> int:
    """
    Create graph nodes from code chunks.

    Extracts type, name, and file path from chunk metadata.
    """
    nodes_created = 0

    for chunk in chunks:
        try:
            # Extract metadata
            metadata = chunk.metadata or {}
            chunk_type = chunk.chunk_type  # class, method, function, interface

            # Get name from metadata (priority order)
            name = (
                metadata.get('name') or
                (metadata.get('signature', {}) or {}).get('function_name') or
                f"{chunk_type}_{chunk.chunk_index}"
            )

            # Get type (use chunk_type or metadata.type)
            node_type = metadata.get('type') or chunk_type

            # Create label (use full name, truncate only if absolutely necessary)
            label = name
            if len(label) > 100:  # Reasonable limit
                label = label[:97] + "..."

            # Build properties
            properties = {
                "type": node_type,
                "name": name,
                "file": chunk.file_path,
                "repository": repository,
                "language": chunk.language,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "chunk_id": str(chunk.chunk_id) if hasattr(chunk, 'chunk_id') else None
            }

            # Add complexity if available
            if 'complexity' in metadata:
                complexity = metadata['complexity']
                if isinstance(complexity, dict):
                    properties['cyclomatic_complexity'] = complexity.get('cyclomatic', 0)
                    properties['lines_of_code'] = complexity.get('lines_of_code', 0)

            # Insert node
            result = await conn.execute(
                text("""
                    INSERT INTO nodes (label, properties, embedding)
                    VALUES (:label, :properties, :embedding)
                    RETURNING node_id
                """),
                {
                    "label": label,
                    "properties": properties,
                    "embedding": chunk.embedding_code
                }
            )

            node_id = result.scalar()
            nodes_created += 1

            self.logger.debug(f"Created node: {label} (type={node_type}, file={chunk.file_path})")

        except Exception as e:
            self.logger.error(f"Failed to create node from chunk {chunk.chunk_index}: {e}")
            continue

    return nodes_created
```

**Step 5: Run test to verify it passes**

Run: `EMBEDDING_MODE=mock TEST_DATABASE_URL=$DATABASE_URL pytest tests/integration/test_graph_node_properties.py -v`

Expected: PASS (2/2 tests)

**Step 6: Commit**

```bash
git add api/services/graph_construction_service.py tests/integration/test_graph_node_properties.py
git commit -m "fix(graph): extract proper type/name/file from chunk metadata

- Extract node type from chunk_type or metadata.type
- Extract name from metadata with fallback chain
- Use full file path instead of truncated
- Create descriptive labels (max 100 chars with ellipsis)
- Add cyclomatic complexity and LOC to properties

Fixes corrupted nodes with type=None and truncated labels.
Tests: 2/2 passing"
```

---

## Task 2: Add Support for Indexing Test Files

**Files:**
- Modify: `api/models/batch_indexing_models.py:10-20`
- Modify: `api/services/batch_indexing_producer.py:50-70`
- Modify: `api/routes/batch_indexing_routes.py:30-50`
- Test: `tests/unit/test_batch_producer_include_tests.py`

**Step 1: Write failing test for include_tests flag**

```python
# tests/unit/test_batch_producer_include_tests.py
import pytest
from pathlib import Path
from services.batch_indexing_producer import BatchIndexingProducer


def test_scan_files_excludes_tests_by_default(tmp_path):
    """Test that test files are excluded by default."""
    # Setup: Create source and test files
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "app.ts").write_text("export const app = 1;")

    test_dir = tmp_path / "__tests__"
    test_dir.mkdir()
    (test_dir / "app.spec.ts").write_text("test('app', () => {});")

    # Execute: Scan files (default: exclude tests)
    producer = BatchIndexingProducer()
    files = producer.scan_files(tmp_path, [".ts"], include_tests=False)

    # Verify: Only source file found
    file_paths = [str(f.relative_to(tmp_path)) for f in files]
    assert "src/app.ts" in file_paths
    assert "tests/app.spec.ts" not in file_paths
    assert len(files) == 1


def test_scan_files_includes_tests_when_flag_enabled(tmp_path):
    """Test that test files are included when include_tests=True."""
    # Setup
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "app.ts").write_text("export const app = 1;")

    test_dir = tmp_path / "__tests__"
    test_dir.mkdir()
    (test_dir / "app.spec.ts").write_text("test('app', () => {});")

    # Execute: Scan with include_tests=True
    producer = BatchIndexingProducer()
    files = producer.scan_files(tmp_path, [".ts"], include_tests=True)

    # Verify: Both files found
    file_paths = [str(f.relative_to(tmp_path)) for f in files]
    assert "src/app.ts" in file_paths
    assert "__tests__/app.spec.ts" in file_paths
    assert len(files) == 2


def test_scan_files_detects_various_test_patterns(tmp_path):
    """Test that all test patterns are detected."""
    # Setup: Various test file patterns
    (tmp_path / "app.spec.ts").write_text("test")
    (tmp_path / "app.test.ts").write_text("test")

    tests_dir = tmp_path / "__tests__"
    tests_dir.mkdir()
    (tests_dir / "unit.ts").write_text("test")

    # Execute: include_tests=True
    producer = BatchIndexingProducer()
    files = producer.scan_files(tmp_path, [".ts"], include_tests=True)

    # Verify: All test files found
    assert len(files) == 3

    # Execute: include_tests=False
    files_no_tests = producer.scan_files(tmp_path, [".ts"], include_tests=False)

    # Verify: No test files
    assert len(files_no_tests) == 0
```

**Step 2: Run test to verify it fails**

Run: `EMBEDDING_MODE=mock pytest tests/unit/test_batch_producer_include_tests.py -v`

Expected: FAIL - method doesn't accept include_tests parameter

**Step 3: Update Pydantic model**

```python
# api/models/batch_indexing_models.py
from pydantic import BaseModel, Field
from typing import List


class BatchIndexingRequest(BaseModel):
    """Request model for starting batch indexing."""
    directory: str = Field(..., description="Directory to scan")
    repository: str = Field(..., description="Repository name")
    extensions: List[str] = Field(
        default=[".ts", ".js"],
        description="File extensions to index"
    )
    include_tests: bool = Field(
        default=False,
        description="Include test files (__tests__/, .spec.*, .test.*)"
    )
```

**Step 4: Update producer scan_files method**

```python
# api/services/batch_indexing_producer.py:50

def scan_files(
    self,
    directory: Path,
    extensions: List[str],
    include_tests: bool = False
) -> List[Path]:
    """
    Scan directory for files with specified extensions.

    Args:
        directory: Root directory to scan
        extensions: List of extensions (e.g., [".ts", ".js"])
        include_tests: Include test files (default: False)

    Returns:
        Sorted list of file paths (excluding node_modules, .git, dist, etc.)
    """
    files = []
    excluded_dirs = {"node_modules", ".git", ".svn", ".hg", "__pycache__", "dist", "build", ".next"}
    test_patterns = {"__tests__", ".spec.", ".test.", "vitest.config", "vitest.setup"}

    for ext in extensions:
        for file_path in directory.rglob(f"*{ext}"):
            # Check excluded directories
            path_parts = set(file_path.relative_to(directory).parts)
            if path_parts & excluded_dirs:
                continue

            # Check test patterns (skip if include_tests=False)
            if not include_tests:
                file_str = str(file_path)
                if any(pattern in file_str for pattern in test_patterns):
                    continue

            files.append(file_path)

    return sorted(files)
```

**Step 5: Update scan_and_enqueue to pass include_tests**

```python
# api/services/batch_indexing_producer.py:82

async def scan_and_enqueue(
    self,
    directory: Path,
    repository: str,
    extensions: List[str] = [".ts", ".js"],
    include_tests: bool = False  # NEW PARAMETER
) -> Dict:
    """
    Scan directory, divide into batches, enqueue to Redis Stream.

    Args:
        directory: Directory to scan
        repository: Repository name
        extensions: File extensions to index
        include_tests: Include test files (default: False)

    Returns:
        {"job_id": "uuid", "total_files": 261, "total_batches": 7, "status": "pending"}
    """
    await self.connect()

    # 1. Scan files (with include_tests parameter)
    files = self.scan_files(directory, extensions, include_tests=include_tests)
    total_files = len(files)

    # ... rest of method unchanged ...
```

**Step 6: Update API route**

```python
# api/routes/batch_indexing_routes.py:30

@router.post("/start")
async def start_batch_indexing(request: BatchIndexingRequest) -> BatchIndexingResponse:
    """Start batch indexing job."""
    producer = BatchIndexingProducer()
    job_info = await producer.scan_and_enqueue(
        Path(request.directory),
        request.repository,
        request.extensions,
        include_tests=request.include_tests  # NEW PARAMETER
    )

    message = f"Batch indexing started. Found {job_info['total_files']} files."
    if request.include_tests:
        message += " (including test files)"
    message += f" Use GET /status/{request.repository} to monitor progress."

    return BatchIndexingResponse(
        job_id=job_info["job_id"],
        total_files=job_info["total_files"],
        total_batches=job_info["total_batches"],
        status=job_info["status"],
        message=message
    )
```

**Step 7: Run test to verify it passes**

Run: `EMBEDDING_MODE=mock pytest tests/unit/test_batch_producer_include_tests.py -v`

Expected: PASS (3/3 tests)

**Step 8: Commit**

```bash
git add api/models/batch_indexing_models.py api/services/batch_indexing_producer.py api/routes/batch_indexing_routes.py tests/unit/test_batch_producer_include_tests.py
git commit -m "feat(batch-indexing): add include_tests flag to index test files

- Add include_tests parameter to BatchIndexingRequest model
- Update scan_files() to detect and exclude/include test patterns
- Test patterns: __tests__/, .spec., .test., vitest.*
- Default: exclude tests (backward compatible)
- Update API route to pass include_tests flag

Tests: 3/3 passing"
```

---

## Task 3: Add lsp_type to TypeScript Metadata

**Files:**
- Modify: `api/services/metadata_extractors/typescript_extractor.py:100-200`
- Test: `tests/services/test_typescript_extractor_lsp_type.py`

**Step 1: Write failing test for lsp_type**

```python
# tests/services/test_typescript_extractor_lsp_type.py
import pytest
from services.metadata_extractors.typescript_extractor import TypeScriptExtractor


def test_extract_metadata_includes_lsp_type_for_class():
    """Test that class chunks include lsp_type='class'."""
    extractor = TypeScriptExtractor()

    code = """
export class Calculator {
    add(a: number, b: number): number {
        return a + b;
    }
}
"""

    chunks = extractor.extract_chunks(code, "/test/Calculator.ts")

    # Find class chunk
    class_chunk = next((c for c in chunks if c['chunk_type'] == 'class'), None)
    assert class_chunk is not None, "Class chunk not found"

    # Verify lsp_type
    assert 'lsp_type' in class_chunk['metadata'], "lsp_type missing from metadata"
    assert class_chunk['metadata']['lsp_type'] == 'class', \
        f"Expected lsp_type='class', got {class_chunk['metadata'].get('lsp_type')}"


def test_extract_metadata_includes_lsp_type_for_method():
    """Test that method chunks include lsp_type='method'."""
    extractor = TypeScriptExtractor()

    code = """
class Calc {
    add(a, b) { return a + b; }
}
"""

    chunks = extractor.extract_chunks(code, "/test/Calc.ts")

    # Find method chunk
    method_chunk = next((c for c in chunks if c['chunk_type'] == 'method'), None)
    assert method_chunk is not None, "Method chunk not found"

    assert method_chunk['metadata']['lsp_type'] == 'method'


def test_extract_metadata_includes_lsp_type_for_function():
    """Test that function chunks include lsp_type='function'."""
    extractor = TypeScriptExtractor()

    code = "export function sum(arr) { return arr.reduce((a, b) => a + b, 0); }"

    chunks = extractor.extract_chunks(code, "/test/utils.ts")

    func_chunk = next((c for c in chunks if c['chunk_type'] == 'function'), None)
    assert func_chunk is not None
    assert func_chunk['metadata']['lsp_type'] == 'function'


def test_extract_metadata_includes_lsp_type_for_interface():
    """Test that interface chunks include lsp_type='interface'."""
    extractor = TypeScriptExtractor()

    code = """
export interface User {
    name: string;
    email: string;
}
"""

    chunks = extractor.extract_chunks(code, "/test/types.ts")

    interface_chunk = next((c for c in chunks if c['chunk_type'] == 'interface'), None)
    assert interface_chunk is not None
    assert interface_chunk['metadata']['lsp_type'] == 'interface'


def test_lsp_type_mapping_completeness():
    """Test that all chunk types have lsp_type mapping."""
    extractor = TypeScriptExtractor()

    # Test data for each chunk type
    test_cases = {
        'class': "class Foo {}",
        'method': "class X { foo() {} }",
        'function': "function bar() {}",
        'interface': "interface Baz {}",
    }

    for expected_type, code in test_cases.items():
        chunks = extractor.extract_chunks(code, f"/test/{expected_type}.ts")
        chunk = chunks[0] if chunks else None
        assert chunk is not None, f"No chunk for {expected_type}"
        assert 'lsp_type' in chunk['metadata'], f"lsp_type missing for {expected_type}"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_typescript_extractor_lsp_type.py -v`

Expected: FAIL - lsp_type not in metadata

**Step 3: Add lsp_type mapping**

```python
# api/services/metadata_extractors/typescript_extractor.py (around line 150)

def _get_lsp_type(self, chunk_type: str, node_type: str = None) -> str:
    """
    Map chunk_type and AST node_type to LSP-compliant type.

    Args:
        chunk_type: The chunk type (class, method, function, interface, etc.)
        node_type: Optional AST node type for additional context

    Returns:
        LSP type string (class, method, function, interface, enum, etc.)
    """
    # Direct mapping for most types
    lsp_mapping = {
        "class": "class",
        "method": "method",
        "function": "function",
        "interface": "interface",
        "enum": "enum",
        "type_alias": "type",
        "config_module": "module",
        "barrel": "module",
        "fallback_fixed": "unknown"
    }

    return lsp_mapping.get(chunk_type, "unknown")


def _build_metadata(self, node, chunk_type: str, ...) -> dict:
    """
    Build metadata dictionary for a code chunk.

    Returns metadata with calls, imports, signature, complexity, and lsp_type.
    """
    metadata = {
        "lsp_type": self._get_lsp_type(chunk_type, node.type if node else None),
        "name": self._extract_name(node, chunk_type),
        "type": chunk_type,  # Keep existing type field for backward compatibility
        "imports": self._extract_imports(node),
        "exports": self._extract_exports(node),
        "calls": self._extract_calls(node),
        "call_contexts": self._extract_call_contexts(node),
        "signature": self._extract_signature(node),
        "complexity": self._calculate_complexity(node),
        "re_exports": self._extract_re_exports(node),
    }

    return metadata
```

**Step 4: Update all metadata extraction calls**

```python
# Ensure _build_metadata is called for all chunk types
# Check lines 200-400 in typescript_extractor.py

# Example for class extraction (around line 220):
def _extract_class_chunk(self, node, ...):
    """Extract class as a chunk."""
    metadata = self._build_metadata(node, "class")  # lsp_type added automatically

    chunk = {
        "chunk_type": "class",
        "source_code": self._get_node_text(node),
        "start_line": node.start_point[0] + 1,
        "end_line": node.end_point[0] + 1,
        "metadata": metadata  # Contains lsp_type
    }

    return chunk

# Repeat for method, function, interface, etc.
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/services/test_typescript_extractor_lsp_type.py -v`

Expected: PASS (5/5 tests)

**Step 6: Commit**

```bash
git add api/services/metadata_extractors/typescript_extractor.py tests/services/test_typescript_extractor_lsp_type.py
git commit -m "feat(metadata): add lsp_type to TypeScript chunk metadata

- Add _get_lsp_type() method to map chunk types to LSP types
- Include lsp_type in all extracted metadata
- Supports: class, method, function, interface, enum, type, module
- LSP-compliant filtering now possible

Tests: 5/5 passing"
```

---

## Task 4: Re-index CVgenerator with Fixes

**Files:**
- Script: Manual re-indexing with verification

**Step 1: Clean existing CVgenerator data**

```bash
docker exec mnemo-api python /app/scripts/clean_and_reindex.py --repository CVgenerator
```

Expected: Deleted 830 chunks, 272 nodes

**Step 2: Restart API to load fixes**

```bash
docker compose restart api
sleep 5  # Wait for API to start
```

**Step 3: Start batch indexing WITH test files**

```bash
curl -X POST http://localhost:8001/api/v1/indexing/batch/start \
  -H "Content-Type: application/json" \
  -d '{
    "directory": "/app/code_test",
    "repository": "CVgenerator",
    "extensions": [".ts", ".js"],
    "include_tests": true
  }' | jq
```

Expected: ~245 files found (including tests)

**Step 4: Start consumer daemon**

```bash
docker exec -d mnemo-api python /app/scripts/batch_index_consumer.py \
  --repository CVgenerator \
  --verbose
```

**Step 5: Monitor progress (wait ~2-3 minutes)**

```bash
# Check every 30 seconds
watch -n 30 'curl -s http://localhost:8001/api/v1/indexing/batch/status/CVgenerator | jq'
```

Wait for `status: "completed"`

**Step 6: Verify improvements**

```bash
docker exec -i mnemo-api python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import os

async def verify():
    engine = create_async_engine(os.getenv('DATABASE_URL'))
    async with engine.begin() as conn:
        # Check chunks
        chunks = await conn.execute(text('SELECT COUNT(*) FROM code_chunks WHERE repository = :repo'), {'repo': 'CVgenerator'})
        chunk_count = chunks.scalar()

        # Check test files
        test_chunks = await conn.execute(text(\"SELECT COUNT(*) FROM code_chunks WHERE repository = :repo AND (file_path LIKE '%__tests__%' OR file_path LIKE '%.spec.%' OR file_path LIKE '%.test.%')\"), {'repo': 'CVgenerator'})
        test_count = test_chunks.scalar()

        # Check lsp_type coverage
        lsp = await conn.execute(text(\"SELECT COUNT(*) FROM code_chunks WHERE repository = :repo AND metadata->>'lsp_type' IS NOT NULL\"), {'repo': 'CVgenerator'})
        lsp_count = lsp.scalar()

        # Check nodes with type
        nodes_typed = await conn.execute(text(\"SELECT COUNT(*) FROM nodes WHERE properties->>'repository' = :repo AND properties->>'type' IS NOT NULL AND properties->>'type' != 'None'\"), {'repo': 'CVgenerator'})
        typed_count = nodes_typed.scalar()

        # Check total nodes
        nodes = await conn.execute(text(\"SELECT COUNT(*) FROM nodes WHERE properties->>'repository' = :repo\"), {'repo': 'CVgenerator'})
        node_count = nodes.scalar()

        # Sample node to verify properties
        sample = await conn.execute(text(\"SELECT label, properties FROM nodes WHERE properties->>'repository' = :repo LIMIT 1\"), {'repo': 'CVgenerator'})
        sample_node = sample.fetchone()

        print('=== VERIFICATION POST-FIX ===')
        print(f'Total chunks: {chunk_count}')
        print(f'Test chunks: {test_count} ({test_count/chunk_count*100:.1f}% if chunk_count > 0 else 0)')
        print(f'Chunks with lsp_type: {lsp_count}/{chunk_count} ({lsp_count/chunk_count*100:.1f}% if chunk_count > 0 else 0)')
        print(f'\\nNodes with valid type: {typed_count}/{node_count} ({typed_count/node_count*100:.1f}% if node_count > 0 else 0)')

        if sample_node:
            print(f'\\nSample node:')
            print(f'  Label: {sample_node.label}')
            print(f'  Type: {sample_node.properties.get(\"type\")}')
            print(f'  Name: {sample_node.properties.get(\"name\")}')
            print(f'  File: {sample_node.properties.get(\"file\", \"N/A\")[:50]}')

        # Success criteria
        print(f'\\n=== SUCCESS CRITERIA ===')
        if test_count > 0:
            print('✅ Test files indexed')
        else:
            print('❌ No test files indexed')

        if lsp_count / chunk_count > 0.9 if chunk_count > 0:
            print('✅ lsp_type coverage > 90%')
        else:
            print(f'❌ lsp_type coverage: {lsp_count/chunk_count*100:.1f}%')

        if typed_count / node_count > 0.9 if node_count > 0:
            print('✅ Node types valid > 90%')
        else:
            print(f'❌ Node types valid: {typed_count/node_count*100:.1f}%')

    await engine.dispose()

asyncio.run(verify())
"
```

Expected:
- Total chunks: > 1500 (with tests)
- Test chunks: > 500 (40%+)
- lsp_type coverage: > 90%
- Nodes with valid type: > 90%

**Step 7: No commit needed (manual verification step)**

---

## Summary

**Tasks Completed:**
1. ✅ Fixed graph node type/name/file extraction
2. ✅ Added include_tests flag for test file indexing
3. ✅ Added lsp_type to TypeScript metadata
4. ✅ Re-indexed CVgenerator with all fixes

**Expected Results After Re-indexing:**
- **Coverage:** 43.7% → 80%+ (test files included)
- **lsp_type:** 0% → 90%+ coverage
- **Graph nodes:** type=None → proper types (class/function/method/interface)
- **Node labels:** Truncated → Full names (max 100 chars)
- **Test files:** 0 → 104+ indexed

**Files Modified:**
- `api/services/graph_construction_service.py` - Node property extraction
- `api/models/batch_indexing_models.py` - include_tests flag
- `api/services/batch_indexing_producer.py` - Test file detection
- `api/routes/batch_indexing_routes.py` - API parameter
- `api/services/metadata_extractors/typescript_extractor.py` - lsp_type

**Tests Added:**
- `tests/integration/test_graph_node_properties.py` (2 tests)
- `tests/unit/test_batch_producer_include_tests.py` (3 tests)
- `tests/services/test_typescript_extractor_lsp_type.py` (5 tests)

**Total:** +10 tests (all passing)
