"""
File classification service for EPIC-29.

Classifies TypeScript/JavaScript files into categories:
- Regular: Standard source files
- Barrel: Re-export aggregators (index.ts with >80% re-exports)
- Config: Configuration files (vite.config.ts, etc.)
- Test: Test files (*.spec.ts, *.test.ts) - to skip
"""

import logging
from enum import Enum
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


class FileType(str, Enum):
    """File classification types."""
    REGULAR = "regular"
    POTENTIAL_BARREL = "potential_barrel"  # index.ts, needs AST confirmation
    BARREL = "barrel"  # Confirmed barrel via heuristic
    CONFIG = "config"
    TEST = "test"


class FileClassificationService:
    """
    Classify TypeScript/JavaScript files by type.

    Uses filename patterns and content heuristics to determine:
    - Whether a file is a barrel (re-export aggregator)
    - Whether a file is a config (light extraction only)
    - Whether a file is a test (skip indexing)
    """

    # Config file patterns
    CONFIG_PATTERNS = [
        "vite.config",
        "vitest.config",
        "tailwind.config",
        "webpack.config",
        "rollup.config",
        "esbuild.config",
        "tsconfig",
        "babel.config",
        ".eslintrc",
        "prettier.config",
        "jest.config",
    ]

    # Test file patterns
    TEST_PATTERNS = [
        ".spec.ts",
        ".spec.js",
        ".test.ts",
        ".test.js",
        "__tests__",
        ".spec.tsx",
        ".test.tsx",
    ]

    def classify_by_filename(self, file_path: str) -> FileType:
        """
        Classify file by filename patterns.

        Args:
            file_path: Path to file (relative or absolute)

        Returns:
            FileType enum value
        """
        path = Path(file_path)
        filename = path.name
        path_str = str(path)

        # Test files - skip indexing
        if any(pattern in path_str for pattern in self.TEST_PATTERNS):
            return FileType.TEST

        # Config files - light extraction
        if any(pattern in filename for pattern in self.CONFIG_PATTERNS):
            return FileType.CONFIG

        # Potential barrels - need AST confirmation
        if filename in ("index.ts", "index.js", "index.tsx", "index.jsx"):
            return FileType.POTENTIAL_BARREL

        # Regular source file
        return FileType.REGULAR

    async def is_barrel_heuristic(
        self,
        source_code: str,
        metadata: dict[str, Any]
    ) -> bool:
        """
        Determine if file is a barrel using heuristics.

        Heuristic: File is barrel if >80% of non-empty, non-comment lines
        are re-export statements.

        Args:
            source_code: Full file source code
            metadata: Extracted metadata with 're_exports' key

        Returns:
            True if file is a barrel, False otherwise
        """
        re_exports = metadata.get("re_exports", [])

        # No re-exports = not a barrel
        if not re_exports:
            return False

        # Count non-empty, non-comment lines
        lines = source_code.strip().split('\n')
        code_lines = [
            line for line in lines
            if line.strip() and not line.strip().startswith('//')
        ]

        total_lines = len(code_lines)

        # Empty file or only comments
        if total_lines == 0:
            return False

        # Count re-export statements (each re-export typically = 1 line)
        reexport_count = len(re_exports)

        # Heuristic: >80% re-exports
        ratio = reexport_count / total_lines

        logger.debug(
            f"Barrel heuristic: {reexport_count} re-exports / "
            f"{total_lines} code lines = {ratio:.1%}"
        )

        return ratio > 0.8

    def should_skip_file(self, file_path: str) -> bool:
        """
        Determine if file should be skipped entirely.

        Args:
            file_path: Path to file

        Returns:
            True if file should be skipped (tests, node_modules, etc.)
        """
        path_str = str(file_path)

        # Skip test files
        if self.classify_by_filename(file_path) == FileType.TEST:
            return True

        # Skip node_modules
        if "node_modules" in path_str:
            return True

        return False
