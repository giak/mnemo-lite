"""
Upload Progress Tracker for EPIC-09.

Provides real-time progress tracking for file upload and processing operations.
Uses in-memory storage for fast access and auto-cleanup of old sessions.

PHASE 2 improvements:
- asyncio.Lock for thread-safe concurrent access
- Consistent error/file limits via constants
"""

import asyncio
import time
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

# Constants
MAX_ERRORS = 200  # Maximum number of errors to track per upload session
MAX_RECENT_FILES = 5  # Number of recent files to keep in activity log


@dataclass
class PipelineStats:
    """Statistics for each pipeline stage."""
    parsed: int = 0
    chunked: int = 0
    metadata_extracted: int = 0
    text_embedded: int = 0
    code_embedded: int = 0
    stored: int = 0
    graphed: int = 0


@dataclass
class UploadProgress:
    """Progress tracking for a single upload session."""
    upload_id: str
    repository: str
    total_files: int
    current_file_index: int = 0
    current_file: str = ""
    current_step: str = "initializing"

    # Pipeline statistics
    pipeline: PipelineStats = field(default_factory=PipelineStats)

    # Counters
    indexed_files: int = 0
    indexed_chunks: int = 0
    indexed_nodes: int = 0
    indexed_edges: int = 0
    failed_files: int = 0

    # Errors (limit to 200 - see MAX_ERRORS constant below)
    errors: List[Dict[str, str]] = field(default_factory=list)

    # Timing
    start_time: float = field(default_factory=time.time)
    last_update: float = field(default_factory=time.time)

    # Recent activity (last 5 files)
    recent_files: List[Dict[str, Any]] = field(default_factory=list)

    # Status
    status: str = "processing"  # processing, completed, error, cancelled

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        elapsed_ms = int((time.time() - self.start_time) * 1000)

        # DEBUG: Log what we're returning (use INFO to ensure visibility)
        logger.info(
            f"[{self.upload_id}] 🔍 to_dict() STATUS: "
            f"indexed={self.indexed_files}, failed={self.failed_files}, "
            f"chunks={self.indexed_chunks}, total={self.total_files}"
        )

        # Calculate estimated remaining time
        if self.current_file_index > 0 and self.current_file_index < self.total_files:
            avg_time_per_file = (time.time() - self.start_time) / self.current_file_index
            remaining_files = self.total_files - self.current_file_index
            estimated_remaining_ms = int(avg_time_per_file * remaining_files * 1000)
        else:
            estimated_remaining_ms = 0

        # Calculate percentage based on processed files (indexed + failed)
        processed_files = self.indexed_files + self.failed_files
        percentage = int((processed_files / self.total_files * 100)) if self.total_files > 0 else 0

        # Cap at 100% (defensive coding for edge cases)
        percentage = min(percentage, 100)

        # When completed, force 100%
        if self.status in ['completed', 'partial']:
            percentage = 100

        return {
            "upload_id": self.upload_id,
            "repository": self.repository,
            "status": self.status,
            "total_files": self.total_files,
            "current_file_index": self.current_file_index,
            "current_file": self.current_file,
            "current_step": self.current_step,
            "percentage": percentage,
            "pipeline": {
                "parsed": self.pipeline.parsed,
                "chunked": self.pipeline.chunked,
                "metadata_extracted": self.pipeline.metadata_extracted,
                "text_embedded": self.pipeline.text_embedded,
                "code_embedded": self.pipeline.code_embedded,
                "stored": self.pipeline.stored,
                "graphed": self.pipeline.graphed,
            },
            "counters": {
                "indexed_files": self.indexed_files,
                "indexed_chunks": self.indexed_chunks,
                "indexed_nodes": self.indexed_nodes,
                "indexed_edges": self.indexed_edges,
                "failed_files": self.failed_files,
            },
            "errors": self.errors[:MAX_ERRORS],  # Limit to MAX_ERRORS
            "error_overflow": len(self.errors) >= MAX_ERRORS,
            "recent_files": self.recent_files[-MAX_RECENT_FILES:],  # Last N files
            "timing": {
                "elapsed_ms": elapsed_ms,
                "estimated_remaining_ms": estimated_remaining_ms,
            },
            "last_update": datetime.fromtimestamp(self.last_update, tz=timezone.utc).isoformat(),
        }

    def update_step(self, step: str):
        """Update current processing step."""
        self.current_step = step
        self.last_update = time.time()

    def update_file(self, file_index: int, file_path: str):
        """Update current file being processed."""
        self.current_file_index = file_index
        self.current_file = file_path
        self.last_update = time.time()

    def add_recent_file(self, file_path: str, chunks: int, time_ms: float, status: str = "success"):
        """Add file to recent activity list."""
        self.recent_files.append({
            "file": file_path,
            "chunks": chunks,
            "time_ms": int(time_ms),
            "status": status,
        })
        # Keep only last MAX_RECENT_FILES
        if len(self.recent_files) > MAX_RECENT_FILES:
            self.recent_files.pop(0)
        self.last_update = time.time()

    def add_error(self, file_path: str, error: str):
        """Add error to error list (limited to MAX_ERRORS)."""
        if len(self.errors) < MAX_ERRORS:
            self.errors.append({
                "file": file_path,
                "error": error,
            })
        self.last_update = time.time()

    def complete(self, status: str = "completed"):
        """Mark upload as complete."""
        self.status = status
        self.current_step = "completed"
        self.last_update = time.time()


