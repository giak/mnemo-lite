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
from services.dual_embedding_service import DualEmbeddingService
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
            f"Repository indexing complete: {indexed_files} files, "
            f"{indexed_chunks} chunks, {indexed_nodes} nodes, "
            f"{indexed_edges} edges in {processing_time_ms:.0f}ms"
        )

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

            # Step 3: Metadata extraction (already done by chunking_service if enabled)
            # Metadata is in chunk.metadata

            # Step 4: Generate embeddings (if enabled) with batch processing
            chunk_embeddings = {}
            if options.generate_embeddings:
                # Process embeddings in batches for better performance
                batch_size = 10  # Process 10 chunks at a time

                for batch_start in range(0, len(chunks), batch_size):
                    batch_end = min(batch_start + batch_size, len(chunks))
                    batch_chunks = chunks[batch_start:batch_end]

                    # Create tasks for parallel processing
                    tasks = []
                    for i, chunk in enumerate(batch_chunks, start=batch_start):
                        task = self._generate_embedding_with_retry(chunk, i)
                        tasks.append(task)

                    # Process batch concurrently
                    batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                    # Store results
                    for i, result in enumerate(batch_results, start=batch_start):
                        if isinstance(result, Exception):
                            self.logger.warning(f"Failed to generate embeddings for chunk {i}: {result}")
                        elif result and (result.get("text") or result.get("code")):
                            chunk_embeddings[i] = result
                        else:
                            self.logger.warning(f"Empty embeddings for chunk {i}")

                    self.logger.debug(
                        f"Processed batch {batch_start}-{batch_end}: "
                        f"{len([r for r in batch_results if not isinstance(r, Exception)])} successful"
                    )

            # Step 5: Store chunks in database
            chunks_created = 0
            chunks_skipped = 0

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
                    # Store without embeddings for later retry
                    # This allows the chunk to be searchable by metadata at least

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

                try:
                    await self.chunk_repository.add(chunk_create)
                    chunks_created += 1
                except Exception as e:
                    self.logger.error(f"Failed to store chunk {i}: {e}")
                    chunks_skipped += 1

            # Calculate processing time
            end_time = datetime.now()
            processing_time_ms = (end_time - start_time).total_seconds() * 1000

            self.logger.debug(
                f"Indexed {file_input.path}: {chunks_created} chunks in {processing_time_ms:.0f}ms"
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
        Generate dual embeddings for a code chunk.

        Strategy:
        - TEXT embedding: docstring + comments (if present)
        - CODE embedding: source code

        Args:
            chunk: Code chunk to generate embeddings for

        Returns:
            {'text': [...], 'code': [...]} or {'text': None, 'code': None}
        """
        try:
            # For TEXT embedding, use docstring if available, else source code
            text_content = (
                chunk.metadata.get("docstring")
                if chunk.metadata
                else None
            )
            if not text_content:
                text_content = chunk.source_code

            # Generate both embeddings using HYBRID domain
            embeddings = await self.embedding_service.generate_embedding(
                text=chunk.source_code, domain="HYBRID"
            )

            return {
                "text": embeddings.get("text"),
                "code": embeddings.get("code"),
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
