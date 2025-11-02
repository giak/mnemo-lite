# Rich Code Metadata Extraction & Graph Enhancement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform MnemoLite into a comprehensive code intelligence system with rich metadata extraction (calls, imports, signatures, metrics), optimized storage in dedicated PostgreSQL tables, and enhanced graph visualization.

**Architecture:** 4-phase pipeline (Chunking → Embeddings → Metadata Extraction → Graph + Metrics). Uses minimalst 2-table approach: `detailed_metadata` (JSONB with GIN indexes) + `computed_metrics` (normalized columns). Metadata extraction integrates existing TypeScriptMetadataExtractor with context enrichment. Graph construction enhanced with PageRank-based importance scoring.

**Tech Stack:** Python 3.12, FastAPI, PostgreSQL 18, tree-sitter, Vue 3, G6 graph visualization, asyncio

---

## Phase 1: Database Schema & Migration

### Task 1.1: Create Database Migration File

**Files:**
- Create: `db/migrations/v9_to_v10_rich_metadata.sql`

**Step 1: Write migration SQL**

```sql
-- Migration: v9 to v10 - Rich Metadata & Metrics Tables
-- Date: 2025-11-02
-- Description: Add dedicated tables for detailed metadata and computed metrics

BEGIN;

-- Table 1: Detailed metadata (flexible JSONB storage)
CREATE TABLE IF NOT EXISTS detailed_metadata (
    metadata_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id UUID NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    chunk_id UUID NOT NULL REFERENCES code_chunks(id) ON DELETE CASCADE,

    -- Metadata payload (calls, imports, signature, context)
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Version tracking
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(node_id, version)
);

-- Indexes for detailed_metadata
CREATE INDEX idx_detailed_metadata_node ON detailed_metadata(node_id);
CREATE INDEX idx_detailed_metadata_chunk ON detailed_metadata(chunk_id);
CREATE INDEX idx_detailed_metadata_version ON detailed_metadata(version);
CREATE INDEX idx_detailed_metadata_gin ON detailed_metadata USING GIN (metadata);

-- Table 2: Computed metrics (normalized columns for performance)
CREATE TABLE IF NOT EXISTS computed_metrics (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id UUID NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    chunk_id UUID NOT NULL REFERENCES code_chunks(id) ON DELETE CASCADE,
    repository TEXT NOT NULL,

    -- Complexity metrics
    cyclomatic_complexity INTEGER DEFAULT 0,
    cognitive_complexity INTEGER DEFAULT 0,
    lines_of_code INTEGER DEFAULT 0,

    -- Coupling metrics
    afferent_coupling INTEGER DEFAULT 0,  -- Incoming dependencies
    efferent_coupling INTEGER DEFAULT 0,  -- Outgoing dependencies

    -- Graph centrality (calculated)
    pagerank_score FLOAT,
    betweenness_centrality FLOAT,

    -- Version tracking
    version INTEGER DEFAULT 1,
    computed_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(node_id, version)
);

-- Indexes for computed_metrics
CREATE INDEX idx_computed_metrics_node ON computed_metrics(node_id);
CREATE INDEX idx_computed_metrics_chunk ON computed_metrics(chunk_id);
CREATE INDEX idx_computed_metrics_repository ON computed_metrics(repository);
CREATE INDEX idx_computed_metrics_version ON computed_metrics(version);
CREATE INDEX idx_computed_metrics_complexity ON computed_metrics(cyclomatic_complexity DESC);
CREATE INDEX idx_computed_metrics_pagerank ON computed_metrics(pagerank_score DESC NULLS LAST);

-- Table 3: Edge weights (relationship strength)
CREATE TABLE IF NOT EXISTS edge_weights (
    weight_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    edge_id UUID NOT NULL REFERENCES edges(edge_id) ON DELETE CASCADE,

    -- Weight components
    call_count INTEGER DEFAULT 1,  -- Unique calls (not loop-multiplied)
    importance_score FLOAT DEFAULT 1.0,  -- 0-1 based on PageRank propagation
    is_critical_path BOOLEAN DEFAULT FALSE,

    -- Version tracking
    version INTEGER DEFAULT 1,
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(edge_id, version)
);

-- Indexes for edge_weights
CREATE INDEX idx_edge_weights_edge ON edge_weights(edge_id);
CREATE INDEX idx_edge_weights_version ON edge_weights(version);
CREATE INDEX idx_edge_weights_importance ON edge_weights(importance_score DESC);

-- Add columns to existing edges table (optimization)
ALTER TABLE edges
    ADD COLUMN IF NOT EXISTS weight FLOAT DEFAULT 1.0,
    ADD COLUMN IF NOT EXISTS is_external BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_edges_weight ON edges(weight DESC);
CREATE INDEX IF NOT EXISTS idx_edges_external ON edges(is_external);

COMMIT;
```

**Step 2: Verify migration syntax**

Run: `docker exec -i mnemo-postgres psql -U mnemo -d mnemolite --dry-run < db/migrations/v9_to_v10_rich_metadata.sql 2>&1 | head -20`

Expected: No syntax errors

**Step 3: Apply migration**

```bash
docker exec -i mnemo-postgres psql -U mnemo -d mnemolite < db/migrations/v9_to_v10_rich_metadata.sql
```

Expected: All CREATE TABLE and CREATE INDEX succeed

**Step 4: Verify tables created**

Run:
```bash
docker exec -i mnemo-postgres psql -U mnemo -d mnemolite -c "\d detailed_metadata"
docker exec -i mnemo-postgres psql -U mnemo -d mnemolite -c "\d computed_metrics"
docker exec -i mnemo-postgres psql -U mnemo -d mnemolite -c "\d edge_weights"
```

Expected: All tables exist with correct schema

**Step 5: Commit migration**

```bash
git add db/migrations/v9_to_v10_rich_metadata.sql
git commit -m "feat(db): Add rich metadata tables (detailed_metadata, computed_metrics, edge_weights)"
```

---

## Phase 2: Repository Layer (Database Access)

### Task 2.1: Create DetailedMetadataRepository

**Files:**
- Create: `api/db/repositories/detailed_metadata_repository.py`

**Step 1: Write test for metadata insertion**

Create: `tests/db/repositories/test_detailed_metadata_repository.py`

```python
import pytest
import uuid
from db.repositories.detailed_metadata_repository import DetailedMetadataRepository
from models.metadata_models import DetailedMetadata


@pytest.mark.asyncio
async def test_create_detailed_metadata(test_db_engine, sample_node_id, sample_chunk_id):
    """Test creating detailed metadata for a node."""
    repo = DetailedMetadataRepository(test_db_engine)

    metadata_payload = {
        "calls": ["validateEmail", "createUser"],
        "imports": ["./utils.validator", "express"],
        "signature": {
            "parameters": [{"name": "email", "type": "string"}],
            "return_type": "Promise<User>"
        },
        "context": {
            "is_async": True,
            "decorators": ["@Injectable()"]
        }
    }

    metadata = await repo.create(
        node_id=sample_node_id,
        chunk_id=sample_chunk_id,
        metadata=metadata_payload,
        version=1
    )

    assert metadata.node_id == sample_node_id
    assert metadata.metadata["calls"] == ["validateEmail", "createUser"]
    assert metadata.metadata["signature"]["return_type"] == "Promise<User>"
    assert metadata.version == 1


@pytest.mark.asyncio
async def test_get_latest_metadata_by_node(test_db_engine, sample_node_id):
    """Test retrieving latest version of metadata."""
    repo = DetailedMetadataRepository(test_db_engine)

    # Create v1
    await repo.create(sample_node_id, sample_chunk_id, {"calls": ["old"]}, version=1)

    # Create v2
    metadata_v2 = await repo.create(sample_node_id, sample_chunk_id, {"calls": ["new"]}, version=2)

    # Get latest
    latest = await repo.get_latest_by_node(sample_node_id)

    assert latest.version == 2
    assert latest.metadata["calls"] == ["new"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/db/repositories/test_detailed_metadata_repository.py -v`

