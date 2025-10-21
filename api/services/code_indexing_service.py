"""
CodeIndexingService for EPIC-06 Phase 4 Story 6.

Orchestrates the complete code indexing pipeline, coordinating all building blocks
from previous stories to provide end-to-end code ingestion.
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncEngine

from db.repositories.code_chunk_repository import CodeChunkRepository
from models.code_chunk_models import ChunkType, CodeChunk, CodeChunkCreate
from services.caches.cascade_cache import CascadeCache
from services.code_chunking_service import CodeChunkingService
from services.dual_embedding_service import DualEmbeddingService, EmbeddingDomain
from services.graph_construction_service import GraphConstructionService
from services.metadata_extractor_service import MetadataExtractorService
from services.symbol_path_service import SymbolPathService  # EPIC-11

logger = logging.getLogger(__name__)


@dataclass
class FileInput:
    """Input file for indexing."""

    path: str
    content: str
    language: Optional[str] = None  # Auto-detect if None


@dataclass
class IndexingOptions:
    """Options for indexing pipeline."""

    extract_metadata: bool = True
    generate_embeddings: bool = True
    build_graph: bool = True
    repository: str = "default"
    repository_root: str = "/app"  # EPIC-11: Absolute path for name_path generation
    commit_hash: Optional[str] = None


@dataclass
class IndexingSummary:
    """Summary of indexing operation."""

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
    """Result of indexing a single file."""

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

    Pipeline (7 steps):
    1. Language detection
    2. Tree-sitter parsing → chunks
    3. Metadata extraction
    4. Embedding generation (dual: TEXT + CODE)
    5. Storage (code_chunks table)
    6. Graph construction (nodes + edges)
    7. Summary generation

    This service coordinates all building blocks from Stories 0-5:
    - CodeChunkingService (Story 1)
    - MetadataExtractorService (Story 3)
    - DualEmbeddingService (Story 0.2)
    - GraphConstructionService (Story 4)
    - CodeChunkRepository (Story 2bis)
    """

    def __init__(
        self,
        engine: AsyncEngine,
        chunking_service: CodeChunkingService,
        metadata_service: MetadataExtractorService,
        embedding_service: DualEmbeddingService,
        graph_service: GraphConstructionService,
        chunk_repository: CodeChunkRepository,
        chunk_cache: Optional[CascadeCache] = None,
        symbol_path_service: Optional[SymbolPathService] = None,  # EPIC-11
    ):
        """
        Initialize CodeIndexingService with all required dependencies.

        Args:
            engine: Database async engine
            chunking_service: Service for parsing and chunking code
            metadata_service: Service for extracting metadata
            embedding_service: Service for generating embeddings
            graph_service: Service for constructing call graphs
            chunk_repository: Repository for storing code chunks
            chunk_cache: Optional L1/L2 cascade cache for code chunks (Story 10.3)
            symbol_path_service: Optional service for generating hierarchical name_path (EPIC-11)
        """
        self.engine = engine
        self.chunking_service = chunking_service
        self.metadata_service = metadata_service
        self.embedding_service = embedding_service
        self.graph_service = graph_service
        self.chunk_repository = chunk_repository
        self.chunk_cache = chunk_cache  # CascadeCache from dependencies.py
        self.symbol_path_service = symbol_path_service or SymbolPathService()  # EPIC-11

        self.logger = logging.getLogger(__name__)
        self.logger.info(
            f"CodeIndexingService initialized with L1/L2 Cascade Cache and SymbolPathService "
            f"(cache_enabled={self.chunk_cache is not None})"
        )

    async def index_repository(
        self,
        files: List[FileInput],
        options: IndexingOptions,
    ) -> IndexingSummary:
        """
        Index a complete repository (multiple files).

        Args:
            files: List of files to index
            options: Indexing options (metadata, embeddings, graph)

        Returns:
            IndexingSummary with statistics and errors
        """
        start_time = datetime.now()

        # Statistics tracking
        indexed_files = 0
        indexed_chunks = 0
        failed_files = 0
        errors = []

        # Index each file sequentially (for v1)
        # Future: Consider parallel processing in v1.1
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
                    errors.append({"file": result.file_path, "error": result.error})

            except Exception as e:
                failed_files += 1
                errors.append({"file": file_input.path, "error": str(e)})
                self.logger.error(
                    f"Unexpected error indexing {file_input.path}: {e}",
                    exc_info=True,
                )

        # Build graph for entire repository (if enabled)
        indexed_nodes = 0
        indexed_edges = 0

        # PHASE 2: Graph construction RE-ENABLED after fixing model pre-loading
        # The blocking issue was caused by lazy model loading, now pre-loaded at startup
        if options.build_graph and indexed_chunks > 0:
            try:
                graph_stats = await self.graph_service.build_graph_for_repository(
                    repository=options.repository
                )
                indexed_nodes = graph_stats.total_nodes
                indexed_edges = graph_stats.total_edges

                self.logger.info(
                    f"Graph construction complete: {indexed_nodes} nodes, {indexed_edges} edges"
                )

            except Exception as e:
                self.logger.error(
                    f"Graph construction failed: {e}", exc_info=True
                )
                errors.append({"stage": "graph_construction", "error": str(e)})

        # Calculate processing time
        end_time = datetime.now()
        processing_time_ms = (end_time - start_time).total_seconds() * 1000

        self.logger.info(
            f"🎯 PHASE 1: Repository indexing complete: {indexed_files} files, "
            f"{indexed_chunks} chunks, {indexed_nodes} nodes, "
            f"{indexed_edges} edges in {processing_time_ms:.0f}ms"
        )

        self.logger.info(f"🚀 PHASE 1: About to return IndexingSummary...")

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
        0. Invalidate cache (Story 10.4 - remove stale data from previous versions)
        1. Detect language
        2. Chunk code (via Tree-sitter)
        3. Extract metadata
        4. Generate embeddings
        5. Store chunks

        Args:
            file_input: File to index
            options: Indexing options

        Returns:
            FileIndexingResult with statistics
        """
        start_time = datetime.now()

        try:
            # Step 0: INVALIDATE CACHE (Story 10.4 - automatic cache invalidation)
            # Clear any cached chunks for this file (all versions/hashes)
            # This ensures stale data from previous file versions is removed
            if self.chunk_cache:
                try:
                    await self.chunk_cache.invalidate(file_input.path)
                    self.logger.debug(
                        f"Cache invalidated for {file_input.path} (preparing for re-index)"
                    )
                except Exception as e:
                    # Cache invalidation failure should not break indexing
                    self.logger.warning(
                        f"Failed to invalidate cache for {file_input.path}: {e}"
                    )

            # Step 1: Language detection
            language = file_input.language or self._detect_language(
                file_input.path
            )

            if not language:
                return FileIndexingResult(
                    file_path=file_input.path,
                    success=False,
                    chunks_created=0,
                    nodes_created=0,
                    edges_created=0,
                    processing_time_ms=0,
                    error="Unable to detect language",
                )

            # L1/L2 CASCADE CACHE LOOKUP (before expensive chunking/embedding pipeline)
            if self.chunk_cache:
                cached_chunks = self.chunk_cache.get(file_input.path, file_input.content)
                if cached_chunks:
                    # Cache HIT: Skip entire pipeline and return cached result
                    end_time = datetime.now()
                    processing_time_ms = (end_time - start_time).total_seconds() * 1000

                    self.logger.info(
                        f"L1/L2 cascade cache HIT for {file_input.path} → {len(cached_chunks)} chunks "
                        f"(skipped chunking/embedding/storage pipeline) in {processing_time_ms:.1f}ms"
                    )

                    return FileIndexingResult(
                        file_path=file_input.path,
                        success=True,
                        chunks_created=len(cached_chunks),
                        nodes_created=0,
                        edges_created=0,
                        processing_time_ms=processing_time_ms,
                    )

            # Step 2: Chunk code via Tree-sitter
            chunks = await self.chunking_service.chunk_code(
                source_code=file_input.content,
                language=language,
                file_path=file_input.path,
            )

            if not chunks:
                return FileIndexingResult(
                    file_path=file_input.path,
                    success=False,
                    chunks_created=0,
                    nodes_created=0,
                    edges_created=0,
                    processing_time_ms=0,
                    error="No chunks extracted (empty file or parsing error)",
                )

            # PHASE 1: Enforce aggressive chunk limit per file (50 chunks max)
            MAX_CHUNKS_PER_FILE = 50
            if len(chunks) > MAX_CHUNKS_PER_FILE:
                self.logger.warning(
                    f"File {file_input.path} has {len(chunks)} chunks, "
                    f"truncating to {MAX_CHUNKS_PER_FILE} (aggressive PHASE 1 limit)"
                )
                chunks = chunks[:MAX_CHUNKS_PER_FILE]

            # Step 3: Metadata extraction (already done by chunking_service if enabled)
            # Metadata is in chunk.metadata

            # Step 4: Generate embeddings (if enabled) - USE BATCH PROCESSING
            # PHASE 1 OPTIMIZATION: Generate TEXT OR CODE (not both) based on chunk characteristics
            chunk_embeddings = {}
            if options.generate_embeddings:
                try:
                    # Group chunks by domain (TEXT vs CODE)
                    text_chunks = []  # Chunks with docstrings → TEXT embedding
                    code_chunks = []  # Pure code → CODE embedding

                    for i, chunk in enumerate(chunks):
                        # Determine domain based on presence of docstring
                        has_docstring = bool(chunk.metadata and chunk.metadata.get("docstring"))
                        if has_docstring:
                            text_chunks.append((i, chunk))
                        else:
                            code_chunks.append((i, chunk))

                    self.logger.info(
                        f"PHASE 1: Batch embedding {len(text_chunks)} TEXT chunks "
                        f"+ {len(code_chunks)} CODE chunks (50% faster than HYBRID)"
                    )

                    # Batch process TEXT chunks
                    if text_chunks:
                        text_indices, text_chunk_objs = zip(*text_chunks)
                        text_sources = [c.source_code for c in text_chunk_objs]
                        text_results = await self.embedding_service.generate_embeddings_batch(
                            texts=text_sources,
                            domain=EmbeddingDomain.TEXT,
                            show_progress_bar=True
                        )
                        for idx, result in zip(text_indices, text_results):
                            if result and result.get("text"):
                                chunk_embeddings[idx] = {
                                    "text": result.get("text"),
                                    "code": None  # Only TEXT embedding
                                }

                    # Batch process CODE chunks
                    if code_chunks:
                        code_indices, code_chunk_objs = zip(*code_chunks)
                        code_sources = [c.source_code for c in code_chunk_objs]
                        code_results = await self.embedding_service.generate_embeddings_batch(
                            texts=code_sources,
                            domain=EmbeddingDomain.CODE,
                            show_progress_bar=True
                        )
                        for idx, result in zip(code_indices, code_results):
                            if result and result.get("code"):
                                chunk_embeddings[idx] = {
                                    "text": None,  # Only CODE embedding
                                    "code": result.get("code")
                                }

                    self.logger.info(
                        f"Batch embedding complete: {len(chunk_embeddings)}/{len(chunks)} successful "
                        f"({len(text_chunks)} TEXT, {len(code_chunks)} CODE)"
                    )

                except Exception as e:
                    self.logger.error(f"Batch embedding generation failed: {e}", exc_info=True)
                    # Fall back to individual processing with retry
                    self.logger.warning("Falling back to individual embedding generation...")
                    for i, chunk in enumerate(chunks):
                        try:
                            result = await self._generate_embedding_with_retry(chunk, i, max_retries=1)
                            if result and (result.get("text") or result.get("code")):
                                chunk_embeddings[i] = result
                        except Exception as chunk_error:
                            self.logger.error(f"Failed to generate embedding for chunk {i}: {chunk_error}")

            # Step 5: Store chunks in database (BATCH INSERT - PHASE 1 OPTIMIZATION)
            chunks_created = 0
            chunks_skipped = 0

            # EPIC-11 Story 11.1: Generate name_path for all chunks
            # This must happen AFTER chunking but BEFORE creating CodeChunkCreate objects
            chunk_name_paths = {}  # Map: chunk_index → name_path

            self.logger.info(f"🔍 EPIC-11: Generating name_path for {len(chunks)} chunks")

            for i, chunk in enumerate(chunks):
                # Extract parent context (for methods in classes)
                parent_context = self.symbol_path_service.extract_parent_context(chunk, chunks)

                # Generate hierarchical name_path
                name_path = self.symbol_path_service.generate_name_path(
                    chunk_name=chunk.name or "unknown",
                    file_path=file_input.path,
                    repository_root=options.repository_root,
                    parent_context=parent_context,
                    language=language
                )

                chunk_name_paths[i] = name_path

                self.logger.debug(
                    f"Generated name_path for chunk {i} ({chunk.name}): {name_path} "
                    f"(parent_context: {parent_context})"
                )

            self.logger.info(f"✅ EPIC-11: name_path generation complete for {len(chunk_name_paths)} chunks")

            # Prepare all chunks for batch insert
            chunks_to_insert = []

            for i, chunk in enumerate(chunks):
                # Get embeddings for this chunk (if generated)
                embeddings = chunk_embeddings.get(i, {})
                embedding_text = embeddings.get("text") if embeddings else None
                embedding_code = embeddings.get("code") if embeddings else None

                # Skip chunk if embeddings were required but not generated
                if options.generate_embeddings and not embedding_text and not embedding_code:
                    self.logger.warning(
                        f"Skipping chunk {i} ({chunk.name}) - no embeddings available"
                    )
                    chunks_skipped += 1
                    continue  # Skip this chunk

                chunk_create = CodeChunkCreate(
                    file_path=chunk.file_path,
                    language=language,
                    chunk_type=chunk.chunk_type,
                    name=chunk.name,
                    name_path=chunk_name_paths.get(i),  # EPIC-11: Hierarchical qualified name
                    source_code=chunk.source_code,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    embedding_text=embedding_text,  # May be None
                    embedding_code=embedding_code,  # May be None
                    metadata=chunk.metadata or {},
                    repository=options.repository,
                    commit_hash=options.commit_hash,
                )
                chunks_to_insert.append(chunk_create)

            # PHASE 1 OPTIMIZATION: Batch insert all chunks in single query (10-50× faster)
            if chunks_to_insert:
                try:
                    self.logger.info(
                        f"💾 PHASE 1: Batch inserting {len(chunks_to_insert)} chunks "
                        f"(was {len(chunks_to_insert)} sequential inserts before)"
                    )
                    chunks_created = await self.chunk_repository.add_batch(chunks_to_insert)
                    self.logger.info(f"✅ Batch insert successful: {chunks_created} chunks stored")
                except Exception as e:
                    self.logger.error(f"Batch insert failed, falling back to sequential: {e}")
                    # Fallback to sequential inserts if batch fails
                    for chunk_create in chunks_to_insert:
                        try:
                            await self.chunk_repository.add(chunk_create)
                            chunks_created += 1
                        except Exception as chunk_error:
                            self.logger.error(f"Failed to store chunk: {chunk_error}")
                            chunks_skipped += 1

            # POPULATE L1 CACHE (after successful storage)
            if self.chunk_cache and chunks_created > 0:
                try:
                    # Serialize chunks for caching (store as list of dicts)
                    serialized_chunks = []
                    for i, chunk in enumerate(chunks[:chunks_created]):  # Only cache successfully stored chunks
                        serialized_chunks.append({
                            "file_path": chunk.file_path,
                            "language": language,
                            "chunk_type": chunk.chunk_type.value if hasattr(chunk.chunk_type, 'value') else str(chunk.chunk_type),
                            "name": chunk.name,
                            "name_path": chunk_name_paths.get(i),  # EPIC-11: Include name_path in cache
                            "source_code": chunk.source_code,
                            "start_line": chunk.start_line,
                            "end_line": chunk.end_line,
                            "metadata": chunk.metadata or {},
                        })

                    await self.chunk_cache.put_chunks(file_input.path, file_input.content, serialized_chunks)
                    self.logger.debug(
                        f"L1/L2 cascade cache populated for {file_input.path} → {len(serialized_chunks)} chunks cached"
                    )
                except Exception as e:
                    # Cache populate failure should not break the indexing pipeline
                    self.logger.warning(f"Failed to populate L1/L2 cascade cache for {file_input.path}: {e}")

            # Calculate processing time
            end_time = datetime.now()
            processing_time_ms = (end_time - start_time).total_seconds() * 1000

            self.logger.info(
                f"✅ PHASE 1: File indexed successfully: {file_input.path} → {chunks_created} chunks in {processing_time_ms:.0f}ms"
            )

            return FileIndexingResult(
                file_path=file_input.path,
                success=True,
                chunks_created=chunks_created,
                nodes_created=0,  # Calculated later during graph construction
                edges_created=0,
                processing_time_ms=processing_time_ms,
            )

        except Exception as e:
            self.logger.error(
                f"Error indexing {file_input.path}: {e}", exc_info=True
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

    async def _generate_embedding_with_retry(
        self,
        chunk: CodeChunk,
        chunk_index: int,
        max_retries: int = 3
    ) -> Dict[str, Optional[List[float]]]:
        """
        Generate embeddings for a chunk with retry logic.

        Args:
            chunk: Code chunk to generate embeddings for
            chunk_index: Index of the chunk (for logging)
            max_retries: Maximum number of retry attempts

        Returns:
            {'text': [...], 'code': [...]} or {'text': None, 'code': None}
        """
        for attempt in range(max_retries):
            try:
                embeddings = await self._generate_embeddings_for_chunk(chunk)
                if embeddings and (embeddings.get("text") or embeddings.get("code")):
                    return embeddings
            except Exception as e:
                self.logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed for chunk {chunk_index}: {e}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff

        # All retries failed
        self.logger.error(f"Failed to generate embeddings for chunk {chunk_index} after {max_retries} attempts")
        return {"text": None, "code": None}

    async def _generate_embeddings_for_chunk(
        self,
        chunk: CodeChunk,
    ) -> Dict[str, Optional[List[float]]]:
        """
        Generate single embedding for a code chunk (TEXT OR CODE, not both).

        PHASE 1 OPTIMIZATION: Generate only one embedding based on chunk characteristics.

        Strategy:
        - TEXT embedding: If chunk has docstring (natural language understanding)
        - CODE embedding: Otherwise (code semantic understanding)

        Args:
            chunk: Code chunk to generate embeddings for

        Returns:
            {'text': [...], 'code': None} OR {'text': None, 'code': [...]}
        """
        try:
            # PHASE 1: Determine domain based on presence of docstring
            has_docstring = bool(chunk.metadata and chunk.metadata.get("docstring"))
            domain = EmbeddingDomain.TEXT if has_docstring else EmbeddingDomain.CODE

            self.logger.debug(
                f"Generating {domain.value.upper()} embedding for chunk "
                f"(docstring={'yes' if has_docstring else 'no'})"
            )

            # Generate single embedding (TEXT OR CODE)
            embeddings = await self.embedding_service.generate_embedding(
                text=chunk.source_code,
                domain=domain
            )

            # Return single embedding (50% faster than HYBRID)
            if domain == EmbeddingDomain.TEXT:
                return {
                    "text": embeddings.get("text"),
                    "code": None
                }
            else:
                return {
                    "text": None,
                    "code": embeddings.get("code")
                }

        except Exception as e:
            self.logger.error(
                f"Failed to generate embeddings for chunk: {e}", exc_info=True
            )
            return {"text": None, "code": None}

    def _detect_language(self, file_path: str) -> Optional[str]:
        """
        Detect programming language from file extension.

        Args:
            file_path: Path to file

        Returns:
            Language name ('python', 'javascript', etc.) or None
        """
        extension_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".cxx": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".rb": "ruby",
            ".php": "php",
            ".cs": "csharp",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
        }

        # Extract extension
        _, ext = os.path.splitext(file_path)

        return extension_map.get(ext.lower())
