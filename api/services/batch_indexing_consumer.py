"""
Batch indexing consumer: Reads Redis Stream and processes batches.

EPIC-27: Batch Processing with Redis Streams
Architecture: Redis Stream → Consumer → subprocess.Popen → Update Status
"""

import asyncio
import subprocess
import sys
import json
import os
from pathlib import Path
from typing import Dict, List
import redis.asyncio as redis
from datetime import datetime

from services.batch_indexing_errors import ErrorType, ErrorHandler


class BatchIndexingConsumer:
    """
    Consumer: Reads Redis Stream, processes batches via subprocess isolation.

    Flow:
        1. Create consumer group (if not exists)
        2. XREADGROUP to read batches
        3. For each batch: spawn subprocess → process → update status → XACK
        4. Check completion → trigger graph construction

    Isolation:
        - subprocess = separate Python process
        - PyTorch models loaded per subprocess
        - Exit subprocess → automatic memory cleanup
    """

    STREAM_KEY_TEMPLATE = "indexing:jobs:{repository}"
    STATUS_KEY_TEMPLATE = "indexing:status:{repository}"
    CONSUMER_GROUP = "indexing-workers"
    CONSUMER_NAME = "worker-1"  # TODO: Generate unique ID per container
    READ_BLOCK_MS = 5000  # Block 5s if stream empty
    READ_COUNT = 1  # 1 batch at a time
    MAX_RETRY_ATTEMPTS = 3
    PENDING_CHECK_INTERVAL = 60  # Check pending every 60s

    def __init__(
        self,
        redis_url: str = "redis://redis:6379/0",
        db_url: str = None
    ):
        self.redis_url = redis_url
        self.db_url = db_url or os.getenv("DATABASE_URL")
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

    def _classify_error(self, error: Exception) -> ErrorType:
        """
        Classify error to determine action.

        Args:
            error: Exception raised during processing

        Returns:
            ErrorType enum value
        """
        error_str = str(error).lower()

        if "timeout" in error_str:
            return ErrorType.SUBPROCESS_TIMEOUT
        elif "connection" in error_str or "database" in error_str:
            return ErrorType.DB_CONNECTION_ERROR
        elif "memory" in error_str or "oom" in error_str:
            return ErrorType.OUT_OF_MEMORY
        elif "subprocess" in error_str or "process" in error_str:
            return ErrorType.SUBPROCESS_CRASH
        else:
            return ErrorType.CRITICAL_ERROR

    async def _run_subprocess_worker(
        self,
        repository: str,
        files: List[str],
        timeout: int = 300  # 5min per batch (40 files × 7.5s = 300s)
    ) -> Dict:
        """
        Execute subprocess worker for 1 batch.

        Args:
            repository: Repository name
            files: List of file paths to process
            timeout: Timeout in seconds (default: 5min)

        Returns:
            Dict with keys:
            - success_count: int
            - error_count: int
            - error: str (if subprocess failed)

        Raises:
            TimeoutError: If subprocess exceeds timeout
            RuntimeError: If subprocess crashes
        """
        # Spawn subprocess using asyncio.create_subprocess_exec()
        process = await asyncio.create_subprocess_exec(
            "python3",
            "/app/workers/batch_worker_subprocess.py",
            "--repository", repository,
            "--db-url", self.db_url,
            "--files", ",".join(files),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Wait with timeout
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            # Kill subprocess on timeout
            process.kill()
            await process.wait()
            raise TimeoutError(f"Subprocess timeout after {timeout}s")

        # Check exit code
        if process.returncode != 0:
            stderr_str = stderr.decode() if stderr else "No error output"
            raise RuntimeError(f"Subprocess failed with exit code {process.returncode}: {stderr_str}")

        # Parse JSON result from stdout
        try:
            result = json.loads(stdout.decode())
            return {
                "success_count": result["success_count"],
                "error_count": result["error_count"]
            }
        except (json.JSONDecodeError, KeyError) as e:
            raise RuntimeError(f"Failed to parse subprocess result: {e}")
