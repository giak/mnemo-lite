# Prompt Perplexity.ai - BM25 Search PostgreSQL 18 pour MnemoLite

**Date**: 2025-10-15
**Version**: 1.0.0
**Objectif**: Rapport exhaustif sur options BM25-like PostgreSQL 18

---

## 📋 Prompt pour Perplexity.ai

```
Je développe MnemoLite, une base de données cognitive pour agents IA basée sur PostgreSQL 17 (migration vers PostgreSQL 18 prévue). J'ai besoin d'une analyse exhaustive et comparative des solutions BM25-like pour implémenter un système de code search hybride (lexical + sémantique).

## Contexte Projet MnemoLite

**Architecture actuelle**:
- PostgreSQL 17 → Migration PostgreSQL 18 planifiée (Phase 0)
- pgvector 0.8.0+ (HNSW indexing, embeddings 768D)
- pg_trgm (trigram similarity, natif PostgreSQL)
- FastAPI + SQLAlchemy 2.0 async
- Sentence-Transformers: nomic-embed-text-v1.5 (137M params, 768D) + jina-embeddings-v2-base-code (161M params, 768D)
- Linux Mint 22 (base Ubuntu 24.04 noble), amd64
- Docker deployment (PostgreSQL 18-alpine prévu)

**Use Case Principal**: Agent memory (conversations, documentation) - DOIT RESTER FONCTIONNEL
**Use Case Nouveau**: Code intelligence (indexation, semantic search, call graph)

**Contraintes Critiques**:
1. PostgreSQL 18 uniquement (pas d'Elasticsearch, Meilisearch, etc.)
2. 100% local (pas d'API cloud, pas de services externes)
3. CPU-friendly (déploiement sans GPU)
4. RAM budget embeddings: <1 GB total (~700 MB actuellement)
5. Backward compatible (table events intacte, API v1 sans breaking changes)
6. Architecture dual-purpose: events (agent memory) + code_chunks (code intelligence)

**Codebase actuelle**: ~50k events, cible code search: ~100k code chunks (Python, JavaScript, TypeScript, Go, Rust, Java)

## Questions à Investiguer

### 1. Solutions BM25-like PostgreSQL 18 (Comparaison Exhaustive)

Pour chacune des solutions suivantes, fournir:

**A) pg_trgm (PostgreSQL natif)**
- Fonctionnement technique (trigrams, similarité)
- Avantages/inconvénients pour code search
- Performance: latency, index size, Recall@10, Precision@10
- Limitations: tokenization, ranking, normalisation longueur
- Cas d'usage optimaux

**B) pg_search (ParadeDB)**
- Version compatible PostgreSQL 18 (vérifier releases 2024-2025)
- Installation Linux Mint 22 / Ubuntu 24.04 noble (.deb disponible?)
- Architecture technique (Rust, Tantivy, index BM25)
- Tokenization configurable: support code-aware (underscore, camelCase, paths)?
- Opérateurs SQL: @@@, pdb.score(), typo-tolerance (Levenshtein)
- Performance vs pg_trgm: benchmarks disponibles?
- Hybrid search patterns: RRF (Reciprocal Rank Fusion) support?
- Maturité: adoption production, bugs connus, communauté
- Dépendances: libicu74, autres?
- Comparaison pg_search vs alternatives (Meilisearch, Typesense)

**C) VectorChord-BM25 (TensorChord)**
- Version compatible PostgreSQL 18
- Architecture: Block-WeakAnd algorithm, bm25vector type
- Tokenization ultra-configurable: pg_tokenizer, custom analyzers
- Installation: packages .deb disponibles ou compilation Rust requise?
- Performance: benchmarks Block-WeakAnd vs BM25 classique
- Exemples code-aware tokenization (preserve underscore, slash, dot)
- Maturité: adoption, communauté, maintenance
- Comparaison VectorChord vs pg_search

**D) plpgsql_bm25 (PL/pgSQL pur)**
- Implémentations disponibles (GitHub, exemples production)
- Architecture: tables TF/DF, fonctions BM25
- Performance: PL/pgSQL vs Rust (quantification overhead)
- Scaling: limites >10k, >100k documents
- Maintenance: overhead calcul statistiques

**E) Alternatives émergentes 2024-2025**
- pg_bm25 (autres projets GitHub)
- Extensions BM25 récentes PostgreSQL
- Tantivy PostgreSQL bindings
- Autres solutions non identifiées

### 2. PostgreSQL 18 Full-Text Search Améliorations

**Questions**:
- Nouvelles fonctionnalités FTS PostgreSQL 18 vs 17?
- ts_rank, ts_rank_cd: améliorations performances?
- tsvector, tsquery: nouvelles capacités?
- GIN index: optimisations PostgreSQL 18 (parallel creation validée)?
- Skip scan B-tree: impact sur index multi-colonnes FTS?
- Cas d'usage où PostgreSQL 18 natif FTS compétitif vs BM25 extensions?

### 3. Tokenization Code-Aware

**Questions critiques**:
- Comment gérer identifiers code: snake_case, camelCase, PascalCase, kebab-case?
- Paths: src/lib.rs → tokens séparés ou préservés?
- Namespaces: std::collections::HashMap → split sur :: ?
- Ponctuation code: ., _, /, ::, <>, [], (), {}
- Comparaison tokenizers:
  - pg_trgm (trigrams fixes)
  - PostgreSQL FTS (ts_lexize, dictionnaires)
  - pg_search (Tantivy tokenizers)
  - VectorChord (pg_tokenizer custom analyzers)
- Best practices tokenization code search (papers, benchmarks)?

### 4. Hybrid Search BM25 + Vector Embeddings

**Questions**:
- RRF (Reciprocal Rank Fusion): algorithme, paramètre k optimal (60? autres?)?
- Fusion alternatives: score normalization, weighted sum, autres?
- Benchmarks hybrid search: BM25+embeddings vs BM25-only vs embeddings-only?
- Cas d'usage où hybrid > individual (code search, semantic search)?
- Implémentations SQL RRF pour PostgreSQL 18: patterns, exemples?

### 5. Benchmarks & Performance

**Rechercher**:
- Benchmarks code search: CodeSearchNet, MTEB Code, autres datasets?
- Comparaisons chiffrées:
  - pg_trgm vs pg_search: Recall@10, Precision@10, latency, index size
  - BM25 vs TF-IDF vs cosine similarity: ranking quality
  - Hybrid (BM25+vector) vs mono-modal: gains quantifiés
- Performance PostgreSQL 18 vs 17: GIN parallel, skip scan, async I/O (chiffres)?
- Scaling: 10k, 100k, 1M documents (latency P95, index size, RAM)?

### 6. Production Experience & Best Practices

**Questions**:
- Retours d'expérience pg_search production (2024-2025)?
- Bugs connus pg_search, VectorChord, plpgsql_bm25?
- Maintenance: fréquence updates, breaking changes?
- Communauté: GitHub stars, issues, discussions actives?
- Comparaison pg_search vs Meilisearch/Typesense (si migration PostgreSQL → autre)?
- Best practices index BM25: création, tuning, monitoring?

### 7. Migration Path & Compatibility

**Questions**:
- pg_search, VectorChord: roadmap PostgreSQL 19, 20?
- Backward compatibility: migrations schema, index rebuild?
- Multi-version support: PostgreSQL 17 + 18 simultané?
- Docker deployment: images officielles, Dockerfile examples?

## Format Réponse Attendu

Produire un rapport structuré avec:

### Section 1: Tableau Comparatif Synthétique

Format Markdown, colonnes:
- Solution
- Installation (complexité 1-5)
- Performance (latency ms, Recall@10 %)
- Tokenization Code-Aware (Oui/Non/Partiel)
- Maturité (1-5)
- PostgreSQL 18 Compatible (Oui/Non/À vérifier)
- MnemoLite Fit Score (/10)

### Section 2: Analyse Détaillée par Solution

Pour chaque solution (pg_trgm, pg_search, VectorChord, plpgsql_bm25):
- Description technique (200-300 mots)
- Installation détaillée (commandes, dépendances)
- Code examples (SQL, configuration)
- Avantages (bullet points avec justifications)
- Inconvénients (bullet points avec impacts)
- Performance (benchmarks, sources)
- Use case optimal MnemoLite
- Score /10 (justifié)

### Section 3: Deep Dive Top 3 Solutions

Tableau comparatif approfondi:
- Architecture interne
- Tokenization examples (code snippets)
- Hybrid search patterns (SQL examples)
- Benchmarks side-by-side
- Production readiness assessment

### Section 4: Recommandation Finale

Format:
1. **Choix #1**: Solution + Raison (100 mots)
2. **Choix #2**: Solution + Raison (si #1 inadéquat)
3. **Choix #3**: Fallback

Chaque recommandation avec:
- Timeline implémentation (estimation jours)
- Risques identifiés
- Mitigations
- Upgrade path (v1.5.0, v1.6.0)

### Section 5: PostgreSQL 18 Specific Insights

- Nouvelles fonctionnalités impactant BM25/FTS
- Gains performance quantifiés (%)
- Recommandation migration PostgreSQL 18 (Oui/Non)

### Section 6: Références & Sources

Pour CHAQUE affirmation technique, benchmark, ou chiffre:
- Source URL
- Date publication
- Crédibilité (GitHub stars, auteur reconnu, paper peer-reviewed)

Format:
```
[1] pg_search documentation: https://docs.paradedb.com/... (2024, officiel)
[2] VectorChord benchmarks: https://github.com/tensorchord/... (2024, 87 stars)
[3] PostgreSQL 18 release notes: https://postgresql.org/... (2024, officiel)
```

## Critères Qualité Rapport

Je m'attends à:
1. **Exhaustivité**: Toutes solutions identifiées (pas seulement pg_search)
2. **Précision**: Chiffres sourcés, pas d'estimations vagues
3. **Actualité**: Recherches 2024-2025, pas d'infos obsolètes 2022-2023
4. **Objectivité**: Avantages ET inconvénients balancés
5. **Actionnable**: Recommendations concrètes avec steps implémentation
6. **Sourcé**: URLs, dates, GitHub repos, papers

Si une information est introuvable ou incertaine, le mentionner explicitement: "⚠️ Information non disponible, recommandation: vérifier manuellement [source]".

## Questions Bonus (si temps disponible)

- Comparaison BM25 PostgreSQL vs Elasticsearch BM25: différences algorithmes?
- Machine learning ranking (LTR) avec PostgreSQL + pgvector: faisable?
- Monitoring & observability: métriques BM25 à tracker?
- Cost analysis: pg_search vs Meilisearch cloud (si self-hosted non viable)?

## Contexte Additionnel

Mon analyse préliminaire actuelle:
- pg_trgm: MVP Phase 1-3, mature mais Recall~65-75%
- pg_search: Candidat v1.5.0 si Recall pg_trgm <80%, installation .deb triviale
- VectorChord: Candidat v1.6.0 si tokenization critique, compilation Rust complexe
- plpgsql_bm25: Fallback uniquement, performance PL/pgSQL limitée

Je cherche à **valider ou invalider** ces hypothèses avec données 2024-2025 récentes.

Merci de produire un rapport de 2000-3000 mots minimum, structuré, sourcé, et directement utilisable pour décision architecture.
```

