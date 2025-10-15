# Migration PostgreSQL 18 - Plan d'Exécution

**Date**: 2025-10-15
**Version**: 1.0.0
**Statut**: 🚀 PRÊT POUR EXÉCUTION
**Décision**: Migration PostgreSQL 18 approuvée

---

## 🎯 Executive Summary

**Décision**: ✅ **Migration PostgreSQL 18 confirmée**

**Découvertes Critiques**:
- ✅ **pgvector 0.8.1**: Compatible PostgreSQL 18 (package Debian disponible)
- ❌ **pg_search**: **NON compatible** PostgreSQL 18 (ParadeDB attend release candidate/finale)

**Stratégie BM25 Ajustée**:
- Phase 1-3: **pg_trgm** (MVP, natif PostgreSQL)
- v1.5.0: **pg_search** (quand PG 18 supporté) OU **VectorChord-BM25** (PG 18-ready maintenant)

**Timeline**: 1-2 jours (Phase 0, Semaine 1 EPIC-06)

---

## 📊 Validation Compatibilité Extensions

### ✅ pgvector 0.8.1 - COMPATIBLE PostgreSQL 18

**Source**: Debian packages (Sid)
- Package: `postgresql-18-pgvector_0.8.1-2_amd64.deb`
- Date: 2024-11-02
- Statut: ✅ **Production-ready**

**Références**:
- https://debian.pkgs.org/sid/debian-main-amd64/postgresql-18-pgvector_0.8.1-2_amd64.deb.html

**Installation Docker**:
```dockerfile
FROM postgres:18-alpine

# Option 1: Build from source (Alpine)
RUN apk add --no-cache git build-base postgresql-dev
RUN git clone --branch v0.8.1 https://github.com/pgvector/pgvector.git /tmp/pgvector
RUN cd /tmp/pgvector && make && make install

# Option 2: Attendre package Alpine (si disponible)
# RUN apk add postgresql18-pgvector
```

---

### ❌ pg_search - NON COMPATIBLE PostgreSQL 18

**Source**: GitHub Issue #2723 (ParadeDB)
- Statut: ⚠️ **Pas encore supporté**
- Build errors sur PostgreSQL 18 Beta 1
- **Déclaration ParadeDB**: "Likely wait until the first release candidate before adding support"

**Références**:
- https://github.com/paradedb/paradedb/issues/2723

**Timeline estimée pg_search PG 18**:
- PostgreSQL 18 RC (Release Candidate): ~Q1 2025
- ParadeDB support: ~1-2 mois après RC
- **Disponibilité réaliste**: Q2 2025 (avril-juin 2025)

**Impact**:
- ❌ **Bloque recommandation #1** (pg_search Phase 3)
- ✅ **Alternatives viables** disponibles (VectorChord, pg_trgm)

---

## 🔄 Stratégie BM25 Ajustée (Post-Découverte)

### Plan Original (Avant Recherches)

```
Phase 1-3: pg_trgm (MVP)
    ↓
Post-Phase 3: Benchmark
    ↓
v1.5.0: pg_search SI Recall < 80%
```

---

### Plan Ajusté (Post-Découverte pg_search KO)

```
Phase 1-3 (v1.4.0): pg_trgm + pgvector + RRF
    ↓
Post-Phase 3: Benchmark Recall@10
    ↓
SI Recall < 80%:
    ├─ Option A: VectorChord-BM25 (PG 18-ready MAINTENANT)
    └─ Option B: Attendre pg_search PG 18 (Q2 2025)
```

---

### Comparaison Options BM25 PostgreSQL 18

| Solution | PG 18 Compatible | Disponibilité | Recommandation |
|----------|------------------|---------------|----------------|
| **pg_trgm** | ✅ Natif | ✅ Maintenant | ⭐⭐⭐ Phase 1-3 |
| **pg_search** | ❌ Non (Q2 2025) | ⚠️ ~6 mois | ⭐ v1.5.0+ |
| **VectorChord-BM25** | ✅ Oui (pg18-latest) | ✅ Maintenant | ⭐⭐ v1.5.0 alternative |
| **plpgsql_bm25** | ✅ Natif | ✅ Maintenant | ⚪ Fallback uniquement |

---

### Décision Finale BM25

#### Phase 1-3 (v1.4.0) - INCHANGÉ

**Solution**: **pg_trgm** + pgvector + RRF (k=60)

**Justification**:
- ✅ Natif PostgreSQL 18
- ✅ Mature, stable, production-ready
- ✅ Suffisant MVP (Recall estimé 65-75%)
- ✅ Upgrade path clair vers BM25 vrai

