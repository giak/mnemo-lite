# tests/unit/test_batch_producer_include_tests.py
import pytest
from pathlib import Path
from services.batch_indexing_producer import BatchIndexingProducer


def test_scan_files_excludes_tests_by_default(tmp_path):
    """Test that test files are excluded by default."""
    # Setup: Create source and test files
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "app.ts").write_text("export const app = 1;")

    test_dir = tmp_path / "__tests__"
    test_dir.mkdir()
    (test_dir / "app.spec.ts").write_text("test('app', () => {});")

    # Execute: Scan files (default: exclude tests)
    producer = BatchIndexingProducer()
    files = producer.scan_files(tmp_path, [".ts"], include_tests=False)

    # Verify: Only source file found
    file_paths = [str(f.relative_to(tmp_path)) for f in files]
    assert "src/app.ts" in file_paths
    assert "tests/app.spec.ts" not in file_paths
    assert len(files) == 1


def test_scan_files_includes_tests_when_flag_enabled(tmp_path):
    """Test that test files are included when include_tests=True."""
    # Setup
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "app.ts").write_text("export const app = 1;")

    test_dir = tmp_path / "__tests__"
    test_dir.mkdir()
    (test_dir / "app.spec.ts").write_text("test('app', () => {});")

    # Execute: Scan with include_tests=True
    producer = BatchIndexingProducer()
    files = producer.scan_files(tmp_path, [".ts"], include_tests=True)

    # Verify: Both files found
    file_paths = [str(f.relative_to(tmp_path)) for f in files]
    assert "src/app.ts" in file_paths
    assert "__tests__/app.spec.ts" in file_paths
    assert len(files) == 2


def test_scan_files_detects_various_test_patterns(tmp_path):
    """Test that all test patterns are detected."""
    # Setup: Various test file patterns
    (tmp_path / "app.spec.ts").write_text("test")
    (tmp_path / "app.test.ts").write_text("test")

    tests_dir = tmp_path / "__tests__"
    tests_dir.mkdir()
    (tests_dir / "unit.ts").write_text("test")

    # Execute: include_tests=True
    producer = BatchIndexingProducer()
    files = producer.scan_files(tmp_path, [".ts"], include_tests=True)

    # Verify: All test files found
    assert len(files) == 3

    # Execute: include_tests=False
    files_no_tests = producer.scan_files(tmp_path, [".ts"], include_tests=False)

    # Verify: No test files
    assert len(files_no_tests) == 0
