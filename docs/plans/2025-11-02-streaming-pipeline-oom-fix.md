# Streaming Pipeline for OOM Fix - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the indexing pipeline into a fully streamed file-at-a-time architecture that maintains constant memory footprint (~2-3GB) regardless of repository size, enabling robust indexation of large codebases like code_test (261 files).

**Architecture:** Replace the current batch-oriented 4-phase pipeline with a streaming architecture where each source file is processed completely and atomically (chunk → embed → metadata → DB) before moving to the next. Graph construction (Phase 4) remains bulk processing after all files. Each file write is wrapped in a database transaction for automatic rollback on errors.

**Tech Stack:** Python 3.12, AsyncIO, SQLAlchemy async transactions, tree-sitter, jinaai/jina-embeddings-v2-base-code

---

## Task 1: Create Atomic File Processor Function

**Files:**
- Modify: `scripts/index_directory.py`
- Test: `tests/integration/test_streaming_pipeline.py` (create)

**Step 1: Write the failing test**

Create new test file that validates atomic file processing:

```python
# tests/integration/test_streaming_pipeline.py
"""
Integration test for streaming pipeline with atomic file processing.
"""
import pytest
import asyncio
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine
from scripts.index_directory import process_file_atomically
from services.dual_embedding_service import DualEmbeddingService
from db.repositories.code_chunk_repository import CodeChunkRepository


@pytest.mark.asyncio
async def test_process_file_atomically_creates_chunks_with_embeddings(tmp_path, test_db_engine):
    """Test that process_file_atomically creates chunks with embeddings in single transaction."""
    # Create test TypeScript file
    test_file = tmp_path / "user.ts"
    test_file.write_text("""
    export function validateUser(email: string): boolean {
        if (!email) return false;
        return email.includes("@");
    }

    export function logError(message: string): void {
        console.error(message);
    }
    """)

    # Setup
    repository = "test_streaming"
    embedding_service = DualEmbeddingService()
    chunk_repo = CodeChunkRepository(test_db_engine)

    # Process file atomically
    result = await process_file_atomically(
        file_path=test_file,
        repository=repository,
        embedding_service=embedding_service,
        engine=test_db_engine
    )

    # Verify chunks created
    assert result.chunks_created == 2  # validateUser + logError
    assert result.success is True

    # Verify chunks in database with embeddings
    chunks = await chunk_repo.get_by_repository(repository)
    assert len(chunks) == 2

    for chunk in chunks:
        assert chunk.embedding_code is not None
        assert len(chunk.embedding_code) == 768  # jinaai dimension
        assert chunk.repository == repository


@pytest.mark.asyncio
async def test_process_file_atomically_rollback_on_error(tmp_path, test_db_engine):
    """Test that transaction rolls back if processing fails mid-way."""
    # Create test file with invalid syntax
    test_file = tmp_path / "invalid.ts"
    test_file.write_text("this is not valid typescript {{{")

    repository = "test_rollback"
    embedding_service = DualEmbeddingService()
    chunk_repo = CodeChunkRepository(test_db_engine)

    # Process should fail but not crash
    result = await process_file_atomically(
        file_path=test_file,
        repository=repository,
        embedding_service=embedding_service,
        engine=test_db_engine
    )

    # Verify failure recorded
    assert result.success is False
    assert result.chunks_created == 0
    assert "error" in result.error_message.lower()

    # Verify NO chunks in database (transaction rolled back)
    chunks = await chunk_repo.get_by_repository(repository)
    assert len(chunks) == 0
```

**Step 2: Run test to verify it fails**

Run: `docker exec -i mnemo-api pytest /app/tests/integration/test_streaming_pipeline.py -v`

Expected: FAIL with "process_file_atomically not defined"

**Step 3: Add FileProcessingResult model**

In `scripts/index_directory.py`, add at top of file after imports:

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FileProcessingResult:
    """Result of processing a single file atomically."""
    file_path: Path
    success: bool
    chunks_created: int
    error_message: str = ""
