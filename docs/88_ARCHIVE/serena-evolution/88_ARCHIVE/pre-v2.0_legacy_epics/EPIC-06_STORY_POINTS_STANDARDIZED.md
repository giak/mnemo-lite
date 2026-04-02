# EPIC-06: Story Points Standardisés

**Date**: 2025-10-16
**Status**: ✅ **FINAL** - À appliquer dans tous documents
**Authority**: Documentation Audit Complet + ADR-017

---

## 📊 Story Points Définitifs

### Phase 0: Infrastructure (8 pts - 100% COMPLETE)

| Story | Points | Status | Date | Rationale |
|-------|--------|--------|------|-----------|
| Story 0.1: Alembic Async Setup | **3 pts** | ✅ COMPLETE | 2025-10-15 | Setup infrastructure, Pydantic v2 migration |
| Story 0.2: Dual Embeddings Service | **5 pts** | ✅ COMPLETE | 2025-10-16 | DualEmbeddingService, EmbeddingDomain, RAM safeguard, Audit 9.4/10 |
| **TOTAL PHASE 0** | **8 pts** | **✅ 100%** | - | - |

**Note**: Story 0.2 = Story 2 originale (voir ADR-017)

---

### Phase 1: Foundation (26 pts - 100% COMPLETE)

| Story | Points | Status | Date | Rationale |
|-------|--------|--------|------|-----------|
| Story 1: Tree-sitter Integration & AST Chunking | **13 pts** | ✅ COMPLETE | 2025-10-16 | Tree-sitter setup, PythonParser, split-then-merge algorithm, 390 lignes service, 9/10 tests |
| ~~Story 2: Dual Embeddings~~ | ~~5 pts~~ | **MOVED TO PHASE 0** | - | **Fusionnée avec Story 0.2** (ADR-017) |
| Story 2bis: Code Chunks Table & Repository | **5 pts** | ✅ COMPLETE | 2025-10-16 | DB migration, code_chunks table, 431 lignes repository, CRUD + search, 10/10 tests, 1 jour |
| Story 3: Code Metadata Extraction | **8 pts** | ✅ COMPLETE | 2025-10-16 | MetadataExtractorService 359 lignes, 9 metadata fields, O(n²) fix (CRITICAL!), 34/34 tests, 655 lignes validation scripts, Audit 9.2/10, 1.5 jours |
| **TOTAL PHASE 1** | **26 pts** | **✅ 100%** | - | 13+5+8 = 26 |

---

### Phase 2: Graph Intelligence (13 pts - 0% COMPLETE)

| Story | Points | Status | Date | Rationale |
|-------|--------|--------|------|-----------|
| Story 4: Dependency Graph Construction | **13 pts** | 🟡 BRAINSTORM | 2025-10-16 | Call graph + import graph, nodes/edges storage, CTE récursifs, API endpoints. **Brainstorm complete**, implementation pending |
| **TOTAL PHASE 2** | **13 pts** | **🟡 0%** | - | Brainstorm ≠ implementation |

---

### Phase 3: Hybrid Search (21 pts - 0% COMPLETE)

| Story | Points | Status | Date | Rationale |
|-------|--------|--------|------|-----------|
| Story 5: Hybrid Search (BM25 + Vector + Graph) | **21 pts** | ⏳ NOT STARTED | - | pg_trgm + pgvector + RRF fusion + graph expansion |
| **TOTAL PHASE 3** | **21 pts** | **⏳ 0%** | - | - |

---

### Phase 4: API & Integration (13 pts - 0% COMPLETE)

| Story | Points | Status | Date | Rationale |
|-------|--------|--------|------|-----------|
| Story 6: Code Indexing Pipeline & API | **13 pts** | ⏳ NOT STARTED | - | Full indexing pipeline, batch processing, API endpoints |
| **TOTAL PHASE 4** | **13 pts** | **⏳ 0%** | - | - |

---

## 📈 Progrès Global

| Phase | Story Points | Status | % Complete |
|-------|--------------|--------|------------|
| **Phase 0** | **8 / 8** | ✅ COMPLETE | **100%** |
| **Phase 1** | **26 / 26** | ✅ COMPLETE | **100%** |
| **Phase 2** | **0 / 13** | 🟡 BRAINSTORM | **0%** |
| **Phase 3** | **0 / 21** | ⏳ NOT STARTED | **0%** |
| **Phase 4** | **0 / 13** | ⏳ NOT STARTED | **0%** |
| **TOTAL EPIC-06** | **34 / 81** | 🚧 IN PROGRESS | **42.0%** |

**Note**: Total epic = 8+26+13+21+13 = **81 pts** (NOT 74 pts comme mentionné dans docs anciens)

**⚠️ CORRECTION**: Si total epic reste 74 pts, alors il manque story points quelque part. À vérifier!

**Calcul alternatif si total = 74 pts**:
- 34 pts complétés / 74 pts total = **45.9% complete**

---

## 🎯 Stories Complètes

**Count**: **5 stories sur 8** (62.5%)

