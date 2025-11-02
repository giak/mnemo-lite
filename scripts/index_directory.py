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
    from services.metadata_extractor_service import get_metadata_extractor_service

    print("\n" + "=" * 80)
    print("📖 Phase 1/4: Code Chunking & AST Parsing")
    print("=" * 80)

    # EPIC-26: Inject metadata extractor service for TypeScript/JavaScript metadata extraction
    metadata_service = get_metadata_extractor_service()
    chunking_service = CodeChunkingService(max_workers=1, metadata_service=metadata_service)

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
    print("🧠 Phase 2/4: Embedding Generation")
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


async def phase3_metadata_extraction(
    chunks: list,
    repository: str,
    engine,
    chunk_to_node: dict,
    verbose: bool = False
):
    """
    Phase 3: Extract detailed metadata and store in dedicated tables.

    NOTE: This phase must run AFTER Phase 4 (graph construction) because
    the detailed_metadata and computed_metrics tables have foreign key
    constraints on the nodes table.

    For each chunk:
    1. Extract enriched metadata (call_contexts, signature, complexity)
    2. Store in detailed_metadata table using node_id from chunk_to_node mapping
    3. Create initial computed_metrics entry

    Args:
        chunks: List of code chunks
        repository: Repository name
        engine: Database engine
        chunk_to_node: Mapping from chunk_id to NodeModel (from graph construction)
        verbose: Enable verbose logging

    Returns:
        Tuple (success_count, error_count)
    """
    from collections import defaultdict
    from services.metadata_extractors.typescript_extractor import TypeScriptMetadataExtractor
    from db.repositories.detailed_metadata_repository import DetailedMetadataRepository
    from db.repositories.computed_metrics_repository import ComputedMetricsRepository
    from tree_sitter_language_pack import get_parser
    import json

    print("\n" + "=" * 80)
    print("📊 Phase 3/4: Detailed Metadata Extraction")
    print("=" * 80)

    metadata_repo = DetailedMetadataRepository(engine)
    metrics_repo = ComputedMetricsRepository(engine)

    success_count = 0
    error_count = 0

    start_time = datetime.now()

    # Group chunks by language
    chunks_by_language = defaultdict(list)
    for chunk in chunks:
        if chunk.language in ("typescript", "javascript"):
            # Only process chunks that have corresponding nodes
            if chunk.id in chunk_to_node:
                chunks_by_language[chunk.language].append(chunk)

    # Process TypeScript/JavaScript chunks
    for language, lang_chunks in chunks_by_language.items():
        print(f"\n   Processing {len(lang_chunks)} {language} chunks...")

        extractor = TypeScriptMetadataExtractor(language)
        parser = get_parser(language)

        for chunk in tqdm(lang_chunks, desc=f"   Extracting {language} metadata"):
            try:
                # Parse the chunk's source code directly
                tree = parser.parse(bytes(chunk.source_code, "utf8"))

                # For chunks, the root node represents the entire chunk
                # (function, class, method, etc.)
                node = tree.root_node

                # If root has a single child (common case), use that
                if len(node.children) == 1:
                    node = node.children[0]

                # Extract enriched metadata
                metadata = await extractor.extract_metadata(chunk.source_code, node, tree)

                # Get the actual node_id from the chunk_to_node mapping
                graph_node = chunk_to_node[chunk.id]
                node_id = graph_node.node_id

                # Store detailed metadata with correct node_id
                await metadata_repo.create(
                    node_id=node_id,
                    chunk_id=chunk.id,
                    metadata=metadata,
                    version=1
                )

                # Create initial metrics entry
                complexity = metadata.get("complexity", {})
                await metrics_repo.create(
                    node_id=node_id,
                    chunk_id=chunk.id,
                    repository=repository,
                    cyclomatic_complexity=complexity.get("cyclomatic", 0),
                    lines_of_code=complexity.get("lines_of_code", 0),
                    version=1
                )

                success_count += 1

            except Exception as e:
                if verbose:
                    print(f"\n   ⚠️  Failed to extract metadata for {chunk.name}: {e}")
                error_count += 1

    elapsed = (datetime.now() - start_time).total_seconds()

    print(f"\n   ✅ Phase 3 complete:")
    print(f"      Success: {success_count}")
    print(f"      Errors: {error_count}")
    print(f"      Time: {elapsed:.1f}s")

    return (success_count, error_count)


