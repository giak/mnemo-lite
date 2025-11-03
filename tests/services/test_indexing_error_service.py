import pytest
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from services.indexing_error_service import IndexingErrorService
from models.indexing_error_models import IndexingErrorCreate


@pytest.mark.asyncio
async def test_log_error_creates_record():
    """Test that logging an error creates a database record."""
    db_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    engine = create_async_engine(db_url)
    service = IndexingErrorService(engine)

    # Cleanup
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM indexing_errors WHERE repository = 'test_error_repo'"))

    # Create error
    error = IndexingErrorCreate(
        repository="test_error_repo",
        file_path="/test/failed.ts",
        error_type="parsing_error",
        error_message="Unexpected token at line 42",
        error_traceback="Traceback...",
        language="typescript"
    )

    # Log error
    error_id = await service.log_error(error)

    # Verify created
    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT * FROM indexing_errors WHERE error_id = :id"),
            {"id": error_id}
        )
        row = result.fetchone()

    await engine.dispose()

    assert row is not None
    assert row.repository == "test_error_repo"
    assert row.file_path == "/test/failed.ts"
    assert row.error_type == "parsing_error"
    assert row.error_message == "Unexpected token at line 42"


@pytest.mark.asyncio
async def test_get_errors_by_repository():
    """Test retrieving errors filtered by repository."""
    db_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    engine = create_async_engine(db_url)
    service = IndexingErrorService(engine)

    # Cleanup
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM indexing_errors WHERE repository = 'test_get_errors'"))

    # Create 3 errors
    for i in range(3):
        error = IndexingErrorCreate(
            repository="test_get_errors",
            file_path=f"/test/file{i}.ts",
            error_type="parsing_error",
            error_message=f"Error {i}"
        )
        await service.log_error(error)

    # Get errors
    errors, total = await service.get_errors(repository="test_get_errors")

    await engine.dispose()

    assert total == 3
    assert len(errors) == 3
    assert all(e.repository == "test_get_errors" for e in errors)


@pytest.mark.asyncio
async def test_get_errors_filtered_by_type():
    """Test retrieving errors filtered by error_type."""
    db_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    engine = create_async_engine(db_url)
    service = IndexingErrorService(engine)

    # Cleanup
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM indexing_errors WHERE repository = 'test_filter'"))

    # Create errors of different types
    await service.log_error(IndexingErrorCreate(
        repository="test_filter",
        file_path="/test/file1.ts",
        error_type="parsing_error",
        error_message="Parse failed"
    ))

    await service.log_error(IndexingErrorCreate(
        repository="test_filter",
        file_path="/test/file2.ts",
        error_type="chunking_error",
        error_message="Chunk failed"
    ))

    # Get only parsing errors
    errors, total = await service.get_errors(
        repository="test_filter",
        error_type="parsing_error"
    )

    await engine.dispose()

    assert total == 1
    assert errors[0].error_type == "parsing_error"


@pytest.mark.asyncio
async def test_get_errors_pagination():
    """Test pagination works correctly."""
    db_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    engine = create_async_engine(db_url)
    service = IndexingErrorService(engine)

    # Cleanup
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM indexing_errors WHERE repository = 'test_pagination'"))

    # Create 10 errors
    for i in range(10):
        await service.log_error(IndexingErrorCreate(
            repository="test_pagination",
            file_path=f"/test/file{i}.ts",
            error_type="parsing_error",
            error_message=f"Error {i}"
        ))

    # Get page 1 (limit 5)
    errors_page1, total = await service.get_errors(
        repository="test_pagination",
        limit=5,
        offset=0
    )

    # Get page 2 (limit 5, offset 5)
    errors_page2, total = await service.get_errors(
        repository="test_pagination",
        limit=5,
        offset=5
    )

    await engine.dispose()

    assert total == 10
    assert len(errors_page1) == 5
    assert len(errors_page2) == 5
    # Verify no overlap
    page1_ids = {e.error_id for e in errors_page1}
    page2_ids = {e.error_id for e in errors_page2}
    assert len(page1_ids & page2_ids) == 0
