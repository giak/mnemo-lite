"""
Symbol Path Service for EPIC-11 Story 11.1.

Generates hierarchical name_path for code symbols to enable:
- Qualified symbol search (e.g., "models.User" vs "utils.User")
- Better call resolution with disambiguation
- Improved graph accuracy with qualified names
"""

import hashlib
import structlog
from pathlib import Path
from typing import Optional, List

logger = structlog.get_logger()


class SymbolPathService:
    """Generate hierarchical name_path for code symbols."""

    def generate_name_path(
        self,
        chunk_name: str,
        file_path: str,
        repository_root: str,
        parent_context: Optional[List[str]] = None,
        language: str = "python"
    ) -> str:
        """
        Generate qualified name_path.

        Examples:
        - Function: api/routes/auth.py::login → routes.auth.login
        - Method: api/models/user.py::User.validate → models.user.User.validate
        - Nested: api/services/cache.py::RedisCache.connect → services.cache.RedisCache.connect

        Args:
            chunk_name: Name of the function/class/method
            file_path: Full path to source file
            repository_root: Root directory of repository
            parent_context: List of parent class names (outermost to innermost)
            language: Programming language (python, javascript, typescript, etc.)

        Returns:
            Qualified name_path string
        """

        # 1. Extract module path from file path
        module_path = self._file_to_module_path(file_path, repository_root, language)

        # 2. Combine with parent context (for nested classes/methods)
        if parent_context:
            # Parent context: ['Outer', 'Inner'] for nested class
            full_path = f"{module_path}.{'.'.join(parent_context)}.{chunk_name}"
        else:
            full_path = f"{module_path}.{chunk_name}"

        return full_path

    def _file_to_module_path(
        self,
        file_path: str,
        repository_root: str,
        language: str = "python"
    ) -> str:
        """
        Convert file path to module path (language-aware).

        Examples:
        - Python: api/routes/auth.py → routes.auth
        - Python: api/models/user.py → models.user
        - Python: api/services/caches/redis_cache.py → services.caches.redis_cache
        - JavaScript: src/components/Button.tsx → components.Button
        - Go: pkg/models/user.go → models.user

        Args:
            file_path: Full path to source file
            repository_root: Root directory of repository
            language: Programming language

        Returns:
            Module path string (dot-separated)
        """

        # Make relative to repository root
        try:
            rel_path = Path(file_path).relative_to(repository_root)
        except ValueError:
            # File is outside repository root, use absolute path
            logger.warning(
                "File outside repository root",
                file_path=file_path,
                repository_root=repository_root
            )
            rel_path = Path(file_path)

        parts = list(rel_path.parts)

        # Language-specific prefixes to remove
        PREFIXES_TO_REMOVE = {
            "python": ["api", "src"],
            "javascript": ["src"],
            "typescript": ["src"],
            "go": ["pkg"],
            "java": ["src", "main", "java"],
            "php": ["src", "app"],
        }

        prefixes = PREFIXES_TO_REMOVE.get(language, ["api", "src"])

        # Remove known prefixes
        while parts and parts[0] in prefixes:
            parts = parts[1:]

        # Remove file extension
        if parts and parts[-1]:
            # Common extensions by language
            extensions = {
                "python": [".py"],
                "javascript": [".js", ".jsx"],
                "typescript": [".ts", ".tsx"],
                "go": [".go"],
                "java": [".java"],
                "php": [".php"],
            }

            exts = extensions.get(language, [".py", ".js", ".ts", ".go", ".java"])

            for ext in exts:
                if parts[-1].endswith(ext):
                    parts[-1] = parts[-1][:-len(ext)]
                    break

        # Remove __init__ / index (package markers)
        if parts and parts[-1] in ("__init__", "index"):
            parts = parts[:-1]

        # Join with dots
        module_path = ".".join(parts) if parts else "root"

        return module_path

    def extract_parent_context(self, chunk, all_chunks) -> List[str]:
        """
        Extract parent class names for methods in OUTERMOST → INNERMOST order.

        This ensures correct hierarchical name_path generation:
        - Outer.Inner.method (correct) vs Inner.Outer.method (wrong)

        Algorithm:
        1. Find all classes that strictly contain this chunk (by line range)
        2. Sort by range size: LARGEST first (outermost parent)
        3. Return class names in order

        Example:
            class Outer:           # Lines 1-10 (range: 9)
                class Inner:       # Lines 2-8  (range: 6)
                    def method():  # Lines 3-5  (range: 2)
                        pass

            parent_context for method = ["Outer", "Inner"]
                                          ^^^^^^   ^^^^^^
                                        outermost  innermost

        Args:
            chunk: The code chunk to find parents for
            all_chunks: All chunks in the file (to search for parents)

        Returns:
            List of parent class names in outermost-to-innermost order
        """

        parent_classes = []

        for potential_parent in all_chunks:
            if potential_parent.chunk_type not in ["class", "CLASS"]:
                continue

            # Sanity check: parent cannot be the chunk itself
            if (potential_parent.start_line == chunk.start_line and
                potential_parent.end_line == chunk.end_line):
                continue

            # STRICT CONTAINMENT: Parent MUST start BEFORE and end AFTER child
            # Using < and > (not <= and >=) to avoid boundary false positives
            is_strictly_contained = (
                potential_parent.start_line < chunk.start_line and  # Parent starts BEFORE
                potential_parent.end_line > chunk.end_line          # Parent ends AFTER
            )

            if is_strictly_contained:
                parent_classes.append(potential_parent)

        # Validate: no overlapping parents (sanity check for AST parsing errors)
        for i, parent1 in enumerate(parent_classes):
            for parent2 in parent_classes[i+1:]:
                # Parent ranges should be nested, not overlapping
                # Either parent1 contains parent2, or parent2 contains parent1
                p1_contains_p2 = (
                    parent1.start_line < parent2.start_line and
                    parent1.end_line > parent2.end_line
                )
                p2_contains_p1 = (
                    parent2.start_line < parent1.start_line and
                    parent2.end_line > parent1.end_line
                )

                if not (p1_contains_p2 or p2_contains_p1):
                    logger.warning(
                        "Overlapping parent classes detected",
                        parent1=parent1.name,
                        parent1_lines=f"{parent1.start_line}-{parent1.end_line}",
                        parent2=parent2.name,
                        parent2_lines=f"{parent2.start_line}-{parent2.end_line}",
                        chunk=chunk.name,
                        message="This may indicate AST parsing error"
                    )

        # FIX #1: Sort by range (LARGEST first = outermost parent)
        # reverse=True is CRITICAL for correct ordering
        parent_classes.sort(
            key=lambda c: (c.end_line - c.start_line),
            reverse=True  # ← FIX: LARGEST range first
        )

        return [c.name for c in parent_classes]
