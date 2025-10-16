# EPIC-06: Code Intelligence - Documentation Complète

**Version**: 1.2.0
**Date**: 2025-10-16 (Updated: Phase 0 COMPLETE)
**Statut**: ✅ **PHASE 0 COMPLETE (100%)** → Phase 1 READY

---

## 📚 Documentation Structure (~150 KB)

```
EPIC-06/
├─ EPIC-06_README.md                           ← VOUS ÊTES ICI (point d'entrée) ⚡ UPDATED
├─ EPIC-06_Code_Intelligence.md                (33 KB) ← Vue d'ensemble Epic
├─ EPIC-06_DEEP_ANALYSIS.md                    (22 KB) ← Analyse comparative embeddings
├─ EPIC-06_IMPLEMENTATION_PLAN.md              (31 KB) ← Plan détaillé étape par étape
├─ EPIC-06_ROADMAP.md                          (17 KB) ← Timeline visuelle & métriques ⚡ UPDATED v1.2.0
├─ EPIC-06_DECISIONS_LOG.md                    (17 KB) ← ADRs (Architecture Decision Records)
├─ STORIES_EPIC-06.md                          (~100 KB) ← User stories détaillées (6 stories)
├─ EPIC-06_PHASE_0_DEEP_DIVE.md                (33 KB) ← Recherches Phase 0 (20+ refs web)
├─ EPIC-06_PHASE_0_IMPLEMENTATION_ULTRADEEP.md (54 KB) ← Guide implémentation Phase 0
├─ EPIC-06_PHASE_0_CRITICAL_INSIGHTS.md        (17 KB) ← 7 insights critiques Phase 0 ⏳ TO UPDATE
├─ EPIC-06_PHASE_0_REVIEW_REPORT.md            (26 KB) ← Review quality (score 8.7/10)
├─ EPIC-06_PHASE_0_STORY_0.1_REPORT.md         (83 KB) ← Rapport complétion Story 0.1 ✅
├─ EPIC-06_PHASE_0_STORY_0.2_REPORT.md         (NEW 15 KB) ← Rapport complétion Story 0.2 ✅
└─ EPIC-06_PHASE_0_STORY_0.2_AUDIT_REPORT.md   (NEW 40 KB) ← Audit approfondi Story 0.2 ✅
```

---

## 🎯 Quick Start - Où commencer?

### Si vous voulez...

#### ...Comprendre l'Epic en 5 minutes
→ Lisez **EPIC-06_Code_Intelligence.md** (sections Vision & Objectif + Recommandation Finale)

#### ...Voir le planning et timeline
→ Lisez **EPIC-06_ROADMAP.md** (timeline 13 semaines + jalons)

#### ...Implémenter (développeur)
→ Lisez **EPIC-06_IMPLEMENTATION_PLAN.md** (plan phase par phase avec code examples)

#### ...Comprendre les choix techniques
→ Lisez **EPIC-06_DECISIONS_LOG.md** (9 ADRs avec justifications)

#### ...Détails user stories
→ Lisez **STORIES_EPIC-06.md** (6 stories avec acceptance criteria + tasks + tests)

#### ...Comprendre pourquoi jina-code vs nomic-code
→ Lisez **EPIC-06_DEEP_ANALYSIS.md** (comparaison 5 modèles + benchmarks)

---

## 🎯 Executive Summary (2 min)

### Objectif
Ajouter **code intelligence** à MnemoLite (indexation, search sémantique, call graph) **TOUT EN préservant** use case principal (agent memory).

### Stratégie
**Architecture dual-purpose**:
- Table `events` (INCHANGÉE) → agent conversations, docs (nomic-embed-text-v1.5)
- Table `code_chunks` (NOUVELLE) → code intelligence (jina-embeddings-v2-base-code)
- Dual embeddings: nomic-text (137M, 768D) + jina-code (161M, 768D) = ~700 MB RAM

### Timeline
**13 semaines** (3 mois) réparties en 5 phases:
- Phase 0: Infrastructure (1 sem, 8 pts)
- Phase 1: Foundation (4 sem, 31 pts)
- Phase 2: Graph (3 sem, 13 pts)
- Phase 3: Hybrid Search (3 sem, 21 pts)
- Phase 4: Integration (2 sem, 13 pts)

**Total**: 74 story points

### Décisions Techniques Clés

