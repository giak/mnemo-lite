# EPIC-29: Memory Relationship Graph

> **Statut:** DRAFT | **Date:** 2026-04-04 | **Auteur:** giak
> **Inspiration:** LightRAG knowledge graph, Neo4j Node Similarity, TF-IDF entity weighting

---

## 1. Problem Statement

Les mémoires dans MnemoLite sont isolées. Un agent qui trouve une mémoire pertinente ne découvre pas automatiquement les mémoires liées par des entités, concepts ou tags communs. La recherche est limitée aux résultats directs — pas de navigation contextuelle, pas de visualisation des liens sémantiques, pas de découverte multi-hop.

**Conséquences :**
- Un agent qui cherche "cache" trouve Redis mais ne découvre pas PostgreSQL (lié par "data store")
- Pas de visualisation du graphe de connaissances dans l'UI
- Les mémoires liées ne sont pas incluses dans les résultats de recherche
- Pas de consolidation basée sur la similarité entitaire

---

## 2. Solution Overview

Construire un **graphe de relations entre mémoires** basé sur les entités, concepts et tags partagés, avec :

1. **Table `memory_relationships`** — stocke les liens entre mémoires avec score TF-IDF
2. **Index inversé** — détection incrémentale O(n × avg_entities) au lieu de O(n²)
3. **Worker async** — calcule les relations après extraction d'entités
4. **3 usages** : navigation multi-hop, recherche contextuelle, visualisation UI

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    MnemoLite Backend                             │
│                                                                  │
│  write_memory()                                                  │
│       │                                                          │
│       ├─ 1. Crée la mémoire (DB)                                 │
│       ├─ 2. Push Redis Stream "entity:extraction"                │
│       │      → LM Studio extrait entities/concepts/tags          │
│       └─ 3. Push Redis Stream "memory:relationships"             │
│              │                                                   │
│              ▼                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Worker (conversation_worker.py)                        │    │
│  │  Consomme "memory:relationships" (batch=10)             │    │
│  │  ├─ Récupère entities/concepts de la nouvelle mém.     │    │
│  │  ├─ Index inversé → candidates (O(n × avg_entities))   │    │
│  │  ├─ TF-IDF scoring → weight par paire                  │    │
│  │  └─ INSERT batché → memory_relationships               │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  memory_relationships (PostgreSQL)                      │    │
│  │  source_id → target_id (score, shared_*, types)         │    │
│  │  Index GIN sur shared_entities/concepts/tags            │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Usage 1: Navigation multi-hop                                   │
│  GET /memories/{id}/related?max_depth=2 → BFS sur relations     │
│  Cache Redis TTL 5 min                                           │
│                                                                  │
│  Usage 2: Recherche contextuelle                                 │
│  search_memory() → résultats → SELECT related WHERE source_id   │
│  IN (result_ids) ORDER BY score DESC LIMIT (limit - found)      │
│                                                                  │
│  Usage 3: Visualisation UI                                       │
│  GET /api/v1/memories/graph → {nodes: [...], edges: [...]}      │
│  Cache Redis TTL 10 min, seuil score > 0.3                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Stories

### Story 29.1: Migration DB — table `memory_relationships` + index

**Objectif** : Créer la table de relations avec contraintes et index optimisés.

**Migration Alembic** :
```python
"""add memory_relationships table

Revision ID: 20260404_0000
Revises: 20260403_0000
Create Date: 2026-04-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260404_0000"
down_revision = "20260403_0000"


def upgrade() -> None:
    op.create_table(
        "memory_relationships",
        sa.Column("id", sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_id", sa.UUID, sa.ForeignKey("memories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_id", sa.UUID, sa.ForeignKey("memories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("shared_entities", postgresql.JSONB, nullable=True, server_default="[]"),
        sa.Column("shared_concepts", postgresql.JSONB, nullable=True, server_default="[]"),
        sa.Column("shared_tags", postgresql.JSONB, nullable=True, server_default="[]"),
        sa.Column("relationship_types", postgresql.ARRAY(sa.Text), nullable=True, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("source_id != target_id", name="chk_no_self_loops"),
        sa.CheckConstraint("score >= 0.0 AND score <= 1.0", name="chk_score_range"),
        sa.UniqueConstraint("source_id", "target_id", name="uq_source_target"),
    )

    # Index pour navigation (BFS)
    op.execute("CREATE INDEX idx_mem_rel_source ON memory_relationships(source_id)")
    op.execute("CREATE INDEX idx_mem_rel_target ON memory_relationships(target_id)")
    # Index pour recherche contextuelle
    op.execute("CREATE INDEX idx_mem_rel_source_score ON memory_relationships(source_id, score DESC)")
    # Index GIN pour requêtes sur le contenu partagé
    op.execute("CREATE INDEX idx_mem_rel_shared_entities ON memory_relationships USING GIN (shared_entities jsonb_path_ops)")
    op.execute("CREATE INDEX idx_mem_rel_shared_concepts ON memory_relationships USING GIN (shared_concepts jsonb_path_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_mem_rel_shared_concepts")
    op.execute("DROP INDEX IF EXISTS idx_mem_rel_shared_entities")
    op.execute("DROP INDEX IF EXISTS idx_mem_rel_source_score")
    op.execute("DROP INDEX IF EXISTS idx_mem_rel_target")
    op.execute("DROP INDEX IF EXISTS idx_mem_rel_source")
    op.drop_table("memory_relationships")
```