Expected: ImportError (module doesn't exist yet)

**Step 3: Create metadata models**

Create: `api/models/metadata_models.py`

```python
"""
Data models for rich metadata and metrics.
"""
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class DetailedMetadata(BaseModel):
    """Detailed metadata for code nodes (JSONB storage)."""
    metadata_id: UUID
    node_id: UUID
    chunk_id: UUID
    metadata: Dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ComputedMetrics(BaseModel):
    """Computed code quality metrics."""
    metric_id: UUID
    node_id: UUID
    chunk_id: UUID
    repository: str

    cyclomatic_complexity: int = 0
    cognitive_complexity: int = 0
    lines_of_code: int = 0

    afferent_coupling: int = 0
    efferent_coupling: int = 0

    pagerank_score: Optional[float] = None
    betweenness_centrality: Optional[float] = None

    version: int = 1
    computed_at: datetime

    class Config:
        from_attributes = True


class EdgeWeight(BaseModel):
    """Edge weight and importance metrics."""
    weight_id: UUID
    edge_id: UUID

    call_count: int = 1
    importance_score: float = 1.0
    is_critical_path: bool = False

    version: int = 1
    updated_at: datetime

    class Config:
        from_attributes = True
```

**Step 4: Implement DetailedMetadataRepository**

Create: `api/db/repositories/detailed_metadata_repository.py`

```python
"""
Repository for detailed_metadata table operations.
"""
import logging
from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import text
from models.metadata_models import DetailedMetadata

logger = logging.getLogger(__name__)


class DetailedMetadataRepository:
    """Repository for CRUD operations on detailed_metadata table."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def create(
        self,
        node_id: UUID,
        chunk_id: UUID,
        metadata: dict,
        version: int = 1,
        connection=None
    ) -> DetailedMetadata:
        """
        Create detailed metadata entry.

        Args:
            node_id: Node UUID
            chunk_id: Code chunk UUID
            metadata: Metadata payload (calls, imports, signature, context)
            version: Version number (default 1)
            connection: Optional external connection for transaction

        Returns:
            DetailedMetadata instance
        """
        query = text("""
            INSERT INTO detailed_metadata (node_id, chunk_id, metadata, version)
            VALUES (:node_id, :chunk_id, :metadata::jsonb, :version)
            RETURNING metadata_id, node_id, chunk_id, metadata, version, created_at, updated_at
        """)

        params = {
            "node_id": str(node_id),
            "chunk_id": str(chunk_id),
            "metadata": str(metadata).replace("'", '"'),  # Convert dict to JSON string
            "version": version
        }

        if connection:
            result = await connection.execute(query, params)
            row = result.fetchone()
        else:
            async with self.engine.begin() as conn:
                result = await conn.execute(query, params)
                row = result.fetchone()

        return DetailedMetadata(
            metadata_id=row[0],
            node_id=row[1],
            chunk_id=row[2],
            metadata=row[3],
            version=row[4],
            created_at=row[5],
            updated_at=row[6]
        )

    async def get_latest_by_node(self, node_id: UUID) -> Optional[DetailedMetadata]:
        """
        Get latest version of metadata for a node.

        Args:
            node_id: Node UUID

        Returns:
            DetailedMetadata instance or None
        """
        query = text("""
            SELECT metadata_id, node_id, chunk_id, metadata, version, created_at, updated_at
            FROM detailed_metadata
            WHERE node_id = :node_id
            ORDER BY version DESC
            LIMIT 1
        """)

        async with self.engine.connect() as conn:
            result = await conn.execute(query, {"node_id": str(node_id)})
            row = result.fetchone()

        if not row:
            return None

        return DetailedMetadata(
            metadata_id=row[0],
            node_id=row[1],
            chunk_id=row[2],
            metadata=row[3],
            version=row[4],
            created_at=row[5],
            updated_at=row[6]
        )

    async def get_by_repository(self, repository: str, version: int = 1) -> List[DetailedMetadata]:
        """
        Get all metadata entries for a repository.

        Args:
            repository: Repository name
            version: Version number (default 1 = latest indexed version)

        Returns:
            List of DetailedMetadata instances
        """
        query = text("""
            SELECT dm.metadata_id, dm.node_id, dm.chunk_id, dm.metadata, dm.version, dm.created_at, dm.updated_at
            FROM detailed_metadata dm
            JOIN nodes n ON dm.node_id = n.node_id
            WHERE n.properties->>'repository' = :repository
              AND dm.version = :version
        """)

        async with self.engine.connect() as conn:
            result = await conn.execute(query, {"repository": repository, "version": version})
            rows = result.fetchall()

        return [
            DetailedMetadata(
                metadata_id=row[0],
                node_id=row[1],
                chunk_id=row[2],
                metadata=row[3],
                version=row[4],
                created_at=row[5],
                updated_at=row[6]
            )
            for row in rows
        ]
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/db/repositories/test_detailed_metadata_repository.py -v`

Expected: All tests PASS

**Step 6: Commit**

```bash
git add api/db/repositories/detailed_metadata_repository.py api/models/metadata_models.py tests/db/repositories/test_detailed_metadata_repository.py
git commit -m "feat(db): Add DetailedMetadataRepository with JSONB storage"
```

### Task 2.2: Create ComputedMetricsRepository

**Files:**
- Create: `api/db/repositories/computed_metrics_repository.py`
- Create: `tests/db/repositories/test_computed_metrics_repository.py`

**Step 1: Write test**

```python
import pytest
import uuid
from db.repositories.computed_metrics_repository import ComputedMetricsRepository


@pytest.mark.asyncio
async def test_create_computed_metrics(test_db_engine, sample_node_id, sample_chunk_id):
    """Test creating computed metrics."""
    repo = ComputedMetricsRepository(test_db_engine)

    metrics = await repo.create(
        node_id=sample_node_id,
        chunk_id=sample_chunk_id,
        repository="test_repo",
        cyclomatic_complexity=5,
        cognitive_complexity=3,
        lines_of_code=50,
        afferent_coupling=2,
        efferent_coupling=4
    )

    assert metrics.cyclomatic_complexity == 5
    assert metrics.afferent_coupling == 2
    assert metrics.repository == "test_repo"


@pytest.mark.asyncio
async def test_update_coupling_metrics(test_db_engine, sample_node_id):
    """Test updating coupling metrics after graph analysis."""
    repo = ComputedMetricsRepository(test_db_engine)

    # Create initial
    metrics = await repo.create(sample_node_id, sample_chunk_id, "test_repo")

    # Update coupling
    updated = await repo.update_coupling(
        node_id=sample_node_id,
        afferent_coupling=10,
        efferent_coupling=5
    )

    assert updated.afferent_coupling == 10
    assert updated.efferent_coupling == 5
```

**Step 2: Run test to verify failure**

Run: `pytest tests/db/repositories/test_computed_metrics_repository.py -v`

Expected: ImportError

**Step 3: Implement repository**

```python
"""
Repository for computed_metrics table operations.
"""
import logging
from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import text
from models.metadata_models import ComputedMetrics

logger = logging.getLogger(__name__)


class ComputedMetricsRepository:
    """Repository for computed code quality metrics."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def create(
        self,
        node_id: UUID,
        chunk_id: UUID,
        repository: str,
        cyclomatic_complexity: int = 0,
        cognitive_complexity: int = 0,
        lines_of_code: int = 0,
        afferent_coupling: int = 0,
        efferent_coupling: int = 0,
        version: int = 1,
        connection=None
    ) -> ComputedMetrics:
        """Create computed metrics entry."""
        query = text("""
            INSERT INTO computed_metrics
            (node_id, chunk_id, repository, cyclomatic_complexity, cognitive_complexity,
             lines_of_code, afferent_coupling, efferent_coupling, version)
            VALUES (:node_id, :chunk_id, :repository, :cc, :cognitive, :loc, :ac, :ec, :version)
            RETURNING metric_id, node_id, chunk_id, repository, cyclomatic_complexity,
                      cognitive_complexity, lines_of_code, afferent_coupling, efferent_coupling,
                      pagerank_score, betweenness_centrality, version, computed_at
        """)

        params = {
            "node_id": str(node_id),
            "chunk_id": str(chunk_id),
            "repository": repository,
            "cc": cyclomatic_complexity,
            "cognitive": cognitive_complexity,
            "loc": lines_of_code,
            "ac": afferent_coupling,
            "ec": efferent_coupling,
            "version": version
        }

        if connection:
            result = await connection.execute(query, params)
            row = result.fetchone()
        else:
            async with self.engine.begin() as conn:
                result = await conn.execute(query, params)
                row = result.fetchone()

        return ComputedMetrics(
            metric_id=row[0],
            node_id=row[1],
            chunk_id=row[2],
            repository=row[3],
            cyclomatic_complexity=row[4],
            cognitive_complexity=row[5],
            lines_of_code=row[6],
            afferent_coupling=row[7],
            efferent_coupling=row[8],
            pagerank_score=row[9],
            betweenness_centrality=row[10],
            version=row[11],
            computed_at=row[12]
        )

    async def update_coupling(
        self,
        node_id: UUID,
        afferent_coupling: int,
        efferent_coupling: int,
        version: int = 1
    ) -> ComputedMetrics:
        """Update coupling metrics after graph construction."""
        query = text("""
            UPDATE computed_metrics
            SET afferent_coupling = :ac,
                efferent_coupling = :ec,
                computed_at = NOW()
            WHERE node_id = :node_id AND version = :version
            RETURNING metric_id, node_id, chunk_id, repository, cyclomatic_complexity,
                      cognitive_complexity, lines_of_code, afferent_coupling, efferent_coupling,
                      pagerank_score, betweenness_centrality, version, computed_at
        """)

        async with self.engine.begin() as conn:
            result = await conn.execute(query, {
                "node_id": str(node_id),
                "ac": afferent_coupling,
                "ec": efferent_coupling,
                "version": version
            })
            row = result.fetchone()

        return ComputedMetrics(
            metric_id=row[0],
            node_id=row[1],
            chunk_id=row[2],
            repository=row[3],
            cyclomatic_complexity=row[4],
            cognitive_complexity=row[5],
            lines_of_code=row[6],
            afferent_coupling=row[7],
            efferent_coupling=row[8],
            pagerank_score=row[9],
            betweenness_centrality=row[10],
            version=row[11],
            computed_at=row[12]
        )

    async def get_by_repository(self, repository: str, version: int = 1) -> List[ComputedMetrics]:
        """Get all metrics for a repository."""
        query = text("""
            SELECT metric_id, node_id, chunk_id, repository, cyclomatic_complexity,
                   cognitive_complexity, lines_of_code, afferent_coupling, efferent_coupling,
                   pagerank_score, betweenness_centrality, version, computed_at
            FROM computed_metrics
            WHERE repository = :repository AND version = :version
        """)

        async with self.engine.connect() as conn:
            result = await conn.execute(query, {"repository": repository, "version": version})
            rows = result.fetchall()

        return [
            ComputedMetrics(
                metric_id=row[0],
                node_id=row[1],
                chunk_id=row[2],
                repository=row[3],
                cyclomatic_complexity=row[4],
                cognitive_complexity=row[5],
                lines_of_code=row[6],
                afferent_coupling=row[7],
                efferent_coupling=row[8],
                pagerank_score=row[9],
                betweenness_centrality=row[10],
                version=row[11],
                computed_at=row[12]
            )
            for row in rows
        ]
```

**Step 4: Run tests**

Run: `pytest tests/db/repositories/test_computed_metrics_repository.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add api/db/repositories/computed_metrics_repository.py tests/db/repositories/test_computed_metrics_repository.py
git commit -m "feat(db): Add ComputedMetricsRepository for code quality metrics"
```

---

## Phase 3: Metadata Extraction Service Enhancement

### Task 3.1: Enhance TypeScriptMetadataExtractor with Context

**Files:**
- Modify: `api/services/metadata_extractors/typescript_extractor.py`

**Step 1: Add test for enriched metadata extraction**

Create: `tests/services/test_typescript_metadata_enriched.py`

```python
import pytest
from services.metadata_extractors.typescript_extractor import TypeScriptMetadataExtractor
from tree_sitter_language_pack import get_parser


@pytest.mark.asyncio
async def test_extract_metadata_with_context():
    """Test metadata extraction includes call context."""
    source_code = """
async function createUser(email: string, name: string): Promise<User> {
    if (email) {
        validateEmail(email);
    }

    for (let i = 0; i < 10; i++) {
        processItem(i);
    }

    return await saveUser(email, name);
}
"""

    parser = get_parser("typescript")
    tree = parser.parse(bytes(source_code, "utf8"))

    # Find function node
    function_node = tree.root_node.children[0]

    extractor = TypeScriptMetadataExtractor("typescript")
    metadata = await extractor.extract_metadata(source_code, function_node, tree)

    # Check calls extracted
    assert "validateEmail" in metadata["calls"]
    assert "processItem" in metadata["calls"]
    assert "saveUser" in metadata["calls"]

    # Check enriched context
    assert "call_contexts" in metadata
    contexts = metadata["call_contexts"]

    # validateEmail context
    validate_ctx = next(c for c in contexts if c["call_name"] == "validateEmail")
    assert validate_ctx["is_conditional"] == True
    assert validate_ctx["is_loop"] == False
    assert validate_ctx["scope_type"] == "function"
    assert validate_ctx["scope_name"] == "createUser"

    # processItem context
    process_ctx = next(c for c in contexts if c["call_name"] == "processItem")
    assert process_ctx["is_loop"] == True
    assert process_ctx["is_conditional"] == False

    # Check signature
    assert "signature" in metadata
    sig = metadata["signature"]
    assert sig["function_name"] == "createUser"
    assert sig["is_async"] == True
    assert sig["return_type"] == "Promise<User>"
    assert len(sig["parameters"]) == 2
    assert sig["parameters"][0] == {"name": "email", "type": "string", "is_optional": False}


@pytest.mark.asyncio
async def test_extract_complexity_metrics():
    """Test cyclomatic complexity calculation."""
    source_code = """
function complexFunction(x: number): number {
    if (x > 10) {
        return x * 2;
    } else if (x > 5) {
        return x + 1;
    } else {
        return x;
    }

    for (let i = 0; i < x; i++) {
        process(i);
    }
}
"""

    parser = get_parser("typescript")
    tree = parser.parse(bytes(source_code, "utf8"))
    function_node = tree.root_node.children[0]

    extractor = TypeScriptMetadataExtractor("typescript")
    metadata = await extractor.extract_metadata(source_code, function_node, tree)

    assert "complexity" in metadata
    # Cyclomatic = 1 (base) + 2 (if/else if) + 1 (for) = 4
    assert metadata["complexity"]["cyclomatic"] == 4
    assert metadata["complexity"]["lines_of_code"] > 0
```

**Step 2: Run test to verify failure**

Run: `pytest tests/services/test_typescript_metadata_enriched.py::test_extract_metadata_with_context -v`

Expected: FAIL (missing call_contexts, signature fields)

**Step 3: Add context extraction methods to TypeScriptMetadataExtractor**

Modify: `api/services/metadata_extractors/typescript_extractor.py`

Add these methods after line 675:

```python
    async def extract_call_contexts(
        self,
        node: Node,
        source_code: str,
        scope_name: str = None
    ) -> list[dict]:
        """
        Extract detailed context for each function call.

        Returns list of call contexts with:
        - call_name: Function/method name
        - line_number: Line where call occurs
        - scope_type: 'function', 'class', 'method', 'global'
        - scope_name: Name of containing scope
        - is_conditional: Inside if/switch/ternary
        - is_loop: Inside for/while/do-while
        - is_try_catch: Inside try-catch block
        - arguments_count: Number of arguments passed
        """
        contexts = []

        # Extract all call expressions
        cursor = QueryCursor(self.call_expression_query)
        matches = cursor.matches(node)

        for pattern_index, captures_dict in matches:
            call_nodes = captures_dict.get('call', [])

            for call_node in call_nodes:
                call_name = self._extract_call_expression(call_node, source_code)

                if not call_name or self._is_blacklisted(call_name):
                    continue

                # Determine context by walking up parent nodes
                context = {
                    "call_name": call_name,
                    "line_number": call_node.start_point[0] + 1,
                    "scope_type": self._determine_scope_type(node),
                    "scope_name": scope_name,
                    "is_conditional": self._is_inside_conditional(call_node),
                    "is_loop": self._is_inside_loop(call_node),
                    "is_try_catch": self._is_inside_try_catch(call_node),
                    "arguments_count": self._count_arguments(call_node)
                }

                contexts.append(context)

        return contexts

    def _determine_scope_type(self, node: Node) -> str:
        """Determine scope type from node type."""
        if node.type in ("function_declaration", "arrow_function", "function"):
            return "function"
        elif node.type in ("method_definition", "method"):
            return "method"
        elif node.type in ("class_declaration", "class"):
            return "class"
        else:
            return "global"

    def _is_inside_conditional(self, node: Node) -> bool:
        """Check if node is inside if/switch/ternary."""
        current = node.parent
        while current:
            if current.type in ("if_statement", "switch_statement", "ternary_expression"):
                return True
            current = current.parent
        return False

    def _is_inside_loop(self, node: Node) -> bool:
        """Check if node is inside for/while/do-while."""
        current = node.parent
        while current:
            if current.type in ("for_statement", "for_in_statement", "for_of_statement",
                               "while_statement", "do_statement"):
                return True
            current = current.parent
        return False

    def _is_inside_try_catch(self, node: Node) -> bool:
        """Check if node is inside try-catch block."""
        current = node.parent
        while current:
            if current.type == "try_statement":
                return True
            current = current.parent
        return False

    def _count_arguments(self, call_node: Node) -> int:
        """Count number of arguments in a call expression."""
        for child in call_node.children:
            if child.type == "arguments":
                # Count non-punctuation children (commas, parens)
                return len([c for c in child.children if c.type not in (",", "(", ")")])
        return 0

    async def extract_function_signature(
        self,
        node: Node,
        source_code: str
    ) -> dict:
        """
        Extract detailed function signature.

        Returns:
        - function_name: Name of function
        - parameters: List of {name, type, is_optional, default_value}
        - return_type: Return type annotation
        - is_async: Whether function is async
        - is_generator: Whether function is generator
        - decorators: List of decorators (TypeScript/ES7)
        """
        signature = {
            "function_name": None,
            "parameters": [],
            "return_type": None,
            "is_async": False,
            "is_generator": False,
            "decorators": []
        }

        # Check if async
        for child in node.children:
            if child.type == "async":
                signature["is_async"] = True
            elif child.type == "*":
                signature["is_generator"] = True
            elif child.type == "identifier":
                # Function name
                source_bytes = source_code.encode('utf-8')
                name_bytes = source_bytes[child.start_byte:child.end_byte]
                signature["function_name"] = name_bytes.decode('utf-8')
            elif child.type == "formal_parameters":
                # Extract parameters
                signature["parameters"] = self._extract_parameters(child, source_code)
            elif child.type == "type_annotation":
                # Return type
                source_bytes = source_code.encode('utf-8')
                type_bytes = source_bytes[child.start_byte:child.end_byte]
                signature["return_type"] = type_bytes.decode('utf-8').lstrip(': ')

        return signature

    def _extract_parameters(self, params_node: Node, source_code: str) -> list[dict]:
        """Extract parameter details from formal_parameters node."""
        parameters = []
        source_bytes = source_code.encode('utf-8')

        for child in params_node.children:
            if child.type == "required_parameter" or child.type == "optional_parameter":
                param = {
                    "name": None,
                    "type": None,
                    "is_optional": child.type == "optional_parameter",
                    "default_value": None
                }

                for subchild in child.children:
                    if subchild.type == "identifier":
                        name_bytes = source_bytes[subchild.start_byte:subchild.end_byte]
                        param["name"] = name_bytes.decode('utf-8')
                    elif subchild.type == "type_annotation":
                        type_bytes = source_bytes[subchild.start_byte:subchild.end_byte]
                        param["type"] = type_bytes.decode('utf-8').lstrip(': ')

                parameters.append(param)

        return parameters

    def calculate_cyclomatic_complexity(self, node: Node) -> int:
        """
        Calculate cyclomatic complexity for a function/method.

        CC = 1 (base) + number of decision points
        Decision points: if, else if, for, while, case, catch, &&, ||, ?:
        """
        complexity = 1  # Base complexity

        # Decision point node types
        decision_nodes = {
            "if_statement", "else_clause", "switch_case",
            "for_statement", "for_in_statement", "for_of_statement",
            "while_statement", "do_statement",
            "catch_clause",
            "&&", "||",
            "ternary_expression"
        }

        def count_decisions(n: Node) -> int:
            count = 1 if n.type in decision_nodes else 0
            for child in n.children:
                count += count_decisions(child)
            return count

        return complexity + count_decisions(node)
```

**Step 4: Update extract_metadata to include enriched data**

Modify the `extract_metadata` method (around line 650):

```python
    async def extract_metadata(
        self,
        source_code: str,
        node: Node,
        tree: Tree
    ) -> dict[str, Any]:
        """
        Extract ALL metadata including enriched context and metrics.

        Returns:
            {
                "imports": [...],
                "calls": [...],
                "re_exports": [...],
                "call_contexts": [{call_name, line, scope, is_conditional, ...}],
                "signature": {function_name, parameters, return_type, is_async, ...},
                "complexity": {cyclomatic, lines_of_code}
            }
        """
        try:
            # Extract basic metadata (existing)
            imports = await self.extract_imports(tree, source_code)
            calls = await self.extract_calls(node, source_code)
            re_exports = await self.extract_re_exports(node, source_code)

            # Extract enriched metadata (NEW)
            # Determine scope name
            scope_name = None
            for child in node.children:
                if child.type == "identifier":
                    source_bytes = source_code.encode('utf-8')
                    name_bytes = source_bytes[child.start_byte:child.end_byte]
                    scope_name = name_bytes.decode('utf-8')
                    break

            call_contexts = await self.extract_call_contexts(node, source_code, scope_name)
            signature = await self.extract_function_signature(node, source_code)

            # Calculate complexity
            cyclomatic = self.calculate_cyclomatic_complexity(node)
            source_bytes = source_code.encode('utf-8')
            node_source = source_bytes[node.start_byte:node.end_byte].decode('utf-8')
            lines_of_code = len([l for l in node_source.split('\n') if l.strip()])

            return {
                "imports": imports,
                "calls": calls,
                "re_exports": re_exports,
                "call_contexts": call_contexts,
                "signature": signature,
                "complexity": {
                    "cyclomatic": cyclomatic,
                    "lines_of_code": lines_of_code
                }
            }

        except Exception as e:
            self.logger.error(f"Failed to extract enriched metadata: {e}", exc_info=True)
            return {
                "imports": [],
                "calls": [],
                "re_exports": [],
                "call_contexts": [],
                "signature": {},
                "complexity": {"cyclomatic": 0, "lines_of_code": 0}
            }
```

**Step 5: Run tests**

Run: `pytest tests/services/test_typescript_metadata_enriched.py -v`

Expected: PASS

**Step 6: Commit**

```bash
git add api/services/metadata_extractors/typescript_extractor.py tests/services/test_typescript_metadata_enriched.py
git commit -m "feat(metadata): Add enriched context extraction (call_contexts, signatures, complexity)"
```

---

## Phase 4: Metrics Calculation Service

### Task 4.1: Create MetricsCalculationService

**Files:**
- Create: `api/services/metrics_calculation_service.py`
- Create: `tests/services/test_metrics_calculation_service.py`

**Step 1: Write test for coupling metrics**

```python
import pytest
from services.metrics_calculation_service import MetricsCalculationService
from models.graph_models import NodeModel


@pytest.mark.asyncio
async def test_calculate_coupling_metrics(test_db_engine):
    """Test afferent/efferent coupling calculation."""
    service = MetricsCalculationService(test_db_engine)

    # Mock graph structure:
    # NodeA -> NodeB
    # NodeA -> NodeC
    # NodeD -> NodeA
    #
    # For NodeA:
    # - Efferent coupling = 2 (depends on B, C)
    # - Afferent coupling = 1 (D depends on it)

    node_a_id = uuid.uuid4()
    node_b_id = uuid.uuid4()
    node_c_id = uuid.uuid4()
    node_d_id = uuid.uuid4()

    # Create nodes
    # ... (setup nodes in DB)

    # Create edges
    # ... (setup edges: A->B, A->C, D->A)

    # Calculate coupling
    coupling = await service.calculate_coupling_for_node(node_a_id)

    assert coupling["afferent"] == 1
    assert coupling["efferent"] == 2
    assert coupling["instability"] == pytest.approx(0.667, rel=0.01)  # 2/(1+2)


@pytest.mark.asyncio
async def test_calculate_pagerank():
    """Test PageRank calculation for graph."""
    service = MetricsCalculationService(test_db_engine)

    # Create simple graph
    repository = "test_repo"
    # ... (setup nodes and edges)

    pagerank_scores = await service.calculate_pagerank(repository)

    # Check scores sum to 1.0
    assert sum(pagerank_scores.values()) == pytest.approx(1.0, rel=0.01)

    # Check most connected node has highest score
    # ...
```

**Step 2: Run test to verify failure**

Run: `pytest tests/services/test_metrics_calculation_service.py -v`

Expected: ImportError

**Step 3: Implement MetricsCalculationService**

```python
"""
Service for calculating code quality metrics and graph analytics.
"""
import logging
from collections import defaultdict
from typing import Dict, List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import text

logger = logging.getLogger(__name__)


class MetricsCalculationService:
    """
    Calculate code quality metrics and graph analytics.

    Responsibilities:
    - Coupling metrics (afferent, efferent, instability)
    - Graph centrality (PageRank, betweenness)
    - Edge weights (importance scoring)
    - Critical path detection
    """

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def calculate_coupling_for_node(
        self,
        node_id: UUID
    ) -> Dict[str, float]:
        """
        Calculate coupling metrics for a single node.

        Afferent coupling (Ca): Number of nodes that depend on this node
        Efferent coupling (Ce): Number of nodes this node depends on
        Instability (I): Ce / (Ca + Ce)

        Returns:
            {"afferent": int, "efferent": int, "instability": float}
        """
        # Count incoming edges (afferent)
        afferent_query = text("""
            SELECT COUNT(DISTINCT source_node_id)
            FROM edges
            WHERE target_node_id = :node_id
              AND relation_type = 'calls'
        """)

        # Count outgoing edges (efferent)
        efferent_query = text("""
            SELECT COUNT(DISTINCT target_node_id)
            FROM edges
            WHERE source_node_id = :node_id
              AND relation_type = 'calls'
        """)

        async with self.engine.connect() as conn:
            afferent_result = await conn.execute(afferent_query, {"node_id": str(node_id)})
            afferent = afferent_result.scalar() or 0

            efferent_result = await conn.execute(efferent_query, {"node_id": str(node_id)})
            efferent = efferent_result.scalar() or 0

        # Calculate instability
        total = afferent + efferent
        instability = efferent / total if total > 0 else 0.0

        return {
            "afferent": afferent,
            "efferent": efferent,
            "instability": instability
        }

    async def calculate_coupling_for_repository(
        self,
        repository: str
    ) -> Dict[UUID, Dict[str, float]]:
        """
        Calculate coupling metrics for all nodes in a repository.

        Returns:
            {node_id: {"afferent": int, "efferent": int, "instability": float}}
        """
        # Get all nodes for repository
        nodes_query = text("""
            SELECT node_id
            FROM nodes
            WHERE properties->>'repository' = :repository
        """)

        async with self.engine.connect() as conn:
            result = await conn.execute(nodes_query, {"repository": repository})
            node_ids = [UUID(row[0]) for row in result.fetchall()]

        # Calculate coupling for each node
        coupling_metrics = {}
        for node_id in node_ids:
            coupling_metrics[node_id] = await self.calculate_coupling_for_node(node_id)

        logger.info(f"Calculated coupling for {len(coupling_metrics)} nodes in {repository}")
        return coupling_metrics

    async def calculate_pagerank(
        self,
        repository: str,
        damping: float = 0.85,
        max_iterations: int = 100,
        tolerance: float = 1e-6
    ) -> Dict[UUID, float]:
        """
        Calculate PageRank scores for all nodes in repository graph.

        PageRank measures node importance based on incoming edges.
        Higher score = more central/important in dependency graph.

        Args:
            repository: Repository name
            damping: Damping factor (0.85 = standard)
            max_iterations: Max iterations for convergence
            tolerance: Convergence threshold

        Returns:
            {node_id: pagerank_score}
        """
        # Get all nodes
        nodes_query = text("""
            SELECT node_id
            FROM nodes
            WHERE properties->>'repository' = :repository
        """)

        # Get all edges (calls relationships)
        edges_query = text("""
            SELECT e.source_node_id, e.target_node_id
            FROM edges e
            JOIN nodes n ON e.source_node_id = n.node_id
            WHERE n.properties->>'repository' = :repository
              AND e.relation_type = 'calls'
        """)

        async with self.engine.connect() as conn:
            nodes_result = await conn.execute(nodes_query, {"repository": repository})
            node_ids = [UUID(row[0]) for row in nodes_result.fetchall()]

            edges_result = await conn.execute(edges_query, {"repository": repository})
            edges = [(UUID(row[0]), UUID(row[1])) for row in edges_result.fetchall()]

        if not node_ids:
            return {}

        # Build adjacency structure
        outlinks = defaultdict(list)
        for source, target in edges:
            outlinks[source].append(target)

        # Initialize PageRank scores (uniform distribution)
        num_nodes = len(node_ids)
        scores = {node_id: 1.0 / num_nodes for node_id in node_ids}

        # Iterative PageRank calculation
        for iteration in range(max_iterations):
            new_scores = {}

            for node in node_ids:
                # Base score (teleportation)
                rank = (1 - damping) / num_nodes

                # Sum contributions from incoming links
                for source in node_ids:
                    if node in outlinks[source]:
                        num_outlinks = len(outlinks[source])
                        rank += damping * (scores[source] / num_outlinks)

                new_scores[node] = rank

            # Check convergence
            diff = sum(abs(new_scores[n] - scores[n]) for n in node_ids)
            scores = new_scores

            if diff < tolerance:
                logger.info(f"PageRank converged after {iteration + 1} iterations")
                break

        # Normalize scores to sum to 1.0
        total = sum(scores.values())
        if total > 0:
            scores = {node: score / total for node, score in scores.items()}

        logger.info(f"Calculated PageRank for {len(scores)} nodes in {repository}")
        return scores

    async def calculate_edge_weights(
        self,
        repository: str,
        pagerank_scores: Dict[UUID, float]
    ) -> Dict[UUID, float]:
        """
        Calculate importance scores for edges based on PageRank propagation.

        Edge weight = (PageRank of source + PageRank of target) / 2
        This gives higher weight to edges between important nodes.

        Args:
            repository: Repository name
            pagerank_scores: Pre-calculated PageRank scores

        Returns:
            {edge_id: importance_score}
        """
        edges_query = text("""
            SELECT e.edge_id, e.source_node_id, e.target_node_id
            FROM edges e
            JOIN nodes n ON e.source_node_id = n.node_id
            WHERE n.properties->>'repository' = :repository
              AND e.relation_type = 'calls'
        """)

        async with self.engine.connect() as conn:
            result = await conn.execute(edges_query, {"repository": repository})
            edges = result.fetchall()

        edge_weights = {}
        for edge_id, source_id, target_id in edges:
            source_score = pagerank_scores.get(UUID(source_id), 0.0)
            target_score = pagerank_scores.get(UUID(target_id), 0.0)

            # Average PageRank as edge importance
            importance = (source_score + target_score) / 2.0
            edge_weights[UUID(edge_id)] = importance

        logger.info(f"Calculated weights for {len(edge_weights)} edges in {repository}")
        return edge_weights
```

**Step 4: Run tests**

Run: `pytest tests/services/test_metrics_calculation_service.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add api/services/metrics_calculation_service.py tests/services/test_metrics_calculation_service.py
git commit -m "feat(metrics): Add MetricsCalculationService with coupling and PageRank"
```

---

## Phase 5: Integration into Indexing Pipeline

### Task 5.1: Add Phase 3 (Metadata Extraction) to index_directory.py

**Files:**
- Modify: `scripts/index_directory.py`

**Step 1: Add test for Phase 3**

Create: `tests/scripts/test_index_directory_phase3.py`

```python
import pytest
from pathlib import Path
from scripts.index_directory import phase3_metadata_extraction


@pytest.mark.asyncio
async def test_phase3_extracts_detailed_metadata(tmp_path, test_db_engine):
    """Test Phase 3 extracts and stores detailed metadata."""
    # Create mock chunks with node IDs
    chunks = [
        MockChunk(
            id=uuid.uuid4(),
            name="testFunction",
            chunk_type="function",
            metadata={"calls": ["helper"], "imports": ["./utils"]}
        )
    ]

    # Run Phase 3
    await phase3_metadata_extraction(chunks, "test_repo", test_db_engine, verbose=True)

    # Verify detailed_metadata table populated
    from db.repositories.detailed_metadata_repository import DetailedMetadataRepository
    repo = DetailedMetadataRepository(test_db_engine)

    metadata_list = await repo.get_by_repository("test_repo")
    assert len(metadata_list) > 0

    # Check enriched data
    metadata = metadata_list[0]
    assert "call_contexts" in metadata.metadata
    assert "signature" in metadata.metadata
    assert "complexity" in metadata.metadata
```

**Step 2: Implement Phase 3 in index_directory.py**

Add this function after `phase2_embeddings` (around line 280):

```python
async def phase3_metadata_extraction(
    chunks: list,
    repository: str,
    engine,
    verbose: bool = False
):
    """
    Phase 3: Extract detailed metadata and store in dedicated tables.

    For each chunk:
    1. Extract enriched metadata (call_contexts, signature, complexity)
    2. Store in detailed_metadata table
    3. Create initial computed_metrics entry

    Returns:
        Tuple (success_count, error_count)
    """
    from services.metadata_extractors.typescript_extractor import TypeScriptMetadataExtractor
    from db.repositories.detailed_metadata_repository import DetailedMetadataRepository
    from db.repositories.computed_metrics_repository import ComputedMetricsRepository
    from tree_sitter_language_pack import get_parser

    print("\n" + "=" * 80)
    print("📊 Phase 3/4: Detailed Metadata Extraction")
    print("=" * 80)

    metadata_repo = DetailedMetadataRepository(engine)
    metrics_repo = ComputedMetricsRepository(engine)

    success_count = 0
    error_count = 0

    start_time = datetime.now()

    # Group chunks by language
    chunks_by_language = defaultdict(list)
    for chunk in chunks:
        if chunk.language in ("typescript", "javascript"):
            chunks_by_language[chunk.language].append(chunk)

    # Process TypeScript/JavaScript chunks
    for language, lang_chunks in chunks_by_language.items():
        print(f"\n   Processing {len(lang_chunks)} {language} chunks...")

        extractor = TypeScriptMetadataExtractor(language)
        parser = get_parser(language)

        for chunk in tqdm(lang_chunks, desc=f"   Extracting {language} metadata"):
            try:
                # Re-parse chunk to get AST node
                file_path = Path(chunk.file_path)
                if not file_path.exists():
                    error_count += 1
                    continue

                with open(file_path, 'r', encoding='utf-8') as f:
                    source_code = f.read()

                tree = parser.parse(bytes(source_code, "utf8"))

                # Find node corresponding to chunk (by start_line)
                # This is simplified - in production, use precise node matching
                node = tree.root_node  # TODO: Find specific node by line range

                # Extract enriched metadata
                metadata = await extractor.extract_metadata(source_code, node, tree)

                # Get node_id from chunk (assuming chunk has associated node)
                # This requires chunk_to_node mapping from Phase 4
                # For now, we'll store with chunk_id only and update later

                # Store detailed metadata
                await metadata_repo.create(
                    node_id=chunk.id,  # Temporary: use chunk_id until nodes created
                    chunk_id=chunk.id,
                    metadata=metadata,
                    version=1
                )

                # Create initial metrics entry
                complexity = metadata.get("complexity", {})
                await metrics_repo.create(
                    node_id=chunk.id,  # Temporary
                    chunk_id=chunk.id,
                    repository=repository,
                    cyclomatic_complexity=complexity.get("cyclomatic", 0),
                    lines_of_code=complexity.get("lines_of_code", 0),
                    version=1
                )

                success_count += 1

            except Exception as e:
                if verbose:
                    print(f"\n   ⚠️  Failed to extract metadata for {chunk.name}: {e}")
                error_count += 1

    elapsed = (datetime.now() - start_time).total_seconds()

    print(f"\n   ✅ Phase 3 complete:")
    print(f"      Success: {success_count}")
    print(f"      Errors: {error_count}")
    print(f"      Time: {elapsed:.1f}s")

    return (success_count, error_count)
```

**Step 3: Integrate Phase 3 into main()**

Modify the `main()` function (around line 370):

```python
async def main():
    # ... existing code ...

    # Phase 2: Embeddings
    chunks, errors_phase2 = await phase2_embeddings(chunks, repository, args.verbose)

    # Phase 3: Metadata Extraction (NEW)
    success, errors_phase3 = await phase3_metadata_extraction(
        chunks, repository, engine, args.verbose
    )

    # Phase 4: Graph Construction (renamed from Phase 3)
    stats = await phase4_graph_construction(repository, args.verbose)

    # ... rest of code ...
```

**Step 4: Run test**

Run: `pytest tests/scripts/test_index_directory_phase3.py -v`

Expected: PASS

**Step 5: Test full pipeline on small dataset**

```bash
# Create test directory with 2 files
mkdir -p /tmp/test_metadata
cat > /tmp/test_metadata/sample.ts << 'EOF'
async function processUser(email: string): Promise<void> {
    if (validateEmail(email)) {
        await saveUser(email);
    }
}
EOF

# Run indexing
docker exec -i mnemo-api python3 /app/scripts/index_directory.py /tmp/test_metadata --repository test_metadata --verbose
```

Expected: Phase 3 completes, detailed_metadata and computed_metrics tables populated

**Step 6: Commit**

```bash
git add scripts/index_directory.py tests/scripts/test_index_directory_phase3.py
git commit -m "feat(indexing): Add Phase 3 metadata extraction to pipeline"
```

### Task 5.2: Enhance Phase 4 (Graph Construction) with Metrics

**Files:**
- Modify: `scripts/index_directory.py`
- Modify: `api/services/graph_construction_service.py`

**Step 1: Add metrics calculation to graph construction**

Modify `services/graph_construction_service.py` - Add after line 262:

```python
    async def calculate_and_store_metrics(
        self,
        repository: str,
        chunk_to_node: Dict[uuid.UUID, NodeModel]
    ) -> None:
        """
        Calculate and store graph metrics after construction.

        Steps:
        1. Calculate coupling metrics for all nodes
        2. Calculate PageRank scores
        3. Calculate edge weights
        4. Update computed_metrics table
        5. Update edge_weights table
        """
        from services.metrics_calculation_service import MetricsCalculationService
        from db.repositories.computed_metrics_repository import ComputedMetricsRepository
        from db.repositories.edge_weights_repository import EdgeWeightsRepository

        self.logger.info(f"Calculating metrics for repository '{repository}'...")

        metrics_service = MetricsCalculationService(self.engine)
        metrics_repo = ComputedMetricsRepository(self.engine)
        weights_repo = EdgeWeightsRepository(self.engine)

        # 1. Calculate coupling for all nodes
        coupling_metrics = await metrics_service.calculate_coupling_for_repository(repository)

        # 2. Calculate PageRank
        pagerank_scores = await metrics_service.calculate_pagerank(repository)

        # 3. Update computed_metrics with coupling and PageRank
        for chunk_id, node in chunk_to_node.items():
            coupling = coupling_metrics.get(node.node_id, {"afferent": 0, "efferent": 0})
            pagerank = pagerank_scores.get(node.node_id, 0.0)

            await metrics_repo.update_coupling(
                node_id=node.node_id,
                afferent_coupling=coupling["afferent"],
                efferent_coupling=coupling["efferent"],
                version=1
            )

            # Update PageRank score
            await metrics_repo.update_pagerank(
                node_id=node.node_id,
                pagerank_score=pagerank,
                version=1
            )

        # 4. Calculate and store edge weights
        edge_weights = await metrics_service.calculate_edge_weights(repository, pagerank_scores)

        for edge_id, importance in edge_weights.items():
            await weights_repo.create_or_update(
                edge_id=edge_id,
                importance_score=importance,
                version=1
            )

        self.logger.info(
            f"✅ Metrics calculated: {len(coupling_metrics)} nodes, "
            f"{len(edge_weights)} edges weighted"
        )
```

**Step 2: Call metrics calculation in build_graph_for_repository**

Modify line 210 in `graph_construction_service.py`:

```python
        # After graph construction transaction commits...
        self.logger.info(
            f"✅ EPIC-12: Graph construction transaction committed - "
            f"{len(chunk_to_node)} nodes and {len(call_edges) + len(import_edges) + len(reexport_edges)} edges stored atomically"
        )

        # Calculate metrics (NEW)
        await self.calculate_and_store_metrics(repository, chunk_to_node)
```

**Step 3: Update index_directory.py Phase 4 name**

Rename function:

```python
async def phase4_graph_construction(repository: str, verbose: bool = False):
    """
    Phase 4: Graph construction and metrics calculation.

    Steps:
    1. Build graph (nodes + edges)
    2. Calculate coupling metrics
    3. Calculate PageRank
    4. Calculate edge weights

    Returns:
        GraphStats
    """
    from services.graph_construction_service import GraphConstructionService

    print("\n" + "=" * 80)
    print("🕸️  Phase 4/4: Graph Construction & Metrics")
    print("=" * 80)

    engine = get_db_engine()
    service = GraphConstructionService(engine)

    stats = await service.build_graph_for_repository(
        repository=repository,
        languages=["typescript", "javascript"]
    )

    print(f"\n   ✅ Graph complete:")
    print(f"      Nodes: {stats.total_nodes}")
    print(f"      Edges: {stats.total_edges}")
    print(f"      Resolution: {stats.resolution_accuracy:.1f}%")
    print(f"      Time: {stats.construction_time_seconds:.2f}s")

    return stats
```

**Step 4: Test full pipeline**

```bash
docker exec -i mnemo-api python3 /app/scripts/index_directory.py /tmp/test_metadata --repository test_metadata --verbose
```

Expected: All 4 phases complete, metrics calculated and stored

**Step 5: Verify metrics in database**

```bash
docker exec -i mnemo-postgres psql -U mnemo -d mnemolite -c "
SELECT
    n.properties->>'name' as name,
    cm.cyclomatic_complexity,
    cm.afferent_coupling,
    cm.efferent_coupling,
    cm.pagerank_score
FROM computed_metrics cm
JOIN nodes n ON cm.node_id = n.node_id
WHERE cm.repository = 'test_metadata'
LIMIT 5;
"
```

Expected: Metrics displayed for test functions

**Step 6: Commit**

```bash
git add api/services/graph_construction_service.py scripts/index_directory.py
git commit -m "feat(graph): Add automatic metrics calculation to graph construction"
```

---

## Phase 6: Frontend Visualization Enhancement

### Task 6.1: Add Metrics Display to Graph UI

**Files:**
- Modify: `frontend/src/pages/Graph.vue`
- Modify: `frontend/src/components/G6Graph.vue`
- Modify: `api/routes/code_graph_routes.py`

**Step 1: Add metrics endpoint to API**

Modify `api/routes/code_graph_routes.py` - Add after line 421:

```python
@router.get("/metrics/{repository}", response_model=Dict[str, Any])
async def get_repository_metrics(
    repository: str = Path(..., description="Repository name"),
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """
    Get aggregated metrics for repository.

    Returns:
        {
            "total_functions": int,
            "avg_complexity": float,
            "max_complexity": int,
            "most_complex_function": str,
            "avg_coupling": float,
            "most_coupled_function": str,
            "top_pagerank": [{name, score}]
        }
    """
    try:
        from sqlalchemy.sql import text

        async with engine.connect() as conn:
            # Aggregate metrics query
            query = text("""
                SELECT
                    COUNT(*) as total_functions,
                    AVG(cyclomatic_complexity) as avg_complexity,
                    MAX(cyclomatic_complexity) as max_complexity,
                    AVG(afferent_coupling + efferent_coupling) as avg_coupling
                FROM computed_metrics
                WHERE repository = :repository
                  AND version = 1
            """)

            result = await conn.execute(query, {"repository": repository})
            row = result.fetchone()

            # Get most complex function
            complex_query = text("""
                SELECT n.properties->>'name' as name, cm.cyclomatic_complexity
                FROM computed_metrics cm
                JOIN nodes n ON cm.node_id = n.node_id
                WHERE cm.repository = :repository
                  AND cm.version = 1
                ORDER BY cm.cyclomatic_complexity DESC
                LIMIT 1
            """)

            complex_result = await conn.execute(complex_query, {"repository": repository})
            complex_row = complex_result.fetchone()

            # Get top PageRank nodes
            pagerank_query = text("""
                SELECT n.properties->>'name' as name, cm.pagerank_score
                FROM computed_metrics cm
                JOIN nodes n ON cm.node_id = n.node_id
                WHERE cm.repository = :repository
                  AND cm.version = 1
                  AND cm.pagerank_score IS NOT NULL
                ORDER BY cm.pagerank_score DESC
                LIMIT 10
            """)

            pagerank_result = await conn.execute(pagerank_query, {"repository": repository})
            pagerank_rows = pagerank_result.fetchall()

        return {
            "total_functions": row[0] or 0,
            "avg_complexity": round(row[1], 2) if row[1] else 0,
            "max_complexity": row[2] or 0,
            "most_complex_function": complex_row[0] if complex_row else "N/A",
            "avg_coupling": round(row[3], 2) if row[3] else 0,
            "top_pagerank": [
                {"name": r[0], "score": round(r[1], 4)}
                for r in pagerank_rows
            ]
        }

    except Exception as e:
        logger.error(f"Failed to get metrics for {repository}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")
```

**Step 2: Add metrics fetching to composable**

Modify `frontend/src/composables/useCodeGraph.ts` - Add after line 143:

```typescript
export interface RepositoryMetrics {
  total_functions: number
  avg_complexity: number
  max_complexity: number
  most_complex_function: string
  avg_coupling: number
  top_pagerank: Array<{ name: string; score: number }>
}

// Add to UseCodeGraphReturn interface
interface UseCodeGraphReturn {
  // ... existing fields ...
  metrics: ReturnType<typeof ref<RepositoryMetrics | null>>
  fetchMetrics: (repository: string) => Promise<void>
}

// Add to useCodeGraph function
export function useCodeGraph(): UseCodeGraphReturn {
  // ... existing refs ...
  const metrics = ref<RepositoryMetrics | null>(null)

  const fetchMetrics = async (repository: string = 'MnemoLite') => {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`http://localhost:8001/v1/code/graph/metrics/${repository}`)

      if (!response.ok) {
        throw new Error(`Failed to fetch metrics: ${response.status} ${response.statusText}`)
      }

      const data = await response.json()
      metrics.value = data
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred'
      error.value = errorMessage
      console.error('Metrics error:', err)
      metrics.value = null
    } finally {
      loading.value = false
    }
  }

  return {
    // ... existing returns ...
    metrics,
    fetchMetrics,
  }
}
```

**Step 3: Add metrics panel to Graph.vue**

Modify `frontend/src/pages/Graph.vue` - Add metrics panel in template:

```vue
<!-- Add after stats cards, before graph -->
<div v-if="metrics" class="bg-slate-800 rounded-lg p-6 mb-6">
  <h3 class="text-xl font-semibold text-gray-200 mb-4">📊 Code Quality Metrics</h3>

  <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
    <div class="bg-slate-700 rounded p-4">
      <p class="text-sm text-gray-400">Avg Complexity</p>
      <p class="text-2xl font-bold text-yellow-400">{{ metrics.avg_complexity }}</p>
    </div>

    <div class="bg-slate-700 rounded p-4">
      <p class="text-sm text-gray-400">Max Complexity</p>
      <p class="text-2xl font-bold text-red-400">{{ metrics.max_complexity }}</p>
      <p class="text-xs text-gray-500 mt-1">{{ metrics.most_complex_function }}</p>
    </div>

    <div class="bg-slate-700 rounded p-4">
      <p class="text-sm text-gray-400">Avg Coupling</p>
      <p class="text-2xl font-bold text-purple-400">{{ metrics.avg_coupling.toFixed(1) }}</p>
    </div>
  </div>

  <div class="bg-slate-700 rounded p-4">
    <h4 class="text-sm font-semibold text-gray-300 mb-3">🏆 Most Important Functions (PageRank)</h4>
    <div class="space-y-2">
      <div
        v-for="(item, idx) in metrics.top_pagerank.slice(0, 5)"
        :key="idx"
        class="flex justify-between items-center text-sm"
      >
        <span class="text-gray-300">{{ item.name }}</span>
        <div class="flex items-center">
          <div class="w-32 bg-slate-600 rounded-full h-2 mr-2">
            <div
              class="bg-green-500 h-2 rounded-full"
              :style="{ width: `${item.score * 100}%` }"
            ></div>
          </div>
          <span class="text-gray-400 w-12 text-right">{{ (item.score * 100).toFixed(1) }}%</span>
        </div>
      </div>
    </div>
  </div>
