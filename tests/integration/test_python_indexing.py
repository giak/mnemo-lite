"""
Integration test for Python indexing pipeline.

Tests that:
1. Python files can be chunked
2. Metadata is extracted (imports, calls)
3. The chunking pipeline works end-to-end

Note: Currently the chunking service uses Python's ast module for Python code,
not tree-sitter. This test validates the ast-based metadata extraction works.
"""

import pytest
from pathlib import Path
from services.code_chunking_service import CodeChunkingService
from services.metadata_extractor_service import MetadataExtractorService
from services.metadata_extractors.python_extractor import PythonMetadataExtractor


@pytest.mark.asyncio
async def test_python_file_chunking():
    """Test that Python files can be chunked and metadata extracted."""
    # Create a simple Python file content
    source_code = """
import os
from pathlib import Path
from typing import List, Optional

class DataProcessor:
    def __init__(self, config: dict):
        self.config = config

    async def process_items(self, items: List[str]) -> Optional[dict]:
        result = self.validate(items)
        data = await self.fetch_data()
        return self.merge(result, data)

    def validate(self, items: List[str]) -> dict:
        return {"valid": True}

    async def fetch_data(self) -> dict:
        return {"data": []}

    def merge(self, a: dict, b: dict) -> dict:
        return {**a, **b}
"""

    # Create metadata service (will use default Python extraction)
    # Note: PythonMetadataExtractor requires tree-sitter objects,
    # but chunking service uses ast, so it will fall back to ast-based extraction
    metadata_service = MetadataExtractorService()

    # Create chunking service
    chunking_service = CodeChunkingService(max_workers=1, metadata_service=metadata_service)

    # Parse and chunk
    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        file_path="test_processor.py",
        language="python"
    )

    # Assertions
    assert len(chunks) > 0, "Should create at least one chunk"

    # Find the process_items method chunk
    process_chunk = next((c for c in chunks if "process_items" in c.source_code), None)
    assert process_chunk is not None, "Should find process_items method chunk"

    # Check metadata exists
    metadata = process_chunk.metadata
    assert metadata is not None, "Chunk should have metadata"

    # Check basic metadata structure (ast-based extraction provides these)
    assert "calls" in metadata, "Should have calls metadata"
    assert "imports" in metadata, "Should have imports metadata"

    # Check that metadata extraction worked (at minimum, should extract calls)
    # The ast-based extraction should find some calls (validate, fetch_data, merge)
    calls = metadata.get("calls", [])
    assert len(calls) > 0, "Should have extracted function calls"

    # Check that validate, fetch_data, or merge are in calls
    calls_str = " ".join(calls)
    assert "validate" in calls_str or "fetch_data" in calls_str or "merge" in calls_str, \
        f"Should extract method calls, got: {calls}"


@pytest.mark.asyncio
async def test_python_metadata_extractor_with_tree_sitter():
    """Test that PythonMetadataExtractor works with tree-sitter objects."""
    from tree_sitter_language_pack import get_parser

    source_code = """
import os
from pathlib import Path

async def process_data(items: list[str]) -> dict:
    result = validate(items)
    return result
"""

    # Parse with tree-sitter
    parser = get_parser("python")
    tree = parser.parse(bytes(source_code, "utf8"))

    # Find the function node
    function_node = None
    for child in tree.root_node.children:
        if child.type == "function_definition":
            function_node = child
            break

    assert function_node is not None, "Should find function node"

    # Create extractor and extract metadata
    extractor = PythonMetadataExtractor()
    metadata = await extractor.extract_metadata(source_code, function_node, tree)

    # Verify metadata structure
    assert "imports" in metadata
    assert "calls" in metadata
    assert "decorators" in metadata
    assert "is_async" in metadata
    assert "type_hints" in metadata

    # Check async detection
    assert metadata["is_async"] is True, "Should detect async function"

    # Check imports
    imports = metadata["imports"]
    assert len(imports) > 0, "Should extract imports"
    assert any("os" in imp for imp in imports)
    assert any("Path" in imp for imp in imports)

    # Check calls
    calls = metadata["calls"]
    assert "validate" in calls, f"Should extract validate call, got: {calls}"
