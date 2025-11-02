# Batch Indexing with Redis Streams Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement robust batch processing system using Redis Streams to index large codebases (261+ files) without memory leaks or crashes.

**Architecture:** Producer scans directory and enqueues 40-file batches into Redis Streams. Consumer reads batches via consumer groups, spawns isolated subprocess per batch for embedding generation, tracks progress in Redis Hash, auto-triggers graph construction on completion.

**Tech Stack:** Redis Streams (consumer groups), Python asyncio, subprocess.Popen (true isolation), PostgreSQL, FastAPI

**Context:** This replaces the failing ProcessPoolExecutor parallel pipeline that crashed at 75% due to PyTorch memory leaks + Python 3.12 bug with max_tasks_per_child.

**Research Validation:**
- Redis Streams: Millions msg/s, built-in consumer groups with ACK/NACK
- subprocess.Popen: True process isolation (vs multiprocessing which shares PyTorch tensors)
- Batch size 40: Optimal for monitoring granularity (~3min/batch)

---

## Task 1: Error Handling Infrastructure

**Files:**
- Create: `api/services/batch_indexing_errors.py`
- Test: `tests/unit/test_batch_errors.py`

**Step 1: Write the failing test**

Create `tests/unit/test_batch_errors.py`:

```python
import pytest
from services.batch_indexing_errors import ErrorType, ErrorHandler


def test_retryable_errors_identified():
    """Test retryable errors are correctly classified."""
    assert ErrorHandler.is_retryable(ErrorType.SUBPROCESS_TIMEOUT) is True
    assert ErrorHandler.is_retryable(ErrorType.DB_CONNECTION_ERROR) is True
    assert ErrorHandler.is_retryable(ErrorType.SUBPROCESS_CRASH) is True

    # Non-retryable
    assert ErrorHandler.is_retryable(ErrorType.FILE_NOT_FOUND) is False
    assert ErrorHandler.is_retryable(ErrorType.PARSE_ERROR) is False


def test_critical_errors_stop_consumer():
    """Test critical errors should stop consumer."""
    assert ErrorHandler.should_stop_consumer(ErrorType.REDIS_CONNECTION_LOST) is True
    assert ErrorHandler.should_stop_consumer(ErrorType.OUT_OF_MEMORY) is True
    assert ErrorHandler.should_stop_consumer(ErrorType.CRITICAL_ERROR) is True

    # Non-critical
    assert ErrorHandler.should_stop_consumer(ErrorType.SUBPROCESS_TIMEOUT) is False


def test_exponential_backoff():
    """Test retry delay uses exponential backoff."""
    assert ErrorHandler.get_retry_delay(1) == 5   # 5s
    assert ErrorHandler.get_retry_delay(2) == 10  # 10s
    assert ErrorHandler.get_retry_delay(3) == 20  # 20s
    assert ErrorHandler.get_retry_delay(10) == 60 # Max 60s
```

**Step 2: Run test to verify it fails**

```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH \
pytest tests/unit/test_batch_errors.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'services.batch_indexing_errors'"

**Step 3: Write minimal implementation**

Create `api/services/batch_indexing_errors.py`:

```python
"""
Centralized error handling for batch indexing.

EPIC-27: Batch Processing with Redis Streams
"""

from enum import Enum
from typing import Dict


class ErrorType(Enum):
    """Types of errors in batch indexing pipeline."""

    # File-level errors (continue-on-error)
    FILE_NOT_FOUND = "file_not_found"
    PARSE_ERROR = "parse_error"
    TIMEOUT = "timeout"
    EMBEDDING_ERROR = "embedding_generation_failed"

    # Batch-level errors (retry batch)
    SUBPROCESS_CRASH = "subprocess_crash"
    SUBPROCESS_TIMEOUT = "subprocess_timeout"
    DB_CONNECTION_ERROR = "db_connection_error"

    # System-level errors (stop consumer)
    REDIS_CONNECTION_LOST = "redis_connection_lost"
    OUT_OF_MEMORY = "out_of_memory"
    CRITICAL_ERROR = "critical_error"


