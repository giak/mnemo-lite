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
