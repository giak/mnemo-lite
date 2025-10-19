"""
Background upload handler for EPIC-09.

Separate module to handle long-running upload processing with progress tracking.
"""

import asyncio
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Dict, Any

# Import all services at module level (not inside function)
from services.code_chunking_service import CodeChunkingService
from services.metadata_extractor_service import MetadataExtractorService
from services.dual_embedding_service import DualEmbeddingService
from services.graph_construction_service import GraphConstructionService
from db.repositories.code_chunk_repository import CodeChunkRepository
from services.code_indexing_service import (
    CodeIndexingService,
    FileInput,
    IndexingOptions,
)

logger = logging.getLogger(__name__)

# Configuration
BATCH_SIZE = int(os.getenv("UPLOAD_BATCH_SIZE", "10"))
INDEXING_TIMEOUT = int(os.getenv("UPLOAD_INDEXING_TIMEOUT", "300"))  # 5 minutes per batch


def is_likely_binary(content: str, sample_size: int = 8192) -> bool:
    """
    Detect if content is likely binary (not text).

    Heuristic: Check first N bytes for null bytes and high ratio of non-printable chars.

    Args:
        content: File content string
        sample_size: Number of characters to check (default 8KB)

    Returns:
        True if content appears to be binary, False otherwise
    """
    if not content:
        return False

    # Sample first N characters
    sample = content[:sample_size]

    # Check for null bytes (strong indicator of binary)
    if '\x00' in sample:
        return True

    # Count non-printable characters (excluding common whitespace)
    non_printable = 0
    printable_whitespace = set('\t\n\r ')

    for char in sample:
        code = ord(char)
        # Printable ASCII: 32-126, or common whitespace
        if char not in printable_whitespace and (code < 32 or code > 126):
            non_printable += 1

    # If >30% non-printable characters, likely binary
    if len(sample) > 0 and (non_printable / len(sample)) > 0.3:
        return True

    return False


def validate_safe_path(file_path: str) -> bool:
    """
    Validate that a file path is safe and doesn't contain path traversal attacks.

    Blocks:
    - Absolute paths (/, C:\, etc.)
    - Parent directory references (..)
    - Null bytes
    - Hidden system paths

    Args:
        file_path: The file path to validate

    Returns:
        True if path is safe, False otherwise
    """
    if not file_path or not isinstance(file_path, str):
        return False

    # Block null bytes
    if '\x00' in file_path:
        logger.warning(f"Path contains null byte: {repr(file_path)}")
        return False

    # Normalize path (resolves . and ..)
    try:
        normalized = os.path.normpath(file_path)
    except (ValueError, TypeError):
        logger.warning(f"Path normalization failed: {file_path}")
        return False

    # Block absolute paths
    if os.path.isabs(normalized):
        logger.warning(f"Absolute path blocked: {normalized}")
        return False

    # Block parent directory references
    path_parts = Path(normalized).parts
    if '..' in path_parts:
        logger.warning(f"Parent directory traversal blocked: {normalized}")
        return False

    # Block paths starting with /
    if normalized.startswith('/') or normalized.startswith('\\'):
        logger.warning(f"Path starts with separator: {normalized}")
        return False

    # Block hidden files/directories (starting with .)
    # Allow .gitignore, .env, etc. but log them
    if any(part.startswith('.') for part in path_parts):
        logger.debug(f"Path contains hidden component: {normalized}")
        # Don't block, just log - some projects have .github, .vscode, etc.

    return True


def normalize_path(file_path: str) -> str:
    """
    Normalize a file path for consistent storage.

    - Converts backslashes to forward slashes (Windows → Unix)
    - Removes redundant slashes
    - Normalizes Unicode (NFC form)
    - Trims whitespace

    Args:
        file_path: Raw file path

    Returns:
        Normalized path string
    """
    if not file_path:
        return ""

    # Trim whitespace
    normalized = file_path.strip()

    # Convert backslashes to forward slashes
    normalized = normalized.replace('\\', '/')

    # Remove redundant slashes
    parts = [p for p in normalized.split('/') if p and p != '.']
    normalized = '/'.join(parts)

    # Normalize Unicode (NFC - Canonical Composition)
    import unicodedata
    normalized = unicodedata.normalize('NFC', normalized)

    return normalized


