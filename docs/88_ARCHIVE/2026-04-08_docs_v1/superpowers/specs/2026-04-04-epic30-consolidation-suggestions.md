# EPIC-30: Entity-Based Consolidation Suggestions

> **Statut:** DRAFT | **Date:** 2026-04-04 | **Auteur:** giak
> **Inspiration:** LightRAG entity-aware consolidation, TF-IDF weighted similarity

---

## 1. Problem Statement

La consolidation mémoire actuelle est **aveugle** — l'agent voit `needs_consolidation: true` (quand >20 mémoires `sys:history`) mais ne sait PAS quelles mémoires sont similaires. Il consolide arbitrairement par date, fusionnant des sujets sans rapport.

**Conséquences :**
- L'agent doit faire N appels `read_memory` pour comprendre le contenu avant de consolider
- Les consolidations mélangent des sujets différents (ex: "Redis cache" + "PostgreSQL migration")
- Le résumé généré est générique car l'agent n'a pas de vue d'ensemble des entités partagées
- Processus inefficace — l'agent passe plus de temps à trier qu'à consolider

---

## 2. Solution Overview

Ajouter un outil MCP `suggest_consolidation` qui retourne des **groupes de mémoires similaires** basés sur le chevauchement d'entités et concepts, avec scoring TF-IDF et suggestions intelligentes.

**Principe :** Réutilise l'infrastructure EPIC-28/29 — les entités/concepts/tags déjà extraits servent maintenant à détecter les similarités sémantiques entre mémoires.

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  suggest_consolidation()                                     │
│                                                              │
│  1. Fetch mémoires (filtrées par type/tag, âge)              │
│  2. Entity frequency cache (Redis, TTL 5 min)                │
│  3. Index inversé: entity_name → [memory_ids]               │
│  4. Pour chaque paire partageant >= min_shared_entities:     │
│     - TF-IDF entity similarity (60%)                         │
│     - TF-IDF concept similarity (40%)                        │
│     - Score composite = 0.6*E + 0.4*C                       │
│  5. Clustering greedy (paires triées par score)              │
│     - Intersection stricte: si empty → ne pas fusionner      │
│  6. Déduplication: groupes qui se chevauchent >50% → skip    │
│  7. Retourner top-N groupes avec:                           │
│     - source_ids (directement utilisable)                    │
│     - titles, content_previews (LEFT 200 chars)              │
│     - shared_entities, shared_concepts                       │
│     - suggested_title, suggested_tags                        │
│     - suggested_summary_hint, avg_similarity                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Agent workflow                                              │
│                                                              │
│  1. get_memory_health() → needs_consolidation: true          │
│  2. suggest_consolidation() → 3 groupes trouvés              │
│  3. Pour chaque groupe:                                      │
│     a. LLM génère résumé (aidé par content_previews)         │
│     b. consolidate_memory(title, summary, source_ids)        │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Stories

### Story 30.1: ConsolidationSuggestionService — TF-IDF similarity + clustering

**Objectif** : Service qui calcule les similarités entre mémoires et groupe les similaires.

**Algorithme TF-IDF weighted similarity** :
```python
def compute_tfidf_similarity(mem_a, mem_b, entity_freq, total_memories):
    """Similarité pondérée TF-IDF entre deux mémoires."""
    a_entities = {e["name"].lower() for e in mem_a.entities if isinstance(e, dict)}
    b_entities = {e["name"].lower() for e in mem_b.entities if isinstance(e, dict)}
    shared_e = a_entities & b_entities
    
    if not shared_e:
        return 0.0, set(), set()
    
    tfidf_shared = sum(
        math.log(max(1, total_memories) / max(1, entity_freq.get(e, 1)))
        for e in shared_e
    )
    tfidf_union = sum(
        math.log(max(1, total_memories) / max(1, entity_freq.get(e, 1)))
        for e in a_entities | b_entities
    )
    entity_sim = tfidf_shared / max(1, tfidf_union)
    
    a_concepts = set(c.lower() for c in mem_a.concepts)
    b_concepts = set(c.lower() for c in mem_b.concepts)
    shared_c = a_concepts & b_concepts
    concept_sim = len(shared_c) / max(1, len(a_concepts | b_concepts))
    
    score = 0.6 * entity_sim + 0.4 * concept_sim
    return score, shared_e, shared_c
```

