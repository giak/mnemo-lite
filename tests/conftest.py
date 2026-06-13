import sys
import os
import pytest
import pytest_asyncio
import logging

# Force test environment so the ASGI lifespan uses TEST_DATABASE_URL
# instead of DATABASE_URL (production). Without this, the lifespan
# overwrites app.state.db_engine with a production engine, causing
# test isolation failures (e.g. test_pagination seeing production data).
# IMPORTANT: Use os.environ[...] not setdefault — the Docker container
# already sets ENVIRONMENT=development, so setdefault is a no-op!
os.environ["ENVIRONMENT"] = "test"

# Disable rate limiting in tests (accumulates across suite → 429s)
os.environ.setdefault("MNEMO_RATE_LIMIT_ENABLED", "false")

# Clear get_settings cache so AppSettings picks up the test env vars above
from api.core import get_settings
get_settings.cache_clear()

# Add project root (/app inside container) to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)

# Import SQLAlchemy AsyncEngine for database tests
# Guard: skip if sqlalchemy not installed (e.g. running script-only tests locally)
try:
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
except ImportError:
    create_async_engine = None
    AsyncEngine = None

# Tables to TRUNCATE for test isolation.
# Shared between _clean_test_db_at_session_start and clean_db to avoid
# divergence — if you add a table here, both fixtures will cover it.
_CORE_TABLES = ("events", "code_chunks", "nodes", "edges")
_OPTIONAL_TABLES = ("metrics", "alerts", "memories", "detailed_metadata", "computed_metrics", "edge_weights")


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
def event_loop():
    """Create a session-scoped event loop for async fixtures.

    pytest-asyncio 0.21.1 requires a session-scoped event_loop fixture
    for any session-scoped async fixtures (e.g. _clean_test_db_at_session_start).
    Without this, pytest raises ScopeMismatch because the default event_loop
    fixture is function-scoped.
    """
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_db_url():
    """
    Get TEST_DATABASE_URL for subprocess tests.

    Auto-converts postgresql:// to postgresql+asyncpg:// for async SQLAlchemy.
    """
    test_db_url = get_settings().TEST_DATABASE_URL

    if not test_db_url:
        raise ValueError("TEST_DATABASE_URL environment variable not set")

    return _ensure_asyncpg_url(test_db_url)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _clean_test_db_at_session_start():
    """TRUNCATE the test DB once before the entire suite starts.

    This is a safety net against stale data left by previous crashed
    test runs. Without it, leftover events/code_chunks/etc. cause
    test isolation failures (e.g. test_pagination seeing 800+ events
    instead of 10).

    The function-scoped clean_db fixture handles per-test isolation,
    but it can only truncate tables BEFORE each test — it cannot
    remove data that was left behind by a previous pytest invocation
    that crashed or was killed mid-suite.

    autouse=True ensures this always runs, even if no test explicitly
    requests it. scope="session" means it runs exactly once.

    Skip if sqlalchemy is not installed (e.g. running contract tests
    that don't need a database).
    """
    if create_async_engine is None:
        return  # sqlalchemy not available — skip DB cleanup

    # Also skip if TEST_DATABASE_URL is not set
    try:
        from api.core import get_settings
        test_db_url = get_settings().TEST_DATABASE_URL
        if not test_db_url:
            return
    except Exception:
        return

    from sqlalchemy import text
    from sqlalchemy.exc import ProgrammingError

    engine = create_async_engine(test_db_url, pool_size=2, max_overflow=0)
    try:
        # Core tables — always exist
        async with engine.connect() as conn:
            await conn.execute(text(f'TRUNCATE TABLE {", ".join(_CORE_TABLES)} CASCADE'))
            await conn.commit()
        # Optional tables — may not exist yet (e.g. before migrations run)
        for table in _OPTIONAL_TABLES:
            try:
                async with engine.connect() as conn:
                    await conn.execute(text(f'TRUNCATE TABLE {table} CASCADE'))
                    await conn.commit()
            except ProgrammingError:
                pass  # Table doesn't exist yet — safe to ignore
    finally:
        await engine.dispose()


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
        text_dimension=1024, code_dimension=768
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
    """Provide a clean database for each test.

    Uses separate transactions for core and optional tables.
    This is critical: if an optional table TRUNCATE fails (table doesn't
    exist), PostgreSQL aborts the entire transaction — which would also
    roll back the core table TRUNCATEs, leaving stale data in the DB
    and causing test isolation failures.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import ProgrammingError
    # Core tables — always exist, TRUNCATE in their own transaction
    # so failures in optional tables can't roll back these TRUNCATEs.
    async with test_engine.connect() as conn:
        await conn.execute(text(f'TRUNCATE TABLE {", ".join(_CORE_TABLES)} CASCADE'))
        await conn.commit()
    # Optional tables — may not exist in all test DBs;
    # each gets its own transaction so a failure doesn't affect others.
    for table in _OPTIONAL_TABLES:
        try:
            async with test_engine.connect() as conn:
                await conn.execute(text(f'TRUNCATE TABLE {table} CASCADE'))
                await conn.commit()
        except ProgrammingError:
            pass  # Table doesn't exist yet — safe to ignore
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
    """Test client with real database.

    Uses FastAPI dependency_overrides to guarantee all routes use
    the test engine and mock embedding service, regardless of what
    the lifespan does to app.state. Also sets app.state for code
    that accesses it directly (e.g. MetricsMiddleware).
    """
    from main import app
    from httpx import AsyncClient, ASGITransport
    from dependencies import get_db_engine, get_embedding_service
    from services.embedding_service import MockEmbeddingService

    mock_service = MockEmbeddingService(model_name="mock", dimension=768)

    # Set app.state for middleware and other direct access
    app.state.db_engine = clean_db
    app.state.embedding_service = mock_service

    # Override FastAPI dependencies to guarantee test engine/service
    # are used by all routes. This is the idiomatic FastAPI testing
    # pattern and prevents the lifespan or other code from accidentally
    # using a production engine.
    def override_get_db_engine():
        return clean_db

    def override_get_embedding_service():
        return mock_service

    # Save existing overrides to restore later (avoids wiping overrides
    # set by other fixtures or conftest layers).
    _saved_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db_engine] = override_get_db_engine
    app.dependency_overrides[get_embedding_service] = override_get_embedding_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Re-override app.state after lifespan (defensive for direct access)
            app.state.db_engine = clean_db
            app.state.embedding_service = mock_service
            yield client
    finally:
        app.dependency_overrides = _saved_overrides


@pytest_asyncio.fixture
async def test_client_with_real_embeddings(clean_db):
    """Test client with real embeddings (for embedding integration tests)."""
    from main import app
    from httpx import AsyncClient, ASGITransport
    from dependencies import get_db_engine, get_embedding_service, DualEmbeddingServiceAdapter
    from services.dual_embedding_service import DualEmbeddingService

    dual_service = DualEmbeddingService(device="cpu", text_dimension=1024, code_dimension=768)
    adapter = DualEmbeddingServiceAdapter(dual_service)

    # Set app.state for middleware and other direct access
    app.state.db_engine = clean_db
    app.state.embedding_service = adapter

    # Override FastAPI dependencies for guaranteed test isolation
    def override_get_db_engine():
        return clean_db

    def override_get_embedding_service():
        return adapter

    # Save existing overrides to restore later
    _saved_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db_engine] = override_get_db_engine
    app.dependency_overrides[get_embedding_service] = override_get_embedding_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            app.state.db_engine = clean_db
            yield client
    finally:
        app.dependency_overrides = _saved_overrides


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
