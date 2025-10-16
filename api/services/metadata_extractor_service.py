"""
Code metadata extraction service for EPIC-06 Phase 1 Story 3.

Extracts rich metadata from code chunks including:
- Signature, parameters, returns, decorators
- Docstrings
- Complexity metrics (cyclomatic, LOC)
- Imports and function calls
"""

import ast
import logging
from typing import Any, Optional

from radon.complexity import cc_visit

logger = logging.getLogger(__name__)


class MetadataExtractorService:
    """
    Extract code metadata from AST nodes.

    Supports Python only in Phase 1. Extracts 9 core metadata fields:
    - signature: Full function/class signature
    - parameters: List of parameter names
    - returns: Return type annotation (if present)
    - decorators: List of decorator names
    - docstring: Function/class docstring
    - complexity.cyclomatic: Cyclomatic complexity (McCabe)
    - complexity.lines_of_code: Lines of code count
    - imports: List of imports used in chunk
    - calls: List of function calls made in chunk
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def extract_metadata(
        self,
        source_code: str,
        node: ast.AST,
        tree: ast.AST,
        language: str = "python",
        module_imports: dict[str, str] | None = None  # Perf optimization
    ) -> dict[str, Any]:
        """
        Extract metadata from AST node.

        Args:
            source_code: Full source code (for radon and ast.get_source_segment)
            node: AST node (FunctionDef, ClassDef, AsyncFunctionDef)
            tree: Full AST tree (for module-level imports)
            language: Programming language (only 'python' supported in Phase 1)

        Returns:
            Metadata dict with 9 core fields. If extraction fails for any field,
            returns None or empty list for that field (graceful degradation).

        Example:
            {
                "signature": "def calculate_total(items: List[Item]) -> float:",
                "parameters": ["items"],
                "returns": "float",
                "decorators": ["@staticmethod"],
                "docstring": "Calculate total price from items list",
                "complexity": {"cyclomatic": 3, "lines_of_code": 12},
                "imports": ["typing.List", "models.Item"],
                "calls": ["sum", "item.get_price"]
            }
        """
        if language != "python":
            # Fallback: basic metadata only for non-Python
            self.logger.warning(f"Language '{language}' not supported, returning basic metadata")
            return self._extract_basic_metadata(node)

        metadata = {}

        try:
            # Category 1: Signature & Types
            metadata.update(self._extract_signature(node, source_code))

            # Category 2: Documentation
            metadata["docstring"] = self._extract_docstring(node)

            # Category 3: Complexity
            metadata.update(self._extract_complexity(source_code, node))

            # Category 4: Dependencies
            metadata["imports"] = self._extract_imports(node, tree, module_imports)
            metadata["calls"] = self._extract_calls(node)

        except Exception as e:
            self.logger.error(f"Metadata extraction failed: {e}", exc_info=True)
            # Return partial metadata (graceful degradation)

        return metadata

    def _extract_signature(self, node: ast.AST, source_code: str) -> dict[str, Any]:
        """
        Extract signature, parameters, returns, decorators.

        Handles:
        - FunctionDef, AsyncFunctionDef
        - ClassDef (signature = class declaration)

        Returns:
            {
                "signature": str,
                "parameters": list[str],
                "returns": str | None,
                "decorators": list[str]
            }
        """
        result = {
            "signature": None,
            "parameters": [],
            "returns": None,
            "decorators": []
        }

        try:
            # Signature (full declaration line)
            result["signature"] = ast.get_source_segment(source_code, node)

            # For functions/methods
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Parameters
                result["parameters"] = [arg.arg for arg in node.args.args]

                # Return type annotation
                if node.returns:
                    result["returns"] = ast.unparse(node.returns)

                # Decorators
                result["decorators"] = [ast.unparse(dec) for dec in node.decorator_list]

            # For classes
            elif isinstance(node, ast.ClassDef):
                # Class bases (inheritance)
                if node.bases:
                    result["parameters"] = [ast.unparse(base) for base in node.bases]

                # Decorators
                result["decorators"] = [ast.unparse(dec) for dec in node.decorator_list]

        except Exception as e:
            self.logger.warning(f"Signature extraction failed: {e}")

        return result

    def _extract_docstring(self, node: ast.AST) -> Optional[str]:
        """
        Extract docstring from function/class.

        Uses ast.get_docstring() which returns the first string literal
        in the body (standard Python docstring convention).

        Returns:
            Docstring text or None if absent
        """
        try:
            return ast.get_docstring(node)
        except Exception as e:
            self.logger.warning(f"Docstring extraction failed: {e}")
            return None

    def _extract_complexity(self, source_code: str, node: ast.AST) -> dict[str, Any]:
        """
        Extract complexity metrics via radon.

        Metrics:
        - cyclomatic: Cyclomatic complexity (McCabe)
        - lines_of_code: Lines of code count

        Note: Radon requires full source code, so we extract the node's
        source segment and run radon on it.

        Returns:
            {
                "complexity": {
                    "cyclomatic": int | None,
                    "lines_of_code": int
                }
            }
        """
        result = {
            "complexity": {
                "cyclomatic": None,
                "lines_of_code": 0
            }
        }

        try:
            # Extract node source segment
            node_source = ast.get_source_segment(source_code, node)

            if node_source:
                # Lines of code (simple count)
                result["complexity"]["lines_of_code"] = len(node_source.split('\n'))

                # Cyclomatic complexity via radon
                try:
                    complexities = cc_visit(node_source)
                    if complexities:
                        # radon returns list of ComplexityVisitor objects
                        # For a single function, expect 1 result
                        cc = complexities[0]
                        result["complexity"]["cyclomatic"] = cc.complexity
                except Exception as radon_error:
                    self.logger.warning(f"Radon complexity extraction failed: {radon_error}")

        except Exception as e:
            self.logger.warning(f"Complexity extraction failed: {e}")

        return result

    def _extract_imports(
        self,
        node: ast.AST,
        tree: ast.AST,
        module_imports: dict[str, str] | None = None
    ) -> list[str]:
        """
        Extract imports used within the function/class.

        Strategy:
        1. Get all imports at module level (or use pre-extracted)
        2. Find names referenced in function/class
        3. Match imports to referenced names

        Args:
            node: AST node (function/class)
            tree: Full AST tree
            module_imports: Pre-extracted module imports (optimization)

        Limitations:
        - Does not resolve cross-file imports
        - May include unused imports (conservative approach)

        Returns:
            List of import strings (e.g., ["typing.List", "models.Item"])
        """
        imports = []

        try:
            # Step 1: Get all module-level imports
            if module_imports is None:
                # Fallback: extract from tree (backwards compatibility)
                module_imports = {}

                for module_node in ast.walk(tree):
                    if isinstance(module_node, ast.Import):
                        for alias in module_node.names:
                            name = alias.asname or alias.name
                            module_imports[name] = alias.name

                    elif isinstance(module_node, ast.ImportFrom):
                        module = module_node.module or ""
                        for alias in module_node.names:
                            name = alias.asname or alias.name
                            full_name = f"{module}.{alias.name}" if module else alias.name
                            module_imports[name] = full_name

            # Step 2: Find names referenced in node
            referenced_names = set()
            for child in ast.walk(node):
                if isinstance(child, ast.Name):
                    referenced_names.add(child.id)
                elif isinstance(child, ast.Attribute):
                    # For obj.method, get 'obj'
                    if isinstance(child.value, ast.Name):
                        referenced_names.add(child.value.id)

            # Step 3: Match imports to referenced names
            for ref in referenced_names:
                if ref in module_imports:
                    imports.append(module_imports[ref])

        except Exception as e:
            self.logger.warning(f"Imports extraction failed: {e}")

        return sorted(list(set(imports)))  # Deduplicate and sort

    def _extract_calls(self, node: ast.AST) -> list[str]:
        """
        Extract function calls made within the function/class.

        Captures:
        - Simple calls: foo()
        - Method calls: obj.foo()
        - Chained calls: obj.foo().bar()

        Limitations:
        - Does not resolve call targets (just captures names)
        - Does not follow dynamic calls (getattr, etc.)

        Returns:
            List of function call names (e.g., ["sum", "item.get_price"])
        """
        calls = []

        try:
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    # Simple call: foo()
                    if isinstance(child.func, ast.Name):
                        calls.append(child.func.id)

                    # Method call: obj.foo()
                    elif isinstance(child.func, ast.Attribute):
                        # Get method name
                        method_name = child.func.attr

                        # Try to get object name for context
                        if isinstance(child.func.value, ast.Name):
                            obj_name = child.func.value.id
                            calls.append(f"{obj_name}.{method_name}")
                        else:
                            # Just method name if object is complex
                            calls.append(method_name)

        except Exception as e:
            self.logger.warning(f"Calls extraction failed: {e}")

        return sorted(list(set(calls)))  # Deduplicate and sort

    def _extract_basic_metadata(self, node: ast.AST) -> dict[str, Any]:
        """
        Fallback for non-Python languages or when extraction fails.

        Returns minimal metadata structure with None/empty values.
        """
        return {
            "signature": None,
            "parameters": [],
            "returns": None,
            "decorators": [],
            "docstring": None,
            "complexity": {
                "cyclomatic": None,
                "lines_of_code": 0
            },
            "imports": [],
            "calls": []
        }


# Singleton instance (will be injected via dependencies if needed)
_metadata_extractor_service: Optional[MetadataExtractorService] = None


def get_metadata_extractor_service() -> MetadataExtractorService:
    """Get singleton instance of MetadataExtractorService."""
    global _metadata_extractor_service
    if _metadata_extractor_service is None:
        _metadata_extractor_service = MetadataExtractorService()
    return _metadata_extractor_service
