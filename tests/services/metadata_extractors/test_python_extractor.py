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
