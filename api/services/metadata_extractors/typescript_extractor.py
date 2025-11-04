"""
TypeScript/JavaScript metadata extractor using tree-sitter.

EPIC-26 Story 26.1: TypeScript import extraction.
EPIC-26 Story 26.2: TypeScript call extraction (TODO).
"""

import logging
from typing import Any
from tree_sitter import Node, Tree, Query, QueryCursor
from tree_sitter_language_pack import get_language


logger = logging.getLogger(__name__)


class TypeScriptMetadataExtractor:
    """
    Extract metadata from TypeScript/JavaScript using tree-sitter queries.

    Supports:
    - ESM imports (import/export statements)
    - CommonJS require (JavaScript only, future)
    - Function calls (TODO: Story 26.2)
    - Method calls (TODO: Story 26.2)
    """

    # EPIC-27 Story 27.4: Framework function blacklist
    # Common test framework functions to filter out (reduce noise)
    FRAMEWORK_BLACKLIST = {
        # Vitest/Jest test structure
        "describe", "it", "test", "suite", "beforeEach", "afterEach",
        "beforeAll", "afterAll", "setup", "teardown",
        # Vitest/Jest assertions
        "expect", "assert", "toBe", "toEqual", "toHaveBeenCalled",
        "toHaveBeenCalledWith", "toBeNull", "toBeDefined", "toBeUndefined",
        "toBeTruthy", "toBeFalsy", "toContain", "toMatch", "toThrow",
        "toHaveProperty", "toBeInstanceOf", "toBeCloseTo", "toBeGreaterThan",
        "toBeLessThan", "toMatchSnapshot", "toMatchInlineSnapshot",
        # Vitest mocking
        "vi", "mock", "mockReturnValue", "mockResolvedValue", "mockRejectedValue",
        "mockImplementation", "spyOn", "fn", "clearAllMocks", "resetAllMocks",
        # Common DOM testing
        "mount", "shallowMount", "render", "screen", "fireEvent", "waitFor",
        "getByText", "getByRole", "queryByText", "findByText",
        # Console logging
        "log", "error", "warn", "info", "debug",
    }

    def __init__(self, language: str = "typescript"):
        """
        Initialize TypeScript/JavaScript language and queries.

        Args:
            language: Language name ('typescript' or 'javascript')
        """
        self.language = get_language(language)
        self.language_name = language
        self.logger = logging.getLogger(__name__)

        # Import extraction queries
        # Split into multiple queries for better compatibility
        self.named_imports_query = Query(
            self.language,
            "(import_statement (import_clause (named_imports (import_specifier name: (identifier) @import_name))) source: (string) @import_source)"
        )

        self.namespace_imports_query = Query(
            self.language,
            "(import_statement (import_clause (namespace_import (identifier) @namespace_name)) source: (string) @import_source)"
        )

        self.default_imports_query = Query(
            self.language,
            "(import_statement (import_clause (identifier) @default_name) source: (string) @import_source)"
        )

        self.side_effect_imports_query = Query(
            self.language,
            "(import_statement source: (string) @import_source)"
        )

        # NOTE: Type-only imports/exports cannot be captured with Query syntax
        # because tree-sitter doesn't support matching literal "type" keyword.
        # We use manual AST traversal instead (see extract_imports method).

        self.re_exports_query = Query(
            self.language,
            "(export_statement (export_clause (export_specifier name: (identifier) @export_name)) source: (string) @export_source)"
        )

        # Call extraction queries (Story 26.2)
        # Query for function/method calls
        self.call_expression_query = Query(
            self.language,
            "(call_expression) @call"
        )

        # Query for new expressions (constructors)
        self.new_expression_query = Query(
            self.language,
            "(new_expression constructor: (_) @constructor)"
        )

    def _extract_string_literal(self, node: Node, source_code: str) -> str:
        """
        Extract string content from string node (remove quotes).

        Args:
            node: String node from tree-sitter
            source_code: Full source code

        Returns:
            String content without quotes (e.g., './models' → ./models)
        """
        # EPIC-28: Fix UTF-8 byte offset bug (slice bytes, not chars)
        source_bytes = source_code.encode('utf-8')
        text_bytes = source_bytes[node.start_byte:node.end_byte]
        text = text_bytes.decode('utf-8')
        # Remove quotes (single or double)
        if (text.startswith("'") and text.endswith("'")) or \
           (text.startswith('"') and text.endswith('"')):
            return text[1:-1]
        return text

    def _extract_type_imports_exports(
        self,
        root_node: Node,
        source_code: str,
        imports: list[str],
        imports_seen: set[str]
    ):
        """
        Extract type-only imports and exports using manual AST traversal.

        CRITICAL FIX 2025-11-04: Resolves 40% isolated nodes bug.

        Handles:
        - import type { Foo, Bar } from './types'
        - export type { Baz } from './types'

        Cannot use Query syntax because tree-sitter doesn't support matching
        literal "type" keyword. Instead, we walk the AST manually and check
        for child nodes with type="type".

        Args:
            root_node: Root AST node
            source_code: Full source code
            imports: List to append extracted imports to
            imports_seen: Set to track duplicates
        """
        def walk_tree(node: Node):
            # Check for type imports: import type { ... } from '...'
            if node.type == "import_statement":
                has_type = any(child.type == "type" for child in node.children)
                if has_type:
                    self._process_type_import(node, source_code, imports, imports_seen)

            # Check for type exports: export type { ... } from '...'
            elif node.type == "export_statement":
                has_type = any(child.type == "type" for child in node.children)
                has_from = any(child.type == "from" for child in node.children)
                if has_type and has_from:
                    self._process_type_export(node, source_code, imports, imports_seen)

            # Recurse to children
            for child in node.children:
                walk_tree(child)

        walk_tree(root_node)

    def _process_type_import(
        self,
        import_node: Node,
        source_code: str,
        imports: list[str],
        imports_seen: set[str]
    ):
        """Process a type-only import statement."""
        source_str = None
        names = []
        source_bytes = source_code.encode('utf-8')

        # Extract source and named imports
        for child in import_node.children:
            if child.type == "string":
                source_str = self._extract_string_literal(child, source_code)
            elif child.type == "import_clause":
                # Look for named_imports
                for subchild in child.children:
                    if subchild.type == "named_imports":
                        # Extract import_specifier identifiers
                        for specifier in subchild.children:
                            if specifier.type == "import_specifier":
                                for id_node in specifier.children:
                                    if id_node.type == "identifier":
                                        name_bytes = source_bytes[id_node.start_byte:id_node.end_byte]
                                        name = name_bytes.decode('utf-8')
                                        names.append(name)

        # Add to imports list
        if source_str and names:
            for name in names:
                import_ref = f"{source_str}.{name}"
                if import_ref not in imports_seen:
                    imports.append(import_ref)
                    imports_seen.add(import_ref)
                    self.logger.debug(f"Extracted type import: {import_ref}")

    def _process_type_export(
        self,
        export_node: Node,
        source_code: str,
        imports: list[str],
        imports_seen: set[str]
    ):
        """Process a type-only export statement."""
        source_str = None
        names = []
        source_bytes = source_code.encode('utf-8')

        # Extract source and named exports
        for child in export_node.children:
            if child.type == "string":
                source_str = self._extract_string_literal(child, source_code)
            elif child.type == "export_clause":
                # Extract export_specifier identifiers
                for specifier in child.children:
                    if specifier.type == "export_specifier":
                        for id_node in specifier.children:
                            if id_node.type == "identifier":
                                name_bytes = source_bytes[id_node.start_byte:id_node.end_byte]
                                name = name_bytes.decode('utf-8')
                                names.append(name)

        # Add to imports list (exports create edges too)
        if source_str and names:
            for name in names:
                import_ref = f"{source_str}.{name}"
                if import_ref not in imports_seen:
                    imports.append(import_ref)
                    imports_seen.add(import_ref)
                    self.logger.debug(f"Extracted type export: {import_ref}")

    def _is_blacklisted(self, call_name: str) -> bool:
        """
        Check if a call name is in the framework blacklist.

        EPIC-27 Story 27.4: Filter out test framework functions.

        Args:
            call_name: Function/method name to check

        Returns:
            True if call should be filtered out, False otherwise

        Examples:
            >>> _is_blacklisted("describe")
            True

            >>> _is_blacklisted("validateEmail")
            False
        """
        if not call_name:
            return True

        # Check against blacklist (case-sensitive)
        return call_name in self.FRAMEWORK_BLACKLIST

    def _clean_call_name(self, raw_call: str) -> str | None:
        """
        Clean up extracted call expression to get function name.

        EPIC-27 Story 27.3: Post-processing cleanup for better call resolution.

        Handles:
        - Chained method calls: "obj.method" → "method"
        - Incomplete fragments: "e('valid" → None
        - Method chains: "vi.fn().mockReturnValue" → "mockReturnValue"
        - Already clean names: "validateEmail" → "validateEmail"

        Args:
            raw_call: Raw call text from tree-sitter

        Returns:
            Clean function name or None if invalid

        Examples:
            >>> _clean_call_name("validateEmail")
            "validateEmail"

            >>> _clean_call_name("obj.method")
            "method"

            >>> _clean_call_name("vi.fn().mockReturnValue")
            "mockReturnValue"

            >>> _clean_call_name("e('valid")
            None

            >>> _clean_call_name("expect(wrapper.exists()).toBe")
            "toBe"
        """
        import re

        # Filter out invalid/incomplete fragments
        if not raw_call or len(raw_call) < 2:
            return None

        if not raw_call[0].isalpha() and raw_call[0] not in ('_', '$'):
            return None

        # Handle chained calls/methods: extract the LAST identifier
        # Pattern: "obj.method", "a.b().c", "vi.fn().mock"
        if '.' in raw_call or '(' in raw_call:
            # Extract last identifier before '(' or at end
            match = re.search(r'([a-zA-Z_$][a-zA-Z0-9_$]*)(?:\(|$)', raw_call)
            if match:
                clean_name = match.group(1)
                # Validate it's a real identifier
                if clean_name and len(clean_name) >= 2:
                    return clean_name
            return None

        # Already clean identifier
        if re.match(r'^[a-zA-Z_$][a-zA-Z0-9_$]*$', raw_call):
            return raw_call

        # Invalid format
        return None

    async def extract_re_exports(self, node: Node, source_code: str) -> list[dict[str, Any]]:
        """
        Extract re-export statements from TypeScript/JavaScript.

        EPIC-29 Task 2: Support all re-export patterns:
        - Named: export { X, Y } from 'source'
        - Wildcard: export * from 'source'
        - Renamed: export { X as Y } from 'source'
        - Type-only: export type { T } from 'source'

        Args:
            node: Tree-sitter AST node (typically root)
            source_code: Full file source code

        Returns:
            List of re-export dicts with keys: symbol, source, [original], [is_type]
        """
        re_exports = []
        re_exports_seen = set()  # Track to avoid duplicates

        try:
            # Process all export_statement nodes
            def walk_tree(n):
                if n.type == "export_statement":
                    self._process_export_statement(n, source_code, re_exports, re_exports_seen)
                for child in n.children:
                    walk_tree(child)

            walk_tree(node)

        except Exception as e:
            self.logger.error(f"Failed to extract re-exports: {e}", exc_info=True)

        self.logger.debug(f"Extracted {len(re_exports)} re-exports")
        return re_exports

    def _process_export_statement(
        self,
        export_node: Node,
        source_code: str,
        re_exports: list,
        re_exports_seen: set
    ):
        """
        Process a single export_statement node to extract re-export info.

        Args:
            export_node: export_statement node
            source_code: Full source code
            re_exports: List to append results to
            re_exports_seen: Set to track duplicates
        """
        # Check if this export has a 'from' clause (re-export)
        has_from = False
        source_str = None
        is_type_only = False
        has_wildcard = False
        export_clause_node = None

        for child in export_node.children:
            if child.type == "from":
                has_from = True
            elif child.type == "string" and has_from:
                source_str = self._extract_string_literal(child, source_code)
            elif child.type == "type":
                is_type_only = True
            elif child.type == "*":
                has_wildcard = True
            elif child.type == "export_clause":
                export_clause_node = child

        # Not a re-export (no 'from' clause)
        if not has_from or not source_str:
            return

        # Case 1: Wildcard re-export (export * from 'source')
        if has_wildcard:
            re_export_key = (source_str, "*", "")
            if re_export_key not in re_exports_seen:
                re_exports.append({
                    "symbol": "*",
                    "source": source_str,
                    "is_type": is_type_only
                })
                re_exports_seen.add(re_export_key)
            return

        # Case 2: Named re-exports (export { X, Y } from 'source')
        if export_clause_node:
            for specifier in export_clause_node.children:
                if specifier.type == "export_specifier":
                    self._process_export_specifier(
                        specifier, source_code, source_str, is_type_only,
                        re_exports, re_exports_seen
                    )

    def _process_export_specifier(
        self,
        specifier_node: Node,
        source_code: str,
        source_str: str,
        is_type_only: bool,
        re_exports: list,
        re_exports_seen: set
    ):
        """
        Process an export_specifier node.

        Handles:
        - Simple: export { X } from 'Y'
        - Renamed: export { X as Z } from 'Y'

        Args:
            specifier_node: export_specifier node
            source_code: Full source code
            source_str: Source module path
            is_type_only: Whether this is a type-only export
            re_exports: List to append results to
            re_exports_seen: Set to track duplicates
        """
        identifiers = []
        has_as = False

        for child in specifier_node.children:
            if child.type == "identifier":
                # EPIC-28: Fix UTF-8 byte offset
                source_bytes = source_code.encode('utf-8')
                name_bytes = source_bytes[child.start_byte:child.end_byte]
                name = name_bytes.decode('utf-8')
                identifiers.append(name)
            elif child.type == "as":
                has_as = True

        # Case: export { X as Y } from 'source'
        # identifiers = ['X', 'Y'], has_as = True
        if has_as and len(identifiers) == 2:
            original_name = identifiers[0]
            alias_name = identifiers[1]
            re_export_key = (source_str, alias_name, original_name)

            if re_export_key not in re_exports_seen:
                re_exports.append({
                    "symbol": alias_name,
                    "original": original_name,
                    "source": source_str,
                    "is_type": is_type_only
                })
                re_exports_seen.add(re_export_key)

        # Case: export { X } from 'source'
        # identifiers = ['X'], has_as = False
        elif not has_as and len(identifiers) == 1:
            symbol_name = identifiers[0]
            re_export_key = (source_str, symbol_name, "")

            if re_export_key not in re_exports_seen:
                re_exports.append({
                    "symbol": symbol_name,
                    "source": source_str,
                    "is_type": is_type_only
                })
                re_exports_seen.add(re_export_key)

    async def extract_imports(self, tree: Tree, source_code: str) -> list[str]:
        """
        Extract all import statements from TypeScript/JavaScript code.

        Handles:
        - Named imports: import { MyClass, MyFunction } from './models'
        - Namespace imports: import * as utils from 'lodash'
        - Default imports: import React from 'react'
        - Side-effect imports: import './styles.css'
        - Re-exports: export { MyService } from './services'
        - Type-only imports: import type { Interface } from './types' (TypeScript)
        - Type-only exports: export type { Type } from './types' (TypeScript)

        Args:
            tree: tree-sitter AST tree
            source_code: Full source code

        Returns:
            List of import references.

            Format:
            - Named import: 'module.ImportName' (e.g., './models.MyClass')
            - Namespace/default: 'module' (e.g., 'lodash')
            - Side-effect: 'module' (e.g., './styles.css')
            - Type import: 'module.TypeName' (e.g., './types.Interface')

        Example:
            ```typescript
            import { MyClass } from './models'
            import type { MyInterface } from './types'
            import * as utils from 'lodash'
            export { MyService } from './services'
            export type { MyType } from './types'
            ```

            Returns: ['./models.MyClass', './types.MyInterface', 'lodash', './services.MyService', './types.MyType']
        """
        imports = []
        imports_seen = set()  # Track to avoid duplicates from side-effect query

        try:
            # Handle both Tree and Node objects (defensive programming)
            root_node = tree.root_node if hasattr(tree, 'root_node') else tree

            # 1. Extract named imports
            cursor = QueryCursor(self.named_imports_query)
            matches = cursor.matches(root_node)

            for pattern_index, captures_dict in matches:
                source_nodes = captures_dict.get('import_source', [])
                name_nodes = captures_dict.get('import_name', [])

                if source_nodes and name_nodes:
                    source = self._extract_string_literal(source_nodes[0], source_code)
                    for name_node in name_nodes:
                        # EPIC-28: Fix UTF-8 byte offset bug
                        source_bytes = source_code.encode('utf-8')
                        name_bytes = source_bytes[name_node.start_byte:name_node.end_byte]
                        name = name_bytes.decode('utf-8')
                        import_ref = f"{source}.{name}"
                        if import_ref not in imports_seen:
                            imports.append(import_ref)
                            imports_seen.add(import_ref)

            # 2. Extract namespace imports
            cursor = QueryCursor(self.namespace_imports_query)
            matches = cursor.matches(root_node)

            for pattern_index, captures_dict in matches:
                source_nodes = captures_dict.get('import_source', [])

                if source_nodes:
                    source = self._extract_string_literal(source_nodes[0], source_code)
                    if source not in imports_seen:
                        imports.append(source)
                        imports_seen.add(source)

            # 3. Extract default imports
            cursor = QueryCursor(self.default_imports_query)
            matches = cursor.matches(root_node)

            for pattern_index, captures_dict in matches:
                source_nodes = captures_dict.get('import_source', [])

                if source_nodes:
                    source = self._extract_string_literal(source_nodes[0], source_code)
                    if source not in imports_seen:
                        imports.append(source)
                        imports_seen.add(source)

            # 4. Extract re-exports
            cursor = QueryCursor(self.re_exports_query)
            matches = cursor.matches(root_node)

            for pattern_index, captures_dict in matches:
                source_nodes = captures_dict.get('export_source', [])
                name_nodes = captures_dict.get('export_name', [])

                if source_nodes and name_nodes:
                    source = self._extract_string_literal(source_nodes[0], source_code)
                    for name_node in name_nodes:
                        # EPIC-28: Fix UTF-8 byte offset bug
                        source_bytes = source_code.encode('utf-8')
                        name_bytes = source_bytes[name_node.start_byte:name_node.end_byte]
                        name = name_bytes.decode('utf-8')
                        import_ref = f"{source}.{name}"
                        if import_ref not in imports_seen:
                            imports.append(import_ref)
                            imports_seen.add(import_ref)

            # 5. Extract side-effect imports (pure imports like "import './styles.css'")
            # For now, skip side-effect imports as the query matches all imports
            # TODO: Find a way to distinguish pure side-effect imports from imports with clauses
            # They will be added in a future iteration once we have a better query
            pass

            # 6. Extract type-only imports/exports (TypeScript)
            # CRITICAL FIX 2025-11-04: This resolves 40% isolated nodes bug
            # Uses manual AST traversal because Query syntax cannot match "type" keyword
            self._extract_type_imports_exports(root_node, source_code, imports, imports_seen)

        except Exception as e:
            self.logger.error(f"Failed to extract imports: {e}", exc_info=True)
            # Graceful degradation: return partial results

        return imports

    def _extract_call_expression(self, call_node: Node, source_code: str) -> str | None:
        """
        Extract call expression text from a call_expression node.

        Handles:
        - Direct calls: calculateTotal()
        - Method calls: this.service.fetchData()
        - Chained calls: user.getProfile().getName()
        - Super calls: super.baseMethod()

        Args:
            call_node: call_expression node
            source_code: Full source code

        Returns:
            Call reference string or None if failed to extract.

        EPIC-27 Story 27.3: Now applies cleanup to extract clean function names.
        """
        try:
            # Get the function part (before the arguments)
            if len(call_node.children) < 1:
                return None

            function_node = call_node.children[0]

            # EPIC-28: Fix UTF-8 byte offset bug
            # Tree-sitter returns BYTE offsets, but Python string slicing uses CHARACTER indices
            # With UTF-8 multi-byte chars (é, à, etc.), these don't align
            # Solution: Slice bytes, then decode
            source_bytes = source_code.encode('utf-8')
            call_bytes = source_bytes[function_node.start_byte:function_node.end_byte]
            call_text = call_bytes.decode('utf-8')

            # Clean up the text (remove whitespace/newlines)
            call_text = call_text.strip()

            # EPIC-27 Story 27.3: Apply cleanup to get clean function name
            # Example: "obj.method()" → "method", "vi.fn().mock" → "mock"
            if call_text:
                cleaned = self._clean_call_name(call_text)
                return cleaned

            return None

        except Exception as e:
            self.logger.debug(f"Failed to extract call expression: {e}")
            return None

    async def extract_calls(self, node: Node, source_code: str) -> list[str]:
        """
        Extract function/method calls from a code node.

        Handles:
        - Direct function calls: calculateTotal()
        - Method calls: this.service.fetchData()
        - Chained calls: user.getProfile().getName()
        - Constructor calls: new User()
        - Super calls: super(), super.baseMethod()
        - Async/await calls: await fetchData()
        - Arrow function calls

        Args:
            node: tree-sitter AST node (function, class, method, or any node)
            source_code: Full source code

        Returns:
            List of call references.

            Format:
            - Direct call: 'functionName'
            - Method call: 'object.method' or 'this.method'
            - Constructor: 'new ClassName' or 'ClassName'
            - Super: 'super' or 'super.method'

        Example:
            ```typescript
            function myFunction() {
                calculateTotal()
                this.service.fetchData()
                new User()
            }
            ```

            Returns: ['calculateTotal', 'this.service.fetchData', 'User']
        """
        calls = []
        calls_seen = set()  # Track to avoid duplicates

        try:
            # 1. Extract regular function/method calls
            cursor = QueryCursor(self.call_expression_query)
            matches = cursor.matches(node)

            for pattern_index, captures_dict in matches:
                call_nodes = captures_dict.get('call', [])

                for call_node in call_nodes:
                    call_ref = self._extract_call_expression(call_node, source_code)
                    # EPIC-27 Story 27.4: Filter out blacklisted framework functions
                    if call_ref and call_ref not in calls_seen and not self._is_blacklisted(call_ref):
                        calls.append(call_ref)
                        calls_seen.add(call_ref)

            # 2. Extract constructor calls (new expressions)
            cursor = QueryCursor(self.new_expression_query)
            matches = cursor.matches(node)

            for pattern_index, captures_dict in matches:
                constructor_nodes = captures_dict.get('constructor', [])

                for constructor_node in constructor_nodes:
                    # EPIC-28: Fix UTF-8 byte offset bug
                    source_bytes = source_code.encode('utf-8')
                    constructor_bytes = source_bytes[constructor_node.start_byte:constructor_node.end_byte]
                    constructor_text = constructor_bytes.decode('utf-8')
                    constructor_text = constructor_text.strip()

                    # Format: 'new ClassName' or just 'ClassName'
                    # We'll use 'ClassName' for consistency
                    if constructor_text and constructor_text not in calls_seen:
                        calls.append(constructor_text)
                        calls_seen.add(constructor_text)

        except Exception as e:
            self.logger.error(f"Failed to extract calls: {e}", exc_info=True)
            # Graceful degradation: return partial results

        return calls

    def _get_lsp_type(self, node_type: str) -> str:
        """
        Map tree-sitter node type to LSP-compliant type.

        Args:
            node_type: The tree-sitter node type (class_declaration, method_definition, etc.)

        Returns:
            LSP type string (class, method, function, interface, enum, type, module, unknown)
        """
        # Direct mapping for TypeScript/JavaScript node types
        lsp_mapping = {
            "class_declaration": "class",
            "method_definition": "method",
            "function_declaration": "function",
            "arrow_function": "function",
            "interface_declaration": "interface",
            "enum_declaration": "enum",
            "type_alias_declaration": "type",
            "module": "module",
        }

        return lsp_mapping.get(node_type, "unknown")

    async def extract_metadata(
        self,
        source_code: str,
        node: Node,
        tree: Tree
    ) -> dict[str, Any]:
        """
        Extract ALL metadata including enriched context and metrics.

        EPIC-28: This method MUST receive full file source code, not chunk source.
        Tree-sitter byte offsets are absolute and require the complete source context.
        EPIC-29: Adds re-export extraction.
        Rich Metadata (v2.0): Adds call_contexts, signature, complexity.

        Args:
            source_code: FULL FILE source code (CRITICAL: not chunk source!)
            node: tree-sitter AST node (function, class, method) from full file tree
            tree: Full file AST tree (parsed from source_code)

        Returns:
            Metadata dict with:
            {
                "imports": [...],
                "calls": [...],
                "re_exports": [...],
                "call_contexts": [{call_name, line, scope, is_conditional, ...}],
                "signature": {function_name, parameters, return_type, is_async, ...},
                "complexity": {cyclomatic, lines_of_code}
            }

        Example:
            {
                "imports": ["./models.MyClass", "lodash"],
                "calls": ["validateEmail", "createSuccess"],
                "re_exports": [
                    {"symbol": "Success", "source": "./types", "is_type": False}
                ],
                "call_contexts": [
                    {
                        "call_name": "validateEmail",
                        "line_number": 5,
                        "scope_type": "function",
                        "scope_name": "createUser",
                        "is_conditional": True,
                        "is_loop": False,
                        "is_try_catch": False,
                        "arguments_count": 1
                    }
                ],
                "signature": {
                    "function_name": "createUser",
                    "parameters": [
                        {"name": "email", "type": "string", "is_optional": False}
                    ],
                    "return_type": "Promise<User>",
                    "is_async": True,
                    "is_generator": False,
                    "decorators": []
                },
                "complexity": {
                    "cyclomatic": 3,
                    "lines_of_code": 25
                }
            }

        Note:
            Byte offsets (node.start_byte, node.end_byte) are absolute positions
            in the full source file. Using chunk source will cause misalignment
            and truncated call names.
        """
        try:
            # Extract basic metadata (existing)
            imports = await self.extract_imports(tree, source_code)
            calls = await self.extract_calls(node, source_code)
            re_exports = await self.extract_re_exports(node, source_code)

            # Extract enriched metadata (NEW)
            # Determine scope name
            scope_name = None
            for child in node.children:
                if child.type == "identifier":
                    source_bytes = source_code.encode('utf-8')
                    name_bytes = source_bytes[child.start_byte:child.end_byte]
                    scope_name = name_bytes.decode('utf-8')
                    break

            call_contexts = await self.extract_call_contexts(node, source_code, scope_name)
            signature = await self.extract_function_signature(node, source_code)

            # Calculate complexity
            cyclomatic = self.calculate_cyclomatic_complexity(node)
            source_bytes = source_code.encode('utf-8')
            node_source = source_bytes[node.start_byte:node.end_byte].decode('utf-8')
            lines_of_code = len([l for l in node_source.split('\n') if l.strip()])

            return {
                "lsp_type": self._get_lsp_type(node.type),
                "imports": imports,
                "calls": calls,
                "re_exports": re_exports,
                "call_contexts": call_contexts,
                "signature": signature,
                "complexity": {
                    "cyclomatic": cyclomatic,
                    "lines_of_code": lines_of_code
                }
            }

        except Exception as e:
            self.logger.error(f"Failed to extract enriched metadata: {e}", exc_info=True)
            # Graceful degradation: return empty metadata
            return {
                "lsp_type": self._get_lsp_type(node.type) if node else "unknown",
                "imports": [],
                "calls": [],
                "re_exports": [],
                "call_contexts": [],
                "signature": {},
                "complexity": {"cyclomatic": 0, "lines_of_code": 0}
            }

    async def extract_call_contexts(
        self,
        node: Node,
        source_code: str,
        scope_name: str = None
    ) -> list[dict]:
        """
        Extract detailed context for each function call.

        Returns list of call contexts with:
        - call_name: Function/method name
        - line_number: Line where call occurs
        - scope_type: 'function', 'class', 'method', 'global'
        - scope_name: Name of containing scope
        - is_conditional: Inside if/switch/ternary
        - is_loop: Inside for/while/do-while
        - is_try_catch: Inside try-catch block
        - arguments_count: Number of arguments passed
        """
        contexts = []

        # Extract all call expressions
        cursor = QueryCursor(self.call_expression_query)
        matches = cursor.matches(node)

        for pattern_index, captures_dict in matches:
            call_nodes = captures_dict.get('call', [])

            for call_node in call_nodes:
                call_name = self._extract_call_expression(call_node, source_code)

                if not call_name or self._is_blacklisted(call_name):
                    continue

                # Determine context by walking up parent nodes
                context = {
                    "call_name": call_name,
                    "line_number": call_node.start_point[0] + 1,
                    "scope_type": self._determine_scope_type(node),
                    "scope_name": scope_name,
                    "is_conditional": self._is_inside_conditional(call_node),
                    "is_loop": self._is_inside_loop(call_node),
                    "is_try_catch": self._is_inside_try_catch(call_node),
                    "arguments_count": self._count_arguments(call_node)
                }

                contexts.append(context)

        return contexts

    def _determine_scope_type(self, node: Node) -> str:
        """Determine scope type from node type."""
        if node.type in ("function_declaration", "arrow_function", "function"):
            return "function"
        elif node.type in ("method_definition", "method"):
            return "method"
        elif node.type in ("class_declaration", "class"):
            return "class"
        else:
            return "global"

    def _is_inside_conditional(self, node: Node) -> bool:
        """Check if node is inside if/switch/ternary."""
        current = node.parent
        while current:
            if current.type in ("if_statement", "switch_statement", "ternary_expression"):
                return True
            current = current.parent
        return False

    def _is_inside_loop(self, node: Node) -> bool:
        """Check if node is inside for/while/do-while."""
        current = node.parent
        while current:
            if current.type in ("for_statement", "for_in_statement", "for_of_statement",
                               "while_statement", "do_statement"):
                return True
            current = current.parent
        return False

    def _is_inside_try_catch(self, node: Node) -> bool:
        """Check if node is inside try-catch block."""
        current = node.parent
        while current:
            if current.type == "try_statement":
                return True
            current = current.parent
        return False

    def _count_arguments(self, call_node: Node) -> int:
        """Count number of arguments in a call expression."""
        for child in call_node.children:
            if child.type == "arguments":
                # Count non-punctuation children (commas, parens)
                return len([c for c in child.children if c.type not in (",", "(", ")")])
        return 0

    async def extract_function_signature(
        self,
        node: Node,
        source_code: str
    ) -> dict:
        """
        Extract detailed function signature.

        Returns:
        - function_name: Name of function
        - parameters: List of {name, type, is_optional, default_value}
        - return_type: Return type annotation
        - is_async: Whether function is async
        - is_generator: Whether function is generator
        - decorators: List of decorators (TypeScript/ES7)
        """
        signature = {
            "function_name": None,
            "parameters": [],
            "return_type": None,
            "is_async": False,
            "is_generator": False,
            "decorators": []
        }

        # Check if async
        for child in node.children:
            if child.type == "async":
                signature["is_async"] = True
            elif child.type == "*":
                signature["is_generator"] = True
            elif child.type == "identifier":
                # Function name
                source_bytes = source_code.encode('utf-8')
                name_bytes = source_bytes[child.start_byte:child.end_byte]
                signature["function_name"] = name_bytes.decode('utf-8')
            elif child.type == "formal_parameters":
                # Extract parameters
                signature["parameters"] = self._extract_parameters(child, source_code)
            elif child.type == "type_annotation":
                # Return type
                source_bytes = source_code.encode('utf-8')
                type_bytes = source_bytes[child.start_byte:child.end_byte]
                signature["return_type"] = type_bytes.decode('utf-8').lstrip(': ')

        return signature

    def _extract_parameters(self, params_node: Node, source_code: str) -> list[dict]:
        """Extract parameter details from formal_parameters node."""
        parameters = []
        source_bytes = source_code.encode('utf-8')

        for child in params_node.children:
            if child.type == "required_parameter" or child.type == "optional_parameter":
                param = {
                    "name": None,
                    "type": None,
                    "is_optional": child.type == "optional_parameter",
                    "default_value": None
                }

                for subchild in child.children:
                    if subchild.type == "identifier":
                        name_bytes = source_bytes[subchild.start_byte:subchild.end_byte]
                        param["name"] = name_bytes.decode('utf-8')
                    elif subchild.type == "type_annotation":
                        type_bytes = source_bytes[subchild.start_byte:subchild.end_byte]
                        param["type"] = type_bytes.decode('utf-8').lstrip(': ')

                parameters.append(param)

        return parameters

    def calculate_cyclomatic_complexity(self, node: Node) -> int:
        """
        Calculate cyclomatic complexity for a function/method.

        CC = 1 (base) + number of decision points
        Decision points: if, else if, for, while, case, catch, &&, ||, ?:
        """
        complexity = 1  # Base complexity

        # Decision point node types
        decision_nodes = {
            "if_statement", "switch_case",
            "for_statement", "for_in_statement", "for_of_statement",
            "while_statement", "do_statement",
            "catch_clause",
            "&&", "||",
            "ternary_expression"
        }

        def count_decisions(n: Node) -> int:
            count = 1 if n.type in decision_nodes else 0
            for child in n.children:
                count += count_decisions(child)
            return count

        return complexity + count_decisions(node)
