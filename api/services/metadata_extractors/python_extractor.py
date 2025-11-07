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

        # Type hint extraction queries
        self.function_type_query = Query(
            self.language,
            """
            (function_definition
              parameters: (parameters
                (typed_parameter
                  type: (_) @param_type))
              return_type: (type) @return_type)
            """
        )

        self.class_attribute_type_query = Query(
            self.language,
            """
            (class_definition
              body: (block
                (expression_statement
                  (assignment
                    left: (identifier) @attr_name
                    type: (type) @attr_type))))
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

    async def extract_type_hints(self, node: Node, source_code: str) -> dict[str, Any]:
        """
        Extract type hints from function signatures or class attributes.

        Args:
            node: tree-sitter AST node
            source_code: Full source code

        Returns:
            Dict with type hint information:
            - For functions: {"parameters": [...], "return_type": "..."}
            - For classes: {"attributes": {"name": "type", ...}}
        """
        type_hints = {}
        source_bytes = bytes(source_code, "utf8")

        # Extract function type hints
        if node.type == "function_definition" or (node.type == "decorated_definition" and
           node.child_by_field_name("definition") and
           node.child_by_field_name("definition").type == "function_definition"):

            func_node = node if node.type == "function_definition" else node.child_by_field_name("definition")

            # Get return type
            return_type_node = func_node.child_by_field_name("return_type")
            if return_type_node:
                return_type_text = source_bytes[return_type_node.start_byte:return_type_node.end_byte].decode("utf8")
                type_hints["return_type"] = return_type_text.strip()

            # Get parameter types
            parameters_node = func_node.child_by_field_name("parameters")
            if parameters_node:
                param_types = []
                for child in parameters_node.children:
                    if child.type == "typed_parameter":
                        # typed_parameter structure: identifier ":" type
                        # Get the identifier (first child) and type (last child)
                        param_name_node = None
                        param_type_node = None

                        for sub_child in child.children:
                            if sub_child.type == "identifier":
                                param_name_node = sub_child
                            elif sub_child.type == "type":
                                param_type_node = sub_child

                        if param_name_node and param_type_node:
                            param_name = source_bytes[param_name_node.start_byte:param_name_node.end_byte].decode("utf8")
                            param_type = source_bytes[param_type_node.start_byte:param_type_node.end_byte].decode("utf8")
                            param_types.append({"name": param_name, "type": param_type})

                if param_types:
                    type_hints["parameters"] = param_types

        # Extract class attribute type hints
        elif node.type == "class_definition" or (node.type == "decorated_definition" and
             node.child_by_field_name("definition") and
             node.child_by_field_name("definition").type == "class_definition"):

            class_node = node if node.type == "class_definition" else node.child_by_field_name("definition")
            body_node = class_node.child_by_field_name("body")

            if body_node:
                attributes = {}
                for child in body_node.children:
                    # Look for annotated assignments (name: type = value)
                    if child.type == "expression_statement":
                        for expr_child in child.children:
                            if expr_child.type == "assignment":
                                # Get attribute name and type
                                left_node = expr_child.child_by_field_name("left")
                                type_node = expr_child.child_by_field_name("type")

                                if left_node and type_node:
                                    attr_name = source_bytes[left_node.start_byte:left_node.end_byte].decode("utf8")
                                    attr_type = source_bytes[type_node.start_byte:type_node.end_byte].decode("utf8")
                                    attributes[attr_name] = attr_type

                if attributes:
                    type_hints["attributes"] = attributes

        return type_hints

    async def extract_metadata(
        self,
        source_code: str,
        node: Node,
        tree: Tree
    ) -> dict[str, Any]:
        """
        Extract all metadata from a code node.

        Args:
            source_code: Full source code
            node: tree-sitter AST node
            tree: Full AST tree

        Returns:
            Metadata dict with: imports, calls, decorators, is_async, type_hints
        """
        imports = await self.extract_imports(tree, source_code)
        calls = await self.extract_calls(node, source_code)
        decorators = await self.extract_decorators(node, source_code)
        is_async = self._is_async_function(node)
        type_hints = await self.extract_type_hints(node, source_code)

        return {
            "imports": imports,
            "calls": calls,
            "decorators": decorators,
            "is_async": is_async,
            "type_hints": type_hints
        }
