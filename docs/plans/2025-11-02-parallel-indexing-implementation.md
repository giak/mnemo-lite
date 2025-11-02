# Parallel Indexing Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform sequential indexing pipeline into parallel multi-worker architecture using Joblib to achieve 100% completion (261/261 files) with 2-4× performance improvement.

**Architecture:** Replace sequential file-at-a-time processing with Joblib parallel workers. Each worker runs in isolated process with own embedding model and DB connection. Workers process files concurrently, maintaining atomic transactions per file.

**Tech Stack:** Joblib 1.3+, SQLAlchemy async, PostgreSQL, jinaai/jina-embeddings-v2-base-code

---

## Task 1: Add Joblib Dependency

**Files:**
- Modify: `requirements.txt`

**Step 1.1: Add Joblib to requirements**

Add to `requirements.txt`:
```
joblib>=1.3.0
```

**Step 1.2: Rebuild Docker image**

Run:
```bash
docker compose build api
```

Expected: Build succeeds, joblib installed

**Step 1.3: Verify Joblib available**

Run:
```bash
docker exec -i mnemo-api python -c "import joblib; print(joblib.__version__)"
```

Expected: Prints version `1.3.0` or higher

**Step 1.4: Commit**

```bash
git add requirements.txt
git commit -m "deps: add joblib for parallel indexing"
```

---

## Task 2: Increase Docker Memory Limit

**Files:**
- Modify: `docker-compose.yml`

**Step 2.1: Update memory limits**

In `docker-compose.yml`, find the `api` service and modify:

```yaml
services:
  api:
    image: mnemo-api
    container_name: mnemo-api
    deploy:
      resources:
        limits:
          memory: 16G  # Changed from 8G
        reservations:
          memory: 12G  # Changed from 4G
```

**Step 2.2: Restart Docker services**

Run:
```bash
docker compose down
docker compose up -d
```

Expected: Services restart successfully

**Step 2.3: Verify memory limit**

Run:
```bash
docker inspect mnemo-api | grep -A 5 Memory
```

Expected: Shows `"Memory": 17179869184` (16GB in bytes)

**Step 2.4: Commit**

```bash
git add docker-compose.yml
git commit -m "config: increase Docker memory to 16GB for parallel indexing"
```

---

## Task 3: Create Worker Function

**Files:**
- Modify: `scripts/index_directory.py`

**Step 3.1: Add worker function before `run_streaming_pipeline`**

Insert this function in `scripts/index_directory.py` at the **top level** (after imports, before any async functions):

```python
def worker_process_file(file_path: Path, repository: str, db_url: str) -> FileProcessingResult:
    """
    Worker function for Joblib - processes 1 file atomically.
    Each worker loads its own embedding model and creates DB connection.

    IMPORTANT: Must be top-level function (required by multiprocessing).

    Args:
        file_path: Path to source file
        repository: Repository name
        db_url: Database connection URL

    Returns:
        FileProcessingResult with success status and chunk count
    """
    import os
    import gc
    from sqlalchemy.ext.asyncio import create_async_engine
    import asyncio

    # Set embedding mode for this worker
    os.environ["EMBEDDING_MODE"] = "real"

    # Create worker-specific resources (NOT shared between workers)
    embedding_service = DualEmbeddingService()
    engine = create_async_engine(db_url, echo=False, pool_size=2, max_overflow=0)

    try:
        # Run async processing
        result = asyncio.run(process_file_atomically(
            file_path, repository, embedding_service, engine
        ))
    except Exception as e:
        # Catch any unhandled errors
        result = FileProcessingResult(
            file_path=file_path,
            success=False,
            chunks_created=0,
            error_message=str(e)
        )
    finally:
        # Cleanup resources
        try:
            asyncio.run(engine.dispose())
        except:
            pass
        del embedding_service
        gc.collect()

    return result
```

**Step 3.2: Verify function is at module level**

Check that `worker_process_file` is:
- NOT inside any class
- NOT inside any other function
- At the same indentation level as imports

**Step 3.3: Test imports**

