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
from datetime import datetime


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
            await self.redis_client.close()

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
