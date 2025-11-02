#!/usr/bin/env python3
"""Re-index CVGenerator with anonymous function filtering (EPIC-30)."""

import asyncio
import sys
sys.path.insert(0, '/app')

from db.session import get_engine
from services.code_chunking_service import CodeChunkingService
from services.graph_construction_service import GraphConstructionService
from repositories.code_chunk_repository import CodeChunkRepository

async def main():
    print("🔄 Re-indexing CVGenerator with anonymous function filtering (EPIC-30)...")

    engine = await get_engine()

    # Create services
    chunking_service = CodeChunkingService(engine)
    graph_service = GraphConstructionService(engine)
    chunk_repo = CodeChunkRepository(engine)

    repository = "CVGenerator"
    path = "/app/CVGenerator"

    # Index code
    print(f"\n1️⃣ Indexing code from {path}...")
    await chunking_service.index_directory(
        directory_path=path,
        repository=repository
    )

    # Count chunks
    chunks = await chunk_repo.get_all_chunks(repository=repository)
    print(f"   ✅ Created {len(chunks)} chunks")

    # Build graph
    print(f"\n2️⃣ Building graph...")
    stats = await graph_service.build_graph_for_repository(repository=repository)

    print(f"\n✅ Re-indexing complete!")
    print(f"   - Chunks: {len(chunks)}")
    print(f"   - Nodes: {stats.total_nodes}")
    print(f"   - Edges: {stats.total_edges}")
    print(f"   - Edge ratio: {(stats.total_edges / stats.total_nodes * 100) if stats.total_nodes > 0 else 0:.1f}%")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