**Clustering avec intersection stricte** :
```python
def find_groups(pairs, min_group_size=3):
    assigned = {}
    groups = []
    
    for mem_a, mem_b, score, shared_e, shared_c in sorted(pairs, key=lambda x: -x[2]):
        ga = assigned.get(mem_a)
        gb = assigned.get(mem_b)
        
        if ga is not None and gb is not None:
            if ga != gb:
                new_shared_e = groups[ga]["shared_entities"] & groups[gb]["shared_entities"]
                new_shared_c = groups[ga]["shared_concepts"] & groups[gb]["shared_concepts"]
                if not new_shared_e and not new_shared_c:
                    continue  # Ne pas fusionner — pas d'entité commune
                groups[ga]["memory_ids"].extend(groups[gb]["memory_ids"])
                groups[ga]["shared_entities"] = new_shared_e
                groups[ga]["shared_concepts"] = new_shared_c
                for mid in groups[gb]["memory_ids"]:
                    assigned[mid] = ga
                groups[gb] = None
        elif ga is not None:
            groups[ga]["memory_ids"].append(mem_b)
            groups[ga]["shared_entities"] &= shared_e
            groups[ga]["shared_concepts"] &= shared_c
            assigned[mem_b] = ga
        elif gb is not None:
            groups[gb]["memory_ids"].append(mem_a)
            groups[gb]["shared_entities"] &= shared_e
            groups[gb]["shared_concepts"] &= shared_c
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
    
    return [g for g in groups if g and len(g["memory_ids"]) >= min_group_size]
```

**Déduplication** :
```python
def deduplicate_groups(groups, overlap_threshold=0.5):
    groups.sort(key=lambda g: -g["avg_score"])
    result = []
    for g in groups:
        if not result:
            result.append(g)
            continue
        overlap = max(
            len(set(g["memory_ids"]) & set(r["memory_ids"])) / len(g["memory_ids"])
            for r in result
        )
        if overlap < overlap_threshold:
            result.append(g)
    return result
```

**Titre suggéré intelligent** :
```python
def suggest_title(group):
    entity = max(group["shared_entities"], key=len) if group["shared_entities"] else ""
    concept = max(group["shared_concepts"], key=len) if group["shared_concepts"] else ""
    if entity and concept:
        return f"{entity.title()} {concept}"
    elif entity:
        return f"{entity.title()} configuration"
    return "Consolidated memories"
```

**Summary hint contextuel** :
```python
def suggest_hint(group):
    entities = ", ".join(list(group["shared_entities"])[:3])
    concepts = ", ".join(list(group["shared_concepts"])[:3])
    n = len(group["memory_ids"])
    return f"{n} memories about {entities}: {concepts}"
```

**Entity frequency cache (Redis)** :
```python
async def get_entity_frequencies(self) -> Dict[str, int]:
    if self.redis:
        cached = await self.redis.get("entity_freq")
        if cached:
            return json.loads(cached)
    
    freq = await self._compute_entity_frequencies()
    
    if self.redis:
        await self.redis.setex("entity_freq", 300, json.dumps(freq))
    return freq
```

**Fichiers** :
- Créer : `api/services/consolidation_suggestion_service.py`

---

### Story 30.2: Outil MCP `suggest_consolidation`

**Objectif** : Nouvel outil MCP qui expose le service de suggestion.

