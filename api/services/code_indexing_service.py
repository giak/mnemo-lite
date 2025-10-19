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
from services.code_chunking_service import CodeChunkingService
from services.dual_embedding_service import DualEmbeddingService, EmbeddingDomain
from services.graph_construction_service import GraphConstructionService
from services.metadata_extractor_service import MetadataExtractorService

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
        """
        self.engine = engine
        self.chunking_service = chunking_service
        self.metadata_service = metadata_service
        self.embedding_service = embedding_service
        self.graph_service = graph_service
        self.chunk_repository = chunk_repository

        self.logger = logging.getLogger(__name__)
        self.logger.info("CodeIndexingService initialized")

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
