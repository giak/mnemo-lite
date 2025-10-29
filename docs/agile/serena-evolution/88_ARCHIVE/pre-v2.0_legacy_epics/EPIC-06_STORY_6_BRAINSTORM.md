# EPIC-06 Story 6: Code Indexing Pipeline & API - Brainstorm Ultra-Complet

**Date**: 2025-10-16
**Status**: 🧠 **BRAINSTORM**
**Story Points**: 13 pts
**Phase**: 4 (Final Phase)
**Estimation**: 2 semaines → ~1-2 jours réels (vu vélocité)

---

## 🎯 Vision & Objectif

### User Story

> **En tant que** développeur utilisant MnemoLite,
> **Je veux** indexer une codebase complète via API,
> **Afin que** MnemoLite ingère et comprenne tout mon projet code.

### Pourquoi Story 6 ?

Story 6 **complète l'EPIC-06** en créant le **pipeline d'indexation end-to-end** qui utilise TOUS les composants qu'on a déjà construits:

✅ **Phase 0-3 Achievements** (building blocks PRÊTS):
- ✅ CodeChunkingService (Story 1)
- ✅ MetadataExtractorService (Story 3)
- ✅ DualEmbeddingService (Story 0.2)
- ✅ GraphConstructionService (Story 4)
- ✅ CodeChunkRepository (Story 2bis)
- ✅ Hybrid Search (Story 5)

➡️ **Story 6 = Orchestration + API Wrapper** autour de ces composants!

---

## 📊 État des Lieux

### Ce qu'on a DÉJÀ ✅

#### 1. Services existants

```python
# api/services/
code_chunking_service.py          # 390 lignes - Parse + chunk code
metadata_extractor_service.py     # 359 lignes - Extract metadata
dual_embedding_service.py          # ~400 lignes - Generate embeddings
graph_construction_service.py     # 455 lignes - Build call graphs
hybrid_code_search_service.py     # 514 lignes - Search orchestration
```

#### 2. Repository

```python
# api/db/repositories/
code_chunk_repository.py           # 431 lignes - CRUD + search
```

#### 3. Database schema

```sql
-- Table code_chunks (EXISTE)
CREATE TABLE code_chunks (
    id UUID PRIMARY KEY,
    file_path TEXT NOT NULL,
    language TEXT NOT NULL,
    chunk_type TEXT NOT NULL,
    name TEXT,
    source_code TEXT NOT NULL,
    start_line INT,
    end_line INT,
    embedding_text VECTOR(768),
    embedding_code VECTOR(768),
    metadata JSONB NOT NULL,
    indexed_at TIMESTAMPTZ DEFAULT NOW(),
    last_modified TIMESTAMPTZ,
    node_id UUID,
    repository TEXT,
    commit_hash TEXT
);

-- Tables nodes & edges (EXISTENT)
CREATE TABLE nodes (
    node_id UUID PRIMARY KEY,
    node_type TEXT,
    label TEXT,
    props JSONB,
    created_at TIMESTAMPTZ
);

CREATE TABLE edges (
    edge_id UUID PRIMARY KEY,
    source_node_id UUID,
    target_node_id UUID,
    relation_type TEXT,
    props JSONB,
    created_at TIMESTAMPTZ
);
```

#### 4. Indexes

✅ HNSW sur embedding_text + embedding_code
✅ GIN sur metadata
✅ Trigram sur source_code + name
✅ B-tree sur file_path, language, chunk_type

### Ce qu'il MANQUE ❌

1. **CodeIndexingService** - Service orchestration complet
2. **API /v1/code/index** - Endpoints REST
3. **Batch processing** - Indexer plusieurs fichiers
4. **Progress tracking** - Suivre l'indexation
5. **Error handling robuste** - Gérer fichiers invalides
6. **Tests end-to-end** - Tester pipeline complet

---

## 🏗️ Architecture Proposée

### Pipeline d'Indexation (7 étapes)