</div>
```

**Step 4: Update script to fetch metrics**

Modify `frontend/src/pages/Graph.vue` script section:

```typescript
const {
  stats, graphData, loading, error, repositories, metrics,
  fetchStats, fetchGraphData, fetchRepositories, fetchMetrics
} = useCodeGraph()

// Update watch to fetch metrics
watch(repository, async (newRepo) => {
  if (newRepo) {
    await fetchStats(newRepo)
    await fetchGraphData(newRepo, 80)
    await fetchMetrics(newRepo)  // NEW
  }
})

// Update onMounted
onMounted(async () => {
  await fetchRepositories()
  if (repositories.value.length > 0) {
    repository.value = repositories.value[0]
    await fetchStats(repository.value)
    await fetchGraphData(repository.value, 80)
    await fetchMetrics(repository.value)  // NEW
  }
})
```

**Step 5: Test frontend**

Navigate to `http://localhost:3002/` and verify:
- Metrics panel displays with complexity, coupling stats
- Top PageRank functions shown with progress bars
- Metrics update when switching repositories

**Step 6: Commit**

```bash
git add frontend/src/pages/Graph.vue frontend/src/composables/useCodeGraph.ts api/routes/code_graph_routes.py
git commit -m "feat(ui): Add code quality metrics dashboard to graph page"
```

