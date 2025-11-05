"""
Unit tests for EPIC-28: Byte Offset Fix in TypeScript Metadata Extractor.

Tests verify that full file source is used correctly to prevent byte offset
misalignment and call name corruption.

EPIC-28 Story 28.4: Add unit tests for byte offset fix.
"""

import pytest
from tree_sitter_language_pack import get_parser
from api.services.metadata_extractors.typescript_extractor import TypeScriptMetadataExtractor


class TestByteOffsetFix:
    """
    Test suite for EPIC-28 byte offset fix.

    Validates that:
    1. Full file source prevents call name corruption
    2. UTF-8 multi-byte characters are handled correctly
    3. Multiple chunks from same file use same full source
    """

    @pytest.mark.asyncio
    async def test_byte_offset_with_full_file_source(self):
        """
        EPIC-28: Verify byte offsets use full file source correctly.

        This test ensures that function call names are extracted correctly
        without truncation (e.g., "createSuccess" not "teSuccess").

        Before EPIC-28: Would extract "teSuccess" (missing 4 bytes)
        After EPIC-28: Correctly extracts "createSuccess"
        """
        # Full file with UTF-8 characters and comments
        full_file_source = '''// Comment avec caractères spéciaux: é à ù
// Line 2
export function createSuccess<T>(value: T): Result<T> {
  return new Success<T>(value);
}

export function createFailure<T>(errors: Error[]): Result<T> {
  return new Failure<T>(errors);
}
'''

        # Parse full file
        parser = get_parser("typescript")
        tree = parser.parse(bytes(full_file_source, "utf8"))

        # Query for function declarations
        from tree_sitter import Query
        language = parser.language
        query = Query(language, "(function_declaration) @func")

        # Get captures using QueryCursor
        from tree_sitter import QueryCursor
        cursor = QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        func_nodes = []
        for pattern_index, captures_dict in matches:
            func_nodes.extend(captures_dict.get('func', []))

        # Get first function node (createSuccess)
        assert len(func_nodes) >= 1, "Should find at least one function"
        create_success_node = func_nodes[0]

        # Extract metadata with FULL file source
        extractor = TypeScriptMetadataExtractor("typescript")
        metadata = await extractor.extract_metadata(
            source_code=full_file_source,  # Full file!
            node=create_success_node,
            tree=tree
        )

        # Verify: Should extract "Success" constructor, NOT truncated "cess"
        calls = metadata.get("calls", [])
        assert "Success" in calls, f"Expected 'Success' in calls, got: {calls}"

        # Verify: No truncated names
        for call in calls:
            assert len(call) > 2, f"Call name too short (truncated?): '{call}'"
            assert call[0].isupper() or call[0].islower(), \
                f"Call name has invalid start character: '{call}'"

        # Verify: Function name appears in metadata (signature or other fields)
        metadata_str = str(metadata)
        assert "createSuccess" in metadata_str or "Success" in metadata_str, \
            "Function name should appear in metadata"

    @pytest.mark.asyncio
    async def test_utf8_handling(self):
        """
        EPIC-28: Verify UTF-8 multi-byte characters don't break offsets.

        Tests that functions with UTF-8 characters (é, à, ù) in comments
        or names are parsed correctly without offset corruption.
        """
        full_file_source = '''export function créateSuccès() {
  return "Succès!";
}
'''

        parser = get_parser("typescript")
        tree = parser.parse(bytes(full_file_source, "utf8"))

        # Extract function node
        from tree_sitter import Query, QueryCursor
        language = parser.language
        query = Query(language, "(function_declaration) @func")
        cursor = QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        func_nodes = []
        for pattern_index, captures_dict in matches:
            func_nodes.extend(captures_dict.get('func', []))

        assert len(func_nodes) == 1, "Should find exactly one function"
        func_node = func_nodes[0]

        extractor = TypeScriptMetadataExtractor("typescript")
        metadata = await extractor.extract_metadata(
            source_code=full_file_source,
            node=func_node,
            tree=tree
        )

        # Should not crash or produce garbage
        assert metadata is not None, "Metadata should not be None"
        assert isinstance(metadata.get("calls", []), list), "Calls should be a list"

        # Verify signature extraction works with UTF-8
        signature = metadata.get("signature", {})
        assert signature is not None, "Signature should be extracted"

    @pytest.mark.asyncio
    async def test_multiple_chunks_same_file(self):
        """
        EPIC-28: Verify multiple chunks from same file use same full source.

        This test simulates the real-world scenario where a file has multiple
        functions (chunks), and each chunk's metadata extraction should use
        the SAME full file source, not re-parse individual chunks.
        """
        full_file_source = '''export function first() { return second(); }
export function second() { return third(); }
export function third() { return "done"; }
'''

        parser = get_parser("typescript")
        tree = parser.parse(bytes(full_file_source, "utf8"))

        # Get all function nodes
        from tree_sitter import Query, QueryCursor
        language = parser.language
        query = Query(language, "(function_declaration) @func")
        cursor = QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        func_nodes = []
        for pattern_index, captures_dict in matches:
            func_nodes.extend(captures_dict.get('func', []))

        assert len(func_nodes) == 3, f"Expected 3 functions, found {len(func_nodes)}"

        extractor = TypeScriptMetadataExtractor("typescript")

        # Extract metadata for all 3 functions with SAME full source
        all_metadata = []
        for func_node in func_nodes:
            metadata = await extractor.extract_metadata(
                source_code=full_file_source,  # Same full source!
                node=func_node,
                tree=tree
            )
            all_metadata.append(metadata)

        # Verify cross-function calls detected
        first_calls = all_metadata[0].get("calls", [])
        assert "second" in first_calls, \
            f"first() should call second(), got calls: {first_calls}"

        second_calls = all_metadata[1].get("calls", [])
        assert "third" in second_calls, \
            f"second() should call third(), got calls: {second_calls}"

        # Verify all metadata extracted successfully
        for i, metadata in enumerate(all_metadata):
            assert metadata is not None, f"Metadata {i} should not be None"
            assert isinstance(metadata.get("calls", []), list), \
                f"Metadata {i} calls should be a list"

    @pytest.mark.asyncio
    async def test_no_call_name_corruption(self):
        """
        EPIC-28: Verify that common corruption patterns are prevented.

        Before EPIC-28, functions like "createSuccess" would be extracted as
        "teSuccess" (missing first 4 bytes). This test verifies the fix.
        """
        # Real-world example from CVGenerator that was corrupted
        full_file_source = '''import { Result } from './types';

export function createSuccess<T>(value: T): Result<T> {
  return { ok: true, value };
}

export function createFailure<E>(error: E): Result<never, E> {
  return { ok: false, error };
}

export function validateEmail(email: string): Result<string> {
  const re = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;
  if (re.test(email)) {
    return createSuccess(email);
  }
  return createFailure("Invalid email");
}
'''

        parser = get_parser("typescript")
        tree = parser.parse(bytes(full_file_source, "utf8"))

        # Get validateEmail function (which calls createSuccess and createFailure)
        from tree_sitter import Query, QueryCursor
        language = parser.language
        query = Query(language, "(function_declaration) @func")
        cursor = QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        func_nodes = []
        for pattern_index, captures_dict in matches:
            func_nodes.extend(captures_dict.get('func', []))

        # Find validateEmail function (third function)
        validate_email_node = None
        for node in func_nodes:
            # Extract function name
            source_bytes = full_file_source.encode('utf-8')
            node_text = source_bytes[node.start_byte:node.end_byte].decode('utf-8')
            if "validateEmail" in node_text:
                validate_email_node = node
                break

        assert validate_email_node is not None, "Should find validateEmail function"

        extractor = TypeScriptMetadataExtractor("typescript")
        metadata = await extractor.extract_metadata(
            source_code=full_file_source,
            node=validate_email_node,
            tree=tree
        )

        calls = metadata.get("calls", [])

        # Critical assertion: Should extract full names, not corrupted versions
        # Before EPIC-28: Would get "teSuccess", "eFailure"
        # After EPIC-28: Should get "createSuccess", "createFailure"

        # Verify createSuccess is called correctly
        assert "createSuccess" in calls, \
            f"Should call 'createSuccess' (not 'teSuccess'!), got: {calls}"

        # Verify createFailure is called correctly
        assert "createFailure" in calls, \
            f"Should call 'createFailure' (not 'eFailure'!), got: {calls}"

        # Verify no truncated call names (all should be >3 chars)
        for call in calls:
            assert len(call) > 3, \
                f"Call name suspiciously short (likely truncated): '{call}'"

    @pytest.mark.asyncio
    async def test_complex_call_patterns(self):
        """
        EPIC-28: Verify complex call patterns are extracted correctly.

        Tests chained calls, method calls, and constructor calls.
        """
        full_file_source = '''export class UserService {
  constructor(private db: Database) {}

  async getUser(id: string) {
    const user = await this.db.query('users').where('id', id).first();
    return this.transformUser(user);
  }

  private transformUser(raw: any) {
    return new User(raw.id, raw.name);
  }
}
'''

        parser = get_parser("typescript")
        tree = parser.parse(bytes(full_file_source, "utf8"))

        # Get getUser method
        from tree_sitter import Query, QueryCursor
        language = parser.language
        query = Query(language, "(method_definition) @method")
        cursor = QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        method_nodes = []
        for pattern_index, captures_dict in matches:
            method_nodes.extend(captures_dict.get('method', []))

        # Find getUser method
        get_user_node = None
        for node in method_nodes:
            source_bytes = full_file_source.encode('utf-8')
            node_text = source_bytes[node.start_byte:node.end_byte].decode('utf-8')
            if "getUser" in node_text:
                get_user_node = node
                break

        assert get_user_node is not None, "Should find getUser method"

        extractor = TypeScriptMetadataExtractor("typescript")
        metadata = await extractor.extract_metadata(
            source_code=full_file_source,
            node=get_user_node,
            tree=tree
        )

        calls = metadata.get("calls", [])

        # Should extract method calls correctly (after cleanup)
        # Chained calls like db.query().where().first() should extract last identifiers
        # transformUser should be extracted from this.transformUser(user)
        assert "transformUser" in calls, \
            f"Should extract 'transformUser' from method call, got: {calls}"

        # Verify no corrupted call names
        for call in calls:
            assert len(call) >= 2, \
                f"Call name too short (corrupted?): '{call}'"
            assert call[0].isalpha() or call[0] in ('_', '$'), \
                f"Call name has invalid start: '{call}'"