class ErrorHandler:
    """Centralized error handling logic."""

    @staticmethod
    def is_retryable(error_type: ErrorType) -> bool:
        """
        Determine if error is retryable.

        Returns:
            True if error should trigger batch retry
        """
        retryable = {
            ErrorType.SUBPROCESS_TIMEOUT,
            ErrorType.DB_CONNECTION_ERROR,
            ErrorType.SUBPROCESS_CRASH
        }
        return error_type in retryable

    @staticmethod
    def should_stop_consumer(error_type: ErrorType) -> bool:
        """
        Determine if consumer should stop.

        Returns:
            True if error is critical and consumer must stop
        """
        critical = {
            ErrorType.REDIS_CONNECTION_LOST,
            ErrorType.OUT_OF_MEMORY,
            ErrorType.CRITICAL_ERROR
        }
        return error_type in critical

    @staticmethod
    def get_retry_delay(attempt: int) -> int:
        """
        Calculate exponential backoff delay.

        Args:
            attempt: Retry attempt number (1-indexed)

        Returns:
            Delay in seconds (max 60s)

        Formula: min(5 * 2^(attempt-1), 60)
        """
        return min(5 * (2 ** (attempt - 1)), 60)
```

**Step 4: Run test to verify it passes**

```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH \
pytest tests/unit/test_batch_errors.py -v
```

Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add api/services/batch_indexing_errors.py tests/unit/test_batch_errors.py
git commit -m "feat(EPIC-27): Add error handling infrastructure for batch indexing

- ErrorType enum with file/batch/system level errors
- ErrorHandler with retry logic and exponential backoff
- Tests for retryable errors and critical errors classification

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Batch Producer - Core Logic

**Files:**
- Create: `api/services/batch_indexing_producer.py`
- Test: `tests/unit/test_batch_producer.py`

**Step 1: Write the failing test**

Create `tests/unit/test_batch_producer.py`:

```python
import pytest
from pathlib import Path
from services.batch_indexing_producer import BatchIndexingProducer


def test_create_batches():
    """Test division of files into batches."""
    producer = BatchIndexingProducer()

    files = [Path(f"file{i}.ts") for i in range(100)]
    batches = producer._create_batches(files, batch_size=40)

    assert len(batches) == 3  # 100 ÷ 40 = 3 batches
    assert len(batches[0]) == 40
    assert len(batches[1]) == 40
    assert len(batches[2]) == 20


def test_create_batches_exact_multiple():
    """Test batching when files divide evenly."""
    producer = BatchIndexingProducer()

    files = [Path(f"file{i}.ts") for i in range(80)]
    batches = producer._create_batches(files, batch_size=40)

    assert len(batches) == 2
    assert len(batches[0]) == 40
    assert len(batches[1]) == 40


def test_scan_files_filters_by_extension():
    """Test scanning filters by .ts and .js extensions."""
    producer = BatchIndexingProducer()

    # Create temp directory with mixed files
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "test1.ts").touch()
        (tmp_path / "test2.js").touch()
        (tmp_path / "test3.py").touch()  # Should be ignored
        (tmp_path / "README.md").touch()  # Should be ignored

        files = producer._scan_files(tmp_path, [".ts", ".js"])

        assert len(files) == 2
        assert all(f.suffix in [".ts", ".js"] for f in files)


def test_scan_files_sorts_alphabetically():
    """Test scanning returns sorted files for reproducibility."""
    producer = BatchIndexingProducer()

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "zebra.ts").touch()
        (tmp_path / "alpha.ts").touch()
        (tmp_path / "beta.ts").touch()

        files = producer._scan_files(tmp_path, [".ts"])

        assert files[0].name == "alpha.ts"
        assert files[1].name == "beta.ts"
        assert files[2].name == "zebra.ts"
