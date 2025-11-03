# tests/services/test_typescript_extractor_lsp_type.py
import pytest
from services.metadata_extractors.typescript_extractor import TypeScriptMetadataExtractor
from tree_sitter_language_pack import get_parser


@pytest.mark.asyncio
async def test_extract_metadata_includes_lsp_type_for_class():
    """Test that class metadata includes lsp_type='class'."""
    extractor = TypeScriptMetadataExtractor()

    code = """
export class Calculator {
    add(a: number, b: number): number {
        return a + b;
    }
}
"""

    parser = get_parser("typescript")
    tree = parser.parse(bytes(code, "utf8"))

    # Find class node
    class_node = tree.root_node.children[0]
    assert class_node.type == "export_statement"
    # Get the actual class declaration
    class_declaration = class_node.children[1]
    assert class_declaration.type == "class_declaration"

    # Extract metadata
    metadata = await extractor.extract_metadata(code, class_declaration, tree)

    # Verify lsp_type
    assert 'lsp_type' in metadata, "lsp_type missing from metadata"
    assert metadata['lsp_type'] == 'class', \
        f"Expected lsp_type='class', got {metadata.get('lsp_type')}"


@pytest.mark.asyncio
async def test_extract_metadata_includes_lsp_type_for_method():
    """Test that method metadata includes lsp_type='method'."""
    extractor = TypeScriptMetadataExtractor()

    code = """
class Calc {
    add(a, b) { return a + b; }
}
"""

    parser = get_parser("typescript")
    tree = parser.parse(bytes(code, "utf8"))

    # Find class node, then method node
    class_node = tree.root_node.children[0]
    class_body = class_node.children[2]  # class_body
    method_def = class_body.children[1]  # method_definition
    assert method_def.type == "method_definition"

    # Extract metadata for method
    metadata = await extractor.extract_metadata(code, method_def, tree)

    assert metadata['lsp_type'] == 'method'


@pytest.mark.asyncio
async def test_extract_metadata_includes_lsp_type_for_function():
    """Test that function metadata includes lsp_type='function'."""
    extractor = TypeScriptMetadataExtractor()

    code = "export function sum(arr) { return arr.reduce((a, b) => a + b, 0); }"

    parser = get_parser("typescript")
    tree = parser.parse(bytes(code, "utf8"))

    # Find function node
    export_statement = tree.root_node.children[0]
    func_declaration = export_statement.children[1]
    assert func_declaration.type == "function_declaration"

    # Extract metadata
    metadata = await extractor.extract_metadata(code, func_declaration, tree)

    assert metadata['lsp_type'] == 'function'


@pytest.mark.asyncio
async def test_extract_metadata_includes_lsp_type_for_interface():
    """Test that interface metadata includes lsp_type='interface'."""
    extractor = TypeScriptMetadataExtractor()

    code = """
export interface User {
    name: string;
    email: string;
}
"""

    parser = get_parser("typescript")
    tree = parser.parse(bytes(code, "utf8"))

    # Find interface node
    export_statement = tree.root_node.children[0]
    interface_declaration = export_statement.children[1]
    assert interface_declaration.type == "interface_declaration"

    # Extract metadata
    metadata = await extractor.extract_metadata(code, interface_declaration, tree)

    assert metadata['lsp_type'] == 'interface'


@pytest.mark.asyncio
async def test_lsp_type_mapping_completeness():
    """Test that all node types have lsp_type mapping."""
    extractor = TypeScriptMetadataExtractor()
    parser = get_parser("typescript")

    # Test data for each node type
    test_cases = {
        'class': ("class Foo {}", "class_declaration"),
        'method': ("class X { foo() {} }", "method_definition"),
        'function': ("function bar() {}", "function_declaration"),
        'interface': ("interface Baz {}", "interface_declaration"),
    }

    for expected_lsp_type, (code, node_type) in test_cases.items():
        tree = parser.parse(bytes(code, "utf8"))

        # Find the node by type
        def find_node_by_type(node, target_type):
            if node.type == target_type:
                return node
            for child in node.children:
                result = find_node_by_type(child, target_type)
                if result:
                    return result
            return None

        target_node = find_node_by_type(tree.root_node, node_type)
        assert target_node is not None, f"No node found for {node_type}"

        # Extract metadata
        metadata = await extractor.extract_metadata(code, target_node, tree)

        assert 'lsp_type' in metadata, f"lsp_type missing for {expected_lsp_type}"
        assert metadata['lsp_type'] == expected_lsp_type, \
            f"Expected lsp_type='{expected_lsp_type}', got '{metadata.get('lsp_type')}'"
