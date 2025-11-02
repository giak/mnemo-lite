import pytest
from pathlib import Path
from services.batch_indexing_producer import BatchIndexingProducer


def test_create_batches():
    """Test division of files into batches."""
    producer = BatchIndexingProducer()

    files = [Path(f"file{i}.ts") for i in range(100)]
    batches = producer._create_batches(files, batch_size=40)

    assert len(batches) == 3  # 100 ÷ 40 = 3 batches
    assert len(batches[0]) == 40
    assert len(batches[1]) == 40
    assert len(batches[2]) == 20


def test_create_batches_exact_multiple():
    """Test batching when files divide evenly."""
    producer = BatchIndexingProducer()

    files = [Path(f"file{i}.ts") for i in range(80)]
    batches = producer._create_batches(files, batch_size=40)

    assert len(batches) == 2
    assert len(batches[0]) == 40
    assert len(batches[1]) == 40


def test_scan_files_filters_by_extension():
    """Test scanning filters by .ts and .js extensions."""
    producer = BatchIndexingProducer()

    # Create temp directory with mixed files
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "test1.ts").touch()
        (tmp_path / "test2.js").touch()
        (tmp_path / "test3.py").touch()  # Should be ignored
        (tmp_path / "README.md").touch()  # Should be ignored

        files = producer.scan_files(tmp_path, [".ts", ".js"])

        assert len(files) == 2
        assert all(f.suffix in [".ts", ".js"] for f in files)


def test_scan_files_sorts_alphabetically():
    """Test scanning returns sorted files for reproducibility."""
    producer = BatchIndexingProducer()

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "zebra.ts").touch()
        (tmp_path / "alpha.ts").touch()
        (tmp_path / "beta.ts").touch()

        files = producer.scan_files(tmp_path, [".ts"])

        assert files[0].name == "alpha.ts"
        assert files[1].name == "beta.ts"
        assert files[2].name == "zebra.ts"
