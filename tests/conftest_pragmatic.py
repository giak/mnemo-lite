"""
Pragmatic test fixtures for MnemoLite.

Focus on real-world testing without mocks, fast feedback, and simplicity.
"""

import sys
import os
import pytest
import pytest_asyncio
import asyncio
import logging
import time
from typing import List, Dict, Any, AsyncGenerator
from datetime import datetime, timezone
import uuid

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

# Configure minimal logging for tests
logging.basicConfig(level=logging.WARNING)  # Less noise during tests

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy import text
from httpx import AsyncClient


# ============================================================================
# DATABASE FIXTURES
# ============================================================================

@pytest_asyncio.fixture(scope="function")
async def test_engine() -> AsyncEngine:
    """
    Create a test database engine with optimized settings for tests.

    Scope: function (isolation between tests)
    """
    test_db_url = os.getenv("TEST_DATABASE_URL")
    if not test_db_url:
        raise ValueError("TEST_DATABASE_URL not set")

    engine = create_async_engine(
        test_db_url,
        echo=False,  # No SQL logging unless debugging
        pool_size=2,  # Smaller pool for tests
        max_overflow=0,  # No overflow needed
        pool_pre_ping=False,  # Tests are fast, skip ping
    )

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def clean_db(test_engine: AsyncEngine) -> AsyncEngine:
    """
    Provide a clean database for each test.

    Truncates all tables before yielding the engine.
    """
    async with test_engine.connect() as conn:
        # Fast truncate with CASCADE
        await conn.execute(text("""
            TRUNCATE TABLE
                events,
                code_chunks,
                nodes,
                edges
            CASCADE
        """))
        await conn.commit()

    yield test_engine


# ============================================================================
# REPOSITORY FIXTURES
# ============================================================================

@pytest_asyncio.fixture
async def event_repo(clean_db: AsyncEngine):
    """Event repository with clean database."""
    from db.repositories.event_repository import EventRepository
    return EventRepository(clean_db)


@pytest_asyncio.fixture
async def code_chunk_repo(clean_db: AsyncEngine):
    """Code chunk repository with clean database."""
    from db.repositories.code_chunk_repository import CodeChunkRepository
    return CodeChunkRepository(clean_db)


# ============================================================================
# SERVICE FIXTURES
# ============================================================================

@pytest_asyncio.fixture(scope="session")
async def mock_embedding_service():
    """
    Mock embedding service for fast tests.

    Use when you don't need real embeddings.
    """
    from services.embedding_service import MockEmbeddingService

    return MockEmbeddingService(
        model_name="mock",
        dimension=768
    )


@pytest_asyncio.fixture(scope="session")
async def real_embedding_service():
    """
    Real embedding service (cached at session level).

    Use sparingly - only when testing real embeddings.
    """
    from dependencies import DualEmbeddingServiceAdapter
    from services.dual_embedding_service import DualEmbeddingService

    dual_service = DualEmbeddingService(
        device="cpu",
        dimension=768,
        cache_size=100  # Small cache for tests
    )

    # Warmup
    await dual_service.generate_embedding("warmup", domain="TEXT")

    # Return adapter for compatibility
    return DualEmbeddingServiceAdapter(dual_service)


# ============================================================================
# API CLIENT FIXTURES
# ============================================================================

@pytest_asyncio.fixture
async def test_client(clean_db: AsyncEngine):
    """
    Test client with real database (no mocks).

    Provides a real FastAPI test client connected to test database.
    """
    from main import app
    from httpx import AsyncClient

    # Override database engine
    app.state.db_engine = clean_db

    # Use mock embeddings for speed (unless testing embeddings specifically)
    from services.embedding_service import MockEmbeddingService
    app.state.embedding_service = MockEmbeddingService(
        model_name="mock",
        dimension=768
    )

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def test_client_with_real_embeddings(clean_db: AsyncEngine, real_embedding_service):
    """
    Test client with real embeddings (slower).

    Use only when testing embedding functionality.
    """
    from main import app
    from httpx import AsyncClient

    app.state.db_engine = clean_db
    app.state.embedding_service = real_embedding_service

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


# ============================================================================
# DATA FIXTURES
# ============================================================================

