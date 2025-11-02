# Directory Indexing Script Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create CLI script to index entire TypeScript/JavaScript codebases with real embeddings and graph construction

**Architecture:** 3-phase pipeline (Scan/Chunk → Embeddings → Graph) orchestrating existing services (CodeChunkingService, DualEmbeddingService, GraphConstructionService) with detailed console progress reporting

**Tech Stack:** Python 3.12, asyncio, pathlib, tqdm (progress bars), existing MnemoLite services

---

## Task 1: Create Script Structure with CLI Parsing

**Files:**
- Create: `scripts/index_directory.py`
- Reference: `api/services/code_indexing_service.py` (pipeline example)

**Step 1: Write basic script structure**

```python
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

    # TODO: Implement phases
    print("\n⚠️  Pipeline not yet implemented")


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 2: Test CLI argument parsing**

Run:
```bash
python scripts/index_directory.py /home/giak/Work/MnemoLite/code_test
```

Expected output:
```
================================================================================
🚀 MnemoLite Directory Indexer
================================================================================

📁 Repository: code_test
📂 Path: /home/giak/Work/MnemoLite/code_test

⚠️  Pipeline not yet implemented
```

**Step 3: Test error handling**

Run:
```bash
python scripts/index_directory.py /nonexistent/path
```

Expected output:
```
❌ Directory not found: /nonexistent/path
```
Exit code: 1

**Step 4: Commit**

```bash
git add scripts/index_directory.py
git commit -m "feat: Add directory indexer script skeleton with CLI parsing

- Argument parsing for directory and repository name
- Directory validation
- Basic console output structure

🤖 Generated with Claude Code"
```

---

## Task 2: Implement File Scanning with Filtering

**Files:**
- Modify: `scripts/index_directory.py`

**Step 1: Add file scanning function**

After `parse_args()`, add:

```python
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
```

**Step 2: Integrate scanning into main()**

In `main()`, replace `# TODO: Implement phases` with:

```python
    # Phase 0: Scan directory
    print("\n🔍 Scanning for TypeScript/JavaScript files...")

    scan_result = scan_directory(args.directory, verbose=args.verbose)
    files = scan_result["files"]
    stats = scan_result["stats"]

    if stats["total"] == 0:
        print("\n❌ No TypeScript/JavaScript files found!")
        sys.exit(1)

    print(f"\n   📊 Total to index: {stats['total']} files")

    # TODO: Phase 1-3
    print("\n⚠️  Chunking/Embedding/Graph not yet implemented")
```

**Step 3: Test scanning**

Run:
```bash
python scripts/index_directory.py /home/giak/Work/MnemoLite/code_test --verbose
```

Expected output:
```
🔍 Scanning for TypeScript/JavaScript files...

   Found files:
   - .js files: 12
   - .ts files: 210
   - .tsx files: 35
   - .jsx files: 2

   Filtered out:
   - tests: 89
   - node_modules: 1245
   - declarations: 45

   📊 Total to index: 259 files

⚠️  Chunking/Embedding/Graph not yet implemented
```

**Step 4: Commit**

```bash
git add scripts/index_directory.py
git commit -m "feat: Add file scanning with TypeScript/JavaScript filtering

- Scan recursively for .ts/.tsx/.js/.jsx
- Exclude tests, node_modules, declaration files
- Report stats by extension

🤖 Generated with Claude Code"
```

---

## Task 3: Implement Phase 1 - Code Chunking

**Files:**
- Modify: `scripts/index_directory.py`

**Step 1: Add chunking phase with progress bar**

After imports, add:
```python
from tqdm import tqdm
```

After `scan_directory()`, add:

```python
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
```

**Step 2: Integrate into main()**

In `main()`, replace `# TODO: Phase 1-3` with:

```python
    # Phase 1: Chunking
    chunks, errors_phase1 = await phase1_chunking(files, repository, args.verbose)

    if len(chunks) == 0:
        print("\n❌ No chunks created! All files failed.")
        sys.exit(1)

    # TODO: Phase 2-3
    print("\n⚠️  Embedding/Graph not yet implemented")
```

**Step 3: Test chunking**

Run in Docker:
```bash
docker exec -i mnemo-api python3 /app/scripts/index_directory.py /app/code_test --repository code_test
```

