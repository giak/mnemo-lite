# EPIC-12 Story 12.2: Transaction Boundaries - Implementation Plan

**Story**: Transaction Boundaries
**Points**: 3 pts
**Status**: 📋 READY FOR IMPLEMENTATION
**Created**: 2025-10-21
**Dependencies**: Story 12.1 (Timeout-Based Execution) ✅ COMPLETE

---

## Implementation Overview

**Goal**: Enable atomic multi-step database operations by adding transaction parameter support to all repositories.

**Strategy**: Add optional `connection` parameter to repository methods (backward compatible).

**Phases**:
1. ✅ **Analysis Complete** - Technical analysis done, risks assessed
2. 📋 **Phase 1**: Repository layer (1-2 hours) - Add transaction support
3. 📋 **Phase 2**: Service layer (2-3 hours) - Wrap operations in transactions
4. 📋 **Phase 3**: Route layer (1 hour) - Migrate from raw SQL to repositories
5. 📋 **Phase 4**: Testing (2-3 hours) - Comprehensive test coverage

**Total Estimated Time**: 6-9 hours

---

## Phase 1: Repository Layer (1-2 hours)

### Step 1.1: Update `_execute_query()` in BaseRepository Pattern

**Objective**: Modify `_execute_query()` to accept optional external connection.

**Files to Modify**: All 4 repositories use this pattern
- `api/db/repositories/code_chunk_repository.py:343-359`
- `api/db/repositories/node_repository.py:106-122`
- `api/db/repositories/edge_repository.py:119-135`
- `api/db/repositories/event_repository.py:99-115`

**Implementation**:

```python
async def _execute_query(
    self,
    query: TextClause,
    params: Dict[str, Any],
    is_mutation: bool = False,
    connection: Optional[AsyncConnection] = None  # ← NEW parameter
) -> Result:
    """
    Execute query with optional external connection.

    Args:
        query: SQL query to execute
        params: Query parameters
        is_mutation: If True, wrap in transaction
        connection: Optional external connection (caller manages transaction)

    Returns:
        Query result

    Raises:
        RepositoryError: If query execution fails
    """
    if connection:
        # Use provided connection (caller manages transaction)
        try:
            result = await connection.execute(query, params)
            return result
        except Exception as e:
            # Don't rollback - caller manages transaction
            raise RepositoryError(f"Query execution failed: {e}") from e
    else:
        # Create own connection and transaction (backward compatible)
        async with self.engine.connect() as conn:
            transaction = await conn.begin() if is_mutation else None
            try:
                result = await conn.execute(query, params)
                if transaction:
                    await transaction.commit()
                return result
            except Exception as e:
                if transaction:
                    await transaction.rollback()
                raise RepositoryError(f"Query execution failed: {e}") from e
```

**Testing**:
```bash
# Verify backward compatibility (no connection parameter)
docker compose exec api python -c "
import asyncio
from db.repositories.code_chunk_repository import CodeChunkRepository
from dependencies import get_engine

async def test():
    engine = await anext(get_engine())
    repo = CodeChunkRepository(engine)
    # Call without connection parameter (backward compatible)
    chunks = await repo.get_by_file_path('test.py')
    print(f'✅ Backward compatible: {len(chunks)} chunks')

asyncio.run(test())
"
```

---

### Step 1.2: Update CodeChunkRepository Methods

**File**: `api/db/repositories/code_chunk_repository.py`

**Methods to Update** (add `connection` parameter):

1. **add()** (line 361):
```python
async def add(
    self,
    chunk_data: CodeChunkCreate,
    connection: Optional[AsyncConnection] = None  # ← NEW
) -> CodeChunkModel:
    """Add a new code chunk."""
    query, params = self.query_builder.build_add_query(chunk_data)
    db_result = await self._execute_query(
        query, params, is_mutation=True, connection=connection
    )
    row = db_result.mappings().first()
    return CodeChunkModel.from_db_record(row)
```

