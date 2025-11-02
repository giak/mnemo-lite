import pytest
from services.metadata_extractors.typescript_extractor import TypeScriptMetadataExtractor
from tree_sitter_language_pack import get_parser


@pytest.mark.asyncio
async def test_extract_metadata_with_context():
    """Test metadata extraction includes call context."""
    source_code = """
async function createUser(email: string, name: string): Promise<User> {
    if (email) {
        validateEmail(email);
    }

    for (let i = 0; i < 10; i++) {
        processItem(i);
    }

    return await saveUser(email, name);
}
"""

    parser = get_parser("typescript")
    tree = parser.parse(bytes(source_code, "utf8"))

    # Find function node
    function_node = tree.root_node.children[0]

    extractor = TypeScriptMetadataExtractor("typescript")
    metadata = await extractor.extract_metadata(source_code, function_node, tree)

    # Check calls extracted
    assert "validateEmail" in metadata["calls"]
    assert "processItem" in metadata["calls"]
    assert "saveUser" in metadata["calls"]

    # Check enriched context
    assert "call_contexts" in metadata
    contexts = metadata["call_contexts"]

    # validateEmail context
    validate_ctx = next(c for c in contexts if c["call_name"] == "validateEmail")
    assert validate_ctx["is_conditional"] == True
    assert validate_ctx["is_loop"] == False
    assert validate_ctx["scope_type"] == "function"
    assert validate_ctx["scope_name"] == "createUser"

    # processItem context
    process_ctx = next(c for c in contexts if c["call_name"] == "processItem")
    assert process_ctx["is_loop"] == True
    assert process_ctx["is_conditional"] == False

    # Check signature
    assert "signature" in metadata
    sig = metadata["signature"]
    assert sig["function_name"] == "createUser"
    assert sig["is_async"] == True
    assert sig["return_type"] == "Promise<User>"
    assert len(sig["parameters"]) == 2
    assert sig["parameters"][0] == {"name": "email", "type": "string", "is_optional": False, "default_value": None}


@pytest.mark.asyncio
async def test_extract_complexity_metrics():
    """Test cyclomatic complexity calculation."""
    source_code = """
function complexFunction(x: number): number {
    if (x > 10) {
        return x * 2;
    } else if (x > 5) {
        return x + 1;
    } else {
        return x;
    }

    for (let i = 0; i < x; i++) {
        process(i);
    }
}
"""

    parser = get_parser("typescript")
    tree = parser.parse(bytes(source_code, "utf8"))
    function_node = tree.root_node.children[0]

    extractor = TypeScriptMetadataExtractor("typescript")
    metadata = await extractor.extract_metadata(source_code, function_node, tree)

    assert "complexity" in metadata
    # Cyclomatic = 1 (base) + 1 (if) + 1 (else if) + 1 (else clause) + 1 (for) + possibly others = 6
    # The actual calculation includes else_clause as a decision point
    assert metadata["complexity"]["cyclomatic"] >= 4
    assert metadata["complexity"]["lines_of_code"] > 0
