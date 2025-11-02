#!/usr/bin/env python3
"""Rebuild graph for a repository with EPIC-30 anonymous filtering."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "api"))

async def main():
    import os
    from sqlalchemy.ext.asyncio import create_async_engine
    from services.graph_construction_service import GraphConstructionService

    repository = sys.argv[1] if len(sys.argv) > 1 else "epic18-stress-test"

    print(f"=" * 80)
    print(f"🔄 Rebuilding graph for: {repository}")
    print(f"   with EPIC-30 anonymous filtering enabled")
    print(f"=" * 80)

    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://mnemo:mnemo@localhost:5432/mnemolite")
    engine = create_async_engine(db_url, echo=False)

    graph_service = GraphConstructionService(engine)

    print(f"\n⚙️  Building graph...")
    stats = await graph_service.build_graph_for_repository(repository=repository)

    print(f"\n" + "=" * 80)
    print("✅ GRAPH CONSTRUCTION COMPLETE!")
    print("=" * 80)
    print(f"📊 Statistics:")
    print(f"   - Nodes created: {stats.total_nodes}")
    print(f"   - Edges created: {stats.total_edges}")

    if stats.total_nodes > 0:
        edge_ratio = (stats.total_edges / stats.total_nodes) * 100
        print(f"   - Edge ratio: {edge_ratio:.1f}%")

    print(f"   - Construction time: {stats.construction_time_seconds:.2f}s")

    # Show node type breakdown
    print(f"\n📋 Nodes by type:")
    for node_type, count in sorted(stats.nodes_by_type.items(), key=lambda x: -x[1]):
        print(f"   - {node_type}: {count}")

    # Show edge type breakdown
    if stats.edges_by_type:
        print(f"\n🔗 Edges by type:")
        for edge_type, count in sorted(stats.edges_by_type.items(), key=lambda x: -x[1]):
            print(f"   - {edge_type}: {count}")

    print(f"\n🎨 View graph at: http://localhost:3002/")
    print("=" * 80)

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
