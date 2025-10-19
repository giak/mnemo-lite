"""
Unit tests for CodeChunkRepository batch operations (PHASE 1).

Tests the critical batch insert optimization that replaced sequential
inserts, providing 10-50× performance improvement.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from models.code_chunk_models import CodeChunkCreate
from db.repositories.code_chunk_repository import CodeChunkRepository


@pytest_asyncio.fixture
async def code_chunk_repo(test_engine):
    """Get CodeChunkRepository with test engine."""
    return CodeChunkRepository(engine=test_engine)


@pytest.mark.anyio
class TestCodeChunkBatchInsert:
    """Test batch insert functionality (PHASE 1 critical optimization)."""

    async def test_add_batch_empty_list(self, code_chunk_repo: CodeChunkRepository):
        """Test batch insert with empty list returns 0."""
        result = await code_chunk_repo.add_batch([])
        
        assert result == 0

    async def test_add_batch_single_chunk(self, code_chunk_repo: CodeChunkRepository):
        """Test batch insert with single chunk."""
        chunk = CodeChunkCreate(
            file_path="test_single.py",
            language="python",
            chunk_type="function",
            source_code="def test(): pass",
            name="test",
            start_line=1,
            end_line=1,
            repository="test-repo",
            metadata={"complexity": {"cyclomatic": 1}}
        )
        
        result = await code_chunk_repo.add_batch([chunk])
        
        assert result == 1

    async def test_add_batch_multiple_chunks(self, code_chunk_repo: CodeChunkRepository):
        """Test batch insert with multiple chunks (typical use case)."""
        chunks = []
        for i in range(10):
            chunks.append(CodeChunkCreate(
                file_path=f"file{i}.py",
                language="python",
                chunk_type="function",
                source_code=f"def func{i}(): return {i}",
                name=f"func{i}",
                start_line=1,
                end_line=1,
                repository="batch-repo"
            ))
        
        result = await code_chunk_repo.add_batch(chunks)
        
        assert result == 10

    async def test_add_batch_large_batch(self, code_chunk_repo: CodeChunkRepository):
        """Test batch insert with large batch (50 chunks - max per file)."""
        chunks = []
        for i in range(50):
            chunks.append(CodeChunkCreate(
                file_path="large_file.py",
                language="python",
                chunk_type="function",
                source_code=f"def func{i}(): return {i}",
                name=f"func{i}",
                start_line=i,
                end_line=i,
                repository="large-batch-repo",
                metadata={"complexity": {"cyclomatic": 1, "lines_of_code": 1}}
            ))
        
        result = await code_chunk_repo.add_batch(chunks)
        
        assert result == 50

    async def test_add_batch_with_metadata(self, code_chunk_repo: CodeChunkRepository):
        """Test batch insert with rich metadata."""
        chunks = []
        for i in range(5):
            chunks.append(CodeChunkCreate(
                file_path=f"meta_{i}.py",
                language="python",
                chunk_type="function",
                source_code=f"def complex_func{i}(): pass",
                name=f"complex_func{i}",
                start_line=1,
                end_line=10,
                repository="metadata-repo",
                metadata={
                    "complexity": {
                        "cyclomatic": i + 1,
                        "lines_of_code": 10,
                        "max_nesting": 2
                    },
                    "calls": [f"helper{i}", f"util{i}"],
                    "imports": ["os", "sys"],
                    "signature": f"complex_func{i}()"
                }
            ))
        
        result = await code_chunk_repo.add_batch(chunks)
        
        assert result == 5

    async def test_add_batch_mixed_languages(self, code_chunk_repo: CodeChunkRepository):
        """Test batch insert with multiple programming languages."""
        chunks = [
            CodeChunkCreate(
                file_path="main.py",
                language="python",
                chunk_type="function",
                source_code="def main(): pass",
                name="main",
                start_line=1,
                end_line=1,
                repository="multi-lang-repo"
            ),
            CodeChunkCreate(
                file_path="app.js",
                language="javascript",
                chunk_type="function",
                source_code="function app() {}",
                name="app",
                start_line=1,
                end_line=1,
                repository="multi-lang-repo"
            ),
            CodeChunkCreate(
                file_path="Component.tsx",
                language="typescript",
                chunk_type="function",
                source_code="export const Component = () => {}",
                name="Component",
                start_line=1,
                end_line=1,
                repository="multi-lang-repo"
            )
        ]
        
        result = await code_chunk_repo.add_batch(chunks)
        
        assert result == 3

    async def test_add_batch_mixed_chunk_types(self, code_chunk_repo: CodeChunkRepository):
        """Test batch insert with different chunk types."""
        chunks = [
            CodeChunkCreate(
                file_path="module.py",
                language="python",
                chunk_type="function",
                source_code="def func(): pass",
                name="func",
                start_line=1,
                end_line=1,
                repository="types-repo"
            ),
            CodeChunkCreate(
                file_path="module.py",
                language="python",
                chunk_type="class",
                source_code="class MyClass: pass",
                name="MyClass",
                start_line=3,
                end_line=3,
                repository="types-repo"
            ),
            CodeChunkCreate(
                file_path="module.py",
                language="python",
                chunk_type="method",
                source_code="def method(self): pass",
                name="method",
                start_line=5,
                end_line=5,
                repository="types-repo"
            ),
            CodeChunkCreate(
                file_path="module.py",
                language="python",
                chunk_type="module",
                source_code='"""Module docstring"""',
                name="module",
                start_line=1,
                end_line=1,
                repository="types-repo"
            )
        ]
        
        result = await code_chunk_repo.add_batch(chunks)
        
        assert result == 4

    async def test_add_batch_with_commit_hash(self, code_chunk_repo: CodeChunkRepository):
        """Test batch insert with commit hash tracking."""
        commit_hash = "abc123def456"
        
        chunks = []
        for i in range(3):
            chunks.append(CodeChunkCreate(
                file_path=f"file{i}.py",
                language="python",
                chunk_type="function",
                source_code=f"def func{i}(): pass",
                name=f"func{i}",
                start_line=1,
                end_line=1,
                repository="commit-repo",
                commit_hash=commit_hash
            ))
        
        result = await code_chunk_repo.add_batch(chunks)
        
        assert result == 3

    async def test_add_batch_very_large_source_code(self, code_chunk_repo: CodeChunkRepository):
        """Test batch insert with large source code chunks."""
        large_source = "def large():\n" + "    # Comment\n" * 100 + "    return 42"
        
        chunks = [
            CodeChunkCreate(
                file_path="large_code.py",
                language="python",
                chunk_type="function",
                source_code=large_source,
                name="large",
                start_line=1,
                end_line=102,
                repository="large-code-repo"
            )
        ]
        
        result = await code_chunk_repo.add_batch(chunks)
        
        assert result == 1

    async def test_add_batch_special_characters_in_source(self, code_chunk_repo: CodeChunkRepository):
        """Test batch insert with special characters in source code."""
        chunks = [
            CodeChunkCreate(
                file_path="special.py",
                language="python",
                chunk_type="function",
                source_code='def special(): return "Hello \'World\'\n\t\\"test\\""',
                name="special",
                start_line=1,
                end_line=1,
                repository="special-char-repo"
            )
        ]
        
        result = await code_chunk_repo.add_batch(chunks)
        
        assert result == 1

    async def test_add_batch_unicode_in_source(self, code_chunk_repo: CodeChunkRepository):
        """Test batch insert with Unicode characters."""
        chunks = [
            CodeChunkCreate(
                file_path="unicode.py",
                language="python",
                chunk_type="function",
                source_code='def greet(): return "Bonjour 🇫🇷 世界 🌍"',
                name="greet",
                start_line=1,
                end_line=1,
                repository="unicode-repo"
            )
        ]
        
        result = await code_chunk_repo.add_batch(chunks)
        
        assert result == 1

    async def test_add_batch_query_builder_multiple(self, code_chunk_repo: CodeChunkRepository):
        """Test batch query with multiple chunks generates correct params."""
        chunks = []
        for i in range(3):
            chunks.append(CodeChunkCreate(
                file_path=f"file{i}.py",
                language="python",
                chunk_type="function",
                source_code=f"def func{i}(): pass",
                name=f"func{i}",
                start_line=1,
                end_line=1,
                repository="multi-query-repo"
            ))
        
        query, params = code_chunk_repo.query_builder.build_add_batch_query(chunks)
        
        # Should have params for all 3 chunks
        assert "file_path_0" in params
        assert "file_path_1" in params
        assert "file_path_2" in params
        
        # Verify values
        assert params["name_0"] == "func0"
        assert params["name_1"] == "func1"
        assert params["name_2"] == "func2"
