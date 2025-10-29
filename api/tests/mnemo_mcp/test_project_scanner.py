"""
Unit tests for ProjectScanner (EPIC-23 Story 23.5).

Tests cover:
- Scanning projects with supported files
- Respecting .gitignore patterns
- Skipping non-code files
- Handling symlinks and permission errors
- Edge cases (empty projects, large projects, invalid paths)
"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock

from mnemo_mcp.utils.project_scanner import ProjectScanner


@pytest.fixture
def temp_project():
    """Create a temporary project directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Create some code files
        (project_root / "main.py").write_text("print('hello')")
        (project_root / "utils.js").write_text("console.log('hello')")
        (project_root / "config.rs").write_text("fn main() {}")

        # Create subdirectory with files
        subdir = project_root / "src"
        subdir.mkdir()
        (subdir / "helper.py").write_text("def helper(): pass")
        (subdir / "api.ts").write_text("export const api = () => {}")

        # Create non-code files (should be skipped)
        (project_root / "README.md").write_text("# Project")
        (project_root / "data.json").write_text("{}")
        (project_root / ".env").write_text("KEY=value")

        yield project_root


@pytest.fixture
def temp_project_with_gitignore():
    """Create temporary project with .gitignore."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Create code files
        (project_root / "main.py").write_text("print('hello')")
        (project_root / "config.py").write_text("CONFIG = {}")

        # Create gitignored files
        (project_root / "secret.py").write_text("API_KEY = 'xxx'")
        build_dir = project_root / "build"
        build_dir.mkdir()
        (build_dir / "output.py").write_text("# generated")

        # Create .gitignore
        gitignore = project_root / ".gitignore"
        gitignore.write_text("secret.py\nbuild/\n")

        yield project_root


@pytest.mark.asyncio
async def test_scan_project_with_supported_files(temp_project):
    """Test scanning project returns only supported code files."""
    scanner = ProjectScanner()

    files = await scanner.scan(str(temp_project), respect_gitignore=False)

    # Should find 5 code files (main.py, utils.js, config.rs, helper.py, api.ts)
    assert len(files) == 5

    # Check file paths
    file_paths = {f.path for f in files}
    assert any("main.py" in p for p in file_paths)
    assert any("utils.js" in p for p in file_paths)
    assert any("config.rs" in p for p in file_paths)
    assert any("helper.py" in p for p in file_paths)
    assert any("api.ts" in p for p in file_paths)

    # Non-code files should be skipped
    assert not any("README.md" in p for p in file_paths)
    assert not any("data.json" in p for p in file_paths)
    assert not any(".env" in p for p in file_paths)


@pytest.mark.asyncio
async def test_scan_respects_gitignore(temp_project_with_gitignore):
    """Test that .gitignore patterns are respected."""
    scanner = ProjectScanner()

    # With gitignore
    files_with_gitignore = await scanner.scan(
        str(temp_project_with_gitignore),
        respect_gitignore=True
    )

    # Should find 2 files (main.py, config.py) - secret.py and build/ ignored
    assert len(files_with_gitignore) == 2
    file_paths = {f.path for f in files_with_gitignore}
    assert any("main.py" in p for p in file_paths)
    assert any("config.py" in p for p in file_paths)
    assert not any("secret.py" in p for p in file_paths)
    assert not any("build" in p for p in file_paths)

    # Without gitignore
    files_without_gitignore = await scanner.scan(
        str(temp_project_with_gitignore),
        respect_gitignore=False
    )

    # Should find 4 files (including secret.py and build/output.py)
    assert len(files_without_gitignore) == 4


@pytest.mark.asyncio
async def test_scan_skips_non_code_files(temp_project):
    """Test that non-code files are skipped."""
    scanner = ProjectScanner()

    files = await scanner.scan(str(temp_project), respect_gitignore=False)

    # No markdown, json, or env files
    file_extensions = {Path(f.path).suffix for f in files}
    assert ".md" not in file_extensions
    assert ".json" not in file_extensions
    assert ".env" not in file_extensions

    # Only code extensions
    expected_extensions = {".py", ".js", ".rs", ".ts"}
    assert file_extensions.issubset(expected_extensions)


@pytest.mark.asyncio
async def test_scan_handles_symlinks():
    """Test that symlinks are handled gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Create real file
        real_file = project_root / "real.py"
        real_file.write_text("# real file")

        # Create symlink
        symlink_file = project_root / "link.py"
        symlink_file.symlink_to(real_file)

        scanner = ProjectScanner()
        files = await scanner.scan(str(project_root), respect_gitignore=False)

        # Should find both (symlink resolves to real file)
        assert len(files) >= 1


@pytest.mark.asyncio
async def test_scan_empty_project():
    """Test scanning empty project returns empty list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        scanner = ProjectScanner()
        files = await scanner.scan(str(project_root), respect_gitignore=False)

        assert len(files) == 0


@pytest.mark.asyncio
async def test_scan_large_project_warning():
    """Test that large projects (>5000 files) trigger warning."""
    scanner = ProjectScanner()

    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Create exactly WARN_FILES files to trigger warning
        for i in range(ProjectScanner.WARN_FILES):
            (project_root / f"file_{i}.py").write_text(f"# file {i}")

        with patch('mnemo_mcp.utils.project_scanner.logger') as mock_logger:
            files = await scanner.scan(str(project_root), respect_gitignore=False)

            # Should log warning at threshold
            assert mock_logger.warning.called
            assert "5,000+ files" in str(mock_logger.warning.call_args)


@pytest.mark.asyncio
async def test_scan_exceeds_max_files_limit():
    """Test that projects exceeding MAX_FILES raise ValueError."""
    scanner = ProjectScanner()

    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Create MAX_FILES + 1 files to exceed limit
        for i in range(ProjectScanner.MAX_FILES + 1):
            (project_root / f"file_{i}.py").write_text(f"# file {i}")

        with pytest.raises(ValueError) as exc_info:
            await scanner.scan(str(project_root), respect_gitignore=False)

        assert "exceeds maximum file limit" in str(exc_info.value)
        assert str(ProjectScanner.MAX_FILES) in str(exc_info.value)


@pytest.mark.asyncio
async def test_scan_invalid_path():
    """Test that invalid project path raises FileNotFoundError."""
    scanner = ProjectScanner()

    with pytest.raises(FileNotFoundError):
        await scanner.scan("/nonexistent/path/to/project", respect_gitignore=False)


@pytest.mark.asyncio
async def test_scan_file_not_directory():
    """Test that passing a file instead of directory raises ValueError."""
    with tempfile.TemporaryFile() as tmpfile:
        scanner = ProjectScanner()

        with pytest.raises(ValueError) as exc_info:
            await scanner.scan(tmpfile.name, respect_gitignore=False)

        assert "not a directory" in str(exc_info.value)
