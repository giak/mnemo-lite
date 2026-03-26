import os
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine


@pytest.fixture(scope="session")
def db_url():
    """Returns PostgreSQL URL from environment or uses default Docker URL."""
    return os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://mnemo:mnemopass@db:5432/mnemolite")


@pytest_asyncio.fixture(scope="function")
async def engine(db_url) -> AsyncEngine:
    """Creates async SQLAlchemy engine for each test."""
    engine = create_async_engine(
        db_url,
        echo=False,
        pool_size=5,
        max_overflow=10,
        future=True,
        pool_pre_ping=True,
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(engine) -> AsyncSession:
    """Creates AsyncSession for each test."""
    async with engine.begin() as conn:
        session = AsyncSession(bind=conn)
        yield session
        await session.close()


@pytest.fixture(scope="session")
def test_fixtures_dir():
    """Returns path to fixtures directory."""
    return os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture(scope="function")
def test_repository():
    """Generates unique repository name for test isolation."""
    import uuid
    return f"test_repo_{uuid.uuid4().hex[:8]}"