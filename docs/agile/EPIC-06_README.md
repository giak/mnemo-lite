# EPIC-06: Code Intelligence - Documentation Complète

**Version**: 1.0.0
**Date**: 2025-10-15
**Statut**: 📋 PLANIFICATION APPROFONDIE TERMINÉE

---

## 📚 Documentation Structure (119 KB)

```
EPIC-06/
├─ EPIC-06_README.md                    ← VOUS ÊTES ICI (point d'entrée)
├─ EPIC-06_Code_Intelligence.md         (33 KB) ← Vue d'ensemble Epic
├─ EPIC-06_DEEP_ANALYSIS.md             (22 KB) ← Analyse comparative embeddings
├─ EPIC-06_IMPLEMENTATION_PLAN.md       (31 KB) ← Plan détaillé étape par étape
├─ EPIC-06_ROADMAP.md                   (16 KB) ← Timeline visuelle & métriques
├─ EPIC-06_DECISIONS_LOG.md             (17 KB) ← ADRs (Architecture Decision Records)
└─ STORIES_EPIC-06.md                   (~100 KB) ← User stories détaillées (6 stories)
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
- Table `events` (INCHANGÉE) → agent conversations, docs
- Table `code_chunks` (NOUVELLE) → code intelligence
- Dual embeddings: nomic-text (137M) + jina-code (161M) = ~700 MB

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

4. **PostgreSQL 17 Only**
   - **Aucune** dépendance externe (Elasticsearch, Meilisearch, etc.)
   - Extensions natives uniquement (pgvector, pg_trgm)

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
- [ ] Alembic initialisé (Phase 0 Story 0.1)
- [ ] Dual embeddings testé (Phase 0 Story 0.2)
- [ ] Variables environnement définies (.env.example)

---

## 🎯 Prochaines Actions

### Immédiat (Cette semaine)
1. ✅ **Validation stakeholders** : Présenter plan complet
2. ✅ **Priorisation**: Confirmer allocation 13 semaines
3. ✅ **Ressources**: Assigner équipe développement

### Semaine 1 (Phase 0 Kickoff)
1. **Story 0.1**: Alembic Async Setup (3 pts)
   - Initialiser: `alembic init -t async alembic`
   - Configurer env.py
   - Migration baseline

2. **Story 0.2**: Dual Embeddings Service (5 pts)
   - Installer: `sentence-transformers`, `tree-sitter-languages`
   - Étendre `EmbeddingService`
   - Benchmark local (RAM < 1 GB)

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

**Date**: 2025-10-15
**Version**: 1.0.0
**Statut**: ✅ DOCUMENTATION COMPLÈTE - PRÊT POUR VALIDATION STAKEHOLDERS

**Prochaine Étape**: Présentation plan → Validation → Kickoff Phase 0 Story 0.1