2. **add_batch()** (line 374):
```python
async def add_batch(
    self,
    chunks_data: List[CodeChunkCreate],
    connection: Optional[AsyncConnection] = None  # ← NEW
) -> int:
    """Batch insert code chunks."""
    query, params = self.query_builder.build_add_batch_query(chunks_data)
    db_result = await self._execute_query(
        query, params, is_mutation=True, connection=connection
    )
    return db_result.rowcount
```

3. **update()** (line 416):
```python
async def update(
    self,
    chunk_id: uuid.UUID,
    chunk_data: CodeChunkCreate,
    connection: Optional[AsyncConnection] = None  # ← NEW
) -> CodeChunkModel:
    """Update an existing code chunk."""
    query, params = self.query_builder.build_update_query(chunk_id, chunk_data)
    db_result = await self._execute_query(
        query, params, is_mutation=True, connection=connection
    )
    row = db_result.mappings().first()
    return CodeChunkModel.from_db_record(row)
```

4. **delete()** (line 427):
```python
async def delete(
    self,
    chunk_id: uuid.UUID,
    connection: Optional[AsyncConnection] = None  # ← NEW
) -> bool:
    """Delete a code chunk."""
    query = text("DELETE FROM code_chunks WHERE id = :chunk_id")

    if connection:
        result = await connection.execute(query, {"chunk_id": str(chunk_id)})
    else:
        result = await self._execute_query(
            query, {"chunk_id": str(chunk_id)}, is_mutation=True
        )

    return result.rowcount > 0
```

**NEW Methods** (bulk operations):

5. **delete_by_repository()** (NEW):
```python
async def delete_by_repository(
    self,
    repository: str,
    connection: Optional[AsyncConnection] = None
) -> int:
    """
    Delete all chunks for a repository.

    Args:
        repository: Repository name
        connection: Optional external connection

    Returns:
        Number of chunks deleted
    """
    query = text("DELETE FROM code_chunks WHERE repository = :repository")

    if connection:
        result = await connection.execute(query, {"repository": repository})
    else:
        result = await self._execute_query(
            query, {"repository": repository}, is_mutation=True
        )

    deleted = result.rowcount
    self.logger.info(f"Deleted {deleted} chunks for repository '{repository}'")
    return deleted
```

6. **delete_by_file_path()** (NEW):
```python
async def delete_by_file_path(
    self,
    file_path: str,
    connection: Optional[AsyncConnection] = None
) -> int:
    """
    Delete all chunks for a file.

    Args:
        file_path: File path
        connection: Optional external connection

    Returns:
        Number of chunks deleted
    """
    query = text("DELETE FROM code_chunks WHERE file_path = :file_path")

    if connection:
        result = await connection.execute(query, {"file_path": file_path})
    else:
        result = await self._execute_query(
            query, {"file_path": file_path}, is_mutation=True
        )

    deleted = result.rowcount
    self.logger.info(f"Deleted {deleted} chunks for file '{file_path}'")
    return deleted
```

---

### Step 1.3: Update NodeRepository Methods

**File**: `api/db/repositories/node_repository.py`

**Methods to Update**:

1. **create()** (line 124)
2. **create_code_node()** (line 137)
3. **delete()** (line 201)

**NEW Method**:

4. **delete_by_repository()** (NEW):
```python
async def delete_by_repository(
    self,
    repository: str,
    connection: Optional[AsyncConnection] = None
) -> int:
    """
    Delete all nodes for a repository.

    Uses properties JSONB field to filter by repository.
    """
    query = text("""
        DELETE FROM nodes
        WHERE properties->>'repository' = :repository
    """)

    if connection:
        result = await connection.execute(query, {"repository": repository})
    else:
        result = await self._execute_query(
            query, {"repository": repository}, is_mutation=True
        )

    deleted = result.rowcount
    self.logger.info(f"Deleted {deleted} nodes for repository '{repository}'")
    return deleted
```

---

### Step 1.4: Update EdgeRepository Methods