async def phase4_graph_construction(repository: str, verbose: bool = False):
    """
    Phase 4: Build graph (nodes + edges) from chunks and calculate metrics.

    Steps:
    1. Build graph (nodes + edges)
    2. Calculate coupling metrics (afferent/efferent)
    3. Calculate PageRank scores
    4. Calculate edge weights

    Uses GraphConstructionService with EPIC-30 anonymous filtering.

    Returns:
        Tuple (GraphStats, chunk_to_node mapping)
    """
    import os
    from services.graph_construction_service import GraphConstructionService
    from db.repositories.code_chunk_repository import CodeChunkRepository
    from db.repositories.node_repository import NodeRepository
    from sqlalchemy.ext.asyncio import create_async_engine

    print("\n" + "=" * 80)
    print("🔗 Phase 4/4: Graph Construction & Metrics")
    print("=" * 80)

    # Create database engine
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://mnemo:mnemo@mnemo-postgres:5432/mnemolite")
    engine = create_async_engine(db_url, echo=False)

    graph_service = GraphConstructionService(engine)

    print(f"\nBuilding graph and calculating metrics for repository: {repository}")

    start_time = datetime.now()

    # Build graph (includes EPIC-30 anonymous filtering + metrics calculation)
    stats = await graph_service.build_graph_for_repository(repository=repository)

    elapsed = (datetime.now() - start_time).total_seconds()

    print(f"\n✅ Graph constructed and metrics calculated in {elapsed:.1f}s")
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

    # Build chunk_to_node mapping for Phase 3 (metadata extraction)
    # Query nodes and match them to chunks by name_path
    print(f"\n   🔗 Building chunk-to-node mapping...")
    node_repo = NodeRepository(engine)
    chunk_repo = CodeChunkRepository(engine)

    nodes = await node_repo.get_by_repository(repository)
    chunks = await chunk_repo.get_by_repository(repository)

    # Build mapping: chunk_id -> node
    chunk_to_node = {}
    node_by_name_path = {node.label: node for node in nodes}  # Simplified matching by label

    for chunk in chunks:
        # Try to find matching node by name_path (or name if name_path not available)
        match_key = chunk.name_path if chunk.name_path else chunk.name
        if match_key in node_by_name_path:
            chunk_to_node[chunk.id] = node_by_name_path[match_key]
        elif chunk.name in node_by_name_path:
            chunk_to_node[chunk.id] = node_by_name_path[chunk.name]

    print(f"   - Mapped {len(chunk_to_node)}/{len(chunks)} chunks to nodes")

    await engine.dispose()

    return stats, chunk_to_node, chunks


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

    # Phase 3: Graph Construction
    # Note: Graph construction must run before metadata extraction because metadata tables
    # have foreign key constraints on nodes table
    graph_stats, chunk_to_node, db_chunks = await phase4_graph_construction(repository, args.verbose)

    # Phase 4: Metadata Extraction
    # Now that nodes exist, we can extract and store detailed metadata
    # Use db_chunks (chunks from database with IDs) instead of chunks (from Phase 1)
    import os
    from sqlalchemy.ext.asyncio import create_async_engine
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://mnemo:mnemo@mnemo-postgres:5432/mnemolite")
    engine = create_async_engine(db_url, echo=False)

    metadata_success, errors_phase3 = await phase3_metadata_extraction(
        db_chunks, repository, engine, chunk_to_node, args.verbose
    )

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
    print(f"   - With metadata: {metadata_success}")
    print(f"\n   Graph:")
    print(f"   - Nodes: {graph_stats.total_nodes}")
    print(f"   - Edges: {graph_stats.total_edges}")

    if graph_stats.total_nodes > 0:
        edge_ratio = (graph_stats.total_edges / graph_stats.total_nodes) * 100
        print(f"   - Edge ratio: {edge_ratio:.1f}%")

    # Show errors
    all_errors = errors_phase1 + errors_phase2 + ([] if metadata_success else [{"phase": "metadata", "error": "Phase 3 failed"}])
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


if __name__ == "__main__":
    asyncio.run(main())