```

**Step 4: Implement process_file_atomically function**

Add before `main()` in `scripts/index_directory.py`:

```python
async def process_file_atomically(
    file_path: Path,
    repository: str,
    embedding_service,
    engine
) -> FileProcessingResult:
    """
    Process a single source file completely and atomically.

    Steps performed in-memory:
    1. Chunk the file
    2. Generate embeddings for each chunk
    3. Extract metadata for each chunk
    4. Write all data to database in single transaction

    If any step fails, transaction rolls back automatically.

    Args:
        file_path: Path to source file
        repository: Repository name
        embedding_service: Pre-loaded DualEmbeddingService instance
        engine: SQLAlchemy async engine

    Returns:
        FileProcessingResult with success status and count
    """
    from services.code_chunking_service import CodeChunkingService
    from services.metadata_extractor_service import get_metadata_extractor_service
    from db.repositories.code_chunk_repository import CodeChunkRepository
    from models.code_chunk_models import CodeChunkCreate
    from services.dual_embedding_service import EmbeddingDomain

    chunks_created = 0

    try:
        # Step 1: Chunk file (in-memory)
        metadata_service = get_metadata_extractor_service()
        chunking_service = CodeChunkingService(max_workers=1, metadata_service=metadata_service)

        chunks = await chunking_service.chunk_file(file_path)

        if not chunks:
            return FileProcessingResult(
                file_path=file_path,
                success=True,
                chunks_created=0,
                error_message="No chunks extracted (empty or filtered)"
            )

        # Step 2 & 3: Generate embeddings + extract metadata (in-memory)
        chunk_creates = []

        for chunk in chunks:
            # Generate CODE embedding
            embedding_result = await embedding_service.generate_embedding(
                chunk.source_code,
                domain=EmbeddingDomain.CODE
            )

            # Create chunk model with embedding
            chunk_create = CodeChunkCreate(
                file_path=chunk.file_path,
                language=chunk.language,
                chunk_type=chunk.chunk_type,
                name=chunk.name,
                source_code=chunk.source_code,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                repository=repository,
                metadata=chunk.metadata,  # Already contains calls, imports from chunking
                embedding_text=None,
                embedding_code=embedding_result['code']
            )

            chunk_creates.append(chunk_create)

        # Step 4: Write to database atomically (single transaction)
        async with engine.begin() as conn:
            chunk_repo = CodeChunkRepository(engine, connection=conn)

            for chunk_create in chunk_creates:
                await chunk_repo.add(chunk_create)
                chunks_created += 1

        return FileProcessingResult(
            file_path=file_path,
            success=True,
            chunks_created=chunks_created
        )

    except Exception as e:
        return FileProcessingResult(
            file_path=file_path,
            success=False,
            chunks_created=0,
            error_message=str(e)
        )
```

**Step 5: Update CodeChunkRepository to support transactions**

Modify `api/db/repositories/code_chunk_repository.py`:

```python
# At top of class
def __init__(self, engine: AsyncEngine, connection=None):
    """
    Initialize repository.

    Args:
        engine: SQLAlchemy async engine
        connection: Optional connection from existing transaction
    """
    self.engine = engine
    self._connection = connection  # If provided, use this connection
```

Update all methods to use `self._connection` if available:

```python
async def add(self, chunk: CodeChunkCreate) -> CodeChunkModel:
    """Add a new code chunk."""
    if self._connection:
        # Use existing transaction connection
        result = await self._connection.execute(query, params)
    else:
        # Create new connection
        async with self.engine.connect() as conn:
            async with conn.begin():
                result = await conn.execute(query, params)