**File**: `api/db/repositories/edge_repository.py`

**Methods to Update**:

1. **create()** (line 137)
2. **create_dependency_edge()** (line 150)
3. **delete()** (line 212)

**NEW Method**:

4. **delete_by_repository()** (NEW):
```python
async def delete_by_repository(
    self,
    repository: str,
    connection: Optional[AsyncConnection] = None
) -> int:
    """
    Delete all edges for a repository.

    Deletes edges where source OR target node belongs to repository.
    Uses subquery to find nodes by repository.
    """
    query = text("""
        DELETE FROM edges
        WHERE source_node_id IN (
            SELECT node_id FROM nodes
            WHERE properties->>'repository' = :repository
        )
        OR target_node_id IN (
            SELECT node_id FROM nodes
            WHERE properties->>'repository' = :repository
        )
    """)

    if connection:
        result = await connection.execute(query, {"repository": repository})
    else:
        result = await self._execute_query(
            query, {"repository": repository}, is_mutation=True
        )

    deleted = result.rowcount
    self.logger.info(f"Deleted {deleted} edges for repository '{repository}'")
    return deleted
```

---

### Step 1.5: Test Repository Layer

**Create Test**: `tests/db/repositories/test_transaction_support.py`

```python
"""
Tests for repository transaction support.

EPIC-12 Story 12.2: Transaction Boundaries
"""

import pytest
import uuid
from sqlalchemy.ext.asyncio import AsyncEngine

from db.repositories.code_chunk_repository import CodeChunkRepository
from db.repositories.node_repository import NodeRepository
from db.repositories.edge_repository import EdgeRepository
from models.code_chunk_models import CodeChunkCreate, ChunkType


@pytest.mark.anyio
async def test_add_with_external_transaction(clean_db: AsyncEngine):
    """Repository.add() works with external transaction."""
    repo = CodeChunkRepository(clean_db)

    chunk_data = CodeChunkCreate(
        file_path="test.py",
        language="python",
        chunk_type=ChunkType.FUNCTION,
        name="test_func",
        source_code="def test_func(): pass",
        start_line=1,
        end_line=1,
        metadata={}
    )

    chunk_id = None
    async with clean_db.begin() as conn:
        chunk = await repo.add(chunk_data, connection=conn)
        chunk_id = chunk.id
        assert chunk_id is not None
        # Transaction not yet committed

    # Verify chunk exists after transaction commits
    retrieved = await repo.get_by_id(chunk_id)
    assert retrieved is not None
    assert retrieved.name == "test_func"


@pytest.mark.anyio
async def test_transaction_rollback_on_error(clean_db: AsyncEngine):
    """Transaction rolls back when error raised."""
    repo = CodeChunkRepository(clean_db)

    chunk_data = CodeChunkCreate(
        file_path="test.py",
        language="python",
        chunk_type=ChunkType.FUNCTION,
        name="test_func",
        source_code="def test_func(): pass",
        start_line=1,
        end_line=1,
        metadata={}
    )

    chunk_id = None
    with pytest.raises(Exception, match="Test error"):
        async with clean_db.begin() as conn:
            chunk = await repo.add(chunk_data, connection=conn)
            chunk_id = chunk.id
            # Force error to trigger rollback
            raise Exception("Test error")

    # Verify chunk was NOT committed
    retrieved = await repo.get_by_id(chunk_id)
    assert retrieved is None


@pytest.mark.anyio
async def test_batch_add_with_transaction(clean_db: AsyncEngine):
    """Batch operations work with transactions."""
    repo = CodeChunkRepository(clean_db)

    chunks_data = [
        CodeChunkCreate(
            file_path="test.py",
            language="python",
            chunk_type=ChunkType.FUNCTION,
            name=f"func_{i}",
            source_code=f"def func_{i}(): pass",
            start_line=i,
            end_line=i,
            metadata={}
        )
        for i in range(10)
    ]

    async with clean_db.begin() as conn:
        count = await repo.add_batch(chunks_data, connection=conn)
        assert count == 10

    # Verify all chunks exist
    chunks = await repo.get_by_file_path("test.py")
    assert len(chunks) == 10


@pytest.mark.anyio
async def test_delete_by_repository(clean_db: AsyncEngine):
    """delete_by_repository() removes all chunks for repository."""
    repo = CodeChunkRepository(clean_db)

    # Create chunks for 2 repositories
    for repo_name in ["repo1", "repo2"]:
        for i in range(5):
            chunk_data = CodeChunkCreate(
                file_path=f"{repo_name}/test.py",
                language="python",
                chunk_type=ChunkType.FUNCTION,
                name=f"func_{i}",
                source_code=f"def func_{i}(): pass",
                start_line=i,
                end_line=i,
                metadata={},
                repository=repo_name
            )
            await repo.add(chunk_data)

    # Delete repo1
    deleted = await repo.delete_by_repository("repo1")
    assert deleted == 5

    # Verify repo1 chunks gone, repo2 chunks remain
    repo1_chunks = await repo.get_by_file_path("repo1/test.py")
    repo2_chunks = await repo.get_by_file_path("repo2/test.py")
    assert len(repo1_chunks) == 0
    assert len(repo2_chunks) == 5
```

