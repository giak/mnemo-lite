"""
Consolidation Suggestion Service — TF-IDF based memory grouping.

Finds groups of similar memories based on shared entities and concepts.
Uses TF-IDF weighting so rare entities contribute more to similarity.
Results are cached in Redis for 5 minutes.

Usage:
    service = ConsolidationSuggestionService(engine, redis_client)
    groups = await service.suggest_consolidation(
        min_shared_entities=2,
        memory_types=["note"],
        tags=["sys:history"],
        max_age_days=30,
    )
"""

import math
import json
import time
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import text

logger = structlog.get_logger(__name__)


@dataclass
class ConsolidationGroup:
    """A group of memories suggested for consolidation."""
    memory_ids: List[str] = field(default_factory=list)
    titles: List[str] = field(default_factory=list)
    content_previews: List[str] = field(default_factory=list)
    shared_entities: Set[str] = field(default_factory=set)
    shared_concepts: Set[str] = field(default_factory=set)
    avg_similarity: float = 0.0


class ConsolidationSuggestionService:
    """
    Suggests memory consolidation groups based on entity/concept overlap.
    
    Uses TF-IDF weighting for entity importance and greedy clustering
    with strict intersection to ensure group coherence.
    """

    def __init__(self, engine: AsyncEngine, redis_client=None):
        self.engine = engine
        self.redis = redis_client

    async def suggest_consolidation(
        self,
        min_shared_entities: int = 2,
        min_shared_concepts: int = 1,
        memory_types: List[str] = None,
        tags: List[str] = None,
        max_age_days: int = 30,
        min_group_size: int = 3,
        max_groups: int = 5,
        similarity_threshold: float = 0.3,
    ) -> List[ConsolidationGroup]:
        """
        Find groups of similar memories that could be consolidated.
        
        Args:
            min_shared_entities: Minimum shared entities to consider similar
            min_shared_concepts: Minimum shared concepts to consider similar
            memory_types: Filter by memory type enum values
            tags: Filter by tag patterns (e.g., "sys:history")
            max_age_days: Only consider memories created in the last N days
            min_group_size: Minimum memories per group
            max_groups: Maximum groups to return
            similarity_threshold: Minimum similarity score to include
            
        Returns:
            List of ConsolidationGroup objects
        """
        memory_types = memory_types or ["note"]
        tags = tags or ["sys:history"]
        
        # Fetch candidate memories
        memories = await self._fetch_candidate_memories(
            memory_types, tags, max_age_days
        )
        
        if len(memories) < min_group_size:
            return []
        
        # Get entity frequencies (cached)
        entity_freq = await self._get_entity_frequencies()
        total_memories = len(memories)
        
        # Build inverted index for efficient pair finding
        pairs = await self._find_similar_pairs(
            memories, entity_freq, total_memories,
            min_shared_entities, min_shared_concepts,
            similarity_threshold
        )
        
        if not pairs:
            return []
        
        # Cluster into groups
        groups = self._cluster_groups(pairs, min_group_size)
        
        # Deduplicate overlapping groups
        groups = self._deduplicate_groups(groups, overlap_threshold=0.5)
        
        # Enrich with titles, previews, suggestions
        groups = await self._enrich_groups(groups, memories)
        
        # Sort by similarity and limit
        groups.sort(key=lambda g: -g.avg_similarity)
        return groups[:max_groups]

    async def _fetch_candidate_memories(
        self,
        memory_types: List[str],
        tags: List[str],
        max_age_days: int,
    ) -> List[Dict[str, Any]]:
        """Fetch memories matching the filter criteria."""
        cutoff = datetime.utcnow() - timedelta(days=max_age_days)
        
        query = text("""
            SELECT id::text, title, LEFT(content, 200) as content_preview,
                   entities, concepts, tags, created_at
            FROM memories
            WHERE deleted_at IS NULL
              AND created_at >= :cutoff
              AND (
                memory_type = ANY(:types)
                OR tags && :tags
              )
            ORDER BY created_at DESC
        """)
        
        try:
            async with self.engine.begin() as conn:
                result = await conn.execute(query, {
                    "cutoff": cutoff,
                    "types": memory_types,
                    "tags": tags,
                })
                rows = result.fetchall()
            
            memories = []
            for row in rows:
                memories.append({
                    "id": row[0],
                    "title": row[1],
                    "content_preview": row[2] or "",
                    "entities": row[3] or [],
                    "concepts": row[4] or [],
                    "tags": row[5] or [],
                    "created_at": row[6],
                })
            return memories
            
        except Exception as e:
            logger.error("fetch_candidate_error", error=str(e))
            return []

    async def _get_entity_frequencies(self) -> Dict[str, int]:
        """Get document frequency for each entity (cached in Redis)."""
        if self.redis:
            try:
                cached = await self.redis.get("entity_freq")
                if cached:
                    return json.loads(cached)
            except Exception as e:
                logger.debug("entity_freq_cache_error", error=str(e))
        
        freq = await self._compute_entity_frequencies()
        
        if self.redis:
            try:
                await self.redis.setex("entity_freq", 300, json.dumps(freq))
            except Exception as e:
                logger.debug("entity_freq_cache_set_error", error=str(e))
        
        return freq

    async def _compute_entity_frequencies(self) -> Dict[str, int]:
        """Compute entity frequencies from the database."""
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
            logger.error("entity_freq_compute_error", error=str(e))
            return {}

    async def _find_similar_pairs(
        self,
        memories: List[Dict[str, Any]],
        entity_freq: Dict[str, int],
        total_memories: int,
        min_shared_entities: int,
        min_shared_concepts: int,
        similarity_threshold: float,
    ) -> List[Tuple[str, str, float, Set[str], Set[str]]]:
        """Find pairs of similar memories using inverted index."""
        # Build inverted index: entity_name -> [memory_ids]
        inverted_index: Dict[str, List[str]] = {}
        for mem in memories:
            for e in mem["entities"]:
                if isinstance(e, dict):
                    name = e.get("name", "").lower()
                    if name:
                        inverted_index.setdefault(name, []).append(mem["id"])
        
        # Find pairs that share >= min_shared_entities
        seen_pairs = set()
        pairs = []
        
        for entity_name, mem_ids in inverted_index.items():
            for i in range(len(mem_ids)):
                for j in range(i + 1, len(mem_ids)):
                    pair_key = tuple(sorted([mem_ids[i], mem_ids[j]]))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)
        
        # Compute similarity for each candidate pair
        mem_by_id = {m["id"]: m for m in memories}
        
        for pair_key in seen_pairs:
            mem_a = mem_by_id.get(pair_key[0])
            mem_b = mem_by_id.get(pair_key[1])
            if not mem_a or not mem_b:
                continue
            
            score, shared_e, shared_c = self._compute_similarity(
                mem_a, mem_b, entity_freq, total_memories
            )
            
            if (score >= similarity_threshold and
                len(shared_e) >= min_shared_entities and
                len(shared_c) >= min_shared_concepts):
                pairs.append((pair_key[0], pair_key[1], score, shared_e, shared_c))
        
        return pairs

    def _compute_similarity(
        self,
        mem_a: Dict[str, Any],
        mem_b: Dict[str, Any],
        entity_freq: Dict[str, int],
        total_memories: int,
    ) -> Tuple[float, Set[str], Set[str]]:
        """Compute TF-IDF weighted similarity between two memories."""
        a_entities = {e.get("name", "").lower() for e in mem_a["entities"] if isinstance(e, dict)}
        b_entities = {e.get("name", "").lower() for e in mem_b["entities"] if isinstance(e, dict)}
        shared_e = a_entities & b_entities
        
        if not shared_e:
            return 0.0, set(), set()
        
        # TF-IDF entity similarity
        tfidf_shared = sum(
            math.log(max(1, total_memories) / max(1, entity_freq.get(e, 1)))
            for e in shared_e
        )
        tfidf_union = sum(
            math.log(max(1, total_memories) / max(1, entity_freq.get(e, 1)))
            for e in a_entities | b_entities
        )
        entity_sim = tfidf_shared / max(1, tfidf_union)
        
        # Concept similarity
        a_concepts = set(c.lower() for c in mem_a["concepts"])
        b_concepts = set(c.lower() for c in mem_b["concepts"])
        shared_c = a_concepts & b_concepts
        concept_sim = len(shared_c) / max(1, len(a_concepts | b_concepts))
        
        # Composite score
        score = 0.6 * entity_sim + 0.4 * concept_sim
        return score, shared_e, shared_c

    def _cluster_groups(
        self,
        pairs: List[Tuple[str, str, float, Set[str], Set[str]]],
        min_group_size: int,
    ) -> List[Dict[str, Any]]:
        """Build groups from sorted pairs with strict intersection."""
        assigned = {}
        groups = []
        
        for mem_a, mem_b, score, shared_e, shared_c in sorted(pairs, key=lambda x: -x[2]):
            ga = assigned.get(mem_a)
            gb = assigned.get(mem_b)
            
            if ga is not None and gb is not None:
                if ga != gb:
                    # Check strict intersection
                    new_shared_e = groups[ga]["shared_entities"] & groups[gb]["shared_entities"]
                    new_shared_c = groups[ga]["shared_concepts"] & groups[gb]["shared_concepts"]
                    if not new_shared_e and not new_shared_c:
                        continue  # Don't merge — no common entities/concepts
                    groups[ga]["memory_ids"].extend(groups[gb]["memory_ids"])
                    groups[ga]["shared_entities"] = new_shared_e
                    groups[ga]["shared_concepts"] = new_shared_c
                    groups[ga]["avg_score"] = min(groups[ga]["avg_score"], score)
                    for mid in groups[gb]["memory_ids"]:
                        assigned[mid] = ga
                    groups[gb] = None
            elif ga is not None:
                groups[ga]["memory_ids"].append(mem_b)
                groups[ga]["shared_entities"] &= shared_e
                groups[ga]["shared_concepts"] &= shared_c
                groups[ga]["avg_score"] = min(groups[ga]["avg_score"], score)
                assigned[mem_b] = ga
            elif gb is not None:
                groups[gb]["memory_ids"].append(mem_a)
                groups[gb]["shared_entities"] &= shared_e
                groups[gb]["shared_concepts"] &= shared_c
                groups[gb]["avg_score"] = min(groups[gb]["avg_score"], score)
                assigned[mem_a] = gb
            else:
                idx = len(groups)
                groups.append({
                    "memory_ids": [mem_a, mem_b],
                    "shared_entities": set(shared_e),
                    "shared_concepts": set(shared_c),
                    "avg_score": score,
                })
                assigned[mem_a] = idx
                assigned[mem_b] = idx
        
        # Filter by min size
        return [g for g in groups if g and len(g["memory_ids"]) >= min_group_size]

    def _deduplicate_groups(
        self,
        groups: List[Dict[str, Any]],
        overlap_threshold: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """Remove groups that overlap too much with higher-score groups."""
        groups.sort(key=lambda g: -g["avg_score"])
        result = []
        for g in groups:
            if not result:
                result.append(g)
                continue
            overlap = max(
                len(set(g["memory_ids"]) & set(r["memory_ids"])) / max(1, len(g["memory_ids"]))
                for r in result
            )
            if overlap < overlap_threshold:
                result.append(g)
        return result

    async def _enrich_groups(
        self,
        groups: List[Dict[str, Any]],
        memories: List[Dict[str, Any]],
    ) -> List[ConsolidationGroup]:
        """Enrich groups with titles, previews, and suggestions."""
        mem_by_id = {m["id"]: m for m in memories}
        result = []
        
        for g in groups:
            titles = []
            previews = []
            for mid in g["memory_ids"]:
                mem = mem_by_id.get(mid)
                if mem:
                    titles.append(mem["title"])
                    previews.append(mem["content_preview"])
            
            result.append(ConsolidationGroup(
                memory_ids=g["memory_ids"],
                titles=titles,
                content_previews=previews,
                shared_entities=g["shared_entities"],
                shared_concepts=g["shared_concepts"],
                avg_similarity=g["avg_score"],
            ))
        
        return result

    @staticmethod
    def suggest_title(group: ConsolidationGroup) -> str:
        """Generate a suggested title for the consolidated memory."""
        entity = max(group.shared_entities, key=len) if group.shared_entities else ""
        concept = max(group.shared_concepts, key=len) if group.shared_concepts else ""
        if entity and concept:
            return f"{entity.title()} {concept}"
        elif entity:
            return f"{entity.title()} configuration"
        elif group.titles:
            return f"{group.titles[0]} (consolidated)"
        return "Consolidated memories"

    @staticmethod
    def suggest_hint(group: ConsolidationGroup) -> str:
        """Generate a contextual summary hint."""
        entities = ", ".join(list(group.shared_entities)[:3])
        concepts = ", ".join(list(group.shared_concepts)[:3])
        n = len(group.memory_ids)
        return f"{n} memories about {entities}: {concepts}"