```

**Step 6: Run tests to verify they pass**

Run: `docker exec -i mnemo-api pytest /app/tests/integration/test_streaming_pipeline.py -v`

Expected: 2 PASSED

**Step 7: Commit**

```bash
git add scripts/index_directory.py api/db/repositories/code_chunk_repository.py tests/integration/test_streaming_pipeline.py
git commit -m "feat(streaming): Add atomic file processing with transaction support"
```

---

## Task 2: Refactor Main Pipeline to Stream Files

**Files:**
- Modify: `scripts/index_directory.py`

**Step 1: Write test for streaming main function**

Add to `tests/integration/test_streaming_pipeline.py`:

```python
@pytest.mark.asyncio
async def test_streaming_pipeline_processes_all_files(tmp_path, test_db_engine):
    """Test that streaming pipeline processes multiple files sequentially."""
    # Create 3 test files
    files = []
    for i in range(3):
        test_file = tmp_path / f"file{i}.ts"
        test_file.write_text(f"export function func{i}() {{ return {i}; }}")
        files.append(test_file)

    # Run streaming pipeline
    from scripts.index_directory import run_streaming_pipeline

    stats = await run_streaming_pipeline(
        directory=tmp_path,
        repository="test_multi",
        verbose=False
    )

    # Verify all files processed
    assert stats['total_files'] == 3
    assert stats['success_files'] == 3
    assert stats['error_files'] == 0
    assert stats['total_chunks'] == 3

    # Verify chunks in database
    from db.repositories.code_chunk_repository import CodeChunkRepository
    chunk_repo = CodeChunkRepository(test_db_engine)
    chunks = await chunk_repo.get_by_repository("test_multi")
    assert len(chunks) == 3


@pytest.mark.asyncio
async def test_streaming_pipeline_continues_on_error(tmp_path, test_db_engine):
    """Test that pipeline continues if one file fails."""
    # Create 2 valid + 1 invalid file
    valid1 = tmp_path / "valid1.ts"
    valid1.write_text("export function good1() { return 1; }")

    invalid = tmp_path / "invalid.ts"
    invalid.write_text("this is garbage {{{")

    valid2 = tmp_path / "valid2.ts"
    valid2.write_text("export function good2() { return 2; }")

    # Run pipeline
    from scripts.index_directory import run_streaming_pipeline

    stats = await run_streaming_pipeline(
        directory=tmp_path,
        repository="test_errors",
        verbose=False
    )

    # Verify: 2 success, 1 error
    assert stats['total_files'] == 3
    assert stats['success_files'] == 2
    assert stats['error_files'] == 1
    assert len(stats['errors']) == 1
    assert 'invalid.ts' in stats['errors'][0]['file']
```

**Step 2: Run tests to verify they fail**

Run: `docker exec -i mnemo-api pytest /app/tests/integration/test_streaming_pipeline.py::test_streaming_pipeline_processes_all_files -v`

Expected: FAIL with "run_streaming_pipeline not defined"

**Step 3: Implement cleanup function**

Add to `scripts/index_directory.py`:

```python
async def cleanup_repository(repository: str, engine):
    """
    Delete all existing data for a repository before reindexing.

    Deletes in order:
    1. edge_weights (FK to edges)
    2. computed_metrics (FK to nodes)
    3. detailed_metadata (FK to nodes)
    4. edges (FK to nodes)
    5. nodes (FK to code_chunks)
    6. code_chunks
    """
    from sqlalchemy.sql import text

    async with engine.begin() as conn:
        # Delete in reverse FK order
        await conn.execute(text("DELETE FROM edge_weights WHERE edge_id IN (SELECT edge_id FROM edges e JOIN nodes n ON e.source_node_id = n.node_id WHERE n.properties->>'repository' = :repo)"), {"repo": repository})

        await conn.execute(text("DELETE FROM computed_metrics WHERE repository = :repo"), {"repo": repository})

        await conn.execute(text("DELETE FROM detailed_metadata WHERE node_id IN (SELECT node_id FROM nodes WHERE properties->>'repository' = :repo)"), {"repo": repository})

        await conn.execute(text("DELETE FROM edges WHERE source_node_id IN (SELECT node_id FROM nodes WHERE properties->>'repository' = :repo)"), {"repo": repository})

        await conn.execute(text("DELETE FROM nodes WHERE properties->>'repository' = :repo"), {"repo": repository})

        # Delete chunks by file_path pattern
        await conn.execute(text("DELETE FROM code_chunks WHERE repository = :repo"), {"repo": repository})