**Run Tests**:
```bash
docker compose exec api pytest tests/db/repositories/test_transaction_support.py -v
```

---

## Phase 2: Service Layer (2-3 hours)

### Step 2.1: Update CodeIndexingService

**File**: `api/services/code_indexing_service.py`

**Modify `_index_file()` method (lines 257-582)**:

```python
async def _index_file(
    self,
    file_input: FileInput,
    options: IndexingOptions,
) -> FileIndexingResult:
    """
    Index a single file through the pipeline.

    EPIC-12 Story 12.2: Wrapped database operations in transaction.
    """
    start_time = datetime.now()

    try:
        # Steps 1-4: Cache invalidation, lookup, chunking, embedding
        # (UNCHANGED - these steps don't need transactions)

        # ... (existing code for steps 1-4) ...

        # Step 5-6: ATOMIC DATABASE + CACHE OPERATION
        chunks_created = 0

        try:
            # EPIC-12 Story 12.2: Wrap database operations in transaction
            async with self.engine.begin() as conn:
                # Step 5: Batch insert chunks (atomic)
                if chunks_to_insert:
                    chunks_created = await self.chunk_repository.add_batch(
                        chunks_to_insert,
                        connection=conn  # ← Pass transaction
                    )

                    self.logger.info(
                        f"Inserted {chunks_created} chunks for {file_input.path} (transaction pending commit)"
                    )

                # Transaction auto-commits here if no exception

            # Step 6: Cache population AFTER successful commit
            # EPIC-12 Story 12.2: Cache populated only after DB commit succeeds
            if chunks_created > 0 and self.chunk_cache:
                try:
                    # Serialize chunks for cache
                    serialized_chunks = [
                        self.chunk_cache._serialize_chunk(chunk)
                        for chunk in chunks_to_insert[:chunks_created]
                    ]

                    await self.chunk_cache.put_chunks(
                        file_input.path,
                        file_input.content,
                        serialized_chunks
                    )

                    self.logger.info(
                        f"Populated cache for {file_input.path} with {len(serialized_chunks)} chunks"
                    )

                except Exception as cache_error:
                    # Cache population failure is NOT fatal
                    # (Database operation already succeeded)
                    self.logger.warning(
                        f"Cache population failed for {file_input.path}: {cache_error}"
                    )

        except Exception as e:
            # Transaction already rolled back
            # Cache not populated (correct behavior)
            self.logger.error(
                f"File indexing transaction failed for {file_input.path}: {e}",
                exc_info=True
            )

            return FileIndexingResult(
                file_path=file_input.path,
                success=False,
                chunks_created=0,
                nodes_created=0,
                edges_created=0,
                processing_time_ms=0,
                error=f"Transaction failed: {str(e)}"
            )

        # Calculate processing time
        end_time = datetime.now()
        processing_time_ms = (end_time - start_time).total_seconds() * 1000

        # Return success result
        return FileIndexingResult(
            file_path=file_input.path,
            success=True,
            chunks_created=chunks_created,
            nodes_created=0,  # Graph built separately
            edges_created=0,
            processing_time_ms=processing_time_ms
        )

    except Exception as e:
        self.logger.error(
            f"Unexpected error indexing {file_input.path}: {e}",
            exc_info=True
        )

        return FileIndexingResult(
            file_path=file_input.path,
            success=False,
            chunks_created=0,
            nodes_created=0,
            edges_created=0,
            processing_time_ms=0,
            error=str(e)
        )
```

