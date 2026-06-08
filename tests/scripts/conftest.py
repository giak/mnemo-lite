"""
Local conftest for tests/scripts/ — overrides DB-dependent fixtures
from the root conftest.py so these tests can run without a database.

The root conftest.py has:
- test_db_url (requires TEST_DATABASE_URL env var)
- _clean_test_db_at_session_start (autouse, needs DB)
- clean_db, test_engine, etc.

These overrides allow `pytest tests/scripts/` to work outside Docker.
"""

import pytest


# Override anyio_backend locally
@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


# Override DB-dependent fixtures from root conftest with safe stubs
# so they don't raise when TEST_DATABASE_URL is unset.
# NOTE: These must be non-async to avoid ScopeMismatch with
# pytest-asyncio 0.21.x's function-scoped event_loop.

@pytest.fixture(scope="session")
def test_db_url():
    """Stub: skip DB-dependent tests when no database is available."""
    pytest.skip("TEST_DATABASE_URL not set — script tests don't need a DB")


@pytest.fixture(scope="session", autouse=True)
def _clean_test_db_at_session_start():
    """Stub: no-op for script tests that don't use a database."""
    yield


@pytest.fixture(scope="function")
def test_engine():
    """Stub: skip if actually requested by a non-script test."""
    pytest.skip("No database available for script tests")


@pytest.fixture(scope="function")
def clean_db():
    """Stub: skip if actually requested by a non-script test."""
    pytest.skip("No database available for script tests")
