import pytest
import json
import subprocess
import sys
from pathlib import Path


def test_subprocess_worker_processes_batch(tmp_path, test_db_url):
    """Test subprocess worker processes batch and returns result."""
    # Create test files
    test_files = []
    for i in range(3):
        file_path = tmp_path / f"test{i}.ts"
        file_path.write_text(f"function test{i}() {{ return {i}; }}")
        test_files.append(str(file_path))

    # Run subprocess
    args = [
        sys.executable,
        "workers/batch_worker_subprocess.py",
        "--repository", "test_subprocess",
        "--db-url", test_db_url,
        "--files", ",".join(test_files)
    ]

    result = subprocess.run(
        args,
        cwd="/app",
        capture_output=True,
        text=True,
        timeout=60
    )

    # Verify subprocess succeeded
    assert result.returncode == 0

    # Parse result from last line of stdout
    output_lines = result.stdout.strip().split("\n")
    result_json = json.loads(output_lines[-1])

    assert "success_count" in result_json
    assert "error_count" in result_json
    assert result_json["success_count"] + result_json["error_count"] == 3


def test_subprocess_worker_handles_invalid_file(tmp_path, test_db_url):
    """Test subprocess worker continues on invalid files."""
    # Create mix of valid and invalid files
    valid_file = tmp_path / "valid.ts"
    valid_file.write_text("function valid() { return 1; }")

    invalid_file = tmp_path / "invalid.ts"
    invalid_file.write_text("x" * 1000000)  # Huge file

    args = [
        sys.executable,
        "workers/batch_worker_subprocess.py",
        "--repository", "test_invalid",
        "--db-url", test_db_url,
        "--files", f"{valid_file},{invalid_file}"
    ]

    result = subprocess.run(
        args,
        cwd="/app",
        capture_output=True,
        text=True,
        timeout=60
    )

    # Should succeed despite invalid file
    assert result.returncode == 0

    output_lines = result.stdout.strip().split("\n")
    result_json = json.loads(output_lines[-1])

    # At least 1 success (valid file)
    assert result_json["success_count"] >= 1
