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


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(scope="function")
async def test_engine() -> AsyncEngine:
    """
    Create a SQLAlchemy AsyncEngine connected to the test database.

    Uses TEST_DATABASE_URL environment variable.
    Scope: function (new engine per test for isolation)
    """
    test_db_url = os.getenv("TEST_DATABASE_URL")

    if not test_db_url:
        raise ValueError("TEST_DATABASE_URL environment variable not set")

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