Expected output:
```
================================================================================
📖 Phase 1/3: Code Chunking & AST Parsing
================================================================================

Chunking files: 100%|██████████| 259/259 [00:52<00:00,  4.92file/s]

✅ Chunking complete in 52.7s
   - Chunks created: 1247
   - Files succeeded: 256
   - Files failed: 3

⚠️  Embedding/Graph not yet implemented
```

**Step 4: Commit**

```bash
git add scripts/index_directory.py
git commit -m "feat: Implement Phase 1 - Code chunking with progress

- Use CodeChunkingService for AST parsing
- Progress bar with tqdm
- Error handling (continue on failure)
- Report stats and timing

🤖 Generated with Claude Code"
```

---

## Task 4: Implement Phase 2 - Embedding Generation

**Files:**
- Modify: `scripts/index_directory.py`

**Step 1: Add embedding phase**

After `phase1_chunking()`, add:

```python
async def phase2_embeddings(chunks: list, repository: str, verbose: bool = False):
    """
    Phase 2: Generate embeddings and persist chunks to database.

    Activates real embeddings (overrides EMBEDDING_MODE=mock).

    Returns:
        Tuple (success_count: int, errors: list)
    """
    import os
    from services.dual_embedding_service import DualEmbeddingService
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
                    code_embedding = await embedding_service.generate_code_embedding(
                        chunk.source_code
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
                        text_embedding=None,  # Skip text embedding for code
                        code_embedding=code_embedding
                    )

                    # Persist to database
                    await chunk_repo.create_chunk(chunk_create)
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
```

**Step 2: Integrate into main()**

In `main()`, replace `# TODO: Phase 2-3` with:

```python
    # Phase 2: Embeddings
    success_count, errors_phase2 = await phase2_embeddings(chunks, repository, args.verbose)

    if success_count == 0:
        print("\n❌ No embeddings generated! All chunks failed.")
        sys.exit(1)

    # TODO: Phase 3
    print("\n⚠️  Graph construction not yet implemented")
```

**Step 3: Test embeddings**

Run in Docker:
```bash
docker exec -i mnemo-api python3 /app/scripts/index_directory.py /app/code_test --repository code_test
```

Expected output:
```
================================================================================
🧠 Phase 2/3: Embedding Generation
================================================================================

🔧 Loading embedding model: jinaai/jina-embeddings-v2-base-code
   (This may take 1-2 minutes on first run...)

Generating embeddings: 100%|██████████| 1247/1247 [03:45<00:00,  5.54chunk/s]

✅ Embeddings generated in 225.3s (3.8m)
   - Code embeddings: 1244
   - Average time/chunk: 0.18s
   - Stored in database: ✅
   - Failed: 3

⚠️  Graph construction not yet implemented
```

**Step 4: Commit**

```bash
git add scripts/index_directory.py
git commit -m "feat: Implement Phase 2 - Embedding generation

- Activate real embeddings (override EMBEDDING_MODE)
- Use DualEmbeddingService for CODE embeddings
- Persist chunks to database with CodeChunkRepository
- Progress bar for batch processing

🤖 Generated with Claude Code"
```

---

## Task 5: Implement Phase 3 - Graph Construction

**Files:**
- Modify: `scripts/index_directory.py`

**Step 1: Add graph construction phase**

After `phase2_embeddings()`, add:

```python
async def phase3_graph(repository: str, verbose: bool = False):
    """
    Phase 3: Build graph (nodes + edges) from chunks.

    Uses GraphConstructionService with EPIC-30 anonymous filtering.

    Returns:
        GraphStats object
    """
    import os
    from services.graph_construction_service import GraphConstructionService
    from sqlalchemy.ext.asyncio import create_async_engine

    print("\n" + "=" * 80)
    print("🔗 Phase 3/3: Graph Construction")
    print("=" * 80)

    # Create database engine
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://mnemo:mnemo@mnemo-postgres:5432/mnemolite")
    engine = create_async_engine(db_url, echo=False)

    graph_service = GraphConstructionService(engine)

    print(f"\nBuilding graph for repository: {repository}")

    start_time = datetime.now()

    # Build graph (includes EPIC-30 anonymous filtering)
    stats = await graph_service.build_graph_for_repository(repository=repository)

    elapsed = (datetime.now() - start_time).total_seconds()

    print(f"\n✅ Graph constructed in {elapsed:.1f}s")
    print(f"   - Nodes: {stats.total_nodes}")
    print(f"   - Edges: {stats.total_edges}")

    if stats.total_nodes > 0:
        edge_ratio = (stats.total_edges / stats.total_nodes) * 100
        print(f"   - Edge ratio: {edge_ratio:.1f}%")

    # Show node breakdown
    if stats.nodes_by_type:
        print(f"\n   📋 Nodes by type:")
        for node_type, count in sorted(stats.nodes_by_type.items(), key=lambda x: -x[1])[:5]:
            print(f"      - {node_type}: {count}")

    # Show edge breakdown
    if stats.edges_by_type:
        print(f"\n   🔗 Edges by type:")
        for edge_type, count in stats.edges_by_type.items():
            print(f"      - {edge_type}: {count}")

    await engine.dispose()

    return stats
```

