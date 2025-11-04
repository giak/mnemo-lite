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
from dataclasses import dataclass

# Add API to path
sys.path.insert(0, str(Path(__file__).parent.parent / "api"))


@dataclass
class FileProcessingResult:
    """Result of processing a single file atomically."""
    file_path: Path
    success: bool
    chunks_created: int
    error_message: str = ""


def worker_process_file(file_path: Path, repository: str, db_url: str) -> FileProcessingResult:
    """
    Worker function for Joblib - processes 1 file atomically.
    Each worker loads its own embedding model and creates DB connection.

    IMPORTANT: Must be top-level function (required by multiprocessing).

    Args:
        file_path: Path to source file
        repository: Repository name
        db_url: Database connection URL

    Returns:
        FileProcessingResult with success status and chunk count
    """
    import os
    import gc
    from sqlalchemy.ext.asyncio import create_async_engine
    import asyncio

    # Set embedding mode for this worker
    os.environ["EMBEDDING_MODE"] = "real"

    # Helper function to run async code in worker process
    async def _process_async():
        # Create worker-specific resources (NOT shared between workers)
        from services.dual_embedding_service import DualEmbeddingService
        embedding_service = DualEmbeddingService()
        engine = create_async_engine(db_url, echo=False, pool_size=2, max_overflow=0)

        try:
            # Run async processing
            result = await process_file_atomically(
                file_path, repository, embedding_service, engine
            )
            return result
        except Exception as e:
            # Catch any unhandled errors
            return FileProcessingResult(
                file_path=file_path,
                success=False,
                chunks_created=0,
                error_message=str(e)
            )
        finally:
            # Cleanup resources
            try:
                await engine.dispose()
            except Exception as e:
                # Log cleanup errors but don't fail the worker
                import logging
                logging.warning(f"Failed to dispose engine in worker cleanup: {e}")
            del embedding_service
            gc.collect()

    # Create new event loop for this worker process
    # Using ProcessPoolExecutor with 'spawn' gives us a clean process
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_process_async())
            return result
        finally:
            loop.close()
    except Exception as e:
        return FileProcessingResult(
            file_path=file_path,
            success=False,
            chunks_created=0,
            error_message=str(e)
        )


async def cleanup_repository(repository: str, engine):
    """
    Delete all existing data for a repository before reindexing.

    Deletes in order:
    1. edge_weights (FK to edges)
    2. computed_metrics (FK to nodes)
    3. detailed_metadata (FK to nodes)
    4. edges (FK to nodes)
    5. nodes (FK to code_chunks)
    6. code_chunks
    """
    from sqlalchemy.sql import text

    async with engine.begin() as conn:
        # Delete in reverse FK order
        await conn.execute(text("DELETE FROM edge_weights WHERE edge_id IN (SELECT edge_id FROM edges e JOIN nodes n ON e.source_node_id = n.node_id WHERE n.properties->>'repository' = :repo)"), {"repo": repository})

        await conn.execute(text("DELETE FROM computed_metrics WHERE repository = :repo"), {"repo": repository})

        await conn.execute(text("DELETE FROM detailed_metadata WHERE node_id IN (SELECT node_id FROM nodes WHERE properties->>'repository' = :repo)"), {"repo": repository})

        await conn.execute(text("DELETE FROM edges WHERE source_node_id IN (SELECT node_id FROM nodes WHERE properties->>'repository' = :repo)"), {"repo": repository})

        await conn.execute(text("DELETE FROM nodes WHERE properties->>'repository' = :repo"), {"repo": repository})

        # Delete chunks by file_path pattern
        await conn.execute(text("DELETE FROM code_chunks WHERE repository = :repo"), {"repo": repository})