**Signature** :
```python
@mcp.tool()
async def suggest_consolidation(
    min_shared_entities: int = 2,
    min_shared_concepts: int = 1,
    memory_types: List[str] = ["note"],
    tags: List[str] = ["sys:history"],
    max_age_days: int = 30,
    min_group_size: int = 3,
    max_groups: int = 5,
    similarity_threshold: float = 0.3,
) -> Dict[str, Any]:
```

**Retour** :
```json
{
    "groups": [
        {
            "source_ids": ["uuid1", "uuid2", "uuid3"],
            "titles": ["Redis cache setup", "Redis TTL config", "Redis persistence"],
            "content_previews": ["first 200 chars...", ...],
            "shared_entities": ["Redis", "cache"],
            "shared_concepts": ["cache layer", "ttl"],
            "avg_similarity": 0.72,
            "suggested_title": "Redis cache configuration",
            "suggested_tags": ["sys:history"],
            "suggested_summary_hint": "3 memories about Redis, cache: cache layer, ttl"
        }
    ],
    "total_groups_found": 3
}
```

**Fichiers** :
- Créer : `api/mnemo_mcp/tools/consolidation_tools.py`
- Modifier : `api/mnemo_mcp/server.py` — enregistrer l'outil

---

### Story 30.3: Tests TDD

**Tests unitaires** :
- `test_consolidation_suggestion_service.py` — TF-IDF similarity, clustering, déduplication, titre suggéré
- `test_consolidation_tools.py` — outil MCP, paramètres, retour

**Tests d'intégration** :
- Créer 6 mémoires avec entités partagées → vérifier 2 groupes trouvés
- Vérifier que les groupes qui se chevauchent >50% sont dédupliqués
- Vérifier le filtrage par type/tag/âge

**Fichiers** :
- Créer : `tests/services/test_consolidation_suggestion_service.py`
- Créer : `tests/mnemo_mcp/test_consolidation_tools.py`

---

## 5. Ordre d'implémentation

1. **Story 30.1** — ConsolidationSuggestionService (TF-IDF + cache Redis + clustering + déduplication)
2. **Story 30.2** — Outil MCP `suggest_consolidation`
3. **Story 30.3** — Tests TDD

---

## 6. Matrice de dégradation

| Scénario | Comportement |
|----------|-------------|
| Pas d'entités extraites | Retourne groupes vides, log warning |
| < 3 mémoires candidates | Retourne `groups: []` |
| DB HS | Retourne `error: "Database unavailable"` |
| Redis cache HS | Calcul direct sans cache (plus lent mais correct) |
| Clustering lent (>5s) | Timeout, retourne les groupes trouvés jusqu'au timeout |

---

## 7. Métriques de succès

| Métrique | Cible | Mesure |
|----------|-------|--------|
| Groupes trouvés par appel | 1-5 | Moyenne sur 50 appels |
| Similarité moyenne des groupes | > 0.4 | avg(group.avg_similarity) |
| Latence de l'outil | < 2s | P95 response time |
| Chevauchement entre groupes | < 10% | % de mémoires dans >1 groupe |
| Taux d'acceptation | > 60% | % de suggestions suivies de consolidate_memory |

---

## 8. Risques et mitigations

| Risque | Probabilité | Impact | Mitigation |
|--------|------------|--------|------------|
| O(n²) sur gros volume | Faible | Moyen | Index inversé + fenêtre temporelle |
| Groupes non pertinents | Moyenne | Moyen | Seuil similarity_threshold configurable |
| Titre suggéré bizarre | Faible | Faible | L'agent peut toujours le réécrire |
| Pas d'entités extraites | Moyenne | Moyen | Fallback sur tags partagés |
| Cache entity_freq stale | Faible | Faible | TTL 5 min + invalidation à l'extraction |

---

## 9. Dépendances

- **EPIC-28** : Entity extraction (entities, concepts doivent être extraits)
- **EPIC-29** : Index inversé (pattern réutilisé pour candidate finding)
- **Aucune nouvelle dépendance externe**