```
┌─────────────────────────────────────────────────────────────┐
│                  Code Indexing Pipeline                     │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 1: Language Detection                                 │
│  ───────────────────────────────────────────────────────    │
│  Input: file_path, content                                  │
│  Output: language ('python', 'javascript', etc.)            │
│  Tool: File extension mapping + magic bytes                 │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 2: Tree-sitter Parsing                                │
│  ───────────────────────────────────────────────────────    │
│  Service: CodeChunkingService                               │
│  Input: source_code, language                               │
│  Output: List[CodeChunk] (AST-based chunks)                 │
│  Fallback: Fixed-size chunking if parsing fails            │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 3: Metadata Extraction                                │
│  ───────────────────────────────────────────────────────    │
│  Service: MetadataExtractorService                          │
│  Input: CodeChunk (with AST node)                           │
│  Output: metadata{signature, params, complexity, calls...}  │
│  Graceful degradation: Partial metadata if extraction fails │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 4: Embedding Generation                               │
│  ───────────────────────────────────────────────────────    │
│  Service: DualEmbeddingService                              │
│  Input: CodeChunk.source_code + metadata.docstring          │
│  Output: embedding_text (768D), embedding_code (768D)       │
│  Domain: HYBRID (TEXT for docstrings, CODE for source)     │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 5: Storage (code_chunks)                              │
│  ───────────────────────────────────────────────────────    │
│  Repository: CodeChunkRepository                            │
│  Input: CodeChunk with embeddings + metadata                │
│  Output: chunk_id (UUID)                                    │
│  Storage: PostgreSQL code_chunks table                      │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 6: Graph Construction                                 │
│  ───────────────────────────────────────────────────────    │
│  Service: GraphConstructionService                          │
│  Input: repository, code_chunks (with metadata.calls)       │
│  Output: nodes + edges (call graph)                         │
│  Storage: PostgreSQL nodes & edges tables                   │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 7: Return Summary                                     │
│  ───────────────────────────────────────────────────────    │
│  Output: IndexingSummary{                                   │
│    indexed_chunks: 127,                                     │
│    indexed_nodes: 89,                                       │
│    indexed_edges: 243,                                      │
│    processing_time_ms: 4523,                                │
│    repository_id: "<uuid>"                                  │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
```

### Async Processing Strategy

**Option A: Synchronous (Simple)** ✅ RECOMMANDÉ pour v1
```python
async def index_files(files: List[FileInput]) -> IndexingSummary:
    for file in files:
        await _index_single_file(file)
    return summary
```

**Pros**:
- Simple à implémenter
- Error handling clair
- Progress tracking facile
- Tests simples

**Cons**:
- Pas de parallélisme
- Peut être lent pour grandes codebases

**Option B: Parallel Processing (Future)**
```python
async def index_files(files: List[FileInput]) -> IndexingSummary:
    tasks = [_index_single_file(file) for file in files]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return summary
```

**Recommandation**: **Option A pour Story 6**, Option B pour v1.5.0 si nécessaire.

---

## 🔨 Implémentation Détaillée

### 1. CodeIndexingService

