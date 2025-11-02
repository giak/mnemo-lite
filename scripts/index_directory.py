#!/usr/bin/env python3
"""
Index entire directory of TypeScript/JavaScript code into MnemoLite.

Usage:
    python scripts/index_directory.py /path/to/code --repository name
"""

import asyncio
import argparse
import sys
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

# Add API to path
sys.path.insert(0, str(Path(__file__).parent.parent / "api"))


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Index TypeScript/JavaScript codebase into MnemoLite"
    )
    parser.add_argument(
        "directory",
        type=Path,
        help="Path to directory to index"
    )
    parser.add_argument(
        "--repository",
        type=str,
        default=None,
        help="Repository name (default: directory name)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    return parser.parse_args()


def scan_directory(directory: Path, verbose: bool = False) -> dict:
    """
    Scan directory for TypeScript/JavaScript files with filtering.

    Include: .ts, .tsx, .js, .jsx
    Exclude: *.test.ts, *.spec.ts, __tests__/, node_modules/, *.d.ts

    Returns:
        Dict with 'files' (list of Paths), 'stats' (dict of counts)
    """
    # Extensions to include
    extensions = {".ts", ".tsx", ".js", ".jsx"}

    # Patterns to exclude
    exclude_patterns = [
        "node_modules",
        "__tests__",
        ".test.",
        ".spec.",
        ".d.ts"
    ]

    # Scan recursively
    all_files = []
    excluded_counts = {
        "tests": 0,
        "node_modules": 0,
        "declarations": 0
    }

    for ext in extensions:
        found = list(directory.rglob(f"*{ext}"))

        for file_path in found:
            path_str = str(file_path)

            # Check exclusions
            if "node_modules" in path_str:
                excluded_counts["node_modules"] += 1
                continue

            if "__tests__" in path_str or ".test." in file_path.name or ".spec." in file_path.name:
                excluded_counts["tests"] += 1
                continue

            if file_path.suffix == ".ts" and file_path.name.endswith(".d.ts"):
                excluded_counts["declarations"] += 1
                continue

            all_files.append(file_path)

    # Count by extension
    by_ext = {}
    for file_path in all_files:
        ext = file_path.suffix
        by_ext[ext] = by_ext.get(ext, 0) + 1

    if verbose:
        print(f"\n   Found files:")
        for ext, count in sorted(by_ext.items()):
            print(f"   - {ext} files: {count}")

        print(f"\n   Filtered out:")
        for category, count in excluded_counts.items():
            print(f"   - {category}: {count}")

    return {
        "files": all_files,
        "stats": {
            "by_extension": by_ext,
            "excluded": excluded_counts,
            "total": len(all_files)
        }
    }


async def phase1_chunking(files: list[Path], repository: str, verbose: bool = False):
    """
    Phase 1: Parse files and create semantic chunks.

    Returns:
        Tuple (chunks: list, errors: list)
    """
    from services.code_chunking_service import CodeChunkingService

    print("\n" + "=" * 80)
    print("📖 Phase 1/3: Code Chunking & AST Parsing")
    print("=" * 80)

    chunking_service = CodeChunkingService(max_workers=4)

    all_chunks = []
    errors = []

    start_time = datetime.now()

    # Progress bar
    with tqdm(total=len(files), desc="Chunking files", unit="file") as pbar:
        for file_path in files:
            try:
                # Read file
                content = file_path.read_text(encoding="utf-8")

                # Detect language
                language = "typescript" if file_path.suffix in {".ts", ".tsx"} else "javascript"

                # Chunk code (note: no 'repository' parameter)
                chunks = await chunking_service.chunk_code(
                    source_code=content,
                    language=language,
                    file_path=str(file_path.relative_to(file_path.parent.parent.parent))
                )

                # Set repository on chunks
                for chunk in chunks:
                    chunk.repository = repository

                all_chunks.extend(chunks)

            except Exception as e:
                errors.append({
                    "file": str(file_path),
                    "error": str(e),
                    "phase": "chunking"
                })
                if verbose:
                    print(f"\n   ⚠️  Failed: {file_path.name} - {e}")

            pbar.update(1)

    elapsed = (datetime.now() - start_time).total_seconds()

    print(f"\n✅ Chunking complete in {elapsed:.1f}s")
    print(f"   - Chunks created: {len(all_chunks)}")
    print(f"   - Files succeeded: {len(files) - len(errors)}")
    print(f"   - Files failed: {len(errors)}")

    return all_chunks, errors


async def main():
    """Main indexing pipeline."""
    args = parse_args()

    # Validate directory
    if not args.directory.exists():
        print(f"❌ Directory not found: {args.directory}")
        sys.exit(1)

    if not args.directory.is_dir():
        print(f"❌ Path is not a directory: {args.directory}")
        sys.exit(1)

    # Set repository name
    repository = args.repository or args.directory.name

    print("=" * 80)
    print("🚀 MnemoLite Directory Indexer")
    print("=" * 80)
    print(f"\n📁 Repository: {repository}")
    print(f"📂 Path: {args.directory.absolute()}")

    # Phase 0: Scan directory
    print("\n🔍 Scanning for TypeScript/JavaScript files...")

    scan_result = scan_directory(args.directory, verbose=args.verbose)
    files = scan_result["files"]
    stats = scan_result["stats"]

    if stats["total"] == 0:
        print("\n❌ No TypeScript/JavaScript files found!")
        sys.exit(1)

    print(f"\n   📊 Total to index: {stats['total']} files")

    # Phase 1: Chunking
    chunks, errors_phase1 = await phase1_chunking(files, repository, args.verbose)

    if len(chunks) == 0:
        print("\n❌ No chunks created! All files failed.")
        sys.exit(1)

    # TODO: Phase 2-3
    print("\n⚠️  Embedding/Graph not yet implemented")


if __name__ == "__main__":
    asyncio.run(main())
