"""Tests for code chunk models."""
import pytest
from api.models.code_chunk_models import ChunkType, CodeChunk


def test_barrel_chunk_type_exists():
    """EPIC-29 Task 1: Verify BARREL ChunkType exists."""
    assert ChunkType.BARREL == "barrel"
    assert "barrel" in [ct.value for ct in ChunkType]


def test_config_module_chunk_type_exists():
    """EPIC-29 Task 1: Verify CONFIG_MODULE ChunkType exists."""
    assert ChunkType.CONFIG_MODULE == "config_module"
    assert "config_module" in [ct.value for ct in ChunkType]


def test_create_barrel_chunk():
    """EPIC-29 Task 1: Create chunk with BARREL type."""
    chunk = CodeChunk(
        file_path="packages/shared/src/index.ts",
        language="typescript",
        chunk_type=ChunkType.BARREL,
        name="shared",
        source_code="export { createSuccess } from './utils/result.utils';",
        start_line=1,
        end_line=1,
        metadata={
            "re_exports": [
                {"symbol": "createSuccess", "source": "./utils/result.utils"}
            ]
        }
    )
    assert chunk.chunk_type == ChunkType.BARREL
    assert chunk.name == "shared"
    assert len(chunk.metadata["re_exports"]) == 1