**Step 2: Integrate into main()**

In `main()`, replace `# TODO: Phase 3` with:

```python
    # Phase 3: Graph Construction
    graph_stats = await phase3_graph(repository, args.verbose)

    # Final summary
    print("\n" + "=" * 80)
    print("✅ INDEXING COMPLETE!")
    print("=" * 80)
    print(f"\n📊 Final Summary:")
    print(f"   Repository: {repository}")
    print(f"\n   Files:")
    print(f"   - Scanned: {stats['total']}")
    print(f"   - Succeeded: {stats['total'] - len(errors_phase1)}")
    print(f"   - Failed: {len(errors_phase1)}")
    print(f"\n   Chunks:")
    print(f"   - Created: {len(chunks)}")
    print(f"   - With embeddings: {success_count}")
    print(f"\n   Graph:")
    print(f"   - Nodes: {graph_stats.total_nodes}")
    print(f"   - Edges: {graph_stats.total_edges}")

    if graph_stats.total_nodes > 0:
        edge_ratio = (graph_stats.total_edges / graph_stats.total_nodes) * 100
        print(f"   - Edge ratio: {edge_ratio:.1f}%")

    # Show errors
    all_errors = errors_phase1 + errors_phase2
    if all_errors:
        print(f"\n⚠️  Failed Items ({len(all_errors)}):")
        for i, error in enumerate(all_errors[:5], 1):
            item = error.get("file") or error.get("chunk")
            print(f"   {i}. {item}")
            print(f"      Error: {error['error']}")

        if len(all_errors) > 5:
            print(f"   ... and {len(all_errors) - 5} more")

    print(f"\n🎨 View graph at: http://localhost:3002/")
    print(f"   Select repository: {repository}")
    print("=" * 80)
```

**Step 3: Test full pipeline**

Run in Docker:
```bash
docker exec -i mnemo-api python3 /app/scripts/index_directory.py /app/code_test --repository code_test
```

Expected output:
```
================================================================================
🔗 Phase 3/3: Graph Construction
================================================================================

Building graph for repository: code_test

✅ Graph constructed in 11.7s
   - Nodes: 850
   - Edges: 324
   - Edge ratio: 38.1%

   📋 Nodes by type:
      - Function: 425
      - Class: 285
      - Method: 140

   🔗 Edges by type:
      - calls: 278
      - imports: 46

================================================================================
✅ INDEXING COMPLETE!
================================================================================

📊 Final Summary:
   Repository: code_test

   Files:
   - Scanned: 259
   - Succeeded: 256
   - Failed: 3

   Chunks:
   - Created: 1247
   - With embeddings: 1244

   Graph:
   - Nodes: 850
   - Edges: 324
   - Edge ratio: 38.1%

🎨 View graph at: http://localhost:3002/
   Select repository: code_test
================================================================================
```

**Step 4: Commit**

```bash
git add scripts/index_directory.py
git commit -m "feat: Implement Phase 3 - Graph construction

- Use GraphConstructionService (with EPIC-30 filtering)
- Report nodes/edges statistics
- Final summary with errors
- Complete 3-phase pipeline

🤖 Generated with Claude Code"
```

---

## Task 6: Make Script Executable and Test End-to-End

**Files:**
- Modify: `scripts/index_directory.py`

**Step 1: Add shebang and make executable**

Ensure first line of script is:
```python
#!/usr/bin/env python3
```

Run:
```bash
chmod +x scripts/index_directory.py
```

**Step 2: Copy script to container**

```bash
docker cp scripts/index_directory.py mnemo-api:/app/scripts/
```

**Step 3: Run full end-to-end test**

```bash
docker exec -i mnemo-api python3 /app/scripts/index_directory.py /app/code_test --repository code_test --verbose
```

Expected: Complete run with all 3 phases, ~5 minutes total

