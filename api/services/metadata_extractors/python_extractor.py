"""
Python metadata extractor using tree-sitter.

EPIC-29 Story 29.1: Python import extraction.
EPIC-29 Story 29.1: Python call extraction.
"""

import logging
from typing import Any
from tree_sitter import Node, Tree, Query, QueryCursor
from tree_sitter_language_pack import get_language


logger = logging.getLogger(__name__)


class PythonMetadataExtractor:
    """
    Extract metadata from Python using tree-sitter queries.

    Supports:
    - Import statements (import X, from X import Y)
    - Function calls
    - Decorators
    - Type hints
    - Async/await patterns
    """

    def __init__(self):
        """Initialize Python language and queries."""
        self.language = get_language("python")
        self.language_name = "python"
        self.logger = logging.getLogger(__name__)

        # Import extraction queries
        self.basic_import_query = Query(
            self.language,
            "(import_statement name: (dotted_name) @import_name)"
        )

        self.from_import_query = Query(
            self.language,
            "(import_from_statement module_name: (dotted_name) @module_name name: (dotted_name) @import_name)"
        )

        self.from_import_alias_query = Query(
            self.language,
            "(import_from_statement module_name: (dotted_name) @module_name name: (aliased_import name: (dotted_name) @import_name))"
        )

        # Call extraction query
        self.call_query = Query(
            self.language,
            "(call function: (_) @call_function)"
        )

        # Decorator extraction query
        self.decorator_query = Query(
            self.language,
            """
            (decorated_definition
              (decorator) @decorator)
            """
        )

    def _extract_module_imports(
        self,
        query: Query,
        root_node: Node,
        source_bytes: bytes
    ) -> list[str]:
        """
        Extract from imports using a tree-sitter query.

        Args:
            query: Tree-sitter query for from imports
            root_node: Root AST node
            source_bytes: Source code as bytes

        Returns:
            List of qualified import references (e.g., ['pathlib.Path'])
        """
        imports = []
        cursor = QueryCursor(query)
        matches = cursor.matches(root_node)

        for pattern_index, captures_dict in matches:
            module_nodes = captures_dict.get('module_name', [])
            import_nodes = captures_dict.get('import_name', [])

            for module_node, import_node in zip(module_nodes, import_nodes):
                module_name = source_bytes[module_node.start_byte:module_node.end_byte].decode("utf8")
                import_name = source_bytes[import_node.start_byte:import_node.end_byte].decode("utf8")
                imports.append(f"{module_name}.{import_name}")

        return imports

    async def extract_imports(self, tree: Tree, source_code: str) -> list[str]:
        """
        Extract import statements from Python code.

        Args:
            tree: tree-sitter AST tree
            source_code: Full source code (for byte range extraction)

        Returns:
            List of import references (e.g., ['os', 'pathlib.Path'])
        """
        # Input validation
        if not tree or not source_code:
            self.logger.warning("Empty tree or source_code provided to extract_imports")
            return []

        imports = []

        try:
            source_bytes = bytes(source_code, "utf8")
        except UnicodeDecodeError as e:
            self.logger.error(f"Failed to encode source code as UTF-8: {e}")
            return []

        root_node = tree.root_node

        # Extract basic imports (import X)
        cursor = QueryCursor(self.basic_import_query)
        matches = cursor.matches(root_node)
        for pattern_index, captures_dict in matches:
            import_nodes = captures_dict.get('import_name', [])
            for node in import_nodes:
                import_text = source_bytes[node.start_byte:node.end_byte].decode("utf8")
                imports.append(import_text)

        # Extract from imports (from X import Y)
        imports.extend(self._extract_module_imports(
            self.from_import_query,
            root_node,
            source_bytes
        ))

        # Extract from imports with aliases (from X import Y as Z)
        imports.extend(self._extract_module_imports(
            self.from_import_alias_query,
            root_node,
            source_bytes
        ))

        return imports

    async def extract_calls(self, node: Node, source_code: str) -> list[str]:
        """
        Extract function/method calls from a code node.

        Args:
            node: tree-sitter AST node (function, class, method)
            source_code: Full source code (for byte range extraction)

        Returns:
            List of call references (e.g., ['calculate_total', 'service.fetch_data'])
        """
        # Input validation
        if not node or not source_code:
            self.logger.warning("Empty node or source_code provided to extract_calls")
            return []

        calls = []
        try:
            source_bytes = bytes(source_code, "utf8")
        except UnicodeDecodeError as e:
            self.logger.error(f"Failed to encode source code as UTF-8: {e}")
            return []
        cursor = QueryCursor(self.call_query)

        # Extract all calls within the node
        matches = cursor.matches(node)
        for pattern_index, captures_dict in matches:
            call_nodes = captures_dict.get('call_function', [])
            for call_node in call_nodes:
                call_text = self._extract_call_name(call_node, source_bytes)
                if call_text:
                    calls.append(call_text)

        return list(set(calls))  # Deduplicate

    def _extract_call_name(self, node: Node, source_bytes: bytes) -> str:
        """
        Extract the full call name from a call node.

        Handles:
        - Simple calls: function()
        - Method calls: object.method()
        - Chained calls: obj.a.b.method()
        """
        if node.type == "identifier":
            return source_bytes[node.start_byte:node.end_byte].decode("utf8")

        elif node.type == "attribute":
            # For attribute access (obj.method), build full path
            parts = []
            current = node
            while current and current.type == "attribute":
                # Get the attribute name (rightmost part)
                attr_node = current.child_by_field_name("attribute")
                if attr_node:
                    parts.insert(0, source_bytes[attr_node.start_byte:attr_node.end_byte].decode("utf8"))

                # Move to the object (left side)
                current = current.child_by_field_name("object")

            # Get the base object name
            if current and current.type == "identifier":
                parts.insert(0, source_bytes[current.start_byte:current.end_byte].decode("utf8"))

            return ".".join(parts) if parts else ""

        return ""

    async def extract_decorators(self, node: Node, source_code: str) -> list[str]:
        """
        Extract decorator names from a node.

        Args:
            node: tree-sitter AST node
            source_code: Full source code

        Returns:
            List of decorator names (e.g., ['dataclass', 'property'])
        """
        decorators = []
        source_bytes = bytes(source_code, "utf8")
        cursor = QueryCursor(self.decorator_query)

        # Extract decorators from this node and all descendants
        matches = cursor.matches(node)
        for pattern_index, captures_dict in matches:
            decorator_nodes = captures_dict.get('decorator', [])
            for decorator_node in decorator_nodes:
                # Decorator node includes '@', get the name after it
                decorator_text = source_bytes[decorator_node.start_byte:decorator_node.end_byte].decode("utf8")
                # Remove '@' and get just the name (handle @decorator and @decorator())
                decorator_name = decorator_text.lstrip("@").split("(")[0].strip()
                decorators.append(decorator_name)

        return decorators

    def _is_async_function(self, node: Node) -> bool:
        """
        Check if a function node is async.

        Args:
            node: tree-sitter AST node

        Returns:
            True if function is async, False otherwise
        """
        # Check decorated_definition wrapping async function
        if node.type == "decorated_definition":
            definition = node.child_by_field_name("definition")
            if definition and definition.type == "function_definition":
                # Check if 'async' keyword is present
                for child in definition.children:
                    if child.type == "async":
                        return True

        # Check direct function_definition
        elif node.type == "function_definition":
            for child in node.children:
                if child.type == "async":
                    return True

        return False

    async def extract_metadata(
        self,
        source_code: str,
        node: Node,
        tree: Tree
    ) -> dict[str, Any]:
        """
        Extract all metadata (imports + calls + decorators + async) from a code node.

        Args:
            source_code: Full source code
            node: tree-sitter AST node
            tree: Full AST tree

        Returns:
            Metadata dict with: {"imports": [...], "calls": [...], "decorators": [...], "is_async": bool}
        """
        imports = await self.extract_imports(tree, source_code)
        calls = await self.extract_calls(node, source_code)
        decorators = await self.extract_decorators(node, source_code)
        is_async = self._is_async_function(node)

        return {
            "imports": imports,
            "calls": calls,
            "decorators": decorators,
            "is_async": is_async
        }