| Aspect | Décision | Raison |
|--------|----------|--------|
| **Architecture** | Tables séparées (events + code_chunks) | Backward compat, séparation concerns |
| **Embeddings** | jina-embeddings-v2-base-code (161M, 768D) | 43× plus léger que nomic-code (7B) |
| **AST Parsing** | tree-sitter-languages (pré-compilé) | Pas de compilation, 50+ langages |
| **Search Lexical** | pg_trgm similarity (natif PostgreSQL) | Simple, performant, pas de dépendances |
| **Search Fusion** | RRF (Reciprocal Rank Fusion, k=60) | Standard industry, robust |
| **Migrations** | Alembic async template | Versioning, rollback support |

### Métriques de Succès

| Métrique | Target |
|----------|--------|
| Indexing speed | <500ms/file (300 LOC) |
| Search latency | <50ms (P95, 10k chunks) |
| Graph traversal | <20ms (depth=2) |
| RAM embeddings | <1 GB (~700 MB) |
| Code chunking quality | >80% fonctions complètes |
| Search recall | >85% (Recall@10) |
| Tests coverage | >85% |
| Backward compatibility | 0 breaking changes API v1 |

---

## 📊 Stories Overview

### Phase 0: Infrastructure (1 semaine, 8 pts)
- **Story 0.1**: Alembic Async Setup (3 pts)
- **Story 0.2**: Dual Embeddings Service (5 pts)

### Phase 1: Foundation (4 semaines, 31 pts)
- **Story 1**: Tree-sitter Integration & AST Chunking (13 pts)
- **Story 2**: Dual Embeddings Integration (5 pts)
- **Story 2bis**: Code Chunks Table & Repository (5 pts)
- **Story 3**: Code Metadata Extraction (8 pts)

### Phase 2: Graph (3 semaines, 13 pts)
- **Story 4**: Dependency Graph Construction (13 pts)

### Phase 3: Hybrid Search (3 semaines, 21 pts)
- **Story 5**: Hybrid Search (pg_trgm + Vector + RRF) (21 pts)

### Phase 4: Integration (2 semaines, 13 pts)
- **Story 6**: Code Indexing Pipeline & API (13 pts)

**Total**: 6 stories principales + 2 stories infrastructure = **8 stories**

---

## 🔬 Recherches Web & Validations

### Recherches Effectuées (2024-2025)

1. **Tree-sitter Python Integration**
   - Package choisi: `tree-sitter-languages` (pré-compilé)
   - Référence: https://pypi.org/project/tree-sitter-languages/

2. **Sentence-Transformers Multiple Models Memory**
   - Validation: 2 modèles simultanés = RAM additive (~700 MB)
   - Optimisations: FP16, batch processing
   - Référence: https://milvus.io/ai-quick-reference/

3. **PostgreSQL pg_trgm BM25 Limitations** ⚠️ CRITIQUE
   - **Découverte**: PostgreSQL natif **NE SUPPORTE PAS BM25**!
   - Alternative: pg_trgm similarity (choisi)
   - Extensions BM25: pg_search, VectorChord (évaluation future)
   - Référence: https://jkatz05.com/post/postgres/hybrid-search-postgres-pgvector/

4. **Alembic SQLAlchemy 2.0 Async Patterns**
   - Template: `alembic init -t async`
   - Pattern `run_sync` pour migrations
   - Référence: https://testdriven.io/blog/fastapi-sqlmodel/

### Rapport Perplexity.ai

**Score Global**: 7.0/10

**Points forts**:
- ✅ Confirme choix jina-embeddings-v2-base-code (convergence indépendante)
- ✅ Identification Codestral Embed (nouveau modèle à surveiller 2025)

**Points faibles**:
- ⚠️ RAM sous-estimée (nomic-code: rapport dit "<2GB quantized", réalité ~7GB INT8)
- ⚠️ MRR scores non sourcés
- ⚠️ Manque profondeur technique (quantization, matryoshka)

**Conclusion**: Notre analyse EPIC-06_DEEP_ANALYSIS.md **plus rigoureuse** que rapport Perplexity.

---

## ⚠️ Points Critiques à Respecter

### 🚨 Contraintes Inviolables

1. **Backward Compatibility ABSOLUE**
   - Table `events` : **0 changements**
   - API v1 `/v1/events` : **0 breaking changes**
   - Tests regression obligatoires avant chaque merge

2. **RAM Budget Strict**
   - Total embeddings : **< 1 GB** (target: ~700 MB)
   - Monitoring RAM requis (psutil)
   - Fallback: désactiver dual embeddings si overflow

3. **768D Embeddings Partout**
   - **PAS de migration DB** tolérée
   - Validation: `len(embedding) == 768` dans tous tests

