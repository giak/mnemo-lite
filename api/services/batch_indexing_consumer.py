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
from services.graph_construction_service import GraphConstructionService


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
            await self.redis_client.aclose()

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

    async def _ensure_consumer_group(self, stream_key: str):
        """
        Create consumer group if not exists.

        Args:
            stream_key: Redis Stream key

        Handles:
            - BUSYGROUP error (group already exists) - OK
            - Other errors - propagate
        """
        try:
            await self.redis_client.xgroup_create(
                stream_key,
                self.CONSUMER_GROUP,
                id="0",
                mkstream=True
            )
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise  # Re-raise non-BUSYGROUP errors

    async def _update_status(self, repository: str, updates: Dict):
        """
        Update Redis status hash with partial updates.

        Args:
            repository: Repository name
            updates: Dict with keys like:
                - processed_files: int (use HINCRBY)
                - failed_files: int (use HINCRBY)
                - current_batch: str
                - status: str
                - completed_at: str
        """
        status_key = self.STATUS_KEY_TEMPLATE.format(repository=repository)

        # Handle counter increments
        if "processed_files" in updates:
            await self.redis_client.hincrby(status_key, "processed_files", updates["processed_files"])
            del updates["processed_files"]

        if "failed_files" in updates:
            await self.redis_client.hincrby(status_key, "failed_files", updates["failed_files"])
            del updates["failed_files"]

        # Handle string updates
        if updates:
            await self.redis_client.hset(
                status_key,
                mapping={k: str(v) for k, v in updates.items()}
            )

    async def _check_pending_messages(self, stream_key: str) -> List[Dict]:
        """
        Find messages not acknowledged after PENDING_CHECK_INTERVAL.

        Args:
            stream_key: Redis Stream key

        Returns:
            List of pending message dicts with keys:
            - message_id
            - consumer
            - idle_time_ms
            - delivery_count
        """
        try:
            pending = await self.redis_client.xpending_range(
                stream_key,
                self.CONSUMER_GROUP,
                min="-",
                max="+",
                count=10
            )

            # Filter messages idle for more than PENDING_CHECK_INTERVAL
            idle_threshold_ms = self.PENDING_CHECK_INTERVAL * 1000
            result = []

            for msg in pending:
                if msg["time_since_delivered"] >= idle_threshold_ms:
                    result.append({
                        "message_id": msg["message_id"],
                        "consumer": msg["consumer"],
                        "idle_time_ms": msg["time_since_delivered"],
                        "delivery_count": msg["times_delivered"]
                    })

            return result

        except redis.ResponseError as e:
            # No pending messages or group doesn't exist
            return []

    async def _retry_pending_batch(
        self,
        stream_key: str,
        message_id: str,
        repository: str
    ):
        """
        Claim abandoned message and retry processing.

        Args:
            stream_key: Redis Stream key
            message_id: Message ID to claim
            repository: Repository name
        """
        # Claim message
        try:
            claimed = await self.redis_client.xclaim(
                stream_key,
                self.CONSUMER_GROUP,
                self.CONSUMER_NAME,
                min_idle_time=self.PENDING_CHECK_INTERVAL * 1000,
                message_ids=[message_id]
            )

            if not claimed:
                # Message already claimed or doesn't exist
                return

            # Parse message data
            message_data = claimed[0][1]
            files_str = message_data["files"]
            files = files_str.split(",")
            batch_number = message_data["batch_number"]

            # Update status to show retry
            await self._update_status(
                repository,
                {"current_batch": batch_number, "status": "processing"}
            )

            # Retry subprocess
            try:
                result = await self._run_subprocess_worker(repository, files)

                # Update status with results
                await self._update_status(
                    repository,
                    {
                        "processed_files": result["success_count"],
                        "failed_files": result["error_count"]
                    }
                )

                # XACK on success
                await self.redis_client.xack(stream_key, self.CONSUMER_GROUP, message_id)

            except Exception as e:
                # Log error, but XACK to avoid infinite retries
                error_type = self._classify_error(e)

                # Only retry if retryable and under max attempts
                if ErrorHandler.is_retryable(error_type):
                    # Leave message pending for next retry cycle
                    pass
                else:
                    # Non-retryable error - XACK and mark as failed
                    await self._update_status(
                        repository,
                        {"failed_files": len(files)}
                    )
                    await self.redis_client.xack(stream_key, self.CONSUMER_GROUP, message_id)

        except redis.ResponseError as e:
            # Claim failed - message may have been claimed by another consumer
            pass

    async def _trigger_graph_construction(self, repository: str, engine):
        """
        Trigger graph construction after all batches complete.

        Args:
            repository: Repository name
            engine: SQLAlchemy AsyncEngine for database access
        """
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text
        import logging

        logger = logging.getLogger(__name__)

        try:
            # Create engine if not provided
            if not engine:
                engine = create_async_engine(self.db_url)

            # Detect languages from chunks
            async with engine.begin() as conn:
                result = await conn.execute(
                    text("""
                        SELECT DISTINCT language
                        FROM code_chunks
                        WHERE repository = :repo
                        ORDER BY language
                    """),
                    {"repo": repository}
                )
                languages = [row.language for row in result]

            if not languages:
                logger.warning(f"No chunks found for repository '{repository}', skipping graph construction")
                return

            logger.info(f"Triggering graph construction for '{repository}' with languages: {languages}")

            # Build graph with detected languages
            graph_service = GraphConstructionService(engine)
            stats = await graph_service.build_graph_for_repository(repository, languages=languages)

            logger.info(f"Graph construction complete: {stats.total_nodes} nodes, {stats.total_edges} edges")

            # Update status to completed
            await self._update_status(
                repository,
                {
                    "status": "completed",
                    "completed_at": datetime.now().isoformat()
                }
            )

            logger.info(f"Graph construction completed for repository '{repository}'")

        except Exception as e:
            logger.error(f"Graph construction failed for repository '{repository}': {e}", exc_info=True)

            # Still mark as completed (indexing succeeded, graph construction is supplementary)
            await self._update_status(
                repository,
                {
                    "status": "completed",
                    "completed_at": datetime.now().isoformat()
                }
            )

    async def process_repository(
        self,
        repository: str,
        stop_event: asyncio.Event = None
    ) -> Dict:
        """
        Main consumer loop: Process all batches from Redis Stream.

        Steps:
            1. Create consumer group
            2. Loop while stream has messages:
               - XREADGROUP to read 1 batch
               - Parse message
               - Call _run_subprocess_worker()
               - Update status hash
               - XACK message
               - Check stop_event
            3. Check pending messages every 60s
            4. Trigger graph construction when complete

        Args:
            repository: Repository name
            stop_event: Optional asyncio.Event to signal graceful stop

        Returns:
            Dict with final stats:
            - processed_files: int
            - failed_files: int
            - status: str
            - completed_at: str
        """
        stream_key = self.STREAM_KEY_TEMPLATE.format(repository=repository)
        status_key = self.STATUS_KEY_TEMPLATE.format(repository=repository)

        # Step 1: Ensure consumer group exists
        await self._ensure_consumer_group(stream_key)

        # Update status to processing
        await self._update_status(repository, {"status": "processing"})

        last_pending_check = datetime.now()

        # Step 2: Main processing loop
        while True:
            # Check stop_event
            if stop_event and stop_event.is_set():
                break

            # Check pending messages every 60s
            now = datetime.now()
            if (now - last_pending_check).total_seconds() >= self.PENDING_CHECK_INTERVAL:
                pending_messages = await self._check_pending_messages(stream_key)
                for msg in pending_messages:
                    await self._retry_pending_batch(
                        stream_key,
                        msg["message_id"],
                        repository
                    )
                last_pending_check = now

            # XREADGROUP to read 1 batch
            try:
                messages = await self.redis_client.xreadgroup(
                    groupname=self.CONSUMER_GROUP,
                    consumername=self.CONSUMER_NAME,
                    streams={stream_key: ">"},
                    count=self.READ_COUNT,
                    block=self.READ_BLOCK_MS
                )
            except redis.ResponseError as e:
                # Consumer group may not exist - try to create it
                await self._ensure_consumer_group(stream_key)
                continue

            # No more messages
            if not messages or len(messages) == 0:
                break

            # Parse message
            stream_name, message_list = messages[0]
            if not message_list:
                break

            message_id, message_data = message_list[0]

            # Extract fields
            batch_number = message_data["batch_number"]
            files_str = message_data["files"]
            files = files_str.split(",")

            # Update status
            await self._update_status(
                repository,
                {"current_batch": batch_number}
            )

            # Process batch
            try:
                result = await self._run_subprocess_worker(repository, files)

                # Update status with results
                await self._update_status(
                    repository,
                    {
                        "processed_files": result["success_count"],
                        "failed_files": result["error_count"]
                    }
                )

            except Exception as e:
                # Log error
                error_type = self._classify_error(e)

                # Update failed count
                await self._update_status(
                    repository,
                    {"failed_files": len(files)}
                )

                # If critical error, stop consumer
                if ErrorHandler.should_stop_consumer(error_type):
                    raise

            # XACK message
            await self.redis_client.xack(stream_key, self.CONSUMER_GROUP, message_id)

        # Step 3: Final pending check
        pending_messages = await self._check_pending_messages(stream_key)
        for msg in pending_messages:
            await self._retry_pending_batch(
                stream_key,
                msg["message_id"],
                repository
            )

        # Step 4: Get final status
        status = await self.redis_client.hgetall(status_key)

        # If not stopped early, trigger graph construction
        if not (stop_event and stop_event.is_set()):
            # Check if there are any pending (unprocessed) messages
            # XLEN returns total messages, but we need to check XPENDING for unacknowledged messages
            pending_messages = await self._check_pending_messages(stream_key)

            # Only trigger graph if NO pending messages
            if len(pending_messages) == 0:
                # Trigger graph construction
                from sqlalchemy.ext.asyncio import create_async_engine
                engine = create_async_engine(self.db_url)
                await self._trigger_graph_construction(repository, engine)
                await engine.dispose()

                # Refresh status after graph construction
                status = await self.redis_client.hgetall(status_key)

        # Return final stats
        return {
            "processed_files": int(status.get("processed_files", 0)),
            "failed_files": int(status.get("failed_files", 0)),
            "status": status.get("status", "unknown"),
            "completed_at": status.get("completed_at", "")
        }
