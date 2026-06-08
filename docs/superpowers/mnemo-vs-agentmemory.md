# 📊 Rapport Comparatif : MnemoLite vs AgentMemory

> **Date** : Juin 2025 (mise à jour)  
> **Auteur** : Analyse automatisée via Codebuff  
> **Version MnemoLite** : 5.0.0-dev  
> **Version AgentMemory** : 0.8.4  
> **Dernière mise à jour** : Juin 2025 — reflète PrivacyService (EPIC-42), GLiNER, Outcome Feedback, Worker, Hooks Claude Code  

---

## Table des Matières

1. [Vue d'Ensemble](#1-vue-densemble)
2. [Architecture des Deux Piliers de MnemoLite](#2-architecture-des-deux-piliers-de-mnemolite)
3. [Architecture d'AgentMemory](#3-architecture-dagentmemory)
4. [Comparaison Détaillée par Fonctionnalité](#4-comparaison-détaillée-par-fonctionnalité)
5. [Analyse des Outils MCP](#5-analyse-des-outils-mcp)
6. [Avantages et Inconvénients](#6-avantages-et-inconvénients)
7. [Idées et Inspirations](#7-idées-et-inspirations)
8. [Recommandations Actionnables](#8-recommandations-actionnables)
9. [Matrice de Décision](#9-matrice-de-décision)
10. [Conclusion](#10-conclusion)

---

## 1. Vue d'Ensemble

| Critère | **MnemoLite** | **AgentMemory** |
|---------|---------------|-----------------|
| **Version** | 5.0.0-dev | 0.8.4 |
| **Langage** | Python (FastAPI + SQLAlchemy) | TypeScript (Node.js ESM) |
| **Licence** | MIT | Apache-2.0 |
| **Base de données** | PostgreSQL 18 + pgvector + pg_trgm + pg_partman | SQLite (via iii-engine / iii-sdk) |
| **Cache** | Redis 7 (L2) + In-Memory (L1) | In-process (iii-sdk StateKV) |
| **Embeddings** | 100% local (nomic-embed-text + jina-code, 768D) | Multi-provider (OpenAI, Cohere, Gemini, Voyage, local/Xenova) |
| **Transport MCP** | Streamable HTTP :8002 + stdio | stdio + HTTP (:3111) |
| **Outils MCP** | ~33 outils + 8 ressources + prompts | ~43 outils |
| **Hooks automatiques** | Partiel (2 hooks : Stop + UserPromptSubmit) | 12 hooks (session-start, pre-tool-use, etc.) |
| **UI** | Vue 3 SPA complète (13 pages, SCADA) | Viewer temps réel (:3113) |
| **Installation** | Docker Compose (8 conteneurs) | `npx @agentmemory/agentmemory` |
| **RAM requise** | ~8-24 GB (avec modèles locaux) | ~512 MB |
| **Observabilité** | OpenObserve + OpenTelemetry | Telemetry basique |
| **Tests** | 1570+ tests (pytest) | Vitest (suite intégrée) |
| **Privacy** | ✅ PrivacyService (EPIC-42, 12 patterns) | ✅ stripPrivateData (tags + regex) |
| **Agents supportés** | Claude Desktop, Cursor, tout client MCP | Claude Code, Cursor, Aider, Gemini CLI, tout MCP/HTTP |

---

## 2. Architecture des Deux Piliers de MnemoLite

MnemoLite possède **deux piliers fondamentaux** distincts qui répondent à des besoins différents :

### 🏗️ Pilier A : Code Intelligence (stockage/indexation de code)

```
Code Source → Tree-sitter AST → Chunks sémantiques
                                    ↓
                           Metadata Extractor (imports, calls, docstrings)
                                    ↓
                           LSP Type Extractor (Pyright, TS LSP)
                                    ↓
                           Dual Embedding (TEXT ou CODE, 768D)
                                    ↓
                           PostgreSQL (code_chunks table)
                                    ↓
                           Graph Construction (calls, imports, re-exports, contains)
                                    ↓
                           Metrics (Coupling, PageRank, Edge Weights)
```

#### Composants clés du Pilier A

| Composant | Fichier | Description |
|-----------|---------|-------------|
| **CodeChunkingService** | `api/services/code_chunking_service.py` | AST parsing via tree-sitter (Python, TypeScript, JavaScript, Markdown), split-then-merge algorithm, détection barrel/config/test |
| **CodeIndexingService** | `api/services/code_indexing_service.py` | Pipeline 7 étapes : langue → chunk → metadata → embedding → stockage → graphe → résumé |
| **DualEmbeddingService** | `api/services/dual_embedding_service.py` | nomic-embed-text-v1.5 (TEXT, 260MB) + jina-embeddings-v2-base-code (CODE, 400MB), 768D, lazy loading, circuit breakers |
| **GraphConstructionService** | `api/services/graph_construction_service.py` | Graphe de dépendances (calls, imports, re-exports, contains), résolution par name_path, métriques coupling/PageRank |
| **LSP Type Extractor** | `api/services/lsp/type_extractor.py` | Pyright pour Python, TypeScript LSP pour TS/JS — enrichit chunks avec return types, param types |
| **SymbolPathService** | `api/services/symbol_path_service.py` | Noms hiérarchiques qualifiés (ex: `models.user.User.validate`) |
| **FileClassificationService** | `api/services/file_classification_service.py` | Détection barrel files, configs, test files |
| **HybridCodeSearchService** | `api/services/hybrid_code_search_service.py` | Recherche hybride code avec filtres (language, chunk_type, repository, LSP return_type/param_type) |
| **CascadeCache** | `api/services/caches/cascade_cache.py` | L1 in-memory + L2 Redis pour les chunks déjà indexés |
| **Incremental Indexing** | `api/mnemo_mcp/tools/indexing_tools.py` | Basé sur mtime vs last_indexed_at (50s vs 6.5h pour full reindex) |
| **Markdown Workspace Indexer** | `api/mnemo_mcp/tools/indexing_tools.py` | Indexation markdown spécialisée (split by ## → embed → store), 10x plus rapide |

#### Pipeline d'indexation complète (7 étapes)

1. **Language Detection** — Extension-based, 15 langues supportées
2. **AST Chunking** — Tree-sitter split-then-merge, détection barrel/config/test
3. **Metadata Extraction** — Imports, calls, docstrings, decorators, exports
4. **LSP Type Enrichment** — Return types, param types (Pyright / TS LSP)
5. **Dual Embedding** — TEXT (nomic) ou CODE (jina) modèle, 768D halfvec
6. **Graph Construction** — Calls, imports, re-exports, contains hierarchy
7. **Summary Generation** — Résumé des chunks et modules

#### Filtres de recherche code

- `language` — Python, TypeScript, JavaScript, etc.
- `chunk_type` — function, class, method, module, barrel, config, test
- `repository` — Nom du projet
- `file_path` — Chemin de fichier
- `lsp_return_type` — Type de retour LSP (ex: `str`, `Optional[int]`)
- `lsp_param_type` — Type de paramètre LSP

### 🧠 Pilier B : Mémoire Sémantique (stockage de texte/connaissances)

```
Texte/Connaissance → write_memory(title, content, type, tags)
                            ↓
                    Embedding (nomic-embed-text, 768D)
                            ↓
                    PostgreSQL (memories table) + halfvec
                            ↓
                    Entity Extraction (GLiNER, async via Redis Streams)
                            ↓
                    Decay Temporel + Outcome Feedback
                            ↓
                    Consolidation (LLM summarize + soft-delete)
```

#### Composants clés du Pilier B

| Composant | Fichier | Description |
|-----------|---------|-------------|
| **MemoryRepository** | `api/db/repositories/memory_repository.py` | CRUD complet, soft-delete, consommation, outcome tracking |
| **HybridMemorySearchService** | `api/services/hybrid_memory_search_service.py` | Recherche hybride lexical + vector + RRF fusion |
| **MemoryDecayService** | `api/services/memory_decay_service.py` | Decay exponentiel configurable par tag, outcome factor |
| **EntityExtractionService** | `api/services/entity_extraction_service.py` | Extraction d'entités via GLiNER (zero-shot NER) |
| **ConsolidationSuggestionService** | `api/services/consolidation_suggestion_service.py` | Groupement TF-IDF + clustering pour suggestion de consolidation |
| **MemoryRelationshipService** | `api/services/memory_relationship_service.py` | Graphe de relations entre mémoires |
| **QueryUnderstandingService** | `api/services/query_understanding_service.py` | Analyse de requête pour la recherche |
| **RRFFusionService** | `api/services/rrf_fusion_service.py` | Reciprocal Rank Fusion (k=60 adaptatif) |
| **BM25RerankService** | `api/services/bm25_rerank_service.py` | Reranking BM25 pour résultats lexicaux |
| **SystemSnapshotTool** | `api/mnemo_mcp/tools/memory_tools.py` | Snapshot boot 4x plus rapide que requêtes séquentielles |
| **ConfigureDecayTool** | `api/mnemo_mcp/tools/memory_tools.py` | Configuration dynamique du decay par tag pattern |

#### 6 Types de Mémoire

| Type | Usage | Exemple |
|------|-------|---------|
| `note` | Observation générale | "User prefers async/await over callbacks" |
| `decision` | Choix architectural | "Chose Redis for L2 cache (see ADR-001)" |
| `task` | TODO/action | "Implement cursor-based pagination" |
| `reference` | Référence externe | "PostgreSQL 18 halfvec documentation" |
| `conversation` | Résumé de conversation | "Discussed migration strategy with team" |
| `investigation` | Recherche en cours | "Debugging memory leak in worker process" |

#### Lifecycle States

| State | Description |
|-------|-------------|
| `sealed` | Validé, fiable, ne change plus |
| `candidate` | À vérifier, pas encore confirmé |
| `doubt` | Incertain, possiblement obsolète |
| `summary` | Mémoire de consolidation |

#### Decay Temporel Configurable

| Tag Pattern | Decay Rate | Half-Life | Description |
|-------------|-----------|-----------|-------------|
| `sys:core` | 0.001 | ~2 ans | Connaissances fondamentales |
| `sys:anchor` | 0.001 | ~2 ans | Points d'ancrage |
| `sys:protocol` | 0.002 | ~1 an | Règles opérationnelles |
| `sys:pattern` | 0.005 | ~140 jours | Patterns identifiés |
| `sys:user:profile` | 0.005 | ~140 jours | Profil utilisateur |
| `sys:extension` | 0.01 | ~70 jours | Extensions |
| `sys:project` | 0.01 | ~70 jours | Contexte projet |
| `sys:drift` | 0.02 | ~35 jours | Dérives/écarts |
| `sys:history` | 0.05 | ~14 jours | Historique |
| `sys:trace` | 0.08 | ~9 jours | Traces d'exécution agent |
| `ephemeral` | 0.1 | ~7 jours | Éphémère |

Formule : `final_score = relevance_score × exp(-decay_rate × age_days) × outcome_factor`

Outcome factor : `1 + 0.5 × (positive - negative) / (positive + negative + 1)`  
Plage : (0.5, 1.5) — les mémoires utiles déclinent plus lentement, les inutiles plus vite.

### 🔗 Services Transversaux

| Service | Description |
|---------|-------------|
| **RRFFusionService** | Reciprocal Rank Fusion avec k=60 adaptatif, poids configurables |
| **DualEmbeddingService** | Routing TEXT vs CODE selon le type de contenu |
| **QueryUnderstandingService** | Analyse et reformulation de requêtes |
| **BM25RerankService** | Reranking post-recherche |
| **CascadeCache** | L1 in-memory (100MB) + L2 Redis — hit rates combinés |
| **PrivacyService** | ✅ EPIC-42 — Secret stripping auto (12 patterns), intégré write_memory / update_memory |
| **Worker Service** | ✅ Background jobs via Redis Streams (conversation import, batch indexing, entity extraction) |
| **OpenTelemetry** | Traces + métriques exportées vers OpenObserve |
| **Circuit Breakers** | Protection contre pannes embedding, Redis, DB |

---

## 3. Architecture d'AgentMemory

```
Claude Code / Cursor / Aider → Hooks (12 scripts .mjs)
                               → MCP Server (43 tools)
                               → REST API (:3111)
                               → iii-engine (SQLite + in-process BM25/Vector/Graph)
                               → Viewer (:3113)
```

### Composants principaux

| Composant | Fichier | Description |
|-----------|---------|-------------|
| **iii-engine** | (dépendance externe) | Moteur SQLite in-process : BM25 + Vector + Graph |
| **StateKV** | `src/state/kv.ts` | Key-value store SQLite persisté |
| **VectorIndex** | `src/state/vector-index.ts` | Index vectoriel in-process |
| **HybridSearch** | `src/state/hybrid-search.ts` | tripleStreamSearch (BM25 + Vector + Graph) |
| **Hooks** | `src/hooks/` | 12 scripts lifecycle automatiques |
| **Providers** | `src/providers/` | OpenAI, Cohere, Gemini, Voyage, local/Xenova |
| **Viewer** | `src/viewer/` | Interface temps réel sur :3113 |

### Pipeline de Mémoire 4-Tier

```
RawObservation → Working Memory (session)
                      ↓ (auto-compress)
               CompressedObservation → Episodic Memory
                                          ↓ (consolidate)
                                    Semantic Memory (patterns, preferences, architecture)
                                          ↓ (crystallize)
                                    Procedural Memory (crystals, lessons, routines)
```

| Tier | Type | Description | Durée |
|------|------|-------------|-------|
| **Working** | `RawObservation` | Capture brute de session | Session |
| **Episodic** | `CompressedObservation` | Compression LLM d'observations | Jours-semaines |
| **Semantic** | `Memory` (pattern, preference, architecture, etc.) | Connaissances consolidées | Semaines-mois |
| **Procedural** | `Crystal`, `Lesson`, `Routine` | Connaissances opérationnelles | Permanent |

### Consolidation Automatique

1. **Collection** — Récupère les `CompressedObservation` d'une session
2. **Filtrage** — Ne garde que importance ≥ 5
3. **Groupement** — Par concept (minimum 3 observations distinctes)
4. **LLM Consolidation** — Max 10 appels LLM, top 8 observations par groupe, timeout 30s
5. **Parsing XML** — Extrait `Memory` avec types validés (pattern, preference, architecture, etc.)
6. **Déduplication** — Évite les titres dupliqués avant insertion

### Recherche Hybride (tripleStreamSearch)

```
Query → BM25 (limit×2) ──┐
      → Vector (limit×2) ─┤→ RRF Fusion (k=60) → Résultats classés
      → Graph (entity-based)─┘     avec poids dynamiques
```

- **BM25** : Keyword search in-process
- **Vector** : Si disponible, avec fallback gracieux
- **Graph** : Extraction d'entités + expansion vectorielle (top 5 résultats vectoriels)
- **Poids dynamiques** : Si un stream ne retourne rien, son poids est redistribué
- **RRF_K** : 60 (même valeur que MnemoLite)

### Secret Stripping (Privacy)

AgentMemory implémente un **stripping automatique des secrets** avant stockage :

| Catégorie | Patterns |
|-----------|----------|
| **Tags privés** | `<private>...</private>` → `[REDACTED]` |
| **OpenAI** | `sk-proj-*`, `sk-*`, `sk-ant-*` |
| **GitHub/NPM** | `gh[pus]_*`, `github_pat_*`, `npm_*` |
| **AWS** | `AKIA*` |
| **Google** | `AIza*` |
| **Slack** | `xoxb-*` |
| **GitLab** | `glpat-*` |
| **DigitalOcean** | `dop_v1_*` |
| **Bearer tokens** | `Bearer ...` |
| **JWT** | `eyJ...` (3 composants séparés par dots) |
| **Generic secrets** | `api-key: ...`, `secret: ...` |

### Auto-Forget

| Critère | Seuil |
|---------|-------|
| **TTL Expiry** | `forgetAfter` timestamp dépassé |
| **Contradiction** | Jaccard similarity > 0.9 |
| **Scope** | Derniers 1000 items non-supprimés |
| **dryRun** | Mode test sans suppression réelle |

### Hooks Automatiques (12)

| Hook | Moment | Action |
|------|--------|--------|
| `session-start` | Début de session | Injecte contexte pertinent |
| `prompt-submit` | Avant envoi prompt | Ajoute contexte mémoire |
| `pre-tool-use` | Avant appel outil | Capture observation |
| `post-tool-use` | Après appel outil | Capture résultat |
| `notification` | Notification agent | Log observation |
| `stop` | Arrêt agent | Compress & save |
| `subagent-stop` | Arrêt subagent | Compress & save |
| `task-completed` | Tâche terminée | Marquer done |
| `session-end` | Fin de session | Consolidation |
| `user-prompt-submit` | Prompt utilisateur | Capture input |
| `auto-consolidation` | Background | Consolidation périodique |
| `auto-forget` | Background | Nettoyage périodique |

### Crystallisation

La cristallisation convertit des **actions terminées** en **cristaux** compacts :

1. Valide que les `actionIds` sont `done` ou `cancelled`
2. Récupère les `ActionEdge` associées (chaîne de contexte)
3. Génère un `CrystalDigest` via LLM (narratif, outcomes, fichiers, leçons)
4. Sauvegarde le `Crystal` dans le store
5. Crée des `Lesson` individuelles à partir du digest
6. Met à jour les `Action` avec référence `crystallizedInto`

---

## 4. Comparaison Détaillée par Fonctionnalité

### 🧠 Mémoire Sémantique

| Fonctionnalité | MnemoLite | AgentMemory | Avantage |
|---|---|---|---|
| **Types de mémoire** | 6 (note, decision, task, reference, conversation, investigation) | 8+ (pattern, preference, architecture, procedure, concept, relationship, fact, heuristic) | AgentMemory — Plus riche en typologie |
| **Lifecycle states** | 4 (sealed, candidate, doubt, summary) | 4 tiers (Working, Episodic, Semantic, Procedural) | Égal — Approches différentes |
| **Decay temporel** | ✅ Exponentiel, configurable par tag (11 presets), outcome factor | ✅ forgetAfter TTL, contradiction Jaccard | MnemoLite — Plus fin et configurable |
| **Outcome feedback** | ✅ rate_memory (helpful/unhelpful, score -1 à 1) | ❌ Non implémenté | **MnemoLite** |
| **Consolidation** | ✅ LLM + TF-IDF clustering + soft-delete | ✅ Auto-consolidation 4-tier + crystallisation | AgentMemory — Pipeline plus mature |
| **Déduplication** | ✅ Jaccard similarity + pg_trgm (dedup_check=True) | ✅ Jaccard similarity + titre unique | **Égal** |
| **Consumption tracking** | ✅ mark_consumed, consumed filter | ❌ Non implémenté | **MnemoLite** |
| **Entity extraction** | ✅ GLiNER (zero-shot NER, local) | ❌ Pas d'extraction d'entités native | **MnemoLite** |
| **Relations entre mémoires** | ✅ Graphe de relations (EPIC-29) + get_related_memories + get_memory_graph | ✅ Graph edges + MemoryRelation | **Égal** |
| **Snapshot boot** | ✅ get_system_snapshot (4x plus rapide) | ❌ Non implémenté | **MnemoLite** |
| **Consolidation suggestion** | ✅ suggest_consolidation (TF-IDF clustering) | ❌ Non | **MnemoLite** |
| **Worker / Background jobs** | ✅ Redis Streams (conversation import, batch indexing, entity extraction) | ❌ Non | **MnemoLite** |
| **Privacy/Secret stripping** | ✅ PrivacyService (EPIC-42, 12 patterns, auto) | ✅ Regex patterns complets + `<private>` tags | **Égal** |
| **Capture silencieuse** | ⚠️ Partiel (2 hooks : Stop + UserPromptSubmit) | ✅ Hooks automatiques (12) | **AgentMemory** |
| **Team sharing** | ❌ Non implémenté | ✅ memory_team_share / memory_team_feed | **AgentMemory** |
| **Export** | ✅ JSON export (REST + MCP, project scoping) | ✅ JSON + Obsidian Markdown | **AgentMemory** (Obsidian) |
| **Audit trail** | ❌ Non implémenté | ✅ memory_audit + governance_delete | **AgentMemory** |
| **Hooks Claude Code** | ⚠️ Partiel (2 hooks déployés) | ✅ 12 hooks complets | **AgentMemory** |

### 🖥️ Code Intelligence

| Fonctionnalité | MnemoLite | AgentMemory | Avantage |
|---|---|---|---|
| **AST Parsing** | ✅ Tree-sitter (15+ langues) | ❌ Aucun | **MnemoLite** |
| **Chunking sémantique** | ✅ Split-then-merge, barrel/config/test | ❌ Aucun | **MnemoLite** |
| **LSP Type Extraction** | ✅ Pyright + TS LSP | ❌ Aucun | **MnemoLite** |
| **Dual Embedding** | ✅ TEXT + CODE models | ❌ Aucun | **MnemoLite** |
| **Graphe de code** | ✅ Calls, imports, re-exports, contains | ❌ Aucun graphe de code | **MnemoLite** |
| **Métriques code** | ✅ Coupling, PageRank, Edge Weights | ❌ Aucune | **MnemoLite** |
| **Incremental indexing** | ✅ mtime-based (50s vs 6.5h) | ❌ Aucun | **MnemoLite** |
| **Markdown indexing** | ✅ Spécialisé (10x plus rapide) | ❌ Aucun | **MnemoLite** |
| **Filtres de recherche** | ✅ Language, chunk_type, repository, LSP types | ❌ Aucun filtre code | **MnemoLite** |
| **Traversée de graphe** | ✅ BFS, incoming/outgoing, find_path | ❌ Aucun | **MnemoLite** |

> **Verdict** : MnemoLite est **incomparable** sur la Code Intelligence. AgentMemory n'a aucune fonctionnalité d'indexation ou de recherche de code.

### 🔍 Recherche Hybride

| Fonctionnalité | MnemoLite | AgentMemory | Avantage |
|---|---|---|---|
| **Lexical search** | ✅ pg_trgm (trigram) | ✅ BM25 in-process | MnemoLite (pg_trgm plus robuste) |
| **Vector search** | ✅ pgvector HNSW (768D halfvec) | ✅ In-process vector index | MnemoLite (HNSW optimisé, halfvec 50% RAM) |
| **Graph search** | ✅ Recursive CTE PostgreSQL | ✅ In-process graph weights | Égal |
| **Fusion** | ✅ RRF (k=60, poids configurables) | ✅ RRF (k=60, poids dynamiques) | AgentMemory (poids dynamiques auto) |
| **BM25 reranking** | ✅ Post-search reranking | ❌ Non | **MnemoLite** |
| **Query understanding** | ✅ Service dédié | ❌ Non | **MnemoLite** |
| **Cascade cache** | ✅ L1 (100MB) + L2 Redis | ❌ Pas de cache | **MnemoLite** |
| **Fallback gracieux** | ✅ Circuit breakers | ✅ Vector/graph skip | Égal |

### 🤖 Orchestration Agent

| Fonctionnalité | MnemoLite | AgentMemory | Avantage |
|---|---|---|---|
| **Actions** | ❌ Non | ✅ Créer, mettre à jour, prioriser | **AgentMemory** |
| **Routines** | ❌ Non | ✅ Workflows figés instanciables | **AgentMemory** |
| **Signals** | ❌ Non | ✅ Messages inter-agents | **AgentMemory** |
| **Leases** | ❌ Non | ✅ Verrous exclusifs sur actions | **AgentMemory** |
| **Checkpoints** | ❌ Non | ✅ Gates externes (CI, approbation) | **AgentMemory** |
| **Sentinels** | ❌ Non | ✅ Conditions auto-unblock | **AgentMemory** |
| **Sketches** | ❌ Non | ✅ Graphes exploratoires éphémères | **AgentMemory** |
| **Crystals** | ❌ Non | ✅ Digestion compacte de chaînes d'actions | **AgentMemory** |
| **Mesh sync** | ❌ Non | ✅ Sync inter-instances | **AgentMemory** |
| **Frontier/Next** | ❌ Non | ✅ Prochaine action priorisée | **AgentMemory** |

> **Verdict** : AgentMemory a un **système d'orchestration agent complet** que MnemoLite n'a pas du tout.

### 📊 Observabilité & Opérations

| Fonctionnalité | MnemoLite | AgentMemory | Avantage |
|---|---|---|---|
| **Distributed tracing** | ✅ OpenTelemetry → OpenObserve | ❌ Non | **MnemoLite** |
| **Metrics** | ✅ Latence P50/P95/P99, throughput | ❌ Basique | **MnemoLite** |
| **Cache monitoring** | ✅ L1/L2 hit rates, memory, evictions | ❌ Non | **MnemoLite** |
| **Indexing errors** | ✅ Tracking, retry, status | ❌ Non | **MnemoLite** |
| **Health checks** | ✅ ping, DB, Redis, embedding | ✅ memory_diagnose, memory_heal | AgentMemory (auto-heal) |
| **Alerting** | ✅ Alert rules, monitoring | ❌ Non | **MnemoLite** |
| **Diagnostics auto** | ❌ Non | ✅ memory_diagnose + memory_heal | **AgentMemory** |

---

## 5. Analyse des Outils MCP

### MnemoLite — 33 Outils + 8 Ressources

#### Outils Mémoire (10)
| Outil | Description |
|-------|-------------|
| `write_memory` | Créer mémoire avec embedding |
| `update_memory` | Mise à jour partielle |
| `delete_memory` | Soft/hard delete avec elicitation |
| `search_memory` | Recherche vectorielle avec filtres |
| `read_memory` | Lecture complète par ID |
| `consolidate_memory` | Fusionner mémoires en résumé |
| `mark_consumed` | Marquer comme traité |
| `rate_memory` | Feedback outcome (helpful/unhelpful) |
| `get_system_snapshot` | Snapshot boot 4x plus rapide |
| `configure_decay` | Configurer decay par tag |

#### Outils Code (4)
| Outil | Description |
|-------|-------------|
| `search_code` | Recherche hybride lexical + vector + RRF |
| `index_project` | Indexation complète avec progress |
| `reindex_file` | Ré-indexer un fichier |
| `index_incremental` | Indexation incrémentale mtime-based |
| `index_markdown_workspace` | Indexation markdown spécialisée |

#### Outils Graphe (4)
| Outil | Description |
|-------|-------------|
| `get_graph_stats` | Statistiques graphe de code |
| `traverse_graph` | Traversée depuis un nœud |
| `find_path` | Plus court chemin BFS |
| `get_module_data` | Données détaillées d'un module |

#### Outils Indexing Observabilité (3)
| Outil | Description |
|-------|-------------|
| `get_indexing_status` | Statut d'indexation en cours |
| `get_indexing_errors` | Erreurs récentes d'indexation |
| `retry_indexing` | Ré-indexer fichiers en erreur |

#### Outils Analytics (4)
| Outil | Description |
|-------|-------------|
| `clear_cache` | Vider cache L1/L2 (avec elicitation) |
| `get_indexing_stats` | Stats d'indexation par repo |
| `get_memory_health` | Santé du système mémoire |
| `get_cache_stats` | Stats cache L1/L2 |

#### Outils Entités (2)
| Outil | Description |
|-------|-------------|
| `extract_entities` | Ré-extraction GLiNER |
| `search_by_entity` | Recherche par nom d'entité |

#### Outils Relations (2)
| Outil | Description |
|-------|-------------|
| `get_related_memories` | Mémoires liées sémantiquement |
| `get_memory_graph` | Graphe de relations pour visualisation |

#### Outils Consolidation (1)
| Outil | Description |
|-------|-------------|
| `suggest_consolidation` | Suggérer groupes de consolidation (TF-IDF) |

#### Outils Config (1)
| Outil | Description |
|-------|-------------|
| `switch_project` | Changer projet actif |

#### Outils Test (1)
| Outil | Description |
|-------|-------------|
| `ping` | Test connectivité |

#### Ressources MCP (8)
| Resource | Description |
|----------|-------------|
| `health://status` | Santé serveur |
| `memories://get/{id}` | Lecture mémoire par UUID |
| `memories://list` | Liste avec filtres |
| `memories://search/{query}` | Recherche sémantique |
| `graph://nodes/{chunk_id}` | Détails nœud graphe |
| `graph://callers/{name}` | Trouver appelants |
| `graph://callees/{name}` | Trouver appelés |
| `index://status/{repository}` | Statut d'indexation |
| `cache://stats` | Stats cache |
| `analytics://search` | Analytics recherche |
| `projects://list` | Liste projets indexés |
| `config://languages` | Langues supportées |

### AgentMemory — 43 Outils

#### Core Tools (10)
| Outil | Description |
|-------|-------------|
| `memory_recall` | Recherche observations de session |
| `memory_save` | Sauver insight/décision/pattern |
| `memory_file_history` | Historique observations par fichier |
| `memory_patterns` | Détection patterns récurrents |
| `memory_sessions` | Lister sessions récentes |
| `memory_smart_search` | Hybride avec progressive disclosure |
| `memory_timeline` | Observations chronologiques |
| `memory_profile` | Profil utilisateur/projet |
| `memory_export` | Export JSON |
| `memory_relations` | Graphe de relations |

#### V040 Tools (8)
| Outil | Description |
|-------|-------------|
| `memory_claude_bridge_sync` | Sync avec MEMORY.md de Claude Code |
| `memory_graph_query` | Requête knowledge graph |
| `memory_consolidate` | Pipeline consolidation 4-tier |
| `memory_team_share` | Partager avec équipe |
| `memory_team_feed` | Feed équipe |
| `memory_audit` | Trail d'audit |
| `memory_governance_delete` | Suppression avec audit |
| `memory_snapshot_create` | Snapshot git-versionné |

#### V050 Tools (10)
| Outil | Description |
|-------|-------------|
| `memory_action_create` | Créer action avec dépendances typées |
| `memory_action_update` | Mettre à jour action |
| `memory_frontier` | Actions débloquées par priorité |
| `memory_next` | Prochaine action la plus importante |
| `memory_lease` | Verrou exclusif sur action |
| `memory_routine_run` | Instancier routine |
| `memory_signal_send` | Message inter-agent |
| `memory_signal_read` | Lire messages |
| `memory_checkpoint` | Gate externe |
| `memory_mesh_sync` | Sync inter-instances |

#### V051 Tools (8)
| Outil | Description |
|-------|-------------|
| `memory_sentinel_create` | Condition auto-unblock |
| `memory_sentinel_trigger` | Déclencher sentinelle |
| `memory_sketch_create` | Graphe exploratoire éphémère |
| `memory_sketch_promote` | Promouvoir sketch en actions |
| `memory_crystallize` | Compresser chaîne d'actions |
| `memory_diagnose` | Diagnostics santé |
| `memory_heal` | Auto-réparation |
| `memory_facet_tag` | Tag structuré |
| `memory_facet_query` | Requête par facets AND/OR |

#### V061 Tools (1)
| Outil | Description |
|-------|-------------|
| `memory_verify` | Vérifier chaîne de citation |

#### V070 Tools (3)
| Outil | Description |
|-------|-------------|
| `memory_lesson_save` | Sauver leçon apprise |
| `memory_lesson_recall` | Rechercher leçons |
| `memory_obsidian_export` | Export Obsidian Markdown |

#### V073 Tools (2)
| Outil | Description |
|-------|-------------|
| `memory_reflect` | Synthétiser insights d'ordre supérieur |
| `memory_insight_list` | Lister insights synthétisés |

---

## 6. Avantages et Inconvénients

### MnemoLite — Avantages ✅

1. **Code Intelligence inégalée** — Tree-sitter, LSP, graphe de code, métriques, chunking sémantique
2. **Recherche hybride mature** — pg_trgm + pgvector HNSW + RRF + BM25 reranking + cache L1/L2
3. **Embeddings 100% locaux** — Aucune API payante, aucune fuite de données, souveraineté totale
4. **Decay temporel fin** — 11 presets configurables par tag + outcome feedback
5. **PostgreSQL-centric** — ACID, pgvector, pg_trgm, recursive CTE, pg_partman — un seul moteur
6. **Observabilité enterprise** — OpenTelemetry, OpenObserve, métriques P50/P95/P99
7. **Cache cascade** — L1 in-memory + L2 Redis, hit rates combinés
8. **Entity extraction local** — GLiNER zero-shot NER, pas d'API externe
9. **Consolidation TF-IDF** — Groupement intelligent avec inverse index et clustering
10. **Incremental indexing** — mtime-based, 50s vs 6.5h pour full reindex
11. **Outcome feedback** — rate_memory modifie le decay, les bonnes mémoires durent plus longtemps
12. **Dual embedding** — TEXT (nomic) vs CODE (jina), routing automatique
13. **System snapshot** — Boot agent 4x plus rapide que requêtes séquentielles
14. **Vue 3 SPA complète** — 13 pages, SCADA dashboard, monitoring temps réel
15. **1570+ tests** — Coverage extensive, pytest fixtures
16. **PrivacyService (EPIC-42)** ✅ — Secret stripping automatique (12 patterns), intégré dans write_memory / update_memory
17. **Worker Service** ✅ — Background jobs via Redis Streams (conversation import, batch indexing, entity extraction)
18. **Hooks Claude Code** ⚠️ — 2 hooks déployés (Stop + UserPromptSubmit), scripts deploy-hooks-to-project.sh

### MnemoLite — Inconvénients ❌

1. **Infrastructure lourde** — Docker Compose avec 8 conteneurs, PostgreSQL 18, Redis 7, OpenObserve
2. **Capture silencieuse partielle** — 2 hooks déployés (vs 12 chez AgentMemory), pas de session-start/pre-tool-use
3. ~~Pas de déduplication~~ ✅ **Jaccard dedup** — `dedup_check=True` par défaut dans write_memory, two-stage pg_trgm→Jaccard (0.9 threshold)
4. **RAM élevée** — 8-24 GB (modèles embedding + GLiNER + PostgreSQL)
5. **Installation complexe** — Docker Compose + variables d'environnement + seed DB
6. **Cold start lent** — GLiNER ~10s, embeddings ~50s au premier appel
7. **Pas d'orchestration agent** — Pas d'actions, routines, signals, leases, checkpoints
8. **Pas de team features** — Pas de partage, pas de feed, pas de mesh sync
9. ~~Pas d'export~~ ✅ JSON export — Export JSON natif (REST + MCP), pas d'Obsidian
10. **Pas d'audit trail** — Pas de traçabilité des opérations
11. **Pas de bridges agent** — Pas de sync avec MEMORY.md ou fichiers natifs agent
12. **Modèle cognitive limité** — 6 types + 4 lifecycle vs 4-tier + crystals + lessons

### AgentMemory — Avantages ✅

1. **Installation zéro infrastructure** — `npx @agentmemory/agentmemory`, SQLite in-process
2. **Capture silencieuse** — 12 hooks automatiques, aucun appel explicite nécessaire
3. **Privacy first** — Secret stripping automatique, tags `<private>`, regex complets
4. **Modèle cognitive riche** — 4-tier (Working → Episodic → Semantic → Procedural) + Crystals + Lessons
5. **Orchestration agent complète** — Actions, Routines, Signals, Leases, Checkpoints, Sentinels, Sketches
6. **Déduplication Jaccard** — Contra-détection (threshold 0.9), pas de doublons
7. **Team features** — Partage, feed, mesh sync inter-instances
8. **Export** — JSON + Obsidian Markdown natif
9. **Audit trail** — memory_audit + governance_delete
10. **Claude Bridge** — Sync bidirectionnel avec MEMORY.md natif Claude Code
11. **Git-versioned snapshots** — memory_snapshot_create
12. **Diagnostics auto** — memory_diagnose + memory_heal (auto-réparation)
13. **Reflect** — Synthèse d'insights d'ordre supérieur via knowledge graph
14. **Multi-provider embeddings** — OpenAI, Cohere, Gemini, Voyage, local/Xenova
15. **RAM minimale** — ~512 MB (tout in-process)
16. **Benchmarks publiés** — 95.2% R@5, ~92% token savings vs mem0/Letta

### AgentMemory — Inconvénients ❌

1. **Aucune Code Intelligence** — Pas d'AST, pas de chunking, pas de LSP, pas de graphe de code
2. **SQLite uniquement** — Pas de concurrency, pas d'ACID distribué, pas de partitionnement
3. **Pas de cache distribué** — In-process seulement, pas de Redis
4. **Embeddings = API payante** — Sauf Xenova local (moins performant)
5. **Pas d'observabilité** — Pas de traces, pas de métriques, pas de dashboards
6. **Pas d'entity extraction** — Pas de NER, pas de GLiNER, pas d'extraction structurée
7. **Pas d'outcome feedback** — Pas de rate_memory, pas de modulation de decay par résultat
8. **Consolidation basique** — Pas de TF-IDF, pas de clustering, pas de suggestion
9. **Pas de Vue SPA** — Viewer basique seulement
10. **Pas de circuit breakers** — Pas de protection contre pannes provider
11. **Pas de LSP integration** — Pas d'enrichissement de type
12. **Pas de graphe de code** — Pas de traversée, pas de métriques
13. **Sensibilité provider** — Dépend d'APIs externes (OpenAI, etc.) pour embeddings
14. **iii-engine dépendance** — Moteur externe non documenté

---

## 7. Idées et Inspirations

### 🔥 Idées Haute Priorité (emprunts AgentMemory → MnemoLite)

#### 1. ~~Secret Stripping automatique~~ ✅ FAIT (EPIC-42)
**Inspiration** : AgentMemory `stripPrivateData()`  
**Statut** : **Implémenté** dans `api/services/privacy_service.py` — 12 patterns regex, auto-détection + redaction, intégré dans `write_memory` / `update_memory`.  
**Patterns implémentés** :
- OpenAI keys (`sk-proj-*`, `sk-*`, `sk-ant-*`) ✅
- GitHub tokens (`ghp_*`, `github_pat_*`, `npm_*`) ✅
- AWS keys (`AKIA*`) ✅
- Bearer tokens ✅
- JWT patterns (`eyJ...`) ✅
- Generic `api-key:`, `secret:`, `password:` patterns ✅
- `<private>...</private>` tags — ❌ Pas encore implémenté (différence vs AgentMemory)  
**Effort réel** : ~4h  
**Impact** : Sécurité critique ✅

#### 2. Hooks automatiques Claude Code / Cursor ⚠️ PARTIEL
**Inspiration** : AgentMemory 12 hooks `.mjs`  
**Statut** : **2 hooks déployés** via scripts shell :
- `Stop/auto-save.sh` → Sauvegarde conversation à la fin de session ✅
- `UserPromptSubmit/auto-save-previous.sh` → Sauvegarde échange précédent ✅
- `deploy-hooks-to-project.sh` → Déploie les stub hooks dans un projet ✅

**Reste à implémenter** :
- `session-start` → `get_system_snapshot()` ❌
- `pre-tool-use` / `post-tool-use` → `write_memory()` pour observations ❌
- `session-end` → `consolidate_memory()` ❌
- `auto-consolidation` → Background périodique ❌  
**Effort restant** : ~6h  
**Impact** : Adoption massive — la mémoire devient invisible

#### 3. ~~Déduplication Jaccard~~ ✅ FAIT
**Inspiration** : AgentMemory auto-forget (contradiction detection)  
**Statut** : **Implémenté** — two-stage dedup dans `MemoryRepository.find_potential_duplicates()`:
- Stage 1: pg_trgm GIN index sur title (SQL, rapide)
- Stage 2: Jaccard similarity Python (title + content + combined, threshold 0.9)
- Intégré dans `write_memory` via `dedup_check=True` (défaut)
- Retourne `duplicate_warning` + `potential_duplicates` pour Jaccard ≥ 0.9
- Retourne `similar_memories` pour near-matches (0.7–0.9)
- Pure Python `utils/jaccard.py` (aucune dépendance SQLAlchemy)
- 24 tests unitaires  
**Effort réel** : ~4h  
**Impact** : Qualité des données mémoire ✅

#### 4. Claude Bridge Sync (MEMORY.md)
**Inspiration** : AgentMemory `memory_claude_bridge_sync`  
**Implémentation MnemoLite** : Sync bidirectionnel entre mémoires MnemoLite et MEMORY.md natif de Claude Code. Permet une lecture hors-ligne et une compatibilité avec le format natif.  
**Effort** : ~4h  
**Impact** : Compatibilité écosystème Claude Code

#### 5. ~~Export JSON~~ ✅ FAIT — Obsidian Markdown restant
**Inspiration** : AgentMemory `memory_export` + `memory_obsidian_export`

Export JSON implémenté : `GET /api/v1/memories/export` (REST téléchargeable) + outil MCP `export_memories(project_id?, include_deleted?)`. Export sans embedding, filtre par projet, enveloppe `mnemolite-memories-v1`.  
**Implémentation MnemoLite** : Ajouter endpoints d'export :
- `/api/memories/export?format=json` — Export complet
- `/api/memories/export?format=obsidian` — Markdown avec frontmatter  
**Effort** : ~3h  
**Impact** : Portabilité, backup, partage

### 💡 Idées Moyenne Priorité

#### 6. Diagnostics + Auto-Heal
**Inspiration** : AgentMemory `memory_diagnose` + `memory_heal`  
**Implémentation** : Health checks automatisés :
- Embeddings manquants → régénérer
- Relations orphelines → nettoyer
- Tags incohérents → corriger
- Decay stale → recalculer  
**Effort** : ~6h

#### 7. Audit Trail
**Inspiration** : AgentMemory `memory_audit` + `memory_governance_delete`  
**Implémentation** : Table `memory_audit_log` + endpoint `GET /api/memories/audit`  
**Effort** : ~4h

#### 8. Orchestration Agent basique
**Inspiration** : AgentMemory Actions + Routines  
**Implémentation** : Commencer par :
- `create_action(title, priority, dependencies)` — Créer action
- `get_next_action()` — Prochaine action priorisée
- `complete_action(id, outcome)` — Terminer avec résultat  
**Effort** : ~8h

#### 9. Git-Versioned Snapshots
**Inspiration** : AgentMemory `memory_snapshot_create`  
**Implémentation** : Export mémoire → git commit → historique versionné  
**Effort** : ~4h

#### 10. Reflect / Insight Synthesis
**Inspiration** : AgentMemory `memory_reflect` + `memory_insight_list`  
**Implémentation** : Service qui traverse le knowledge graph, groupe les mémoires liées, et synthétise des insights d'ordre supérieur via LLM.  
**Effort** : ~6h

### 🌟 Idées Basse Priorité / Long Terme

#### 11. Mesh Sync inter-instances
**Inspiration** : AgentMemory `memory_mesh_sync`  
**Pour MnemoLite** : Sync entre plusieurs instances MnemoLite (multi-projet, multi-équipe)

#### 12. Sentinels / Auto-triggers
**Inspiration** : AgentMemory sentinels  
**Pour MnemoLite** : Conditions surveillées qui déclenchent automatiquement des actions (ex: auto-consolidation quand count > threshold)

#### 13. Facet Tags (AND/OR queries)
**Inspiration** : AgentMemory `memory_facet_tag` + `memory_facet_query`  
**Pour MnemoLite** : Tags structurés avec requêtes booléennes

#### 14. Progressive Disclosure Search
**Inspiration** : AgentMemory `memory_smart_search`  
**Pour MnemoLite** : Retourner d'abord des résumés, puis contenu complet on-demand

#### 15. Multi-provider Embeddings
**Inspiration** : AgentMemory providers  
**Pour MnemoLite** : Fallback OpenAI/Cohere si modèles locaux indisponibles (avec opt-in pour privacy)

---

## 8. Recommandations Actionnables

### Phase 1 — Quick Wins (1-2 jours)

| # | Action | Effort | Impact | Fichier | Statut |
|---|--------|--------|--------|---------|--------|
| 1 | **Secret stripping** | 2h | 🔴 Critique | `api/services/privacy_service.py` + intégration write/update | ✅ **FAIT** (EPIC-42) |
| 2 | **Déduplication Jaccard** | 3h | 🟡 Important | `api/utils/jaccard.py` + `api/db/repositories/memory_repository.py` + `api/mnemo_mcp/tools/memory_tools.py` | ✅ **FAIT** (dedup_check) |
| 3 | **Export JSON** | 3h | 🟢 Utile | `api/routes/memories_routes.py` + `api/db/repositories/memory_repository.py` (export_memories) + MCP tool | ✅ **FAIT** (JSON only, pas Obsidian) |

### Phase 2 — Adoption (3-5 jours)

| # | Action | Effort | Impact | Fichier | Statut |
|---|--------|--------|--------|---------|--------|
| 4 | **Hooks Claude Code** | 4h→6h restant | 🔴 Critique | `scripts/hooks/` + `scripts/deploy-hooks-to-project.sh` | ⚠️ **PARTIEL** (2/12 hooks) |
| 5 | **Claude Bridge Sync** | 4h | 🟡 Important | `api/services/claude_bridge_service.py` (nouveau) | ❌ À faire |
| 6 | **Audit Trail** | 4h | 🟡 Important | `api/db/repositories/audit_repository.py` + migration | ❌ À faire |
| 7 | **Diagnostics + Auto-Heal** | 6h | 🟢 Utile | `api/services/memory_health_service.py` (nouveau) | ❌ À faire |

### Phase 3 — Enrichissement (1-2 semaines)

| # | Action | Effort | Impact | Fichier | Statut |
|---|--------|--------|--------|---------|--------|
| 8 | **Orchestration Agent basique** | 8h | 🟡 Important | `api/models/action_models.py` + `api/services/action_service.py` | ❌ À faire |
| 9 | **Reflect / Insight Synthesis** | 6h | 🟢 Utile | `api/services/insight_service.py` (nouveau) | ❌ À faire |
| 10 | **Git-Versioned Snapshots** | 4h | 🟢 Utile | `api/services/snapshot_service.py` (nouveau) | ❌ À faire |

---

## 9. Matrice de Décision

### Scores par Domaine (1-5 ⭐)

| Domaine | MnemoLite | AgentMemory |
|---------|-----------|-------------|
| **Code Intelligence** | ⭐⭐⭐⭐⭐ | ⭐ |
| **Recherche Hybride** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Mémoire Sémantique** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Capture Automatique** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Privacy/Sécurité** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐½ |
| **Orchestration Agent** | ⭐ | ⭐⭐⭐⭐⭐ |
| **Observabilité** | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| **Simplicité installation** | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Enterprise-readiness** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Extensibilité** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Documentation** | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Tests** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

### Synthèse

| Catégorie | Gagnant | Raison |
|-----------|---------|--------|
| **Code Intelligence** | **MnemoLite** | AgentMemory n'a rien de tout ça |
| **Recherche Hybride** | **MnemoLite** | pg_trgm + HNSW + RRF + BM25 + cache |
| **Mémoire Sémantique** | **Tie** | MnemoLite : decay fin, outcome, entities ; AgentMemory : 4-tier, capture, privacy |
| **Capture Automatique** | **AgentMemory** | 12 hooks vs 2 hooks (MnemoLite en progrès) |
| **Privacy** | **AgentMemory** (léger) | MnemoLite : PrivacyService (EPIC-42) ✅ ; AgentMemory : stripPrivateData + `<private>` tags (avantage : tags `<private>`)
| **Orchestration Agent** | **AgentMemory** | Actions, routines, signals, leases |
| **Observabilité** | **MnemoLite** | OpenTelemetry + OpenObserve + dashboards |
| **Installation** | **AgentMemory** | `npx` vs Docker Compose 8 conteneurs |
| **Enterprise** | **MnemoLite** | PostgreSQL, Redis, ACID, partitioning, 1570+ tests |

---

## 10. Conclusion

MnemoLite et AgentMemory sont **complémentaires, pas concurrents**. Ils visent des besoins différents :

- **MnemoLite** est un **serveur d'intelligence de code** avec mémoire sémantique — son cœur est la compréhension du code (AST, LSP, graphe, métriques).
- **AgentMemory** est un **système cognitif agent** avec capture silencieuse — son cœur est l'automatisation de la mémoire (hooks, 4-tier, orchestration, privacy).

**L'idéal serait un hybride** combinant :
- La **Code Intelligence** de MnemoLite (AST, LSP, graphe, chunking, dual embedding)
- La **Capture silencieuse + Dédup** d'AgentMemory (hooks, Jaccard) — Privacy et Dédup désormais couverts par les deux
- La **Recherche hybride** des deux (triple-stream + RRF + cache cascade)
- L'**Orchestration agent** d'AgentMemory (actions, routines, signals)
- L'**Observabilité** de MnemoLite (OpenTelemetry, dashboards, métriques)

### Progrès depuis avril 2025

| Recommandation | Statut | Détail |
|---------------|--------|-------|
| Phase 1 #1 : Secret stripping | ✅ **FAIT** | PrivacyService (EPIC-42), 12 patterns, intégré write/update |
| Phase 1 #2 : Déduplication Jaccard | ✅ **FAIT** | utils/jaccard.py + find_potential_duplicates() + dedup_check=True, 24 tests |
| Phase 2 #4 : Hooks Claude Code | ⚠️ **PARTIEL** | 2/12 hooks (Stop + UserPromptSubmit), deploy-scripts |
| GLiNER Entity Extraction | ✅ **FAIT** | Nouveau feature non listée dans le rapport initial |
| Outcome Feedback (rate_memory) | ✅ **FAIT** | Nouveau feature non listée dans le rapport initial |
| Worker Service (Redis Streams) | ✅ **FAIT** | Nouveau feature non listée dans le rapport initial |

### Prochaine étape recommandée

Implémenter les **Quick Wins restants de Phase 1** (déduplication Jaccard + export JSON/Obsidian) puis compléter les **Hooks Claude Code** de Phase 2 (10 hooks restants) pour atteindre la capture silencieuse complète.

---


*Fin du rapport — Généré le 13 avril 2025 — Mis à jour le juin 2025*
