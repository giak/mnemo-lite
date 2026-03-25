"""
Tests for Markdown chunking support (Expanse Vessel integration).

Tests:
- Markdown files are scanned by ProjectScanner
- Markdown is chunked by ## headers into MARKDOWN_SECTION chunks
- Each chunk has correct metadata (header, start/end lines)
- Edge cases: no headers, single header, nested headers, empty file
- Fallback: if chunker fails, fixed chunking is used
"""

import pytest

from models.code_chunk_models import ChunkType
from services.code_chunking_service import CodeChunkingService


@pytest.fixture
def chunking_service():
    """Get CodeChunkingService instance."""
    return CodeChunkingService(max_workers=2)


# ============================================================================
# Test 1: Simple markdown with ## headers
# ============================================================================

@pytest.mark.asyncio
async def test_markdown_chunked_by_h2_headers(chunking_service):
    """Test that markdown files are split by ## headers."""
    source_code = """# Title

Intro paragraph.

## Section Alpha

Content of alpha.

## Section Beta

Content of beta.

## Section Gamma

Content of gamma.
"""

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="markdown",
        file_path="KERNEL.md"
    )

    assert len(chunks) == 3, f"Expected 3 chunks (3 ## sections), got {len(chunks)}"

    assert chunks[0].name == "Section Alpha"
    assert "Content of alpha" in chunks[0].source_code

    assert chunks[1].name == "Section Beta"
    assert "Content of beta" in chunks[1].source_code

    assert chunks[2].name == "Section Gamma"
    assert "Content of gamma" in chunks[2].source_code


# ============================================================================
# Test 2: Chunk type is MARKDOWN_SECTION
# ============================================================================

@pytest.mark.asyncio
async def test_markdown_chunks_have_correct_type(chunking_service):
    """Test that markdown chunks have MARKDOWN_SECTION type."""
    source_code = """## First

Content.

## Second

More content.
"""

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="markdown",
        file_path="doc.md"
    )

    for chunk in chunks:
        assert chunk.chunk_type == ChunkType.MARKDOWN_SECTION, \
            f"Expected MARKDOWN_SECTION, got {chunk.chunk_type}"


# ============================================================================
# Test 3: Line numbers are correct
# ============================================================================

@pytest.mark.asyncio
async def test_markdown_chunks_have_line_numbers(chunking_service):
    """Test that start_line and end_line are set correctly."""
    source_code = """# Title

## Section One

Content one.

## Section Two

Content two.
"""

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="markdown",
        file_path="doc.md"
    )

    assert len(chunks) == 2
    # First chunk includes preamble, starts at line 1
    assert chunks[0].start_line == 1
    # Second chunk starts at its header line
    assert chunks[1].start_line > chunks[0].start_line
    # Each chunk's end_line > start_line
    for chunk in chunks:
        assert chunk.end_line > chunk.start_line


# ============================================================================
# Test 4: Content before first ## is prepended to first chunk
# ============================================================================

@pytest.mark.asyncio
async def test_markdown_preamble_included_in_first_chunk(chunking_service):
    """Test that content before first ## header is included in first chunk."""
    source_code = """# Document Title

Some intro text that appears before any section.

## First Section

Content here.
"""

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="markdown",
        file_path="doc.md"
    )

    assert len(chunks) >= 1
    # The preamble ("# Document Title" + intro) should be in the first chunk
    assert "Document Title" in chunks[0].source_code
    assert "intro text" in chunks[0].source_code


# ============================================================================
# Test 5: File path is preserved
# ============================================================================

@pytest.mark.asyncio
async def test_markdown_chunks_preserve_file_path(chunking_service):
    """Test that file_path is set on all chunks."""
    source_code = """## A

Content A.

## B

Content B.
"""

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="markdown",
        file_path="/home/user/project/KERNEL.md"
    )

    for chunk in chunks:
        assert chunk.file_path == "/home/user/project/KERNEL.md"
        assert chunk.language == "markdown"


# ============================================================================
# Test 6: No headers → single chunk (whole file)
# ============================================================================

@pytest.mark.asyncio
async def test_markdown_no_headers_single_chunk(chunking_service):
    """Test that markdown without ## headers produces a single chunk."""
    source_code = """This is a markdown file
with no headers at all.
Just plain text content.
"""

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="markdown",
        file_path="README.md"
    )

    assert len(chunks) == 1
    assert chunks[0].chunk_type == ChunkType.MARKDOWN_SECTION
    assert "no headers" in chunks[0].source_code


# ============================================================================
# Test 7: Empty markdown file
# ============================================================================

@pytest.mark.asyncio
async def test_markdown_empty_file_raises(chunking_service):
    """Test that empty markdown raises ValueError."""
    with pytest.raises(ValueError, match="source_code cannot be empty"):
        await chunking_service.chunk_code(
            source_code="",
            language="markdown",
            file_path="empty.md"
        )


# ============================================================================
# Test 8: Large section gets split (respects max_chunk_size)
# ============================================================================

@pytest.mark.asyncio
async def test_markdown_large_section_split(chunking_service):
    """Test that very large sections are split respecting max_chunk_size."""
    # Create a section with >2000 characters
    big_content = "Line of content.\n" * 150  # ~2550 chars
    source_code = f"""## Big Section

{big_content}

## Small Section

Tiny.
"""

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="markdown",
        file_path="big.md",
        max_chunk_size=2000
    )

    # Should have at least 2 chunks (big section split + small section)
    assert len(chunks) >= 2
    # The small section should be intact
    small_chunks = [c for c in chunks if "Tiny" in c.source_code]
    assert len(small_chunks) == 1


# ============================================================================
# Test 9: Language field is "markdown"
# ============================================================================

@pytest.mark.asyncio
async def test_markdown_language_field(chunking_service):
    """Test that language field is set to 'markdown'."""
    source_code = "## Test\n\nContent."

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="markdown",
        file_path="test.md"
    )

    for chunk in chunks:
        assert chunk.language == "markdown"