Run:
```bash
docker exec -i mnemo-api python -c "from scripts.index_directory import worker_process_file; print('OK')"
```

Expected: Prints `OK`

---

## Task 4: Create Parallel Pipeline Function

**Files:**
- Modify: `scripts/index_directory.py`

**Step 4.1: Rename existing function**

Rename `run_streaming_pipeline` to `run_streaming_pipeline_sequential`:

```python
async def run_streaming_pipeline_sequential(
    directory: Path,
    repository: str,
    verbose: bool = False,
    engine: AsyncEngine = None
) -> dict:
    # ... existing code unchanged ...
```

**Step 4.2: Create new parallel pipeline function**

Add new function after `run_streaming_pipeline_sequential`:

```python
async def run_parallel_pipeline(
    directory: Path,
    repository: str,
    n_jobs: int = 4,
    verbose: bool = False,
    engine: AsyncEngine = None
) -> dict:
    """
    Run parallel indexing pipeline with Joblib.

    Args:
        directory: Path to codebase
        repository: Repository name
        n_jobs: Number of parallel workers (default: 4)
        verbose: Enable detailed logging
        engine: Optional pre-created engine for cleanup phase

    Returns:
        dict with stats: total_files, success_files, error_files, total_chunks, errors
    """
    # Create engine if not provided
    if not engine:
        db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://mnemo:mnemo@mnemo-postgres:5432/mnemolite")
        engine = create_async_engine(db_url, echo=False)
        should_dispose = True
    else:
        should_dispose = False

    # Phase 1: Cleanup (sequential)
    print("\n" + "=" * 80)
    print("🧹 Phase 1/3: Cleanup")
    print("=" * 80)
    await cleanup_repository(repository, engine)

    # Phase 2: Scan files
    print("\n" + "=" * 80)
    print("🔍 Phase 2/3: Scanning Files")
    print("=" * 80)
    files = scan_files(directory)
    print(f"📊 Found {len(files)} files to index")

    # Phase 3: Parallel processing with Joblib
    print("\n" + "=" * 80)
    print(f"⚡ Phase 3/3: Parallel Processing ({n_jobs} workers)")
    print("=" * 80)

    from joblib import Parallel, delayed

    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://mnemo:mnemo@mnemo-postgres:5432/mnemolite")

    print(f"🔧 Starting {n_jobs} parallel workers...")
    print(f"📈 Each worker will load its own embedding model (~2GB)")
    print(f"💾 Expected memory usage: ~{n_jobs * 3}GB")
    print()

    # Execute parallel processing
    results = Parallel(n_jobs=n_jobs, verbose=10 if verbose else 0)(
        delayed(worker_process_file)(file_path, repository, db_url)
        for file_path in files
    )

    # Aggregate results
    success_count = sum(1 for r in results if r.success)
    error_count = len(results) - success_count
    total_chunks = sum(r.chunks_created for r in results)
    errors = [
        {"file": str(r.file_path), "error": r.error_message}
        for r in results if not r.success
    ]

    # Cleanup engine if we created it
    if should_dispose:
        await engine.dispose()

    return {
        "total_files": len(files),
        "success_files": success_count,
        "error_files": error_count,
        "total_chunks": total_chunks,
        "errors": errors
    }
```

**Step 4.3: Verify syntax**

Run:
```bash
docker exec -i mnemo-api python -m py_compile /app/scripts/index_directory.py
```

Expected: No errors

---

## Task 5: Update Main Entry Point

**Files:**
- Modify: `scripts/index_directory.py`

**Step 5.1: Update argument parser**

In the `main()` function, update `argparse` section:

```python
async def main():
    """Main entry point - parallel mode by default."""
    parser = argparse.ArgumentParser(
        description="Index TypeScript/JavaScript codebase with parallel processing"
    )
    parser.add_argument("directory", type=Path, help="Path to codebase")
    parser.add_argument("--repository", type=str, help="Repository name (default: directory name)")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers (default: 4)")
    parser.add_argument("--sequential", action="store_true", help="Use sequential mode instead of parallel")
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging")

    args = parser.parse_args()
```

**Step 5.2: Update main pipeline call**

