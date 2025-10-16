# EPIC-06: Roadmap Visuelle - Code Intelligence

**Version**: 1.2.0
**Date**: 2025-10-16 (Updated: Phase 0 COMPLETE)
**Durée totale**: 13 semaines (3 mois)
**Story Points**: 74 points

---

## 🗺️ Vue d'Ensemble Chronologique

```
┌─────────────────────────────────────────────────────────────────┐
│                    EPIC-06 Timeline (13 semaines)               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Semaine 1                                                      │
│  ┌──────────────────────────────────────────────┐              │
│  │ PHASE 0: Infrastructure Setup (8 pts)        │              │
│  │ • Story 0.1: Alembic Async (3 pts)          │              │
│  │ • Story 0.2: Dual Embeddings (5 pts)        │              │
│  └──────────────────────────────────────────────┘              │
│                                                                 │
│  Semaines 2-5                                                   │
│  ┌──────────────────────────────────────────────┐              │
│  │ PHASE 1: Foundation Code (31 pts)            │              │
│  │ • Story 1: Tree-sitter Chunking (13 pts)    │ S2-3         │
│  │ • Story 2: Dual Embeddings Int. (5 pts)     │ S4           │
│  │ • Story 2bis: code_chunks Table (5 pts)     │ S4           │
│  │ • Story 3: Metadata Extraction (8 pts)      │ S5           │
│  └──────────────────────────────────────────────┘              │
│                                                                 │
│  Semaines 6-8                                                   │
│  ┌──────────────────────────────────────────────┐              │
│  │ PHASE 2: Graph Intelligence (13 pts)         │              │
│  │ • Story 4: Dependency Graph (13 pts)         │ S6-8         │
│  └──────────────────────────────────────────────┘              │
│                                                                 │
│  Semaines 9-11                                                  │
│  ┌──────────────────────────────────────────────┐              │
│  │ PHASE 3: Hybrid Search (21 pts)              │              │
│  │ • Story 5: pg_trgm + Vector + RRF (21 pts)  │ S9-11        │
│  └──────────────────────────────────────────────┘              │
│                                                                 │
│  Semaines 12-13                                                 │
│  ┌──────────────────────────────────────────────┐              │
│  │ PHASE 4: API & Integration (13 pts)          │              │
│  │ • Story 6: Indexing Pipeline (13 pts)       │ S12-13       │
│  └──────────────────────────────────────────────┘              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 Breakdown par Phase

### Phase 0: Infrastructure (Semaine 1) - ✅ COMPLETE
```
┌─────────────────────────────────────┐
│ Story 0.1: Alembic Async (3 pts)   │  ██████████ 100% ✅ COMPLETE
│ Story 0.2: Dual Embeddings (5 pts) │  ██████████ 100% ✅ COMPLETE
└─────────────────────────────────────┘
Total: 8/8 pts | Progression: 100% ✅
```

**Livrables Story 0.1** (2025-10-15 - ✅ COMPLETE):
- ✅ Alembic 1.17.0 installé avec template async
- ✅ `workers/config/settings.py` migré Pydantic v2 avec dual embeddings
- ✅ `api/alembic/env.py` configuré (psycopg2 sync + NullPool)
- ✅ Baseline NO-OP migration créée (9dde1f9db172)
- ✅ Database stamped, `alembic_version` table opérationnelle
- ✅ Smoke tests passés (API + DB + Settings)
- ✅ Documentation: `EPIC-06_PHASE_0_STORY_0.1_REPORT.md`

**Livrables Story 0.2** (2025-10-16 - ✅ COMPLETE):
- ✅ `DualEmbeddingService` créé (EmbeddingDomain: TEXT | CODE | HYBRID)
- ✅ Lazy loading avec double-checked locking (thread-safe)
- ✅ RAM safeguard (bloque CODE model si > 900 MB)
- ✅ Backward compatibility 100% (Adapter pattern)
- ✅ 24 unit tests + 19 regression tests passent
- ⚠️ RAM réelle: 1.25 GB TEXT model (vs 260 MB estimé) - stakeholder approved
- ✅ Audit complet: Score 9.4/10 - Production Ready
- ✅ Documentation: `EPIC-06_PHASE_0_STORY_0.2_REPORT.md` + `EPIC-06_PHASE_0_STORY_0.2_AUDIT_REPORT.md`

**Critical Findings Story 0.2**:
- 🐛 Bug #1 Fixed: Empty HYBRID domain retournait mauvais format
- 🐛 Bug #2 Fixed: Deprecated `asyncio.get_event_loop()` → `get_running_loop()`
- 📊 RAM Process = 3-5× model weights (lesson learned pour estimations futures)

---

### Phase 1: Foundation Code (Semaines 2-5)
```
┌─────────────────────────────────────────┐
│ Story 1: Tree-sitter Chunking (13 pts) │  ████████████░ 42%
│ Story 2: Dual Emb. Int. (5 pts)        │  ████░░░░░░░░░ 16%
│ Story 2bis: code_chunks Table (5 pts)  │  ████░░░░░░░░░ 16%
│ Story 3: Metadata Extract. (8 pts)     │  ███████░░░░░░ 26%
└─────────────────────────────────────────┘
Total: 31 pts | Durée: 4 semaines
```

**Livrables**:
- ✅ Chunking sémantique via AST (Python, JS, TS, Go, Rust, Java)
- ✅ Table `code_chunks` créée avec dual embeddings
- ✅ Metadata extraction (complexity, docstrings, imports, calls)
- ✅ Repository pattern `CodeChunkRepository`

---

### Phase 2: Graph Intelligence (Semaines 6-8)
```
┌────────────────────────────────────────┐
│ Story 4: Dependency Graph (13 pts)    │  ██████████████ 100%
└────────────────────────────────────────┘
Total: 13 pts | Durée: 3 semaines
```

**Livrables**:
- ✅ Call graph extraction (Python AST)
- ✅ Import graph
- ✅ CTE récursifs (≤3 hops)
- ✅ API `/v1/code/graph`

---

### Phase 3: Hybrid Search (Semaines 9-11)
```
┌────────────────────────────────────────────┐
│ Story 5: Hybrid Search (21 pts)           │  ██████████████ 100%
│  • pg_trgm similarity (lexical)           │
│  • pgvector HNSW (semantic)               │
│  • RRF fusion (k=60)                      │
│  • Graph expansion (optional)             │
└────────────────────────────────────────────┘
Total: 21 pts | Durée: 3 semaines
```

**Livrables**:
- ✅ pg_trgm search opérationnel
- ✅ Vector search via HNSW
- ✅ RRF fusion (Reciprocal Rank Fusion)
- ✅ Graph expansion optionnel (depth 0-3)
- ✅ API `/v1/code/search`

---

### Phase 4: API & Integration (Semaines 12-13)
```
┌────────────────────────────────────────┐
│ Story 6: Indexing Pipeline (13 pts)   │  ██████████████ 100%
│  • Code indexing service               │
│  • Batch processing                    │
│  • API /v1/code/index                  │
│  • Documentation OpenAPI               │
└────────────────────────────────────────┘
Total: 13 pts | Durée: 2 semaines
```

**Livrables**:
- ✅ Pipeline complet (detect → parse → chunk → metadata → graph → embed → store)
- ✅ Endpoint `/v1/code/index`
- ✅ Batch indexing (~100 fichiers)
- ✅ Documentation OpenAPI complète
- ✅ UI v4.0 integration

---

## 🎯 Jalons (Milestones)

```
M0: Infrastructure Ready (Fin Semaine 1)
├─ Alembic async configuré
├─ Dual embeddings opérationnels
└─ Tests infrastructure passent

