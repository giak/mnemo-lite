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


async def phase2_embeddings(chunks: list, repository: str, verbose: bool = False):
    """
    Phase 2: Generate embeddings and persist chunks to database.

    Activates real embeddings (overrides EMBEDDING_MODE=mock).

    Returns:
        Tuple (success_count: int, errors: list)
    """
    import os
    from services.dual_embedding_service import DualEmbeddingService, EmbeddingDomain
    from db.repositories.code_chunk_repository import CodeChunkRepository
    from models.code_chunk_models import CodeChunkCreate
    from sqlalchemy.ext.asyncio import create_async_engine

    print("\n" + "=" * 80)
    print("🧠 Phase 2/3: Embedding Generation")
    print("=" * 80)

    # Override embedding mode to use real embeddings
    os.environ["EMBEDDING_MODE"] = "real"

    # Create database engine
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://mnemo:mnemo@mnemo-postgres:5432/mnemolite")
    engine = create_async_engine(db_url, echo=False)

    embedding_service = DualEmbeddingService()
    chunk_repo = CodeChunkRepository(engine)

    print(f"\n🔧 Loading embedding model: jinaai/jina-embeddings-v2-base-code")
    print("   (This may take 1-2 minutes on first run...)")

    success_count = 0
    errors = []
    batch_size = 50

    start_time = datetime.now()

    # Process in batches with progress bar
    with tqdm(total=len(chunks), desc="Generating embeddings", unit="chunk") as pbar:
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]

            for chunk in batch:
                try:
                    # Generate CODE embedding
                    embedding_result = await embedding_service.generate_embedding(
                        chunk.source_code,
                        domain=EmbeddingDomain.CODE
                    )

                    # Create chunk with embedding
                    chunk_create = CodeChunkCreate(
                        file_path=chunk.file_path,
                        language=chunk.language,
                        chunk_type=chunk.chunk_type,
                        name=chunk.name,
                        source_code=chunk.source_code,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        repository=chunk.repository,
                        metadata=chunk.metadata,
                        embedding_text=None,  # Skip text embedding for code
                        embedding_code=embedding_result['code']
                    )

                    # Persist to database
                    await chunk_repo.add(chunk_create)
                    success_count += 1

                except Exception as e:
                    errors.append({
                        "chunk": f"{chunk.file_path}:{chunk.name}",
                        "error": str(e),
                        "phase": "embedding"
                    })
                    if verbose:
                        print(f"\n   ⚠️  Failed: {chunk.name} - {e}")

                pbar.update(1)

    elapsed = (datetime.now() - start_time).total_seconds()

    print(f"\n✅ Embeddings generated in {elapsed:.1f}s ({elapsed/60:.1f}m)")
    print(f"   - Code embeddings: {success_count}")
    print(f"   - Average time/chunk: {elapsed/len(chunks):.2f}s")
    print(f"   - Stored in database: ✅")
    print(f"   - Failed: {len(errors)}")

    await engine.dispose()

    return success_count, errors


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

    # Phase 2: Embeddings
    success_count, errors_phase2 = await phase2_embeddings(chunks, repository, args.verbose)

    if success_count == 0:
        print("\n❌ No embeddings generated! All chunks failed.")
        sys.exit(1)

    # TODO: Phase 3
    print("\n⚠️  Graph construction not yet implemented")


if __name__ == "__main__":
    asyncio.run(main())