```python
# api/services/code_indexing_service.py

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncEngine

from api.services.code_chunking_service import CodeChunkingService
from api.services.metadata_extractor_service import MetadataExtractorService
from api.services.dual_embedding_service import DualEmbeddingService
from api.services.graph_construction_service import GraphConstructionService
from api.db.repositories.code_chunk_repository import CodeChunkRepository
from api.models.code_chunk_models import CodeChunk, CodeChunkCreate

logger = logging.getLogger(__name__)


@dataclass
class FileInput:
    """Input file for indexing"""
    path: str
    content: str
    language: Optional[str] = None  # Auto-detect if None


@dataclass
class IndexingOptions:
    """Options for indexing pipeline"""
    extract_metadata: bool = True
    generate_embeddings: bool = True
    build_graph: bool = True
    repository: str = "default"
    commit_hash: Optional[str] = None


@dataclass
class IndexingSummary:
    """Summary of indexing operation"""
    repository: str
    indexed_files: int
    indexed_chunks: int
    indexed_nodes: int
    indexed_edges: int
    failed_files: int
    processing_time_ms: float
    errors: List[Dict[str, Any]]


@dataclass
class FileIndexingResult:
    """Result of indexing a single file"""
    file_path: str
    success: bool
    chunks_created: int
    nodes_created: int
    edges_created: int
    processing_time_ms: float
    error: Optional[str] = None


class CodeIndexingService:
    """
    Orchestrates the complete code indexing pipeline.

    Pipeline:
    1. Language detection
    2. Tree-sitter parsing → chunks
    3. Metadata extraction
    4. Embedding generation (dual: TEXT + CODE)
    5. Storage (code_chunks table)
    6. Graph construction (nodes + edges)
    7. Summary generation
    """

    def __init__(
        self,
        engine: AsyncEngine,
        chunking_service: CodeChunkingService,
        metadata_service: MetadataExtractorService,
        embedding_service: DualEmbeddingService,
        graph_service: GraphConstructionService,
        chunk_repository: CodeChunkRepository,
    ):
        self.engine = engine
        self.chunking_service = chunking_service
        self.metadata_service = metadata_service
        self.embedding_service = embedding_service
        self.graph_service = graph_service
        self.chunk_repository = chunk_repository

        self.logger = logging.getLogger(__name__)


    async def index_repository(
        self,
        files: List[FileInput],
        options: IndexingOptions,
    ) -> IndexingSummary:
        """
        Index a complete repository (multiple files).

        Args:
            files: List of files to index
            options: Indexing options

        Returns:
            IndexingSummary with statistics
        """
        start_time = datetime.now()

        # Statistics tracking
        indexed_files = 0
        indexed_chunks = 0
        failed_files = 0
        errors = []

        # Index each file sequentially (for now)
        file_results: List[FileIndexingResult] = []

        for file_input in files:
            try:
                result = await self._index_file(file_input, options)
                file_results.append(result)

                if result.success:
                    indexed_files += 1
                    indexed_chunks += result.chunks_created
                else:
                    failed_files += 1
                    errors.append({
                        "file": result.file_path,
                        "error": result.error
                    })

            except Exception as e:
                failed_files += 1
                errors.append({
                    "file": file_input.path,
                    "error": str(e)
                })
                self.logger.error(
                    f"Unexpected error indexing {file_input.path}: {e}",
                    exc_info=True
                )

        # Build graph for entire repository (if enabled)
        indexed_nodes = 0
        indexed_edges = 0

        if options.build_graph and indexed_chunks > 0:
            try:
                graph_stats = await self.graph_service.build_repository_graph(
                    repository=options.repository,
                    engine=self.engine
                )
                indexed_nodes = graph_stats["total_nodes"]
                indexed_edges = graph_stats["total_edges"]

            except Exception as e:
                self.logger.error(
                    f"Graph construction failed: {e}",
                    exc_info=True
                )
                errors.append({
                    "stage": "graph_construction",
                    "error": str(e)
                })

        # Calculate processing time
        end_time = datetime.now()
        processing_time_ms = (end_time - start_time).total_seconds() * 1000

        return IndexingSummary(
            repository=options.repository,
            indexed_files=indexed_files,
            indexed_chunks=indexed_chunks,
            indexed_nodes=indexed_nodes,
            indexed_edges=indexed_edges,
            failed_files=failed_files,
            processing_time_ms=processing_time_ms,
            errors=errors,
        )


    async def _index_file(
        self,
        file_input: FileInput,
        options: IndexingOptions,
    ) -> FileIndexingResult:
        """
        Index a single file through the pipeline.

        Steps:
        1. Detect language
        2. Chunk code (via Tree-sitter)
        3. Extract metadata
        4. Generate embeddings
        5. Store chunks

        Returns:
            FileIndexingResult with statistics
        """
        start_time = datetime.now()

        try:
            # Step 1: Language detection
            language = file_input.language or self._detect_language(file_input.path)

            if not language:
                return FileIndexingResult(
                    file_path=file_input.path,
                    success=False,
                    chunks_created=0,
                    nodes_created=0,
                    edges_created=0,
                    processing_time_ms=0,
                    error="Unable to detect language"
                )

            # Step 2: Chunk code via Tree-sitter
            chunks = await self.chunking_service.chunk_code(
                source_code=file_input.content,
                language=language,
                file_path=file_input.path,
                extract_metadata=options.extract_metadata,
            )

            if not chunks:
                return FileIndexingResult(
                    file_path=file_input.path,
                    success=False,
                    chunks_created=0,
                    nodes_created=0,
                    edges_created=0,
                    processing_time_ms=0,
                    error="No chunks extracted (empty file or parsing error)"
                )

            # Step 3: Metadata extraction (already done by chunking_service if enabled)
            # Metadata is in chunk.metadata

            # Step 4: Generate embeddings (if enabled)
            if options.generate_embeddings:
                for chunk in chunks:
                    embeddings = await self._generate_embeddings_for_chunk(chunk)
                    chunk.embedding_text = embeddings.get("text")
                    chunk.embedding_code = embeddings.get("code")

            # Step 5: Store chunks in database
            chunks_created = 0
            for chunk in chunks:
                chunk_create = CodeChunkCreate(
                    file_path=chunk.file_path,
                    language=language,
                    chunk_type=chunk.chunk_type.value,
                    name=chunk.name,
                    source_code=chunk.source_code,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    embedding_text=chunk.embedding_text,
                    embedding_code=chunk.embedding_code,
                    metadata=chunk.metadata or {},
                    repository=options.repository,
                    commit_hash=options.commit_hash,
                )

                await self.chunk_repository.add(chunk_create)
                chunks_created += 1

            # Calculate processing time
            end_time = datetime.now()
            processing_time_ms = (end_time - start_time).total_seconds() * 1000

            return FileIndexingResult(
                file_path=file_input.path,
                success=True,
                chunks_created=chunks_created,
                nodes_created=0,  # Will be calculated later during graph construction
                edges_created=0,
                processing_time_ms=processing_time_ms,
            )

        except Exception as e:
            self.logger.error(
                f"Error indexing {file_input.path}: {e}",
                exc_info=True
            )

            end_time = datetime.now()
            processing_time_ms = (end_time - start_time).total_seconds() * 1000

            return FileIndexingResult(
                file_path=file_input.path,
                success=False,
                chunks_created=0,
                nodes_created=0,
                edges_created=0,
                processing_time_ms=processing_time_ms,
                error=str(e),
            )


    async def _generate_embeddings_for_chunk(
        self,
        chunk: CodeChunk,
    ) -> Dict[str, List[float]]:
        """
        Generate dual embeddings for a code chunk.

        Strategy:
        - TEXT embedding: docstring + comments (if present)
        - CODE embedding: source code

        Returns:
            {'text': [...], 'code': [...]}
        """
        # For TEXT embedding, use docstring if available, else source code
        text_content = chunk.metadata.get("docstring") if chunk.metadata else None
        if not text_content:
            text_content = chunk.source_code

        # Generate both embeddings
        embeddings = await self.embedding_service.generate_embedding(
            text=chunk.source_code,  # For CODE embedding
            domain="HYBRID"  # Generate both TEXT and CODE
        )

        return embeddings


    def _detect_language(self, file_path: str) -> Optional[str]:
        """
        Detect programming language from file extension.

        Args:
            file_path: Path to file

        Returns:
            Language name ('python', 'javascript', etc.) or None
        """
        extension_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.go': 'go',
            '.rs': 'rust',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp',
        }

        # Extract extension
        import os
        _, ext = os.path.splitext(file_path)

        return extension_map.get(ext.lower())
```

