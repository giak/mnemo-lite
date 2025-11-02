"""
Batch indexing producer: Scans directories and enqueues batches.

EPIC-27: Batch Processing with Redis Streams
Architecture: Producer → Redis Streams → Consumer
"""

import asyncio
import uuid
from pathlib import Path
from typing import List, Dict
import redis.asyncio as redis
from datetime import datetime, timezone


class BatchIndexingProducer:
    """
    Producer: Scans directory, divides into batches, enqueues to Redis Stream.

    Flow:
        1. Scan directory for .ts/.js files
        2. Divide into batches of 40 files
        3. Enqueue batches into Redis Stream
        4. Initialize status Hash for tracking
    """

    BATCH_SIZE = 40  # Optimal: 40 files × ~5s = ~3min/batch
    STREAM_KEY_TEMPLATE = "indexing:jobs:{repository}"
    STATUS_KEY_TEMPLATE = "indexing:status:{repository}"
    STREAM_MAX_LEN = 1000
    STATUS_TTL = 86400  # 24h auto-cleanup

    def __init__(self, redis_url: str = "redis://redis:6379/0"):
        self.redis_url = redis_url
        self.redis_client: redis.Redis | None = None

    async def connect(self):
        """Initialize Redis connection."""
        if not self.redis_client:
            self.redis_client = await redis.from_url(
                self.redis_url,
                decode_responses=True
            )

    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.aclose()

    def _scan_files(self, directory: Path, extensions: List[str]) -> List[Path]:
        """
        Scan directory for files with specified extensions.

        Args:
            directory: Root directory to scan
            extensions: List of extensions (e.g., [".ts", ".js"])

        Returns:
            Sorted list of file paths
        """
        files = []
        for ext in extensions:
            files.extend(directory.rglob(f"*{ext}"))
        return sorted(files)  # Sort for reproducibility

    def _create_batches(self, files: List[Path], batch_size: int) -> List[List[Path]]:
        """
        Divide files into batches.

        Args:
            files: List of file paths
            batch_size: Number of files per batch

        Returns:
            List of batches (each batch is a list of paths)
        """
        batches = []
        for i in range(0, len(files), batch_size):
            batches.append(files[i:i + batch_size])
        return batches

    async def scan_and_enqueue(
        self,
        directory: Path,
        repository: str,
        extensions: List[str] = [".ts", ".js"]
    ) -> Dict:
        """
        Scan directory, divide into batches, enqueue to Redis Stream.

        Args:
            directory: Directory to scan
            repository: Repository name
            extensions: File extensions to index

        Returns:
            {
                "job_id": "uuid",
                "total_files": 261,
                "total_batches": 7,
                "status": "pending"
            }
        """
        await self.connect()

        # 1. Scan files
        files = self._scan_files(directory, extensions)
        total_files = len(files)

        # 2. Divide into batches
        batches = self._create_batches(files, self.BATCH_SIZE)
        total_batches = len(batches)

        # 3. Initialize status hash
        job_id = str(uuid.uuid4())
        await self._init_status(repository, job_id, total_files, total_batches)

        # 4. Enqueue batches into Redis Stream
        stream_key = self.STREAM_KEY_TEMPLATE.format(repository=repository)

        for batch_num, batch_files in enumerate(batches, start=1):
            message = {
                "job_id": job_id,
                "repository": repository,
                "batch_number": str(batch_num),
                "total_batches": str(total_batches),
                "files": ",".join(str(f) for f in batch_files),  # Serialize paths
                "created_at": datetime.now(timezone.utc).isoformat()
            }

            await self.redis_client.xadd(
                stream_key,
                message,
                maxlen=self.STREAM_MAX_LEN,
                approximate=True
            )

        return {
            "job_id": job_id,
            "total_files": total_files,
            "total_batches": total_batches,
            "status": "pending"
        }

    async def _init_status(
        self,
        repository: str,
        job_id: str,
        total_files: int,
        total_batches: int
    ):
        """Initialize Redis Hash for status tracking."""
        status_key = self.STATUS_KEY_TEMPLATE.format(repository=repository)

        await self.redis_client.hset(
            status_key,
            mapping={
                "job_id": job_id,
                "total_files": str(total_files),
                "total_batches": str(total_batches),
                "processed_files": "0",
                "failed_files": "0",
                "current_batch": "0",
                "status": "pending",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": "",
                "errors": "[]"
            }
        )

        # Set TTL for auto-cleanup
        await self.redis_client.expire(status_key, self.STATUS_TTL)

    async def get_status(self, repository: str) -> Dict:
        """
        Get current indexing status.

        Returns:
            {
                "job_id": "...",
                "total_files": 261,
                "processed_files": 120,
                "failed_files": 2,
                "current_batch": 3,
                "total_batches": 7,
                "status": "processing",
                "progress": "120/261",
                "started_at": "...",
                "completed_at": "..."
            }
        """
        await self.connect()

        status_key = self.STATUS_KEY_TEMPLATE.format(repository=repository)
        status = await self.redis_client.hgetall(status_key)

        if not status:
            return {"status": "not_found"}

        return {
            "job_id": status.get("job_id"),
            "total_files": int(status.get("total_files", 0)),
            "processed_files": int(status.get("processed_files", 0)),
            "failed_files": int(status.get("failed_files", 0)),
            "current_batch": int(status.get("current_batch", 0)),
            "total_batches": int(status.get("total_batches", 0)),
            "status": status.get("status"),
            "progress": f"{status.get('processed_files', 0)}/{status.get('total_files', 0)}",
            "started_at": status.get("started_at"),
            "completed_at": status.get("completed_at")
        }
