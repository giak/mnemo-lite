"""
Entity Extraction MCP Tool — Manual entity extraction and search.

Provides tools for:
- extract_entities: Re-extract entities from an existing memory
- search_by_entity: Search memories containing a specific entity
"""

from typing import Dict, Any, List
import structlog
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import text

from services.ollama_client import OllamaClient
from services.entity_extraction_service import EntityExtractionService

logger = structlog.get_logger()


class ExtractEntitiesTool:
    """MCP tool to manually trigger entity extraction on an existing memory."""

    def __init__(self, engine: AsyncEngine, ollama_client: OllamaClient):
        self.engine = engine
        self.extraction_service = EntityExtractionService(engine=engine, ollama_client=ollama_client)

    async def execute(
        self,
        memory_id: str,
    ) -> Dict[str, Any]:
        """
        Re-extract entities for a memory.

        Args:
            memory_id: Memory UUID

        Returns:
            Dict with extraction result
        """
        query = text("""
            SELECT id::text, title, content, memory_type, tags
            FROM memories WHERE id = :memory_id AND deleted_at IS NULL
        """)
        async with self.engine.begin() as conn:
            result = await conn.execute(query, {"memory_id": memory_id})
            row = result.fetchone()

        if not row:
            return {"error": f"Memory {memory_id} not found", "success": False}

        memory_id_str, title, content, memory_type, tags = row

        if isinstance(tags, str):
            tags = tags.strip("{}").split(",") if tags != "{}" else []

        success = await self.extraction_service.extract_entities(
            memory_id=memory_id_str,
            title=title,
            content=content,
            memory_type=memory_type,
            tags=tags or [],
        )

        return {
            "success": success,
            "memory_id": memory_id,
            "message": "Entities extracted" if success else "Extraction failed or skipped",
        }


class SearchByEntityTool:
    """MCP tool to search memories by entity name."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def execute(
        self,
        entity_name: str,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Search memories containing a specific entity.

        Args:
            entity_name: Entity name to search for
            limit: Max results

        Returns:
            Dict with matching memories
        """
        import json
        query = text("""
            SELECT id::text, title, memory_type, tags, created_at::text, entities
            FROM memories
            WHERE deleted_at IS NULL
              AND entities @> :entity_json::jsonb
            ORDER BY created_at DESC
            LIMIT :limit
        """)
        async with self.engine.begin() as conn:
            result = await conn.execute(query, {"entity_name": entity_name, "entity_json": json.dumps([{"name": entity_name}]), "limit": limit})
            rows = result.fetchall()

        memories = []
        for row in rows:
            memories.append({
                "id": row[0],
                "title": row[1],
                "memory_type": row[2],
                "tags": row[3],
                "created_at": row[4],
                "entities": row[5],
            })

        return {
            "query": entity_name,
            "memories": memories,
            "total": len(memories),
        }