**Estimation**: ~500-600 lignes avec docstrings et error handling complet

---

### 2. API Routes

```python
# api/routes/code_indexing_routes.py

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncEngine

from api.dependencies import get_engine
from api.services.code_indexing_service import (
    CodeIndexingService,
    FileInput,
    IndexingOptions,
    IndexingSummary,
)

router = APIRouter(prefix="/v1/code/index", tags=["v1_Code_Indexing"])


# ============================================================================
# Pydantic Models (Request/Response)
# ============================================================================

class FileInputModel(BaseModel):
    """Input file for indexing"""
    path: str = Field(..., description="File path (relative to repository root)")
    content: str = Field(..., description="File content (source code)")
    language: Optional[str] = Field(None, description="Programming language (auto-detected if not provided)")


class IndexRequest(BaseModel):
    """Request to index files"""
    repository: str = Field(..., description="Repository name/identifier")
    files: List[FileInputModel] = Field(..., description="List of files to index")
    commit_hash: Optional[str] = Field(None, description="Git commit hash (optional)")
    extract_metadata: bool = Field(True, description="Extract metadata (complexity, calls, etc.)")
    generate_embeddings: bool = Field(True, description="Generate dual embeddings (TEXT + CODE)")
    build_graph: bool = Field(True, description="Build call graph after indexing")

    class Config:
        json_schema_extra = {
            "example": {
                "repository": "my-project",
                "files": [
                    {
                        "path": "src/main.py",
                        "content": "def main():\n    print('Hello, World!')"
                    }
                ],
                "extract_metadata": True,
                "generate_embeddings": True,
                "build_graph": True
            }
        }


class IndexResponse(BaseModel):
    """Response from indexing operation"""
    repository: str
    indexed_files: int
    indexed_chunks: int
    indexed_nodes: int
    indexed_edges: int
    failed_files: int
    processing_time_ms: float
    errors: List[dict]


# ============================================================================
# Endpoints
# ============================================================================

@router.post(
    "",
    response_model=IndexResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Index code files",
    description="""
    Index a list of code files into MnemoLite.

    Pipeline:
    1. Language detection (if not provided)
    2. Tree-sitter parsing → semantic chunks
    3. Metadata extraction (complexity, calls, docstrings, etc.)
    4. Dual embedding generation (TEXT + CODE, 768D)
    5. Storage in PostgreSQL (code_chunks table)
    6. Call graph construction (nodes + edges tables)

    **Performance targets**:
    - <500ms per file (300 LOC average)
    - Batch processing supported

    **Error handling**:
    - Individual file failures don't stop batch
    - Errors returned in response
    - Partial success possible
    """,
)
async def index_files(
    request: IndexRequest,
    engine: AsyncEngine = Depends(get_engine),
):
    """
    Index code files into MnemoLite.

    Args:
        request: IndexRequest with files and options
        engine: Database engine (injected)

    Returns:
        IndexResponse with statistics
    """
    # Initialize services
    # (In real implementation, use dependency injection)
    from api.services.code_chunking_service import CodeChunkingService
    from api.services.metadata_extractor_service import MetadataExtractorService
    from api.services.dual_embedding_service import DualEmbeddingService
    from api.services.graph_construction_service import GraphConstructionService
    from api.db.repositories.code_chunk_repository import CodeChunkRepository

    chunking_service = CodeChunkingService()
    metadata_service = MetadataExtractorService()
    embedding_service = DualEmbeddingService()
    graph_service = GraphConstructionService(engine)
    chunk_repository = CodeChunkRepository(engine)

    indexing_service = CodeIndexingService(
        engine=engine,
        chunking_service=chunking_service,
        metadata_service=metadata_service,
        embedding_service=embedding_service,
        graph_service=graph_service,
        chunk_repository=chunk_repository,
    )

    # Convert request to service models
    files = [
        FileInput(
            path=f.path,
            content=f.content,
            language=f.language,
        )
        for f in request.files
    ]

    options = IndexingOptions(
        extract_metadata=request.extract_metadata,
        generate_embeddings=request.generate_embeddings,
        build_graph=request.build_graph,
        repository=request.repository,
        commit_hash=request.commit_hash,
    )

    # Index files
    summary = await indexing_service.index_repository(files, options)

    # Return response
    return IndexResponse(
        repository=summary.repository,
        indexed_files=summary.indexed_files,
        indexed_chunks=summary.indexed_chunks,
        indexed_nodes=summary.indexed_nodes,
        indexed_edges=summary.indexed_edges,
        failed_files=summary.failed_files,
        processing_time_ms=summary.processing_time_ms,
        errors=summary.errors,
    )


@router.get(
    "/repositories",
    summary="List indexed repositories",
    description="Get list of all indexed repositories with statistics",
)
async def list_repositories(
    engine: AsyncEngine = Depends(get_engine),
):
    """
    List all indexed repositories.

    Returns list of repositories with:
    - Repository name
    - Number of indexed files
    - Number of chunks
    - Last indexed timestamp
    """
    # Query code_chunks grouped by repository
    from sqlalchemy import text

    query = text("""
        SELECT
            repository,
            COUNT(DISTINCT file_path) as file_count,
            COUNT(*) as chunk_count,
            MAX(indexed_at) as last_indexed
        FROM code_chunks
        GROUP BY repository
        ORDER BY last_indexed DESC
    """)

    async with engine.begin() as conn:
        result = await conn.execute(query)
        rows = result.fetchall()

    repositories = [
        {
            "repository": row[0],
            "file_count": row[1],
            "chunk_count": row[2],
            "last_indexed": row[3].isoformat() if row[3] else None,
        }
        for row in rows
    ]

    return {"repositories": repositories}


@router.delete(
    "/repositories/{repository}",
    summary="Delete repository",
    description="Delete all indexed data for a repository",
)
async def delete_repository(
    repository: str,
    engine: AsyncEngine = Depends(get_engine),
):
    """
    Delete all indexed data for a repository.

    Deletes:
    - All code chunks
    - All nodes & edges associated with repository

    Args:
        repository: Repository name
    """
    from sqlalchemy import text

    # Delete code chunks
    delete_chunks = text("""
        DELETE FROM code_chunks
        WHERE repository = :repository
    """)

    # Delete nodes (assuming nodes have repository in props)
    delete_nodes = text("""
        DELETE FROM nodes
        WHERE props->>'repository' = :repository
    """)

    # Delete orphaned edges
    delete_edges = text("""
        DELETE FROM edges
        WHERE NOT EXISTS (
            SELECT 1 FROM nodes WHERE nodes.node_id = edges.source_node_id
        )
    """)

    async with engine.begin() as conn:
        result1 = await conn.execute(delete_chunks, {"repository": repository})
        result2 = await conn.execute(delete_nodes, {"repository": repository})
        result3 = await conn.execute(delete_edges)

    return {
        "repository": repository,
        "deleted_chunks": result1.rowcount,
        "deleted_nodes": result2.rowcount,
        "deleted_edges": result3.rowcount,
    }


@router.get(
    "/health",
    summary="Health check",
    description="Check if indexing service is operational",
)
async def health_check():
    """
    Health check for indexing service.

    Returns:
        - status: "ok"
        - services: List of available services
    """
    return {
        "status": "ok",
        "services": [
            "code_chunking",
            "metadata_extraction",
            "embedding_generation",
            "graph_construction",
        ]
    }
```

