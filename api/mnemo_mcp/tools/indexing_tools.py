"""
MCP Indexing Tools (EPIC-23 Story 23.5).

Tools for project indexing, incremental re-indexing, file re-indexing, and status tracking.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
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
        start_time = datetime.now(timezone.utc)

        # Check services availability
        if not self._services.get("code_indexing_service"):
            return {"success": False, "message": "CodeIndexingService not available"}

        indexing_service = self._services["code_indexing_service"]
        redis = self._services.get("redis")  # May be None (graceful degradation)

        try:
            # P0-6 FIX: Validate project path (prevent path traversal)
            import os
            project_path = os.path.realpath(project_path)
            if not project_path.startswith("/"):
                return {"success": False, "message": "Invalid project path", "error": "SecurityError"}

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

            # Step 2: Log if many files (elicitation skipped — FastMCP API changed)
            if len(files) > 100:
                logger.warning(f"Indexing {len(files)} files — large project, proceeding without confirmation")

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
                                "completed_at": datetime.now(timezone.utc).isoformat(),
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
                            "completed_at": datetime.now(timezone.utc).isoformat(),
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
        if not self._services.get("code_indexing_service"):
            return {"success": False, "message": "CodeIndexingService not available"}

        indexing_service = self._services["code_indexing_service"]
        chunk_cache = self._services.get("chunk_cache")  # CascadeCache L1/L2

        try:
            # P0-5 FIX: Validate file path (prevent path traversal)
            import os
            file_path = os.path.realpath(file_path)
            if not file_path.startswith("/"):
                return {"success": False, "message": "Invalid file path", "error": "SecurityError"}

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

            # P2-4 FIX: Invalidate search code cache (Redis keys search:v1:*)
            redis = self._services.get("redis")
            if redis:
                try:
                    cursor = 0
                    deleted = 0
                    while True:
                        cursor, keys = await redis.scan(cursor, match="search:v1:*", count=100)
                        if keys:
                            await redis.delete(*keys)
                            deleted += len(keys)
                        if cursor == 0:
                            break
                    if deleted:
                        logger.info(f"Invalidated {deleted} search cache keys after reindex")
                except Exception as e:
                    logger.warning(f"Failed to invalidate search cache: {e}")

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


class IndexIncrementalTool(BaseMCPComponent):
    """
    Tool: index_incremental — Re-index only changed files.

    Compares file modification times against last indexed timestamps
    to identify files that need re-indexing. Much faster than full
    index_project for large repositories.

    Performance comparison (782 files, Expanse):
        index_project:    ~6.5 hours (re-index everything)
        index_incremental: ~50 seconds (only changed files)

    Algorithm:
    1. Scan project directory for supported files
    2. Query DB for MAX(indexed_at) per file_path
    3. Compare file mtime vs last indexed_at
    4. Re-index only files where mtime > indexed_at or no chunks exist
    """

    def get_name(self) -> str:
        return "index_incremental"

    def get_description(self) -> str:
        return (
            "Re-index only files modified since last indexing. "
            "Much faster than index_project for large repositories. "
            "Compares file modification times against database timestamps."
        )

    async def execute(self, ctx: Context, **params) -> dict:
        """
        Incrementally re-index a project directory.

        Args:
            project_path: Path to project root directory
            repository: Repository name for scoping (default: "default")
            include_gitignored: Include files ignored by .gitignore (default: False)

        Returns:
            Dict with: scanned, changed, indexed, skipped, errors, time_ms
        """
        project_path = params.get("project_path", ".")
        repository = params.get("repository", "default")
        include_gitignored = params.get("include_gitignored", False)

        start_time = datetime.now()

        try:
            services = self._services
            engine = services.get("engine")
            # P0-4 FIX: correct service key is "code_indexing_service" (server.py:226)
            indexing_service = services.get("code_indexing_service")

            if not engine:
                raise RuntimeError("Database engine not available")
            if not indexing_service:
                raise RuntimeError("CodeIndexingService not available")

            # 1. Scan project directory
            scanner = ProjectScanner()
            all_files = await scanner.scan(
                project_path=project_path,
                respect_gitignore=not include_gitignored
            )
            scanned_count = len(all_files)

            if scanned_count == 0:
                return {
                    "success": True,
                    "scanned": 0,
                    "changed": 0,
                    "indexed": 0,
                    "skipped": 0,
                    "message": "No supported files found in project",
                }

            # 2. Query DB for last indexed time per file
            from sqlalchemy import text
            async with engine.connect() as conn:
                result = await conn.execute(
                    text("""
                        SELECT file_path, MAX(indexed_at) as last_indexed
                        FROM code_chunks
                        WHERE repository = :repo
                        GROUP BY file_path
                    """),
                    {"repo": repository}
                )
                rows = result.fetchall()

            # Build lookup: file_path → last_indexed datetime
            indexed_files = {}
            for row in rows:
                fpath = row[0]
                last_indexed = row[1]
                if last_indexed:
                    indexed_files[fpath] = last_indexed

            # 3. Filter to changed files
            changed_files = []
            skipped_count = 0

            for file_input in all_files:
                fpath = file_input.path
                last_indexed = indexed_files.get(fpath)

                if last_indexed is None:
                    # Never indexed → must index
                    changed_files.append(file_input)
                    continue

                # Compare file mtime with last indexed time
                try:
                    mtime = os.path.getmtime(fpath)
                    mtime_dt = datetime.fromtimestamp(mtime)

                    # Make both timezone-naive for comparison
                    if hasattr(last_indexed, 'tzinfo') and last_indexed.tzinfo:
                        last_indexed = last_indexed.replace(tzinfo=None)

                    if mtime_dt > last_indexed:
                        changed_files.append(file_input)
                    else:
                        skipped_count += 1
                except OSError:
                    # File deleted or inaccessible → must re-index to clean up
                    changed_files.append(file_input)

            changed_count = len(changed_files)

            if changed_count == 0:
                elapsed = (datetime.now() - start_time).total_seconds() * 1000
                return {
                    "success": True,
                    "scanned": scanned_count,
                    "changed": 0,
                    "indexed": 0,
                    "skipped": skipped_count,
                    "time_ms": elapsed,
                    "message": f"All {scanned_count} files up to date ({elapsed:.0f}ms scan)",
                }

            # 4. Index only changed files
            from services.code_indexing_service import IndexingOptions as ServiceIndexingOptions

            # Notify start
            if ctx:
                try:
                    await ctx.report_progress(0, changed_count, f"Re-indexing {changed_count} changed files...")
                except Exception:
                    pass

            indexing_result = await indexing_service.index_repository(
                files=changed_files,
                options=ServiceIndexingOptions(
                    extract_metadata=True,
                    generate_embeddings=True,
                    build_graph=True,
                    repository=repository,
                    repository_root=project_path,
                ),
            )

            elapsed = (datetime.now() - start_time).total_seconds() * 1000

            # Build graph if needed
            if indexing_result.indexed_files > 0:
                try:
                    graph_service = services.get("graph_service")
                    if graph_service:
                        await graph_service.build_graph_for_repository(repository=repository)
                except Exception as e:
                    logger.warning(f"Graph build after incremental failed: {e}")

                # P2-4: Invalidate search cache after reindex
                redis = services.get("redis")
                if redis:
                    try:
                        cursor = 0
                        deleted = 0
                        while True:
                            cursor, keys = await redis.scan(cursor, match="search:v1:*", count=100)
                            if keys:
                                await redis.delete(*keys)
                                deleted += len(keys)
                            if cursor == 0:
                                break
                        if deleted:
                            logger.info(f"Invalidated {deleted} search cache keys after incremental reindex")
                    except Exception:
                        pass

            result = {
                "success": True,
                "scanned": scanned_count,
                "changed": changed_count,
                "indexed": indexing_result.indexed_files,
                "failed": indexing_result.failed_files,
                "chunks_created": indexing_result.indexed_chunks,
                "skipped": skipped_count,
                "time_ms": elapsed,
                "errors": indexing_result.errors,
                "message": (
                    f"Incremental index: {indexing_result.indexed_files}/{changed_count} files "
                    f"({skipped_count} skipped, {scanned_count} scanned) in {elapsed:.0f}ms"
                ),
            }

            logger.info(
                "Incremental indexing completed",
                **{k: v for k, v in result.items() if k != "errors"}
            )

            return result

        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Incremental indexing failed: {e}", exc_info=True)
            return {
                "success": False,
                "scanned": 0,
                "changed": 0,
                "indexed": 0,
                "skipped": 0,
                "time_ms": elapsed,
                "error": str(e),
                "message": f"Incremental indexing failed: {e}",
            }


class IndexMarkdownWorkspaceTool(BaseMCPComponent):
    """
    Tool: index_markdown_workspace — Index markdown files for agent memory.

    Specialized for Expanse: skip tree-sitter, LSP, metadata, graph.
    Just: scan .md → split by ## → embed TEXT → store halfvec.

    Performance: 10x faster than index_project for markdown-only repos.
    """

    def get_name(self) -> str:
        return "index_markdown_workspace"

    async def execute(self, ctx: Context, **params) -> dict:
        """
        Index markdown workspace.

        Args:
            root_path: Path to project root
            repository: Repository name (default: "expanse")
            max_file_size_kb: Skip files larger than this (default: 50)
            skip_patterns: Additional directories to skip
        """
        root_path = params.get("root_path", ".")
        repository = params.get("repository", "expanse")
        max_file_size_kb = params.get("max_file_size_kb", 50)
        skip_patterns = params.get("skip_patterns", [])

        start_time = datetime.now()

        try:
            services = self._services
            engine = services.get("engine")
            embedding_service = services.get("embedding_service")

            if not engine:
                raise RuntimeError("Database engine not available")

            # 1. Scan for .md files only
            from mnemo_mcp.utils.project_scanner import ProjectScanner
            scanner = ProjectScanner()
            all_files = await scanner.scan(
                project_path=root_path,
                respect_gitignore=True
            )

            # Filter to .md only and skip large files
            md_files = []
            skipped_large = 0
            for f in all_files:
                if not f.path.endswith('.md'):
                    continue
                try:
                    size_kb = os.path.getsize(f.path) / 1024
                    if size_kb > max_file_size_kb:
                        skipped_large += 1
                        continue
                except OSError:
                    continue
                md_files.append(f)

            if not md_files:
                return {"success": True, "scanned": 0, "indexed": 0, "message": "No .md files found"}

            # 2. Chunk all files using MarkdownChunker
            from services.code_chunking_service import CodeChunkingService
            chunker = CodeChunkingService(max_workers=1)

            all_chunks = []
            for file_input in md_files:
                try:
                    chunks = await chunker._chunk_markdown(
                        source_code=file_input.content,
                        file_path=file_input.path,
                    )
                    for chunk in chunks:
                        chunk.repository = repository
                    all_chunks.extend(chunks)
                except Exception as e:
                    logger.warning(f"Failed to chunk {file_input.path}: {e}")

            if not all_chunks:
                return {"success": True, "scanned": len(md_files), "indexed": 0, "message": "No chunks generated"}

            # 3. Generate TEXT embeddings only (skip CODE)
            if embedding_service:
                try:
                    texts = [f"{c.name}\n{c.source_code[:500]}" for c in all_chunks]
                    # P0-1 FIX: correct method name is generate_embeddings_batch
                    embeddings = await embedding_service.generate_embeddings_batch(texts)
                    for chunk, emb in zip(all_chunks, embeddings):
                        if isinstance(emb, dict):
                            chunk.embedding_text = emb.get("text")
                        elif isinstance(emb, list):
                            chunk.embedding_text = emb
                except Exception as e:
                    logger.warning(f"Embedding generation failed: {e}")

            # 4. Store in DB
            from db.repositories.code_chunk_repository import CodeChunkRepository
            chunk_repo = CodeChunkRepository(engine=engine)

            async with engine.begin() as conn:
                # Delete existing chunks for this repository
                await conn.execute(
                    text("DELETE FROM code_chunks WHERE repository = :repo"),
                    {"repo": repository}
                )

                # Insert new chunks
                inserted = await chunk_repo.add_batch(
                    chunks_data=[c.to_db_dict() for c in all_chunks],
                    connection=conn,
                )

            elapsed = (datetime.now() - start_time).total_seconds() * 1000

            return {
                "success": True,
                "scanned": len(md_files),
                "indexed": len(md_files),
                "chunks_created": inserted,
                "skipped_large": skipped_large,
                "time_ms": elapsed,
                "message": f"Indexed {len(md_files)} .md files → {inserted} chunks in {elapsed:.0f}ms",
            }

        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            return {
                "success": False,
                "scanned": 0,
                "indexed": 0,
                "time_ms": elapsed,
                "error": str(e),
                "message": f"Markdown indexing failed: {e}",
            }


# Singleton instances for registration
index_project_tool = IndexProjectTool()
reindex_file_tool = ReindexFileTool()
index_incremental_tool = IndexIncrementalTool()
index_markdown_workspace_tool = IndexMarkdownWorkspaceTool()