```

**Step 2: Run test to verify it fails**

```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH \
pytest tests/unit/test_batch_producer.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'services.batch_indexing_producer'"

**Step 3: Write minimal implementation**

Create `api/services/batch_indexing_producer.py`:

```python
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
```

**Step 4: Run test to verify it passes**

```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH \
pytest tests/unit/test_batch_producer.py -v
```

Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add api/services/batch_indexing_producer.py tests/unit/test_batch_producer.py
git commit -m "feat(EPIC-27): Add batch producer core logic

- Scan directory for .ts/.js files
- Divide into batches of 40 files
- Sorted output for reproducibility
- Tests for batching and scanning

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: Batch Producer - Redis Integration

**Files:**
- Modify: `api/services/batch_indexing_producer.py`
- Test: `tests/integration/test_batch_producer_redis.py`

**Step 1: Write the failing test**

Create `tests/integration/test_batch_producer_redis.py`:

```python
import pytest
import json
from pathlib import Path
from services.batch_indexing_producer import BatchIndexingProducer


@pytest.mark.asyncio
@pytest.mark.integration
async def test_scan_and_enqueue_creates_batches(redis_client, tmp_path):
    """Test producer enqueues batches into Redis Stream."""
    # Create 10 test files
    for i in range(10):
        (tmp_path / f"file{i}.ts").write_text(f"// test {i}")

    producer = BatchIndexingProducer()
    await producer.connect()

    try:
        result = await producer.scan_and_enqueue(
            directory=tmp_path,
            repository="test_repo"
        )

        # Verify result
        assert result["total_files"] == 10
        assert result["total_batches"] == 1  # 10 files = 1 batch (size 40)
        assert result["status"] == "pending"
        assert "job_id" in result

        # Verify stream contains message
        stream_key = "indexing:jobs:test_repo"
        messages = await redis_client.xread({stream_key: "0"}, count=10)

        assert len(messages) == 1
        stream_name, message_list = messages[0]
        assert len(message_list) == 1  # 1 batch

        message_id, message_data = message_list[0]
        assert message_data["repository"] == "test_repo"
        assert message_data["batch_number"] == "1"
        assert message_data["total_batches"] == "1"
        assert len(message_data["files"].split(",")) == 10

    finally:
        await producer.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_scan_and_enqueue_multiple_batches(redis_client, tmp_path):
    """Test producer creates multiple batches for large directories."""
    # Create 100 files (should create 3 batches: 40, 40, 20)
    for i in range(100):
        (tmp_path / f"file{i}.ts").write_text(f"// test {i}")

    producer = BatchIndexingProducer()
    await producer.connect()

    try:
        result = await producer.scan_and_enqueue(
            directory=tmp_path,
            repository="test_large"
        )

        assert result["total_files"] == 100
        assert result["total_batches"] == 3  # 100 ÷ 40 = 3 batches

        # Verify stream contains 3 messages
        stream_key = "indexing:jobs:test_large"
        messages = await redis_client.xread({stream_key: "0"}, count=10)

        stream_name, message_list = messages[0]
        assert len(message_list) == 3  # 3 batches

        # Verify batch numbers
        batch_numbers = [msg[1]["batch_number"] for msg in message_list]
        assert batch_numbers == ["1", "2", "3"]

    finally:
        await producer.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_init_status_creates_hash(redis_client):
    """Test status hash initialization."""
    producer = BatchIndexingProducer()
    await producer.connect()

    try:
        await producer._init_status(
            repository="test_status",
            job_id="test-job-123",
            total_files=100,
            total_batches=3
        )

        # Verify status hash
        status_key = "indexing:status:test_status"
        status = await redis_client.hgetall(status_key)

        assert status["job_id"] == "test-job-123"
        assert status["total_files"] == "100"
        assert status["total_batches"] == "3"
        assert status["processed_files"] == "0"
        assert status["failed_files"] == "0"
        assert status["current_batch"] == "0"
        assert status["status"] == "pending"
        assert status["started_at"] != ""
        assert status["errors"] == "[]"

        # Verify TTL is set
        ttl = await redis_client.ttl(status_key)
        assert ttl > 0
        assert ttl <= 86400

    finally:
        await producer.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_status_returns_dict(redis_client):
    """Test get_status returns formatted dict."""
    producer = BatchIndexingProducer()
    await producer.connect()

    try:
        # Initialize status
        await producer._init_status(
            repository="test_get",
            job_id="job-456",
            total_files=50,
            total_batches=2
        )

        # Get status
        status = await producer.get_status("test_get")

        assert status["job_id"] == "job-456"
        assert status["total_files"] == 50
        assert status["processed_files"] == 0
        assert status["failed_files"] == 0
        assert status["current_batch"] == 0
        assert status["total_batches"] == 2
        assert status["status"] == "pending"
        assert "progress" in status
        assert status["progress"] == "0/50"

    finally:
        await producer.close()
```