async def process_file_atomically(
    file_path: Path,
    repository: str,
    embedding_service,
    engine
) -> FileProcessingResult:
    """
    Process a single source file completely and atomically.

    Steps performed in-memory:
    1. Chunk the file
    2. Generate embeddings for each chunk
    3. Extract metadata for each chunk
    4. Write all data to database in single transaction

    If any step fails, transaction rolls back automatically.

    Args:
        file_path: Path to source file
        repository: Repository name
        embedding_service: Pre-loaded DualEmbeddingService instance
        engine: SQLAlchemy async engine

    Returns:
        FileProcessingResult with success status and count
    """
    from services.code_chunking_service import CodeChunkingService
    from services.metadata_extractor_service import get_metadata_extractor_service
    from db.repositories.code_chunk_repository import CodeChunkRepository
    from models.code_chunk_models import CodeChunkCreate
    from services.dual_embedding_service import EmbeddingDomain

    chunks_created = 0

    try:
        # Step 1: Chunk file (in-memory)
        metadata_service = get_metadata_extractor_service()
        chunking_service = CodeChunkingService(max_workers=1, metadata_service=metadata_service)

        # Read file content
        content = file_path.read_text(encoding="utf-8")

        # Detect language
        language = "typescript" if file_path.suffix in {".ts", ".tsx"} else "javascript"

        # Chunk code
        chunks = await chunking_service.chunk_code(
            source_code=content,
            language=language,
            file_path=str(file_path)
        )

        if not chunks:
            return FileProcessingResult(
                file_path=file_path,
                success=True,
                chunks_created=0,
                error_message="No chunks extracted (empty or filtered)"
            )

        # Step 2 & 3: Generate embeddings + extract metadata (in-memory)
        chunk_creates = []

        for chunk in chunks:
            # Generate CODE embedding
            embedding_result = await embedding_service.generate_embedding(
                chunk.source_code,
                domain=EmbeddingDomain.CODE
            )

            # Create chunk model with embedding
            chunk_create = CodeChunkCreate(
                file_path=chunk.file_path,
                language=chunk.language,
                chunk_type=chunk.chunk_type,
                name=chunk.name,
                source_code=chunk.source_code,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                repository=repository,
                metadata=chunk.metadata,  # Already contains calls, imports from chunking
                embedding_text=None,
                embedding_code=embedding_result['code']
            )

            chunk_creates.append(chunk_create)

        # Step 4: Write to database atomically (single transaction)
        async with engine.begin() as conn:
            chunk_repo = CodeChunkRepository(engine, connection=conn)

            for chunk_create in chunk_creates:
                await chunk_repo.add(chunk_create)
                chunks_created += 1

        result = FileProcessingResult(
            file_path=file_path,
            success=True,
            chunks_created=chunks_created
        )

        # Force memory cleanup after each file
        embedding_service.force_memory_cleanup()

        return result

    except Exception as e:
        # Force memory cleanup even on error
        try:
            embedding_service.force_memory_cleanup()
        except Exception:
            pass  # Ignore cleanup errors

        return FileProcessingResult(
            file_path=file_path,
            success=False,
            chunks_created=0,
            error_message=str(e)
        )


def scan_files(directory: Path) -> list[Path]:
    """Scan directory for TypeScript/JavaScript files, applying filters."""
    files = []

    for ext in ["*.ts", "*.js"]:
        files.extend(directory.rglob(ext))

    # Filter out tests, node_modules, declarations
    filtered = []
    for f in files:
        path_str = str(f)
        # Check for node_modules
        if "node_modules" in path_str:
            continue
        # Check for declaration files
        if path_str.endswith(".d.ts"):
            continue
        # Check for test files (in file name, not in path)
        if ".test." in f.name or ".spec." in f.name or "__tests__" in path_str:
            continue
        filtered.append(f)

    return sorted(filtered)


async def run_streaming_pipeline_sequential(
    directory: Path,
    repository: str,
    verbose: bool = False,
    engine=None
) -> dict:
    """
    Run streaming pipeline: process files one-at-a-time with constant memory.

    Returns:
        Dict with statistics: total_files, success_files, error_files, total_chunks, errors
    """
    import os
    from services.dual_embedding_service import DualEmbeddingService
    from sqlalchemy.ext.asyncio import create_async_engine
    from tqdm import tqdm
    import gc

    # Database setup
    if engine is None:
        db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://mnemo:mnemopass@db:5432/mnemolite")
        engine = create_async_engine(db_url, echo=False)
        should_dispose = True
    else:
        should_dispose = False

    # Cleanup existing data
    if verbose:
        print(f"\n🧹 Cleaning up existing data for repository: {repository}")
    await cleanup_repository(repository, engine)

    # Scan files
    files = scan_files(directory)

    if verbose:
        print(f"\n📊 Found {len(files)} files to index")

    # Load embedding model ONCE
    if verbose:
        print(f"\n🔧 Loading embedding model...")
    os.environ["EMBEDDING_MODE"] = "real"
    embedding_service = DualEmbeddingService()

    # Stream files one-at-a-time
    success_count = 0
    error_count = 0
    total_chunks = 0
    errors = []

    with tqdm(total=len(files), desc="Processing files", disable=not verbose) as pbar:
        for file_path in files:
            result = await process_file_atomically(
                file_path=file_path,
                repository=repository,
                embedding_service=embedding_service,
                engine=engine
            )

            if result.success:
                success_count += 1
                total_chunks += result.chunks_created
            else:
                error_count += 1
                errors.append({
                    "file": str(file_path),
                    "error": result.error_message
                })
                if verbose:
                    print(f"\n   ⚠️  Failed: {file_path.name} - {result.error_message}")

            # Force comprehensive memory cleanup
            embedding_service.force_memory_cleanup()
            gc.collect()
            pbar.update(1)

    if should_dispose:
        await engine.dispose()

    return {
        "total_files": len(files),
        "success_files": success_count,
        "error_files": error_count,
        "total_chunks": total_chunks,
        "errors": errors
    }


