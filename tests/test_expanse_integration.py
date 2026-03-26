"""
Integration test: index real Expanse .md files into Mnemolite DB.
"""

import pytest
import os

from mnemo_mcp.utils.project_scanner import ProjectScanner
from services.code_chunking_service import CodeChunkingService
from services.embedding_service import MockEmbeddingService


@pytest.mark.asyncio
async def test_scan_expanse_md_files():
    """Scanner finds Expanse .md files (not dot-prefixed)."""
    scanner = ProjectScanner()
    files = await scanner.scan('/external/projects/expanse', respect_gitignore=True)

    md_files = [f for f in files if f.path.endswith('.md')]
    assert len(md_files) > 0, "Should find at least some .md files"

    # Verify no dot-prefixed dirs
    for f in md_files:
        parts = f.path.replace('/external/projects/expanse/', '').split('/')
        assert not any(p.startswith('.') for p in parts), f"Dot-dir leaked: {f.path}"

    # Verify core files exist
    paths = [f.path for f in md_files]
    assert any('KERNEL.md' in p for p in paths)
    assert any('expanse-v15-apex.md' in p for p in paths)


@pytest.mark.asyncio
async def test_chunk_real_expanse_file():
    """Chunk a real Expanse .md file."""
    chunker = CodeChunkingService(max_workers=2)

    with open('/external/projects/expanse/runtime/expanse-v15-apex.md') as f:
        content = f.read()

    chunks = await chunker.chunk_code(
        source_code=content,
        language='markdown',
        file_path='/external/projects/expanse/runtime/expanse-v15-apex.md'
    )

    assert len(chunks) > 0
    assert all(c.chunk_type.value == 'markdown_section' for c in chunks)
    assert all(c.language == 'markdown' for c in chunks)
    # Apex has sections Ⅰ through Ⅵ
    assert len(chunks) >= 4


@pytest.mark.asyncio
async def test_chunk_multiple_expanse_files():
    """Chunk 5 real Expanse files."""
    chunker = CodeChunkingService(max_workers=2)
    scanner = ProjectScanner()
    files = await scanner.scan('/external/projects/expanse', respect_gitignore=True)
    md_files = [f for f in files if f.path.endswith('.md')][:5]

    total_chunks = 0
    for f in md_files:
        chunks = await chunker.chunk_code(
            source_code=f.content,
            language='markdown',
            file_path=f.path
        )
        total_chunks += len(chunks)
        assert len(chunks) > 0, f"No chunks for {f.path}"

    print(f'\n  {len(md_files)} files → {total_chunks} chunks')
    assert total_chunks > 0