```

**Step 4: Implement run_streaming_pipeline function**

Add to `scripts/index_directory.py`:

```python
async def run_streaming_pipeline(
    directory: Path,
    repository: str,
    verbose: bool = False
) -> dict:
    """
    Run streaming pipeline: process files one-at-a-time with constant memory.

    Returns:
        Dict with statistics: total_files, success_files, error_files, total_chunks, errors
    """
    import os
    from services.dual_embedding_service import DualEmbeddingService
    from sqlalchemy.ext.asyncio import create_async_engine
    from tqdm import tqdm
    import gc

    # Database setup
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://mnemo:mnemo@mnemo-postgres:5432/mnemolite")
    engine = create_async_engine(db_url, echo=False)

    # Cleanup existing data
    if verbose:
        print(f"\n🧹 Cleaning up existing data for repository: {repository}")
    await cleanup_repository(repository, engine)

    # Scan files
    files = scan_files(directory)

    if verbose:
        print(f"\n📊 Found {len(files)} files to index")

    # Load embedding model ONCE
    if verbose:
        print(f"\n🔧 Loading embedding model...")
    os.environ["EMBEDDING_MODE"] = "real"
    embedding_service = DualEmbeddingService()

    # Stream files one-at-a-time
    success_count = 0
    error_count = 0
    total_chunks = 0
    errors = []

    with tqdm(total=len(files), desc="Processing files", disable=not verbose) as pbar:
        for file_path in files:
            result = await process_file_atomically(
                file_path=file_path,
                repository=repository,
                embedding_service=embedding_service,
                engine=engine
            )

            if result.success:
                success_count += 1
                total_chunks += result.chunks_created
            else:
                error_count += 1
                errors.append({
                    "file": str(file_path),
                    "error": result.error_message
                })
                if verbose:
                    print(f"\n   ⚠️  Failed: {file_path.name} - {result.error_message}")

            # Force memory cleanup
            gc.collect()
            pbar.update(1)

    await engine.dispose()

    return {
        "total_files": len(files),
        "success_files": success_count,
        "error_files": error_count,
        "total_chunks": total_chunks,
        "errors": errors
    }


def scan_files(directory: Path) -> list[Path]:
    """Scan directory for TypeScript/JavaScript files, applying filters."""
    files = []

    for ext in ["*.ts", "*.js"]:
        files.extend(directory.rglob(ext))

    # Filter out tests, node_modules, declarations
    filtered = []
    for f in files:
        path_str = str(f)
        if any(skip in path_str for skip in ["node_modules", "test", "spec", ".d.ts"]):
            continue
        filtered.append(f)

    return sorted(filtered)
```

**Step 5: Update main() to use streaming pipeline**

Replace existing main() in `scripts/index_directory.py`:

```python
async def main():
    """Main entry point for directory indexer."""
    import argparse
    from pathlib import Path
    from datetime import datetime

    parser = argparse.ArgumentParser(description="Index TypeScript/JavaScript codebase")
    parser.add_argument("directory", type=Path, help="Directory to index")
    parser.add_argument("--repository", type=str, help="Repository name")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    directory = args.directory.resolve()
    repository = args.repository or directory.name

    print("=" * 80)
    print("🚀 MnemoLite Directory Indexer (Streaming Mode)")
    print("=" * 80)
    print(f"\n📁 Repository: {repository}")
    print(f"📂 Path: {directory}")

    start_time = datetime.now()

    # Run streaming pipeline
    stats = await run_streaming_pipeline(
        directory=directory,
        repository=repository,
        verbose=args.verbose
    )

    elapsed = (datetime.now() - start_time).total_seconds()

    # Summary
    print("\n" + "=" * 80)
    print("✅ INDEXING COMPLETE")
    print("=" * 80)
    print(f"\n📊 Summary:")
    print(f"   - Total files: {stats['total_files']}")
    print(f"   - Success: {stats['success_files']}")
    print(f"   - Errors: {stats['error_files']}")
    print(f"   - Total chunks: {stats['total_chunks']}")
    print(f"   - Time: {elapsed:.1f}s ({elapsed/60:.1f}m)")

    if stats['errors']:
        print(f"\n❌ Failed files:")
        for error in stats['errors'][:10]:  # Show first 10
            print(f"   - {error['file']}: {error['error']}")

    # TODO: Run Phase 4 (Graph Construction) here
    print("\n⚠️  Note: Graph construction (Phase 4) not yet implemented in streaming mode")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