---

## 📝 Instructions Utilisation

1. **Copier** le texte entre les ``` (prompt complet)
2. **Coller** dans Perplexity.ai (mode Pro recommandé pour recherches approfondies)
3. **Attendre** génération rapport (2-5 minutes)
4. **Sauvegarder** résultat dans `docs/perplexity_report_bm25_pg18.md`
5. **Analyser** et comparer avec `EPIC-06_BM25_DEEP_DIVE_PG18.md`

---

## 🎯 Résultat Attendu

**Rapport Perplexity.ai** devrait fournir:
- ✅ Comparaison exhaustive 4-5 solutions BM25
- ✅ Benchmarks chiffrés (sources récentes 2024-2025)
- ✅ Installation pg_search PostgreSQL 18 validée
- ✅ Tokenization code-aware: capacités réelles par solution
- ✅ Hybrid search patterns: SQL examples concrets
- ✅ Recommandation finale: choix #1, #2, #3 justifiés
- ✅ PostgreSQL 18 insights spécifiques
- ✅ 20-30 sources minimum (URLs, dates, crédibilité)

**Score qualité attendu**: 8-9/10 (vs 7/10 rapport embeddings précédent)

---

**Date**: 2025-10-15
**Auteur**: Équipe MnemoLite
**Usage**: Copy-paste dans Perplexity.ai