---

#### v1.5.0 (Post-Benchmark) - AJUSTÉ

**SI Recall@10 < 80%** (post-Phase 3 benchmark):

**Option A**: **VectorChord-BM25** (RECOMMANDÉ)
- ✅ Compatible PostgreSQL 18 **maintenant** (images pg18-latest)
- ✅ BM25 vrai + Block-WeakAnd (performance)
- ✅ Tokenization ultra-configurable (pg_tokenizer.rs)
- ⚠️ Écosystème plus jeune que pg_search
- **Timeline**: 1-2 semaines migration

**Option B**: **Attendre pg_search** (Q2 2025)
- ✅ BM25 mature (Tantivy)
- ✅ Tokenizers code-aware (source_code, ngram)
- ⚠️ Attente ~6 mois (Q2 2025)
- **Timeline**: Conserver pg_trgm jusqu'à Q2 2025

**Recommandation**: **Option A (VectorChord)** SI Recall < 80%
- Rationale: Éviter attente 6 mois, VectorChord PG 18-ready maintenant

---

## 🚀 Plan de Migration PostgreSQL 18

### Timeline Globale

```
Jour 1 (4h): Préparation + Backup
    ├─ Backup DB prod
    ├─ Update Dockerfile
    ├─ Build image PostgreSQL 18 + pgvector 0.8.1
    └─ Tests DB test (mnemolite_test)

Jour 2 (4h): Migration + Validation
    ├─ Migration DB prod (docker-compose up)
    ├─ Tests regression (142 tests)
    ├─ Benchmarks performance
    └─ Documentation
```

**Durée totale**: 1-2 jours

---

### Jour 1: Préparation

#### Étape 1.1: Backup DB Prod

```bash
# Backup complet PostgreSQL 17
make db-backup

# Vérifier backup créé
ls -lh backups/

# Backup manuel (double sécurité)
docker exec mnemo-postgres pg_dumpall -U mnemo > backups/mnemolite_pg17_20251015.sql
```

**Durée**: 10 minutes

---

#### Étape 1.2: Update Dockerfile

**Fichier**: `db/Dockerfile`

**Changements**:

```dockerfile
# AVANT (PostgreSQL 17)
FROM postgres:17-alpine

# APRÈS (PostgreSQL 18)
FROM postgres:18-alpine

# pgvector 0.8.1 (build from source Alpine)
RUN apk add --no-cache \
    git \
    build-base \
    postgresql-dev \
    clang \
    llvm

# Clone et build pgvector 0.8.1
RUN git clone --branch v0.8.1 https://github.com/pgvector/pgvector.git /tmp/pgvector && \
    cd /tmp/pgvector && \
    make && \
    make install && \
    rm -rf /tmp/pgvector

# Extensions (inchangé)
RUN apk add --no-cache postgresql-contrib

# Init scripts (inchangé)
COPY init/*.sql /docker-entrypoint-initdb.d/
```

**Durée**: 5 minutes

---

#### Étape 1.3: Build Image PostgreSQL 18

```bash
# Build nouvelle image
docker-compose build db

# Vérifier version PostgreSQL
docker run --rm mnemo-postgres:latest postgres --version
# Attendu: postgres (PostgreSQL) 18.x

# Vérifier pgvector installé
docker run --rm mnemo-postgres:latest ls /usr/local/lib/postgresql/ | grep vector
# Attendu: vector.so
```

**Durée**: 10 minutes (build + download)

---

#### Étape 1.4: Test Migration DB Test

```bash
# Reset DB test avec PostgreSQL 18
make db-test-reset

# Vérifier extensions
docker exec mnemo-postgres psql -U mnemo -d mnemolite_test -c "SELECT extname, extversion FROM pg_extension;"
# Attendu:
# extname  | extversion
# ---------+-----------
# plpgsql  | 1.0
# vector   | 0.8.1
# pg_trgm  | 1.6

# Vérifier collation
docker exec mnemo-postgres psql -U mnemo -d mnemolite_test -c "SHOW lc_collate;"
# Noter collation actuelle
```

**Durée**: 5 minutes

---

#### Étape 1.5: Tests Collation Provider

**Contexte**: PostgreSQL 18 bascule provider vers `libc` par défaut.

```bash
# Comparer collation PG 17 vs PG 18
# PG 17
docker exec mnemo-postgres-pg17 psql -U mnemo -d mnemolite -c "SELECT datcollate, datctype FROM pg_database WHERE datname = 'mnemolite';"

# PG 18
docker exec mnemo-postgres psql -U mnemo -d mnemolite_test -c "SELECT datcollate, datctype FROM pg_database WHERE datname = 'mnemolite_test';"

# SI différence:
# → Rebuild index pg_trgm requis
# → Tests queries pg_trgm avant/après
```