async def run_parallel_pipeline(
    directory: Path,
    repository: str,
    n_jobs: int = 4,
    verbose: bool = False,
    engine=None
) -> dict:
    """
    Run parallel indexing pipeline with Joblib.

    Args:
        directory: Path to codebase
        repository: Repository name
        n_jobs: Number of parallel workers (default: 4)
        verbose: Enable detailed logging
        engine: Optional pre-created engine for cleanup phase

    Returns:
        dict with stats: total_files, success_files, error_files, total_chunks, errors
    """
    import os
    from sqlalchemy.ext.asyncio import create_async_engine

    # Create engine if not provided
    if not engine:
        db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://mnemo:mnemopass@db:5432/mnemolite")
        engine = create_async_engine(db_url, echo=False)
        should_dispose = True
    else:
        should_dispose = False

    # Phase 1: Cleanup (sequential)
    print("\n" + "=" * 80)
    print("🧹 Phase 1/3: Cleanup")
    print("=" * 80)
    await cleanup_repository(repository, engine)

    # Phase 2: Scan files
    print("\n" + "=" * 80)
    print("🔍 Phase 2/3: Scanning Files")
    print("=" * 80)
    files = scan_files(directory)
    print(f"📊 Found {len(files)} files to index")

    # Phase 3: Parallel processing with ProcessPoolExecutor
    print("\n" + "=" * 80)
    print(f"⚡ Phase 3/3: Parallel Processing ({n_jobs} workers)")
    print("=" * 80)

    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://mnemo:mnemopass@db:5432/mnemolite")

    print(f"🔧 Starting {n_jobs} parallel workers...")
    print(f"📈 Each worker will load its own embedding model (~2GB)")
    print(f"💾 Expected memory usage: ~{n_jobs * 3}GB")
    print()

    # Execute parallel processing
    # Use ProcessPoolExecutor for proper process isolation (Joblib has event loop conflicts)
    from concurrent.futures import ProcessPoolExecutor
    import multiprocessing

    # Set start method to 'spawn' to ensure clean worker processes
    ctx = multiprocessing.get_context('spawn')

    with ProcessPoolExecutor(max_workers=n_jobs, mp_context=ctx) as executor:
        # Submit all tasks
        futures = [
            executor.submit(worker_process_file, file_path, repository, db_url)
            for file_path in files
        ]

        # Collect results with progress indication
        results = []
        for i, future in enumerate(futures, 1):
            if not verbose:
                print(f"\rProcessing: {i}/{len(files)} files", end='', flush=True)
            result = future.result()  # Wait for completion
            results.append(result)
            if verbose:
                status = "✓" if result.success else "✗"
                print(f"{status} {result.file_path.name}: {result.chunks_created} chunks")

        if not verbose:
            print()  # New line after progress

    # Aggregate results
    success_count = sum(1 for r in results if r.success)
    error_count = len(results) - success_count
    total_chunks = sum(r.chunks_created for r in results)
    errors = [
        {"file": str(r.file_path), "error": r.error_message}
        for r in results if not r.success
    ]

    # Cleanup engine if we created it
    if should_dispose:
        await engine.dispose()

    return {
        "total_files": len(files),
        "success_files": success_count,
        "error_files": error_count,
        "total_chunks": total_chunks,
        "errors": errors
    }


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Index TypeScript/JavaScript codebase with parallel processing"
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
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)"
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Use sequential mode instead of parallel"
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
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://mnemo:mnemopass@db:5432/mnemolite")
    engine = create_async_engine(db_url, echo=False)

    embedding_service = DualEmbeddingService()
    chunk_repo = CodeChunkRepository(engine)

    print(f"\n🔧 Loading embedding model: jinaai/jina-embeddings-v2-base-code")
    print("   (This may take 1-2 minutes on first run...)")

    success_count = 0
    errors = []
    batch_size = 25  # Reduced from 50 to prevent OOM

    start_time = datetime.now()

    # Process in batches with progress bar
    total_batches = (len(chunks) + batch_size - 1) // batch_size
    print(f"   Processing {len(chunks)} chunks in {total_batches} batches of {batch_size}")

    with tqdm(total=len(chunks), desc="Generating embeddings", unit="chunk") as pbar:
        for batch_num, i in enumerate(range(0, len(chunks), batch_size), 1):
            batch = chunks[i:i + batch_size]

            if verbose:
                print(f"\n   📦 Batch {batch_num}/{total_batches} ({len(batch)} chunks)")

            # Process batch
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

            # Force garbage collection after each batch to free memory
            import gc
            gc.collect()

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


