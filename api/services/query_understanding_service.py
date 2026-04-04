"""
Query Understanding Service — Deterministic keyword extraction.

Extracts HL/LL keywords from search queries using simple heuristics
instead of LLMs. Zero latency, zero hallucinations.
"""
import re
from dataclasses import dataclass
from typing import List

import structlog

logger = structlog.get_logger(__name__)

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "because", "but", "and", "or", "if", "while", "about", "what", "which",
    "who", "whom", "this", "that", "these", "those", "i", "me", "my",
    "myself", "we", "our", "ours", "ourselves", "you", "your", "yours",
    "yourself", "yourselves", "he", "him", "his", "himself", "she", "her",
    "hers", "herself", "it", "its", "itself", "they", "them", "their",
    "theirs", "themselves",
}


@dataclass
class QueryKeywords:
    """Extracted keywords from query understanding."""
    hl_keywords: List[str]
    ll_keywords: List[str]


class QueryUnderstandingService:
    """
    Extracts HL/LL keywords from search queries using deterministic heuristics.

    HL keywords: Most frequent content words (concepts/themes)
    LL keywords: Named entities (acronyms, versions, proper nouns)
    """

    def extract_keywords(self, query: str) -> QueryKeywords:
        """
        Extract high-level and low-level keywords from a query.

        Args:
            query: User search query

        Returns:
            QueryKeywords with hl_keywords and ll_keywords.
        """
        words = re.findall(r'\b[a-zA-Z]{3,}\b', query.lower())
        hl_keywords = list(dict.fromkeys(w for w in words if w not in STOPWORDS))[:4]

        ll_keywords = []
        
        acronyms = re.findall(r'\b[A-Z]{2,}\b', query)
        ll_keywords.extend(acronyms)
        
        versions = re.findall(r'\b(?:v?\d+\.\d+(?:\.\d+)?)\b', query)
        ll_keywords.extend(versions)
        
        proper = re.findall(r'\b[A-Z][a-z]{2,}\b', query)
        common_words = {"the", "a", "an", "is", "are", "was", "what", "how", "when", "where", "why", "who", "which", "this", "that", "these", "those", "some", "any", "all", "each", "every", "both", "few", "more", "most", "other", "such", "only", "own", "same", "very", "just", "also", "then", "than", "too", "can", "will", "would", "should", "could", "may", "might", "must", "shall", "need", "do", "does", "did", "has", "have", "had", "but", "and", "or", "if", "so", "yet", "for", "nor", "not"}
        ll_keywords.extend(p for p in proper if p.lower() not in common_words)

        ll_keywords = list(dict.fromkeys(ll_keywords))[:5]

        logger.debug(
            "query_keywords_extracted",
            query=query[:50],
            hl_count=len(hl_keywords),
            ll_count=len(ll_keywords),
        )

        return QueryKeywords(hl_keywords=hl_keywords, ll_keywords=ll_keywords)