1. ✅ Story 0.1: Alembic Async Setup
2. ✅ Story 0.2: Dual Embeddings Service (= Story 2 originale)
3. ✅ Story 1: Tree-sitter Integration & AST Chunking
4. ✅ Story 2bis: Code Chunks Table & Repository
5. ✅ Story 3: Code Metadata Extraction
6. 🟡 Story 4: Dependency Graph Construction (brainstorm only)
7. ⏳ Story 5: Hybrid Search
8. ⏳ Story 6: Code Indexing Pipeline

---

## 📋 Justifications Détaillées

### Pourquoi Story 2bis = 5 pts?

**Complexity**: MOYENNE
- DB schema design (4 types indexes)
- Repository pattern (431 lignes)
- Dual embeddings support
- Vector + trigram search
- **Temps réel**: 1 jour
- **Tests**: 10/10 tests

**Comparaison**:
- Plus complexe que Story 0.1 (3 pts - setup infra)
- Moins complexe que Story 3 (8 pts - métadonnées + O(n²))

---

### Pourquoi Story 3 = 8 pts?

**Complexity**: HAUTE
- Python AST parsing (stdlib)
- Radon library integration
- 9 metadata fields extraction
- MetadataExtractorService 359 lignes
- **O(n²) → O(n) optimization** (CRITICAL ISSUE!)
  - Root cause analysis
  - Pre-extraction strategy
  - 5x performance improvement
- **Comprehensive validation**:
  - 15 unit tests
  - 19 integration tests
  - 12 edge cases validation
  - 3 validation scripts (655 lignes total)
- **Audit complet**: Score 9.2/10, rapport 600+ lignes
- **Temps réel**: 1.5 jours (dev + audit)

**Comparaison**:
- Plus complexe que Story 2bis (5 pts)
- Moins complexe que Story 1 (13 pts - tree-sitter multi-language)

---

### Pourquoi Story 1 = 13 pts?

**Complexity**: TRÈS HAUTE
- Tree-sitter setup (C bindings Python)
- Multi-language parsers (Python, JS, TS, Go, Rust, Java)
- AST traversal + queries
- Split-then-merge algorithm (inspired by cAST paper)
- Fallback chunking
- CodeChunkingService 390 lignes
- Pydantic models (CodeChunk, CodeUnit, ChunkType)
- **Tests**: 10 tests (9 passing + 1 xfail expected)
- **Estimated**: 10-13 jours
- **Temps réel**: 1 jour (AHEAD!)

---

### Pourquoi Story 0.2 = 5 pts?

**Complexity**: MOYENNE-HAUTE
- DualEmbeddingService design
- EmbeddingDomain enum (TEXT | CODE | HYBRID)
- Lazy loading + double-checked locking (thread-safe)
- RAM safeguard (prevent OOM)
- Adapter pattern (backward compat)
- **Tests**: 24 unit + 19 regression
- **Audit**: 9.4/10
- **Critical bugs fixed**: 2 (empty HYBRID, deprecated asyncio API)
- **RAM Discovery**: 3-5× multiplier lesson learned
- **Temps réel**: 1 jour (vs 3 estimés)

---

## 🔄 Application dans Documentation

Ces valeurs DOIVENT être appliquées dans:

1. ✅ `EPIC-06_STORY_POINTS_STANDARDIZED.md` (CE DOCUMENT)
2. ⏳ `EPIC-06_Code_Intelligence.md` (toutes sections)
3. ⏳ `EPIC-06_ROADMAP.md`
4. ⏳ `EPIC-06_README.md`
5. ⏳ `EPIC-06_DOCUMENTATION_STATUS.md`
6. ⏳ `STORIES_EPIC-06.md`

**Checklist Validation**:
- [ ] Story 2bis: 5 pts partout ✓
- [ ] Story 3: 8 pts partout ✓
- [ ] Phase 1 Total: 26 pts partout ✓
- [ ] Grand Total: 34 pts partout (ou 81 pts total epic si confirmé)
- [ ] % Complete: 45.9% partout (ou 42.0% si total=81)

---

## 🎯 Timeline Achievements

**Temps total réel**: 6 jours (Oct 14-16, 2025)
- Phase 0: 3 jours (Stories 0.1 + 0.2)
- Phase 1: 3 jours (Stories 1 + 2bis + 3)

**Temps estimé initial**: 23-32 jours
- Phase 0: 5-6 jours estimés
- Phase 1: 18-26 jours estimés

**Performance**: **AHEAD OF SCHEDULE -17 jours minimum** (ahead by 2.8-5.3x!)

---

**Date Création**: 2025-10-16
**Version**: 1.0.0
**Status**: ✅ **FINAL** - Source de vérité pour story points

**Related ADRs**:
- ADR-017: Story 2 vs Story 2bis Clarification

**Next Steps**:
1. Appliquer ces valeurs dans tous documents EPIC-06
2. Créer commit git "docs(EPIC-06): Standardize story points"
3. Valider cohérence finale avec checklist