**Fichiers** :
- Créer : `api/alembic/versions/20260404_0000_add_memory_relationships.py`

---

### Story 29.2: MemoryRelationshipService — calcul TF-IDF et détection

**Objectif** : Service qui calcule les relations entre une nouvelle mémoire et les candidates via index inversé + TF-IDF.

**Algorithme TF-IDF** :
```python
def compute_tfidf_weight(entity_name: str, total_memories: int, entity_doc_freq: int) -> float:
    """TF-IDF weight pour une entité.
    Les entités rares (ADR-001) ont plus de poids que les communes (Redis).
    """
    idf = math.log(total_memories / max(1, entity_doc_freq))
    return idf

def compute_relationship_score(
    new_memory, candidate, entity_freq: dict, total_memories: int
) -> float:
    """Score composite TF-IDF entre deux mémoires."""
    new_entities = {e["name"].lower() for e in new_memory.entities}
    cand_entities = {e["name"].lower() for e in candidate.entities}
    shared = new_entities & cand_entities
    
    if not shared:
        return 0.0
    
    # TF-IDF score
    tfidf_score = sum(
        compute_tfidf_weight(e, total_memories, entity_freq.get(e, 1))
        for e in shared
    )
    
    # Normaliser par la taille de l'union
    union_size = len(new_entities | cand_entities)
    normalized = tfidf_score / max(1, union_size)
    
    # Clamp 0-1
    return min(1.0, normalized)
```

**Détection incrémentale via index inversé** :
```python
async def find_candidates(memory_id: str, entities: list, concepts: list, tags: list) -> list:
    """Trouver les mémoires candidates via index inversé (O(n × avg_entities))."""
    # Utiliser les index GIN pour trouver les mémoires qui partagent
    # au moins une entité, concept ou tag
    query = text("""
        SELECT id, entities, concepts, tags, auto_tags
        FROM memories
        WHERE deleted_at IS NULL
          AND id != :memory_id
          AND (
            entities @> ANY(ARRAY[:entity_jsons]::jsonb[])
            OR concepts && ARRAY[:concepts]
            OR tags && ARRAY[:tags]
            OR auto_tags && ARRAY[:tags]
          )
    """)
```

**Fichiers** :
- Créer : `api/services/memory_relationship_service.py`

---

### Story 29.3: Worker — consommation du stream `memory:relationships`

**Objectif** : Le worker existant consomme un nouveau stream et calcule les relations par batch.

**Flux** :
```
write_memory() → Redis Stream "memory:relationships"
       │
       ▼
Worker (batch=10, poll=100ms)
       │
       ├─ Récupère les 10 messages
       ├─ Pour chaque mémoire :
       │   ├─ Fetch candidates via index inversé
       │   ├─ Calcul TF-IDF pour chaque paire
       │   └─ Filtrer score < 0.1
       ├─ INSERT batché (ON CONFLICT DO UPDATE)
       └─ ACK tous les messages
```

**Fichiers** :
- Modifier : `workers/conversation_worker.py` — ajouter consommation `memory:relationships`

---

### Story 29.4: API Endpoints — `/related`, `/graph`, recherche contextuelle

**Objectif** : 3 endpoints pour les 3 usages.

**Endpoint 1 : Navigation multi-hop**
```
GET /api/v1/memories/{id}/related?max_depth=2&min_score=0.2

Response:
{
  "memory_id": "...",
  "related": [
    {
      "memory_id": "...",
      "title": "...",
      "score": 0.85,
      "shared_entities": ["Redis", "PostgreSQL"],
      "shared_concepts": ["data store"],
      "depth": 1,
      "path": ["...", "..."]  // chemin BFS
    },
    ...
  ]
}
```

**Endpoint 2 : Visualisation UI**
```
GET /api/v1/memories/graph?min_score=0.3&limit=100

Response:
{
  "nodes": [
    {"id": "...", "title": "...", "memory_type": "...", "size": 5},
    ...
  ],
  "edges": [
    {"source": "...", "target": "...", "score": 0.85, "types": ["shared_entity"]},
    ...
  ]
}
```

**Endpoint 3 : Recherche contextuelle (modifié)**
```
POST /api/v1/memories/search
→ Après recherche normale, si résultats < limit :
  SELECT related FROM memory_relationships
  WHERE source_id IN (result_ids)
  ORDER BY score DESC
  LIMIT (limit - found)
→ Merge résultats directs + liés
```

