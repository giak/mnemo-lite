"""
Base protocol for metadata extractors.

EPIC-26: Protocol-based dependency injection pattern.
Each language implements this protocol to provide metadata extraction.
"""

from typing import Protocol, Any
from tree_sitter import Node, Tree


class MetadataExtractor(Protocol):
    """
    Protocol for language-specific metadata extractors.

    DIP Pattern: MetadataExtractorService depends on abstraction (Protocol),
    not concrete implementations (PythonExtractor, TypeScriptExtractor).

    This allows easy addition of new languages without modifying existing code.
    """

    async def extract_imports(self, tree: Tree, source_code: str) -> list[str]:
        """
        Extract import/require statements from code.

        Args:
            tree: tree-sitter AST tree
            source_code: Full source code (for byte range extraction)

        Returns:
            List of import references (e.g., ['./models.MyClass', 'lodash'])

        Example (TypeScript):
            import { MyClass } from './models'
            → Returns: ['./models.MyClass']
        """
        ...

    async def extract_calls(self, node: Node, source_code: str) -> list[str]:
        """
        Extract function/method calls from a code node.

        Args:
            node: tree-sitter AST node (function, class, method)
            source_code: Full source code (for byte range extraction)

        Returns:
            List of call references (e.g., ['calculateTotal', 'service.fetchData'])

        Example (TypeScript):
            const result = calculateTotal(items)
            this.service.fetchData()
            → Returns: ['calculateTotal', 'service.fetchData']
        """
        ...

    async def extract_metadata(
        self,
        source_code: str,
        node: Node,
        tree: Tree
    ) -> dict[str, Any]:
        """
        Extract all metadata (imports + calls + other) from a code node.

        Args:
            source_code: Full source code
            node: tree-sitter AST node
            tree: Full AST tree

        Returns:
            Metadata dict with at minimum: {"imports": [...], "calls": [...]}

        This is the main entry point called by MetadataExtractorService.
        """
        ...
