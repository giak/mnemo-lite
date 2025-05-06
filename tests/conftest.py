import sys
import os
import pytest
import logging

# Add project root (/app inside container) to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
