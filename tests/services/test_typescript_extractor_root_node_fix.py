"""
Unit test for TypeScriptMetadataExtractor root_node bug fix.

Tests that extract_imports() handles both Tree and Node objects correctly.
"""
import pytest
from tree_sitter_language_pack import get_parser
from services.metadata_extractors.typescript_extractor import TypeScriptMetadataExtractor


@pytest.fixture
def extractor():
    """Create TypeScriptMetadataExtractor instance."""
    return TypeScriptMetadataExtractor()


@pytest.mark.asyncio
async def test_extract_imports_with_tree_object(extractor):
    """Test extract_imports() with a Tree object (normal case)."""
    source_code = """
    import { MyClass, MyFunction } from './models';
    import * as utils from 'lodash';
    import React from 'react';
    """

    parser = get_parser("typescript")
    tree = parser.parse(bytes(source_code, "utf-8"))

    # Pass Tree object
    imports = await extractor.extract_imports(tree, source_code)

    assert len(imports) >= 2  # At least './models.MyClass' and 'lodash'
    assert any('models' in imp for imp in imports)
    assert 'lodash' in imports or any('lodash' in imp for imp in imports)


@pytest.mark.asyncio
async def test_extract_imports_with_node_object(extractor):
    """Test extract_imports() with a Node object (defensive case)."""
    source_code = """
    import { MyClass, MyFunction } from './models';
    import * as utils from 'lodash';
    import React from 'react';
    """

    parser = get_parser("typescript")
    tree = parser.parse(bytes(source_code, "utf-8"))

    # Pass Node object (root_node) instead of Tree
    root_node = tree.root_node
    imports = await extractor.extract_imports(root_node, source_code)

    # Should work the same as with Tree
    assert len(imports) >= 2
    assert any('models' in imp for imp in imports)
    assert 'lodash' in imports or any('lodash' in imp for imp in imports)


@pytest.mark.asyncio
async def test_extract_imports_both_cases_produce_same_result(extractor):
    """Test that Tree and Node produce identical results."""
    source_code = """
    import { User, Product } from './types';
    import axios from 'axios';
    export { Service } from './services';
    """

    parser = get_parser("typescript")
    tree = parser.parse(bytes(source_code, "utf-8"))

    # Extract with Tree
    imports_from_tree = await extractor.extract_imports(tree, source_code)

    # Extract with Node
    imports_from_node = await extractor.extract_imports(tree.root_node, source_code)

    # Both should produce identical results
    assert set(imports_from_tree) == set(imports_from_node)
    assert len(imports_from_tree) == len(imports_from_node)
