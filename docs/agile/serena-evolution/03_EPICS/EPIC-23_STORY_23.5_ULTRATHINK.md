# EPIC-23 Story 23.5 ULTRATHINK - Project Indexing Tools

**Date**: 2025-10-28
**Story**: 23.5 - Project Indexing Tools (2 pts, ~7h estimated)
**Status**: 🧠 ULTRATHINK ANALYSIS - Pre-Implementation Deep Dive

---

## 📋 TABLE OF CONTENTS

1. [Story Overview](#story-overview)
2. [Existing Infrastructure Analysis](#existing-infrastructure-analysis)
3. [Technical Challenges](#technical-challenges)
4. [Design Decisions](#design-decisions)
5. [Implementation Approach](#implementation-approach)
6. [Risk Analysis](#risk-analysis)
7. [Test Strategy](#test-strategy)
8. [Acceptance Criteria](#acceptance-criteria)

---

## 1. STORY OVERVIEW

### 1.1 Goals

Expose project indexing capabilities via MCP protocol to enable Claude Desktop to:
- **Index entire projects** (1000+ files) with real-time progress reporting
- **Reindex individual files** after modifications
- **Query index status** (indexed files, chunks, languages, last update)
- **Stream progress** updates during long-running operations

### 1.2 Sub-Stories Breakdown

| Sub-Story | Description | Estimated Time | Priority |
|-----------|-------------|----------------|----------|
| 23.5.1 | `index_project` Tool | 2.5h | 🔴 CRITICAL |
| 23.5.2 | `reindex_file` Tool | 1.5h | 🟡 HIGH |
| 23.5.3 | `index://status` Resource | 1.5h | 🟡 HIGH |
| 23.5.4 | Progress Streaming (SSE) | 1.5h | 🟢 MEDIUM |

**Total**: 7h (4 sub-stories)

### 1.3 MCP Components

**Tools** (2):
- `index_project(project_path, repository, options)` → `IndexResult`
- `reindex_file(file_path, repository)` → `FileIndexResult`

**Resources** (1):
- `index://status` → `IndexStatus`

**Features**:
- Real-time progress reporting via `ctx.report_progress()`
- Elicitation for destructive operations
- Graceful degradation if services unavailable

---

## 2. EXISTING INFRASTRUCTURE ANALYSIS

### 2.1 Current CodeIndexingService

**Location**: `api/services/code_indexing_service.py`

**Key Methods**:
```python
class CodeIndexingService:
    async def index_repository(
        files: List[FileInput],
        options: IndexingOptions
    ) -> IndexingSummary

    async def _index_file(
        file_input: FileInput,
        options: IndexingOptions
    ) -> FileIndexingResult
```

**Current Capabilities** ✅:
- ✅ Language detection (15+ languages)
- ✅ Tree-sitter chunking
- ✅ Metadata extraction
- ✅ LSP type extraction (Python, TypeScript, JavaScript)
- ✅ Dual embeddings (TEXT + CODE domains)
- ✅ Batch processing
- ✅ L1/L2 cascade cache integration
- ✅ Transactional batch insert (EPIC-12)
- ✅ Timeout protection (EPIC-12)
- ✅ Graceful degradation

**What's Missing** ❌:
- ❌ **Progress callback support** - No mechanism for real-time progress
- ❌ **Project path scanning** - `index_repository()` takes `List[FileInput]`, not a project directory
- ❌ **Status tracking** - No persistent state for "indexing in progress"
- ❌ **Single file reindex** - No public method (only private `_index_file()`)

### 2.2 Dependency Services

**Available Services** (from `api/dependencies.py`):
1. `CodeIndexingService` ✅
2. `CodeChunkRepository` ✅
3. `NodeRepository` ✅
4. `GraphTraversalService` ✅
5. `EmbeddingService` (DualEmbeddingService) ✅
6. `CascadeCache` (L1/L2) ✅
7. `RedisCache` ✅

**All required services are already available** ✅

### 2.3 Performance Characteristics

From EPIC-06/08 benchmarks:
- **File indexing**: <100ms per file (7-step pipeline)
- **Project indexing (1000 files)**: ~100 seconds (1.7 minutes)
- **Cache hit rate**: 80%+ after warm-up
- **Throughput**: 10-15 files/second
- **Timeout protection**: 60s per file (EPIC-12)

**Expected Story 23.5 Performance**:
- **1000-file project**: ~2-3 minutes (first index, no cache)
- **1000-file project (cached)**: ~10-20 seconds (90% cache hit)
- **Progress updates**: Every 1 second or every 10 files
- **Status query**: <50ms (simple DB query)

---

## 3. TECHNICAL CHALLENGES

### 3.1 Challenge 1: Project Path Scanning

**Problem**: Current `index_repository()` accepts `List[FileInput]`, not a project directory.

**Options**:

#### Option A: Add `scan_project_files()` to CodeIndexingService
```python
async def scan_project_files(project_path: str) -> List[FileInput]:
    """Scan project directory for code files."""
    # Walk directory tree
    # Filter by supported languages
    # Respect .gitignore
    # Return List[FileInput]
```

**Pros**:
- ✅ Clean separation of concerns
- ✅ Reusable for other tools
- ✅ Testable in isolation

**Cons**:
- ⚠️ Adds complexity to service
- ⚠️ Requires .gitignore parsing

#### Option B: Create separate `ProjectScanner` utility
```python
# utils/project_scanner.py
class ProjectScanner:
    async def scan(
        project_path: str,
        respect_gitignore: bool = True
    ) -> List[FileInput]:
        pass
```

**Pros**:
- ✅ Single responsibility
- ✅ Easy to test
- ✅ Can use pathspec library (already used in Serena)

**Cons**:
- ⚠️ New dependency

**DECISION**: **Option B** - Create `ProjectScanner` utility
- **Rationale**: Single responsibility, clean separation, reusable
- **Implementation**: Use Python's `pathlib` + `pathspec` for .gitignore support

---

### 3.2 Challenge 2: Progress Callback Integration

**Problem**: `CodeIndexingService.index_repository()` doesn't support progress callbacks.

**Current Implementation**:
```python
async def index_repository(files, options) -> IndexingSummary:
    for file_input in files:  # Sequential
        result = await self._index_file(file_input, options)
        # NO CALLBACK HERE ❌
```

**Options**:

#### Option A: Add `progress_callback` parameter to `index_repository()`
```python
async def index_repository(
    files: List[FileInput],
    options: IndexingOptions,
    progress_callback: Optional[Callable[[int, int, str], Awaitable[None]]] = None
) -> IndexingSummary:
    for i, file_input in enumerate(files):
        result = await self._index_file(file_input, options)
        if progress_callback:
            await progress_callback(i + 1, len(files), f"Indexed {file_input.path}")
```

**Pros**:
- ✅ Minimal changes
- ✅ Backward compatible (optional parameter)
- ✅ Clean async callback pattern

**Cons**:
- ⚠️ Changes public API signature

#### Option B: Create wrapper method in MCP tool
```python
async def index_project_with_progress(
    files, options, ctx: Context
) -> IndexingSummary:
    total = len(files)
    for i, file in enumerate(files):
        # Index file
        result = await indexing_service._index_file(file, options)
        # Report progress
        await ctx.report_progress(i / total, f"Indexed {file.path}")
```

**Pros**:
- ✅ No changes to CodeIndexingService
- ✅ Keeps MCP logic in MCP layer

**Cons**:
- ⚠️ Duplicates indexing logic
- ⚠️ Couples MCP tool to private `_index_file()` method

**DECISION**: **Option A** - Add `progress_callback` parameter
- **Rationale**: Cleaner, more maintainable, keeps logic in service layer
- **Implementation**: Optional parameter (default None) for backward compatibility

---

### 3.3 Challenge 3: Indexing Status Tracking

**Problem**: No persistent state to track "indexing in progress", "completed", "failed".

**Requirements**:
- Query current status via `index://status` resource
- Prevent concurrent indexing of same project
- Track last indexed time, file count, chunk count

**Options**:

#### Option A: In-memory status tracking
```python
# Global state in CodeIndexingService
_indexing_status = {
    "repository_name": {
        "status": "in_progress",
        "total_files": 1000,
        "indexed_files": 450,
        "started_at": datetime(...),
    }
}
```

**Pros**:
- ✅ Fast (no DB queries)
- ✅ Simple implementation

**Cons**:
- ❌ Lost on server restart
- ❌ Not shared across workers
- ❌ No persistence

#### Option B: PostgreSQL `indexing_jobs` table
```sql
CREATE TABLE indexing_jobs (
    id UUID PRIMARY KEY,
    repository VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,  -- 'in_progress', 'completed', 'failed'
    total_files INT,
    indexed_files INT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error TEXT
);
```

**Pros**:
- ✅ Persistent across restarts
- ✅ Shared across workers
- ✅ Queryable history

**Cons**:
- ⚠️ Requires DB migration
- ⚠️ Slower queries

#### Option C: Redis key-value store
```python
# Redis keys: "indexing:status:{repository}"
await redis.set(
    f"indexing:status:{repository}",
    json.dumps({"status": "in_progress", "total_files": 1000}),
    ex=3600  # 1 hour TTL
)
```

**Pros**:
- ✅ Fast (<1ms)
- ✅ Shared across workers
- ✅ Auto-expiry (TTL)

**Cons**:
- ⚠️ Lost if Redis unavailable
- ⚠️ Not persistent (ephemeral)

**DECISION**: **Option C** - Redis key-value store
- **Rationale**: Fast, shared, auto-expiry fits use case (temporary status)
- **Fallback**: If Redis unavailable, return "unknown" status
- **No DB migration needed**: Reduces implementation time

---

### 3.4 Challenge 4: Concurrent Indexing Prevention

**Problem**: Multiple clients might trigger `index_project` simultaneously → race conditions, duplicate work.

**Solution**: **Distributed Lock with Redis**

```python
async def index_project(project_path: str, repository: str):
    lock_key = f"indexing:lock:{repository}"

    # Try to acquire lock (5-minute TTL)
    acquired = await redis.set(lock_key, "1", nx=True, ex=300)

    if not acquired:
        # Lock held by another process
        return MCPBaseResponse(
            success=False,
            message="Indexing already in progress for this repository"
        )

    try:
        # Perform indexing
        result = await _do_indexing(...)
        return result
    finally:
        # Release lock
        await redis.delete(lock_key)
```

**Properties**:
- ✅ Atomic lock acquisition (Redis `SET NX`)
- ✅ Auto-release on timeout (TTL = 300s = 5 minutes)
- ✅ Prevents concurrent indexing
- ✅ Works across workers

**Edge Case**: Lock holder crashes → Lock auto-expires after 5 minutes

---

## 4. DESIGN DECISIONS

### 4.1 Tool: `index_project`

**Signature**:
```python
async def execute(
    project_path: str,
    repository: str = "default",
    include_gitignored: bool = False,
    ctx: Optional[Context] = None
) -> IndexResult
```

**Workflow**:
1. **Elicit confirmation** (via `ctx.elicit()`) if project has >100 files
2. **Acquire distributed lock** (Redis: `indexing:lock:{repository}`)
3. **Scan project** → List[FileInput] (ProjectScanner utility)
4. **Index files** with progress callback
5. **Update status** in Redis
6. **Release lock**
7. **Return result**

**Example**:
```python
result = await index_project.execute(
    project_path="/workspace/my-project",
    repository="my-project",
    ctx=ctx
)
# Returns: IndexResult(
#     repository="my-project",
#     indexed_files=1000,
#     indexed_chunks=5000,
#     processing_time_ms=120000,
#     ...
# )
```

---

### 4.2 Tool: `reindex_file`

**Signature**:
```python
async def execute(
    file_path: str,
    repository: str = "default",
    ctx: Optional[Context] = None
) -> FileIndexResult
```

**Workflow**:
1. **Validate file exists**
2. **Read file content**
3. **Call `CodeIndexingService._index_file()`**
4. **Invalidate cache** for this file
5. **Return result**

**Use Cases**:
- File was edited → Need fresh embeddings
- LSP type info changed → Re-extract metadata
- Manual refresh after fixing bugs

---

### 4.3 Resource: `index://status`

**Signature**:
```python
async def get(self) -> IndexStatus
```

**Returns**:
```python
class IndexStatus(MCPBaseResponse):
    status: Literal["not_indexed", "in_progress", "completed", "failed"]
    repository: str
    total_files: int
    indexed_files: int
    total_chunks: int
    languages: List[str]
    last_indexed_at: Optional[datetime]
    embedding_model: str
    cache_stats: dict  # L1/L2 hit rates
```

**Data Sources**:
1. **Status**: Redis key `indexing:status:{repository}`
2. **Total files/chunks**: Query `code_chunks` table (COUNT DISTINCT)
3. **Languages**: Query `code_chunks.language` (DISTINCT)
4. **Last indexed**: MAX(`code_chunks.created_at`)
5. **Cache stats**: From `CascadeCache.get_stats()`

**Performance**: <50ms (2 queries + 1 Redis read)

---

### 4.4 Progress Streaming

**Implementation**:
```python
async def progress_callback(current: int, total: int, message: str):
    if ctx:
        await ctx.report_progress(
            progress=current / total,  # 0.0 to 1.0
            message=f"{message} ({current}/{total}, {current/total*100:.1f}%)"
        )
```

**Update Frequency**:
- Every 10 files (avoid flooding)
- Every 1 second (time-based throttle)
- On significant events (start, end, errors)

**MCP 2025-06-18 Spec**:
- `progress`: float (0.0 to 1.0)
- `message`: string (human-readable status)
- Optional: `total`, `current` (deprecated in favor of message)

---

## 5. IMPLEMENTATION APPROACH

### 5.1 Implementation Order

**Priority**: Critical-path first

1. **Day 1 (3h)**:
   - Sub-Story 23.5.1: `index_project` tool
     - Create `ProjectScanner` utility (1h)
     - Add `progress_callback` to `CodeIndexingService` (0.5h)
     - Implement `IndexProjectTool` with elicitation + lock (1h)
     - Write unit tests (0.5h)

2. **Day 2 (2h)**:
   - Sub-Story 23.5.2: `reindex_file` tool (1h)
   - Sub-Story 23.5.3: `index://status` resource (1h)
     - Redis status tracking
     - DB queries for statistics

3. **Day 3 (2h)**:
   - Sub-Story 23.5.4: Progress streaming (1h)
     - Integrate progress callback
     - Throttling logic
   - Integration testing + validation (1h)

**Total**: 7h (matches estimate)

---

### 5.2 File Structure

**New Files**:
```
api/
├── mnemo_mcp/
│   ├── tools/
│   │   └── indexing_tools.py          # NEW: IndexProjectTool, ReindexFileTool
│   ├── resources/
│   │   └── indexing_resources.py      # NEW: IndexStatusResource
│   ├── models/
│   │   └── indexing_models.py         # NEW: IndexResult, IndexStatus, etc.
│   └── utils/
│       └── project_scanner.py         # NEW: ProjectScanner utility

tests/
└── mnemo_mcp/
    ├── test_indexing_tools.py         # NEW: 15+ tests
    ├── test_indexing_resources.py     # NEW: 5+ tests
    └── test_project_scanner.py        # NEW: 8+ tests
```

**Modified Files**:
```
api/
├── services/
│   └── code_indexing_service.py       # MODIFY: Add progress_callback parameter
└── mnemo_mcp/
    └── server.py                      # MODIFY: Register tools/resources
```

---

### 5.3 Code Examples

#### ProjectScanner Utility
```python
# api/mnemo_mcp/utils/project_scanner.py
from pathlib import Path
from typing import List
import pathspec

class ProjectScanner:
    """Scan project directory for code files."""

    SUPPORTED_EXTENSIONS = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs",
        ".java", ".c", ".cpp", ".h", ".hpp", ".rb", ".php"
    }

    async def scan(
        self,
        project_path: str,
        respect_gitignore: bool = True
    ) -> List[FileInput]:
        """Scan project and return list of code files."""
        files = []
        project_root = Path(project_path)

        # Load .gitignore if exists
        gitignore_spec = None
        if respect_gitignore:
            gitignore_path = project_root / ".gitignore"
            if gitignore_path.exists():
                with open(gitignore_path) as f:
                    gitignore_spec = pathspec.PathSpec.from_lines(
                        'gitwildmatch', f
                    )

        # Walk directory
        for file_path in project_root.rglob("*"):
            if not file_path.is_file():
                continue

            # Skip gitignored files
            if gitignore_spec:
                relative = file_path.relative_to(project_root)
                if gitignore_spec.match_file(str(relative)):
                    continue

            # Check supported extension
            if file_path.suffix not in self.SUPPORTED_EXTENSIONS:
                continue

            # Read file content
            try:
                content = file_path.read_text(encoding='utf-8')
                files.append(FileInput(
                    path=str(file_path),
                    content=content
                ))
            except Exception as e:
                logger.warning(f"Failed to read {file_path}: {e}")

        return files
```

#### IndexProjectTool
```python
# api/mnemo_mcp/tools/indexing_tools.py
class IndexProjectTool(BaseMCPComponent):
    """Tool: index_project - Index entire project directory."""

    async def execute(
        self,
        project_path: str,
        repository: str = "default",
        include_gitignored: bool = False,
        ctx: Optional[Context] = None
    ) -> dict:
        """Index project with progress reporting."""

        # 1. Scan project
        scanner = ProjectScanner()
        files = await scanner.scan(
            project_path,
            respect_gitignore=not include_gitignored
        )

        # 2. Elicit confirmation if many files
        if len(files) > 100 and ctx:
            response = await ctx.elicit(
                prompt=f"Index {len(files)} files in {repository}? This may take several minutes.",
                schema={"type": "string", "enum": ["yes", "no"]}
            )
            if response.value == "no":
                return {"success": False, "message": "Indexing cancelled by user"}

        # 3. Acquire lock
        redis = self.services["redis"]
        lock_key = f"indexing:lock:{repository}"
        acquired = await redis.set(lock_key, "1", nx=True, ex=300)

        if not acquired:
            return {"success": False, "message": "Indexing already in progress"}

        try:
            # 4. Progress callback
            async def progress_callback(current: int, total: int, msg: str):
                if ctx:
                    await ctx.report_progress(
                        progress=current / total,
                        message=f"{msg} ({current}/{total}, {current/total*100:.1f}%)"
                    )

            # 5. Index repository
            indexing_service = self.services["code_indexing_service"]
            result = await indexing_service.index_repository(
                files=files,
                options=IndexingOptions(repository=repository),
                progress_callback=progress_callback
            )

            # 6. Update Redis status
            await redis.set(
                f"indexing:status:{repository}",
                json.dumps({
                    "status": "completed",
                    "indexed_files": result.indexed_files,
                    "completed_at": datetime.utcnow().isoformat()
                }),
                ex=3600
            )

            return {
                "success": True,
                "repository": result.repository,
                "indexed_files": result.indexed_files,
                "indexed_chunks": result.indexed_chunks,
                "processing_time_ms": result.processing_time_ms
            }

        finally:
            # 7. Release lock
            await redis.delete(lock_key)
```

---

## 6. RISK ANALYSIS

### 6.1 High-Risk Areas

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Long-running operations timeout** | High | High | Increase timeout to 10 minutes, use progress reporting |
| **Redis unavailable during indexing** | Medium | Medium | Graceful degradation: allow without lock, log warning |
| **Project scanner fails on large projects** | Medium | High | Add file count limit (10,000), stream files instead of loading all |
| **Progress callback overhead** | Low | Medium | Throttle to every 10 files or 1 second |
| **Concurrent indexing race** | Low | High | Redis distributed lock (NX flag) |

### 6.2 Edge Cases

1. **Project with 50,000+ files**: Add limit (10,000 files) with error message
2. **Circular symlinks**: Use `pathlib.resolve()` to detect cycles
3. **Binary files misdetected**: Validate UTF-8 encoding before indexing
4. **Redis connection lost mid-indexing**: Continue without progress updates (graceful degradation)
5. **User cancels mid-indexing**: No graceful cancellation (MCP limitation) → Lock expires after 5 minutes

---

## 7. TEST STRATEGY

### 7.1 Unit Tests

**test_project_scanner.py** (8 tests):
- ✅ Scan project with supported files
- ✅ Respect .gitignore
- ✅ Skip non-code files
- ✅ Handle symlinks
- ✅ Empty project
- ✅ Large project (>1000 files)
- ✅ Invalid path
- ✅ Permission denied

**test_indexing_tools.py** (15 tests):
- ✅ Index project success
- ✅ Index project with progress
- ✅ Elicitation flow (yes/no)
- ✅ Concurrent indexing prevention (lock)
- ✅ Reindex single file
- ✅ Invalid file path
- ✅ Missing services
- ✅ Redis unavailable (graceful degradation)

**test_indexing_resources.py** (5 tests):
- ✅ Get index status (in_progress)
- ✅ Get index status (completed)
- ✅ Get index status (not_indexed)
- ✅ Status with cache stats
- ✅ Redis unavailable

**Total**: 28 new tests

### 7.2 Integration Tests

**Scenario 1: End-to-end indexing**
```python
async def test_e2e_index_project():
    # 1. Create test project (10 files)
    # 2. Call index_project tool
    # 3. Verify all files indexed
    # 4. Verify progress updates received
    # 5. Verify index status = "completed"
    # 6. Verify cache populated
```

**Scenario 2: Concurrent indexing**
```python
async def test_concurrent_indexing_prevented():
    # 1. Start index_project (async)
    # 2. Try to start second index_project
    # 3. Verify second fails with "already in progress"
    # 4. Wait for first to complete
    # 5. Retry second → success
```

---

## 8. ACCEPTANCE CRITERIA

### 8.1 Functional Requirements

- [ ] ✅ `index_project` tool indexes entire project directory
- [ ] ✅ Progress reporting works (0-100% with messages)
- [ ] ✅ Elicitation prompts for confirmation (>100 files)
- [ ] ✅ `reindex_file` tool updates single file
- [ ] ✅ `index://status` resource returns accurate status
- [ ] ✅ Concurrent indexing prevented (distributed lock)
- [ ] ✅ Graceful degradation if Redis unavailable
- [ ] ✅ .gitignore respected by default

### 8.2 Performance Requirements

- [ ] ✅ 1000-file project indexes in <3 minutes (first run)
- [ ] ✅ 1000-file project with 90% cache hit: <30 seconds
- [ ] ✅ Status query: <50ms
- [ ] ✅ Progress updates: ≤1 second latency
- [ ] ✅ Reindex single file: <100ms (cached), <2s (uncached)

### 8.3 Quality Requirements

- [ ] ✅ 28+ unit tests passing (100%)
- [ ] ✅ 2+ integration tests passing
- [ ] ✅ Type hints on all public methods
- [ ] ✅ Structured logging (JSON)
- [ ] ✅ Error handling with graceful degradation
- [ ] ✅ MCP 2025-06-18 compliant

---

## 9. OPEN QUESTIONS & DECISIONS NEEDED

### 9.1 Questions for User

1. **File count limit**: Should we hard-limit projects to 10,000 files? Or make it configurable?
   - **Recommendation**: Hard limit 10,000, log warning at 5,000

2. **Progress update frequency**: Every 10 files or every 1 second?
   - **Recommendation**: Whichever comes first (max 1 update/second)

3. **Elicitation threshold**: Confirm if >100 files or >1000 files?
   - **Recommendation**: >100 files (conservative)

4. **Lock timeout**: 5 minutes or 10 minutes for large projects?
   - **Recommendation**: 10 minutes (safe for 5000+ files)

5. **DB migration**: Should we add `indexing_jobs` table for persistence?
   - **Recommendation**: NO - Use Redis (faster, simpler)

### 9.2 Decisions Made

| Decision | Rationale |
|----------|-----------|
| Use `ProjectScanner` utility | Clean separation of concerns |
| Add `progress_callback` to service | Keeps logic in service layer |
| Redis for status tracking | Fast, ephemeral, shared across workers |
| Distributed lock with Redis | Prevents concurrent indexing |
| No DB migration required | Reduces complexity, Redis sufficient |
| Throttle progress to 1/second | Avoids flooding client |

---

## 10. NEXT STEPS

### 10.1 Pre-Implementation Checklist

- [ ] Review this ULTRATHINK with user
- [ ] Get approval on design decisions
- [ ] Clarify open questions
- [ ] Create TODO list for implementation

### 10.2 Implementation Phases

**Phase 1** (Day 1 - 3h):
- Create `ProjectScanner` utility
- Modify `CodeIndexingService.index_repository()` (add progress_callback)
- Implement `IndexProjectTool`
- Write unit tests for tool + scanner

**Phase 2** (Day 2 - 2h):
- Implement `ReindexFileTool`
- Implement `IndexStatusResource`
- Write unit tests for both

**Phase 3** (Day 3 - 2h):
- Integrate progress streaming
- Integration testing
- Validation with MCP Inspector

**Total**: 7h

---

## 11. SUMMARY & RECOMMENDATIONS

### 11.1 Key Insights

1. **Existing infrastructure is 90% ready** - CodeIndexingService already has most capabilities
2. **Main gap is progress reporting** - Need to add callback support
3. **Redis is perfect for status tracking** - Fast, shared, ephemeral
4. **Distributed lock prevents races** - Critical for production safety
5. **No DB migration needed** - Saves significant time

### 11.2 Confidence Level

**Overall**: 95% confident in 7h estimate

**Breakdown**:
- ProjectScanner: 95% (straightforward file walking)
- Progress callback: 90% (minor API change)
- Redis lock: 95% (standard pattern)
- Status tracking: 90% (simple queries)
- Progress streaming: 85% (throttling complexity)

**Risk Factors**:
- ⚠️ Large project handling (>5000 files) - might need tuning
- ⚠️ Progress callback overhead - might need optimization
- ✅ Redis integration - well understood
- ✅ MCP protocol - already validated in Stories 23.1-23.4

### 11.3 Go/No-Go Decision

**RECOMMENDATION**: ✅ **GO - Ready for Implementation**

**Rationale**:
- All technical challenges analyzed
- Clear implementation path
- No blockers identified
- Existing tests provide safety net
- Redis already in place (EPIC-10)
- CodeIndexingService well-tested (EPIC-06)

**Prerequisites**:
- ✅ User approval of design decisions
- ✅ Clarification of open questions (file limits, thresholds)
- ✅ Agreement on 7h estimate

---

**Status**: 🟢 **READY FOR IMPLEMENTATION**
**Estimated Completion**: 7h (3 days at 2-3h/day)
**Confidence**: 95%