M1: Code Indexing Ready (Fin Semaine 5)
├─ Chunking sémantique fonctionne
├─ Table code_chunks créée
├─ Metadata extraction opérationnelle
└─ Tests foundation passent

M2: Graph Analysis Ready (Fin Semaine 8)
├─ Call graph extraction
├─ API graph opérationnelle
└─ Tests graph passent

M3: Search Ready (Fin Semaine 11)
├─ Hybrid search opérationnel
├─ API search fonctionnelle
└─ Benchmarks validés

M4: EPIC-06 Complete (Fin Semaine 13)
├─ Pipeline indexing complet
├─ Documentation complète
├─ Tests end-to-end passent
└─ UI v4.0 intégrée
```

---

## 📈 Métriques de Progression

### Story Points Velocity

| Semaine | Phase | Points Planifiés | Points Cumulés | % Complet | Statut |
|---------|-------|------------------|----------------|-----------|---------|
| S1      | Phase 0 | 8 (0.1+0.2)    | 8/74           | 10.8%     | ✅ Story 0.1 (3 pts) COMPLETE<br>✅ Story 0.2 (5 pts) COMPLETE<br>⏳ Phase 1 READY |
| S2-3    | Phase 1 | 13 (Story 1)   | 21/74          | 28%       | ⏳ NEXT |
| S4      | Phase 1 | 10 (S2+S2bis)  | 31/74          | 42%       |  |
| S5      | Phase 1 | 8 (Story 3)    | 39/74          | 53%       |  |
| S6-8    | Phase 2 | 13 (Story 4)   | 52/74          | 70%       |  |
| S9-11   | Phase 3 | 21 (Story 5)   | 73/74          | 99%       |  |
| S12-13  | Phase 4 | 13 (Story 6)   | 86/74          | 116%*     |  |

*116% = 74 pts planifiés + 12 pts buffer (contingence restante après Phase 0 ahead of schedule)

---

## 🔄 Dépendances entre Stories

```
Story 0.1 (Alembic)
    │
    ├──> Story 2bis (Table code_chunks)
    │        │
    │        ├──> Story 4 (Graph - needs code_chunks)
    │        │        │
    │        │        └──> Story 5 (Hybrid Search - needs graph)
    │        │                 │
    │        │                 └──> Story 6 (API - needs search)
    │        │
    │        └──> Story 3 (Metadata - reads code_chunks)
    │
    └──> Story 0.2 (Dual Embeddings)
             │
             ├──> Story 1 (Chunking - uses embeddings indirectly)
             │        │
             │        └──> Story 3 (Metadata - needs chunking)
             │
             └──> Story 2 (Dual Emb. Integration - validates Phase 0)
