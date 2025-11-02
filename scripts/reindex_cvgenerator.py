#!/usr/bin/env python3
"""
Re-index CVGenerator repository with EPIC-30 anonymous function filtering.

This script:
1. Scans CVGenerator directory for .ts/.js files
2. Indexes them using CodeIndexingService
3. Builds graph with anonymous filtering enabled
4. Reports results
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# Add API path
sys.path.insert(0, str(Path(__file__).parent.parent / "api"))

async def main():
    print("=" * 80)
    print("🚀 CVGenerator Re-Indexing with EPIC-30 Anonymous Filtering")
    print("=" * 80)

    from sqlalchemy.ext.asyncio import create_async_engine
    from services.code_indexing_service import (
        CodeIndexingService,
        FileInput,
        IndexingOptions
    )

    # Database connection
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://mnemo:mnemo@localhost:5432/mnemolite")
    engine = create_async_engine(db_url, echo=False)

    # Repository info
    repository = "CVGenerator"
    repo_path = Path("/app/CVGenerator")

    # Check if repository exists
    if not repo_path.exists():
        print(f"❌ Repository not found: {repo_path}")
        print(f"   Trying alternative path...")
        repo_path = Path.cwd() / "CVGenerator"
        if not repo_path.exists():
            print(f"❌ Repository not found: {repo_path}")
            await engine.dispose()
            return

    print(f"\n📁 Repository: {repo_path}")

    # Scan for TypeScript/JavaScript files
    print(f"\n🔍 Scanning for TypeScript/JavaScript files...")
    files_to_index = []
    extensions = {".ts", ".js", ".tsx", ".jsx"}

    for ext in extensions:
        found = list(repo_path.rglob(f"*{ext}"))
        print(f"   - Found {len(found)} {ext} files")
        files_to_index.extend(found)

    # Filter out node_modules and test files
    files_to_index = [
        f for f in files_to_index
        if "node_modules" not in str(f) and "__tests__" not in str(f)
    ]

    print(f"\n📊 Total files to index: {len(files_to_index)}")

    if len(files_to_index) == 0:
        print("❌ No files found to index!")
        await engine.dispose()
        return

    # Create indexing service
    indexing_service = CodeIndexingService(engine)

    # Prepare file inputs
    file_inputs = []
    print(f"\n📖 Reading file contents...")
    for file_path in files_to_index[:10]:  # Limit to 10 files for testing
        try:
            content = file_path.read_text(encoding="utf-8")
            language = "typescript" if file_path.suffix in {".ts", ".tsx"} else "javascript"
            file_inputs.append(FileInput(
                path=str(file_path),
                content=content,
                language=language
            ))
        except Exception as e:
            print(f"   ⚠️  Failed to read {file_path.name}: {e}")

    print(f"   ✅ Loaded {len(file_inputs)} files")

    # Index options
    options = IndexingOptions(
        extract_metadata=True,
        generate_embeddings=False,  # Skip embeddings for speed
        build_graph=True,
        repository=repository,
        repository_root=str(repo_path),
        commit_hash=None
    )

    # Index repository
    print(f"\n⚙️  Indexing repository...")
    start_time = datetime.now()

    try:
        summary = await indexing_service.index_repository(file_inputs, options)

        elapsed = (datetime.now() - start_time).total_seconds()

        print(f"\n" + "=" * 80)
        print("✅ INDEXING COMPLETE!")
        print("=" * 80)
        print(f"📊 Statistics:")
        print(f"   - Files indexed: {summary.indexed_files}")
        print(f"   - Files failed: {summary.failed_files}")
        print(f"   - Chunks created: {summary.indexed_chunks}")
        print(f"   - Nodes created: {summary.indexed_nodes} (anonymous filtered!)")
        print(f"   - Edges created: {summary.indexed_edges}")
        print(f"   - Processing time: {summary.processing_time_ms / 1000:.2f}s")

        if summary.indexed_nodes > 0:
            edge_ratio = (summary.indexed_edges / summary.indexed_nodes) * 100
            print(f"   - Edge ratio: {edge_ratio:.1f}%")

        if summary.errors:
            print(f"\n⚠️  Errors ({len(summary.errors)}):")
            for error in summary.errors[:5]:
                print(f"   - {error.get('file', 'unknown')}: {error.get('error', 'unknown error')}")

        print("\n🎨 View graph at: http://localhost:3002/")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Indexing failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