---

### Step 2.2: Update GraphConstructionService

**File**: `api/services/graph_construction_service.py`

**Modify `build_graph_for_repository()` (lines 76-200)**:

```python
async def build_graph_for_repository(
    self,
    repository: str,
    language: str = "python"
) -> GraphStats:
    """
    Build complete graph for a repository.

    EPIC-12 Story 12.2: Wrapped graph operations in transaction.
    """
    start_time = time.time()
    self.logger.info(f"Building graph for repository '{repository}', language '{language}'")

    # Step 1: Get all chunks for repository
    chunks = await self._get_chunks_for_repository(repository, language)
    self.logger.info(f"Found {len(chunks)} chunks for repository '{repository}'")

    if not chunks:
        self.logger.warning(f"No chunks found for repository '{repository}'")
        return GraphStats(
            repository=repository,
            total_nodes=0,
            total_edges=0,
            nodes_by_type={},
            edges_by_type={},
            construction_time_seconds=time.time() - start_time,
            resolution_accuracy=None
        )

    # Steps 2-4: ATOMIC GRAPH CONSTRUCTION
    try:
        # EPIC-12 Story 12.2: Wrap graph construction in transaction
        async with self.engine.begin() as conn:
            # Step 2: Create nodes from chunks (atomic)
            chunk_to_node = await self._create_nodes_from_chunks(
                chunks,
                connection=conn  # ← Pass transaction
            )
            self.logger.info(f"Created {len(chunk_to_node)} nodes (transaction pending)")

            # Step 3: Create call edges (atomic)
            call_edges = await self._create_all_call_edges(
                chunks,
                chunk_to_node,
                connection=conn  # ← Pass transaction
            )

            # Step 4: Create import edges (atomic)
            import_edges = await self._create_all_import_edges(
                chunks,
                chunk_to_node,
                connection=conn  # ← Pass transaction
            )

            total_edges = len(call_edges) + len(import_edges)
            self.logger.info(
                f"Created {len(call_edges)} call edges + {len(import_edges)} import edges (transaction pending)"
            )

            # Transaction auto-commits here

        # Compute statistics AFTER successful commit
        construction_time = time.time() - start_time

        # Count nodes by type
        nodes_by_type = defaultdict(int)
        for node in chunk_to_node.values():
            nodes_by_type[node.node_type] += 1

        # Count edges by type
        edges_by_type = {
            "calls": len(call_edges),
            "imports": len(import_edges),
        }

        # Compute resolution accuracy
        total_calls = sum(
            len(chunk.metadata.get("calls", []))
            for chunk in chunks
            if chunk.metadata
        )
        resolution_accuracy = (len(call_edges) / total_calls * 100) if total_calls > 0 else 100.0

        stats = GraphStats(
            repository=repository,
            total_nodes=len(chunk_to_node),
            total_edges=total_edges,
            nodes_by_type=dict(nodes_by_type),
            edges_by_type=edges_by_type,
            construction_time_seconds=construction_time,
            resolution_accuracy=resolution_accuracy
        )

        self.logger.info(
            f"Graph construction complete: {stats.total_nodes} nodes, "
            f"{stats.total_edges} edges, {stats.resolution_accuracy:.1f}% resolution accuracy, "
            f"{stats.construction_time_seconds:.2f}s"
        )

        return stats

    except Exception as e:
        # Transaction already rolled back
        self.logger.error(
            f"Graph construction transaction failed for repository '{repository}': {e}",
            exc_info=True
        )
        raise
```

