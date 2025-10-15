# ADR-003-REVISION: Réévaluation pg_search avec Package .deb Ubuntu

**Date**: 2025-10-15
**Statut**: 🔄 EN RÉVISION
**Type**: REVISION ADR-003 (BM25 Search)
**Décideurs**: Équipe MnemoLite

---

## 🚨 Nouvelle Information Critique

**Découverte**: ParadeDB `pg_search` dispose d'un **package .deb officiel** pour Ubuntu 24.04 (noble), **100% compatible Linux Mint 22**.

### ✅ Validations Croisées (Web Research)

#### 1. Linux Mint 22 = Ubuntu 24.04 noble base
- **Source**: Linux Mint Forums (forums.linuxmint.com)
- **Citation**: "Mine is 24.04, so every package for Ubuntu 24.04 noble will work on my Linux Mint Cinnamon installation"
- **Confirmation**: Linux Mint 22 basé sur Ubuntu 24.04 LTS noble

#### 2. PostgreSQL 17 installable sur Linux Mint 22
- **Sources**: idroot.us, TecMint, YouTube tutorials
- **Méthode**: apt via repository officiel PostgreSQL
- **Status**: ✅ Validé par multiples tutorials

#### 3. pg_search package .deb officiel
- **Source**: ParadeDB Documentation (docs.paradedb.com)
- **Package**: `postgresql-17-pg-search_0.19.0-1PARADEDB-noble_amd64.deb`
- **Architecture**: amd64 (standard Linux Mint 22)
- **Version**: v0.19.0 (2024)
- **Status**: ✅ Package officiellement disponible

### Installation Validée (Linux Mint 22)

```bash
# 1. Installer dépendance (automatique avec apt)
sudo apt-get install -y libicu74

# 2. Télécharger package .deb
curl -L "https://github.com/paradedb/paradedb/releases/download/v0.19.0/postgresql-17-pg-search_0.19.0-1PARADEDB-noble_amd64.deb" -o /tmp/pg_search.deb

# 3. Installer via apt (gère dépendances automatiquement)
sudo apt-get install -y /tmp/pg_search.deb

# 4. Activer extension dans PostgreSQL
psql -U mnemo -d mnemolite -c "CREATE EXTENSION IF NOT EXISTS pg_search;"
```

**Durée installation**: ~5 minutes (téléchargement + installation)

**Références**:
- ParadeDB docs: https://docs.paradedb.com/deploy/self-hosted/extension
- Neon pg_search: https://neon.com/docs/extensions/pg_search
- ParadeDB releases: https://github.com/paradedb/paradedb/releases

---

## Comparaison Installation: pg_search vs pgvector

| Aspect | pgvector | pg_search (ParadeDB) |
|--------|----------|----------------------|
| **Installation** | `apt install postgresql-17-pgvector` | `apt install postgresql-17-pg-search_*.deb` |
| **Compilation** | ❌ Non requise (package distro) | ❌ Non requise (package .deb) |
| **Complexité** | ✅ Triviale | ✅ Triviale |
| **Dépendance externe** | ⚠️ Extension tierce (officielle) | ⚠️ Extension tierce (ParadeDB) |
| **Maintenance** | ✅ Communauté large | ⚠️ ParadeDB (startup, funding) |
| **Maturité** | ✅✅✅ Très mature | ⚠️⚠️ Récent (v0.19.0) |

---

## Fonctionnalités pg_search (Synthèse Recherche)

### 1. BM25 Natif avec Tokenization Code-Aware

```sql
-- Index BM25 couvrant plusieurs champs
CREATE INDEX code_bm25_idx ON code_chunks
USING bm25 (id, path, source_code)
WITH (key_field='id');

-- Recherche BM25
SELECT id, name, path, pdb.score(id) AS bm25
FROM code_chunks
WHERE source_code @@@ 'HashMap insert'
ORDER BY bm25 DESC
LIMIT 20;
```

**Opérateur**: `@@@` (BM25 search)
**Score**: `pdb.score(id)` (score BM25 natif)

### 2. Typo-Tolerance Intégré

```sql
SELECT id, path, pdb.score(id)
FROM code_chunks
WHERE id @@@ paradedb.match('source_code', 'hashtable', distance => 1)
ORDER BY pdb.score(id) DESC
LIMIT 20;
```

**Distance Levenshtein**: `distance => 1` (typos automatiques)

### 3. Hybrid Search BM25 + Vector (RRF)

```sql
WITH
bm AS (
  SELECT id, row_number() OVER (ORDER BY pdb.score(id) DESC) AS r
  FROM code_chunks
  WHERE source_code @@@ 'serde json'
  ORDER BY pdb.score(id) DESC
  LIMIT 100
),
vv AS (
  SELECT id, row_number() OVER (ORDER BY embedding_code <=> $1) AS r
  FROM code_chunks
  ORDER BY embedding_code <=> $1
  LIMIT 100
)
SELECT c.id, c.name, c.path,
       1.0/(60 + COALESCE(bm.r, 1e9)) + 1.0/(60 + COALESCE(vv.r, 1e9)) AS rrf
FROM code_chunks c
LEFT JOIN bm ON bm.id = c.id
LEFT JOIN vv ON vv.id = c.id
ORDER BY rrf DESC
LIMIT 20;
```

