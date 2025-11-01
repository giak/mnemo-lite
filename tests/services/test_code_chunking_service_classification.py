"""Integration tests for file classification in chunking (EPIC-29 Task 4)."""
import pytest
from api.services.code_chunking_service import CodeChunkingService
from api.models.code_chunk_models import ChunkType


@pytest.mark.asyncio
async def test_chunk_barrel_file():
    """Barrel files should create single BARREL chunk."""
    # Create service with metadata extraction enabled (needed for re-exports)
    from services.metadata_extractor_service import get_metadata_extractor_service
    metadata_service = get_metadata_extractor_service()
    chunking_service = CodeChunkingService(metadata_service=metadata_service)

    barrel_source = """export { createSuccess, createFailure } from './utils/result.utils';
export { Success, Failure } from './types/result.type';
export type { ValidationError } from './types/validation.interface';
"""

    chunks = await chunking_service.chunk_code(
        source_code=barrel_source,
        file_path="packages/shared/src/index.ts",
        language="typescript"
    )

    # Should create 1 BARREL chunk
    assert len(chunks) == 1
    assert chunks[0].chunk_type == ChunkType.BARREL
    assert chunks[0].name == "shared"  # Derived from package name
    assert len(chunks[0].metadata["re_exports"]) == 5


@pytest.mark.asyncio
async def test_chunk_config_file():
    """Config files should create single CONFIG_MODULE chunk."""
    from services.metadata_extractor_service import get_metadata_extractor_service
    metadata_service = get_metadata_extractor_service()
    chunking_service = CodeChunkingService(metadata_service=metadata_service)

    config_source = """import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@ui': resolve(__dirname, 'src'),
    }
  }
})
"""

    chunks = await chunking_service.chunk_code(
        source_code=config_source,
        file_path="packages/ui/vite.config.ts",
        language="typescript"
    )

    # Should create 1 CONFIG_MODULE chunk
    assert len(chunks) == 1
    assert chunks[0].chunk_type == ChunkType.CONFIG_MODULE
    assert chunks[0].name == "vite.config"
    # Light extraction: imports only, no calls
    assert "imports" in chunks[0].metadata
    assert len(chunks[0].metadata["calls"]) == 0  # No call extraction


@pytest.mark.asyncio
async def test_skip_test_files():
    """Test files should return empty chunks."""
    from services.metadata_extractor_service import get_metadata_extractor_service
    metadata_service = get_metadata_extractor_service()
    chunking_service = CodeChunkingService(metadata_service=metadata_service)

    test_source = """import { describe, it, expect } from 'vitest';

describe('Tests', () => {
  it('should work', () => {
    expect(true).toBe(true);
  });
});
"""

    chunks = await chunking_service.chunk_code(
        source_code=test_source,
        file_path="utils/__tests__/result.utils.spec.ts",
        language="typescript"
    )

    # Should skip test files entirely
    assert len(chunks) == 0
