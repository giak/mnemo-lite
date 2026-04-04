"""
Entity Extraction Service — Deterministic extraction of entities, concepts, and tags.

Uses GLiNER (Generalist and Lightweight Model for NER) to extract structured 
metadata from memories with zero hallucinations.

Usage:
    service = EntityExtractionService(gliner_service)
    await service.extract_entities(memory_id, title, content, memory_type, tags)
"""

import os
import json
from typing import List, Dict, Any

import structlog
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import text

from services.gliner_service import GLiNERService

logger = structlog.get_logger(__name__)

# Memory types that should be extracted
EXTRACTABLE_TYPES = {"decision", "reference", "note", "investigation"}
# System tags that trigger extraction regardless of type
EXTRACTABLE_SYSTEM_TAGS = {"sys:core", "sys:anchor", "sys:pattern"}


class EntityExtractionService:
    """
    Extracts entities, concepts, and tags from memories via GLiNER.

    Extraction is async and non-blocking. If GLiNER is unavailable,
    extraction is silently skipped.
    """

    def __init__(self, engine: AsyncEngine, gliner_service: GLiNERService):
        self.engine = engine
        self.gliner_service = gliner_service
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

        text = f"{title}\n\n{content}"
        entities = self.gliner_service.extract_entities(text)

        if not entities:
            logger.debug("entity_extraction_no_results", memory_id=memory_id)
            return False

        mapped_entities = [{"name": e["name"], "type": e["type"]} for e in entities]
        concepts = [e["name"] for e in entities if e["type"] == "concept"]
        auto_tags = list(set(e["name"].lower().replace(" ", "-") for e in entities))

        saved = await self._save_to_db(memory_id, mapped_entities, concepts, auto_tags)
        if not saved:
            logger.warning("entity_extraction_save_failed", memory_id=memory_id)
            return False

        logger.info(
            "entities_extracted",
            memory_id=memory_id,
            entity_count=len(mapped_entities),
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
        """Save extracted entities to the database."""
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