**Estimation**: ~400 lignes

---

## 🧪 Stratégie de Tests

### Tests Unitaires (CodeIndexingService)

```python
# tests/services/test_code_indexing_service.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from api.services.code_indexing_service import (
    CodeIndexingService,
    FileInput,
    IndexingOptions,
)


class TestCodeIndexingService:
    """Unit tests for CodeIndexingService"""

    @pytest.fixture
    def mock_services(self):
        """Create mock services"""
        return {
            "chunking": AsyncMock(),
            "metadata": AsyncMock(),
            "embedding": AsyncMock(),
            "graph": AsyncMock(),
            "repository": AsyncMock(),
        }

    @pytest.fixture
    def indexing_service(self, mock_services, test_engine):
        """Create indexing service with mocked dependencies"""
        return CodeIndexingService(
            engine=test_engine,
            chunking_service=mock_services["chunking"],
            metadata_service=mock_services["metadata"],
            embedding_service=mock_services["embedding"],
            graph_service=mock_services["graph"],
            chunk_repository=mock_services["repository"],
        )


    @pytest.mark.anyio
    async def test_language_detection_python(self, indexing_service):
        """Test language detection for Python file"""
        language = indexing_service._detect_language("main.py")
        assert language == "python"


    @pytest.mark.anyio
    async def test_language_detection_javascript(self, indexing_service):
        """Test language detection for JavaScript file"""
        language = indexing_service._detect_language("app.js")
        assert language == "javascript"


    @pytest.mark.anyio
    async def test_language_detection_unknown(self, indexing_service):
        """Test language detection for unknown extension"""
        language = indexing_service._detect_language("file.xyz")
        assert language is None


    @pytest.mark.anyio
    async def test_index_file_success(
        self,
        indexing_service,
        mock_services,
    ):
        """Test successful file indexing"""
        # Setup mocks
        mock_chunk = MagicMock()
        mock_chunk.source_code = "def hello(): pass"
        mock_chunk.metadata = {"docstring": "Hello function"}

        mock_services["chunking"].chunk_code.return_value = [mock_chunk]
        mock_services["embedding"].generate_embedding.return_value = {
            "text": [0.1] * 768,
            "code": [0.2] * 768,
        }

        # Index file
        file_input = FileInput(
            path="test.py",
            content="def hello(): pass",
            language="python",
        )

        options = IndexingOptions(
            extract_metadata=True,
            generate_embeddings=True,
            build_graph=False,
            repository="test-repo",
        )

        result = await indexing_service._index_file(file_input, options)

        # Assertions
        assert result.success is True
        assert result.chunks_created == 1
        assert result.file_path == "test.py"
        assert result.error is None


    @pytest.mark.anyio
    async def test_index_file_parsing_error(
        self,
        indexing_service,
        mock_services,
    ):
        """Test file indexing with parsing error"""
        # Setup mock to return no chunks
        mock_services["chunking"].chunk_code.return_value = []

        file_input = FileInput(
            path="invalid.py",
            content="invalid python code {{{",
            language="python",
        )

        options = IndexingOptions(repository="test-repo")

        result = await indexing_service._index_file(file_input, options)

        # Assertions
        assert result.success is False
        assert result.chunks_created == 0
        assert "No chunks extracted" in result.error


    @pytest.mark.anyio
    async def test_index_repository_multiple_files(
        self,
        indexing_service,
        mock_services,
    ):
        """Test indexing multiple files"""
        # Setup mocks
        mock_chunk = MagicMock()
        mock_services["chunking"].chunk_code.return_value = [mock_chunk]
        mock_services["embedding"].generate_embedding.return_value = {
            "text": [0.1] * 768,
            "code": [0.2] * 768,
        }
        mock_services["graph"].build_repository_graph.return_value = {
            "total_nodes": 10,
            "total_edges": 15,
        }

        # Index repository
        files = [
            FileInput(path="file1.py", content="code1", language="python"),
            FileInput(path="file2.py", content="code2", language="python"),
        ]

        options = IndexingOptions(
            repository="test-repo",
            build_graph=True,
        )

        summary = await indexing_service.index_repository(files, options)

        # Assertions
        assert summary.indexed_files == 2
        assert summary.indexed_chunks == 2
        assert summary.indexed_nodes == 10
        assert summary.indexed_edges == 15
        assert summary.failed_files == 0
```

