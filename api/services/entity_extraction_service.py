"""
Entity Extraction Service — Async extraction of entities, concepts, and tags.

Uses LM Studio (Qwen2.5-7B) to extract structured metadata from memories.
Runs asynchronously — does not block memory creation.

Usage:
    service = EntityExtractionService(lm_client)
    await service.extract_entities(memory_id, title, content, memory_type, tags)
"""

import os
import json
from typing import List, Dict, Any

import structlog
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import text

from services.lm_studio_client import LMStudioClient

logger = structlog.get_logger(__name__)

# Memory types that should be extracted
EXTRACTABLE_TYPES = {"decision", "reference", "note", "investigation"}
# System tags that trigger extraction regardless of type
EXTRACTABLE_SYSTEM_TAGS = {"sys:core", "sys:anchor", "sys:pattern"}

ENTITY_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string", "enum": ["technology", "product", "file", "person", "organization", "concept", "other"]}
                },
                "required": ["name", "type"]
            }
        },
        "concepts": {
            "type": "array",
            "items": {"type": "string"}
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["entities", "concepts", "tags"]
}

ENTITY_EXTRACTION_SYSTEM_PROMPT = """You are an entity and concept extraction specialist.

Extract named entities, abstract concepts, and suggested tags from the text.

Rules:
- Only extract what is EXPLICITLY mentioned or clearly implied
- Do not invent or infer entities not present
- Normalize names (lowercase for tags, proper case for entities)
- Entities are concrete: technologies, products, files, people, organizations
- Concepts are abstract: patterns, decisions, architectural choices
- Tags should be short, lowercase, hyphenated (e.g., "cache-layer", "redis")
- Return ONLY valid JSON, no explanation"""


class EntityExtractionService:
    """
    Extracts entities, concepts, and tags from memories via LM Studio.

    Extraction is async and non-blocking. If LM Studio is unavailable,
    extraction is silently skipped.
    """

    def __init__(self, engine: AsyncEngine, lm_client: LMStudioClient):
        self.engine = engine
        self.lm_client = lm_client
        self.enabled = os.getenv("ENTITY_EXTRACTION_ENABLED", "true").lower() == "true"
        logger.info("EntityExtractionService initialized", enabled=self.enabled)

    @staticmethod
    def should_extract(memory_type: str, tags: List[str]) -> bool:
        """Determine if a memory should have entities extracted."""
        if memory_type in EXTRACTABLE_TYPES:
            return True
        if any(tag in EXTRACTABLE_SYSTEM_TAGS for tag in tags):
            return True
        return False

    async def extract_entities(
        self,
        memory_id: str,
        title: str,
        content: str,
        memory_type: str,
        tags: List[str],
    ) -> bool:
        """
        Extract entities, concepts, and tags for a memory.

        Args:
            memory_id: Memory UUID
            title: Memory title
            content: Memory content
            memory_type: Memory type (note, decision, etc.)
            tags: Existing tags

        Returns:
            True if extraction succeeded, False otherwise
        """
        if not self.enabled:
            logger.debug("entity_extraction_disabled", memory_id=memory_id)
            return False

        if not self.should_extract(memory_type, tags):
            logger.debug("entity_extraction_skipped", memory_id=memory_id, memory_type=memory_type)
            return False

        if not await self.lm_client.is_available():
            logger.debug("entity_extraction_skipped_lm_unavailable", memory_id=memory_id)
            return False

        user_content = f"Title: {title}\n\nContent: {content}"

        result = await self.lm_client.extract_json(
            system_prompt=ENTITY_EXTRACTION_SYSTEM_PROMPT,
            user_content=user_content,
            json_schema=ENTITY_EXTRACTION_SCHEMA,
            temperature=0.1,
        )

        if result is None:
            logger.warning("entity_extraction_failed", memory_id=memory_id)
            return False

        entities = result.get("entities", [])
        concepts = result.get("concepts", [])
        auto_tags = result.get("tags", [])

        saved = await self._save_to_db(memory_id, entities, concepts, auto_tags)
        if not saved:
            logger.warning("entity_extraction_save_failed", memory_id=memory_id)
            return False

        logger.info(
            "entities_extracted",
            memory_id=memory_id,
            entity_count=len(entities),
            concept_count=len(concepts),
            tag_count=len(auto_tags),
        )
        return True

    async def _save_to_db(
        self,
        memory_id: str,
        entities: List[Dict[str, Any]],
        concepts: List[str],
        auto_tags: List[str],
    ) -> bool:
        """Save extracted entities to the database.

        Returns:
            True if save succeeded, False otherwise.
        """
        query = text("""
            UPDATE memories
            SET entities = :entities,
                concepts = :concepts,
                auto_tags = :auto_tags
            WHERE id = :memory_id
        """)
        params = {
            "memory_id": memory_id,
            "entities": json.dumps(entities),
            "concepts": json.dumps(concepts),
            "auto_tags": json.dumps(auto_tags),
        }
        try:
            async with self.engine.begin() as conn:
                await conn.execute(query, params)
            return True
        except Exception as e:
            logger.error("entity_extraction_db_error", memory_id=memory_id, error=str(e))
            return False
