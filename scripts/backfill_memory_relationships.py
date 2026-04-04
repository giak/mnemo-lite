"""
Backfill Memory Relationships — One-shot script to compute initial relationships.

Usage:
    python scripts/backfill_memory_relationships.py

Environment:
    DATABASE_URL: PostgreSQL connection string
    MIN_SCORE: Minimum relationship score threshold (default: 0.1)
    CHUNK_SIZE: Number of memories to process per batch (default: 1000)
"""

import os
import sys
import asyncio
import json
import math
from typing import Dict, List, Set, Any, Tuple

import structlog
from sqlalchemy import create_engine, text

logger = structlog.get_logger()


def get_entity_frequencies(engine) -> Tuple[Dict[str, int], int]:
    """Get document frequency for each entity and total memory count."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT e->>'name' as entity_name, COUNT(*) as freq
            FROM memories, jsonb_array_elements(entities) as e
            WHERE deleted_at IS NULL
              AND entities != '[]'::jsonb
            GROUP BY e->>'name'
        """))
        entity_freq = {row[0]: row[1] for row in result}

        result = conn.execute(text("SELECT COUNT(*) FROM memories WHERE deleted_at IS NULL"))
        total = result.scalar() or 0

    return entity_freq, total


def fetch_memories_with_entities(engine, offset: int, limit: int) -> List[Dict[str, Any]]:
    """Fetch memories with their entities, concepts, tags."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id::text, entities, concepts, tags, auto_tags
            FROM memories
            WHERE deleted_at IS NULL
              AND (entities != '[]'::jsonb OR concepts != '[]' OR tags != '{}' OR auto_tags != '{}')
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """), {"limit": limit, "offset": offset})

        memories = []
        for row in result:
            memories.append({
                "id": row[0],
                "entities": row[1] or [],
                "concepts": row[2] or [],
                "tags": row[3] or [],
                "auto_tags": row[4] or [],
            })
        return memories


def compute_tfidf_score(
    source: Dict[str, Any],
    target: Dict[str, Any],
    entity_freq: Dict[str, int],
    total_memories: int,
) -> float:
    """Compute TF-IDF score between two memories."""
    src_entities = {e.get("name", "").lower() for e in source["entities"] if isinstance(e, dict)}
    tgt_entities = {e.get("name", "").lower() for e in target["entities"] if isinstance(e, dict)}
    shared_e = src_entities & tgt_entities

    if not shared_e:
        return 0.0

    tfidf_score = sum(
        math.log(max(1, total_memories) / max(1, entity_freq.get(e, 1)))
        for e in shared_e
    )

    union_e = len(src_entities | tgt_entities)
    return min(1.0, tfidf_score / max(1, union_e))


def store_relationships(engine, relationships: List[Dict[str, Any]]) -> int:
    """Batch insert relationships."""
    if not relationships:
        return 0

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO memory_relationships
                (source_id, target_id, score, shared_entities, shared_concepts, shared_tags, relationship_types)
            VALUES
                (:source_id, :target_id, :score, :shared_entities, :shared_concepts, :shared_tags, :relationship_types)
            ON CONFLICT (source_id, target_id)
            DO UPDATE SET
                score = EXCLUDED.score,
                shared_entities = EXCLUDED.shared_entities,
                shared_concepts = EXCLUDED.shared_concepts,
                shared_tags = EXCLUDED.shared_tags,
                relationship_types = EXCLUDED.relationship_types,
                created_at = NOW()
        """), relationships)

    return len(relationships)


def main():
    database_url = os.getenv("DATABASE_URL", "postgresql+psycopg2://mnemo:mnemopass@localhost:5432/mnemolite")
    min_score = float(os.getenv("MIN_SCORE", "0.1"))
    chunk_size = int(os.getenv("CHUNK_SIZE", "1000"))

    logger.info("backfill_start", database_url=database_url, min_score=min_score, chunk_size=chunk_size)

    engine = create_engine(database_url)
    entity_freq, total_memories = get_entity_frequencies(engine)

    logger.info("entity_freq_loaded", entities=len(entity_freq), total_memories=total_memories)

    # Build inverted index: entity_name → [memory_ids]
    inverted_index: Dict[str, List[int]] = {}
    all_memories: List[Dict[str, Any]] = []

    offset = 0
    while True:
        chunk = fetch_memories_with_entities(engine, offset, chunk_size)
        if not chunk:
            break

        all_memories.extend(chunk)
        for mem in chunk:
            for e in mem["entities"]:
                if isinstance(e, dict):
                    name = e.get("name", "").lower()
                    if name:
                        inverted_index.setdefault(name, []).append(len(all_memories) - 1)

        offset += chunk_size
        logger.info("backfill_progress", processed=len(all_memories))

    logger.info("backfill_index_built", memories=len(all_memories), entities=len(inverted_index))

    # Compute relationships
    total_relationships = 0
    seen_pairs = set()
    batch = []

    for i, source in enumerate(all_memories):
        # Find candidates via inverted index
        candidate_indices = set()
        for e in source["entities"]:
            if isinstance(e, dict):
                name = e.get("name", "").lower()
                if name in inverted_index:
                    candidate_indices.update(inverted_index[name])

        for j in candidate_indices:
            if j <= i:
                continue

            target = all_memories[j]
            pair_key = (source["id"], target["id"])
            if pair_key in seen_pairs:
                continue

            score = compute_tfidf_score(source, target, entity_freq, total_memories)
            if score >= min_score:
                seen_pairs.add(pair_key)

                src_entities = {e.get("name", "").lower() for e in source["entities"] if isinstance(e, dict)}
                tgt_entities = {e.get("name", "").lower() for e in target["entities"] if isinstance(e, dict)}
                shared_e = list(src_entities & tgt_entities)

                src_concepts = set(c.lower() for c in source["concepts"])
                tgt_concepts = set(c.lower() for c in target["concepts"])
                shared_c = list(src_concepts & tgt_concepts)

                src_tags = set(t.lower() for t in (source["tags"] or []))
                tgt_tags = set(t.lower() for t in (target["tags"] or []))
                shared_t = list(src_tags & tgt_tags)

                rel_types = []
                if shared_e:
                    rel_types.append("shared_entity")
                if shared_c:
                    rel_types.append("shared_concept")
                if shared_t:
                    rel_types.append("shared_tag")

                batch.append({
                    "source_id": source["id"],
                    "target_id": target["id"],
                    "score": score,
                    "shared_entities": json.dumps(shared_e),
                    "shared_concepts": json.dumps(shared_c),
                    "shared_tags": json.dumps(shared_t),
                    "relationship_types": rel_types,
                })

                if len(batch) >= 500:
                    count = store_relationships(engine, batch)
                    total_relationships += count
                    logger.info("backfill_batch_stored", count=count, total=total_relationships)
                    batch = []

    # Store remaining
    if batch:
        count = store_relationships(engine, batch)
        total_relationships += count

    logger.info("backfill_complete", total_relationships=total_relationships)
    print(f"\nBackfill complete: {total_relationships} relationships stored")


if __name__ == "__main__":
    main()