---

## Phase 7: Testing & Validation

### Task 7.1: Integration Test - Full Pipeline

**Files:**
- Create: `tests/integration/test_full_pipeline.py`

**Step 1: Write end-to-end test**

```python
import pytest
import tempfile
from pathlib import Path
from scripts.index_directory import main as index_main


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_indexing_pipeline(test_db_engine):
    """
    End-to-end test: Index code → Verify all tables populated.
    """
    # Create temporary TypeScript project
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir) / "test_project"
        project_dir.mkdir()

        # Create sample TypeScript file
        (project_dir / "user.ts").write_text("""
async function validateUser(email: string): Promise<boolean> {
    if (!email) return false;

    const isValid = checkEmailFormat(email);
    if (isValid) {
        await logValidation(email);
    }

    return isValid;
}

function checkEmailFormat(email: string): boolean {
    return email.includes('@');
}

async function logValidation(email: string): Promise<void> {
    console.log('Validated:', email);
}
        """)

        # Run indexing pipeline
        import sys
        sys.argv = [
            "index_directory.py",
            str(project_dir),
            "--repository", "test_integration",
            "--verbose"
        ]

        await index_main()

        # Verify Phase 1: Chunks created
        from db.repositories.code_chunk_repository import CodeChunkRepository
        chunk_repo = CodeChunkRepository(test_db_engine)
        chunks = await chunk_repo.get_by_repository("test_integration")
        assert len(chunks) == 3  # 3 functions

        # Verify Phase 2: Embeddings generated
        for chunk in chunks:
            assert chunk.embedding_code is not None
            assert len(chunk.embedding_code) == 768  # jina-code dimension

        # Verify Phase 3: Detailed metadata stored
        from db.repositories.detailed_metadata_repository import DetailedMetadataRepository
        metadata_repo = DetailedMetadataRepository(test_db_engine)
        metadata_list = await metadata_repo.get_by_repository("test_integration")
        assert len(metadata_list) == 3

        # Check validateUser metadata
        validate_meta = next(m for m in metadata_list if "validateUser" in str(m.metadata))
        assert "checkEmailFormat" in validate_meta.metadata["calls"]
        assert "logValidation" in validate_meta.metadata["calls"]
        assert validate_meta.metadata["signature"]["is_async"] == True
        assert validate_meta.metadata["complexity"]["cyclomatic"] >= 2

        # Verify Phase 4: Graph constructed
        from db.repositories.node_repository import NodeRepository
        node_repo = NodeRepository(test_db_engine)
        nodes = await node_repo.get_by_repository("test_integration")
        assert len(nodes) == 3

        # Verify edges exist
        from db.repositories.edge_repository import EdgeRepository
        edge_repo = EdgeRepository(test_db_engine)
        edges = await edge_repo.get_by_repository("test_integration")
        assert len(edges) >= 2  # validateUser -> checkEmailFormat, logValidation

        # Verify metrics calculated
        from db.repositories.computed_metrics_repository import ComputedMetricsRepository
        metrics_repo = ComputedMetricsRepository(test_db_engine)
        metrics_list = await metrics_repo.get_by_repository("test_integration")
        assert len(metrics_list) == 3

        # Check validateUser has efferent coupling >= 2
        validate_node = next(n for n in nodes if n.label == "validateUser")
        validate_metrics = next(m for m in metrics_list if m.node_id == validate_node.node_id)
        assert validate_metrics.efferent_coupling >= 2
        assert validate_metrics.pagerank_score is not None
        assert validate_metrics.pagerank_score > 0
```