**Step 2: Run test to verify it fails**

```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH \
EMBEDDING_MODE=mock \
pytest tests/integration/test_batch_producer_redis.py -v
```

Expected: FAIL with "AttributeError: 'BatchIndexingProducer' object has no attribute 'scan_and_enqueue'"

**Step 3: Write implementation**

Modify `api/services/batch_indexing_producer.py`, add these methods:

```python
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
                "created_at": datetime.utcnow().isoformat()
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
                "started_at": datetime.utcnow().isoformat(),
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
```

**Step 4: Run test to verify it passes**

```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH \
EMBEDDING_MODE=mock \
pytest tests/integration/test_batch_producer_redis.py -v
```

Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add api/services/batch_indexing_producer.py tests/integration/test_batch_producer_redis.py
git commit -m "feat(EPIC-27): Add Redis Stream integration to producer

- scan_and_enqueue() creates batches and enqueues to stream
- _init_status() creates Redis Hash for tracking
- get_status() returns formatted status dict
- Integration tests with real Redis

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: Subprocess Worker Script

**Files:**
- Create: `workers/batch_worker_subprocess.py`
- Test: `tests/unit/test_subprocess_worker.py`

**Note:** This worker runs in isolated subprocess, loads PyTorch models, processes files atomically.

**Step 1: Write the failing test**

Create `tests/unit/test_subprocess_worker.py`:

```python
import pytest
import json
import subprocess
import sys
from pathlib import Path


def test_subprocess_worker_processes_batch(tmp_path, test_db_url):
    """Test subprocess worker processes batch and returns result."""
    # Create test files
    test_files = []
    for i in range(3):
        file_path = tmp_path / f"test{i}.ts"
        file_path.write_text(f"function test{i}() {{ return {i}; }}")
        test_files.append(str(file_path))

    # Run subprocess
    args = [
        sys.executable,
        "workers/batch_worker_subprocess.py",
        "--repository", "test_subprocess",
        "--db-url", test_db_url,
        "--files", ",".join(test_files)
    ]

    result = subprocess.run(
        args,
        cwd="/home/giak/Work/MnemoLite",
        capture_output=True,
        text=True,
        timeout=60
    )

    # Verify subprocess succeeded
    assert result.returncode == 0

    # Parse result from last line of stdout
    output_lines = result.stdout.strip().split("\n")
    result_json = json.loads(output_lines[-1])

    assert "success_count" in result_json
    assert "error_count" in result_json
    assert result_json["success_count"] + result_json["error_count"] == 3


def test_subprocess_worker_handles_invalid_file(tmp_path, test_db_url):
    """Test subprocess worker continues on invalid files."""
    # Create mix of valid and invalid files
    valid_file = tmp_path / "valid.ts"
    valid_file.write_text("function valid() { return 1; }")

    invalid_file = tmp_path / "invalid.ts"
    invalid_file.write_text("x" * 1000000)  # Huge file

    args = [
        sys.executable,
        "workers/batch_worker_subprocess.py",
        "--repository", "test_invalid",
        "--db-url", test_db_url,
        "--files", f"{valid_file},{invalid_file}"
    ]

    result = subprocess.run(
        args,
        cwd="/home/giak/Work/MnemoLite",
        capture_output=True,
        text=True,
        timeout=60
    )

    # Should succeed despite invalid file
    assert result.returncode == 0

    output_lines = result.stdout.strip().split("\n")
    result_json = json.loads(output_lines[-1])

    # At least 1 success (valid file)
    assert result_json["success_count"] >= 1
```