4. **PostgreSQL 18 Only** ✅ MIGRÉ
   - Migration PostgreSQL 17 → 18 complétée (Phase 0)
   - **Aucune** dépendance externe (Elasticsearch, Meilisearch, etc.)
   - Extensions natives uniquement (pgvector 0.8.1, pg_trgm)

### ⚡ Décisions Critiques Validées

| Décision | Statut | Référence |
|----------|--------|-----------|
| Tables séparées (events + code_chunks) | ✅ VALIDÉE | ADR-001 |
| jina-embeddings-v2-base-code (161M, 768D) | ✅ VALIDÉE | ADR-002 |
| pg_trgm (pas BM25 vrai) | ✅ VALIDÉE (réserve) | ADR-003 |
| tree-sitter-languages (pré-compilé) | ✅ VALIDÉE | ADR-004 |
| Alembic async template | ✅ VALIDÉE | ADR-005 |
| RRF fusion (k=60) | ✅ VALIDÉE | ADR-006 |
| Graph depth ≤ 3 | ✅ VALIDÉE | ADR-007 |

---

## 🚧 Risques Majeurs Identifiés

### Risque 1: Tree-sitter Parsing Failures
**Impact**: HAUT | **Probabilité**: MOYENNE

**Plan d'urgence**:
- Activer fallback chunking fixe automatiquement
- Logger fichiers problématiques
- Réduire langages (Python only si critique)

### Risque 2: pg_trgm Insufficient Quality
**Impact**: MOYEN | **Probabilité**: MOYENNE

**Plan d'urgence**:
- Augmenter weight vector search dans RRF
- Évaluer pg_search extension (BM25 vrai)
- Fallback: vector-only search

### Risque 3: RAM Overflow Dual Embeddings
**Impact**: MOYEN | **Probabilité**: FAIBLE

**Plan d'urgence**:
- Quantization FP16 (sentence-transformers)
- Lazy loading (charger à la demande)
- Fallback: nomic-text uniquement

---

## ✅ Checklist Pre-Kickoff

### Documentation
- [x] Epic défini (EPIC-06_Code_Intelligence.md)
- [x] Deep analysis complète (EPIC-06_DEEP_ANALYSIS.md)
- [x] Plan implémentation détaillé (EPIC-06_IMPLEMENTATION_PLAN.md)
- [x] Roadmap visuelle (EPIC-06_ROADMAP.md)
- [x] ADRs documentées (EPIC-06_DECISIONS_LOG.md)
- [x] User stories détaillées (STORIES_EPIC-06.md)

### Recherches
- [x] Embeddings benchmarks (jina-code vs nomic-code)
- [x] Tree-sitter integration best practices
- [x] PostgreSQL BM25 limitations identifiées
- [x] Alembic async patterns validés
- [x] Rapport Perplexity.ai analysé (score 7/10)

### Validations Techniques
- [x] jina-embeddings-v2-base-code (161M, 768D) choisi
- [x] tree-sitter-languages (pré-compilé) validé
- [x] pg_trgm similarity (natif) choisi
- [x] RRF fusion algorithm (k=60) validé
- [x] Alembic async setup défini

### Infrastructure
- [x] PostgreSQL 18 + pgvector 0.8.1 ✅ (Pré-Phase 0)
- [x] Alembic 1.17.0 installé et configuré ✅ (Story 0.1 - 2025-10-15)
- [x] Baseline migration créée et stampée ✅ (Story 0.1 - revision 9dde1f9db172)
- [x] Pydantic v2 settings avec dual embeddings ✅ (Story 0.1 - workers/config/settings.py)
- [x] DualEmbeddingService créé et testé ✅ (Story 0.2 - 2025-10-16)
- [x] Lazy loading + RAM safeguard actifs ✅ (Story 0.2 - thread-safe)
- [x] Backward compatibility 100% validée ✅ (Story 0.2 - Adapter pattern)
- [x] Audit complet: Score 9.4/10 ✅ (Story 0.2 - Production Ready)
- [ ] Tree-sitter-languages installé (Story 1 - Phase 1)

---

## 🎯 Prochaines Actions

### ✅ Complété - Phase 0 (100%)
1. ✅ **Validation stakeholders** : Présenter plan complet
2. ✅ **Priorisation**: Confirmer allocation 13 semaines
3. ✅ **Ressources**: Assigner équipe développement
4. ✅ **Story 0.1**: Alembic Async Setup (3 pts) - **COMPLETE 2025-10-15**
5. ✅ **Story 0.2**: Dual Embeddings Service (5 pts) - **COMPLETE 2025-10-16**