async def safe_process_upload_with_tracking(
    payload: Dict[str, Any],
    engine,
    upload_id: str,
    progress,
    embedding_service=None
):
    """
    Safe wrapper for process_upload_with_tracking that catches ALL exceptions.

    This wrapper ensures that:
    1. Exceptions are never silent (always logged)
    2. Progress tracker is always updated with error status
    3. Task failures are visible to users

    Args:
        payload: Upload request payload with files and options
        engine: Database engine
        upload_id: Unique upload session ID
        progress: UploadProgress tracker instance
        embedding_service: Pre-loaded embedding service from app.state (optional)
    """
    try:
        await process_upload_with_tracking(
            payload=payload,
            engine=engine,
            upload_id=upload_id,
            progress=progress,
            embedding_service=embedding_service
        )
    except Exception as e:
        # This catches exceptions that escaped the inner try/except
        # (should never happen, but defense in depth)
        logger.critical(
            f"[{upload_id}] CRITICAL: Exception escaped process_upload_with_tracking: {e}",
            exc_info=True
        )
        try:
            progress.add_error("system", f"Critical system error: {str(e)}")
            progress.complete("error")
        except Exception as inner_e:
            # Even updating progress failed - log and give up
            logger.critical(
                f"[{upload_id}] CRITICAL: Failed to update progress tracker: {inner_e}",
                exc_info=True
            )


