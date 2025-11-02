# tests/unit/test_batch_producer_exclusions.py
import pytest
from pathlib import Path
from services.batch_indexing_producer import BatchIndexingProducer


def test_scan_files_excludes_dist_directory(tmp_path):
    """Test that files in dist/ are excluded from scanning."""
    # Setup: Create test directory structure
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "app.ts").write_text("export const app = 1;")

    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "app.js").write_text("export const app = 1;")
    (dist_dir / "app.d.ts").write_text("export declare const app: number;")

    # Execute: Scan files
    producer = BatchIndexingProducer()
    files = producer.scan_files(tmp_path, [".ts", ".js"])

    # Verify: Only src/ files found, dist/ excluded
    file_paths = [str(f.relative_to(tmp_path)) for f in files]
    assert "src/app.ts" in file_paths, "Source file should be included"
    assert "dist/app.js" not in file_paths, "dist/ JS should be excluded"
    assert "dist/app.d.ts" not in file_paths, "dist/ .d.ts should be excluded"
    assert len(files) == 1, f"Expected 1 file, got {len(files)}: {file_paths}"


def test_scan_files_excludes_nested_dist_directory(tmp_path):
    """Test that nested dist/ directories are also excluded."""
    # Setup: Create nested structure
    packages_dir = tmp_path / "packages" / "core"
    packages_dir.mkdir(parents=True)
    (packages_dir / "index.ts").write_text("export const core = 1;")

    nested_dist = packages_dir / "dist"
    nested_dist.mkdir()
    (nested_dist / "index.js").write_text("export const core = 1;")

    # Execute
    producer = BatchIndexingProducer()
    files = producer.scan_files(tmp_path, [".ts", ".js"])

    # Verify: Only source file, nested dist excluded
    file_paths = [str(f.relative_to(tmp_path)) for f in files]
    assert "packages/core/index.ts" in file_paths
    assert not any("dist" in p for p in file_paths), f"dist/ files found: {file_paths}"