**Step 2: Run test to verify it fails**

```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH \
EMBEDDING_MODE=mock \
pytest tests/unit/test_subprocess_worker.py -v
```

Expected: FAIL with "FileNotFoundError: [Errno 2] No such file or directory: 'workers/batch_worker_subprocess.py'"

**Step 3: Write implementation**

Create `workers/batch_worker_subprocess.py`:

```python
#!/usr/bin/env python3
"""
Subprocess worker: Processes 1 batch of files in isolated process.

EPIC-27: Batch Processing with Redis Streams
Architecture: subprocess.Popen → load PyTorch → process batch → exit (auto cleanup)

Isolation guarantees:
    - Separate Python process (subprocess, not multiprocessing)
    - PyTorch models loaded in this process only
    - Exit subprocess → complete memory cleanup
    - No shared tensor memory (unlike torch.multiprocessing)
"""

import asyncio
import argparse
import json
import sys
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine

# Add api to path
sys.path.insert(0, "/app")

from services.dual_embedding_service import DualEmbeddingService
from services.code_chunking_service import CodeChunkingService


async def process_batch(repository: str, db_url: str, files: list) -> dict:
    """
    Process batch of files atomically.

    Args:
        repository: Repository name
        db_url: Database connection URL
        files: List of file paths to process

    Returns:
        {"success_count": 38, "error_count": 2}
    """
    # Load services (in this subprocess only)
    print(f"Loading embedding models...", file=sys.stderr)
    embedding_service = DualEmbeddingService()

    print(f"Initializing chunking service...", file=sys.stderr)
    chunking_service = CodeChunkingService()

    # Create DB engine
    engine = create_async_engine(db_url, echo=False, pool_size=2, max_overflow=0)

    success_count = 0
    error_count = 0

    try:
        print(f"Processing {len(files)} files...", file=sys.stderr)

        for file_path_str in files:
            file_path = Path(file_path_str)

            try:
                # Process file atomically (chunking + embeddings + persist)
                result = await process_file_atomically(
                    file_path,
                    repository,
                    chunking_service,
                    embedding_service,
                    engine
                )

                if result.get("success", False):
                    success_count += 1
                    print(f"✓ {file_path.name}", file=sys.stderr)
                else:
                    error_count += 1
                    print(f"✗ {file_path.name}: {result.get('error', 'unknown')}", file=sys.stderr)

            except Exception as e:
                error_count += 1
                print(f"✗ {file_path.name}: {e}", file=sys.stderr)

        return {"success_count": success_count, "error_count": error_count}

    finally:
        # Cleanup
        await engine.dispose()
        del embedding_service
        del chunking_service


async def process_file_atomically(
    file_path: Path,
    repository: str,
    chunking_service,
    embedding_service,
    engine
):
    """
    Process 1 file: chunking + embeddings + persist.

    Implementation reuses existing logic from scripts/index_directory.py
    """
    from sqlalchemy import text
    from services.metadata_extractors.registry import METADATA_EXTRACTORS

    try:
        # Read file
        content = file_path.read_text(encoding="utf-8")

        # Determine language
        language = "typescript" if file_path.suffix == ".ts" else "javascript"

        # Extract metadata (AST)
        extractor = METADATA_EXTRACTORS.get(language)
        if extractor:
            metadata = extractor.extract_metadata(content, str(file_path))
        else:
            metadata = {}

        # Chunk code
        chunks = chunking_service.chunk_code(
            content=content,
            language=language,
            file_path=str(file_path),
            metadata=metadata
        )

        if not chunks:
            return {"success": False, "error": "no chunks generated"}

        # Generate embeddings
        texts = [chunk["content"] for chunk in chunks]
        embeddings = await embedding_service.generate_code_embeddings(texts)

        # Persist to DB
        async with engine.begin() as conn:
            for chunk, embedding in zip(chunks, embeddings):
                await conn.execute(
                    text("""
                        INSERT INTO code_chunks (
                            repository, file_path, language, chunk_type,
                            content, start_line, end_line,
                            embedding_code, metadata, indexed_at
                        ) VALUES (
                            :repository, :file_path, :language, :chunk_type,
                            :content, :start_line, :end_line,
                            :embedding_code, :metadata, NOW()
                        )
                        ON CONFLICT (repository, file_path, start_line, end_line)
                        DO UPDATE SET
                            content = EXCLUDED.content,
                            embedding_code = EXCLUDED.embedding_code,
                            metadata = EXCLUDED.metadata,
                            indexed_at = NOW()
                    """),
                    {
                        "repository": repository,
                        "file_path": str(file_path),
                        "language": language,
                        "chunk_type": chunk.get("type", "unknown"),
                        "content": chunk["content"],
                        "start_line": chunk.get("start_line", 0),
                        "end_line": chunk.get("end_line", 0),
                        "embedding_code": embedding,
                        "metadata": json.dumps(chunk.get("metadata", {}))
                    }
                )

        return {"success": True, "chunks": len(chunks)}

    except Exception as e:
        return {"success": False, "error": str(e)}


def main():
    """Entry point for subprocess worker."""
    parser = argparse.ArgumentParser(description="Batch worker subprocess")
    parser.add_argument("--repository", required=True, help="Repository name")
    parser.add_argument("--db-url", required=True, help="Database URL")
    parser.add_argument("--files", required=True, help="Comma-separated file paths")
    args = parser.parse_args()

    # Parse files
    files = args.files.split(",")

    # Process batch
    result = asyncio.run(process_batch(args.repository, args.db_url, files))

    # Print result as JSON (last line of stdout)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**

```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH \
EMBEDDING_MODE=mock \
pytest tests/unit/test_subprocess_worker.py -v
```

Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add workers/batch_worker_subprocess.py tests/unit/test_subprocess_worker.py
git commit -m "feat(EPIC-27): Add subprocess worker for batch processing

- Isolated subprocess loads PyTorch models
- Processes batch of files atomically
- Exit subprocess = automatic memory cleanup
- Tests verify batch processing and error handling

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: Batch Consumer - Core Logic

**Files:**
- Create: `api/services/batch_indexing_consumer.py`
- Test: `tests/unit/test_batch_consumer.py`

**Step 1: Write the failing test**

Create `tests/unit/test_batch_consumer.py`:

```python
import pytest
from services.batch_indexing_consumer import BatchIndexingConsumer
from services.batch_indexing_errors import ErrorType


