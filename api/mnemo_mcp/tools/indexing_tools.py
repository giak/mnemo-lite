"""
MCP Indexing Tools (EPIC-23 Story 23.5).

Tools for project indexing, file re-indexing, and status tracking.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import Context

from mnemo_mcp.base import BaseMCPComponent
from mnemo_mcp.models.indexing_models import (
    FileIndexResult,
    IndexResult,
    IndexingOptions,
)
from mnemo_mcp.utils.project_scanner import ProjectScanner
from services.code_indexing_service import FileInput, IndexingOptions as ServiceIndexingOptions

logger = logging.getLogger(__name__)


class IndexProjectTool(BaseMCPComponent):
    """
    Tool: index_project - Index entire project directory.

    Features:
    - Scans project directory for code files
    - Respects .gitignore by default
    - Real-time progress reporting via MCP Context
    - Distributed lock (Redis) to prevent concurrent indexing
    - Elicitation for confirmation if >100 files
    - Graceful degradation if Redis unavailable
    """

    def get_name(self) -> str:
        return "index_project"

    def get_description(self) -> str:
        return (
            "Index an entire project directory. Scans for code files, "
            "generates embeddings, builds dependency graph. "
            "Use for initial indexing or complete re-indexing."
        )

    async def execute(
        self,
        project_path: str,
        repository: str = "default",
        include_gitignored: bool = False,
        ctx: Optional[Context] = None,
    ) -> dict:
        """
        Index project with progress reporting and concurrency control.

        Args:
            project_path: Path to project root directory
            repository: Repository name for organization
            include_gitignored: If True, index files even if gitignored
            ctx: MCP Context for progress reporting and elicitation

        Returns:
            IndexResult with statistics
        """
        start_time = datetime.utcnow()

        # Check services availability
        if not self.services.get("code_indexing_service"):
            return {"success": False, "message": "CodeIndexingService not available"}

        indexing_service = self.services["code_indexing_service"]
        redis = self.services.get("redis")  # May be None (graceful degradation)

        try:
            # Step 1: Scan project directory
            logger.info(f"Scanning project: {project_path}")

            scanner = ProjectScanner()
            try:
                files = await scanner.scan(
                    project_path=project_path,
                    respect_gitignore=not include_gitignored
                )
            except FileNotFoundError as e:
                return {
                    "success": False,
                    "message": f"Project path not found: {project_path}",
                    "error": str(e)
                }
            except ValueError as e:
                return {
                    "success": False,
                    "message": str(e),
                    "error": "Project validation failed"
                }

            logger.info(f"Found {len(files)} code files in {project_path}")

            # Step 2: Elicit confirmation if many files
            if len(files) > 100 and ctx:
                response = await ctx.elicit(
                    prompt=(
                        f"Index {len(files)} files in repository '{repository}'? "
                        f"This may take several minutes and will generate embeddings for all code chunks."
                    ),
                    schema={"type": "string", "enum": ["yes", "no"]}
                )

                if response.value == "no":
                    return {
                        "success": False,
                        "message": "Indexing cancelled by user"
                    }

            # Step 3: Acquire distributed lock (prevent concurrent indexing)
            lock_key = f"indexing:lock:{repository}"
            lock_acquired = False

            if redis:
                try:
                    # Try to acquire lock (10-minute TTL for large projects)
                    lock_acquired = await redis.set(
                        lock_key,
                        "1",
                        nx=True,  # Only set if doesn't exist
                        ex=600    # Expire after 10 minutes
                    )

                    if not lock_acquired:
                        return {
                            "success": False,
                            "message": (
                                f"Indexing already in progress for repository '{repository}'. "
                                "Please wait for the current operation to complete."
                            )
                        }

                    logger.info(f"Acquired distributed lock for {repository}")

                except Exception as redis_error:
                    # Redis unavailable - log warning but continue without lock
                    logger.warning(
                        f"Failed to acquire distributed lock (Redis error): {redis_error}. "
                        "Continuing without concurrency protection."
                    )

            try:
                # Step 4: Update status in Redis (if available)
                if redis:
                    try:
                        await redis.set(
                            f"indexing:status:{repository}",
                            json.dumps({
                                "status": "in_progress",
                                "total_files": len(files),
                                "indexed_files": 0,
                                "started_at": start_time.isoformat(),
                                "repository": repository
                            }),
                            ex=3600  # 1 hour TTL
                        )
                    except Exception as e:
                        logger.warning(f"Failed to update Redis status: {e}")

                # Step 5: Progress callback with throttling
                last_progress_time = 0.0
                progress_interval = 1.0  # Max 1 update per second

                async def progress_callback(current: int, total: int, message: str):
                    """Report progress to MCP client (throttled)."""
                    nonlocal last_progress_time

                    if not ctx:
                        return

                    # Throttle updates to max 1/second
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_progress_time < progress_interval:
                        # Skip this update (too soon)
                        return

                    last_progress_time = current_time

                    try:
                        progress_pct = (current / total) * 100
                        await ctx.report_progress(
                            progress=current / total,  # 0.0 to 1.0
                            message=f"{message} ({current}/{total}, {progress_pct:.1f}%)"
                        )

                        # Also update Redis status (if available)
                        if redis:
                            try:
                                await redis.set(
                                    f"indexing:status:{repository}",
                                    json.dumps({
                                        "status": "in_progress",
                                        "total_files": total,
                                        "indexed_files": current,
                                        "started_at": start_time.isoformat(),
                                        "repository": repository
                                    }),
                                    ex=3600
                                )
                            except Exception:
                                pass  # Ignore Redis errors during progress updates

                    except Exception as e:
                        # Progress reporting failure should not break indexing
                        logger.warning(f"Progress reporting failed: {e}")

                # Step 6: Index repository
                logger.info(f"Starting indexing of {len(files)} files for {repository}")

                result = await indexing_service.index_repository(
                    files=files,
                    options=ServiceIndexingOptions(
                        extract_metadata=True,
                        generate_embeddings=True,
                        build_graph=True,
                        repository=repository,
                        repository_root=project_path
                    ),
                    progress_callback=progress_callback
                )

                # Step 7: Update final status in Redis
                if redis:
                    try:
                        await redis.set(
                            f"indexing:status:{repository}",
                            json.dumps({
                                "status": "completed" if result.failed_files == 0 else "failed",
                                "total_files": len(files),
                                "indexed_files": result.indexed_files,
                                "started_at": start_time.isoformat(),
                                "completed_at": datetime.utcnow().isoformat(),
                                "repository": repository,
                                "errors": result.errors if result.errors else []
                            }),
                            ex=3600
                        )
                    except Exception as e:
                        logger.warning(f"Failed to update final Redis status: {e}")

                # Step 8: Return result
                return {
                    "success": True,
                    "repository": result.repository,
                    "indexed_files": result.indexed_files,
                    "indexed_chunks": result.indexed_chunks,
                    "indexed_nodes": result.indexed_nodes,
                    "indexed_edges": result.indexed_edges,
                    "failed_files": result.failed_files,
                    "processing_time_ms": result.processing_time_ms,
                    "errors": result.errors,
                    "message": (
                        f"Successfully indexed {result.indexed_files} files "
                        f"({result.indexed_chunks} chunks, {result.indexed_nodes} nodes, "
                        f"{result.indexed_edges} edges) in {result.processing_time_ms:.0f}ms"
                    )
                }

            finally:
                # Step 9: Release lock (always, even if indexing failed)
                if redis and lock_acquired:
                    try:
                        await redis.delete(lock_key)
                        logger.info(f"Released distributed lock for {repository}")
                    except Exception as e:
                        logger.error(f"Failed to release lock: {e}")

        except Exception as e:
            logger.error(f"Unexpected error during project indexing: {e}", exc_info=True)

            # Update Redis status to failed
            if redis:
                try:
                    await redis.set(
                        f"indexing:status:{repository}",
                        json.dumps({
                            "status": "failed",
                            "started_at": start_time.isoformat(),
                            "completed_at": datetime.utcnow().isoformat(),
                            "repository": repository,
                            "error": str(e)
                        }),
                        ex=3600
                    )
                except Exception:
                    pass

            return {
                "success": False,
                "message": f"Indexing failed: {str(e)}",
                "error": str(e)
            }


class ReindexFileTool(BaseMCPComponent):
    """
    Tool: reindex_file - Reindex a single file.

    Use after file modifications to update chunks, embeddings, and graph.
    """

    def get_name(self) -> str:
        return "reindex_file"

    def get_description(self) -> str:
        return (
            "Reindex a single file after modifications. "
            "Updates code chunks, embeddings, and dependency graph. "
            "Useful after editing code to refresh search index."
        )

    async def execute(
        self,
        file_path: str,
        repository: str = "default",
        ctx: Optional[Context] = None,
    ) -> dict:
        """
        Reindex single file.

        Args:
            file_path: Path to file to reindex
            repository: Repository name
            ctx: MCP Context (unused for single file)

        Returns:
            FileIndexResult with statistics
        """
        # Check services
        if not self.services.get("code_indexing_service"):
            return {"success": False, "message": "CodeIndexingService not available"}

        indexing_service = self.services["code_indexing_service"]
        chunk_cache = self.services.get("chunk_cache")  # CascadeCache L1/L2

        try:
            # Validate file exists
            file_path_obj = Path(file_path)

            if not file_path_obj.exists():
                return {
                    "success": False,
                    "message": f"File not found: {file_path}",
                    "error": "FileNotFoundError"
                }

            if not file_path_obj.is_file():
                return {
                    "success": False,
                    "message": f"Path is not a file: {file_path}",
                    "error": "ValueError"
                }

            # Read file content
            try:
                content = file_path_obj.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                return {
                    "success": False,
                    "message": f"File is not UTF-8 encoded: {file_path}",
                    "error": "UnicodeDecodeError"
                }

            # Invalidate cache for this file (force fresh indexing)
            if chunk_cache:
                try:
                    await chunk_cache.invalidate(file_path)
                    logger.info(f"Cache invalidated for {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to invalidate cache: {e}")

            # Reindex file
            logger.info(f"Reindexing file: {file_path}")

            file_input = FileInput(
                path=file_path,
                content=content,
                language=None  # Auto-detect
            )

            result = await indexing_service._index_file(
                file_input=file_input,
                options=ServiceIndexingOptions(
                    extract_metadata=True,
                    generate_embeddings=True,
                    build_graph=False,  # Don't rebuild entire graph for single file
                    repository=repository,
                    repository_root=str(file_path_obj.parent)
                )
            )

            return {
                "success": result.success,
                "file_path": result.file_path,
                "chunks_created": result.chunks_created,
                "processing_time_ms": result.processing_time_ms,
                "error": result.error,
                "message": (
                    f"Successfully reindexed {file_path} → {result.chunks_created} chunks "
                    f"in {result.processing_time_ms:.0f}ms"
                    if result.success
                    else f"Failed to reindex {file_path}: {result.error}"
                )
            }

        except Exception as e:
            logger.error(f"Unexpected error reindexing {file_path}: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Reindexing failed: {str(e)}",
                "error": str(e)
            }


# Singleton instances for registration
index_project_tool = IndexProjectTool()
reindex_file_tool = ReindexFileTool()
