import sys
import os
import pytest
import pytest_asyncio
import logging

# Add project root (/app inside container) to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)

# Import SQLAlchemy AsyncEngine for database tests
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine


def _ensure_asyncpg_url(url: str) -> str:
    """Convert postgresql:// to postgresql+asyncpg:// for async SQLAlchemy.

    Safe to call with None — returns None unchanged.
    Idempotent — won't double-convert postgresql+asyncpg:// URLs.
    """
    if not url:
        return url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def test_db_url():
    """
    Get TEST_DATABASE_URL for subprocess tests.

    Auto-converts postgresql:// to postgresql+asyncpg:// for async SQLAlchemy.
    """
    test_db_url = os.getenv("TEST_DATABASE_URL")

    if not test_db_url:
        raise ValueError("TEST_DATABASE_URL environment variable not set")

    return _ensure_asyncpg_url(test_db_url)


@pytest_asyncio.fixture(scope="function")
async def test_engine(test_db_url) -> AsyncEngine:
    """
    Create a SQLAlchemy AsyncEngine connected to the test database.

    Uses the test_db_url fixture (already asyncpg-compatible).
    Scope: function (new engine per test for isolation)
    """
    # Create engine
    engine = create_async_engine(
        test_db_url,
        echo=False,  # Set to True for SQL query debugging
        pool_size=5,
        max_overflow=10,
        future=True,
        pool_pre_ping=True,
    )

    yield engine

    # Cleanup: dispose engine after test
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def code_chunk_repo(test_engine):
    """Get CodeChunkRepository with test engine."""
    from db.repositories.code_chunk_repository import CodeChunkRepository
    return CodeChunkRepository(engine=test_engine)


@pytest_asyncio.fixture(scope="session")
async def dual_embedding_service():
    """
    Get DualEmbeddingService for tests.

    Scope: session (reuse models across tests for performance)
    """
    from services.dual_embedding_service import DualEmbeddingService

    service = DualEmbeddingService(
        device="cpu",
        dimension=768
    )

    # Pre-load TEXT model (commonly used)
    # This happens on first call, so do it once at session start
    await service.generate_embedding("warmup text", domain="TEXT")

    return service


# ============================================================================
# PRAGMATIC TEST FIXTURES
# ============================================================================

@pytest_asyncio.fixture(scope="function")
async def clean_db(test_engine):
    """Provide a clean database for each test."""
    from sqlalchemy import text
    async with test_engine.connect() as conn:
        # Fast truncate with CASCADE (EPIC-22: added metrics and alerts tables)
        # Use TRUNCATE only if tables exist (they may not exist in older test DBs)
        await conn.execute(text("""
            DO $$
            BEGIN
                TRUNCATE TABLE events, code_chunks, nodes, edges CASCADE;
                -- EPIC-22 tables (may not exist in all test DBs yet)
                IF EXISTS (SELECT FROM pg_tables WHERE tablename = 'metrics') THEN
                    TRUNCATE TABLE metrics CASCADE;
                END IF;
                IF EXISTS (SELECT FROM pg_tables WHERE tablename = 'alerts') THEN
                    TRUNCATE TABLE alerts CASCADE;
                END IF;
                -- EPIC-24 tables (may not exist in all test DBs yet)
                IF EXISTS (SELECT FROM pg_tables WHERE tablename = 'memories') THEN
                    TRUNCATE TABLE memories CASCADE;
                END IF;
                -- Rich metadata tables (EPIC-27)
                IF EXISTS (SELECT FROM pg_tables WHERE tablename = 'detailed_metadata') THEN
                    TRUNCATE TABLE detailed_metadata CASCADE;
                END IF;
                IF EXISTS (SELECT FROM pg_tables WHERE tablename = 'computed_metrics') THEN
                    TRUNCATE TABLE computed_metrics CASCADE;
                END IF;
                IF EXISTS (SELECT FROM pg_tables WHERE tablename = 'edge_weights') THEN
                    TRUNCATE TABLE edge_weights CASCADE;
                END IF;
            END $$;
        """))
        await conn.commit()
    yield test_engine


@pytest_asyncio.fixture
async def event_repo(clean_db):
    """Event repository with clean database."""
    from db.repositories.event_repository import EventRepository
    return EventRepository(clean_db)