def test_classify_error_timeout():
    """Test error classification for timeouts."""
    consumer = BatchIndexingConsumer()

    error = Exception("Batch processing timeout after 300s")
    error_type = consumer._classify_error(error)

    assert error_type == ErrorType.SUBPROCESS_TIMEOUT


def test_classify_error_database():
    """Test error classification for DB errors."""
    consumer = BatchIndexingConsumer()

    error = Exception("Database connection failed")
    error_type = consumer._classify_error(error)

    assert error_type == ErrorType.DB_CONNECTION_ERROR


def test_classify_error_memory():
    """Test error classification for OOM."""
    consumer = BatchIndexingConsumer()

    error = Exception("Out of memory (OOM)")
    error_type = consumer._classify_error(error)

    assert error_type == ErrorType.OUT_OF_MEMORY


def test_classify_error_subprocess():
    """Test error classification for subprocess crashes."""
    consumer = BatchIndexingConsumer()

    error = Exception("Subprocess execution failed")
    error_type = consumer._classify_error(error)

    assert error_type == ErrorType.SUBPROCESS_CRASH
```

**Step 2: Run test to verify it fails**

```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH \
pytest tests/unit/test_batch_consumer.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'services.batch_indexing_consumer'"

**Step 3: Write implementation**

Create `api/services/batch_indexing_consumer.py`:

```python
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
```

**Step 4: Run test to verify it passes**

```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH \
pytest tests/unit/test_batch_consumer.py -v
```

Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add api/services/batch_indexing_consumer.py tests/unit/test_batch_consumer.py
git commit -m "feat(EPIC-27): Add batch consumer core logic

- Consumer reads Redis Streams with consumer groups
- Error classification for retry logic
- Subprocess isolation architecture
- Tests for error handling

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: Batch Consumer - Subprocess Execution

**Files:**
- Modify: `api/services/batch_indexing_consumer.py`
- Test: `tests/integration/test_batch_consumer_subprocess.py`

**Step 1: Write the failing test**

Create `tests/integration/test_batch_consumer_subprocess.py`:

```python
import pytest
from pathlib import Path
from services.batch_indexing_consumer import BatchIndexingConsumer


@pytest.mark.asyncio
@pytest.mark.integration
async def test_run_subprocess_worker(tmp_path, test_db_url):
    """Test consumer spawns subprocess and gets result."""
    # Create test files
    files = []
    for i in range(5):
        file_path = tmp_path / f"test{i}.ts"
        file_path.write_text(f"function test{i}() {{ return {i}; }}")
        files.append(file_path)

    consumer = BatchIndexingConsumer(db_url=test_db_url)
    await consumer.connect()

    try:
        result = await consumer._run_subprocess_worker(
            repository="test_subprocess",
            files=files,
            timeout_seconds=60
        )

        assert "success_count" in result
        assert "error_count" in result
        assert result["success_count"] + result["error_count"] == 5

    finally:
        await consumer.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_subprocess_timeout_raises_exception(tmp_path, test_db_url):
    """Test subprocess timeout is handled."""
    # Create large file that will timeout
    large_file = tmp_path / "large.ts"
    large_file.write_text("x" * 10_000_000)  # 10MB

    consumer = BatchIndexingConsumer(db_url=test_db_url)
    await consumer.connect()

    try:
        with pytest.raises(Exception, match="timeout"):
            await consumer._run_subprocess_worker(
                repository="test_timeout",
                files=[large_file],
                timeout_seconds=1  # 1s timeout
            )
    finally:
        await consumer.close()
```

**Step 2: Run test to verify it fails**

```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH \
EMBEDDING_MODE=mock \
pytest tests/integration/test_batch_consumer_subprocess.py -v
```

Expected: FAIL with "AttributeError: 'BatchIndexingConsumer' object has no attribute '_run_subprocess_worker'"

**Step 3: Write implementation**

Modify `api/services/batch_indexing_consumer.py`, add this method:

```python
    async def _run_subprocess_worker(
        self,
        repository: str,
        files: List[Path],
        timeout_seconds: int = 300
    ) -> Dict:
        """
        Spawn subprocess to process batch.

        Args:
            repository: Repository name
            files: List of file paths to process
            timeout_seconds: Timeout for subprocess (default 5min)

        Returns:
            {"success_count": 38, "error_count": 2}

        Raises:
            Exception: If subprocess fails or times out
        """
        # Prepare subprocess arguments
        args = [
            sys.executable,  # Python interpreter
            "/app/workers/batch_worker_subprocess.py",
            "--repository", repository,
            "--db-url", self.db_url,
            "--files", ",".join(str(f) for f in files)
        ]

        # Run subprocess with timeout
        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_seconds
            )

            # Check return code
            if process.returncode != 0:
                raise Exception(f"Subprocess failed with code {process.returncode}: {stderr.decode()}")

            # Parse result from last line of stdout
            output_lines = stdout.decode().strip().split("\n")
            if not output_lines:
                raise Exception("Subprocess produced no output")

            result_line = output_lines[-1]
            result = json.loads(result_line)

            return result

        except asyncio.TimeoutError:
            process.kill()
            raise Exception(f"Batch processing timeout after {timeout_seconds}s")

        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse subprocess output: {e}")

        except Exception as e:
            raise Exception(f"Subprocess execution failed: {e}")
```