async def build_graph_phase(repository: str, engine) -> dict:
    """
    Phase 4: Build graph from indexed chunks.

    Steps:
    1. Create nodes from chunks
    2. Resolve edges (calls, imports)
    3. Calculate metrics (PageRank, coupling)
    4. Store everything

    Returns:
        Dict with stats: total_nodes, total_edges, or error dict on failure
    """
    from services.graph_construction_service import GraphConstructionService

    print("\n" + "=" * 80)
    print("🕸️  Phase 4: Graph Construction")
    print("=" * 80)

    try:
        graph_service = GraphConstructionService(engine)

        # Build graph for repository
        stats = await graph_service.build_graph_for_repository(
            repository=repository,
            languages=["typescript", "javascript"]
        )

        print(f"\n✅ Graph construction complete:")
        print(f"   - Nodes: {stats.total_nodes}")
        print(f"   - Edges: {stats.total_edges}")
        print(f"   - Nodes by type: {stats.nodes_by_type}")
        print(f"   - Edges by type: {stats.edges_by_type}")

        return {
            "total_nodes": stats.total_nodes,
            "total_edges": stats.total_edges,
            "nodes_by_type": stats.nodes_by_type,
            "edges_by_type": stats.edges_by_type
        }

    except Exception as e:
        print(f"\n❌ Graph construction failed: {e}")
        return {
            "total_nodes": 0,
            "total_edges": 0,
            "nodes_by_type": {},
            "edges_by_type": {},
            "error": str(e)
        }


async def main():
    """Main entry point for directory indexer."""
    import os
    from sqlalchemy.ext.asyncio import create_async_engine

    args = parse_args()

    # Validate directory
    if not args.directory.exists():
        print(f"❌ Directory not found: {args.directory}")
        sys.exit(1)

    if not args.directory.is_dir():
        print(f"❌ Path is not a directory: {args.directory}")
        sys.exit(1)

    directory = args.directory.resolve()
    repository = args.repository or directory.name

    print("=" * 80)
    print("🚀 MnemoLite Directory Indexer")
    print("=" * 80)
    print(f"\n📁 Repository: {repository}")
    print(f"📂 Path: {directory}")

    start_time = datetime.now()

    # Create database engine for graph construction
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://mnemo:mnemopass@db:5432/mnemolite")
    engine = create_async_engine(db_url, echo=False)

    # Run pipeline (parallel by default, sequential if --sequential flag)
    if args.sequential:
        print("🐌 Running in SEQUENTIAL mode")
        stats = await run_streaming_pipeline_sequential(
            directory, repository, verbose=args.verbose, engine=engine
        )
    else:
        print(f"⚡ Running in PARALLEL mode with {args.workers} workers")
        stats = await run_parallel_pipeline(
            directory, repository, n_jobs=args.workers, verbose=args.verbose, engine=engine
        )

    # Run Phase 4: Graph Construction
    if stats['success_files'] > 0:
        graph_stats = await build_graph_phase(repository, engine)
        stats['graph'] = graph_stats

    await engine.dispose()

    elapsed = (datetime.now() - start_time).total_seconds()

    # Print summary
    print("\n" + "=" * 80)
    print("✅ INDEXING COMPLETE")
    print("=" * 80)
    print(f"   - Total files: {stats['total_files']}")
    print(f"   - Success: {stats['success_files']} ({stats['success_files']*100//stats['total_files'] if stats['total_files'] > 0 else 0}%)")
    print(f"   - Errors: {stats['error_files']}")
    print(f"   - Total chunks: {stats['total_chunks']}")
    if 'graph' in stats:
        print(f"   - Graph nodes: {stats['graph'].get('total_nodes', 0)}")
        print(f"   - Graph edges: {stats['graph'].get('total_edges', 0)}")
    print(f"   - Time: {elapsed:.1f}s ({elapsed/60:.1f}m)")

    if stats['errors']:
        print(f"\n❌ Failed files ({len(stats['errors'])}):")
        for error in stats['errors'][:10]:  # Show first 10
            print(f"   - {error['file']}")
            print(f"     Error: {error['error'][:100]}")  # Truncate long errors


if __name__ == "__main__":
    asyncio.run(main())