**Modify `_create_nodes_from_chunks()` (lines 189-243)**:

```python
async def _create_nodes_from_chunks(
    self,
    chunks: List[CodeChunkModel],
    connection: Optional[AsyncConnection] = None  # ← NEW parameter
) -> Dict[uuid.UUID, NodeModel]:
    """
    Create node for each function/class chunk.

    EPIC-12 Story 12.2: Added connection parameter for transaction support.
    """
    chunk_to_node: Dict[uuid.UUID, NodeModel] = {}

    for chunk in chunks:
        # Only create nodes for functions, methods, classes
        if chunk.chunk_type not in ["function", "method", "class"]:
            continue

        # Determine node type
        node_type = chunk.chunk_type

        # Use chunk name as label (fallback to "anonymous")
        label = chunk.name if chunk.name else "anonymous"

        # Build node properties from chunk metadata
        properties = {
            "chunk_id": str(chunk.id),
            "file_path": chunk.file_path,
            "language": chunk.language,
            "repository": chunk.repository,  # CRITICAL for filtering
            "signature": chunk.metadata.get("signature", ""),
            "complexity": chunk.metadata.get("complexity", {}),
            "is_builtin": False,
            "is_stdlib": False,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
        }

        # Create node (uses same transaction)
        try:
            node = await self.node_repo.create_code_node(
                node_type=node_type,
                label=label,
                chunk_id=chunk.id,
                file_path=chunk.file_path,
                metadata=properties,
                connection=connection  # ← Pass transaction
            )
            chunk_to_node[chunk.id] = node
            self.logger.debug(f"Created node {node.node_id} for chunk {chunk.id} ({label})")
        except Exception as e:
            self.logger.error(f"Failed to create node for chunk {chunk.id}: {e}")
            # Re-raise to trigger transaction rollback
            raise

    return chunk_to_node
```

**Similar updates for `_create_call_edges()` and `_create_import_edges()` methods.**

---

## Phase 3: Route Layer (1 hour)

### Step 3.1: Update Repository Deletion Routes

**File**: `api/routes/code_indexing_routes.py`

**Replace raw SQL deletion (lines 397-451) with repository methods:**

```python
@router.delete("/repositories/{repository}")
async def delete_repository(
    repository: str,
    chunk_repo: CodeChunkRepository = Depends(get_code_chunk_repository),
    node_repo: NodeRepository = Depends(get_node_repository),
    edge_repo: EdgeRepository = Depends(get_edge_repository),
    chunk_cache: CascadeCache = Depends(get_cascade_cache),
    engine: AsyncEngine = Depends(get_engine)
):
    """
    Delete all data for a repository (atomic).

    EPIC-12 Story 12.2: Uses repositories with transaction for atomicity.
    """
    try:
        logger.info(f"Deleting repository '{repository}'")

        # ATOMIC DELETION using repositories
        async with engine.begin() as conn:
            # Delete in dependency order: edges → nodes → chunks
            deleted_edges = await edge_repo.delete_by_repository(
                repository,
                connection=conn
            )
            deleted_nodes = await node_repo.delete_by_repository(
                repository,
                connection=conn
            )
            deleted_chunks = await chunk_repo.delete_by_repository(
                repository,
                connection=conn
            )

            logger.info(
                f"Deleted repository '{repository}': "
                f"{deleted_chunks} chunks, {deleted_nodes} nodes, {deleted_edges} edges"
            )

        # Cache invalidation AFTER successful commit
        try:
            await chunk_cache.invalidate_repository(repository)
            logger.info(f"Invalidated cache for repository '{repository}'")
        except Exception as cache_error:
            # Cache invalidation failure is NOT fatal
            logger.warning(f"Cache invalidation failed: {cache_error}")

        return {
            "status": "success",
            "repository": repository,
            "deleted": {
                "chunks": deleted_chunks,
                "nodes": deleted_nodes,
                "edges": deleted_edges
            }
        }

    except Exception as e:
        logger.error(f"Failed to delete repository {repository}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
```

