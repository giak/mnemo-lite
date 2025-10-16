"""
Unit tests for MetadataExtractorService (EPIC-06 Phase 1 Story 3).

Tests metadata extraction including:
- Signature, parameters, returns, decorators
- Docstrings
- Complexity metrics
- Imports and calls
"""

import ast

import pytest

from services.metadata_extractor_service import MetadataExtractorService


@pytest.fixture
def metadata_service():
    """Get MetadataExtractorService instance."""
    return MetadataExtractorService()


# Test 1: Signature extraction - simple function

@pytest.mark.asyncio
async def test_extract_signature_simple_function(metadata_service):
    """Test signature extraction for simple function."""
    source_code = """
def calculate_total(items):
    return sum(items)
"""

    tree = ast.parse(source_code)
    node = tree.body[0]  # FunctionDef

    metadata = await metadata_service.extract_metadata(source_code, node, tree)

    assert metadata["signature"] is not None
    assert "calculate_total" in metadata["signature"]
    assert metadata["parameters"] == ["items"]
    assert metadata["returns"] is None  # No type hint
    assert metadata["decorators"] == []


# Test 2: Signature extraction - with type hints

@pytest.mark.asyncio
async def test_extract_signature_with_type_hints(metadata_service):
    """Test signature extraction with type annotations."""
    source_code = """
def calculate_total(items: list[float]) -> float:
    return sum(items)
"""

    tree = ast.parse(source_code)
    node = tree.body[0]

    metadata = await metadata_service.extract_metadata(source_code, node, tree)

    assert metadata["parameters"] == ["items"]
    assert metadata["returns"] == "float"


# Test 3: Signature extraction - multiple parameters

@pytest.mark.asyncio
async def test_extract_parameters_multiple(metadata_service):
    """Test extraction of multiple parameters."""
    source_code = """
def add_numbers(a: int, b: int, c: int = 0) -> int:
    return a + b + c
"""

    tree = ast.parse(source_code)
    node = tree.body[0]

    metadata = await metadata_service.extract_metadata(source_code, node, tree)

    assert metadata["parameters"] == ["a", "b", "c"]
    assert metadata["returns"] == "int"


# Test 4: Decorators extraction - single

@pytest.mark.asyncio
async def test_extract_decorators_single(metadata_service):
    """Test extraction of single decorator."""
    source_code = """
@staticmethod
def helper():
    pass
"""

    tree = ast.parse(source_code)
    node = tree.body[0]

    metadata = await metadata_service.extract_metadata(source_code, node, tree)

    assert metadata["decorators"] == ["staticmethod"]


# Test 5: Decorators extraction - multiple

@pytest.mark.asyncio
async def test_extract_decorators_multiple(metadata_service):
    """Test extraction of multiple decorators."""
    source_code = """
@staticmethod
@cached_property
@validate_input
def complex_function():
    pass
"""

    tree = ast.parse(source_code)
    node = tree.body[0]

    metadata = await metadata_service.extract_metadata(source_code, node, tree)

    assert len(metadata["decorators"]) == 3
    assert "staticmethod" in metadata["decorators"]
    assert "cached_property" in metadata["decorators"]
    assert "validate_input" in metadata["decorators"]


# Test 6: Docstring extraction - Google style

@pytest.mark.asyncio
async def test_extract_docstring_google_style(metadata_service):
    """Test docstring extraction (Google style)."""
    source_code = '''
def calculate_total(items):
    """Calculate total price from items list.

    Args:
        items: List of items with prices

    Returns:
        Total price as float
    """
    return sum(item.price for item in items)
'''

    tree = ast.parse(source_code)
    node = tree.body[0]

    metadata = await metadata_service.extract_metadata(source_code, node, tree)

    assert metadata["docstring"] is not None
    assert "Calculate total price" in metadata["docstring"]
    assert "Args:" in metadata["docstring"]
    assert "Returns:" in metadata["docstring"]


# Test 7: Docstring extraction - none

@pytest.mark.asyncio
async def test_extract_docstring_none(metadata_service):
    """Test that missing docstring returns None."""
    source_code = """
def no_docstring():
    return 42
"""

    tree = ast.parse(source_code)
    node = tree.body[0]

    metadata = await metadata_service.extract_metadata(source_code, node, tree)

    assert metadata["docstring"] is None


# Test 8: Complexity extraction - cyclomatic

@pytest.mark.asyncio
async def test_extract_complexity_cyclomatic(metadata_service):
    """Test cyclomatic complexity extraction."""
    source_code = """
def complex_function(x):
    if x > 0:
        if x > 10:
            return "large"
        else:
            return "small"
    else:
        return "negative"
"""

    tree = ast.parse(source_code)
    node = tree.body[0]

    metadata = await metadata_service.extract_metadata(source_code, node, tree)

    assert "complexity" in metadata
    assert metadata["complexity"]["cyclomatic"] is not None
    assert metadata["complexity"]["cyclomatic"] >= 3  # 3 decision points