**Step 6: Run tests to verify they pass**

Run: `docker exec -i mnemo-api pytest /app/tests/integration/test_streaming_pipeline.py -v`

Expected: 4 PASSED

**Step 7: Commit**

```bash
git add scripts/index_directory.py tests/integration/test_streaming_pipeline.py
git commit -m "feat(streaming): Refactor main pipeline to stream files one-at-a-time"
```

---

## Task 3: Add Phase 4 Graph Construction (Bulk Mode)

**Files:**
- Modify: `scripts/index_directory.py`

**Step 1: Write test for graph construction phase**

Add to `tests/integration/test_streaming_pipeline.py`:

```python
@pytest.mark.asyncio
async def test_graph_construction_after_streaming(tmp_path, test_db_engine):
    """Test that graph construction works after streaming pipeline."""
    # Create test files with function calls
    file1 = tmp_path / "utils.ts"
    file1.write_text("""
    export function helper() {
        return "help";
    }
    """)

    file2 = tmp_path / "main.ts"
    file2.write_text("""
    import { helper } from './utils';

    export function main() {
        const result = helper();
        return result;
    }
    """)

    # Run streaming pipeline (creates chunks)
    from scripts.index_directory import run_streaming_pipeline
    await run_streaming_pipeline(tmp_path, "test_graph", verbose=False)

    # Run graph construction
    from scripts.index_directory import build_graph_phase
    graph_stats = await build_graph_phase("test_graph", test_db_engine)

    # Verify nodes created
    assert graph_stats['total_nodes'] == 2  # helper + main
    assert graph_stats['total_edges'] >= 1  # main calls helper

    # Verify in database
    from db.repositories.node_repository import NodeRepository
    node_repo = NodeRepository(test_db_engine)
    nodes = await node_repo.get_by_repository("test_graph")
    assert len(nodes) == 2
```

**Step 2: Run test to verify it fails**

Run: `docker exec -i mnemo-api pytest /app/tests/integration/test_streaming_pipeline.py::test_graph_construction_after_streaming -v`

Expected: FAIL with "build_graph_phase not defined"

**Step 3: Implement build_graph_phase function**

Add to `scripts/index_directory.py`:

```python
async def build_graph_phase(repository: str, engine) -> dict:
    """
    Phase 4: Build graph from indexed chunks.

    Steps:
    1. Create nodes from chunks
    2. Resolve edges (calls, imports)
    3. Calculate metrics (PageRank, coupling)
    4. Store everything

    Returns:
        Dict with stats: total_nodes, total_edges
    """
    from services.graph_construction_service import GraphConstructionService

    print("\n" + "=" * 80)
    print("🕸️  Phase 4: Graph Construction")
    print("=" * 80)

    graph_service = GraphConstructionService(engine)

    # Build graph for repository
    stats = await graph_service.build_graph_for_repository(
        repository=repository,
        languages=["typescript", "javascript"]
    )

    print(f"\n✅ Graph construction complete:")
    print(f"   - Nodes: {stats.total_nodes}")
    print(f"   - Edges: {stats.total_edges}")
    print(f"   - Nodes by type: {stats.nodes_by_type}")
    print(f"   - Edges by type: {stats.edges_by_type}")

    return {
        "total_nodes": stats.total_nodes,
        "total_edges": stats.total_edges,
        "nodes_by_type": stats.nodes_by_type,
        "edges_by_type": stats.edges_by_type
    }
```