**Similar update for `ui_routes.py:code_repository_delete()`**

---

## Phase 4: Testing (2-3 hours)

### Step 4.1: Integration Tests

**Create**: `tests/integration/test_transactional_indexing.py`

```python
"""
Integration tests for transactional indexing.

EPIC-12 Story 12.2: Transaction Boundaries
"""

import pytest
from unittest.mock import patch, AsyncMock

from services.code_indexing_service import (
    CodeIndexingService,
    FileInput,
    IndexingOptions
)


@pytest.mark.anyio
async def test_file_indexing_rollback_on_embedding_failure(
    clean_db,
    mock_chunking_service,
    mock_metadata_service,
    mock_embedding_service,
    mock_graph_service,
    test_chunk_repo,
):
    """If embedding fails, chunks NOT stored."""

    # Create indexing service
    indexing_service = CodeIndexingService(
        engine=clean_db,
        chunking_service=mock_chunking_service,
        metadata_service=mock_metadata_service,
        embedding_service=mock_embedding_service,
        graph_service=mock_graph_service,
        chunk_repository=test_chunk_repo
    )

    # Mock embedding to fail
    mock_embedding_service.generate_embeddings_batch = AsyncMock(
        side_effect=Exception("Embedding failed")
    )

    # Attempt to index file (should fail)
    file_input = FileInput(
        path="test.py",
        content="def foo(): pass",
        language="python"
    )
    options = IndexingOptions(repository="test-repo")

    result = await indexing_service._index_file(file_input, options)

    # Verify indexing failed
    assert result.success is False
    assert "Embedding failed" in result.error

    # Verify chunks NOT in database (transaction rolled back)
    chunks = await test_chunk_repo.get_by_file_path("test.py")
    assert len(chunks) == 0


@pytest.mark.anyio
async def test_graph_construction_rollback_on_failure(
    clean_db,
    mock_graph_service,
    code_chunk_repo,
    node_repository,
    edge_repository
):
    """If graph construction fails, NO partial graph."""

    # Create some chunks first
    from models.code_chunk_models import CodeChunkCreate, ChunkType

    for i in range(10):
        chunk_data = CodeChunkCreate(
            file_path="test.py",
            language="python",
            chunk_type=ChunkType.FUNCTION,
            name=f"func_{i}",
            source_code=f"def func_{i}(): pass",
            start_line=i,
            end_line=i,
            metadata={},
            repository="test-repo"
        )
        await code_chunk_repo.add(chunk_data)

    # Mock node creation to fail on 5th node
    call_count = 0
    original_create = node_repository.create_code_node

    async def mock_create(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 5:
            raise Exception("Node creation failed")
        return await original_create(*args, **kwargs)

    with patch.object(node_repository, 'create_code_node', side_effect=mock_create):
        with pytest.raises(Exception, match="Node creation failed"):
            await mock_graph_service.build_graph_for_repository("test-repo")

    # Verify NO nodes in database (all rolled back)
    # Query nodes by repository
    query = text("""
        SELECT * FROM nodes
        WHERE properties->>'repository' = :repository
    """)
    async with clean_db.connect() as conn:
        result = await conn.execute(query, {"repository": "test-repo"})
        nodes = result.fetchall()

    assert len(nodes) == 0  # All rolled back


@pytest.mark.anyio
async def test_cache_populated_after_successful_commit(
    clean_db,
    mock_chunking_service,
    mock_metadata_service,
    mock_embedding_service,
    mock_graph_service,
    test_chunk_repo
):
    """Cache populated only after successful database commit."""

    from services.caches.cascade_cache import CascadeCache
    from services.caches import L1Cache, RedisCache

    # Create real cache
    l1 = L1Cache(max_size_mb=10)
    l2 = RedisCache(redis_url="redis://redis:6379/0")
    cache = CascadeCache(l1=l1, l2=l2)

    # Create indexing service
    indexing_service = CodeIndexingService(
        engine=clean_db,
        chunking_service=mock_chunking_service,
        metadata_service=mock_metadata_service,
        embedding_service=mock_embedding_service,
        graph_service=mock_graph_service,
        chunk_repository=test_chunk_repo,
        chunk_cache=cache
    )

    # Index file successfully
    file_input = FileInput(
        path="test.py",
        content="def foo(): pass",
        language="python"
    )
    options = IndexingOptions(repository="test-repo")

    result = await indexing_service._index_file(file_input, options)

    # Verify success
    assert result.success is True
    assert result.chunks_created > 0

    # Verify cache has the chunks
    cached = cache.get(file_input.path, file_input.content)
    assert cached is not None
    assert len(cached) > 0


@pytest.mark.anyio
async def test_repository_deletion_atomic(
    clean_db,
    code_chunk_repo,
    node_repository,
    edge_repository
):
    """Repository deletion is atomic."""

    # Create data for repo1
    from models.code_chunk_models import CodeChunkCreate, ChunkType

    for i in range(5):
        chunk_data = CodeChunkCreate(
            file_path="test.py",
            language="python",
            chunk_type=ChunkType.FUNCTION,
            name=f"func_{i}",
            source_code=f"def func_{i}(): pass",
            start_line=i,
            end_line=i,
            metadata={},
            repository="repo1"
        )
        await code_chunk_repo.add(chunk_data)

    # Delete atomically
    async with clean_db.begin() as conn:
        deleted_chunks = await code_chunk_repo.delete_by_repository(
            "repo1",
            connection=conn
        )
        deleted_nodes = await node_repository.delete_by_repository(
            "repo1",
            connection=conn
        )
        deleted_edges = await edge_repository.delete_by_repository(
            "repo1",
            connection=conn
        )

    # Verify all deleted
    assert deleted_chunks == 5
    chunks = await code_chunk_repo.get_by_file_path("test.py")
    assert len(chunks) == 0
```