async def process_upload_with_tracking(
    payload: Dict[str, Any],
    engine,
    upload_id: str,
    progress,
    embedding_service=None
):
    """
    Process uploaded files in background with real-time progress tracking.

    This function runs as a background task and updates the progress tracker
    throughout execution, allowing the frontend to poll for status updates.

    Args:
        payload: Upload request payload with files and options
        engine: Database engine
        upload_id: Unique upload session ID
        progress: UploadProgress tracker instance
        embedding_service: Pre-loaded embedding service from app.state (optional)
    """
    try:
        # Track overall timing
        start_time = time.time()

        # Initialize counters
        total_files = len(payload["files"])
        indexed_files = 0
        indexed_chunks = 0
        indexed_nodes = 0
        indexed_edges = 0
        failed_files = 0

        logger.info(f"[{upload_id}] Starting batch processing of {total_files} files")

        # Update progress: initializing services
        progress.update_step("initializing_services")

        # Validate upload options (PHASE 2 - Security)
        extract_metadata = payload.get("extract_metadata", True)
        generate_embeddings = payload.get("generate_embeddings", True)
        build_graph = payload.get("build_graph", True)

        # Ensure booleans (prevent type confusion attacks)
        if not isinstance(extract_metadata, bool):
            logger.warning(f"[{upload_id}] Invalid extract_metadata type: {type(extract_metadata)}, defaulting to True")
            extract_metadata = True

        if not isinstance(generate_embeddings, bool):
            logger.warning(f"[{upload_id}] Invalid generate_embeddings type: {type(generate_embeddings)}, defaulting to True")
            generate_embeddings = True

        if not isinstance(build_graph, bool):
            logger.warning(f"[{upload_id}] Invalid build_graph type: {type(build_graph)}, defaulting to True")
            build_graph = True

        # Create services once (reuse across batches)
        # NOTE: All imports are now at module level (PHASE 2 improvement)
        chunking_service = CodeChunkingService()
        metadata_service = MetadataExtractorService()

        # Use pre-loaded embedding service from app.state if available, otherwise create new
        if embedding_service is None:
            logger.warning("No pre-loaded embedding service provided, creating new instance")
            dual_embedding_service = DualEmbeddingService()
        else:
            logger.info("Using pre-loaded embedding service from app.state")

            # FIXED: Check isinstance() BEFORE hasattr() to avoid incorrect unwrapping
            # The order matters because hasattr() is too broad and may match inherited attributes
            if isinstance(embedding_service, DualEmbeddingService):
                logger.info("Using DualEmbeddingService directly")
                dual_embedding_service = embedding_service
            elif hasattr(embedding_service, '_dual_service'):
                logger.info("Unwrapping adapter to get raw DualEmbeddingService")
                dual_embedding_service = embedding_service._dual_service
            else:
                # Fallback: create new instance if type is unknown
                logger.warning(f"Unknown embedding service type: {type(embedding_service)}, creating new instance")
                dual_embedding_service = DualEmbeddingService()

        graph_service = GraphConstructionService(engine)
        chunk_repository = CodeChunkRepository(engine)

        indexing_service = CodeIndexingService(
            engine=engine,
            chunking_service=chunking_service,
            metadata_service=metadata_service,
            embedding_service=dual_embedding_service,
            graph_service=graph_service,
            chunk_repository=chunk_repository,
        )

        options = IndexingOptions(
            extract_metadata=extract_metadata,
            generate_embeddings=generate_embeddings,
            build_graph=build_graph,
            repository=payload["repository"],
            commit_hash=payload.get("commit_hash"),
        )

        # Update progress: services ready
        progress.update_step("processing_files")

        # Process files in batches
        for i in range(0, total_files, BATCH_SIZE):
            batch_end = min(i + BATCH_SIZE, total_files)
            batch_files = payload["files"][i:batch_end]

            batch_num = i // BATCH_SIZE + 1
            logger.info(f"[{upload_id}] Processing batch {batch_num}: files {i+1}-{batch_end} of {total_files}")

            # Update progress: current batch
            progress.update_step(f"processing_batch_{batch_num}")

            # Convert batch to service models
            files = []
            for file_idx, f in enumerate(batch_files):
                global_idx = i + file_idx

                # Update current file in progress
                progress.update_file(global_idx, f.get("path", "unknown"))

                try:
                    # Validate file data
                    if not f.get("path") or not f.get("content"):
                        error_msg = "Missing path or content"
                        progress.add_error(f.get("path", "unknown"), error_msg)
                        failed_files += 1
                        continue

                    # SECURITY: Validate path to prevent path traversal attacks
                    if not validate_safe_path(f["path"]):
                        error_msg = f"Invalid or unsafe path (path traversal blocked): {f['path']}"
                        progress.add_error(f["path"], error_msg)
                        logger.warning(f"[{upload_id}] {error_msg}")
                        failed_files += 1
                        continue

                    # PHASE 2: Normalize path for consistency
                    normalized_path = normalize_path(f["path"])
                    if not normalized_path:
                        error_msg = "Path normalization resulted in empty path"
                        progress.add_error(f["path"], error_msg)
                        failed_files += 1
                        continue

                    # PHASE 1: Skip lock files and package artifacts
                    SKIP_PATTERNS = {
                        '.lock', 'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock',
                        'composer.lock', 'gemfile.lock', 'cargo.lock', 'poetry.lock',
                        'pipfile.lock', 'go.sum', 'mix.lock', 'pubspec.lock'
                    }
                    filename_lower = normalized_path.lower()
                    if any(pattern in filename_lower for pattern in SKIP_PATTERNS):
                        error_msg = "Skipped: lock file or package artifact"
                        progress.add_error(normalized_path, error_msg)
                        logger.info(f"[{upload_id}] Skipping lock file: {normalized_path}")
                        failed_files += 1
                        continue

                    # PHASE 2: Detect binary files (likely to crash parser)
                    if is_likely_binary(f["content"]):
                        error_msg = "Binary file detected (not supported for code analysis)"
                        progress.add_error(normalized_path, error_msg)
                        logger.info(f"[{upload_id}] Skipping binary file: {normalized_path}")
                        failed_files += 1
                        continue

                    # PHASE 1: Skip files that are too large (>500KB per file)
                    MAX_FILE_SIZE = 500 * 1024  # 500KB (was 10MB - 20x reduction)
                    if len(f["content"]) > MAX_FILE_SIZE:
                        error_msg = f"File too large (>{MAX_FILE_SIZE // 1024}KB)"
                        progress.add_error(normalized_path, error_msg)
                        logger.info(f"[{upload_id}] Skipping large file: {normalized_path} ({len(f['content']) // 1024}KB)")
                        failed_files += 1
                        continue

                    files.append(FileInput(
                        path=normalized_path,  # Use normalized path
                        content=f["content"],
                        language=f.get("language"),
                    ))
                except Exception as e:
                    error_msg = f"Failed to process file: {str(e)}"
                    progress.add_error(f.get("path", "unknown"), error_msg)
                    failed_files += 1

            if files:
                try:
                    # Track batch processing time
                    batch_start = time.time()

                    # Update progress: indexing batch
                    progress.update_step("indexing_batch")

                    logger.info(
                        f"[{upload_id}] Batch {batch_num}: Starting indexing of {len(files)} files..."
                    )

                    # Index batch with timeout protection
                    try:
                        batch_summary = await asyncio.wait_for(
                            indexing_service.index_repository(files, options),
                            timeout=INDEXING_TIMEOUT
                        )
                    except asyncio.TimeoutError:
                        logger.error(
                            f"[{upload_id}] Batch {batch_num} TIMEOUT after {INDEXING_TIMEOUT}s - "
                            f"{len(files)} files may be corrupted or very large"
                        )
                        for f in files:
                            progress.add_error(f.path, f"Indexing timeout ({INDEXING_TIMEOUT}s)")
                        failed_files += len(files)
                        continue  # Skip to next batch

                    batch_time_ms = (time.time() - batch_start) * 1000
                    logger.info(
                        f"[{upload_id}] Batch {batch_num}: Completed in {batch_time_ms:.0f}ms - "
                        f"{batch_summary.indexed_files} files, {batch_summary.indexed_chunks} chunks"
                    )

                    # Update counters
                    indexed_files += batch_summary.indexed_files
                    indexed_chunks += batch_summary.indexed_chunks
                    indexed_nodes += batch_summary.indexed_nodes
                    indexed_edges += batch_summary.indexed_edges
                    failed_files += batch_summary.failed_files

                    # Add to recent files
                    for file_input in files[:5]:  # Last 5 files from batch
                        progress.add_recent_file(
                            file_path=file_input.path,
                            chunks=batch_summary.indexed_chunks // max(len(files), 1),
                            time_ms=batch_time_ms / max(len(files), 1),
                            status="success"
                        )

                    # Collect errors from batch
                    if batch_summary.errors:
                        for error in batch_summary.errors:
                            progress.add_error(
                                error.get("file", "unknown"),
                                error.get("error", "Unknown error")
                            )

                    logger.info(
                        f"[{upload_id}] Batch {batch_num} complete: "
                        f"{batch_summary.indexed_files} files, "
                        f"{batch_summary.indexed_chunks} chunks, "
                        f"{batch_summary.failed_files} failures in {batch_time_ms:.0f}ms"
                    )

                except Exception as e:
                    logger.error(f"[{upload_id}] Batch {batch_num} failed: {e}", exc_info=True)
                    # Mark all files in batch as failed
                    for f in files:
                        error_msg = f"Batch processing error: {str(e)}"
                        progress.add_error(f.path, error_msg)
                    failed_files += len(files)

            # BUGFIX: Update progress counters even if batch had no valid files
            # This fixes the 0% stuck issue when all files fail validation
            progress.indexed_files = indexed_files
            progress.indexed_chunks = indexed_chunks
            progress.indexed_nodes = indexed_nodes
            progress.indexed_edges = indexed_edges
            progress.failed_files = failed_files

            # Update pipeline stats (approximate based on batch completion)
            progress.pipeline.parsed = indexed_files + failed_files
            progress.pipeline.chunked = indexed_files + failed_files
            progress.pipeline.metadata_extracted = indexed_files
            progress.pipeline.text_embedded = indexed_files if options.generate_embeddings else 0
            progress.pipeline.code_embedded = indexed_files if options.generate_embeddings else 0
            progress.pipeline.stored = indexed_files
            progress.pipeline.graphed = indexed_nodes

            logger.info(
                f"[{upload_id}] 📊 PROGRESS UPDATE Batch {batch_num}: "
                f"indexed={indexed_files}, failed={failed_files}, chunks={indexed_chunks}, "
                f"processed={(indexed_files + failed_files)}/{total_files}"
            )

        # Calculate total processing time
        processing_time_ms = (time.time() - start_time) * 1000

        # Mark upload as complete
        progress.complete("completed" if failed_files == 0 else "partial")

        # Log summary
        logger.info(
            f"[{upload_id}] Batch processing complete for '{payload['repository']}': "
            f"{indexed_files}/{total_files} files indexed, "
            f"{indexed_chunks} chunks created, "
            f"{indexed_nodes} nodes, {indexed_edges} edges, "
            f"{failed_files} failures in {processing_time_ms:.0f}ms"
        )

    except Exception as e:
        logger.error(f"[{upload_id}] Upload processing failed: {e}", exc_info=True)
        progress.add_error("system", f"System error: {str(e)}")
        progress.complete("error")
