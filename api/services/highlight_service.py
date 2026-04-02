"""
Search Result Highlighting Service (EPIC-35 Story 35.1).

Finds matching query terms in text and returns highlighted snippets
with <mark> tags for frontend rendering.
"""
import re
from typing import List, Dict, Optional


def highlight_matches(
    text: str,
    query: str,
    max_snippets: int = 3,
    snippet_length: int = 150,
) -> List[Dict[str, str]]:
    """
    Find matching query terms in text and return highlighted snippets.

    Args:
        text: Full text content to search in
        query: Search query terms
        max_snippets: Maximum number of snippets to return
        snippet_length: Approximate length of each snippet

    Returns:
        List of dicts with 'before', 'match', 'after' keys for highlighting
    """
    if not text or not query:
        return []

    # Extract query tokens (alphanumeric, min 2 chars)
    tokens = [t.lower() for t in re.findall(r'[a-zA-Z0-9\u00C0-\u024F]{2,}', query)]
    if not tokens:
        return []

    text_lower = text.lower()
    matches = []

    # Find all positions where any token matches
    for token in tokens:
        start = 0
        while True:
            pos = text_lower.find(token, start)
            if pos == -1:
                break
            matches.append((pos, pos + len(token), token))
            start = pos + 1

    if not matches:
        return []

    # Sort by position
    matches.sort(key=lambda x: x[0])

    # Merge overlapping matches
    merged = [matches[0]]
    for pos, end, token in matches[1:]:
        if pos <= merged[-1][1]:
            # Overlapping, extend
            merged[-1] = (merged[-1][0], max(merged[-1][1], end), merged[-1][2])
        else:
            merged.append((pos, end, token))

    # Create snippets around each match
    snippets = []
    used_positions = set()

    for pos, end, token in merged:
        # Skip if this match is too close to an already-used one
        if any(abs(pos - up) < snippet_length for up in used_positions):
            continue

        # Calculate snippet boundaries
        snippet_start = max(0, pos - snippet_length // 3)
        snippet_end = min(len(text), end + snippet_length * 2 // 3)

        # Try to start at a word boundary
        if snippet_start > 0:
            space_pos = text.rfind(' ', snippet_start - 20, snippet_start)
            if space_pos > 0:
                snippet_start = space_pos + 1

        # Try to end at a word boundary
        if snippet_end < len(text):
            space_pos = text.find(' ', snippet_end, snippet_end + 20)
            if space_pos > 0:
                snippet_end = space_pos

        # Build highlighted snippet
        before = text[snippet_start:pos]
        match_text = text[pos:end]
        after = text[end:snippet_end]

        # Add ellipsis if truncated
        if snippet_start > 0:
            before = '...' + before
        if snippet_end < len(text):
            after = after + '...'

        snippets.append({
            'before': before,
            'match': match_text,
            'after': after,
        })
        used_positions.add(pos)

        if len(snippets) >= max_snippets:
            break

    return snippets


def highlight_text(text: str, query: str) -> str:
    """
    Return full text with query terms wrapped in <mark> tags.

    Args:
        text: Full text content
        query: Search query terms

    Returns:
        Text with <mark> tags around matching terms
    """
    if not text or not query:
        return text

    tokens = [t for t in re.findall(r'[a-zA-Z0-9\u00C0-\u024F]{2,}', query)]
    if not tokens:
        return text

    # Escape special regex chars and build pattern
    escaped = [re.escape(t) for t in tokens]
    pattern = '|'.join(escaped)
    
    return re.sub(
        f'({pattern})',
        r'<mark>\1</mark>',
        text,
        flags=re.IGNORECASE
    )