**Step 2: Run integration test**

Run: `pytest tests/integration/test_full_pipeline.py -v -m integration`

Expected: PASS - All phases complete and verified

**Step 3: Commit**

```bash
git add tests/integration/test_full_pipeline.py
git commit -m "test(integration): Add end-to-end pipeline validation test"
```

---

## Phase 8: Documentation

### Task 8.1: Update scripts/README.md

**Files:**
- Modify: `scripts/README.md`

**Step 1: Add section for new features**

Add after line 190 in `scripts/README.md`:

```markdown
## Rich Metadata Extraction (v2.0)

**Updated**: 2025-11-02

### New Features

The indexing pipeline now extracts comprehensive metadata in 4 phases:

1. **Phase 1: Code Chunking** - AST parsing (unchanged)
2. **Phase 2: Embeddings** - CODE embeddings (unchanged)
3. **Phase 3: Metadata Extraction** ⭐ NEW
   - Function signatures with parameters and types
   - Call contexts (scope, conditionals, loops)
   - Cyclomatic complexity per function
4. **Phase 4: Graph Construction + Metrics** ⭐ ENHANCED
   - Graph construction with call/import edges
   - Coupling metrics (afferent/efferent)
   - PageRank importance scoring
   - Edge weights

### Database Schema

**New Tables**:
- `detailed_metadata` - JSONB storage for call contexts, signatures
- `computed_metrics` - Normalized metrics (complexity, coupling, PageRank)
- `edge_weights` - Edge importance scores

### Performance

- 100 files: ~4-5 minutes (was ~2min)
- 500 files: ~18-20 minutes (was ~8min)
- Bottleneck: Metadata extraction + PageRank calculation

### Viewing Results

**Graph UI** (http://localhost:3002/):
- View code dependency graph
- See complexity metrics per function
- Filter by PageRank importance
- Explore call relationships

**Metrics Dashboard**:
- Avg/Max complexity
- Most complex functions
- Top PageRank functions
- Coupling statistics

### API Endpoints

```bash
# Get repository metrics
curl http://localhost:8001/v1/code/graph/metrics/my_repo

