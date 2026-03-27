"""
Safe SQL vector formatting for pgvector.

Provides validated formatting functions for embedding vectors
to be used in SQL queries with pgvector operators (<=>, <->).

CRITICAL SECURITY: These functions validate input types before
formatting to prevent SQL injection via corrupted embeddings.
"""

from typing import List


def format_vector_for_sql(embedding: List[float]) -> str:
    """
    Format embedding as a pgvector vector literal for safe SQL interpolation.

    Validates:
    - Input is a list/tuple
    - All elements are numeric (int/float)
    - Output is strictly [num,num,...] format

    Returns: "[0.1,0.2,...]" string for SQL cast ::vector(768)
    """
    if not isinstance(embedding, (list, tuple)):
        raise ValueError(f"Expected list/tuple, got {type(embedding).__name__}")
    if len(embedding) == 0:
        raise ValueError("Empty embedding vector")
    for i, x in enumerate(embedding):
        if not isinstance(x, (int, float)):
            raise ValueError(f"Non-numeric at index {i}: {type(x).__name__}")
    return "[" + ",".join(str(float(x)) for x in embedding) + "]"


def format_halfvec_for_sql(embedding: List[float]) -> str:
    """
    Format embedding as a pgvector halfvec literal for safe SQL interpolation.

    Same validation as format_vector_for_sql.
    Returns: "[0.1,0.2,...]" string for SQL cast ::halfvec(768)
    """
    return format_vector_for_sql(embedding)