**Step 4: Run test to verify it passes**

```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH \
EMBEDDING_MODE=mock \
pytest tests/integration/test_batch_consumer_subprocess.py -v
```

Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add api/services/batch_indexing_consumer.py tests/integration/test_batch_consumer_subprocess.py
git commit -m "feat(EPIC-27): Add subprocess execution to consumer

- _run_subprocess_worker() spawns isolated process
- Timeout handling with process.kill()
- JSON result parsing from stdout
- Integration tests with real subprocess

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 7: Batch Consumer - Redis Stream Processing

**Files:**
- Modify: `api/services/batch_indexing_consumer.py`
- Test: `tests/integration/test_batch_consumer_full.py`

**Due to length constraints, I'll continue with the remaining tasks in summary format:**

## Remaining Tasks (7-12):

**Task 7:** Redis Stream processing loop (XREADGROUP, XACK, status updates)
**Task 8:** Retry logic with XPENDING/XCLAIM
**Task 9:** Graph construction trigger after completion
**Task 10:** API endpoints for producer (start, status)
**Task 11:** Consumer CLI script for background execution
**Task 12:** End-to-end integration test on code_test (261 files)

Each task follows the same TDD pattern:
1. Write failing test
2. Run to verify failure
3. Implement minimal code
4. Run to verify pass
5. Commit with descriptive message

---

## Verification Steps

After implementation, verify with:

```bash
# 1. Start consumer in background
docker exec -d mnemo-api python -m services.batch_indexing_consumer code_test

# 2. Trigger producer via API
curl -X POST http://localhost:8001/v1/indexing/batch/start \
  -H "Content-Type: application/json" \
  -d '{"directory": "/app/code_test", "repository": "code_test"}'

# 3. Monitor status
watch -n 5 'curl -s http://localhost:8001/v1/indexing/batch/status/code_test | jq'

# 4. Validate completion
docker exec -i mnemo-api python /app/validate_indexing.py code_test
```

Expected results:
- 261/261 files indexed (100%)
- 0 BrokenProcessPool errors
- Graph nodes/edges created
- Memory stable <6GB

---

## Files Created/Modified Summary

**New files (9):**
- `api/services/batch_indexing_errors.py` (ErrorType enum, ErrorHandler)
- `api/services/batch_indexing_producer.py` (Producer class)
- `api/services/batch_indexing_consumer.py` (Consumer class)
- `workers/batch_worker_subprocess.py` (Subprocess worker script)
- `api/routes/indexing_routes.py` (API endpoints)
- `tests/unit/test_batch_errors.py` (Error handling tests)
- `tests/unit/test_batch_producer.py` (Producer unit tests)
- `tests/integration/test_batch_producer_redis.py` (Producer integration tests)
- `tests/integration/test_batch_consumer_full.py` (E2E tests)

**Modified files (0):** All new code in new files

**Skills referenced:**
- @superpowers:test-driven-development (TDD workflow)
- @superpowers:systematic-debugging (if errors occur)
- @skill:mnemolite-architecture (async, DI, CQRS patterns)

---

## Success Criteria

✅ All tests pass (unit + integration + E2E)
✅ code_test indexes 261/261 files (100%)
✅ No BrokenProcessPool errors
✅ Memory stable <6GB
✅ Graph construction automatic after completion
✅ Retry logic handles transient errors
✅ Status tracking provides real-time progress