# Get graph data with weights
curl http://localhost:8001/v1/code/graph/data/my_repo?limit=100
```
```

**Step 2: Commit**

```bash
git add scripts/README.md
git commit -m "docs: Update README with rich metadata extraction features"
```

---

## Summary & Verification

### Final Verification Checklist

**Step 1: Run all tests**

```bash
# Unit tests
pytest tests/db/repositories/ -v
pytest tests/services/ -v

# Integration test
pytest tests/integration/test_full_pipeline.py -v -m integration
```

Expected: All PASS

**Step 2: Verify database schema**

```bash
docker exec -i mnemo-postgres psql -U mnemo -d mnemolite -c "\dt"
```

Expected: Tables `detailed_metadata`, `computed_metrics`, `edge_weights` exist

**Step 3: Test full pipeline on real codebase**

```bash
# Index code_test (100 files subset)
docker exec -i mnemo-api python3 /app/scripts/index_directory.py /tmp/code_test_subset --repository code_test_v2 --verbose
```

Expected: 4 phases complete, no errors

**Step 4: Verify UI displays metrics**

Navigate to `http://localhost:3002/`, select `code_test_v2`

Expected:
- Graph displays nodes and edges
- Metrics panel shows complexity, coupling
- PageRank top functions listed
- Edge weights visible (thicker lines = higher importance)

