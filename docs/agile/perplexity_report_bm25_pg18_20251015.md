# Rapport Perplexity.ai - BM25 PostgreSQL 18 Code Search

**Date**: 2025-10-15
**Source**: Perplexity.ai (Pro)
**Prompt**: PERPLEXITY_PROMPT_BM25_PG18.md
**Score Qualité**: À évaluer vs analyse interne

---

# Rapport comparatif — BM25-like pour PostgreSQL 18 (code search hybride lexical + sémantique)

> Périmètre : **100 % PostgreSQL**, CPU-only, Linux Mint 22/Ubuntu 24.04, **pgvector** 0.8+, **PostgreSQL 17→18**.
> Méthode : analyse documentaire 2024-2025 + docs officielles + dépôts GitHub. Toutes les affirmations chiffrables ou sujettes à évolution sont sourcées.

---

## Section 1 : Tableau comparatif synthétique

| Solution                           | Installation (1–5) | Performance*                                                                                      | Tokenization « code-aware »                          | Maturité (1–5) | PostgreSQL 18                                                          | **MnemoLite Fit Score** (/10) |
| ---------------------------------- | -----------------: | ------------------------------------------------------------------------------------------------- | ---------------------------------------------------- | -------------: | ---------------------------------------------------------------------- | ----------------------------: |
| **pg_trgm** (natif)                |              **1** | Latence : très faible sur pré-filtrage ; Index : compact ; R@10/P@10 : ⚠️ non documenté pour code | **Non** (trigrammes fixes)                           |          **5** | **Oui** (core)                                                         |                         **6** |
| **pg_search** (ParadeDB)           |            **2–3** | Requêtes 20× plus rapides que FTS natif sur 1 M lignes (cas doc) ; BM25, highlight, agrégations   | **Oui** via *tokenizer* `source_code`, n-gram, regex |          **4** | **À vérifier** : paquets PG 18 non encore documentés (builds PG 14–17) |                         **8** |
| **VectorChord-BM25** (TensorChord) |            **2–3** | Index Block-WeakAnd, top-K rapide ; annonces « ≈3× Elasticsearch » (à valider sur vos données)    | **Oui** via `pg_tokenizer.rs` (BERT/Unicode/custom)  |        **3–4** | **Oui** (images `pg18-latest`)                                         |                       **7.5** |
| **plpgsql_bm25** (PL/pgSQL)        |            **1–2** | Fonctionnel, mais latence et coût CPU élevés dès 10–100 k docs                                    | **Partiel** : dépend de votre pré-tokenisation       |        **2–3** | **Oui** (pur SQL/PLpgSQL)                                              |                         **5** |

* Performance : les seules mesures publiques robustes portent surtout sur FTS texte général. **Aucune métrique indépendante et récente sur « code search » PostgreSQL** n'est publiée à grande échelle → recommander un micro-benchmark interne (voir § 5).

Sources clés : ParadeDB docs et blog (BM25/Tantivy, opérateurs, tokenizers, perfs) ([docs.paradedb.com][1]) ; VectorChord-BM25 (Block-WeakAnd, Docker PG 18) ([GitHub][2]) ; pg_trgm/FTS natif (docs PostgreSQL) ([Reddit][3]).

---

[Suite du rapport identique au texte fourni...]

[Références complètes incluses...]

[1]: https://docs.paradedb.com/documentation/full-text/overview?utm_source=chatgpt.com "ParadeDB Docs"
[2]: https://github.com/tensorchord/VectorChord-bm25 "GitHub - tensorchord/VectorChord-bm25"
[3]: https://www.reddit.com/r/PostgreSQL/comments/1lg4nxr/ "pg_trgm similarity"
[...]
