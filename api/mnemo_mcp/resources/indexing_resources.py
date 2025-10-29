"""
MCP Indexing Resources (EPIC-23 Story 23.5).

Resources for querying indexing status and statistics.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncConnection

from mnemo_mcp.base import BaseMCPComponent
from mnemo_mcp.models.indexing_models import IndexStatus
from models.code_chunk_models import CodeChunk

logger = logging.getLogger(__name__)


class IndexStatusResource(BaseMCPComponent):
    """
    Resource: index://status - Get indexing status for repository.

    Returns current status (in_progress, completed, failed, not_indexed)
    with statistics (files, chunks, languages, last update).
    """

    def get_name(self) -> str:
        return "index://status"

    async def get(
        self,
        repository: str = "default"
    ) -> dict:
        """
        Get indexing status for repository.

        Args:
            repository: Repository name to query

        Returns:
            IndexStatus with current status and statistics
        """
        try:
            # Check services
            redis = self.services.get("redis")
            engine = self.services.get("sqlalchemy_engine")
            chunk_cache = self.services.get("chunk_cache")

            if not engine:
                return {
                    "success": False,
                    "message": "Database engine not available",
                    "status": "unknown"
                }

            # Step 1: Check Redis for in-progress/recent status
            current_status = "unknown"
            indexed_files_progress = 0
            total_files_progress = 0
            started_at = None
            completed_at = None
            error = None

            if redis:
                try:
                    status_key = f"indexing:status:{repository}"
                    status_data = await redis.get(status_key)

                    if status_data:
                        status_info = json.loads(status_data)
                        current_status = status_info.get("status", "unknown")
                        total_files_progress = status_info.get("total_files", 0)
                        indexed_files_progress = status_info.get("indexed_files", 0)

                        started_str = status_info.get("started_at")
                        if started_str:
                            started_at = datetime.fromisoformat(started_str)

                        completed_str = status_info.get("completed_at")
                        if completed_str:
                            completed_at = datetime.fromisoformat(completed_str)

                        error = status_info.get("error")

                        logger.debug(
                            f"Redis status for {repository}: {current_status} "
                            f"({indexed_files_progress}/{total_files_progress})"
                        )

                except Exception as e:
                    logger.warning(f"Failed to read Redis status: {e}")

            # Step 2: Query database for statistics
            total_chunks = 0
            total_files_db = 0
            languages = []
            last_indexed_at = None

            try:
                async with engine.connect() as conn:
                    # Count total chunks for this repository
                    chunk_count_query = text(
                        "SELECT COUNT(*) FROM code_chunks WHERE repository = :repository"
                    )
                    result = await conn.execute(chunk_count_query, {"repository": repository})
                    total_chunks = result.scalar() or 0

                    # Count distinct files
                    file_count_query = text(
                        "SELECT COUNT(DISTINCT file_path) FROM code_chunks WHERE repository = :repository"
                    )
                    result = await conn.execute(file_count_query, {"repository": repository})
                    total_files_db = result.scalar() or 0

                    # Get distinct languages
                    languages_query = text(
                        "SELECT DISTINCT language FROM code_chunks WHERE repository = :repository AND language IS NOT NULL"
                    )
                    result = await conn.execute(languages_query, {"repository": repository})
                    languages = [row[0] for row in result]

                    # Get last indexed timestamp
                    last_indexed_query = text(
                        "SELECT MAX(created_at) FROM code_chunks WHERE repository = :repository"
                    )
                    result = await conn.execute(last_indexed_query, {"repository": repository})
                    last_indexed_at = result.scalar()

            except Exception as e:
                logger.error(f"Failed to query database statistics: {e}", exc_info=True)

            # Step 3: Determine final status
            # Priority: Redis status (if recent) > DB data (if exists) > not_indexed
            if current_status in ("in_progress", "failed"):
                # Trust Redis for active/failed states
                pass
            elif current_status == "completed" and completed_at:
                # Redis says completed - verify with DB
                if total_chunks == 0:
                    # Redis stale data - no chunks in DB
                    current_status = "not_indexed"
            elif total_chunks > 0:
                # No Redis status but DB has data
                current_status = "completed"
            else:
                # No Redis status, no DB data
                current_status = "not_indexed"

            # Step 4: Get cache statistics (if available)
            cache_stats = {}
            if chunk_cache:
                try:
                    cache_stats = chunk_cache.get_stats()
                except Exception as e:
                    logger.warning(f"Failed to get cache stats: {e}")

            # Step 5: Return status
            return {
                "success": True,
                "repository": repository,
                "status": current_status,
                "total_files": total_files_db if current_status != "in_progress" else total_files_progress,
                "indexed_files": indexed_files_progress if current_status == "in_progress" else total_files_db,
                "total_chunks": total_chunks,
                "languages": languages,
                "last_indexed_at": last_indexed_at.isoformat() if last_indexed_at else None,
                "embedding_model": "nomic-embed-text-v1.5",
                "cache_stats": cache_stats,
                "started_at": started_at.isoformat() if started_at else None,
                "completed_at": completed_at.isoformat() if completed_at else None,
                "error": error,
                "message": self._get_status_message(
                    current_status,
                    total_files_db,
                    total_chunks,
                    indexed_files_progress,
                    total_files_progress
                )
            }

        except Exception as e:
            logger.error(f"Unexpected error getting index status: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to get index status: {str(e)}",
                "status": "unknown",
                "error": str(e)
            }

    def _get_status_message(
        self,
        status: str,
        total_files: int,
        total_chunks: int,
        indexed_files: int,
        total_files_progress: int
    ) -> str:
        """Generate human-readable status message."""
        if status == "not_indexed":
            return "Repository not indexed yet. Use index_project to start."
        elif status == "in_progress":
            progress_pct = (indexed_files / total_files_progress * 100) if total_files_progress > 0 else 0
            return (
                f"Indexing in progress: {indexed_files}/{total_files_progress} files "
                f"({progress_pct:.1f}%)"
            )
        elif status == "completed":
            return (
                f"Repository indexed: {total_files} files, {total_chunks} chunks"
            )
        elif status == "failed":
            return "Last indexing attempt failed. Check errors."
        else:
            return "Status unknown"


# Singleton instance for registration
index_status_resource = IndexStatusResource()
