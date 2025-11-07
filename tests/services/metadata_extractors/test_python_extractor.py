"""
Tests for Python metadata extractor.
"""

import pytest
from tree_sitter_language_pack import get_parser
from services.metadata_extractors.python_extractor import PythonMetadataExtractor


@pytest.fixture
def python_extractor():
    """Create a PythonMetadataExtractor instance."""
    return PythonMetadataExtractor()


@pytest.fixture
def python_parser():
    """Create a tree-sitter Python parser."""
    return get_parser("python")


@pytest.mark.asyncio
async def test_extract_basic_import(python_extractor, python_parser):
    """Test extraction of basic import statement."""
    source_code = "import os"
    tree = python_parser.parse(bytes(source_code, "utf8"))

    imports = await python_extractor.extract_imports(tree, source_code)

    assert imports == ["os"]


@pytest.mark.asyncio
async def test_extract_from_import(python_extractor, python_parser):
    """Test extraction of from...import statement."""
    source_code = "from pathlib import Path"
    tree = python_parser.parse(bytes(source_code, "utf8"))

    imports = await python_extractor.extract_imports(tree, source_code)

    assert imports == ["pathlib.Path"]


@pytest.mark.asyncio
async def test_extract_from_import_multiple(python_extractor, python_parser):
    """Test extraction of from...import with multiple names."""
    source_code = "from typing import List, Dict, Optional"
    tree = python_parser.parse(bytes(source_code, "utf8"))

    imports = await python_extractor.extract_imports(tree, source_code)

    assert imports == ["typing.List", "typing.Dict", "typing.Optional"]


@pytest.mark.asyncio
async def test_extract_from_import_alias(python_extractor, python_parser):
    """Test extraction of import with alias."""
    source_code = "from datetime import datetime as dt"
    tree = python_parser.parse(bytes(source_code, "utf8"))

    imports = await python_extractor.extract_imports(tree, source_code)

    assert imports == ["datetime.datetime"]


@pytest.mark.asyncio
async def test_extract_basic_call(python_extractor, python_parser):
    """Test extraction of basic function call."""
    source_code = """
def my_function():
    result = calculate_total()
    return result
"""
    tree = python_parser.parse(bytes(source_code, "utf8"))
    function_node = tree.root_node.children[0]  # function_definition

    calls = await python_extractor.extract_calls(function_node, source_code)

    assert "calculate_total" in calls


@pytest.mark.asyncio
async def test_extract_method_call(python_extractor, python_parser):
    """Test extraction of method call."""
    source_code = """
def my_function():
    result = service.fetch_data()
    return result
"""
    tree = python_parser.parse(bytes(source_code, "utf8"))
    function_node = tree.root_node.children[0]

    calls = await python_extractor.extract_calls(function_node, source_code)

    assert "service.fetch_data" in calls


@pytest.mark.asyncio
async def test_extract_chained_call(python_extractor, python_parser):
    """Test extraction of chained method calls."""
    source_code = """
def my_function():
    result = database.session.query(User).all()
    return result
"""
    tree = python_parser.parse(bytes(source_code, "utf8"))
    function_node = tree.root_node.children[0]

    calls = await python_extractor.extract_calls(function_node, source_code)

    assert "database.session.query" in calls


@pytest.mark.asyncio
async def test_extract_metadata_with_decorator(python_extractor, python_parser):
    """Test metadata extraction includes decorator information."""
    source_code = """
@dataclass
class User:
    name: str
    age: int
"""
    tree = python_parser.parse(bytes(source_code, "utf8"))
    class_node = tree.root_node.children[0]  # decorated_definition

    metadata = await python_extractor.extract_metadata(source_code, class_node, tree)

    assert "decorators" in metadata
    assert "dataclass" in metadata["decorators"]


@pytest.mark.asyncio
async def test_extract_metadata_with_property_decorator(python_extractor, python_parser):
    """Test extraction of @property decorator."""
    source_code = """
class MyClass:
    @property
    def value(self):
        return self._value
"""
    tree = python_parser.parse(bytes(source_code, "utf8"))
    class_node = tree.root_node.children[0]

    metadata = await python_extractor.extract_metadata(source_code, class_node, tree)

    assert "decorators" in metadata
    assert "property" in metadata["decorators"]


@pytest.mark.asyncio
async def test_extract_metadata_with_async_decorator(python_extractor, python_parser):
    """Test extraction of custom async decorator."""
    source_code = """
@async_cached
async def fetch_data():
    return await database.query()
"""
    tree = python_parser.parse(bytes(source_code, "utf8"))
    function_node = tree.root_node.children[0]

    metadata = await python_extractor.extract_metadata(source_code, function_node, tree)

    assert "decorators" in metadata
    assert "async_cached" in metadata["decorators"]
    assert metadata.get("is_async") is True


@pytest.mark.asyncio
async def test_extract_type_hints_from_function(python_extractor, python_parser):
    """Test extraction of function parameter type hints."""
    source_code = """
def process_data(items: List[str], count: int) -> Dict[str, int]:
    return {}
"""
    tree = python_parser.parse(bytes(source_code, "utf8"))
    function_node = tree.root_node.children[0]

    metadata = await python_extractor.extract_metadata(source_code, function_node, tree)

    assert "type_hints" in metadata
    type_hints = metadata["type_hints"]
    assert "parameters" in type_hints
    assert "return_type" in type_hints
    assert type_hints["return_type"] == "Dict[str, int]"


@pytest.mark.asyncio
async def test_extract_optional_type_hint(python_extractor, python_parser):
    """Test extraction of Optional type hint."""
    source_code = """
def get_user(user_id: int) -> Optional[User]:
    return None
"""
    tree = python_parser.parse(bytes(source_code, "utf8"))
    function_node = tree.root_node.children[0]

    metadata = await python_extractor.extract_metadata(source_code, function_node, tree)

    assert metadata["type_hints"]["return_type"] == "Optional[User]"


@pytest.mark.asyncio
async def test_extract_class_attribute_type_hints(python_extractor, python_parser):
    """Test extraction of class attribute type hints."""
    source_code = """
class User:
    name: str
    age: int
    email: Optional[str] = None
"""
    tree = python_parser.parse(bytes(source_code, "utf8"))
    class_node = tree.root_node.children[0]

    metadata = await python_extractor.extract_metadata(source_code, class_node, tree)

    assert "type_hints" in metadata
    assert "attributes" in metadata["type_hints"]
