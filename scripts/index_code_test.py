#!/usr/bin/env python3
"""
Index code_test repository with full pipeline:
- Code chunking
- Embeddings generation (text + code)
- Graph construction
- EPIC-30 anonymous filtering
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "api"))

async def main():
    print("=" * 80)
    print("🚀 Indexing code_test Repository")
    print("=" * 80)

    from sqlalchemy.ext.asyncio import create_async_engine
    from services.code_chunking_service import CodeChunkingService
    from services.dual_embedding_service import DualEmbeddingService
    from services.graph_construction_service import GraphConstructionService
    from db.repositories.code_chunk_repository import CodeChunkRepository
    from models.code_chunk_models import CodeChunkCreate

    # Database connection
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://mnemo:mnemo@localhost:5432/mnemolite")
    engine = create_async_engine(db_url, echo=False)

    repository = "code_test"
    repo_path = Path("/app/code_test")

    if not repo_path.exists():
        print(f"❌ Repository not found: {repo_path}")
        await engine.dispose()
        return

    print(f"\n📁 Repository: {repo_path}")

    # Scan for source files (skip node_modules and tests)
    print(f"\n🔍 Scanning for source files...")
    extensions = {".ts", ".tsx", ".js", ".jsx"}
    files_to_index = []

    for ext in extensions:
        found = [
            f for f in repo_path.rglob(f"*{ext}")
            if "node_modules" not in str(f)
            and "__tests__" not in str(f)
            and ".test." not in f.name
            and ".spec." not in f.name
        ]
        print(f"   - Found {len(found)} {ext} files")
        files_to_index.extend(found)

    print(f"\n📊 Total files to index: {len(files_to_index)}")

    if len(files_to_index) == 0:
        print("❌ No files found!")
        await engine.dispose()
        return

    # Services
    chunking_service = CodeChunkingService(max_workers=4)
    embedding_service = DualEmbeddingService()
    graph_service = GraphConstructionService(engine)
    chunk_repo = CodeChunkRepository(engine)

    # Step 1: Chunking
    print(f"\n1️⃣  Code Chunking...")
    start_time = datetime.now()
    all_chunks = []

    for i, file_path in enumerate(files_to_index, 1):
        try:
            content = file_path.read_text(encoding="utf-8")
            language = "typescript" if file_path.suffix in {".ts", ".tsx"} else "javascript"

            chunks = await chunking_service.chunk_code(
                source_code=content,
                file_path=str(file_path.relative_to(repo_path)),
                language=language,
                repository=repository
            )

            all_chunks.extend(chunks)

            if i % 10 == 0:
                print(f"   Processed {i}/{len(files_to_index)} files ({len(all_chunks)} chunks)")

        except Exception as e:
            print(f"   ⚠️  Failed to chunk {file_path.name}: {e}")

    print(f"   ✅ Created {len(all_chunks)} chunks in {(datetime.now() - start_time).total_seconds():.2f}s")

    # Step 2: Embeddings
    print(f"\n2️⃣  Generating Embeddings...")
    start_time = datetime.now()

    for i, chunk in enumerate(all_chunks, 1):
        try:
            # Generate dual embeddings
            text_emb = await embedding_service.generate_text_embedding(chunk.source_code)
            code_emb = await embedding_service.generate_code_embedding(chunk.source_code)

            # Store in database
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
                text_embedding=text_emb,
                code_embedding=code_emb
            )

            await chunk_repo.create_chunk(chunk_create)

            if i % 50 == 0:
                print(f"   Embedded {i}/{len(all_chunks)} chunks")

        except Exception as e:
            print(f"   ⚠️  Failed to embed chunk {i}: {e}")

    print(f"   ✅ Generated embeddings in {(datetime.now() - start_time).total_seconds():.2f}s")

    # Step 3: Graph Construction
    print(f"\n3️⃣  Building Graph (with EPIC-30 anonymous filtering)...")
    start_time = datetime.now()

    stats = await graph_service.build_graph_for_repository(repository=repository)

    print(f"   ✅ Graph built in {stats.construction_time_seconds:.2f}s")

    # Final Summary
    print(f"\n" + "=" * 80)
    print("✅ INDEXING COMPLETE!")
    print("=" * 80)
    print(f"📊 Statistics:")
    print(f"   - Files processed: {len(files_to_index)}")
    print(f"   - Chunks created: {len(all_chunks)}")
    print(f"   - Nodes in graph: {stats.total_nodes}")
    print(f"   - Edges in graph: {stats.total_edges}")

    if stats.total_nodes > 0:
        edge_ratio = (stats.total_edges / stats.total_nodes) * 100
        print(f"   - Edge ratio: {edge_ratio:.1f}%")

    # Node breakdown
    if stats.nodes_by_type:
        print(f"\n📋 Nodes by type:")
        for node_type, count in sorted(stats.nodes_by_type.items(), key=lambda x: -x[1])[:5]:
            print(f"   - {node_type}: {count}")

    print(f"\n🎨 View graph at: http://localhost:3002/")
    print(f"   Select repository: code_test")
    print("=" * 80)

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
