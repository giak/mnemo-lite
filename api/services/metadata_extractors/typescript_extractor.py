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

    def __init__(self):
        """Initialize TypeScript language and queries."""
        self.language = get_language("typescript")
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
        text = source_code[node.start_byte:node.end_byte]
        # Remove quotes (single or double)
        if (text.startswith("'") and text.endswith("'")) or \
           (text.startswith('"') and text.endswith('"')):
            return text[1:-1]
        return text

    async def extract_imports(self, tree: Tree, source_code: str) -> list[str]:
        """
        Extract all import statements from TypeScript/JavaScript code.

        Handles:
        - Named imports: import { MyClass, MyFunction } from './models'
        - Namespace imports: import * as utils from 'lodash'
        - Default imports: import React from 'react'
        - Side-effect imports: import './styles.css'
        - Re-exports: export { MyService } from './services'

        Args:
            tree: tree-sitter AST tree
            source_code: Full source code

        Returns:
            List of import references.

            Format:
            - Named import: 'module.ImportName' (e.g., './models.MyClass')
            - Namespace/default: 'module' (e.g., 'lodash')
            - Side-effect: 'module' (e.g., './styles.css')

        Example:
            ```typescript
            import { MyClass } from './models'
            import * as utils from 'lodash'
            export { MyService } from './services'
            ```

            Returns: ['./models.MyClass', 'lodash', './services.MyService']
        """
        imports = []
        imports_seen = set()  # Track to avoid duplicates from side-effect query

        try:
            # 1. Extract named imports
            cursor = QueryCursor(self.named_imports_query)
            matches = cursor.matches(tree.root_node)

            for pattern_index, captures_dict in matches:
                source_nodes = captures_dict.get('import_source', [])
                name_nodes = captures_dict.get('import_name', [])

                if source_nodes and name_nodes:
                    source = self._extract_string_literal(source_nodes[0], source_code)
                    for name_node in name_nodes:
                        name = source_code[name_node.start_byte:name_node.end_byte]
                        import_ref = f"{source}.{name}"
                        if import_ref not in imports_seen:
                            imports.append(import_ref)
                            imports_seen.add(import_ref)

            # 2. Extract namespace imports
            cursor = QueryCursor(self.namespace_imports_query)
            matches = cursor.matches(tree.root_node)

            for pattern_index, captures_dict in matches:
                source_nodes = captures_dict.get('import_source', [])

                if source_nodes:
                    source = self._extract_string_literal(source_nodes[0], source_code)
                    if source not in imports_seen:
                        imports.append(source)
                        imports_seen.add(source)

            # 3. Extract default imports
            cursor = QueryCursor(self.default_imports_query)
            matches = cursor.matches(tree.root_node)

            for pattern_index, captures_dict in matches:
                source_nodes = captures_dict.get('import_source', [])

                if source_nodes:
                    source = self._extract_string_literal(source_nodes[0], source_code)
                    if source not in imports_seen:
                        imports.append(source)
                        imports_seen.add(source)

            # 4. Extract re-exports
            cursor = QueryCursor(self.re_exports_query)
            matches = cursor.matches(tree.root_node)

            for pattern_index, captures_dict in matches:
                source_nodes = captures_dict.get('export_source', [])
                name_nodes = captures_dict.get('export_name', [])

                if source_nodes and name_nodes:
                    source = self._extract_string_literal(source_nodes[0], source_code)
                    for name_node in name_nodes:
                        name = source_code[name_node.start_byte:name_node.end_byte]
                        import_ref = f"{source}.{name}"
                        if import_ref not in imports_seen:
                            imports.append(import_ref)
                            imports_seen.add(import_ref)

            # 5. Extract side-effect imports (pure imports like "import './styles.css'")
            # For now, skip side-effect imports as the query matches all imports
            # TODO: Find a way to distinguish pure side-effect imports from imports with clauses
            # They will be added in a future iteration once we have a better query
            pass

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
        """
        try:
            # Get the function part (before the arguments)
            if len(call_node.children) < 1:
                return None

            function_node = call_node.children[0]

            # Extract the call text
            call_text = source_code[function_node.start_byte:function_node.end_byte]

            # Clean up the text (remove whitespace/newlines)
            call_text = call_text.strip()

            return call_text if call_text else None

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
                    if call_ref and call_ref not in calls_seen:
                        calls.append(call_ref)
                        calls_seen.add(call_ref)

            # 2. Extract constructor calls (new expressions)
            cursor = QueryCursor(self.new_expression_query)
            matches = cursor.matches(node)

            for pattern_index, captures_dict in matches:
                constructor_nodes = captures_dict.get('constructor', [])

                for constructor_node in constructor_nodes:
                    constructor_text = source_code[constructor_node.start_byte:constructor_node.end_byte]
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

    async def extract_metadata(
        self,
        source_code: str,
        node: Node,
        tree: Tree
    ) -> dict[str, Any]:
        """
        Extract all metadata from TypeScript/JavaScript code.

        Args:
            source_code: Full source code
            node: tree-sitter AST node (function, class, method)
            tree: Full AST tree

        Returns:
            Metadata dict with imports and calls.

        Example:
            {
                "imports": ["./models.MyClass", "lodash"],
                "calls": []  # TODO: Story 26.2
            }
        """
        try:
            # Extract imports from full tree
            imports = await self.extract_imports(tree, source_code)

            # Extract calls from specific node (TODO: Story 26.2)
            calls = await self.extract_calls(node, source_code)

            return {
                "imports": imports,
                "calls": calls,
            }

        except Exception as e:
            self.logger.error(f"Failed to extract metadata: {e}", exc_info=True)
            # Graceful degradation: return empty metadata
            return {
                "imports": [],
                "calls": [],
            }