Replace the `run_streaming_pipeline` call with:

```python
    # Create engine for cleanup and graph phases
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://mnemo:mnemo@mnemo-postgres:5432/mnemolite")
    engine = create_async_engine(db_url, echo=False)

    # Run pipeline (parallel by default, sequential if --sequential flag)
    if args.sequential:
        print("🐌 Running in SEQUENTIAL mode")
        stats = await run_streaming_pipeline_sequential(
            directory, repository, verbose=args.verbose, engine=engine
        )
    else:
        print(f"⚡ Running in PARALLEL mode with {args.workers} workers")
        stats = await run_parallel_pipeline(
            directory, repository, n_jobs=args.workers, verbose=args.verbose, engine=engine
        )
```

**Step 5.3: Update summary output**

Update the summary print section:

```python
    # Print summary
    print("\n" + "=" * 80)
    print("✅ INDEXING COMPLETE")
    print("=" * 80)
    print(f"   - Total files: {stats['total_files']}")
    print(f"   - Success: {stats['success_files']} ({stats['success_files']*100//stats['total_files']}%)")
    print(f"   - Errors: {stats['error_files']}")
    print(f"   - Total chunks: {stats['total_chunks']}")
    if 'graph' in stats:
        print(f"   - Graph nodes: {stats['graph'].get('total_nodes', 0)}")
        print(f"   - Graph edges: {stats['graph'].get('total_edges', 0)}")

    if stats['errors']:
        print(f"\n❌ Failed files ({len(stats['errors'])}):")
        for error in stats['errors'][:10]:  # Show first 10
            print(f"   - {error['file']}")
            print(f"     Error: {error['error'][:100]}")  # Truncate long errors
```

**Step 5.4: Verify syntax**

Run:
```bash
docker exec -i mnemo-api python -m py_compile /app/scripts/index_directory.py
```

Expected: No errors

**Step 5.5: Commit**

```bash
git add scripts/index_directory.py
git commit -m "feat: add parallel indexing pipeline with Joblib"
```

---

## Task 6: Write Unit Tests

**Files:**
- Create: `tests/integration/test_parallel_pipeline.py`

**Step 6.1: Write test for worker isolation**

Create `tests/integration/test_parallel_pipeline.py`:

```python
"""
Integration tests for parallel indexing pipeline.
"""
import pytest
from pathlib import Path
from scripts.index_directory import run_parallel_pipeline, cleanup_repository
from db.repositories.code_chunk_repository import CodeChunkRepository


@pytest.fixture
async def clean_db(db_engine):
    """Clean database before each test."""
    await cleanup_repository("test_parallel", db_engine)
    yield db_engine
    await cleanup_repository("test_parallel", db_engine)


@pytest.mark.asyncio
async def test_worker_isolation_no_shared_memory_leak(tmp_path, clean_db):
    """
    Verify workers are isolated (no shared memory leak).
    Each worker processes files independently without affecting others.
    """
    # Create 10 test files
    for i in range(10):
        file_path = tmp_path / f"file{i}.ts"
        file_path.write_text(f"export function func{i}() {{ return {i}; }}")

    # Run with 2 workers
    stats = await run_parallel_pipeline(
        tmp_path,
        "test_parallel",
        n_jobs=2,
        verbose=False,
        engine=clean_db
    )

    # Verify all files processed
    assert stats['total_files'] == 10
    assert stats['success_files'] == 10
    assert stats['error_files'] == 0
    assert stats['total_chunks'] == 10

    # Verify chunks in database
    chunk_repo = CodeChunkRepository(clean_db)
    chunks = await chunk_repo.get_by_repository("test_parallel")
    assert len(chunks) == 10


@pytest.mark.asyncio
async def test_parallel_pipeline_handles_errors_gracefully(tmp_path, clean_db):
    """
    Verify continue-on-error with parallel workers.
    Invalid files should fail without crashing other workers.
    """
    # Create 2 valid files + 1 invalid file
    (tmp_path / "valid1.ts").write_text("export function f1() { return 1; }")
    (tmp_path / "invalid.ts").write_text("!!!INVALID SYNTAX!!!")
    (tmp_path / "valid2.ts").write_text("export function f2() { return 2; }")

    # Run with 2 workers
    stats = await run_parallel_pipeline(
        tmp_path,
        "test_parallel",
        n_jobs=2,
        verbose=False,
        engine=clean_db
    )

    # Verify continue-on-error behavior
    assert stats['total_files'] == 3
    assert stats['success_files'] >= 2  # At least 2 valid files
    assert len(stats['errors']) <= 1    # Max 1 error

    # Verify valid files indexed
    chunk_repo = CodeChunkRepository(clean_db)
    chunks = await chunk_repo.get_by_repository("test_parallel")
    assert len(chunks) >= 2


@pytest.mark.asyncio
async def test_parallel_with_single_worker_matches_sequential(tmp_path, clean_db):
    """
    Verify n_jobs=1 produces identical results to sequential mode.
    """
    # Create test files
    for i in range(5):
        (tmp_path / f"file{i}.ts").write_text(f"export function func{i}() {{ return {i}; }}")

    # Run with 1 worker (should behave like sequential)
    stats = await run_parallel_pipeline(
        tmp_path,
        "test_parallel",
        n_jobs=1,
        verbose=False,
        engine=clean_db
    )

    # Verify results
    assert stats['total_files'] == 5
    assert stats['success_files'] == 5
    assert stats['total_chunks'] == 5

    # Verify chunks
    chunk_repo = CodeChunkRepository(clean_db)
    chunks = await chunk_repo.get_by_repository("test_parallel")
    assert len(chunks) == 5

    # Each chunk should have embedding
    for chunk in chunks:
        assert chunk.embedding_code is not None
        assert len(chunk.embedding_code) == 768


@pytest.mark.asyncio
async def test_parallel_pipeline_empty_directory(tmp_path, clean_db):
    """
    Verify graceful handling of empty directories.
    """
    # Create empty directory
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    stats = await run_parallel_pipeline(
        empty_dir,
        "test_parallel",
        n_jobs=2,
        verbose=False,
        engine=clean_db
    )

    # Verify empty results
    assert stats['total_files'] == 0
    assert stats['success_files'] == 0
    assert stats['total_chunks'] == 0
```

**Step 6.2: Run tests to verify they fail**

Run:
```bash
docker exec -i mnemo-api pytest tests/integration/test_parallel_pipeline.py -v
```

Expected: Tests fail (functions not fully implemented yet)

**Step 6.3: Commit tests**

```bash
git add tests/integration/test_parallel_pipeline.py
git commit -m "test: add parallel pipeline integration tests"
```

---

## Task 7: Run Integration Test with code_test

**Files:**
- None (testing only)

**Step 7.1: Clear existing code_test data**

Run:
```bash
docker exec -i mnemo-api psql -U mnemo -d mnemolite -c "
DELETE FROM edge_weights WHERE edge_id IN (SELECT edge_id FROM edges WHERE source_node_id IN (SELECT node_id FROM nodes WHERE properties->>'repository' = 'code_test'));
DELETE FROM computed_metrics WHERE repository = 'code_test';
DELETE FROM detailed_metadata WHERE chunk_id IN (SELECT chunk_id FROM code_chunks WHERE repository = 'code_test');
DELETE FROM edges WHERE source_node_id IN (SELECT node_id FROM nodes WHERE properties->>'repository' = 'code_test');
DELETE FROM nodes WHERE properties->>'repository' = 'code_test';
DELETE FROM code_chunks WHERE repository = 'code_test';
"
```

Expected: Rows deleted

**Step 7.2: Run parallel indexing with 4 workers**

Run:
```bash
time docker exec -i mnemo-api python /app/scripts/index_directory.py \
  /app/code_test \
  --repository code_test \
  --workers 4 \
  --verbose
```

