# 🅿️ EPIC-70 : Parking code - suspension du volet code (traitement différé)

> **Status:** PARKED (créé le 2026-08-08, décision utilisateur : focus sur la recherche vectorielle/sémantique TEXTE ; tout le volet « code » est mis en pause)
> **Priority:** P3 (différé, aucune urgence fonctionnelle : la recherche TEXT memories/events est 100 % opérationnelle)
> **Date:** 2026-08-08
> **Effort:** non évalué (reprise ultérieure)

## Problem Statement

Décision du 2026-08-08 : l'intérêt actuel porte sur la **recherche vectorielle et sémantique TEXTE**
(mémoires, events), pas sur le code. Cette EPIC consolide **tous** les problèmes relatifs au volet
« code » (indexation `code_chunks`, recherche de code, MCP code) constatés lors du point d'audit du
2026-08-08, pour un traitement différé. Elle **absorbe l'EPIC-69** (migration `code_chunks` TEXT
768 → 1024) et la met en pause.

## Périmètre consolidé (faits vérifiés le 2026-08-08)

### S1. EPIC-69 absorbée : migration `code_chunks` TEXT 768 → 1024
- Table `code_chunks` : 53 268 lignes, **4 colonnes d'embedding en 768D** (`embedding_text`,
  `embedding_text_half`, `embedding_code`, `embedding_code_half`).
- Couverture réelle : `embedding_text` = **120 / 53 268 (0,2 %)** ; `embedding_code` = **19 348 / 53 268 (36 %)**.
- Le domaine TEXT (bge-m3, 1024D) est **cassé** : les insertions 1024D échouent sur les colonnes
  `vector(768)` (DataError silencieux). CODE (jina-code, 768D) passe.
- Référence : `EPIC-69-code-chunks-migration-1024.md` (stories S2-S5 complètes, migration SQL
  v12→v13, backfill, tests) → **absorbée ici, traitée à la reprise**.

### S2. `truth-engine` : 33 717 chunks sans AUCUN embedding
- `truth-engine` = 33 717 chunks (63 % du total), indexés le **2026-07-13** (avant la migration
  bge-m3) : **0 embedding code, 0 embedding text**.
- Conséquence : la recherche sémantique de code sur truth-engine (notre projet principal) est
  **inopérante** ; seule la recherche lexicale fonctionne (testée : OK).
- À la reprise : re-indexation ou backfill `embedding_code` pour `truth-engine` (le backfill TEXT
  seul ne suffit pas).

### S3. Artefact MCP `get_indexing_status` → `never_indexed`
- `get_indexing_status(repository='default')` renvoie `never_indexed` alors que l'index code existe
  (53 268 chunks). Cause : la requête filtre sur `repository = :repo` et **aucun chunk ne porte le
  nom `default`** (vrais noms : `truth-engine`, `mnemolite-python`, `code_test_*`, etc.).
- À la reprise : corriger la logique de statut (agréger par nom de repo réel, ou mapper `default`).

### S4. Endpoints REST code search : embedding exigé côté client
- `POST /v1/code/search/hybrid` et `/vector` exigent un embedding **pré-calculé côté client**
  (`embedding_text`/`embedding_code`, 768D). Appel avec `query` seul → `Embedding must be a
  768-dimensional vector` (testé le 2026-08-08).
- À la reprise : décider si le serveur doit encodrer la query (cohérence avec la voie TEXT
  memories) ou documenter clairement le contrat.

### S5. Symptôme observé : mismatch de dimension du modèle CODE au boot
- Log au boot (ancien boot 15:39) : `CODE model dimension mismatch: expected 1024, got 768`.
- À re-diagnostiquer à CPU libre (contexte EPIC-56/EPIC-69 : CODE = jina-code 768D vs attentes
  d'adaptateur). Non bloquant pour la voie TEXT.

### S6. `indexing_errors` : 33 erreurs
- Top : « no chunks generated » (17). À auditer à la reprise (mineur).

## Contre-expertise : ce qui fonctionne (hors périmètre, ne pas casser)

- **Voie TEXT (focus actuel)** : `memories` 39 567/39 567 (100 %, 1024D) et `events` 3 784/3 784
  (100 %, 1024D), recherche vectorielle prouvée (122 ms, pertinence correcte).
- **Recherche code lexicale** : opérationnelle sur tous les repos (`/v1/code/search/lexical` testé OK).
- Health code search : healthy, 3/3 tables.

## Stories / Tasks (reprise ultérieure)

| Story | Task | Statut |
|---|---|---|
| S1. Migration TEXT code_chunks | T1.1 Appliquer EPIC-69 (SQL v12→v13, backfill, tests) | ⬜ PARKED |
| S2. truth-engine | T2.1 Backfill/re-index embeddings code pour `truth-engine` (33 717 chunks) | ⬜ PARKED |
| S3. MCP statut | T3.1 Corriger `get_indexing_status` (agrégation par repo réel) | ⬜ PARKED |
| S4. REST code | T4.1 Décider serveur-side embedding vs contrat documenté | ⬜ PARKED |
| S5. Modèle CODE | T5.1 Re-diagnostiquer le mismatch 768/1024 à CPU libre | ⬜ PARKED |
| S6. Erreurs | T6.1 Auditer les 33 `indexing_errors` | ⬜ PARKED |

## Règle de reprise

Toute session touchant `code_chunks`, `HybridCodeSearchService`, `search_code` MCP, ou la recherche
de code doit **d'abord** lire cette EPIC et l'EPIC-69 absorbée, et confirmer que le focus TEXT
(memories/events) reste intact (pas de régression sur `_expected_dim_for_domain` hors code).

## Validation

- Aucune validation de code : EPIC de parking pur, créée le 2026-08-08 après audit d'indexation.
- À la reprise : suivre les stories S1-S6 ci-dessus.
