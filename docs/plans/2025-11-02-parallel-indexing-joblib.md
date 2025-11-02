# Parallel Indexing Pipeline with Joblib

**Date:** 2025-11-02
**Status:** Design Approved
**Goal:** Achieve 100% completion (261/261 files) + 2-4× performance improvement

---

## Problem Statement

**Current State (Streaming Pipeline):**
- Processes files sequentially (1 at a time)
- Achieves 75% completion (196/261 files) before OOM
- Memory: ~738MB constant, but accumulates over time
- Estimated time: ~10-15 minutes for partial completion
- Suspected memory leak in embedding model (transformers)

**Requirements:**
- **Primary:** 100% completion without OOM
- **Secondary:** Improve performance (reduce total indexing time)

---

## Solution Overview

**Parallel Pipeline with Joblib** - Transform sequential pipeline into parallel multi-worker architecture.

### Key Decisions

| Aspect | Choice | Rationale |
|--------|--------|-----------|
| **Parallelization Library** | Joblib | Simple, mature, built for data science workflows |
| **Embedding Strategy** | 1 model per worker | Isolation guarantees no shared memory leaks |
| **Worker Count** | 4 workers | Optimal for 12-16GB RAM (4 × 3GB = 12GB) |
| **Batching Strategy** | File-at-a-time | Automatic load balancing, simplest code |
| **DB Connections** | Independent per worker | PostgreSQL handles concurrency well |
| **Error Handling** | Continue-on-error | Preserve robustness, collect errors at end |

---

## Architecture

### High-Level Flow

```
Main Process
    ├─ Phase 1: Cleanup (sequential)
    │   └─ Delete existing repository data
    │
    ├─ Phase 2: Parallel Processing (Joblib)
    │   ├─ Worker 1 [Embedding Model + DB Connection]
    │   │   └─ process_file_atomically(file_1, file_5, file_9, ...)
    │   ├─ Worker 2 [Embedding Model + DB Connection]
    │   │   └─ process_file_atomically(file_2, file_6, file_10, ...)
    │   ├─ Worker 3 [Embedding Model + DB Connection]
    │   │   └─ process_file_atomically(file_3, file_7, file_11, ...)
    │   └─ Worker 4 [Embedding Model + DB Connection]
    │       └─ process_file_atomically(file_4, file_8, file_12, ...)
    │
    └─ Phase 3: Graph Construction (sequential)
        └─ Build nodes, edges, compute metrics
```

### Worker Architecture

Each worker is a **separate Python process** with:
- Own embedding model instance (~2GB)
- Own SQLAlchemy async engine + connection pool
- Own memory space (no shared state)
- Processes files assigned by Joblib scheduler

**Benefits of Isolation:**
- Memory leaks in one worker don't affect others
- Workers can be killed/restarted independently
- No lock contention on shared resources

---

## Implementation Details

### 1. New Worker Function

```python
def worker_process_file(file_path: Path, repository: str, db_url: str) -> FileProcessingResult:
    """
    Worker function for Joblib - processes 1 file atomically.
    Each worker loads its own embedding model and creates DB connection.

    IMPORTANT: Must be top-level function (required by multiprocessing).
    """
    import os
    import gc
    from sqlalchemy.ext.asyncio import create_async_engine
    import asyncio

    # Set embedding mode
    os.environ["EMBEDDING_MODE"] = "real"

    # Create worker-specific resources (NOT shared)
    embedding_service = DualEmbeddingService()  # Each worker loads its own model
    engine = create_async_engine(db_url, echo=False)

    try:
        # Run async processing
        result = asyncio.run(process_file_atomically(
            file_path, repository, embedding_service, engine
        ))
    finally:
        # Cleanup
        asyncio.run(engine.dispose())
        del embedding_service
        gc.collect()

    return result
```

**Key Points:**
- Top-level function (multiprocessing requirement)
- Creates own embedding service (no sharing)
- Creates own DB engine (independent connection pool)
- Cleanup resources after processing
- Returns `FileProcessingResult` for aggregation