Expected output:
```
⚡ Running in PARALLEL mode with 4 workers

================================================================================
🧹 Phase 1/3: Cleanup
================================================================================

================================================================================
🔍 Phase 2/3: Scanning Files
================================================================================
📊 Found 261 files to index

================================================================================
⚡ Phase 3/3: Parallel Processing (4 workers)
================================================================================
🔧 Starting 4 parallel workers...
📈 Each worker will load its own embedding model (~2GB)
💾 Expected memory usage: ~12GB

[Parallel processing output...]

================================================================================
✅ INDEXING COMPLETE
================================================================================
   - Total files: 261
   - Success: 261 (100%)
   - Errors: 0
   - Total chunks: ~1,847
   - Graph nodes: ~500
   - Graph edges: ~800

real    4m32s
```

**Step 7.3: Verify 100% completion**

Run:
```bash
docker exec -i mnemo-api psql -U mnemo -d mnemolite -c "
SELECT COUNT(*) as total_chunks FROM code_chunks WHERE repository = 'code_test';
SELECT COUNT(*) as total_nodes FROM nodes WHERE properties->>'repository' = 'code_test';
SELECT COUNT(*) as total_edges FROM edges WHERE source_node_id IN (SELECT node_id FROM nodes WHERE properties->>'repository' = 'code_test');
"
```

Expected:
- total_chunks: ~1,847
- total_nodes: >0
- total_edges: >0

**Step 7.4: Monitor memory during execution**

In separate terminal:
```bash
docker stats mnemo-api --format "table {{.MemUsage}}\t{{.MemPerc}}"
```

Expected: Memory stays around 12GB, never reaches 16GB limit

**Step 7.5: Document results**

Create file `docs/benchmarks/2025-11-02-parallel-pipeline-results.md`:

```markdown
# Parallel Pipeline Benchmark Results

**Date:** 2025-11-02
**Test:** code_test (261 TypeScript/JavaScript files)
**Workers:** 4
**Docker Memory:** 16GB

## Results

- **Completion:** 261/261 files (100%) ✅
- **Time:** [ACTUAL TIME]
- **Chunks Created:** [ACTUAL COUNT]
- **Graph Nodes:** [ACTUAL COUNT]
- **Graph Edges:** [ACTUAL COUNT]
- **Peak Memory:** [ACTUAL PEAK]

## Comparison to Baseline

| Metric | Baseline (Sequential) | Parallel (4 workers) | Improvement |
|--------|----------------------|---------------------|-------------|
| Completion | 196/261 (75%) | 261/261 (100%) | +33% |
| Time | ~10-15min (partial) | [ACTUAL] | [ACTUAL]× |
| Memory | OOM at 75% | [ACTUAL] stable | ✅ |

## Notes

[Any observations, issues, or anomalies]
```

**Step 7.6: Commit results**

```bash
git add docs/benchmarks/2025-11-02-parallel-pipeline-results.md
git commit -m "docs: add parallel pipeline benchmark results"
```

---

## Task 8: Update Documentation

**Files:**
- Modify: `scripts/README.md`

**Step 8.1: Add Parallel Mode section**

In `scripts/README.md`, add new section after "### Pipeline Architecture (Streaming Mode)":

```markdown
### Parallel Processing Mode (NEW)

**Available since:** 2025-11-02

The indexing script now supports parallel processing with multiple workers for improved performance and 100% completion on large repositories.

**Usage:**

```bash
# Default: 4 workers
docker exec -i mnemo-api python /app/scripts/index_directory.py \
  /app/code_test \
  --repository code_test \
  --verbose

# Custom worker count
docker exec -i mnemo-api python /app/scripts/index_directory.py \
  /app/code_test \
  --repository code_test \
  --workers 6

# Sequential mode (old behavior)
docker exec -i mnemo-api python /app/scripts/index_directory.py \
  /app/code_test \
  --repository code_test \
  --sequential