**Action SI différence collation**:
```sql
-- Rebuild index pg_trgm
REINDEX INDEX CONCURRENTLY idx_events_content_trgm;  -- Si existe
```

**Durée**: 10 minutes

---

### Jour 2: Migration Production

#### Étape 2.1: Migration DB Prod

```bash
# Stop services
docker-compose down

# Backup final (double sécurité)
cp -r postgres-data postgres-data-pg17-backup

# Start avec PostgreSQL 18
docker-compose up -d

# Attendre services ready
sleep 10

# Vérifier healthcheck
make health
# Attendu: API healthy, DB healthy
```

**Durée**: 5 minutes

---

#### Étape 2.2: Vérification Migration

```bash
# Vérifier version PostgreSQL
docker exec mnemo-postgres psql -U mnemo -d mnemolite -c "SELECT version();"
# Attendu: PostgreSQL 18.x

# Vérifier extensions
docker exec mnemo-postgres psql -U mnemo -d mnemolite -c "SELECT extname, extversion FROM pg_extension;"
# Attendu: vector 0.8.1, pg_trgm 1.6

# Vérifier tables
docker exec mnemo-postgres psql -U mnemo -d mnemolite -c "\dt"
# Attendu: events, nodes, edges

# Compter events
docker exec mnemo-postgres psql -U mnemo -d mnemolite -c "SELECT COUNT(*) FROM events;"
# Vérifier cohérence avec backup
```

**Durée**: 5 minutes

---

#### Étape 2.3: Tests Regression

```bash
# Run full test suite
make api-test

# Attendu: 142 passing, 11 skipped, 2 xfailed, 1 xpassed
# ✅ 0 failed

# Tests spécifiques vector search
pytest tests/test_routes_search.py -v

# Tests embedding service
pytest tests/test_services_embedding.py -v
```

**SI tests échouent**:
1. Analyser logs: `docker-compose logs api`
2. Vérifier collation provider (rebuild index)
3. Vérifier pgvector queries (HNSW index)

**Durée**: 10 minutes

---

#### Étape 2.4: Benchmarks Performance

```bash
# Baseline performance PostgreSQL 18
make benchmark

# Métriques attendues (similaires PG 17):
# - Vector search (HNSW): ~12ms P95
# - Hybrid search: ~11ms P95
# - Metadata filtering: ~3ms P95

# Comparer avec baseline PG 17
# Gains attendus PostgreSQL 18:
# - Skip scan B-tree: queries multi-colonnes
# - Async I/O: scans larges
# - Optimizer: OR/IN clauses
```

**SI dégradation performance > 20%**:
1. Vérifier index HNSW: `EXPLAIN ANALYZE SELECT ...`
2. Vérifier collation: rebuild index pg_trgm
3. Vérifier stats: `ANALYZE events;`

**Durée**: 15 minutes

---

#### Étape 2.5: Rollback Plan (SI échec)

**Critères échec**:
- ❌ Tests regression >5% failed
- ❌ Performance dégradée >30%
- ❌ Corruption données

**Procédure rollback**:
```bash
# Stop PostgreSQL 18
docker-compose down

# Restore PostgreSQL 17 data
rm -rf postgres-data
mv postgres-data-pg17-backup postgres-data

# Rollback Dockerfile
# FROM postgres:18-alpine → FROM postgres:17-alpine

# Rebuild image PostgreSQL 17
docker-compose build db

# Start services
docker-compose up -d

# Vérifier restauration
make health
make api-test
```

**Durée rollback**: 10 minutes

---

### Jour 2: Documentation

#### Étape 2.6: Documenter Migration

**Fichiers à mettre à jour**:

1. **README.md**:
```markdown
## Requirements

- Docker & Docker Compose
- **PostgreSQL 18** (via Docker)
- **pgvector 0.8.1**
- Python 3.11+ (for local development)
```

2. **CHANGELOG.md**:
```markdown
## [Unreleased]

### Changed
- **BREAKING**: Migrated to PostgreSQL 18 (from 17)
- Updated pgvector 0.7.x → 0.8.1
- Improved query performance (skip scan B-tree, async I/O)

### Migration Notes
- Automatic migration from PostgreSQL 17 data
- pgvector 0.8.1 backward compatible with 0.7.x indexes
- Collation provider: verify pg_trgm indexes (rebuild if needed)
```