class TestBackwardCompatibility:
    """
    Test that the EPIC-28 fix doesn't break existing functionality.
    """

    @pytest.mark.asyncio
    async def test_empty_file_handling(self):
        """Verify empty files don't cause issues."""
        full_file_source = "// Empty file\n"

        parser = get_parser("typescript")
        tree = parser.parse(bytes(full_file_source, "utf8"))

        extractor = TypeScriptMetadataExtractor("typescript")

        # Should not crash with empty file
        metadata = await extractor.extract_metadata(
            source_code=full_file_source,
            node=tree.root_node,
            tree=tree
        )

        assert metadata is not None
        assert metadata.get("calls", []) == []

    @pytest.mark.asyncio
    async def test_file_with_only_imports(self):
        """Verify files with only imports work correctly."""
        full_file_source = '''import { Foo } from './foo';
import { Bar } from './bar';
export { Foo, Bar };
'''

        parser = get_parser("typescript")
        tree = parser.parse(bytes(full_file_source, "utf8"))

        extractor = TypeScriptMetadataExtractor("typescript")
        metadata = await extractor.extract_metadata(
            source_code=full_file_source,
            node=tree.root_node,
            tree=tree
        )

        # Should extract imports
        imports = metadata.get("imports", [])
        assert len(imports) > 0, "Should extract imports"

        # No calls expected
        calls = metadata.get("calls", [])
        assert len(calls) == 0, "Should have no calls in import-only file"