**RRF natif SQL** (k=60 standard)

---

## Comparaison Options BM25 (Mise à Jour)

| Critère | pg_trgm | pg_search | VectorChord-BM25 | plpgsql_bm25 |
|---------|---------|-----------|------------------|--------------|
| **BM25 vrai** | ❌ (similarité simple) | ✅ Natif | ✅ Natif | ✅ TF-IDF saturation |
| **Installation** | ✅ Native PostgreSQL | ✅ Package .deb | ⚠️ Compilation Rust | ✅ Script SQL |
| **Code tokenization** | ⚠️ Trigrams (coupe `_`) | ✅ Configurable | ✅✅ Très configurable | ⚠️ Basique |
| **Typo-tolerance** | ✅ Fuzzy matching | ✅ Distance Levenshtein | ⚠️ Manuel | ❌ Non |
| **Performance** | ✅✅ Rapide (GIN) | ✅✅ Rapide (Rust) | ✅✅✅ Très rapide | ⚠️ Moyen (PL/pgSQL) |
| **Maturité** | ✅✅✅ Très mature | ⚠️⚠️ Récent (2024) | ⚠️ Expérimental | ⚠️ Proof-of-concept |
| **Dépendances externes** | ❌ Aucune | ⚠️ Package .deb ParadeDB | ⚠️ VectorChord | ❌ Aucune |
| **Hybrid integration** | ⚠️ Manuel (RRF SQL) | ✅ Intégré + RRF SQL | ⚠️ Manuel | ⚠️ Manuel |

---

## Analyse Contrainte "PostgreSQL 17 Only"

### Interprétation Contrainte (CLAUDE.md)

> "◊Arch: PG17.only ∧ CQRS.inspired ∧ DIP.protocols ∧ async.first"

**Deux interprétations possibles**:

#### Option A: "PostgreSQL 17 uniquement, aucune dépendance tierce"
- ✅ pg_trgm (extension native PostgreSQL)
- ✅ plpgsql_bm25 (script SQL pur)
- ❌ pg_search (package .deb externe)
- ❌ VectorChord-BM25 (extension externe)
- ❌ pgvector (extension externe... **MAIS DÉJÀ UTILISÉE!**)

#### Option B: "PostgreSQL 17 + extensions tierces via packages" ⭐ INTERPRÉTATION PROBABLE
- ✅ pg_trgm (native)
- ✅ pgvector (déjà utilisée, package externe)
- ✅ pg_search (package .deb, installation triviale)
- ✅ VectorChord-BM25 (si package .deb disponible)
- ✅ plpgsql_bm25 (script SQL)

**Conclusion**: Puisque **pgvector est déjà utilisé** (extension tierce), la contrainte signifie probablement "PostgreSQL 17 + extensions PostgreSQL standard" plutôt que "PostgreSQL natif uniquement".

---

## Impact sur ADR-003

### Recommandation Originale (ADR-003)
1. **Phase 1-3 (v1.4.0)**: pg_trgm (natif, simple)
2. **Post-Phase 3**: Benchmark qualité
3. **Si Recall@10 < 80%**: Évaluer alternatives
   - **Option préférée**: plpgsql_bm25 (pur SQL)
   - **Option performance**: VectorChord-BM25 (si dépendances acceptées)
   - **Option complète**: pg_search (si BM25 + hybrid souhaité)

### Nouvelle Recommandation (RÉVISION)

#### Scénario 1: Conserver Approche Progressive (Recommandé)
1. **Phase 1-3 (v1.4.0)**: pg_trgm + pgvector + RRF
   - Rationale: Simple, natif, MVP fonctionnel
   - Pas de nouvelle dépendance
2. **Post-Phase 3 Benchmark**: Mesurer Recall@10, Precision@10
3. **Si insuffisant (<80% recall)**: Migrer vers pg_search
   - Installation triviale (.deb)
   - BM25 vrai + typo-tolerance
   - Tokenization code-aware configurable

#### Scénario 2: Adopter pg_search dès Phase 3 (Audacieux)
1. **Phase 0**: Installer `postgresql-17-pg-search` (.deb)
2. **Phase 3**: Implémenter hybrid pg_search BM25 + pgvector + RRF
   - Rationale: BM25 vrai > pg_trgm, installation triviale
   - Tokenization code-aware dès v1.4.0
3. **Risque**: Extension récente (v0.19.0), maturité moindre

---

## Recommandation Finale

### ✅ CONSERVER ADR-003 ORIGINALE (Scénario 1)