3. **docs/docker_setup.md**:
```markdown
## PostgreSQL 18 + pgvector 0.8.1

MnemoLite uses PostgreSQL 18 with pgvector 0.8.1 for vector similarity search.

### Extensions
- `vector` (pgvector 0.8.1): HNSW indexing, vector operations
- `pg_trgm` (native): Trigram similarity search
- `pgmq` (Tembo): Message queue (infrastructure only)
```

**Durée**: 15 minutes

---

## ⚠️ Risques & Mitigations

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| **pgvector build errors** | Faible | Haut | Tester build Jour 1, fallback pre-built image |
| **Collation breaking changes** | Moyen | Moyen | Tests collation, rebuild index pg_trgm |
| **Performance dégradation** | Faible | Moyen | Benchmarks Jour 2, rollback si >30% |
| **Tests regression échec** | Faible | Haut | Tests DB test Jour 1, rollback plan ready |
| **Corruption données** | Très faible | Critique | Backup multiple (prod + data dir), rollback < 10 min |

---

## ✅ Checklist Pre-Migration

### Infrastructure
- [ ] Backup DB prod créé (`make db-backup`)
- [ ] Backup data directory (`cp -r postgres-data postgres-data-pg17-backup`)
- [ ] Dockerfile mis à jour (PostgreSQL 18 + pgvector 0.8.1)
- [ ] Image PostgreSQL 18 build successful
- [ ] pgvector 0.8.1 installé (vérifier `vector.so`)

### Tests DB Test
- [ ] DB test reset avec PostgreSQL 18
- [ ] Extensions vérifiées (vector 0.8.1, pg_trgm)
- [ ] Collation provider vérifiée
- [ ] Tests regression passent sur DB test

### Rollback Plan
- [ ] Backup PostgreSQL 17 data directory intact
- [ ] Procédure rollback documentée
- [ ] Timeline rollback < 15 minutes

---

## 📊 Validation Post-Migration

### Critères Success

| Critère | Target | Validation |
|---------|--------|------------|
| **Tests regression** | 100% passing | `make api-test` |
| **Performance** | ±10% baseline | `make benchmark` |
| **Vector search** | Latency < 15ms | Benchmark HNSW |
| **Data integrity** | 0 perte | COUNT(*) events |
| **Extensions** | vector 0.8.1, pg_trgm 1.6 | `SELECT extversion` |

### Tests Manuels

```bash
# 1. Vector search
curl -X POST http://localhost:8001/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query":"test semantic search","limit":10}'

# 2. Hybrid search (metadata + vector)
curl -X POST http://localhost:8001/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query":"python function","metadata":{"language":"python"},"limit":5}'

# 3. Health check
curl http://localhost:8001/health
```

---

## 🎯 Décisions Finales

### PostgreSQL 18 Migration

**Statut**: ✅ **APPROUVÉ** (Jour 1-2, Phase 0)

**Justification**:
- ✅ pgvector 0.8.1 compatible (package Debian, build source)
- ✅ Gains performance: skip scan, async I/O, optimizer
- ✅ Tests DB test validation avant prod
- ✅ Rollback plan < 15 minutes

---

### Stratégie BM25

**Phase 1-3 (v1.4.0)**: ✅ **pg_trgm** (MVP)
- Natif PostgreSQL 18
- Mature, stable
- Upgrade path clair

**v1.5.0 (SI Recall < 80%)**: ✅ **VectorChord-BM25**
- PG 18-ready maintenant
- BM25 vrai + Block-WeakAnd
- Alternative pg_search (attente Q2 2025)

---

## 📚 Références

### PostgreSQL 18
- Release notes: https://www.postgresql.org/docs/18/release-18.html
- Skip scan: https://neon.com/postgresql/postgresql-18/skip-scan-btree
- Async I/O: https://postgresql.org/about/news/postgresql-18-released-3142/

### pgvector 0.8.1
- GitHub: https://github.com/pgvector/pgvector
- Debian package: https://debian.pkgs.org/sid/debian-main-amd64/postgresql-18-pgvector_0.8.1-2_amd64.deb.html

### pg_search Compatibility
- Issue PG 18: https://github.com/paradedb/paradedb/issues/2723
- Status: Attente release candidate PostgreSQL 18

### VectorChord-BM25
- GitHub: https://github.com/tensorchord/VectorChord-bm25
- Docker pg18-latest: https://hub.docker.com/r/tensorchord/vchord-suite

---

**Date**: 2025-10-15
**Version**: 1.0.0
**Statut**: ✅ PLAN VALIDÉ - PRÊT POUR EXÉCUTION

**Prochaine Action**: Jour 1 Étape 1.1 - Backup DB Prod
