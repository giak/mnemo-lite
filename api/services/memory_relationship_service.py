"""
Memory Relationship Service — TF-IDF based relationship detection.

Calculates semantic relationships between memories based on shared
entities, concepts, and tags. Uses TF-IDF weighting so rare entities
(ADR-001) contribute more than common ones (Redis).

Architecture:
    1. Inverted index: entity_name → [memory_ids]
    2. Candidate finding: O(n × avg_entities) via GIN index queries
    3. TF-IDF scoring per pair
    4. INSERT batched with ON CONFLICT DO UPDATE
"""

import math
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

import structlog
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import text

logger = structlog.get_logger(__name__)


@dataclass
class RelationshipCandidate:
    """A candidate memory to compare against."""
    id: str
    entities: List[Dict[str, Any]]
    concepts: List[str]
    tags: List[str]
    auto_tags: List[str]


@dataclass
class Relationship:
    """A calculated relationship between two memories."""
    source_id: str
    target_id: str
    score: float
    shared_entities: List[str] = field(default_factory=list)
    shared_concepts: List[str] = field(default_factory=list)
    shared_tags: List[str] = field(default_factory=list)
    relationship_types: List[str] = field(default_factory=list)


class MemoryRelationshipService:
    """
    Calculates and stores memory relationships.

    Uses TF-IDF weighting for entity importance and inverted index
    for efficient candidate finding.
    """

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def compute_relationships(
        self,
        memory_id: str,
        entities: List[str],
        concepts: List[str],
        tags: List[str],
        auto_tags: List[str],
        min_score: float = 0.1,
    ) -> List[Relationship]:
        """
        Compute relationships for a new/updated memory.

        Args:
            memory_id: The memory to find relationships for
            entities: Entity names (lowercase)
            concepts: Concept names (lowercase)
            tags: Manual tags (lowercase)
            auto_tags: Auto-generated tags (lowercase)
            min_score: Minimum score threshold for relationships

        Returns:
            List of relationships above min_score
        """
        candidates = await self._find_candidates(
            memory_id, entities, concepts, tags, auto_tags
        )

        if not candidates:
            return []

        entity_freq = await self._get_entity_frequencies()
        total_memories = await self._get_total_memory_count()

        relationships = []
        for candidate in candidates:
            rel = self._compute_tfidf_score(
                memory_id, entities, concepts, tags, auto_tags,
                candidate, entity_freq, total_memories
            )
            if rel and rel.score >= min_score:
                relationships.append(rel)

        if relationships:
            await self._store_relationships(relationships)

        return relationships

    async def _find_candidates(
        self,
        memory_id: str,
        entities: List[str],
        concepts: List[str],
        tags: List[str],
        auto_tags: List[str],
    ) -> List[RelationshipCandidate]:
        """Find candidate memories via simple queries (avoiding complex type casting)."""
        # Use a simpler approach: fetch all non-deleted memories with entities/concepts/tags
        # and filter in Python. For large datasets, this would need optimization,
        # but for typical memory counts (<10k), this is fast enough.
        query = text("""
            SELECT id, entities, concepts, tags, auto_tags
            FROM memories
            WHERE deleted_at IS NULL
              AND id != :memory_id
              AND (entities IS NOT NULL OR concepts IS NOT NULL OR tags IS NOT NULL OR auto_tags IS NOT NULL)
        """)

        params = {"memory_id": memory_id}

        try:
            async with self.engine.begin() as conn:
                result = await conn.execute(query, params)
                rows = result.fetchall()

            # Filter in Python
            src_entities = set(e.lower() for e in entities)
            src_concepts = set(c.lower() for c in concepts)
            src_tags = set(t.lower() for t in (tags or []))
            src_auto_tags = set(t.lower() for t in (auto_tags if isinstance(auto_tags, list) else []))
            src_all_tags = src_tags | src_auto_tags

            candidates = []
            for row in rows:
                row_entities = {e.get("name", "").lower() for e in (row[1] or []) if isinstance(e, dict)}
                row_concepts = set()
                if row[2]:
                    if isinstance(row[2], list):
                        row_concepts = set(c.lower() for c in row[2])
                    elif isinstance(row[2], str):
                        try:
                            row_concepts = set(c.lower() for c in json.loads(row[2]))
                        except json.JSONDecodeError:
                            pass
                
                row_tags = set(t.lower() for t in (row[3] or []))
                row_auto_tags = set()
                if row[4]:
                    if isinstance(row[4], list):
                        row_auto_tags = set(t.lower() for t in row[4])
                    elif isinstance(row[4], str):
                        try:
                            row_auto_tags = set(t.lower() for t in json.loads(row[4]))
                        except json.JSONDecodeError:
                            pass
                row_all_tags = row_tags | row_auto_tags

                # Check for overlap
                if (src_entities & row_entities) or (src_concepts & row_concepts) or (src_all_tags & row_all_tags):
                    candidates.append(RelationshipCandidate(
                        id=str(row[0]),
                        entities=row[1] or [],
                        concepts=row[2] if isinstance(row[2], list) else [],
                        tags=row[3] or [],
                        auto_tags=row[4] if isinstance(row[4], list) else [],
                    ))

            return candidates

        except Exception as e:
            logger.error("candidate_find_error", error=str(e))
            return []

    async def _get_entity_frequencies(self) -> Dict[str, int]:
        """Get document frequency for each entity."""
        query = text("""
            SELECT e->>'name' as entity_name, COUNT(*) as freq
            FROM memories, jsonb_array_elements(entities) as e
            WHERE deleted_at IS NULL
              AND entities != '[]'::jsonb
            GROUP BY e->>'name'
        """)

        try:
            async with self.engine.begin() as conn:
                result = await conn.execute(query)
                return {row[0]: row[1] for row in result}
        except Exception as e:
            logger.error("entity_freq_error", error=str(e))
            return {}

    async def _get_total_memory_count(self) -> int:
        """Get total number of non-deleted memories."""
        query = text("SELECT COUNT(*) FROM memories WHERE deleted_at IS NULL")
        try:
            async with self.engine.begin() as conn:
                result = await conn.execute(query)
                return result.scalar() or 0
        except Exception as e:
            logger.error("total_count_error", error=str(e))
            return 0

    def _compute_tfidf_score(
        self,
        source_id: str,
        source_entities: List[str],
        source_concepts: List[str],
        source_tags: List[str],
        source_auto_tags: List[str],
        candidate: RelationshipCandidate,
        entity_freq: Dict[str, int],
        total_memories: int,
    ) -> Optional[Relationship]:
        """Compute TF-IDF score between source and candidate."""
        cand_entities = {e.get("name", "").lower() for e in candidate.entities if isinstance(e, dict)}
        cand_concepts = set(c.lower() for c in candidate.concepts)
        cand_tags = set(t.lower() for t in (candidate.tags or []))
        cand_auto_tags = set(t.lower() for t in (candidate.auto_tags or []))

        src_entities = set(e.lower() for e in source_entities)
        src_concepts = set(c.lower() for c in source_concepts)
        src_tags = set(t.lower() for t in source_tags)
        src_auto_tags = set(t.lower() for t in source_auto_tags)

        shared_e = src_entities & cand_entities
        tfidf_score = 0.0
        for e in shared_e:
            idf = math.log(max(1, total_memories) / max(1, entity_freq.get(e, 1)))
            tfidf_score += idf

        shared_c = src_concepts & cand_concepts
        shared_t = (src_tags | src_auto_tags) & (cand_tags | cand_auto_tags)

        if not shared_e and not shared_c and not shared_t:
            return None

        union_e = len(src_entities | cand_entities)
        union_c = len(src_concepts | cand_concepts)
        union_t = len((src_tags | src_auto_tags) | (cand_tags | cand_auto_tags))

        entity_component = tfidf_score / max(1, union_e) if shared_e else 0
        concept_component = len(shared_c) / max(1, union_c) if shared_c else 0
        tag_component = len(shared_t) / max(1, union_t) if shared_t else 0

        raw_score = 0.5 * entity_component + 0.3 * concept_component + 0.2 * tag_component
        score = min(1.0, raw_score)

        rel_types = []
        if shared_e:
            rel_types.append("shared_entity")
        if shared_c:
            rel_types.append("shared_concept")
        if shared_t:
            rel_types.append("shared_tag")

        return Relationship(
            source_id=source_id,
            target_id=candidate.id,
            score=score,
            shared_entities=list(shared_e),
            shared_concepts=list(shared_c),
            shared_tags=list(shared_t),
            relationship_types=rel_types,
        )

    async def _store_relationships(self, relationships: List[Relationship]) -> None:
        """Store relationships with ON CONFLICT DO UPDATE."""
        if not relationships:
            return

        query = text("""
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
        """)

        try:
            async with self.engine.begin() as conn:
                await conn.execute(query, [
                    {
                        "source_id": r.source_id,
                        "target_id": r.target_id,
                        "score": r.score,
                        "shared_entities": json.dumps(r.shared_entities),
                        "shared_concepts": json.dumps(r.shared_concepts),
                        "shared_tags": json.dumps(r.shared_tags),
                        "relationship_types": r.relationship_types,
                    }
                    for r in relationships
                ])

            logger.info(
                "relationships_stored",
                count=len(relationships),
                source_id=relationships[0].source_id if relationships else None,
            )
        except Exception as e:
            logger.error("relationship_store_error", error=str(e))

    async def get_related_memories(
        self,
        memory_id: str,
        max_depth: int = 1,
        min_score: float = 0.1,
    ) -> List[Dict[str, Any]]:
        """
        Get related memories via BFS traversal.

        Args:
            memory_id: Starting memory
            max_depth: Maximum BFS depth
            min_score: Minimum relationship score

        Returns:
            List of related memories with path info
        """
        visited = set()
        queue = [(memory_id, 0, [])]
        results = []

        while queue:
            current_id, depth, path = queue.pop(0)

            if current_id in visited or depth > max_depth:
                continue

            visited.add(current_id)

            if depth > 0:
                results.append({
                    "memory_id": current_id,
                    "depth": depth,
                    "path": path,
                })

            query = text("""
                SELECT target_id, score, shared_entities, shared_concepts, shared_tags
                FROM memory_relationships
                WHERE source_id = :source_id AND score >= :min_score
                ORDER BY score DESC
            """)

            try:
                async with self.engine.begin() as conn:
                    result = await conn.execute(query, {"source_id": current_id, "min_score": min_score})
                    for row in result:
                        if row[0] not in visited:
                            queue.append((
                                str(row[0]),
                                depth + 1,
                                path + [current_id],
                            ))
            except Exception as e:
                logger.error("bfs_error", error=str(e))

        return results