**Step 4: Verify in database**

```bash
docker exec -i mnemo-postgres psql -U mnemo -d mnemolite -c "
SELECT COUNT(*) as chunks FROM code_chunks WHERE repository = 'code_test';
"
```

Expected: ~1244 chunks

```bash
docker exec -i mnemo-postgres psql -U mnemo -d mnemolite -c "
SELECT COUNT(*) as nodes FROM nodes WHERE properties->>'repository' = 'code_test';
"
```

Expected: ~850 nodes

**Step 5: Verify in UI**

1. Open http://localhost:3002/
2. Select repository: "code_test"
3. Verify graph is visible with nodes and edges

Expected: Graph displayed with 850 nodes, 324 edges

**Step 6: Commit**

```bash
git add scripts/index_directory.py
chmod +x scripts/index_directory.py
git add scripts/index_directory.py
git commit -m "feat: Finalize directory indexing script

Complete 3-phase pipeline:
- Phase 1: Chunking (AST parsing)
- Phase 2: Embeddings (real CODE embeddings)
- Phase 3: Graph construction (EPIC-30 filtering)

Features:
- Detailed progress bars (tqdm)
- Error resilience (continue on failure)
- Comprehensive reporting
- TypeScript/JavaScript filtering

Tested on code_test (259 files → 850 nodes, 324 edges)

🤖 Generated with Claude Code"
```

---

## Task 7: Add Installation Instructions

**Files:**
- Create: `scripts/README.md`

**Step 1: Create README**

```markdown
# MnemoLite Indexing Scripts

## Directory Indexer

Index entire TypeScript/JavaScript codebases into MnemoLite.

### Requirements

- Python 3.12+
- Docker (for running in container)
- tqdm: `pip install tqdm`

### Usage

**In Docker (recommended)**:
```bash
# Copy script to container
docker cp scripts/index_directory.py mnemo-api:/app/scripts/

# Run indexing
docker exec -i mnemo-api python3 /app/scripts/index_directory.py \
  /app/code_test \
  --repository code_test \
  --verbose
```

**On Host**:
```bash
# Ensure DATABASE_URL is set
export DATABASE_URL="postgresql+asyncpg://mnemo:mnemo@localhost:5432/mnemolite"

# Run indexing
python scripts/index_directory.py /path/to/code --repository myproject
```

### Options

- `directory` (required): Path to codebase
- `--repository` (optional): Repository name (default: directory name)
- `--verbose`: Enable detailed logging

### Pipeline

1. **Phase 1: Chunking** (~1 min)
   - Scans TypeScript/JavaScript files
   - Excludes tests, node_modules, declarations
   - AST parsing with tree-sitter

2. **Phase 2: Embeddings** (~3-5 min)
   - Generates CODE embeddings (768D)
   - Uses jinaai/jina-embeddings-v2-base-code
   - Stores in PostgreSQL

3. **Phase 3: Graph** (~10-20s)
   - Creates nodes (functions, classes)
   - Resolves call/import edges
   - EPIC-30: Filters anonymous functions

### Performance

- 100 files: ~2 minutes
- 500 files: ~8 minutes
- 1000 files: ~15 minutes

Bottleneck: Embedding generation (CPU-bound)

### Viewing Results

1. Open http://localhost:3002/
2. Select repository from dropdown
3. Explore graph visualization
```

**Step 2: Commit**

```bash
git add scripts/README.md
git commit -m "docs: Add directory indexer usage instructions

- Installation requirements
- Usage examples (Docker + host)
- Pipeline explanation
- Performance expectations

🤖 Generated with Claude Code"
```

---

## Execution Plan Summary

**Total Tasks**: 7
**Estimated Time**: 45-60 minutes
**Order**: Sequential (each task builds on previous)

**Key Deliverables**:
1. ✅ Functional CLI script (`scripts/index_directory.py`)
2. ✅ 3-phase pipeline (Chunk → Embed → Graph)
3. ✅ Real embeddings with jinaai/jina-embeddings-v2-base-code
4. ✅ Progress bars and detailed reporting
5. ✅ Error resilience (continue on failure)
6. ✅ Documentation (README)
7. ✅ Tested on code_test (259 files → 850 nodes)

**Success Criteria**:
- Script indexes code_test in ~5 minutes
- Graph visible in UI with 800+ nodes
- <5 file failures
- Embeddings stored in database
- EPIC-30 filtering active (reduces anonymes)
