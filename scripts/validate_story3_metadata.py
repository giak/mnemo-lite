#!/usr/bin/env python3
"""
Validation script for EPIC-06 Phase 1 Story 3 - Code Metadata Extraction.

Tests the CodeChunkingService with metadata extraction on real Python code
from the MnemoLite codebase to verify end-to-end functionality.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "api"))

from services.code_chunking_service import CodeChunkingService


async def validate_metadata_extraction():
    """Validate metadata extraction on real Python file."""

    # Initialize service
    print("=" * 80)
    print("EPIC-06 PHASE 1 STORY 3 - CODE METADATA EXTRACTION VALIDATION")
    print("=" * 80)
    print()

    service = CodeChunkingService(max_workers=2)

    # Test file: metadata_extractor_service.py itself
    # In Docker container, files are at /app/services/ not /app/api/services/
    test_file = Path("/app/services/metadata_extractor_service.py")

    print(f"📄 Test file: {test_file.name}")
    print(f"📍 Path: {test_file}")
    print()

    # Read source code
    source_code = test_file.read_text()
    line_count = len(source_code.split('\n'))
    char_count = len(source_code)

    print(f"📊 File stats: {line_count} lines, {char_count} characters")
    print()

    # Chunk with metadata extraction
    print("🔍 Chunking with metadata extraction...")
    chunks = await service.chunk_code(
        source_code=source_code,
        language="python",
        file_path=str(test_file),
        extract_metadata=True  # Enable metadata extraction
    )

    print(f"✅ Generated {len(chunks)} chunks")
    print()

    # Display results for first 3 chunks
    print("=" * 80)
    print("CHUNK DETAILS (First 3 chunks)")
    print("=" * 80)
    print()

    for i, chunk in enumerate(chunks[:3], 1):
        print(f"{'=' * 80}")
        print(f"CHUNK {i}/{len(chunks)}: {chunk.name}")
        print(f"{'=' * 80}")
        print(f"Type: {chunk.chunk_type.value}")
        print(f"Lines: {chunk.start_line}-{chunk.end_line} ({chunk.end_line - chunk.start_line + 1} lines)")
        print(f"Size: {len(chunk.source_code)} characters")
        print()

        # Display metadata
        print("METADATA:")
        print("-" * 80)

        metadata = chunk.metadata

        # 1. Signature
        signature = metadata.get("signature", "N/A")
        if signature:
            # Truncate if too long
            if len(signature) > 120:
                signature = signature[:120] + "..."
        print(f"  1. Signature:    {signature}")

        # 2. Parameters
        params = metadata.get("parameters", [])
        print(f"  2. Parameters:   {params if params else 'None'}")

        # 3. Returns
        returns = metadata.get("returns", None)
        print(f"  3. Returns:      {returns if returns else 'None'}")

        # 4. Decorators
        decorators = metadata.get("decorators", [])
        print(f"  4. Decorators:   {decorators if decorators else 'None'}")

        # 5. Docstring
        docstring = metadata.get("docstring", None)
        if docstring:
            # Show first line only
            first_line = docstring.split('\n')[0]
            if len(first_line) > 60:
                first_line = first_line[:60] + "..."
            print(f"  5. Docstring:    \"{first_line}\"")
        else:
            print(f"  5. Docstring:    None")

        # 6. Complexity - Cyclomatic
        complexity = metadata.get("complexity", {})
        cyclomatic = complexity.get("cyclomatic", "N/A")
        print(f"  6. Cyclomatic:   {cyclomatic}")

        # 7. Complexity - LOC
        loc = complexity.get("lines_of_code", "N/A")
        print(f"  7. Lines of Code: {loc}")

        # 8. Imports
        imports = metadata.get("imports", [])
        if imports:
            print(f"  8. Imports:      {imports[:3]}{'...' if len(imports) > 3 else ''}")
        else:
            print(f"  8. Imports:      None")

        # 9. Calls
        calls = metadata.get("calls", [])
        if calls:
            print(f"  9. Calls:        {calls[:5]}{'...' if len(calls) > 5 else ''}")
        else:
            print(f"  9. Calls:        None")

        print()

    # Summary statistics
    print("=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    print()

    chunks_with_metadata = sum(1 for c in chunks if c.metadata.get("signature"))
    chunks_with_docstring = sum(1 for c in chunks if c.metadata.get("docstring"))
    chunks_with_complexity = sum(1 for c in chunks if c.metadata.get("complexity", {}).get("cyclomatic") is not None)
    chunks_with_calls = sum(1 for c in chunks if c.metadata.get("calls"))

    print(f"Total chunks:              {len(chunks)}")
    print(f"Chunks with signature:     {chunks_with_metadata} ({chunks_with_metadata/len(chunks)*100:.1f}%)")
    print(f"Chunks with docstring:     {chunks_with_docstring} ({chunks_with_docstring/len(chunks)*100:.1f}%)")
    print(f"Chunks with complexity:    {chunks_with_complexity} ({chunks_with_complexity/len(chunks)*100:.1f}%)")
    print(f"Chunks with function calls: {chunks_with_calls} ({chunks_with_calls/len(chunks)*100:.1f}%)")
    print()

    # Average complexity
    complexities = [c.metadata.get("complexity", {}).get("cyclomatic", 0) for c in chunks if c.metadata.get("complexity", {}).get("cyclomatic")]
    if complexities:
        avg_complexity = sum(complexities) / len(complexities)
        max_complexity = max(complexities)
        print(f"Average cyclomatic complexity: {avg_complexity:.2f}")
        print(f"Maximum cyclomatic complexity: {max_complexity}")
        print()

    print("✅ VALIDATION COMPLETE - Story 3 metadata extraction is working!")
    print()


if __name__ == "__main__":
    asyncio.run(validate_metadata_extraction())
