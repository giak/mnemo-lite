import pytest
import os
import asyncio
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


@pytest.mark.asyncio
async def test_worker_logs_parsing_errors_to_database():
    """Test that worker subprocess logs errors to indexing_errors table."""
    db_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    engine = create_async_engine(db_url)
    test_repo = "test_worker_errors"

    # Cleanup
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM code_chunks WHERE repository = :repo"), {"repo": test_repo})
        await conn.execute(text("DELETE FROM indexing_errors WHERE repository = :repo"), {"repo": test_repo})

    # Create a file with intentionally broken TypeScript
    test_dir = Path("/tmp/test_worker_error_capture")
    test_dir.mkdir(exist_ok=True)

    broken_file = test_dir / "broken.ts"
    broken_file.write_text("class Foo { invalid syntax )))))")

    # Run worker subprocess
    import subprocess
    result = subprocess.run([
        "python3",
        "/app/workers/batch_worker_subprocess.py",
        "--repository", test_repo,
        "--db-url", db_url,
        "--files", str(broken_file)
    ], capture_output=True, text=True, timeout=30)

    # Worker should complete (not crash)
    assert result.returncode == 0

    # Check errors were logged
    async with engine.begin() as conn:
        errors = await conn.execute(
            text("SELECT * FROM indexing_errors WHERE repository = :repo"),
            {"repo": test_repo}
        )
        error_rows = errors.fetchall()

    await engine.dispose()

    # Should have at least 1 error logged
    assert len(error_rows) >= 1
    assert error_rows[0].file_path == str(broken_file)
    assert error_rows[0].error_type in ["parsing_error", "chunking_error"]

    # Cleanup
    broken_file.unlink()
    test_dir.rmdir()
