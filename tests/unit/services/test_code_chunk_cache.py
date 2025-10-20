"""
Unit tests for CodeChunkCache (EPIC-10 Story 10.1).

Tests L1 in-memory cache with LRU eviction and MD5 validation.
"""

import pytest
from services.caches import CodeChunkCache


class TestCodeChunkCache:
    """Test suite for CodeChunkCache."""

    def test_cache_initialization(self):
        """Test cache initializes with correct configuration."""
        cache = CodeChunkCache(max_size_mb=50)

        assert cache.max_size_bytes == 50 * 1024 * 1024
        assert cache.current_size == 0
        assert len(cache.cache) == 0
        assert cache.hits == 0
        assert cache.misses == 0
        assert cache.evictions == 0

    def test_cache_put_and_get_hit(self):
        """Test cache PUT followed by GET (cache HIT)."""
        cache = CodeChunkCache(max_size_mb=10)

        file_path = "test.py"
        source_code = "def hello():\n    print('world')"
        chunks = [
            {
                "file_path": "test.py",
                "name": "hello",
                "source_code": source_code,
                "chunk_type": "function",
            }
        ]

        # PUT
        cache.put(file_path, source_code, chunks)

        # GET (should HIT)
        result = cache.get(file_path, source_code)

        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "hello"
        assert cache.hits == 1
        assert cache.misses == 0

    def test_cache_get_miss(self):
        """Test cache GET without prior PUT (cache MISS)."""
        cache = CodeChunkCache(max_size_mb=10)

        file_path = "test.py"
        source_code = "def hello():\n    print('world')"

        # GET without PUT (should MISS)
        result = cache.get(file_path, source_code)

        assert result is None
        assert cache.hits == 0
        assert cache.misses == 1

    def test_cache_md5_validation_content_change(self):
        """Test MD5 validation detects content changes (ZERO-TRUST)."""
        cache = CodeChunkCache(max_size_mb=10)

        file_path = "test.py"
        source_code_v1 = "def hello():\n    print('world')"
        source_code_v2 = "def hello():\n    print('universe')"  # Changed!

        chunks_v1 = [{"name": "hello", "source_code": source_code_v1}]

        # PUT v1
        cache.put(file_path, source_code_v1, chunks_v1)

        # GET with v2 content (hash mismatch → should MISS + invalidate)
        result = cache.get(file_path, source_code_v2)

        assert result is None
        assert cache.hits == 0
        assert cache.misses == 1
        assert cache.evictions == 1  # Old entry evicted due to hash mismatch
        assert len(cache.cache) == 0  # Entry removed

    def test_cache_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        # Small cache: 2KB max (will force eviction after 2 items)
        cache = CodeChunkCache(max_size_mb=2 / 1024)  # 2KB

        # Create chunks that will fit 2 in cache but not 3
        file1 = "file1.py"
        source1 = "x" * 400  # 400 bytes
        chunks1 = [{"name": "chunk1", "source_code": source1}]

        file2 = "file2.py"
        source2 = "y" * 400  # 400 bytes
        chunks2 = [{"name": "chunk2", "source_code": source2}]

        file3 = "file3.py"
        source3 = "z" * 400  # 400 bytes (will exceed 2KB → evict file1)
        chunks3 = [{"name": "chunk3", "source_code": source3}]

        # PUT file1, file2 (both should fit)
        cache.put(file1, source1, chunks1)
        cache.put(file2, source2, chunks2)

        # PUT file3 (should evict file1 - LRU)
        cache.put(file3, source3, chunks3)

        # file1 should be evicted
        assert cache.get(file1, source1) is None  # MISS
        assert cache.get(file2, source2) is not None  # HIT
        assert cache.get(file3, source3) is not None  # HIT
        assert cache.evictions >= 1

    def test_cache_lru_move_to_end(self):
        """Test LRU updates on GET (move to end)."""
        cache = CodeChunkCache(max_size_mb=1.8 / 1024)  # 1.8KB

        file1 = "file1.py"
        source1 = "x" * 300
        chunks1 = [{"name": "chunk1", "source_code": source1}]

        file2 = "file2.py"
        source2 = "y" * 300
        chunks2 = [{"name": "chunk2", "source_code": source2}]

        file3 = "file3.py"
        source3 = "z" * 500  # Larger file (will force eviction)
        chunks3 = [{"name": "chunk3", "source_code": source3}]

        # PUT file1, file2 (both should fit in 1.8KB)
        cache.put(file1, source1, chunks1)
        cache.put(file2, source2, chunks2)

        # GET file1 (moves to end - most recently used)
        cache.get(file1, source1)

        # PUT file3 (should evict file2, NOT file1 since file1 was just accessed)
        cache.put(file3, source3, chunks3)

        # file1 should still be cached (moved to end)
        # file2 should be evicted (LRU)
        assert cache.get(file1, source1) is not None  # HIT
        assert cache.get(file2, source2) is None  # MISS (evicted)
        assert cache.get(file3, source3) is not None  # HIT

    def test_cache_stats(self):
        """Test cache statistics reporting."""
        cache = CodeChunkCache(max_size_mb=10)

        file_path = "test.py"
        source_code = "def test(): pass"
        chunks = [{"name": "test", "source_code": source_code}]

        # PUT
        cache.put(file_path, source_code, chunks)

        # GET (HIT)
        cache.get(file_path, source_code)

        # GET (MISS)
        cache.get("other.py", "other code")

        stats = cache.stats()

        assert stats["type"] == "L1_memory"
        assert stats["max_size_mb"] == 10
        assert stats["entries"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate_percent"] == 50.0  # 1 hit / 2 total = 50%
        assert "size_mb" in stats
        assert "utilization_percent" in stats

    def test_cache_clear(self):
        """Test cache clear removes all entries."""
        cache = CodeChunkCache(max_size_mb=10)

        # PUT some entries
        cache.put("file1.py", "code1", [{"name": "chunk1"}])
        cache.put("file2.py", "code2", [{"name": "chunk2"}])

        assert len(cache.cache) == 2

        # CLEAR
        cache.clear()

        assert len(cache.cache) == 0
        assert cache.current_size == 0

    def test_cache_invalidate(self):
        """Test cache invalidate removes specific entry."""
        cache = CodeChunkCache(max_size_mb=10)

        # PUT entries
        cache.put("file1.py", "code1", [{"name": "chunk1"}])
        cache.put("file2.py", "code2", [{"name": "chunk2"}])

        assert len(cache.cache) == 2

        # INVALIDATE file1
        cache.invalidate("file1.py")

        assert len(cache.cache) == 1
        assert cache.get("file1.py", "code1") is None  # MISS
        assert cache.get("file2.py", "code2") is not None  # HIT

    def test_cache_update_existing_entry(self):
        """Test PUT with same file_path replaces old entry."""
        cache = CodeChunkCache(max_size_mb=10)

        file_path = "test.py"
        source_v1 = "version 1"
        source_v2 = "version 2"

        chunks_v1 = [{"name": "v1"}]
        chunks_v2 = [{"name": "v2"}]

        # PUT v1
        cache.put(file_path, source_v1, chunks_v1)
        result = cache.get(file_path, source_v1)
        assert result[0]["name"] == "v1"

        # PUT v2 (should replace)
        cache.put(file_path, source_v2, chunks_v2)
        result_v2 = cache.get(file_path, source_v2)
        assert result_v2[0]["name"] == "v2"

        # v1 should no longer work (hash mismatch)
        result_v1_invalid = cache.get(file_path, source_v1)
        assert result_v1_invalid is None

    def test_cache_empty_chunks(self):
        """Test cache handles empty chunks list."""
        cache = CodeChunkCache(max_size_mb=10)

        file_path = "empty.py"
        source_code = "# empty file"
        chunks = []

        # PUT empty chunks
        cache.put(file_path, source_code, chunks)

        # GET (should HIT even with empty list)
        result = cache.get(file_path, source_code)
        assert result is not None
        assert len(result) == 0
        assert cache.hits == 1

    def test_cache_large_chunks(self):
        """Test cache handles large chunks."""
        cache = CodeChunkCache(max_size_mb=10)

        file_path = "large.py"
        large_code = "x" * 1024 * 1024  # 1MB
        chunks = [{"name": "large", "source_code": large_code}]

        # PUT large chunk
        cache.put(file_path, large_code, chunks)

        # GET
        result = cache.get(file_path, large_code)
        assert result is not None
        assert len(result) == 1

        stats = cache.stats()
        assert stats["size_mb"] >= 2.0  # At least 2MB (source + chunk)