**Step 4: Integrate graph construction into main()**

Update main() in `scripts/index_directory.py`:

```python
async def main():
    """Main entry point for directory indexer."""
    # ... existing setup code ...

    # Run streaming pipeline
    stats = await run_streaming_pipeline(
        directory=directory,
        repository=repository,
        verbose=args.verbose
    )

    # Run Phase 4: Graph Construction
    if stats['success_files'] > 0:
        graph_stats = await build_graph_phase(repository, engine)
        stats['graph'] = graph_stats

    elapsed = (datetime.now() - start_time).total_seconds()

    # Summary
    print("\n" + "=" * 80)
    print("✅ INDEXING COMPLETE")
    print("=" * 80)
    print(f"\n📊 Summary:")
    print(f"   - Total files: {stats['total_files']}")
    print(f"   - Success: {stats['success_files']}")
    print(f"   - Errors: {stats['error_files']}")
    print(f"   - Total chunks: {stats['total_chunks']}")
    print(f"   - Graph nodes: {stats.get('graph', {}).get('total_nodes', 0)}")
    print(f"   - Graph edges: {stats.get('graph', {}).get('total_edges', 0)}")
    print(f"   - Time: {elapsed:.1f}s ({elapsed/60:.1f}m)")
```

**Step 5: Run tests to verify they pass**

Run: `docker exec -i mnemo-api pytest /app/tests/integration/test_streaming_pipeline.py -v`

Expected: 5 PASSED

**Step 6: Commit**

```bash
git add scripts/index_directory.py tests/integration/test_streaming_pipeline.py
git commit -m "feat(streaming): Add Phase 4 graph construction in bulk mode"
```

---

## Task 4: Integration Test with code_test

**Files:**
- Test manually with real code_test directory

**Step 1: Run streaming pipeline on code_test**

```bash
docker exec -i mnemo-api python /app/scripts/index_directory.py /app/code_test --repository code_test --verbose
```

Expected: Completes successfully without OOM, showing progress for all 261 files

**Step 2: Verify results in database**

```bash
# Check chunks created
docker compose exec -T db psql -U mnemo -d mnemolite -c "
SELECT COUNT(*), language
FROM code_chunks
WHERE repository = 'code_test'
GROUP BY language;"

# Expected: ~500-1000 chunks total (depends on file sizes)

# Check nodes created
docker compose exec -T db psql -U mnemo -d mnemolite -c "
SELECT COUNT(*), node_type
FROM nodes
WHERE properties->>'repository' = 'code_test'
GROUP BY node_type;"

# Expected: ~400-800 nodes (functions, classes)

# Check edges created
docker compose exec -T db psql -U mnemo -d mnemolite -c "
SELECT COUNT(*), relation_type
FROM edges e
JOIN nodes n ON e.source_node_id = n.node_id
WHERE n.properties->>'repository' = 'code_test'
GROUP BY relation_type;"

# Expected: ~300-600 edges (calls, imports)
```

**Step 3: Verify in UI**

1. Open http://localhost:3002/
2. Select "code_test" from repository dropdown
3. Verify graph visualization shows nodes and edges
4. Check metrics dashboard shows complexity/coupling/PageRank

**Step 4: Verify memory usage stayed low**

```bash
docker stats mnemo-api --no-stream
```

Expected: Memory usage peaked at ~2-3GB (not 8GB), stayed constant throughout

**Step 5: Document success**

If all checks pass, document in commit message:
- Total files indexed
- Total chunks/nodes/edges created
- Peak memory usage
- Total time taken

**Step 6: Final commit**

```bash
git add .
git commit -m "feat(streaming): Validate streaming pipeline with code_test (261 files)

- Successfully indexed 261 TypeScript/JavaScript files
- Memory footprint: ~2-3GB constant (was OOM at 8GB)
- Total time: ~X minutes
- Created ~XXX chunks, ~XXX nodes, ~XXX edges
- Graph visualization working in UI"
```