### 2. Modified Pipeline Function

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
        dict with stats: total_files, success_files, total_chunks, errors
    """
    # Phase 1: Cleanup (sequential)
    if not engine:
        db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://mnemo:mnemo@mnemo-postgres:5432/mnemolite")
        engine = create_async_engine(db_url, echo=False)

    await cleanup_repository(repository, engine)

    # Phase 2: Scan files
    files = scan_files(directory)

    # Phase 3: Parallel processing with Joblib
    from joblib import Parallel, delayed

    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://mnemo:mnemo@mnemo-postgres:5432/mnemolite")

    print(f"\n🔧 Starting {n_jobs} parallel workers...")
    print(f"📊 Processing {len(files)} files with {n_jobs} workers")

    results = Parallel(n_jobs=n_jobs, verbose=10 if verbose else 0)(
        delayed(worker_process_file)(file_path, repository, db_url)
        for file_path in files
    )

    # Aggregate results
    success_count = sum(1 for r in results if r.success)
    total_chunks = sum(r.chunks_created for r in results)
    errors = [{"file": str(r.file_path), "error": r.error_message}
              for r in results if not r.success]

    return {
        "total_files": len(files),
        "success_files": success_count,
        "error_files": len(errors),
        "total_chunks": total_chunks,
        "errors": errors
    }
```

**Key Changes from Streaming Pipeline:**
- Add `n_jobs` parameter (default: 4)
- Replace `for file in files` with `Parallel(n_jobs=n_jobs)(...)`
- Pass `db_url` to workers (not engine, as it can't be pickled)
- Aggregate results from all workers

### 3. Updated Main Entry Point

```python
async def main():
    """Main entry point - parallel mode."""
    parser = argparse.ArgumentParser(description="Index TypeScript/JavaScript codebase")
    parser.add_argument("directory", type=Path, help="Path to codebase")
    parser.add_argument("--repository", type=str, help="Repository name")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers")
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging")

    args = parser.parse_args()

    directory = args.directory.resolve()
    repository = args.repository or directory.name

    # Create engine for cleanup and graph phases
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://mnemo:mnemo@mnemo-postgres:5432/mnemolite")
    engine = create_async_engine(db_url, echo=False)

    # Run parallel pipeline
    stats = await run_parallel_pipeline(
        directory, repository, n_jobs=args.workers, verbose=args.verbose, engine=engine
    )

    # Run graph construction if files succeeded
    if stats['success_files'] > 0:
        graph_stats = await build_graph_phase(repository, engine)
        stats['graph'] = graph_stats

    await engine.dispose()

    # Print summary
    print("\n" + "=" * 80)
    print("✅ INDEXING COMPLETE")
    print("=" * 80)
    print(f"   - Total files: {stats['total_files']}")
    print(f"   - Success: {stats['success_files']}")
    print(f"   - Errors: {stats['error_files']}")
    print(f"   - Total chunks: {stats['total_chunks']}")
    print(f"   - Graph nodes: {stats.get('graph', {}).get('total_nodes', 0)}")
    print(f"   - Graph edges: {stats.get('graph', {}).get('total_edges', 0)}")

    if stats['errors']:
        print(f"\n❌ Failed files:")
        for error in stats['errors'][:10]:  # Show first 10
            print(f"   - {error['file']}: {error['error']}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Configuration Changes

### 1. Docker Memory Limit

**docker-compose.yml:**

```yaml
services:
  api:
    image: mnemo-api
    container_name: mnemo-api
    deploy:
      resources:
        limits:
          memory: 16G  # INCREASED from 8G to 16G
        reservations:
          memory: 12G
```

**Why 16GB:**
- 4 workers × 3GB (2GB model + 1GB processing) = 12GB
- 4GB margin for PostgreSQL, OS, overhead

### 2. Python Dependencies

**requirements.txt:**

```
# Add Joblib
joblib>=1.3.0
```

### 3. Environment Variables

**.env or command-line:**

```bash
DATABASE_URL=postgresql+asyncpg://mnemo:mnemo@mnemo-postgres:5432/mnemolite
EMBEDDING_MODE=real  # Set by workers automatically
```

---

## Usage

### Build and Deploy

```bash
# Rebuild with new memory limit
docker compose build api

# Restart services
docker compose up -d
```

### Run Indexing

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
  --workers 6 \
  --verbose
```

### Monitor Progress

```bash
# Watch memory usage
docker stats mnemo-api

# Follow logs
docker logs -f mnemo-api
```

---

## Performance Metrics

### Expected Performance

| Metric | Baseline (Streaming) | Target (Parallel) | Improvement |
|--------|---------------------|-------------------|-------------|
| **Completion** | 75% (196/261 files) | 100% (261/261 files) | ✅ +33% |
| **Time** | ~10-15min (partial) | ~4.5-5.5min (full) | ✅ 2-3× faster |
| **Memory Peak** | 738MB → OOM | 12GB stable | ✅ Controlled |
| **Throughput** | ~13 files/min | ~47 files/min | ✅ 3.6× |

### Breakdown by Phase

1. **Cleanup:** <5s (unchanged)
2. **Worker Startup:** ~2min (4 models load in parallel)
3. **Processing:** ~2-3min (261 files / 4 workers = ~65 files/worker)
4. **Graph Construction:** ~10-15s (unchanged)

**Total:** ~4.5-5.5 minutes for 100% completion

---

## Testing Strategy

### Unit Tests

**tests/integration/test_parallel_pipeline.py:**

```python
@pytest.mark.asyncio
async def test_worker_isolation_no_shared_memory_leak(tmp_path, clean_db):
    """Verify workers are isolated (no shared memory leak)."""
    for i in range(10):
        (tmp_path / f"file{i}.ts").write_text(f"export function func{i}() {{ return {i}; }}")

    stats = await run_parallel_pipeline(tmp_path, "test_isolation", n_jobs=2, engine=clean_db)

    assert stats['success_files'] == 10
    assert stats['total_chunks'] == 10

@pytest.mark.asyncio
async def test_parallel_pipeline_handles_errors_gracefully(tmp_path, clean_db):
    """Verify continue-on-error with parallel workers."""
    (tmp_path / "valid1.ts").write_text("export function f1() {}")
    (tmp_path / "invalid.ts").write_text("!!!INVALID SYNTAX!!!")
    (tmp_path / "valid2.ts").write_text("export function f2() {}")

    stats = await run_parallel_pipeline(tmp_path, "test_errors", n_jobs=2, engine=clean_db)

    assert stats['success_files'] >= 2
    assert len(stats['errors']) <= 1

@pytest.mark.asyncio
async def test_parallel_faster_than_sequential(tmp_path, clean_db):
    """Verify parallel is faster than sequential."""
    for i in range(20):
        (tmp_path / f"file{i}.ts").write_text(f"export function func{i}() {{ return {i}; }}")

    # Sequential (n_jobs=1)
    start = time.time()
    await run_parallel_pipeline(tmp_path, "test_seq", n_jobs=1, engine=clean_db)
    seq_time = time.time() - start

    # Parallel (n_jobs=4)
    await cleanup_repository("test_par", clean_db)
    start = time.time()
    await run_parallel_pipeline(tmp_path, "test_par", n_jobs=4, engine=clean_db)
    par_time = time.time() - start

    assert par_time < seq_time * 0.6  # At least 40% faster
```

### Integration Test

**Real-world validation with code_test (261 files):**

```bash
# Full test
time docker exec -i mnemo-api python /app/scripts/index_directory.py \
  /app/code_test \
  --repository code_test \
  --workers 4 \
  --verbose

# Expected output:
# ✅ INDEXING COMPLETE
#    - Total files: 261
#    - Success: 261 (100%)
#    - Total chunks: ~1,847
#    - Graph nodes: ~500
#    - Graph edges: ~800
#
# real    4m32.156s
```

---

## Error Handling

### Worker Failures

**Scenario:** Worker crashes during file processing

**Behavior:**
- Transaction automatically rolled back (atomicity preserved)
- File marked as failed in results
- Other workers continue processing
- Error logged in final report

**Example:**

```
❌ Failed files:
   - /app/code_test/large_file.ts: Out of memory (file too large)
   - /app/code_test/corrupted.ts: Invalid UTF-8 encoding
```

### Out of Memory

**Scenario:** Docker runs out of memory despite 16GB limit

**Detection:**
- Exit code 137 (OOM killer)
- `docker stats` shows memory at 100%

**Solutions:**
1. Reduce worker count: `--workers 2` (6GB instead of 12GB)
2. Increase Docker memory: 20-24GB
3. Process in batches: Split repository into subdirectories

### Database Connection Issues

**Scenario:** PostgreSQL max_connections exceeded

**Detection:**
- Error: "too many clients already"
- PostgreSQL logs show connection count at limit

**Solutions:**
1. Increase `max_connections` in postgresql.conf
2. Reduce worker count
3. Adjust SQLAlchemy pool size: `pool_size=2, max_overflow=0`

---

## Rollback Plan

If parallel pipeline has issues, revert to streaming pipeline:

```bash
# Checkout previous version
git checkout HEAD~1 -- scripts/index_directory.py

# Or use streaming mode flag (if implemented)
docker exec -i mnemo-api python /app/scripts/index_directory.py \
  /app/code_test \
  --repository code_test \
  --streaming  # Force sequential mode
```

---

## Future Enhancements

### Short-term (Nice-to-have)

1. **Progress bar** - Real-time progress with `tqdm` multiprocessing support
2. **Adaptive worker count** - Auto-detect based on available memory
3. **Resume capability** - Checkpoint progress, skip already-processed files

### Long-term (If needed for larger repos)

1. **Distributed processing** - Ray or Dask for multi-machine scaling
2. **Embedding server** - Separate service for embedding generation (reduce memory per worker)
3. **Incremental indexing** - Only process changed files (git diff integration)

---

## Success Criteria

✅ **Must Have:**
- [ ] 100% completion on code_test (261/261 files)
- [ ] No OOM errors with 16GB Docker memory
- [ ] All tests passing
- [ ] Performance improvement: <6 minutes total time

✅ **Should Have:**
- [ ] 2-4× faster than baseline
- [ ] Memory usage stable ~12GB
- [ ] Continue-on-error works correctly
- [ ] Clear error reporting

✅ **Nice to Have:**
- [ ] <5 minutes total time
- [ ] Works with 2-8 workers flexibly
- [ ] Helpful logging and progress indication

---

## References

- **Joblib Documentation:** https://joblib.readthedocs.io/
- **Previous Implementation:** `docs/plans/2025-11-02-streaming-pipeline-oom-fix.md`
- **Current Code:** `scripts/index_directory.py`
- **Tests:** `tests/integration/test_streaming_pipeline.py`