```

**Architecture:**

- **Isolation:** Each worker = separate Python process with own embedding model and DB connection
- **Parallelization:** Files distributed automatically by Joblib across workers
- **Memory:** ~3GB per worker (2GB model + 1GB processing)
- **Recommended:** 4 workers for 12-16GB Docker memory

**Performance:**

| Workers | Memory | Time (261 files) | Completion |
|---------|--------|-----------------|------------|
| 1 (sequential) | ~3GB | ~10-15min | 75% (OOM) |
| 2 | ~6GB | ~5-7min | 100% ✅ |
| 4 | ~12GB | ~4-5min | 100% ✅ |
| 6 | ~18GB | ~3-4min | 100% ✅ |

**Requirements:**

- Docker memory: Minimum 16GB for 4 workers
- PostgreSQL: max_connections ≥ 20 (for worker connection pools)
- Joblib: ≥1.3.0
```

**Step 8.2: Update Troubleshooting section**

Add new troubleshooting item:

```markdown
**Issue**: Parallel indexing slower than expected or workers idle

- **Cause**: Insufficient CPU cores, or workers waiting on DB locks
- **Solution**:
  - Check CPU usage: `docker stats mnemo-api`
  - Reduce worker count if CPU maxed out
  - Check PostgreSQL connection count: `SELECT count(*) FROM pg_stat_activity;`
  - Increase `max_connections` in postgresql.conf if needed

**Issue**: "too many clients already" error

- **Cause**: PostgreSQL max_connections exceeded by worker pools
- **Solution**:
  - Reduce worker count: `--workers 2`
  - Or increase max_connections in PostgreSQL config
  - Each worker creates ~2 connections (pool_size=2)
```

**Step 8.3: Commit documentation**

```bash
git add scripts/README.md
git commit -m "docs: add parallel processing mode documentation"
```

---

## Task 9: Final Verification

**Files:**
- None (testing only)

**Step 9.1: Run full test suite**

Run:
```bash
docker exec -i mnemo-api pytest tests/integration/test_parallel_pipeline.py -v
```

Expected: All tests PASS

**Step 9.2: Run sequential mode to verify backward compatibility**

Run:
```bash
docker exec -i mnemo-api python /app/scripts/index_directory.py \
  /app/code_test \
  --repository code_test_sequential \
  --sequential \
  --verbose
```

Expected: Completes (may OOM at 75%, but that's expected for sequential mode)

**Step 9.3: Verify Docker memory can be reduced for sequential**

Update docker-compose.yml temporarily:

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          memory: 8G
```

Run sequential mode again, verify it works (up to OOM at 75%)

Revert back to 16G for parallel mode.

**Step 9.4: Check for any uncommitted changes**

Run:
```bash
git status
```

Expected: "working tree clean" or only expected files

**Step 9.5: Push all commits**

Run:
```bash
git log --oneline -10  # Review last 10 commits
git push origin HEAD
```

Expected: All commits pushed successfully

---

## Success Criteria Checklist

After completing all tasks, verify:

✅ **Must Have:**
- [ ] Joblib installed and working
- [ ] Docker memory increased to 16GB
- [ ] Parallel pipeline processes 261/261 files (100%)
- [ ] No OOM errors during full indexing
- [ ] All integration tests pass
- [ ] Graph construction works after parallel indexing
- [ ] Sequential mode still works (backward compatibility)

✅ **Performance:**
- [ ] Parallel mode completes in <6 minutes (4 workers)
- [ ] Memory usage stable around 12GB
- [ ] 2-4× faster than baseline sequential

✅ **Quality:**
- [ ] All code committed with clear messages
- [ ] Documentation updated
- [ ] Benchmark results documented
- [ ] No regression in existing functionality

---

## Rollback Plan

If parallel mode has critical issues:

1. Revert to sequential mode default:
   ```bash
   git revert <commit-hash-of-parallel-feature>
   ```

2. Or use `--sequential` flag:
   ```bash
   docker exec -i mnemo-api python /app/scripts/index_directory.py \
     /app/code_test \
     --repository code_test \
     --sequential
   ```

3. Reduce Docker memory back to 8GB if needed:
   ```yaml
   memory: 8G
   ```

---

## Related Documents

- Design: `docs/plans/2025-11-02-parallel-indexing-joblib.md`
- Baseline: `docs/plans/2025-11-02-streaming-pipeline-oom-fix.md`
- Joblib Docs: https://joblib.readthedocs.io/en/latest/parallel.html