# Test 9: Complexity extraction - lines of code

@pytest.mark.asyncio
async def test_extract_complexity_lines_of_code(metadata_service):
    """Test LOC extraction."""
    source_code = """
def multiline_function():
    line1 = 1
    line2 = 2
    line3 = 3
    line4 = 4
    return line1 + line2 + line3 + line4
"""

    tree = ast.parse(source_code)
    node = tree.body[0]

    metadata = await metadata_service.extract_metadata(source_code, node, tree)

    assert "complexity" in metadata
    assert metadata["complexity"]["lines_of_code"] > 0
    # Function has ~6 lines (def + 5 body lines)
    assert metadata["complexity"]["lines_of_code"] >= 5


# Test 10: Imports extraction

@pytest.mark.asyncio
async def test_extract_imports_used_in_function(metadata_service):
    """Test extraction of imports used in function."""
    source_code = """
from typing import List
import math

def process_numbers(numbers: List[float]) -> float:
    return math.sqrt(sum(numbers))
"""

    tree = ast.parse(source_code)
    node = tree.body[2]  # FunctionDef (after 2 import statements)

    metadata = await metadata_service.extract_metadata(source_code, node, tree)

    assert "imports" in metadata
    # Should capture 'math' (used) and potentially 'List' (used in annotation)
    assert "math" in metadata["imports"] or "typing.List" in metadata["imports"]


# Test 11: Calls extraction - simple

@pytest.mark.asyncio
async def test_extract_calls_simple(metadata_service):
    """Test extraction of simple function calls."""
    source_code = """
def calculator(items):
    total = sum(items)
    result = abs(total)
    return result
"""

    tree = ast.parse(source_code)
    node = tree.body[0]

    metadata = await metadata_service.extract_metadata(source_code, node, tree)

    assert "calls" in metadata
    assert "sum" in metadata["calls"]
    assert "abs" in metadata["calls"]


# Test 12: Calls extraction - method calls

@pytest.mark.asyncio
async def test_extract_calls_method_calls(metadata_service):
    """Test extraction of method calls."""
    source_code = """
def process_data(data):
    cleaned = data.strip()
    upper = cleaned.upper()
    result = upper.split()
    return result
"""

    tree = ast.parse(source_code)
    node = tree.body[0]

    metadata = await metadata_service.extract_metadata(source_code, node, tree)

    assert "calls" in metadata
    # Should capture method names
    assert any("strip" in call for call in metadata["calls"])
    assert any("upper" in call for call in metadata["calls"])
    assert any("split" in call for call in metadata["calls"])


# Test 13: Class metadata extraction

@pytest.mark.asyncio
async def test_extract_class_metadata(metadata_service):
    """Test metadata extraction for class."""
    source_code = """
class Calculator:
    '''Calculator class for basic operations.'''

    def add(self, a, b):
        return a + b
"""

    tree = ast.parse(source_code)
    node = tree.body[0]  # ClassDef

    metadata = await metadata_service.extract_metadata(source_code, node, tree)

    assert metadata["signature"] is not None
    assert "Calculator" in metadata["signature"]
    assert metadata["docstring"] == "Calculator class for basic operations."


# Test 14: Async function

@pytest.mark.asyncio
async def test_extract_async_function_metadata(metadata_service):
    """Test metadata extraction for async function."""
    source_code = """
async def fetch_data(url: str) -> dict:
    '''Fetch data from URL asynchronously.'''
    return {"data": "example"}
"""

    tree = ast.parse(source_code)
    node = tree.body[0]  # AsyncFunctionDef

    metadata = await metadata_service.extract_metadata(source_code, node, tree)

    assert metadata["signature"] is not None
    assert "async def fetch_data" in metadata["signature"]
    assert metadata["parameters"] == ["url"]
    assert metadata["returns"] == "dict"
    assert "Fetch data" in metadata["docstring"]


# Test 15: Graceful degradation - non-Python

@pytest.mark.asyncio
async def test_graceful_degradation_non_python(metadata_service):
    """Test that non-Python language returns basic metadata."""
    # JavaScript code (won't parse as Python AST)
    source_code = """
function calculateTotal(items) {
    return items.reduce((sum, item) => sum + item.price, 0);
}
"""

    # Create empty AST node for testing
    tree = ast.parse("")
    node = ast.FunctionDef(name="dummy", args=ast.arguments(args=[], posonlyargs=[], kwonlyargs=[], kw_defaults=[], defaults=[]), body=[], decorator_list=[])

    metadata = await metadata_service.extract_metadata(source_code, node, tree, language="javascript")

    # Should return basic structure
    assert "signature" in metadata
    assert "parameters" in metadata
    assert "complexity" in metadata
    assert metadata["signature"] is None  # No extraction for non-Python
    assert metadata["parameters"] == []