**Estimation**: ~300 lignes (15-20 tests)

---

### Tests d'Intégration (API)

```python
# tests/integration/test_code_indexing_integration.py

import pytest
from httpx import AsyncClient

from api.main import app


class TestCodeIndexingIntegration:
    """Integration tests for code indexing API"""

    @pytest.mark.anyio
    async def test_index_single_python_file(self, test_engine):
        """Test indexing a single Python file"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            request_data = {
                "repository": "test-repo",
                "files": [
                    {
                        "path": "main.py",
                        "content": "def calculate_total(items):\n    return sum(items)"
                    }
                ],
                "extract_metadata": True,
                "generate_embeddings": True,
                "build_graph": True
            }

            response = await client.post(
                "/v1/code/index",
                json=request_data
            )

            assert response.status_code == 201
            data = response.json()

            assert data["repository"] == "test-repo"
            assert data["indexed_files"] == 1
            assert data["indexed_chunks"] >= 1
            assert data["failed_files"] == 0


    @pytest.mark.anyio
    async def test_index_multiple_files(self, test_engine):
        """Test indexing multiple files"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            request_data = {
                "repository": "multi-file-repo",
                "files": [
                    {
                        "path": "utils.py",
                        "content": "def helper():\n    pass"
                    },
                    {
                        "path": "main.py",
                        "content": "from utils import helper\n\ndef main():\n    helper()"
                    }
                ],
                "build_graph": True
            }

            response = await client.post(
                "/v1/code/index",
                json=request_data
            )

            assert response.status_code == 201
            data = response.json()

            assert data["indexed_files"] == 2
            assert data["indexed_nodes"] >= 2  # helper + main functions
            assert data["indexed_edges"] >= 1  # main calls helper


    @pytest.mark.anyio
    async def test_list_repositories(self, test_engine):
        """Test listing indexed repositories"""
        # First index a repository
        async with AsyncClient(app=app, base_url="http://test") as client:
            await client.post(
                "/v1/code/index",
                json={
                    "repository": "list-test-repo",
                    "files": [
                        {"path": "test.py", "content": "def test(): pass"}
                    ]
                }
            )

            # List repositories
            response = await client.get("/v1/code/index/repositories")

            assert response.status_code == 200
            data = response.json()

            assert "repositories" in data
            assert len(data["repositories"]) > 0

            # Find our repository
            our_repo = next(
                (r for r in data["repositories"] if r["repository"] == "list-test-repo"),
                None
            )
            assert our_repo is not None
            assert our_repo["file_count"] >= 1


    @pytest.mark.anyio
    async def test_delete_repository(self, test_engine):
        """Test deleting a repository"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Index a repository
            await client.post(
                "/v1/code/index",
                json={
                    "repository": "delete-test-repo",
                    "files": [
                        {"path": "test.py", "content": "def test(): pass"}
                    ]
                }
            )

            # Delete repository
            response = await client.delete(
                "/v1/code/index/repositories/delete-test-repo"
            )

            assert response.status_code == 200
            data = response.json()

            assert data["repository"] == "delete-test-repo"
            assert data["deleted_chunks"] >= 1


    @pytest.mark.anyio
    async def test_health_check(self):
        """Test health check endpoint"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/v1/code/index/health")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "ok"
            assert "services" in data
```