**Step 5: Query metrics via SQL**

```bash
docker exec -i mnemo-postgres psql -U mnemo -d mnemolite -c "
SELECT
    n.properties->>'name' as function_name,
    cm.cyclomatic_complexity as complexity,
    cm.afferent_coupling as incoming,
    cm.efferent_coupling as outgoing,
    ROUND(cm.pagerank_score::numeric, 4) as importance
FROM computed_metrics cm
JOIN nodes n ON cm.node_id = n.node_id
WHERE cm.repository = 'code_test_v2'
  AND cm.version = 1
ORDER BY cm.pagerank_score DESC NULLS LAST
LIMIT 10;
"
```

Expected: Top 10 most important functions with metrics

---

## Implementation Notes

### Assumptions

1. **Node-Chunk Mapping**: Each chunk has exactly one corresponding node (1:1 relationship)
2. **Version Management**: Version 1 = current indexed state; future versions for historical tracking
3. **Language Support**: Phase 3 currently TypeScript/JavaScript only; Python support in future
4. **PageRank Convergence**: 100 iterations with tolerance 1e-6 is sufficient for most codebases
5. **Test Database**: Tests use separate TEST_DATABASE_URL to avoid polluting dev DB

### Known Limitations

1. **Memory**: Large repos (>1000 files) may need batch processing in Phase 3
2. **Call Resolution**: Uses name_path matching; may miss dynamic calls (`obj[method]()`)
3. **External Dependencies**: npm packages, stdlib imports not tracked (graph shows internal only)
4. **Complexity**: Cognitive complexity not yet implemented (only cyclomatic)
5. **UI Performance**: G6 graph may lag with >500 nodes; needs virtualization

### Future Enhancements

1. **Python Support**: Add PythonMetadataExtractor with same enrichment
2. **Batch Mode**: Process repos in chunks to handle 10k+ files
3. **Delta Indexing**: Re-index only changed files (git diff)
4. **Metric Trends**: Track metrics over time (TimescaleDB)
5. **Code Smells**: Detect circular dependencies, god classes, etc.
6. **Export Formats**: Add DOT, GraphML export endpoints

---

**Plan saved to**: `docs/plans/2025-11-02-rich-metadata-extraction.md`

**Total Tasks**: 16 tasks across 8 phases
**Estimated Time**: 8-12 hours for experienced engineer
**Testing Coverage**: Unit tests + Integration test + Manual verification