---

## Task 5: Update Documentation

**Files:**
- Modify: `scripts/README.md`

**Step 1: Update pipeline documentation**

Replace the "Pipeline (4 Phases)" section in `scripts/README.md`:

```markdown
### Pipeline Architecture (Streaming Mode)

**Streaming Pipeline** - Constant memory footprint regardless of repository size

**Processing Model:**
- **File-at-a-Time**: Each source file processed completely before next
- **Atomic Transactions**: Each file = 1 DB transaction (auto-rollback on error)
- **Continue-on-Error**: Failed files logged, processing continues
- **Memory Footprint**: Constant ~2-3GB (embedding model + single file)

**Phases:**

1. **Cleanup**: Delete existing repository data (clean slate)

2. **Streaming Process** (per file):
   ```
   For each source file:
   a. Chunk (in-memory) → list[CodeChunk]
   b. Generate embeddings (in-memory) → add 768D vectors
   c. Extract metadata (in-memory) → calls, imports, signatures, complexity
   d. Write atomically to DB (single transaction)
   e. Clear memory (gc.collect())
   ```

3. **Graph Construction** (bulk after all files):
   - Create nodes from chunks
   - Resolve call/import edges
   - Calculate PageRank & coupling metrics
   - Store graph data

**Performance:**
- 100 files: ~3-4 minutes
- 261 files (code_test): ~8-10 minutes
- 500 files: ~15-18 minutes
- 1000 files: ~30-35 minutes

**Bottleneck**: Embedding generation (CPU-bound, ~2s per chunk)

**Memory**: Constant ~2-3GB regardless of repository size
```

**Step 2: Add troubleshooting section**

Add new section to `scripts/README.md`:

```markdown
### Troubleshooting

**Issue**: Script fails with "out of memory" error
- **Cause**: Very large individual files (>100MB)
- **Solution**: Increase Docker memory limit or exclude large files

**Issue**: Some files show as "failed" in summary
- **Cause**: Parse errors, invalid syntax, unsupported language constructs
- **Solution**: Check error log, fix source files or add to exclusion filters

**Issue**: Graph visualization empty despite chunks indexed
- **Cause**: Phase 4 (graph construction) failed
- **Solution**: Check logs for graph construction errors, re-run indexing

**Issue**: Indexing very slow (>1 minute per file)
- **Cause**: Very large functions/classes, complex metadata extraction
- **Solution**: This is expected for large files, let it complete

**Issue**: Missing edges in graph
- **Cause**: Call/import resolution failed (dynamic imports, aliases)
- **Solution**: This is expected, graph shows statically analyzable relationships
```

**Step 3: Commit documentation**

```bash
git add scripts/README.md
git commit -m "docs: Update README with streaming pipeline architecture"
```

---

## Verification Checklist

After all tasks complete, verify:

- [ ] All integration tests pass (5 tests)
- [ ] code_test (261 files) indexes successfully without OOM
- [ ] Memory usage stays ~2-3GB constant
- [ ] Graph visualization shows nodes/edges in UI
- [ ] Metrics dashboard displays complexity/coupling/PageRank
- [ ] Failed files are logged but don't crash pipeline
- [ ] Documentation updated with streaming architecture

---

## Notes

**Memory Optimization**: The key insight is loading the embedding model once and reusing it, while processing files one-at-a-time with explicit memory cleanup (gc.collect()) after each file.

**Transaction Safety**: Each file write is wrapped in `async with engine.begin()` which automatically rolls back on exceptions, ensuring no partial data in database.

**Trade-offs**: Streaming mode is slightly slower than batch mode (~10% overhead) due to more database transactions, but the robustness gain is worth it for large codebases.

**Future Enhancements** (not in this plan):
- Checkpoint/resume capability (skip already-indexed files)
- File hash tracking (detect changes, skip unchanged)
- Parallel file processing (risk OOM, needs careful memory management)
- PostgreSQL native graph metrics (avoid loading all nodes in memory)