### Phase 0 Achievements (3 jours - AHEAD OF SCHEDULE)

**Story 0.1: Alembic Async Setup** ✅ COMPLETE (2025-10-15)
- ✅ Alembic 1.17.0 installé avec template async
- ✅ `workers/config/settings.py` migré Pydantic v2
- ✅ `api/alembic/env.py` configuré (psycopg2 + NullPool)
- ✅ Baseline migration créée (9dde1f9db172)
- ✅ Database stampée, `alembic_version` opérationnelle
- ✅ Documentation: `EPIC-06_PHASE_0_STORY_0.1_REPORT.md`

**Story 0.2: Dual Embeddings Service** ✅ COMPLETE (2025-10-16)
- ✅ `DualEmbeddingService` créé (450 lines, EmbeddingDomain enum)
- ✅ Lazy loading + double-checked locking (thread-safe)
- ✅ RAM safeguard (bloque CODE model si > 900 MB)
- ✅ Adapter pattern (backward compatibility 100%)
- ✅ 24 unit tests + 19 regression tests passent
- ✅ Audit complet: Score 9.4/10 - Production Ready
- ✅ 2 bugs critiques corrigés (empty HYBRID, deprecated API)
- ✅ Documentation:
  - `EPIC-06_PHASE_0_STORY_0.2_REPORT.md` (15 KB)
  - `EPIC-06_PHASE_0_STORY_0.2_AUDIT_REPORT.md` (40 KB)

### ⏳ Phase 1 - Story 1 (NEXT - 5 jours, 13 pts)

**Story 1: Tree-sitter Integration & AST Chunking**
- [ ] Install tree-sitter-languages (pré-compilé)
- [ ] Create CodeChunker service (AST-based)
- [ ] Language detection (Python, JS, TS, Go, Rust, Java)
- [ ] Chunking strategies (functions, classes, blocks)
- [ ] Tests: 50+ code samples
- [ ] Fallback: fixed-size chunking si parsing fails

**Blockers**: None (Phase 0 100% complete)

---

## 📚 Références Complètes

### Papers & Research
- **cAST**: Chunking via Abstract Syntax Trees (arxiv 2024, ICLR 2025)
  - 82% amélioration précision vs chunking fixe
- **jina-embeddings-v2-base-code**: Lead 9/15 CodeSearchNet benchmarks
- **Hybrid Search PostgreSQL**: Jonathan Katz (2024)

### Libraries & Tools
- **tree-sitter-languages**: https://pypi.org/project/tree-sitter-languages/
- **sentence-transformers**: https://huggingface.co/sentence-transformers
- **radon**: https://github.com/rubik/radon (complexity Python)
- **alembic**: https://alembic.sqlalchemy.org/

### PostgreSQL
- **pgvector**: https://github.com/pgvector/pgvector
- **pg_trgm**: https://www.postgresql.org/docs/current/pgtrgm.html
- **pg_search** (éval future): https://blog.paradedb.com/pages/introducing_search

### Benchmarks
- **CodeSearchNet**: https://github.com/github/CodeSearchNet
- **MTEB Code**: https://huggingface.co/spaces/mteb/leaderboard

---

## 📞 Contact & Support

**Questions sur le plan**:
- Lire d'abord: EPIC-06_IMPLEMENTATION_PLAN.md (plan détaillé)
- Décisions techniques: EPIC-06_DECISIONS_LOG.md (9 ADRs)

**Pendant implémentation**:
- Blocker technique: Consulter ADRs
- Changement scope: Créer ADR-XXX-REVISION
- Performance issues: Check EPIC-06_ROADMAP.md (métriques target)

---

**Date**: 2025-10-16 (Updated: Phase 0 COMPLETE)
**Version**: 1.2.0
**Statut**: ✅ **PHASE 0 COMPLETE (100%)** → Phase 1 READY

**Prochaine Étape**: Kickoff Phase 1 Story 1 - Tree-sitter Integration (5 jours, 13 pts)

**Progrès EPIC-06**: 8/74 story points (10.8%) | 2/8 stories complètes | Phase 0: 100% ✅

**Achievements**:
- Phase 0 complétée en 3 jours (vs 5 jours estimés) - **AHEAD OF SCHEDULE**
- 0 breaking changes API
- Audit complet: Score 9.4/10 - Production Ready
- Infrastructure robuste et testée (43 tests passed)