@pytest.fixture
def sample_events():
    """Sample events for testing."""
    from datetime import datetime, timezone
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
def random_vector():
    """Generate a random 768-dimensional vector."""
    import random
    return [random.random() for _ in range(768)]


@pytest.fixture
def timer():
    """Simple timer for performance tests."""
    import time

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


@pytest_asyncio.fixture
async def test_client(clean_db):
    """Test client with real database."""
    from main import app
    from httpx import AsyncClient, ASGITransport

    # Override database engine
    app.state.db_engine = clean_db

    # Use mock embeddings for speed
    from services.embedding_service import MockEmbeddingService
    app.state.embedding_service = MockEmbeddingService(
        model_name="mock",
        dimension=768
    )

    # Create AsyncClient with ASGI transport for FastAPI app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def test_client_with_real_embeddings(clean_db):
    """Test client with real embeddings (for embedding integration tests)."""
    from main import app
    from httpx import AsyncClient, ASGITransport

    # Override database engine
    app.state.db_engine = clean_db

    # Use real dual embedding service for these tests
    from services.dual_embedding_service import DualEmbeddingService
    app.state.embedding_service = DualEmbeddingService(
        device="cpu",
        dimension=768
    )

    # Create AsyncClient with ASGI transport for FastAPI app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def async_engine(clean_db: AsyncEngine) -> AsyncEngine:
    """Alias for clean_db fixture for compatibility with integration tests."""
    return clean_db


@pytest_asyncio.fixture
async def event_repository(clean_db):
    """Event repository with clean database."""
    from db.repositories.event_repository import EventRepository
    return EventRepository(clean_db)


@pytest_asyncio.fixture(scope="session")
async def mock_embedding_service():
    """Mock embedding service for fast tests."""
    from services.embedding_service import MockEmbeddingService
    return MockEmbeddingService(model_name="mock", dimension=768)


@pytest_asyncio.fixture
async def mock_chunking_service():
    """Mock chunking service for testing."""
    from unittest.mock import AsyncMock
    from services.code_chunking_service import CodeChunkingService
    from models.code_chunk_models import CodeChunk, ChunkType

    service = AsyncMock(spec=CodeChunkingService)

    async def mock_chunk_code(source_code, language, file_path, **kwargs):
        return [
            CodeChunk(
                file_path=file_path,
                language=language,
                chunk_type=ChunkType.FUNCTION,
                name="mock_function",
                source_code=source_code[:100],
                start_line=1,
                end_line=10,
                metadata={}
            )
        ]

    service.chunk_code = mock_chunk_code
    return service


@pytest_asyncio.fixture
async def mock_metadata_service():
    """Mock metadata extraction service."""
    from unittest.mock import AsyncMock
    from services.metadata_extractor_service import MetadataExtractorService

    service = AsyncMock(spec=MetadataExtractorService)

    async def mock_extract(chunk, **kwargs):
        return {"complexity": {"cyclomatic": 1}, "calls": [], "imports": []}

    service.extract_metadata = mock_extract
    return service


@pytest_asyncio.fixture
async def mock_graph_service():
    """Mock graph construction service."""
    from unittest.mock import AsyncMock
    from services.graph_construction_service import GraphConstructionService
    from models.graph_models import GraphStats

    service = AsyncMock(spec=GraphConstructionService)

    async def mock_build_graph(repository, language="python"):
        return GraphStats(
            repository=repository,
            total_nodes=0,
            total_edges=0,
            nodes_by_type={},
            edges_by_type={},
            construction_time_seconds=0.0,
            resolution_accuracy=100.0
        )

    service.build_graph_for_repository = mock_build_graph
    return service


@pytest_asyncio.fixture
async def test_chunk_repo(clean_db):
    """Test chunk repository with clean database."""
    from db.repositories.code_chunk_repository import CodeChunkRepository
    return CodeChunkRepository(clean_db)


@pytest_asyncio.fixture
async def redis_client():
    """
    Provide a real Redis client for integration tests.

    Requires Redis server running at redis://redis:6379/0
    Cleans up test keys after each test.
    """
    import redis.asyncio as redis

    client = await redis.from_url(
        "redis://redis:6379/0",
        decode_responses=True
    )

    yield client

    # Cleanup: delete all test keys
    test_patterns = [
        "indexing:jobs:test*",
        "indexing:status:test*"
    ]

    for pattern in test_patterns:
        async for key in client.scan_iter(match=pattern):
            await client.delete(key)

    await client.aclose()