**Justification**:
1. **Maturité**: pg_trgm très mature vs pg_search récent (2024)
2. **Risque**: Nouvelle dépendance = nouveau point de failure
3. **MVP**: pg_trgm suffisant pour v1.4.0 (code search basique)
4. **Upgrade path clair**: pg_search disponible si besoin (installation .deb triviale)
5. **Benchmarks**: Valider besoin réel BM25 avant adoption

**Plan d'action**:
- ✅ **Phase 1-3**: Conserver pg_trgm + pgvector + RRF
- ✅ **Post-Phase 3**: Benchmark qualité (Recall@10, Precision@10)
- ✅ **Si Recall@10 < 80%**: Migrer pg_search (installation .deb, 1-2 jours)
- ✅ **Documenter**: Installation pg_search dans README (section "Advanced Setup")

**Upgrade path v1.5.0** (si nécessaire):
```bash
# Installation pg_search (5 minutes)
curl -L "https://github.com/paradedb/paradedb/releases/download/v0.19.0/postgresql-17-pg-search_0.19.0-1PARADEDB-noble_amd64.deb" -o /tmp/pg_search.deb
sudo docker cp /tmp/pg_search.deb mnemo-postgres:/tmp/
sudo docker exec mnemo-postgres apt install -y /tmp/pg_search.deb

# Migration SQL (1 jour)
CREATE EXTENSION pg_search;
CREATE INDEX code_bm25_idx ON code_chunks USING bm25 (id, path, source_code) WITH (key_field='id');

# Update HybridSearchService (1 jour)
# Replace pg_trgm query with pg_search @@@ operator
```

---

## Mise à Jour ADR-003

### Options Considérées (Ajout)

#### Option C: pg_search Extension (ParadeDB) - MISE À JOUR

**Installation Ubuntu 24.04 (Linux Mint 22)**:
```bash
curl -L "https://github.com/paradedb/paradedb/releases/download/v0.19.0/postgresql-17-pg-search_0.19.0-1PARADEDB-noble_amd64.deb" -o /tmp/pg_search.deb
sudo apt install -y /tmp/pg_search.deb
```

**Avantages**:
- ✅ **Installation triviale** (package .deb, 5 minutes)
- ✅ Vrai BM25 (TF-IDF avec saturation)
- ✅ Tokenization configurable (code-aware)
- ✅ Typo-tolerance intégré (distance Levenshtein)
- ✅ Opérateur SQL natif (`@@@`, `pdb.score()`)
- ✅ Hybrid search patterns documentés
- ✅ Performance excellente (Rust)

**Inconvénients**:
- ⚠️ Dépendance externe (package .deb ParadeDB, pas native PostgreSQL)
- ⚠️ Maturité récente (v0.19.0, 2024)
- ⚠️ Maintenance dépend startup ParadeDB (funding risk)
- ⚠️ Communauté plus petite que pgvector

**Verdict**: **Excellente alternative** si pg_trgm insuffisant. Installation aussi simple que pgvector.

---

## Références Complètes

### Installation
- **Neon pg_search docs**: https://neon.com/docs/extensions/pg_search
- **ParadeDB releases**: https://github.com/paradedb/paradedb/releases
- **ParadeDB docs**: https://docs.paradedb.com/deploy/self-hosted/extension

### Hybrid Search
- **Jonathan Katz (pgvector + BM25)**: https://jkatz.github.io/post/postgres/hybrid-search-postgres-pgvector/
- **ParadeDB Full-Text Overview**: https://docs.paradedb.com/documentation/full-text/overview

### Alternatives
- **VectorChord-BM25**: https://github.com/tensorchord/VectorChord-bm25
- **plpgsql_bm25**: https://github.com/paradedb/paradedb/discussions/1584
- **pgvector**: https://github.com/pgvector/pgvector

---

## Décision Finale

**MAINTENIR ADR-003 ORIGINALE**: pg_trgm (Phase 1-3), évaluer pg_search post-benchmark.

**Justification**:
- pg_trgm mature, stable, natif
- pg_search excellent mais récent
- Installation .deb triviale = upgrade path facile
- Valider besoin réel avant adoption

**Prochaines Actions**:
1. ✅ **Phase 3**: Implémenter pg_trgm + pgvector + RRF
2. ✅ **Post-Phase 3**: Benchmark Recall@10, Precision@10
3. ✅ **Documenter**: Installation pg_search dans README (section optionnelle)
4. ⚠️ **Si Recall@10 < 80%**: Créer Story v1.5.0 "Migrate to pg_search BM25"

---

**Date**: 2025-10-15
**Statut**: 🔄 RÉVISION COMPLÉTÉE → ADR-003 MAINTENUE
**Action**: Documenter upgrade path pg_search dans README

**Conclusion**: L'installation .deb simplifie drastiquement pg_search, mais la maturité de pg_trgm justifie approche progressive. pg_search devient option de migration évidente si qualité insuffisante.