@pytest.fixture
def sample_events() -> List[Dict[str, Any]]:
    """
    Sample events for testing.

    Returns 5 diverse events covering common use cases.
    """
    return [
        {
            "content": {
                "type": "note",
                "text": "Meeting notes about project planning",
                "tags": ["meeting", "planning"]
            },
            "metadata": {
                "source": "test",
                "priority": "high"
            }
        },
        {
            "content": {
                "type": "code",
                "text": "def calculate_sum(a, b):\n    return a + b",
                "language": "python"
            },
            "metadata": {
                "source": "test",
                "file": "utils.py"
            }
        },
        {
            "content": {
                "type": "task",
                "text": "Review pull request #123",
                "status": "pending"
            },
            "metadata": {
                "source": "test",
                "assignee": "alice"
            }
        },
        {
            "content": {
                "type": "log",
                "text": "System started successfully",
                "level": "info"
            },
            "metadata": {
                "source": "test",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        },
        {
            "content": {
                "type": "error",
                "text": "Connection timeout to database",
                "code": "DB_TIMEOUT"
            },
            "metadata": {
                "source": "test",
                "severity": "critical"
            }
        }
    ]


@pytest.fixture
def sample_python_code() -> str:
    """
    Sample Python code for indexing tests.

    Returns a realistic Python module.
    """
    return '''
"""Sample module for testing."""

import math
from typing import List, Optional


class Calculator:
    """A simple calculator class."""

    def __init__(self, precision: int = 2):
        """Initialize calculator with precision."""
        self.precision = precision

    def add(self, a: float, b: float) -> float:
        """Add two numbers."""
        result = a + b
        return round(result, self.precision)

    def divide(self, a: float, b: float) -> Optional[float]:
        """Divide two numbers safely."""
        if b == 0:
            return None
        return round(a / b, self.precision)


def fibonacci(n: int) -> List[int]:
    """Generate Fibonacci sequence."""
    if n <= 0:
        return []
    elif n == 1:
        return [0]

    sequence = [0, 1]
    for i in range(2, n):
        sequence.append(sequence[-1] + sequence[-2])

    return sequence


# Constants
PI = math.pi
E = math.e
'''


@pytest.fixture
def sample_graph_data() -> Dict[str, Any]:
    """
    Sample graph data for testing.

    Returns nodes and edges for a small graph.
    """
    nodes = [
        {"id": "n1", "type": "function", "label": "main"},
        {"id": "n2", "type": "function", "label": "calculate"},
        {"id": "n3", "type": "function", "label": "validate"},
        {"id": "n4", "type": "class", "label": "Calculator"},
        {"id": "n5", "type": "method", "label": "add"},
    ]

    edges = [
        {"source": "n1", "target": "n2", "type": "calls"},
        {"source": "n1", "target": "n3", "type": "calls"},
        {"source": "n2", "target": "n5", "type": "uses"},
        {"source": "n4", "target": "n5", "type": "contains"},
        {"source": "n3", "target": "n4", "type": "instantiates"},
    ]

    return {"nodes": nodes, "edges": edges}


@pytest.fixture
def random_vector() -> List[float]:
    """Generate a random 768-dimensional vector."""
    import random
    return [random.random() for _ in range(768)]


# ============================================================================
# UTILITY FIXTURES
# ============================================================================

@pytest.fixture
def timer():
    """
    Simple timer for performance tests.

    Usage:
        def test_performance(timer):
            with timer.measure("operation"):
                # do something
            assert timer.elapsed("operation") < 1.0
    """
    class Timer:
        def __init__(self):
            self.timings = {}

        def measure(self, name: str):
            class TimerContext:
                def __init__(self, timer, name):
                    self.timer = timer
                    self.name = name
                    self.start = None

                def __enter__(self):
                    self.start = time.time()
                    return self

                def __exit__(self, *args):
                    elapsed = time.time() - self.start
                    self.timer.timings[self.name] = elapsed

            return TimerContext(self, name)

        def elapsed(self, name: str) -> float:
            return self.timings.get(name, 0.0)

    return Timer()


@pytest.fixture
def assert_similar_vectors():
    """
    Assertion helper for vector similarity.

    Usage:
        assert_similar_vectors(vec1, vec2, threshold=0.95)
    """
    def _assert(vec1: List[float], vec2: List[float], threshold: float = 0.9):
        import numpy as np

        # Convert to numpy arrays
        v1 = np.array(vec1)
        v2 = np.array(vec2)

        # Compute cosine similarity
        similarity = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

        assert similarity >= threshold, f"Vectors not similar enough: {similarity:.3f} < {threshold}"

    return _assert


# ============================================================================
# ASYNC UTILITIES
# ============================================================================

@pytest.fixture
def run_async():
    """
    Helper to run async functions in sync tests.

    Usage:
        def test_something(run_async):
            result = run_async(some_async_function())
    """
    def _run(coro):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro)

    return _run


# ============================================================================
# TEST MARKERS
# ============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers",
        "performance: marks tests as performance tests"
    )
    config.addinivalue_line(
        "markers",
        "real_embeddings: marks tests that need real embeddings"
    )