class UploadProgressTracker:
    """
    Global upload progress tracker with thread-safe concurrent access.

    Maintains progress state for all active upload sessions.
    Auto-cleans sessions older than 1 hour.

    PHASE 2: Added asyncio.Lock to prevent race conditions when multiple
    concurrent uploads access the shared _sessions dictionary.
    """

    def __init__(self):
        self._sessions: Dict[str, UploadProgress] = {}
        self._max_age_seconds = 3600  # 1 hour
        self._lock = asyncio.Lock()  # PHASE 2: Thread-safe access

    async def create_session(
        self,
        upload_id: str,
        repository: str,
        total_files: int
    ) -> UploadProgress:
        """
        Create new upload progress session (thread-safe).

        PHASE 2: Now async with lock protection.
        """
        async with self._lock:
            progress = UploadProgress(
                upload_id=upload_id,
                repository=repository,
                total_files=total_files,
            )
            self._sessions[upload_id] = progress
            logger.info(f"Created progress tracker for upload {upload_id}: {total_files} files")

            # Clean old sessions while holding lock
            self._cleanup_old_sessions()

            return progress

    async def get_session(self, upload_id: str) -> Optional[UploadProgress]:
        """
        Get progress session by ID (NO LOCK for fast read access).

        BUGFIX: Removed lock to prevent blocking status endpoint.
        Dict.get() is atomic in Python, so no race condition risk.
        """
        return self._sessions.get(upload_id)

    async def remove_session(self, upload_id: str):
        """
        Remove progress session (thread-safe).

        PHASE 2: Now async with lock protection.
        """
        async with self._lock:
            if upload_id in self._sessions:
                del self._sessions[upload_id]
                logger.info(f"Removed progress tracker for upload {upload_id}")

    def _cleanup_old_sessions(self):
        """
        Remove sessions older than max age.

        NOTE: This is a private method called only while holding self._lock,
        so it doesn't need additional locking.
        """
        now = time.time()
        to_remove = []

        for upload_id, progress in self._sessions.items():
            age = now - progress.start_time
            if age > self._max_age_seconds:
                to_remove.append(upload_id)

        for upload_id in to_remove:
            logger.info(f"Auto-cleaning old upload session: {upload_id}")
            del self._sessions[upload_id]

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old upload sessions")

    async def get_all_sessions(self) -> List[Dict]:
        """
        Get all active sessions (for debugging) - thread-safe.

        PHASE 2: Now async with lock protection.
        """
        async with self._lock:
            return [p.to_dict() for p in self._sessions.values()]


# Global singleton instance
_tracker = UploadProgressTracker()


def get_tracker() -> UploadProgressTracker:
    """Get global upload progress tracker instance."""
    return _tracker
