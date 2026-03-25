"""
Tests for ProjectScanner Markdown support.

Tests that .md files are scanned and included in indexing.
"""

from pathlib import Path

import pytest

from mnemo_mcp.utils.project_scanner import ProjectScanner


@pytest.mark.asyncio
async def test_scan_finds_markdown_files(tmp_path):
    """Test that .md files are included in scan results."""
    (tmp_path / "README.md").write_text("# Project\n\nDescription.")
    (tmp_path / "KERNEL.md").write_text("## Loi I\n\nContenu.")
    (tmp_path / "code.py").write_text("print('hello')")

    scanner = ProjectScanner()
    files = await scanner.scan(str(tmp_path), respect_gitignore=False)

    extensions = {Path(f.path).suffix for f in files}
    assert ".md" in extensions, "Markdown files should be scanned"
    assert ".py" in extensions, "Python files should still be scanned"

    md_files = [f for f in files if f.path.endswith(".md")]
    assert len(md_files) == 2, f"Expected 2 .md files, got {len(md_files)}"


@pytest.mark.asyncio
async def test_scan_markdown_in_subdirectories(tmp_path):
    """Test that .md files in subdirectories are found."""
    (tmp_path / "doc").mkdir()
    (tmp_path / "doc" / "VISION.md").write_text("# Vision")
    (tmp_path / "doc" / "SYNTHESE.md").write_text("# Synthèse")
    (tmp_path / "runtime").mkdir()
    (tmp_path / "runtime" / "apex.md").write_text("# Apex")

    scanner = ProjectScanner()
    files = await scanner.scan(str(tmp_path), respect_gitignore=False)

    md_files = [f for f in files if f.path.endswith(".md")]
    assert len(md_files) == 3


@pytest.mark.asyncio
async def test_scan_markdown_content_preserved(tmp_path):
    """Test that markdown file content is read correctly."""
    content = "# KERNEL\n\n## Section I\n\nContenu important."
    (tmp_path / "KERNEL.md").write_text(content)

    scanner = ProjectScanner()
    files = await scanner.scan(str(tmp_path), respect_gitignore=False)

    md_files = [f for f in files if f.path.endswith(".md")]
    assert len(md_files) == 1
    assert md_files[0].content == content
