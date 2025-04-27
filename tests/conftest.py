import pytest
import logging

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio" 