**Estimation**: ~250 lignes (12-15 tests)

---

### Tests End-to-End

```python
# tests/end_to_end/test_indexing_pipeline_e2e.py

import pytest
from httpx import AsyncClient

from api.main import app


class TestIndexingPipelineE2E:
    """End-to-end tests for complete indexing pipeline"""

    @pytest.mark.anyio
    async def test_complete_indexing_workflow(self, test_engine):
        """
        Test complete workflow:
        1. Index Python files
        2. Verify chunks stored
        3. Verify graph constructed
        4. Search indexed code
        5. Query graph
        """
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Step 1: Index files
            index_request = {
                "repository": "e2e-test",
                "files": [
                    {
                        "path": "calculator.py",
                        "content": """
def add(a, b):
    '''Add two numbers'''
    return a + b

def multiply(a, b):
    '''Multiply two numbers'''
    return a * b

def calculate_total(items):
    '''Calculate total using add'''
    result = 0
    for item in items:
        result = add(result, item)
    return result
"""
                    }
                ],
                "extract_metadata": True,
                "generate_embeddings": True,
                "build_graph": True
            }

            index_response = await client.post(
                "/v1/code/index",
                json=index_request
            )

            assert index_response.status_code == 201
            index_data = index_response.json()

            assert index_data["indexed_files"] == 1
            assert index_data["indexed_chunks"] >= 3  # add, multiply, calculate_total
            assert index_data["indexed_nodes"] >= 3
            assert index_data["indexed_edges"] >= 1  # calculate_total calls add

            # Step 2: Search indexed code
            search_request = {
                "query": "addition",
                "repository": "e2e-test",
                "top_k": 5
            }

            search_response = await client.post(
                "/v1/code/search/hybrid",
                json=search_request
            )

            assert search_response.status_code == 200
            search_data = search_response.json()

            # Should find 'add' function
            results = search_data["results"]
            assert len(results) > 0

            # Check first result
            top_result = results[0]
            assert "add" in top_result["name"].lower() or "add" in top_result["source_code"].lower()

            # Step 3: Query graph
            # Find calculate_total node ID first
            calculate_total_chunk = next(
                (r for r in results if "calculate_total" in r["name"]),
                None
            )

            if calculate_total_chunk and calculate_total_chunk.get("node_id"):
                graph_response = await client.post(
                    "/v1/code/graph/traverse",
                    json={
                        "start_node_id": calculate_total_chunk["node_id"],
                        "direction": "outbound",
                        "max_depth": 1
                    }
                )

                assert graph_response.status_code == 200
                graph_data = graph_response.json()

                # Should find 'add' as dependency
                nodes = graph_data.get("nodes", [])
                assert any("add" in node["label"] for node in nodes)
```

