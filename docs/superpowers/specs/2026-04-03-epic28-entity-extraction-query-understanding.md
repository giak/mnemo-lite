# EPIC-28: Entity Extraction & Query Understanding via LM Studio

> **Statut:** DRAFT | **Date:** 2026-04-03 | **Auteur:** giak
> **Inspiration:** LightRAG (HKUDS) — dual-level keyword extraction + entity-aware indexing
> **Infrastructure:** LM Studio local (API OpenAI-compatible, port 1234)

---

## 1. Problem Statement

MnemoLite recherche du texte/mémoires de manière **réactive** : la requête brute est embeddée et comparée au contenu brut. Aucune compréhension de l'intention de la requête n'est effectuée. Les mémoires sont stockées sans métadonnées structurées (entités, concepts, tags auto-générés).

**Conséquences :**
- Un agent qui cherche `"pourquoi Redis pour le cache?"` ne trouve pas une mémoire intitulée `"Decision: Chose Redis for L2 cache"` si l'embedding n'est pas assez proche sémantiquement
- Les tags sont manuels — aucune extraction automatique de concepts clés
- La recherche ne distingue pas les **concepts abstraits** (HL) des **entités nommées** (LL)
- Pas de provenance structurée : on ne sait pas quels concepts sont liés à quelle mémoire

---

## 2. Solution Overview

Deux services alimentés par **LM Studio** (Qwen2.5-7B-Instruct, ~5.5 GB RAM, GGUF Q5_K_M) :

### 2.1 Entity Extraction (à l'indexation — async)
Quand une mémoire importante est créée, un LLM local extrait :
- **Entities** : noms propres, technologies, produits, fichiers (`["Redis", "PostgreSQL", "ADR-001"]`)
- **Concepts** : idées abstraites, patterns, décisions (`["cache layer", "décision architecture", "L2 cache"]`)
- **Auto-tags** : tags suggérés normalisés (`["redis", "cache", "architecture-decision"]`)

**Non-bloquant** : la mémoire est créée instantanément. L'extraction se fait en arrière-plan via une tâche asyncio. Si LM Studio est éteint → skip silencieux.

### 2.2 Query Understanding (à la recherche — synchrone)
Avant chaque recherche mémoire, un LLM local extrait :
- **HL keywords** : concepts de haut niveau → boostent la recherche vectorielle
- **LL keywords** : entités de bas niveau → boostent la recherche lexicale + matching de tags

**Fallback** : si LM Studio indisponible → comportement actuel (requête brute).

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Linux Mint 22 (64 GB RAM, 32 GB libres)                             │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  LM Studio                                                  │    │
│  │  Modèle: Qwen2.5-7B-Instruct (GGUF Q5_K_M, ~5.5 GB RAM)    │    │
│  │  API: http://localhost:1234/v1 (OpenAI-compatible)          │    │
│  │  Structured output: json_schema (GBNF grammar)              │    │
│  └────────────────────────┬────────────────────────────────────┘    │
│                           │ http://host.docker.internal:1234        │
│                           ▼                                         │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Container API MnemoLite (FastAPI)                          │    │
│  │                                                              │    │
│  │  ┌──────────────────────────────────────────────────────┐  │    │
│  │  │  EntityExtractionService                             │  │    │
│  │  │  ├─ POST /v1/chat/completions (async httpx)         │  │    │
│  │  │  ├─ json_schema response_format (structured output) │  │    │
│  │  │  ├─ Parse → entities[], concepts[], auto_tags[]     │  │    │
│  │  │  ├─ UPDATE memories SET ... WHERE id=?              │  │    │
│  │  │  └─ Fallback: LM Studio off → skip silencieux       │  │    │
│  │  └──────────────────────────────────────────────────────┘  │    │
│  │                                                              │    │
│  │  ┌──────────────────────────────────────────────────────┐  │    │
│  │  │  QueryUnderstandingService                           │  │    │
│  │  │  ├─ POST /v1/chat/completions (async httpx)         │  │    │
│  │  │  ├─ json_schema response_format                     │  │    │
│  │  │  ├─ Extract hl_keywords[], ll_keywords[]            │  │    │
│  │  │  └─ Fallback: requête brute (comportement actuel)   │  │    │
│  │  └──────────────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  PostgreSQL 18                                              │    │
│  │  Table: memories                                            │    │
│  │  + entities JSONB (GIN index)                               │    │
│  │  + concepts JSONB (GIN index)                               │    │
│  │  + auto_tags TEXT[]                                         │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Stories

### Story 28.1: Migration schéma — colonnes JSONB + index GIN