**Fichiers** :
- Créer : `api/routes/memory_relationship_routes.py`
- Modifier : `api/services/hybrid_memory_search_service.py` — inclure mémoires liées

---

### Story 29.5: Outils MCP — `get_related_memories`, `get_memory_graph`

**Objectif** : Deux nouveaux outils MCP pour les agents.

| Tool | Description |
|------|-------------|
| `get_related_memories` | Retourne les mémoires liées (BFS, max_depth configurable) |
| `get_memory_graph` | Retourne le graphe complet pour visualisation |

**Fichiers** :
- Créer : `api/mnemo_mcp/tools/relationship_tools.py`
- Modifier : `api/mnemo_mcp/server.py` — enregistrer les outils

---

### Story 29.6: Cache Redis pour les relations

**Objectif** : Cacher les résultats de navigation et graphe pour éviter les requêtes répétées.

| Clé | TTL | Contenu |
|-----|-----|---------|
| `memrel:{id}:d{depth}` | 5 min | Mémoires liées à {id} jusqu'à depth {depth} |
| `memgraph:min{score}` | 10 min | Graphe complet avec seuil {score} |

**Invalidation** : Quand une relation est créée/mise à jour → invalider les caches des deux mémoires concernées.

**Fichiers** :
- Créer : `api/services/memrel_cache_service.py`

---

### Story 29.7: Backfill — calcul initial des relations

**Objectif** : Script one-shot pour calculer les relations des mémoires existantes.

**Algorithme** :
1. Fetch toutes les mémoires avec entities/concepts/tags
2. Construire l'index inversé : entity_name → [memory_ids]
3. Pour chaque entité, créer les paires entre toutes les mémoires qui la partagent
4. Calculer TF-IDF pour chaque paire
5. Aggréger (une row par paire, score composite)
6. INSERT batché

**Optimisation** : Traiter par chunks de 1000 mémoires pour éviter OOM.

**Fichiers** :
- Créer : `scripts/backfill_memory_relationships.py`

---

### Story 29.8: Tests TDD

**Tests unitaires** :
- `test_memory_relationship_service.py` — TF-IDF scoring, candidate finding, incremental detection
- `test_memrel_cache_service.py` — cache hit/miss, invalidation
- `test_memory_relationship_worker.py` — stream consumption, batch processing

**Tests d'intégration** :
- Créer 3 mémoires avec entités partagées → vérifier relations créées
- Navigation multi-hop → vérifier BFS correct
- Recherche contextuelle → vérifier inclusion des mémoires liées

**Fichiers** :
- Créer : `tests/services/test_memory_relationship_service.py`
- Créer : `tests/services/test_memrel_cache_service.py`
- Créer : `tests/workers/test_memory_relationship_worker.py`

---

## 5. Ordre d'implémentation

1. **Story 29.1** — Migration DB
2. **Story 29.2** — MemoryRelationshipService (TF-IDF + index inversé)
3. **Story 29.6** — Cache Redis
4. **Story 29.3** — Worker consommation stream
5. **Story 29.4** — API Endpoints
6. **Story 29.5** — Outils MCP
7. **Story 29.7** — Backfill
8. **Story 29.8** — Tests

---

## 6. Matrice de dégradation

| Scénario | Comportement |
|----------|-------------|
| Table non créée | Skip silencieux, recherche normale |
| Worker down | Relations non calculées, recherche normale |
| Redis cache down | Pas de cache, requêtes DB directes |
| TF-IDF erreur | Fallback Jaccard simple |
| Backfill échoue | Retry manuel, pas de blocage |

---

## 7. Métriques de succès

| Métrique | Cible | Mesure |
|----------|-------|--------|
| Relations par mémoire (moyenne) | 2-5 | COUNT / COUNT(DISTINCT source_id) |
| Latence calcul relations (async) | < 2s | Time from stream push to INSERT |
| Latence navigation multi-hop | < 100ms | P95 GET /memories/{id}/related |
| Latence recherche contextuelle | < 150ms | P95 search with related merge |
| Précision relations (manuel) | > 80% pertinentes | Review 50 random relations |
| Cache hit rate | > 70% | Redis hits / total requests |

---

## 8. Risques et mitigations

| Risque | Probabilité | Impact | Mitigation |
|--------|------------|--------|------------|
| O(n²) au backfill | Moyenne | Élevé | Index inversé O(n × avg_entities) |
| Relations obsolètes | Faible | Moyen | Invalidation incrémentale à l'update |
| Worker bottleneck | Faible | Moyen | Batch processing + async |
| TF-IDF peu pertinent | Moyenne | Moyen | Seuil configurable, ajustable |
| Cache staleness | Faible | Faible | TTL courts (5-10 min) |

---

## 9. Dépendances

- **EPIC-28** : Entity extraction (entities, concepts, auto_tags doivent être extraits)
- **Redis** : Déjà en place pour le cache L2
- **PostgreSQL 18** : Déjà en place, GIN index natif
