"""
Jaccard Similarity Utilities for Memory Deduplication.

Pure Python functions with no external dependencies.
Used by MemoryRepository.find_potential_duplicates() for
two-stage duplicate detection (pg_trgm pre-filter → Jaccard confirmation).

Inspired by AgentMemory's auto-forget contradiction detection
which uses Jaccard > 0.9 threshold.
"""

import re


def tokenize(text: str) -> set:
    """Tokenize text into a set of lowercase words for Jaccard comparison.

    Splits on non-word characters (whitespace + punctuation),
    lowercases, and filters out words <= 2 chars to reduce noise
    from common short words like "is", "to", "of", etc.

    Args:
        text: Input text to tokenize

    Returns:
        Set of lowercase word tokens (each > 2 chars)
    """
    if not text:
        return set()
    words = re.split(r'[^\w]+', text.lower())
    return {w for w in words if len(w) > 2}


def jaccard_similarity(a: str, b: str) -> float:
    """
    Compute Jaccard similarity between two strings.

    J(A,B) = |A ∩ B| / |A ∪ B|

    Range: 0.0 (no overlap) to 1.0 (identical).
    Uses word-level tokenization (words > 2 chars) to avoid
    noise from common short words.

    AgentMemory uses Jaccard > 0.9 as duplicate threshold.
    MnemoLite uses the same threshold for is_duplicate flag.

    Args:
        a: First string
        b: Second string

    Returns:
        Jaccard similarity score (0.0–1.0)
    """
    set_a = tokenize(a)
    set_b = tokenize(b)
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)
