"""
ProjectScanner utility for scanning project directories (EPIC-23 Story 23.5).

Scans project directories to find code files for indexing, respecting .gitignore rules.
"""

import logging
from pathlib import Path
from typing import List, Optional, Set

try:
    import pathspec
    PATHSPEC_AVAILABLE = True
except ImportError:
    PATHSPEC_AVAILABLE = False

from services.code_indexing_service import FileInput

logger = logging.getLogger(__name__)


class ProjectScanner:
    """
    Scan project directory for code files.

    Features:
    - Supports 15+ programming languages
    - Respects .gitignore rules (via pathspec library)
    - Filters by supported file extensions
    - Handles symlinks and permission errors gracefully
    - Hard limit: 10,000 files (prevents memory issues)
    """

    # Supported file extensions (from CodeIndexingService)
    SUPPORTED_EXTENSIONS: Set[str] = {
        ".py",      # Python
        ".js",      # JavaScript
        ".ts",      # TypeScript
        ".jsx",     # React JavaScript
        ".tsx",     # React TypeScript
        ".go",      # Go
        ".rs",      # Rust
        ".java",    # Java
        ".c",       # C
        ".cpp",     # C++
        ".cc",      # C++
        ".cxx",     # C++
        ".h",       # C header
        ".hpp",     # C++ header
        ".rb",      # Ruby
        ".php",     # PHP
        ".cs",      # C#
        ".swift",   # Swift
        ".kt",      # Kotlin
        ".scala",   # Scala
    }

    # Hard limit to prevent memory issues with very large projects
    MAX_FILES = 10_000

    # Warn threshold
    WARN_FILES = 5_000

    def __init__(self):
        """Initialize ProjectScanner."""
        self.logger = logging.getLogger(__name__)

    async def scan(
        self,
        project_path: str,
        respect_gitignore: bool = True
    ) -> List[FileInput]:
        """
        Scan project directory and return list of code files.

        Args:
            project_path: Path to project root directory
            respect_gitignore: If True, skip files matching .gitignore patterns

        Returns:
            List[FileInput]: List of code files ready for indexing

        Raises:
            FileNotFoundError: If project_path doesn't exist
            PermissionError: If project_path is not readable
            ValueError: If project has >10,000 files
        """
        project_root = Path(project_path)

        # Validate project path
        if not project_root.exists():
            raise FileNotFoundError(f"Project path not found: {project_path}")

        if not project_root.is_dir():
            raise ValueError(f"Project path is not a directory: {project_path}")

        # Load .gitignore patterns if requested
        gitignore_spec = None
        if respect_gitignore:
            gitignore_spec = self._load_gitignore(project_root)

        # Scan for files
        files: List[FileInput] = []
        scanned_count = 0
        skipped_gitignore = 0
        skipped_extension = 0
        skipped_error = 0

        self.logger.info(f"Scanning project: {project_path}")

        # Walk directory tree
        try:
            for file_path in project_root.rglob("*"):
                scanned_count += 1

                # Check hard limit
                if len(files) >= self.MAX_FILES:
                    raise ValueError(
                        f"Project exceeds maximum file limit ({self.MAX_FILES} files). "
                        f"Consider indexing subdirectories separately."
                    )

                # Warn at threshold
                if len(files) == self.WARN_FILES:
                    self.logger.warning(
                        f"Project has {self.WARN_FILES}+ files - indexing may take several minutes"
                    )

                # Skip directories
                if not file_path.is_file():
                    continue

                # Check if gitignored
                if gitignore_spec and self._is_gitignored(file_path, project_root, gitignore_spec):
                    skipped_gitignore += 1
                    continue

                # Check supported extension
                if file_path.suffix not in self.SUPPORTED_EXTENSIONS:
                    skipped_extension += 1
                    continue

                # Read file content
                try:
                    # Resolve symlinks
                    resolved_path = file_path.resolve()

                    # Read as UTF-8 (code files should be text)
                    content = resolved_path.read_text(encoding='utf-8')

                    files.append(FileInput(
                        path=str(file_path),
                        content=content,
                        language=None  # Auto-detect in indexing service
                    ))

                except (UnicodeDecodeError, PermissionError) as e:
                    # Skip binary files or permission-denied files
                    self.logger.debug(f"Skipped {file_path}: {e}")
                    skipped_error += 1
                    continue

                except Exception as e:
                    # Unexpected error - log but continue
                    self.logger.warning(f"Error reading {file_path}: {e}")
                    skipped_error += 1
                    continue

        except RecursionError:
            # Circular symlink or very deep directory structure
            raise ValueError(
                f"Directory structure too deep or circular symlink detected in {project_path}"
            )

        # Log summary
        self.logger.info(
            f"Scan complete: {len(files)} files found "
            f"(scanned: {scanned_count}, "
            f"gitignored: {skipped_gitignore}, "
            f"unsupported: {skipped_extension}, "
            f"errors: {skipped_error})"
        )

        return files

    def _load_gitignore(self, project_root: Path) -> Optional['pathspec.PathSpec']:
        """
        Load .gitignore patterns from project root.

        Args:
            project_root: Project root directory

        Returns:
            PathSpec object or None if .gitignore not found or pathspec unavailable
        """
        if not PATHSPEC_AVAILABLE:
            self.logger.warning(
                "pathspec library not available - .gitignore will not be respected. "
                "Install with: pip install pathspec"
            )
            return None

        gitignore_path = project_root / ".gitignore"

        if not gitignore_path.exists():
            self.logger.debug(f"No .gitignore found in {project_root}")
            return None

        try:
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                patterns = f.read().splitlines()

            # Parse .gitignore patterns
            spec = pathspec.PathSpec.from_lines('gitwildmatch', patterns)

            self.logger.debug(
                f"Loaded {len(patterns)} .gitignore patterns from {gitignore_path}"
            )

            return spec

        except Exception as e:
            self.logger.warning(f"Failed to load .gitignore: {e}")
            return None

    def _is_gitignored(
        self,
        file_path: Path,
        project_root: Path,
        gitignore_spec: 'pathspec.PathSpec'
    ) -> bool:
        """
        Check if file matches .gitignore patterns.

        Args:
            file_path: File to check
            project_root: Project root directory
            gitignore_spec: PathSpec object with .gitignore patterns

        Returns:
            True if file should be ignored
        """
        try:
            # Get path relative to project root
            relative_path = file_path.relative_to(project_root)

            # Check if matches any pattern
            return gitignore_spec.match_file(str(relative_path))

        except ValueError:
            # File is not relative to project_root (shouldn't happen)
            return False
