# EPIC-06: Roadmap Visuelle - Code Intelligence

**Version**: 1.0.0
**Date**: 2025-10-15
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

### Phase 0: Infrastructure (Semaine 1)
```
┌─────────────────────────────────────┐
│ Story 0.1: Alembic Async (3 pts)   │  ████░░░░░ 33%
│ Story 0.2: Dual Embeddings (5 pts) │  ████████░ 67%
└─────────────────────────────────────┘
Total: 8 pts | Durée: 1 semaine
```

**Livrables**:
- ✅ Alembic configuré avec template async
- ✅ Dual embeddings (nomic-embed-text-v1.5 + jina-embeddings-v2-base-code) opérationnels
- ✅ RAM < 1 GB validé (~700 MB total)
- ✅ Tests infrastructure passent

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

| Semaine | Phase | Points Planifiés | Points Cumulés | % Complet |
|---------|-------|------------------|----------------|-----------|
| S1      | Phase 0 | 8              | 8/74           | 11%       |
| S2-3    | Phase 1 | 13 (Story 1)   | 21/74          | 28%       |
| S4      | Phase 1 | 10 (S2+S2bis)  | 31/74          | 42%       |
| S5      | Phase 1 | 8 (Story 3)    | 39/74          | 53%       |
| S6-8    | Phase 2 | 13 (Story 4)   | 52/74          | 70%       |
| S9-11   | Phase 3 | 21 (Story 5)   | 73/74          | 99%       |
| S12-13  | Phase 4 | 13 (Story 6)   | 86/74          | 116%*     |

*116% = 74 pts planifiés + 12 pts buffer (contingence)

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
- [ ] PostgreSQL 18 + pgvector 0.8.1 opérationnels
- [ ] Migration Alembic testée (upgrade + downgrade)
- [ ] Table code_chunks créée (main + test DB)
- [ ] Index HNSW opérationnels (EXPLAIN ANALYZE validé)
- [ ] pg_trgm extension installée
- [ ] Dual embeddings (nomic-embed-text-v1.5 + jina-embeddings-v2-base-code) chargés
- [ ] RAM usage < 1 GB validé (monitoring actif, target ~700 MB)

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

**Date**: 2025-10-15
**Version**: 1.0.0
**Statut**: ✅ ROADMAP VALIDÉE

**Prochaine Action**: Kickoff Phase 0 Story 0.1 (Alembic Async Setup) - Semaine 1