```

**Chemin critique**: Phase 0 → Story 1 → Story 2bis → Story 4 → Story 5 → Story 6

---

## ⚠️ Points de Décision Clés

### Décision 1: pg_trgm vs BM25 (Phase 3, Semaine 9)

**Options**:
- A) Utiliser pg_trgm similarity (natif PostgreSQL)
- B) Installer extension pg_search (BM25 vrai)
- C) Développer BM25 custom

**Recommandation**: **Option A** (pg_trgm)
- ✅ Natif PostgreSQL
- ✅ Pas de dépendances externes
- ✅ Performance correcte
- ⚠️ Pas de vrai BM25 (mais acceptable pour v1.4.0)

**Validation**: Benchmark qualité search après Phase 3. Si insuffisant, évaluer pg_search pour v1.5.0.

---

### Décision 2: Graph Depth Limit (Phase 2, Semaine 6)

**Question**: Quelle profondeur maximale pour graph traversal?

**Options**:
- A) depth ≤ 2 (conservatif, rapide)
- B) depth ≤ 3 (recommandé)
- C) depth ≤ 5 (flexible, risque performance)

**Recommandation**: **Option B** (depth ≤ 3)
- ✅ Équilibre performance/utilité
- ✅ CTE récursifs efficaces
- ✅ Cas d'usage couverts (call chain, import dependencies)

**Validation**: Benchmark latency P95 <20ms avec depth=3 sur codebase ~500 functions.

---

### Décision 3: Metadata Extraction Languages (Phase 1, Semaine 5)

**Question**: Quels langages supporter pour metadata extraction?

**Priorité 1 (Must-have)**:
- Python (radon + ast)

**Priorité 2 (Should-have)**:
- JavaScript / TypeScript (via tree-sitter queries)

**Priorité 3 (Nice-to-have)**:
- Go, Rust, Java (via tree-sitter queries)

**Recommandation**: Implémenter Python (P1) en Phase 1, JS/TS (P2) si temps restant, Go/Rust/Java (P3) en v1.5.0.

---

## 🚨 Risques Majeurs & Plans d'Urgence

### Risque 1: Tree-sitter Parsing Failures
**Probabilité**: Moyenne | **Impact**: Haut

**Symptômes**:
- Parsing échoue sur >20% fichiers réels
- Performance <100ms non atteinte
- Langages non supportés

**Plan d'urgence**:
1. Activer fallback chunking fixe automatiquement
2. Logger fichiers problématiques pour debug
3. Réduire langages supportés (Python only si critique)
4. Reporter multi-langages à v1.5.0

---

### Risque 2: RAM Overflow Dual Embeddings
**Probabilité**: Faible | **Impact**: Moyen

**Symptômes**:
- RAM total > 1 GB
- OOM errors sur CPU modestes
- Latence embedding >200ms

**Plan d'urgence**:
1. Activer quantization FP16 (sentence-transformers)
2. Lazy loading (charger modèles à la demande)
3. Réduire batch size (32 → 16)
4. Fallback: désactiver dual embeddings, utiliser nomic-text uniquement

---

### Risque 3: pg_trgm Insufficient Quality
**Probabilité**: Moyenne | **Impact**: Moyen

**Symptômes**:
- Recall hybrid search <70%
- Precision dégradée vs vector-only
- Users reports "search misses obvious code"

**Plan d'urgence**:
1. Augmenter weight vector search dans RRF fusion
2. Évaluer installation pg_search extension (BM25 vrai)
3. Fallback: désactiver pg_trgm, vector-only search
4. Documentation: encourager queries sémantiques vs lexicales

---

## ✅ Checklist Go-Live (Fin Semaine 13)

### Infrastructure
- [x] PostgreSQL 18 + pgvector 0.8.1 opérationnels ✅ (Phase 0 Story 0.1)
- [x] Alembic 1.17.0 installé et configuré ✅ (Phase 0 Story 0.1)
- [x] Baseline migration créée et stampée ✅ (Phase 0 Story 0.1)
- [x] DualEmbeddingService opérationnel ✅ (Phase 0 Story 0.2)
- [x] Lazy loading + RAM safeguard actifs ✅ (Phase 0 Story 0.2)
- [x] Backward compatibility 100% validée ✅ (Phase 0 Story 0.2)
- [ ] Table code_chunks créée (main + test DB) (Story 2bis)
- [ ] Index HNSW opérationnels (EXPLAIN ANALYZE validé) (Story 2bis)
- [ ] pg_trgm extension installée (Story 5)

### Code Quality
- [ ] Tests coverage >85% (tous nouveaux modules)
- [ ] Linters passent (ruff, mypy)
- [ ] Pre-commit hooks configurés
- [ ] CI/CD pipeline green

### API
- [ ] Endpoint `/v1/code/index` documenté (OpenAPI)
- [ ] Endpoint `/v1/code/search` documenté (OpenAPI)
- [ ] Endpoint `/v1/code/graph` documenté (OpenAPI)
- [ ] Backward compatibility validée (API v1 events intacte)
- [ ] Rate limiting configuré

### Performance
- [ ] Indexing <500ms/file (300 LOC) - P95 validé
- [ ] Search hybrid <50ms - P95 validé (10k chunks)
- [ ] Graph traversal <20ms (depth=2) - P95 validé

### Documentation
- [ ] README section Code Intelligence
- [ ] ADRs rédigées (tree-sitter, jina-code, pg_trgm)
- [ ] Guide utilisateur: comment indexer codebase
- [ ] API docs OpenAPI publiées
- [ ] CHANGELOG.md mis à jour

### UI
- [ ] Page Code Search intégrée (UI v4.0)
- [ ] Page Graph Visualization intégrée
- [ ] Tests E2E UI passent

---

## 🎉 Deliverables Finaux

À la fin de l'EPIC-06 (Semaine 13), MnemoLite v1.4.0 disposera de:

### Fonctionnalités
✅ **Code Indexing**: Pipeline complet (6+ langages)
✅ **Semantic Chunking**: AST-based (tree-sitter)
✅ **Dual Embeddings**: Text (nomic-embed-text-v1.5, 137M, 768D) + Code (jina-embeddings-v2-base-code, 161M, 768D)
✅ **Metadata Extraction**: Complexity, docstrings, imports, calls
✅ **Dependency Graph**: Call graph, import graph (≤3 hops)
✅ **Hybrid Search**: pg_trgm + pgvector 0.8.1 + RRF fusion
✅ **Graph Expansion**: Optionnel (enrich search results)

### API Endpoints
✅ `POST /v1/code/index` - Index codebase
✅ `GET /v1/code/search` - Hybrid code search
✅ `GET /v1/code/graph` - Navigate call graph

### Architecture
✅ **Tables séparées**: `events` (agent memory) + `code_chunks` (code intelligence)
✅ **Dual embeddings**: ~700 MB RAM total
✅ **768D everywhere**: Pas de migration DB
✅ **Backward compatible**: API v1 intacte

### Performance
✅ **Indexing**: <500ms/file (P95)
✅ **Search**: <50ms (P95, 10k chunks)
✅ **Graph**: <20ms (P95, depth=2)

---

**Date**: 2025-10-16
**Version**: 1.2.0 (Updated post-Story 0.2 + Audit)
**Statut**: ✅ **PHASE 0 COMPLETE (100%)** - Phase 1 READY

**Progrès Global**: 8/74 story points (10.8%) | 2/8 stories complètes

**Dernière Complétion**: Story 0.2 - Dual Embeddings Service (2025-10-16)
- DualEmbeddingService créé (450 lines, EmbeddingDomain enum)
- Lazy loading + RAM safeguard + backward compatibility
- Audit complet: Score 9.4/10 - Production Ready
- 2 bugs critiques corrigés (empty HYBRID, deprecated API)
- Documentation:
  - `EPIC-06_PHASE_0_STORY_0.2_REPORT.md`
  - `EPIC-06_PHASE_0_STORY_0.2_AUDIT_REPORT.md`

**Prochaine Action**: Kickoff Phase 1 Story 1 (Tree-sitter Integration) - 5 jours (13 pts)

**Achievements Phase 0**:
✅ 3 jours (vs 5 jours estimés) - **AHEAD OF SCHEDULE**
✅ 0 breaking changes API
✅ Infrastructure robuste et testée
✅ RAM safeguard prevents OOM