**Objectif** : Ajouter les colonnes de stockage d'entités à la table `memories`.

**Migration** :
```sql
-- Migration: 20260403_0000_add_memory_entities.sql

ALTER TABLE memories
  ADD COLUMN IF NOT EXISTS entities JSONB DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS concepts JSONB DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS auto_tags TEXT[] DEFAULT '{}';

-- GIN index pour recherche par containment
CREATE INDEX IF NOT EXISTS idx_memories_entities_gin
  ON memories USING GIN (entities jsonb_path_ops);

CREATE INDEX IF NOT EXISTS idx_memories_concepts_gin
  ON memories USING GIN (concepts jsonb_path_ops);

-- Expression index pour recherche d'entité spécifique
CREATE INDEX IF NOT EXISTS idx_memories_entity_contains
  ON memories USING GIN ((entities->>'entities') gin_trgm_ops);
```

**Pourquoi JSONB plutôt que TEXT[]** :
- JSONB permet de stocker des objets structurés : `[{"name": "Redis", "type": "technology", "confidence": 0.95}]`
- GIN `jsonb_path_ops` supporte les opérateurs `@>`, `?`, `@?` pour des requêtes complexes
- PostgreSQL 18 optimise les opérations JSONB avec des indexes GIN partiels

**Fichiers** :
- Créer : `db/migrations/20260403_0000_add_memory_entities.sql`
- Modifier : `api/db/repositories/memory_repository.py` — méthodes `update_entities()`, `search_by_entity()`

---

### Story 28.2: LMStudioClient — Client HTTP robuste pour LM Studio

**Objectif** : Client async HTTP qui communique avec LM Studio via l'API OpenAI-compatible.

