"""Tests for TypeScript re-export extraction (EPIC-29 Task 2)."""
import pytest
from tree_sitter_language_pack import get_parser
from api.services.metadata_extractors.typescript_extractor import TypeScriptMetadataExtractor


@pytest.mark.asyncio
async def test_extract_named_reexports():
    """Test extraction of named re-exports: export { X, Y } from 'source'."""
    source = """
export { createSuccess, createFailure } from './utils/result.utils';
export { Success, Failure } from './types/result.type';
"""

    parser = get_parser("typescript")
    tree = parser.parse(bytes(source, "utf8"))

    extractor = TypeScriptMetadataExtractor("typescript")
    metadata = await extractor.extract_metadata(
        source_code=source,
        node=tree.root_node,
        tree=tree
    )

    # Should extract re-exports
    assert "re_exports" in metadata
    assert len(metadata["re_exports"]) == 4

    # Verify structure
    reexports = metadata["re_exports"]
    assert {"symbol": "createSuccess", "source": "./utils/result.utils", "is_type": False} in reexports
    assert {"symbol": "createFailure", "source": "./utils/result.utils", "is_type": False} in reexports
    assert {"symbol": "Success", "source": "./types/result.type", "is_type": False} in reexports
    assert {"symbol": "Failure", "source": "./types/result.type", "is_type": False} in reexports


@pytest.mark.asyncio
async def test_extract_wildcard_reexports():
    """Test extraction of wildcard re-exports: export * from 'source'."""
    source = """
export * from './utils/result.utils';
export * from './types/result.type';
"""

    parser = get_parser("typescript")
    tree = parser.parse(bytes(source, "utf8"))

    extractor = TypeScriptMetadataExtractor("typescript")
    metadata = await extractor.extract_metadata(
        source_code=source,
        node=tree.root_node,
        tree=tree
    )

    assert "re_exports" in metadata
    assert len(metadata["re_exports"]) == 2

    # Wildcard exports use "*" as symbol
    assert {"symbol": "*", "source": "./utils/result.utils", "is_type": False} in metadata["re_exports"]
    assert {"symbol": "*", "source": "./types/result.type", "is_type": False} in metadata["re_exports"]


@pytest.mark.asyncio
async def test_extract_renamed_reexports():
    """Test extraction of renamed re-exports: export { X as Y } from 'source'."""
    source = """
export { Success as SuccessResult } from './types/result.type';
export { createSuccess as makeSuccess } from './utils/result.utils';
"""

    parser = get_parser("typescript")
    tree = parser.parse(bytes(source, "utf8"))

    extractor = TypeScriptMetadataExtractor("typescript")
    metadata = await extractor.extract_metadata(
        source_code=source,
        node=tree.root_node,
        tree=tree
    )

    assert "re_exports" in metadata
    assert len(metadata["re_exports"]) == 2

    # Renamed exports store both original and alias
    assert {"symbol": "SuccessResult", "original": "Success", "source": "./types/result.type", "is_type": False} in metadata["re_exports"]
    assert {"symbol": "makeSuccess", "original": "createSuccess", "source": "./utils/result.utils", "is_type": False} in metadata["re_exports"]


@pytest.mark.asyncio
async def test_extract_type_only_reexports():
    """Test extraction of TypeScript type-only re-exports."""
    source = """
export type { ValidationError } from './types/validation.interface';
export type { ResultType, OptionType } from './types/result.type';
"""

    parser = get_parser("typescript")
    tree = parser.parse(bytes(source, "utf8"))

    extractor = TypeScriptMetadataExtractor("typescript")
    metadata = await extractor.extract_metadata(
        source_code=source,
        node=tree.root_node,
        tree=tree
    )

    assert "re_exports" in metadata
    assert len(metadata["re_exports"]) == 3

    # Type-only exports are marked with is_type flag
    validation_export = next(e for e in metadata["re_exports"] if e["symbol"] == "ValidationError")
    assert validation_export["is_type"] is True
    assert validation_export["source"] == "./types/validation.interface"
