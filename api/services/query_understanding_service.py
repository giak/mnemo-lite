"""
Query Understanding Service — Extracts HL/LL keywords from search queries.

Uses LM Studio to decompose queries into high-level concepts and low-level
entities for improved hybrid search.

Usage:
    service = QueryUnderstandingService(lm_client)
    keywords = await service.extract_keywords("how do we handle memory consolidation?")
    # keywords.hl_keywords = ["memory consolidation", "lifecycle management"]
    # keywords.ll_keywords = ["sys:history", "consolidate_memory", "configure_decay"]
"""

import os
from dataclasses import dataclass
from typing import List

import structlog

from services.lm_studio_client import LMStudioClient

logger = structlog.get_logger(__name__)

QUERY_UNDERSTANDING_SCHEMA = {
    "type": "object",
    "properties": {
        "hl_keywords": {
            "type": "array",
            "items": {"type": "string"},
            "description": "High-level concepts and themes (abstract)"
        },
        "ll_keywords": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Low-level entities and specifics (concrete)"
        }
    },
    "required": ["hl_keywords", "ll_keywords"]
}

QUERY_UNDERSTANDING_SYSTEM_PROMPT = """You are a query understanding assistant.

Analyze the user's search query and extract:
- hl_keywords: High-level concepts and themes (abstract, 2-4 items)
- ll_keywords: Low-level entities and specifics (concrete, 2-5 items)

HL keywords should capture the intent and themes.
LL keywords should capture specific names, technologies, files, or tags.

Return ONLY valid JSON."""


@dataclass
class QueryKeywords:
    """Extracted keywords from query understanding."""
    hl_keywords: List[str]
    ll_keywords: List[str]


class QueryUnderstandingService:
    """
    Extracts HL/LL keywords from search queries via LM Studio.

    Falls back to empty keywords (query brute) if LM Studio is unavailable.
    """

    def __init__(self, lm_client: LMStudioClient):
        self.lm_client = lm_client
        self.enabled = os.getenv("QUERY_UNDERSTANDING_ENABLED", "true").lower() == "true"
        logger.info("QueryUnderstandingService initialized", enabled=self.enabled)

    async def extract_keywords(self, query: str) -> QueryKeywords:
        """
        Extract high-level and low-level keywords from a query.

        Args:
            query: User search query

        Returns:
            QueryKeywords with hl_keywords and ll_keywords.
            Returns empty lists if extraction fails (fallback).
        """
        if not self.enabled:
            logger.debug("query_understanding_disabled")
            return QueryKeywords(hl_keywords=[], ll_keywords=[])

        if not await self.lm_client.is_available():
            logger.debug("query_understanding_skipped_lm_unavailable")
            return QueryKeywords(hl_keywords=[], ll_keywords=[])

        result = await self.lm_client.extract_json(
            system_prompt=QUERY_UNDERSTANDING_SYSTEM_PROMPT,
            user_content=f"Query: {query}",
            json_schema=QUERY_UNDERSTANDING_SCHEMA,
            temperature=0.1,
        )

        if result is None:
            logger.warning("query_understanding_failed", query=query[:50])
            return QueryKeywords(hl_keywords=[], ll_keywords=[])

        hl = result.get("hl_keywords", [])
        ll = result.get("ll_keywords", [])

        # Ensure lists contain only strings
        hl = [str(k) for k in hl if isinstance(k, str) and k.strip()]
        ll = [str(k) for k in ll if isinstance(k, str) and k.strip()]

        logger.debug(
            "query_keywords_extracted",
            query=query[:50],
            hl_count=len(hl),
            ll_count=len(ll),
        )

        return QueryKeywords(hl_keywords=hl, ll_keywords=ll)