**Contraintes LM Studio identifiées** (recherche web, issues GitHub) :
- `response_format: "json_object"` est **rejeté** par LM Studio (issue #189, #46)
- `response_format: "json_schema"` **fonctionne** avec GBNF grammar (llama.cpp #11988 fixed)
- LM Studio 0.3.29+ supporte l'API Responses avec structured output
- Le fallback sans `response_format` fonctionne mais le JSON n'est pas garanti

**Design du client** :
```python
class LMStudioClient:
    """
    Client HTTP async pour LM Studio (API OpenAI-compatible).
    
    Utilise json_schema (GBNF) pour garantir du JSON valide.
    Fallback: si json_schema échoue, retry sans response_format + parsing JSON.
    """
    
    def __init__(self, base_url: str, model: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._available: bool | None = None
    
    async def is_available(self) -> bool:
        """Check if LM Studio server is running and model is loaded."""
        try:
            client = self._get_client()
            resp = await client.get(f"{self.base_url}/models")
            models = resp.json().get("data", [])
            return len(models) > 0
        except Exception:
            return False
    
    async def extract_json(
        self,
        system_prompt: str,
        user_content: str,
        json_schema: dict,
        temperature: float = 0.1,
        max_retries: int = 2,
    ) -> dict | None:
        """
        Extract structured JSON from LM Studio.
        
        Uses json_schema (GBNF grammar) for guaranteed valid JSON.
        Falls back to plain text + json_repair if schema fails.
        """
        # Attempt 1: json_schema (GBNF grammar)
        # Attempt 2: No response_format + json_repair parsing
        # Attempt 3: Return None (LM Studio unavailable)
```

**Schéma JSON pour l'extraction d'entités** :
```json
{
  "type": "object",
  "properties": {
    "entities": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {"type": "string"},
          "type": {"type": "string", "enum": ["technology", "product", "file", "person", "organization", "concept", "other"]}
        },
        "required": ["name", "type"]
      }
    },
    "concepts": {
      "type": "array",
      "items": {"type": "string"}
    },
    "tags": {
      "type": "array",
      "items": {"type": "string"}
    }
  },
  "required": ["entities", "concepts", "tags"]
}
```

**Schéma JSON pour le query understanding** :
```json
{
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
```

**Fichiers** :
- Créer : `api/services/lm_studio_client.py`

---

### Story 28.3: EntityExtractionService — Extraction async à l'indexation

**Objectif** : Service qui extrait entités/concepts/tags d'une mémoire via LM Studio, de manière asynchrone.

**Flux** :
```
WriteMemoryTool.execute()
    │
    ├─ 1. Crée la mémoire en DB → IMMÉDIAT (retour à l'agent)
    │
    └─ 2. Si mémoire "importante" → asyncio.create_task(extract_entities(memory_id))
            │
            ├─ Vérifie LM Studio disponible (is_available)
            ├─ Si non disponible → log debug, return
            │
            ├─ POST LM Studio avec prompt d'extraction
            │
            ├─ Parse JSON → entities, concepts, tags
            │
            ├─ UPDATE memories SET entities=?, concepts=?, auto_tags=? WHERE id=?
            │
            └─ Log: "entities_extracted" memory_id=... entities=3 concepts=2 tags=4
```

**Quelles mémoires extraire** :
| Memory Type | Extraire ? | Raison |
|-------------|-----------|--------|
| `decision` | ✅ Oui | Décisions architecturales — riche en entités |
| `reference` | ✅ Oui | Documentation — concepts clés importants |
| `note` | ✅ Oui | Observations — peut contenir des insights |
| `investigation` | ✅ Oui | Truth Engine outputs — entités critiques |
| `sys:core` | ✅ Oui | Connaissances permanentes — extraction prioritaire |
| `sys:anchor` | ✅ Oui | Points de référence — liens entre concepts |
| `sys:pattern` | ✅ Oui | Patterns appris — concepts réutilisables |
| `conversation` | ❌ Non | Conversations brutes — trop de bruit |
| `sys:history` | ❌ Non | Historique éphémère — decay rapide |
| `sys:trace` | ❌ Non | Traces d'exécution — pas de valeur sémantique |
| `task` | ❌ Non | TODOs simples — pas assez de contenu |

**Prompt d'extraction** :
```
You are an entity and concept extraction specialist.

Extract named entities, abstract concepts, and suggested tags from the text.

Rules:
- Only extract what is EXPLICITLY mentioned or clearly implied
- Do not invent or infer entities not present
- Normalize names (lowercase for tags, proper case for entities)
- Entities are concrete: technologies, products, files, people, organizations
- Concepts are abstract: patterns, decisions, architectural choices
- Tags should be short, lowercase, hyphenated (e.g., "cache-layer", "redis")
- Return ONLY valid JSON, no explanation

Text:
Title: {title}
Content: {content}
```

**Fichiers** :
- Créer : `api/services/entity_extraction_service.py`
- Modifier : `api/mnemo_mcp/tools/memory_tools.py` — appeler `extract_entities()` après `WriteMemoryTool.execute()`

---

### Story 28.4: QueryUnderstandingService — HL/LL keywords pour la recherche

**Objectif** : Avant chaque recherche mémoire, extraire les keywords HL (concepts) et LL (entités) de la requête.

**Flux** :
```
search_memory(query="comment on gère la consolidation des mémoires?")
    │
    ├─ QueryUnderstandingService.extract_keywords(query)
    │   │
    │   ├─ LM Studio disponible ? → Oui
    │   │
    │   ├─ POST LM Studio:
    │   │   "Extract high-level concepts and low-level entities from this query.
    │   │    HL = abstract themes, LL = concrete specifics.
    │   │    Query: comment on gère la consolidation des mémoires?"
    │   │
    │   └─ → {"hl_keywords": ["consolidation de mémoires", "cycle de vie"],
    │         "ll_keywords": ["sys:history", "configure_decay", "consolidate_memory"]}
    │
    ├─ PARALLEL:
    │   ├─ Lexical search sur LL keywords (title ILIKE, trigram boosté)
    │   ├─ Vector search sur requête originale (embedding)
    │   ├─ Tag search sur LL keywords si match auto_tags ou tags
    │   └─ Entity search sur LL keywords si match entities JSONB
    │
    ├─ RRF Fusion (weights: lexical 0.35, vector 0.35, tag 0.15, entity 0.15)
    │
    ├─ BM25 Reranking (top 30)
    │
    ├─ Temporal Decay
    │
    └─ Résultats
```

**Prompt de query understanding** :
```
You are a query understanding assistant.

Analyze the user's search query and extract:
- hl_keywords: High-level concepts and themes (abstract, 2-4 items)
- ll_keywords: Low-level entities and specifics (concrete, 2-5 items)

HL keywords should capture the intent and themes.
LL keywords should capture specific names, technologies, files, or tags.

Query: {query}

Return ONLY valid JSON.
```

**Fichiers** :
- Créer : `api/services/query_understanding_service.py`
- Modifier : `api/services/hybrid_memory_search_service.py` — intégrer HL/LL dans `_perform_search()`

---

### Story 28.5: Intégration dans le pipeline de recherche hybride

**Objectif** : Modifier `HybridMemorySearchService` pour utiliser les HL/LL keywords.

**Modifications** :

**1. Nouvelle méthode `_entity_search()`** :
```python
async def _entity_search(self, ll_keywords: list[str], filters: dict) -> list:
    """Search memories by entity containment in JSONB column."""
    # SELECT * FROM memories WHERE entities @> '[{"name": "Redis"}]'::jsonb
    # Utilise GIN index pour performance
```

**2. Nouvelle méthode `_tag_search()`** :
```python
async def _tag_search(self, ll_keywords: list[str], filters: dict) -> list:
    """Search memories by tag/auto_tag matching."""
    # SELECT * FROM memories WHERE auto_tags && ARRAY['redis', 'cache']
    # OU tags && ARRAY[...]
```

**3. Modification de `_perform_search()`** :
```python
async def _perform_search(self, query, keywords, filters):
    # Si keywords disponibles (LM Studio a répondu)
    if keywords:
        lexical_results = await self._lexical_search(keywords.ll_keywords, filters)
        vector_results = await self._vector_search(query, filters)
        tag_results = await self._tag_search(keywords.ll_keywords, filters)
        entity_results = await self._entity_search(keywords.ll_keywords, filters)
    else:
        # Fallback: comportement actuel
        lexical_results, vector_results = await asyncio.gather(
            self._lexical_search(query, filters),
            self._vector_search(query, filters),
        )
        tag_results = []
        entity_results = []
    
    return lexical_results, vector_results, tag_results, entity_results
```

**4. Modification de la RRF fusion** :
```python
# 4 sources au lieu de 2
weights = {
    "lexical": 0.35,
    "vector": 0.35,
    "tag": 0.15,
    "entity": 0.15,
}
```

**Fichiers** :
- Modifier : `api/services/hybrid_memory_search_service.py`
- Modifier : `api/services/rrf_fusion_service.py` — supporter 4 sources

---

### Story 28.6: Configuration et variables d'environnement

**Variables d'environnement** :
```env
# LM Studio Configuration
LM_STUDIO_URL=http://host.docker.internal:1234/v1
LM_STUDIO_MODEL=qwen2.5-7b-instruct
LM_STUDIO_TIMEOUT=30

# Entity Extraction
ENTITY_EXTRACTION_ENABLED=true
ENTITY_EXTRACTION_MEMORY_TYPES=decision,reference,note,investigation
ENTITY_EXTRACTION_SYSTEM_TAGS=sys:core,sys:anchor,sys:pattern

# Query Understanding
QUERY_UNDERSTANDING_ENABLED=true
QUERY_UNDERSTANDING_FALLBACK=true  # Si LM Studio off → requête brute
```

**docker-compose.yml** — ajouter au service `api` :
```yaml
environment:
  - LM_STUDIO_URL=http://host.docker.internal:1234/v1
  - LM_STUDIO_MODEL=qwen2.5-7b-instruct
  - LM_STUDIO_TIMEOUT=30
  - ENTITY_EXTRACTION_ENABLED=${ENTITY_EXTRACTION_ENABLED:-true}
  - ENTITY_EXTRACTION_MEMORY_TYPES=${ENTITY_EXTRACTION_MEMORY_TYPES:-decision,reference,note,investigation}
  - ENTITY_EXTRACTION_SYSTEM_TAGS=${ENTITY_EXTRACTION_SYSTEM_TAGS:-sys:core,sys:anchor,sys:pattern}
  - QUERY_UNDERSTANDING_ENABLED=${QUERY_UNDERSTANDING_ENABLED:-true}
  - QUERY_UNDERSTANDING_FALLBACK=${QUERY_UNDERSTANDING_FALLBACK:-true}
```

**Fichiers** :
- Modifier : `docker-compose.yml`

---

### Story 28.7: Outil MCP pour ré-extraction et debugging

**Objectif** : Nouvel outil MCP `extract_entities` pour :
1. Ré-extracter les entités d'une mémoire existante
2. Lister les entités/concepts d'une mémoire
3. Rechercher des mémoires par entité

**Outils MCP ajoutés** :
| Tool | Description |
|------|-------------|
| `extract_entities` | Ré-extrait les entités d'une mémoire (manuel ou refresh) |
| `search_by_entity` | Recherche des mémoires contenant une entité spécifique |

**Fichiers** :
- Créer : `api/mnemo_mcp/tools/entity_extraction_tool.py`
- Modifier : `api/mnemo_mcp/server.py` — enregistrer le nouvel outil

---

### Story 28.8: Tests et validation

**Tests unitaires** :
- `test_lm_studio_client.py` — disponibilité, extraction JSON, fallback
- `test_entity_extraction_service.py` — extraction, skip si LM Studio off
- `test_query_understanding_service.py` — HL/LL extraction, fallback
- `test_hybrid_search_with_keywords.py` — RRF 4 sources, weights

**Tests d'intégration** :
- Créer une mémoire → vérifier extraction async → rechercher par entité
- Rechercher avec query understanding → vérifier résultats améliorés
- LM Studio éteint → vérifier fallback transparent

**Fichiers** :
- Créer : `api/tests/test_lm_studio_client.py`
- Créer : `api/tests/test_entity_extraction_service.py`
- Créer : `api/tests/test_query_understanding_service.py`

---

## 5. Matrice de dégradation

| Scénario | Entity Extraction | Query Understanding | Recherche |
|----------|------------------|---------------------|-----------|
| LM Studio éteint | Skip silencieux | Fallback requête brute | Lexical + Vectoriel (actuel) |
| Timeout LM Studio | Retry 1×, puis skip | Fallback requête brute | Lexical + Vectoriel (actuel) |
| JSON invalide | Retry avec json_repair | Retry avec json_repair | Lexical + Vectoriel (actuel) |
| Modèle non chargé | Détection via `/models`, skip | Détection via `/models`, fallback | Lexical + Vectoriel (actuel) |
| PostgreSQL HS | Échec UPDATE, log error | Échec recherche, 503 | 503 |

---

## 6. Métriques de succès

| Métrique | Cible | Mesure |
|----------|-------|--------|
| Taux d'extraction JSON valide | > 90% | `json_repair` parse rate |
| Latence extraction (async) | < 5s | Time from memory creation to entity update |
| Latence query understanding | < 2s | Time from query to keywords |
| Amélioration recall@5 | +20% | Benchmark avant/après sur 50 requêtes |
| Amélioration precision@5 | +15% | Benchmark avant/après sur 50 requêtes |
| Taux de fallback | < 5% | % de recherches sans query understanding |

---

## 7. Ordre d'implémentation

1. **Story 28.1** — Migration DB (prérequis pour tout le reste)
2. **Story 28.2** — LMStudioClient (prérequis pour 28.3, 28.4)
3. **Story 28.3** — EntityExtractionService (valeur immédiate : métadonnées)
4. **Story 28.4** — QueryUnderstandingService (valeur immédiate : recherche améliorée)
5. **Story 28.5** — Intégration pipeline de recherche
6. **Story 28.6** — Configuration docker-compose
7. **Story 28.7** — Outils MCP
8. **Story 28.8** — Tests

---

## 8. Risques et mitigations

| Risque | Probabilité | Impact | Mitigation |
|--------|------------|--------|------------|
| LM Studio pas lancé au démarrage | Haute | Faible | Fallback silencieux, extraction retardée |
| Modèle Qwen2.5-7B trop lent | Moyenne | Moyen | Timeout 30s, retry 1×, skip si échec |
| JSON extraction peu fiable | Faible | Moyen | json_repair parsing, retry, validation schema |
| GIN index trop lourd en écriture | Faible | Faible | UPDATE async, pas de write path critique |
| Over-engineering pour peu de gain | Moyenne | Moyen | Benchmark avant/après, feature flag |

---

## 9. Dépendances

- **LM Studio** : Doit être lancé avec Qwen2.5-7B-Instruct chargé
- **httpx** : Déjà dans requirements.txt (utilisé ailleurs)
- **json_repair** : À ajouter dans requirements.txt (parsing JSON robuste)
- **PostgreSQL 18** : Déjà en place, GIN index natif

---

## 10. Notes de recherche

### LM Studio structured output
- `response_format: "json_object"` est **rejeté** (issue #189)
- `response_format: "json_schema"` **fonctionne** via GBNF grammar (llama.cpp #11988 fixed)
- LM Studio 0.3.29+ a l'API Responses avec structured output
- **Stratégie** : Utiliser `json_schema` en priorité, fallback sans response_format + `json_repair`

### Qwen2.5-7B pour l'extraction
- Benchmark AscentCore : JSON schema compliance 74% (Q4), ROUGE-L 0.462
- r/LocalLLaMA : Qwen3 gagne sur les structured outputs via LM Studio
- Qwen2.5-7B est excellent en multilingue FR/EN
- Latence estimée : 1-2s pour des prompts courts d'extraction

### PostgreSQL JSONB GIN
- `jsonb_path_ops` : Plus petit, plus rapide pour `@>` containment
- Expression index sur `entities->>'entities'` pour recherche substring
- GIN index sur JSONB arrays est natif et performant
- PostgreSQL 18 améliore les performances JSONB vs 17
