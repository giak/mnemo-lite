"""Tests for file classification service (EPIC-29 Task 3)."""
import pytest
from pathlib import Path
from api.services.file_classification_service import FileClassificationService, FileType


def test_detect_barrel_by_filename():
    """Detect barrel by filename (index.ts)."""
    classifier = FileClassificationService()

    file_path = "packages/shared/src/index.ts"
    file_type = classifier.classify_by_filename(file_path)

    assert file_type == FileType.POTENTIAL_BARREL


def test_detect_config_by_filename():
    """Detect config files by naming pattern."""
    classifier = FileClassificationService()

    config_files = [
        "vite.config.ts",
        "vitest.config.ts",
        "tailwind.config.ts",
        "packages/ui/vite.config.ts",
    ]

    for file_path in config_files:
        file_type = classifier.classify_by_filename(file_path)
        assert file_type == FileType.CONFIG, f"Failed for {file_path}"


def test_detect_test_file():
    """Detect test files to skip."""
    classifier = FileClassificationService()

    test_files = [
        "utils/result.utils.spec.ts",
        "components/Button.test.ts",
        "packages/core/__tests__/user.test.ts",
    ]

    for file_path in test_files:
        file_type = classifier.classify_by_filename(file_path)
        assert file_type == FileType.TEST, f"Failed for {file_path}"


def test_detect_regular_file():
    """Regular source files."""
    classifier = FileClassificationService()

    file_type = classifier.classify_by_filename("utils/result.utils.ts")
    assert file_type == FileType.REGULAR


@pytest.mark.asyncio
async def test_is_barrel_heuristic_high_reexport_ratio():
    """File with >80% re-exports is a barrel."""
    classifier = FileClassificationService()

    # File with 10 lines, 9 are re-exports
    source = """// Comment
export { createSuccess } from './utils/result.utils';
export { createFailure } from './utils/result.utils';
export { Success } from './types/result.type';
export { Failure } from './types/result.type';
export { isSuccess } from './utils/result.utils';
export { isFailure } from './utils/result.utils';
export { map } from './utils/result.utils';
export { flatMap } from './utils/result.utils';
export type { ResultType } from './types/result.type';
"""

    metadata = {
        "re_exports": [
            {"symbol": "createSuccess", "source": "./utils/result.utils"},
            {"symbol": "createFailure", "source": "./utils/result.utils"},
            {"symbol": "Success", "source": "./types/result.type"},
            {"symbol": "Failure", "source": "./types/result.type"},
            {"symbol": "isSuccess", "source": "./utils/result.utils"},
            {"symbol": "isFailure", "source": "./utils/result.utils"},
            {"symbol": "map", "source": "./utils/result.utils"},
            {"symbol": "flatMap", "source": "./utils/result.utils"},
            {"symbol": "ResultType", "source": "./types/result.type", "is_type": True},
        ]
    }

    is_barrel = await classifier.is_barrel_heuristic(source, metadata)
    assert is_barrel is True


@pytest.mark.asyncio
async def test_is_barrel_heuristic_low_reexport_ratio():
    """File with <80% re-exports is NOT a barrel."""
    classifier = FileClassificationService()

    # File with implementation + some re-exports
    source = """// Utility functions
export function createSuccess<T>(value: T) {
  return new Success(value);
}

export function createFailure<T>(errors: Error[]) {
  return new Failure(errors);
}

// Re-export types
export type { ResultType } from './types/result.type';
"""

    metadata = {
        "re_exports": [
            {"symbol": "ResultType", "source": "./types/result.type", "is_type": True},
        ]
    }

    is_barrel = await classifier.is_barrel_heuristic(source, metadata)
    assert is_barrel is False
