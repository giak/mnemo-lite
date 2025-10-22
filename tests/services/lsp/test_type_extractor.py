"""
Unit tests for TypeExtractorService.

Story: EPIC-13 Story 13.2 - Type Metadata Extraction Service
Author: Claude Code
Date: 2025-10-22
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from services.lsp import PyrightLSPClient, TypeExtractorService, LSPError
from models.code_chunk_models import CodeChunk, ChunkType


# Mark all tests as async
pytestmark = pytest.mark.anyio


# ============================================
# Unit Tests (Mocked LSP)
# ============================================

@pytest.fixture
def mock_lsp_client():
    """Create a mock LSP client."""
    client = AsyncMock(spec=PyrightLSPClient)
    client.hover = AsyncMock()
    return client


@pytest.fixture
def type_extractor(mock_lsp_client):
    """Create TypeExtractorService with mocked LSP client."""
    return TypeExtractorService(lsp_client=mock_lsp_client)


async def test_type_extractor_initialization():
    """Test TypeExtractorService can be initialized."""
    # With LSP client
    client = Mock(spec=PyrightLSPClient)
    extractor = TypeExtractorService(lsp_client=client)
    assert extractor.lsp == client

    # Without LSP client (graceful degradation)
    extractor = TypeExtractorService(lsp_client=None)
    assert extractor.lsp is None


async def test_extract_function_types(type_extractor, mock_lsp_client):
    """Extract return type and param types from function."""
    # Mock hover response (Pyright format)
    mock_lsp_client.hover.return_value = "(function) process_user: (user_id: int, name: str) -> User"

    chunk = CodeChunk(
        file_path="/app/test.py",
        language="python",
        chunk_type=ChunkType.FUNCTION,
        name="process_user",
        source_code="def process_user(user_id: int, name: str) -> User: ...",
        start_line=10,
        end_line=12,
        metadata={}
    )

    metadata = await type_extractor.extract_type_metadata(
        "/app/test.py",
        "def process_user(user_id: int, name: str) -> User: ...",
        chunk
    )

    # Verify extracted types
    assert metadata["return_type"] == "User"
    assert metadata["param_types"] == {"user_id": "int", "name": "str"}
    assert "process_user" in metadata["signature"]
    assert "User" in metadata["signature"]

    # Verify LSP was called correctly
    mock_lsp_client.hover.assert_called_once_with(
        file_path="/app/test.py",
        source_code="def process_user(user_id: int, name: str) -> User: ...",
        line=10,
        character=4
    )


async def test_extract_method_types(type_extractor, mock_lsp_client):
    """Extract method types (with self parameter)."""
    mock_lsp_client.hover.return_value = "(method) Calculator.add: (self, a: int, b: int) -> int"

    chunk = CodeChunk(
        file_path="/app/calc.py",
        language="python",
        chunk_type=ChunkType.METHOD,
        name="add",
        source_code="def add(self, a: int, b: int) -> int: ...",
        start_line=5,
        end_line=7,
        metadata={}
    )

    metadata = await type_extractor.extract_type_metadata(
        "/app/calc.py",
        "class Calculator:\n    def add(self, a: int, b: int) -> int: ...",
        chunk
    )

    assert metadata["return_type"] == "int"
    # Note: "self" may or may not be included by Pyright (implementation detail)
    # The important thing is that typed parameters are extracted
    assert metadata["param_types"]["a"] == "int"
    assert metadata["param_types"]["b"] == "int"
    assert len(metadata["param_types"]) >= 2  # At least a and b


async def test_extract_no_return_type(type_extractor, mock_lsp_client):
    """Extract function without return type annotation."""
    mock_lsp_client.hover.return_value = "(function) log_message: (msg: str)"

    chunk = CodeChunk(
        file_path="/app/logger.py",
        language="python",
        chunk_type=ChunkType.FUNCTION,
        name="log_message",
        source_code="def log_message(msg: str): ...",
        start_line=0,
        end_line=2,
        metadata={}
    )

    metadata = await type_extractor.extract_type_metadata(
        "/app/logger.py",
        "def log_message(msg: str): ...",
        chunk
    )

    assert metadata["return_type"] is None  # No return type
    assert metadata["param_types"] == {"msg": "str"}


async def test_extract_complex_types(type_extractor, mock_lsp_client):
    """Extract complex generic types (List, Dict, Optional)."""
    mock_lsp_client.hover.return_value = (
        "(function) process_items: (items: List[int], config: Dict[str, Any]) -> Optional[List[User]]"
    )

    chunk = CodeChunk(
        file_path="/app/processor.py",
        language="python",
        chunk_type=ChunkType.FUNCTION,
        name="process_items",
        source_code="def process_items(items: List[int], config: Dict[str, Any]) -> Optional[List[User]]: ...",
        start_line=0,
        end_line=2,
        metadata={}
    )

    metadata = await type_extractor.extract_type_metadata(
        "/app/processor.py",
        "def process_items(...): ...",
        chunk
    )

    assert metadata["return_type"] == "Optional[List[User]]"
    assert metadata["param_types"]["items"] == "List[int]"
    assert metadata["param_types"]["config"] == "Dict[str, Any]"


async def test_extract_default_values(type_extractor, mock_lsp_client):
    """Extract param types with default values."""
    mock_lsp_client.hover.return_value = "(function) greet: (name: str, count: int = 1) -> str"

    chunk = CodeChunk(
        file_path="/app/greet.py",
        language="python",
        chunk_type=ChunkType.FUNCTION,
        name="greet",
        source_code="def greet(name: str, count: int = 1) -> str: ...",
        start_line=0,
        end_line=2,
        metadata={}
    )

    metadata = await type_extractor.extract_type_metadata(
        "/app/greet.py",
        "def greet(name: str, count: int = 1) -> str: ...",
        chunk
    )

    # Default value should be stripped from type
    assert metadata["param_types"]["count"] == "int"  # Not "int = 1"
    assert metadata["param_types"]["name"] == "str"


async def test_graceful_degradation_no_lsp_client():
    """Gracefully degrade when LSP client is None."""
    extractor = TypeExtractorService(lsp_client=None)

    chunk = CodeChunk(
        file_path="/app/test.py",
        language="python",
        chunk_type=ChunkType.FUNCTION,
        name="foo",
        source_code="def foo(): ...",
        start_line=0,
        end_line=1,
        metadata={}
    )

    metadata = await extractor.extract_type_metadata(
        "/app/test.py",
        "def foo(): ...",
        chunk
    )

    # Should return empty metadata (graceful degradation)
    assert metadata["return_type"] is None
    assert metadata["param_types"] == {}
    assert metadata["signature"] is None


async def test_graceful_degradation_lsp_error(type_extractor, mock_lsp_client):
    """Gracefully degrade when LSP query fails."""
    # Mock LSP to raise error
    mock_lsp_client.hover.side_effect = LSPError("Server crashed")

    chunk = CodeChunk(
        file_path="/app/test.py",
        language="python",
        chunk_type=ChunkType.FUNCTION,
        name="foo",
        source_code="def foo(): ...",
        start_line=0,
        end_line=1,
        metadata={}
    )

    metadata = await type_extractor.extract_type_metadata(
        "/app/test.py",
        "def foo(): ...",
        chunk
    )

    # Should return empty metadata (not raise exception)
    assert metadata["return_type"] is None
    assert metadata["param_types"] == {}


async def test_graceful_degradation_no_hover_info(type_extractor, mock_lsp_client):
    """Gracefully degrade when hover returns None."""
    mock_lsp_client.hover.return_value = None

    chunk = CodeChunk(
        file_path="/app/test.py",
        language="python",
        chunk_type=ChunkType.FUNCTION,
        name="foo",
        source_code="def foo(): ...",
        start_line=0,
        end_line=1,
        metadata={}
    )

    metadata = await type_extractor.extract_type_metadata(
        "/app/test.py",
        "def foo(): ...",
        chunk
    )

    # Should return empty metadata
    assert metadata["return_type"] is None
    assert metadata["param_types"] == {}


async def test_graceful_degradation_no_start_line(type_extractor, mock_lsp_client):
    """Gracefully degrade when chunk has no start_line."""
    chunk = CodeChunk(
        file_path="/app/test.py",
        language="python",
        chunk_type=ChunkType.FUNCTION,
        name="foo",
        source_code="def foo(): ...",
        start_line=None,  # No line info
        end_line=None,
        metadata={}
    )

    metadata = await type_extractor.extract_type_metadata(
        "/app/test.py",
        "def foo(): ...",
        chunk
    )

    # Should return empty metadata (no LSP query made)
    assert metadata["return_type"] is None
    assert metadata["param_types"] == {}

    # LSP should NOT be called
    mock_lsp_client.hover.assert_not_called()


async def test_parse_class_signature(type_extractor, mock_lsp_client):
    """Parse class hover (no params, no return type)."""
    mock_lsp_client.hover.return_value = "(class) User"

    chunk = CodeChunk(
        file_path="/app/models.py",
        language="python",
        chunk_type=ChunkType.CLASS,
        name="User",
        source_code="class User: ...",
        start_line=0,
        end_line=5,
        metadata={}
    )

    metadata = await type_extractor.extract_type_metadata(
        "/app/models.py",
        "class User: ...",
        chunk
    )

    # Class has no return type or params
    assert metadata["signature"] == "User"
    assert metadata["return_type"] is None
    assert metadata["param_types"] == {}


async def test_parse_variable_signature(type_extractor, mock_lsp_client):
    """Parse variable hover."""
    mock_lsp_client.hover.return_value = "(variable) count: int"

    chunk = CodeChunk(
        file_path="/app/config.py",
        language="python",
        chunk_type=ChunkType.MODULE,
        name="count",
        source_code="count = 42",
        start_line=0,
        end_line=1,
        metadata={}
    )

    metadata = await type_extractor.extract_type_metadata(
        "/app/config.py",
        "count = 42",
        chunk
    )

    # Variable type stored in signature (no return type or params)
    assert "count" in metadata["signature"]
    assert "int" in metadata["signature"]


# ============================================
# Integration Tests (Real Pyright)
# ============================================

@pytest.mark.skipif(
    True,  # Skip by default (environment-sensitive)
    reason="Requires pyright-langserver installed (integration test)"
)
async def test_extract_function_types_real():
    """Extract types from real Pyright LSP (INTEGRATION TEST)."""
    client = PyrightLSPClient()
    await client.start()

    try:
        extractor = TypeExtractorService(lsp_client=client)

        source = '''def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
'''

        chunk = CodeChunk(
            file_path="/tmp/test.py",
            language="python",
            chunk_type=ChunkType.FUNCTION,
            name="add",
            source_code=source,
            start_line=0,
            end_line=3,
            metadata={}
        )

        metadata = await extractor.extract_type_metadata(
            "/tmp/test.py",
            source,
            chunk
        )

        # Verify extracted types
        assert metadata["return_type"] == "int"
        assert "a" in metadata["param_types"]
        assert metadata["param_types"]["a"] == "int"
        assert metadata["param_types"]["b"] == "int"
        assert "add" in metadata["signature"]

    finally:
        await client.shutdown()


@pytest.mark.skipif(
    True,  # Skip by default (environment-sensitive)
    reason="Requires pyright-langserver installed (integration test)"
)
async def test_extract_class_method_types_real():
    """Extract method types from real Pyright LSP (INTEGRATION TEST)."""
    client = PyrightLSPClient()
    await client.start()

    try:
        extractor = TypeExtractorService(lsp_client=client)

        source = '''class Calculator:
    def multiply(self, x: float, y: float) -> float:
        """Multiply two numbers."""
        return x * y
'''

        chunk = CodeChunk(
            file_path="/tmp/test.py",
            language="python",
            chunk_type=ChunkType.METHOD,
            name="multiply",
            source_code=source,
            start_line=1,  # Method starts at line 1
            end_line=4,
            metadata={}
        )

        metadata = await extractor.extract_type_metadata(
            "/tmp/test.py",
            source,
            chunk
        )

        # Verify extracted types
        assert metadata["return_type"] == "float"
        assert "self" in metadata["param_types"]
        assert metadata["param_types"]["x"] == "float"
        assert metadata["param_types"]["y"] == "float"

    finally:
        await client.shutdown()


@pytest.mark.skipif(
    True,  # Skip by default
    reason="Requires pyright-langserver installed"
)
async def test_extract_complex_types_real():
    """Extract complex generic types from real Pyright LSP (INTEGRATION TEST)."""
    client = PyrightLSPClient()
    await client.start()

    try:
        extractor = TypeExtractorService(lsp_client=client)

        source = '''from typing import List, Dict, Optional

def process_users(users: List[str], config: Dict[str, int]) -> Optional[List[int]]:
    """Process a list of users."""
    return [1, 2, 3]
'''

        chunk = CodeChunk(
            file_path="/tmp/test.py",
            language="python",
            chunk_type=ChunkType.FUNCTION,
            name="process_users",
            source_code=source,
            start_line=2,  # Function starts at line 2
            end_line=5,
            metadata={}
        )

        metadata = await extractor.extract_type_metadata(
            "/tmp/test.py",
            source,
            chunk
        )

        # Verify complex types extracted
        assert "Optional" in metadata["return_type"]
        assert "List" in metadata["return_type"]
        assert "List[str]" in metadata["param_types"]["users"]
        assert "Dict[str, int]" in metadata["param_types"]["config"]

    finally:
        await client.shutdown()
