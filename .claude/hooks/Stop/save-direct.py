#!/usr/bin/env python3
"""
Direct save via write_memory MCP tool with embeddings.
This script is called by the Stop hook and runs inside the Docker API container.
"""

import asyncio
import sys
import os


async def save_via_write_memory(user_msg: str, assistant_msg: str, session_id: str, project_id: str = None):
    """Save conversation using MnemoLite's write_memory tool with embeddings."""
    try:
        # Change to app directory
        os.chdir('/app')
        sys.path.insert(0, '/app')

        from mnemo_mcp.tools.memory_tools import WriteMemoryTool
        from services.embedding_service import MockEmbeddingService
        from db.repositories.memory_repository import MemoryRepository
        from sqlalchemy.ext.asyncio import create_async_engine
        from datetime import datetime

        # Create SQLAlchemy async engine (MemoryRepository requires AsyncEngine, not asyncpg pool)
        database_url = 'postgresql://mnemo:mnemopass@db:5432/mnemolite'
        sqlalchemy_url = database_url.replace("postgresql://", "postgresql+asyncpg://")

        sqlalchemy_engine = create_async_engine(
            sqlalchemy_url,
            pool_size=2,
            max_overflow=5,
            echo=False
        )

        # Initialize services
        embedding_service = MockEmbeddingService(model_name="mock", dimension=768)
        memory_repo = MemoryRepository(sqlalchemy_engine)

        # Create tool instance
        tool = WriteMemoryTool()
        tool._services = {
            'embedding_service': embedding_service,
            'memory_repository': memory_repo
        }

        # Mock context
        class MockContext:
            pass

        ctx = MockContext()

        # Build content
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        content = f"""# Conversation - {timestamp}

## 👤 User
{user_msg}

## 🤖 Claude
{assistant_msg}

---
**Session**: {session_id}
**Saved**: {timestamp}"""

        title = f"Conv: {user_msg[:60]}..." if len(user_msg) > 60 else f"Conv: {user_msg}"

        # Call write_memory (generates embeddings!)
        result = await tool.execute(
            ctx=ctx,
            title=title,
            content=content,
            memory_type="conversation",
            tags=["auto-saved", f"session:{session_id}", f"date:{session_id[:8]}"],
            author="AutoSave",
            project_id=project_id
        )

        await sqlalchemy_engine.dispose()

        print(f"✓ Saved: {result.get('id')}", file=sys.stderr)
        return {"success": True, "id": result.get("id")}

    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    # Read from args
    if len(sys.argv) < 4:
        sys.exit(0)

    user_msg = sys.argv[1]
    assistant_msg = sys.argv[2]
    session_id = sys.argv[3]
    project_id = sys.argv[4] if len(sys.argv) > 4 else None

    asyncio.run(save_via_write_memory(user_msg, assistant_msg, session_id, project_id))