**Estimation**: ~200 lignes (5-8 tests end-to-end)

---

## 📊 Métriques de Succès

### Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Indexing speed** | <500ms/file (300 LOC) | P95 latency |
| **Batch processing** | 100 files in <1 minute | Total time for 100 files |
| **Memory usage** | <2 GB RAM | Peak memory during indexing |
| **Storage efficiency** | <10 MB per 1000 LOC | Database size |

### Acceptance Criteria

✅ **Functional**:
- [ ] POST /v1/code/index endpoint operational
- [ ] Batch indexing (multiple files) works
- [ ] Error handling for invalid files
- [ ] GET /v1/code/index/repositories lists repos
- [ ] DELETE /v1/code/index/repositories/{repo} deletes data

✅ **Performance**:
- [ ] <500ms per Python file (300 LOC) - P95
- [ ] Can index 100 files in <60 seconds

✅ **Quality**:
- [ ] >85% test coverage
- [ ] All tests passing (unit + integration + e2e)
- [ ] OpenAPI documentation complete
- [ ] Error messages clear and actionable

✅ **Integration**:
- [ ] Uses all existing services (Stories 1-5)
- [ ] No breaking changes to existing APIs
- [ ] Compatible with existing code_chunks schema

---

## 🚨 Risques & Mitigations

### Risque 1: RAM Overflow (Batch Processing)

**Risk**: Indexer de nombreux fichiers peut saturer RAM

**Probability**: Medium
**Impact**: High

**Mitigation**:
1. Process files sequentially (not parallel) pour v1
2. Add memory monitoring
3. Chunk large files before processing
4. Add rate limiting (max N files per request)

### Risque 2: Slow Performance

**Risk**: Pipeline trop lent pour grandes codebases

**Probability**: Medium
**Impact**: Medium

**Mitigation**:
1. Profile pipeline steps
2. Identify bottlenecks (likely embedding generation)
3. Add caching for embeddings
4. Consider async parallel processing for v1.1

### Risque 3: Database Errors

**Risk**: Erreurs DB lors stockage chunks/nodes

**Probability**: Low
**Impact**: High

**Mitigation**:
1. Wrap all DB calls in try/except
2. Transaction rollback on errors
3. Partial success possible (some files succeed)
4. Comprehensive logging

---

## 📝 Plan d'Implémentation

### Day 1: Core Service (4-6 hours)

1. **CodeIndexingService** (3-4h)
   - [ ] Créer structure de base
   - [ ] Implémenter `_detect_language()`
   - [ ] Implémenter `_index_file()`
   - [ ] Implémenter `index_repository()`
   - [ ] Add logging

2. **Tests unitaires service** (1-2h)
   - [ ] Tests language detection
   - [ ] Tests single file indexing
   - [ ] Tests error handling

### Day 2: API Routes + Tests (4-6 hours)

1. **API Routes** (2-3h)
   - [ ] POST /v1/code/index
   - [ ] GET /v1/code/index/repositories
   - [ ] DELETE /v1/code/index/repositories/{repo}
   - [ ] GET /v1/code/index/health

2. **Tests intégration** (2-3h)
   - [ ] Tests API endpoints
   - [ ] Tests end-to-end workflow
   - [ ] Tests error cases

3. **Documentation** (1h)
   - [ ] OpenAPI docs
   - [ ] Update README
   - [ ] Completion report

---

## ✅ Conclusion

### Story 6 en résumé

**Complexité**: 🟡 **MOYENNE** (principalement de l'orchestration)

**Estimation réaliste**: 1-2 jours (vs 14 jours estimés)

**Pourquoi rapide?**:
- ✅ Tous les building blocks EXISTENT (Stories 0-5)
- ✅ Story 6 = Wrapper + Orchestration
- ✅ Pas de nouveaux algorithmes compliqués
- ✅ Architecture déjà validée

**Livrables**:
1. CodeIndexingService (500-600 lignes)
2. API routes (400 lignes)
3. Tests (750 lignes total)
4. **Total: ~1,700 lignes** (vs ~2,500 pour Story 5)

**EPIC-06 après Story 6**: ✅ **100% COMPLETE** 🎉

---

**Date**: 2025-10-16
**Auteur**: Claude Code (Assistant)
**Status**: 🧠 **BRAINSTORM COMPLET** - Ready for implementation

**Next Step**: User approval → Implementation Story 6!