**Run Integration Tests**:
```bash
docker compose exec api pytest tests/integration/test_transactional_indexing.py -v
```

---

## Testing Checklist

- [ ] Repository unit tests (10 tests)
- [ ] Service integration tests (8 tests)
- [ ] Route integration tests (5 tests)
- [ ] Performance regression tests (2 tests)
- [ ] Backward compatibility tests (3 tests)

**Total**: 28 tests

---

## Acceptance Criteria Checklist

- [ ] All repositories support `connection` parameter
- [ ] `_execute_query()` accepts optional connection
- [ ] Bulk delete methods added
- [ ] CodeIndexingService uses transactions
- [ ] GraphConstructionService uses transactions
- [ ] Routes migrated from raw SQL to repositories
- [ ] Cache coordinated with transactions
- [ ] 28 tests passing (100%)
- [ ] No performance regression
- [ ] Documentation complete

---

## Rollback Plan

If issues arise:

1. **Repository layer**: Revert individual repository (backward compatible)
2. **Service layer**: Remove transaction wrapping (services still work)
3. **Route layer**: Revert to raw SQL temporarily

**Low Risk**: Optional parameter ensures backward compatibility.

---

## Completion Criteria

- [ ] All code implemented and tested
- [ ] 28 tests passing (100%)
- [ ] Performance benchmarks show 10x improvement for bulk ops
- [ ] Code review complete
- [ ] Documentation updated
- [ ] Completion report created

---

**Status**: 📋 READY FOR IMPLEMENTATION

**Next**: Begin Phase 1 - Repository Layer

🤖 Generated with [Claude Code](https://claude.com/claude-code)
