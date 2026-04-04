"""
GLiNER Service — Deterministic entity extraction.

Uses GLiNER (Generalist and Lightweight Model for NER) to extract
entities from text with zero hallucinations.
"""
import os
from typing import List, Dict, Any, Optional

import structlog

logger = structlog.get_logger(__name__)

# Default entity types for extraction
DEFAULT_ENTITY_TYPES = [
    "technology", "product", "file", "person",
    "organization", "concept", "location"
]


class GLiNERService:
    """
    Service for deterministic entity extraction using GLiNER.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        entity_types: Optional[List[str]] = None,
    ):
        self.model_path = model_path or os.getenv(
            "GLINER_MODEL_PATH", "/app/models/gliner_multi-v2.1"
        )
        self.entity_types = entity_types or DEFAULT_ENTITY_TYPES
        self.model = None
        self._load_model()

    def _load_model(self) -> None:
        """Load GLiNER model from local path."""
        try:
            from gliner import GLiNER
            logger.info("loading_gliner_model", path=self.model_path)
            self.model = GLiNER.from_pretrained(self.model_path)
            logger.info("gliner_model_loaded")
        except ImportError:
            logger.error("gliner_not_installed")
            self.model = None
        except Exception as e:
            logger.warning("gliner_model_load_failed", error=str(e))
            self.model = None

    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract entities from text using GLiNER.

        Args:
            text: Input text

        Returns:
            List of entities with name, type, start, end positions.
            Returns empty list if model not loaded.
        """
        if not self.model:
            return []

        try:
            raw_entities = self.model.predict_entities(text, self.entity_types)
            return self._post_process(raw_entities, text)
        except Exception as e:
            logger.error("gliner_extraction_failed", error=str(e))
            return []

    def _post_process(
        self,
        raw_entities: List[Dict[str, Any]],
        text: str
    ) -> List[Dict[str, Any]]:
        """
        Post-process raw entities: deduplicate, clean types, validate.
        """
        seen = {}
        type_map = {
            "tech": "technology",
            "product": "technology",
            "org": "organization",
            "company": "organization",
            "per": "person",
            "loc": "location",
        }

        for e in raw_entities:
            name = e.get("text", "").strip()
            if not name or len(name) < 2:
                continue

            # Validate existence in text
            if name.lower() not in text.lower():
                continue

            key = name.lower()
            if key not in seen:
                raw_type = e.get("label", "concept").lower()
                clean_type = type_map.get(raw_type, raw_type)

                seen[key] = {
                    "name": name,
                    "type": clean_type,
                    "start": e.get("start", 0),
                    "end": e.get("end", 0),
                }

        return list(seen.values())
