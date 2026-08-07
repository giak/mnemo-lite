# 🗄️ EPIC-61 : Suite de tests DB fiable (mocks async, TEST_DATABASE_URL, asserts SQL drifés)

> **Status:** TODO (documenté le 2026-08-07, preuves capturées sur run réel)
> **Priority:** P1 : 11 tests DB cassés (8 failed + 3 errors), révélés par le run complet d'EPIC-57, préexistants prouvés par stash
> **Date:** 2026-08-07
> **Effort:** estimé 1 h à 1 h 30

## Problem Statement

Trois fichiers de tests DB ne passent pas. Preuve de préexistence : `git stash` (working tree net, sans les modifs EPIC-57) puis run des 3 fichiers → **identique : 8 failed, 31 passed, 3 errors en 0,60 s**.

```
FAILED tests/db/test_database.py::test_database_init_with_env_dsn
FAILED tests/db/test_database.py::test_database_init_with_default_dsn
FAILED tests/db/repositories/test_event_repository.py::test_search_vector_metadata_only
FAILED tests/db/repositories/test_event_repository.py::test_search_vector_vector_only
FAILED tests/db/repositories/test_event_repository.py::test_search_vector_hybrid
FAILED tests/db/repositories/test_event_repository.py::test_build_add_query
FAILED tests/db/repositories/test_event_repository.py::test_build_search_vector_query_vector_only
FAILED tests/db/repositories/test_event_repository.py::test_build_search_vector_query_hybrid
ERROR tests/db/repositories/test_computed_metrics_repository.py::test_create_computed_metrics
ERROR tests/db/repositories/test_computed_metrics_repository.py::test_update_coupling_metrics
ERROR tests/db/repositories/test_computed_metrics_repository.py::test_get_by_repository
```

## Cause racine (vérifiée par run réel, 2026-08-07)

### 1. `tests/db/test_database.py` (2 F) : singleton `get_settings` + format DSN

Le code réel (`api/db/database.py:51`) :

```python
self.dsn = dsn or get_settings().DATABASE_URL or "postgresql://user:password@localhost:5432/mnemolite_db"
```

Les tests font `monkeypatch.setenv("DATABASE_URL", "postgresql://testuser:testpass@testhost:5432/testdb")` puis `Database()`. **Le monkeypatch est inopérant** : `get_settings()` est un singleton pydantic-settings déjà instancié (cache), qui lit son env à la première instanciation, pas à chaque appel. Preuve du run réel :

```
E AssertionError: assert 'postgresql+a...432/mnemolite' == 'postgresql:/...t:5432/testdb'
+ postgresql+asyncpg://mnemo:mnemopass@db:5432/mnemolite
```

Deux problèmes superposés :
- **T1.1** : le DSN réel du conteneur (`postgresql+asyncpg://...`) est lu via le singleton, pas la valeur monkeypatchée.
- **T1.2** : le format réel est `postgresql+asyncpg://` (SQLAlchemy async) : `test_database_init_with_default_dsn` fait `assert "postgresql://" in db.dsn` → échoue car la chaîne est `postgresql+asyncpg://` (le `+asyncpg` casse la sous-chaîne `postgresql://`).

### 2. `test_event_repository.py` : search_vector (3 F) : mock async non résolu

`api/db/repositories/event_repository.py:280` (et zone similaire fallback) :

```python
db_result = await conn.execute(query_data, params_data)
rows = db_result.mappings().all()
```

Les tests mockent `conn.execute` avec un `AsyncMock` dont la valeur de retour n'est pas un objet avec `.mappings().all()`. Preuve du run réel :

```
ERROR:repository.event:Failed to search events: 'coroutine' object has no attribute 'all'
  File "/app/db/repositories/event_repository.py", line 280, in search_vector
    rows = db_result.mappings().all()
AttributeError: 'coroutine' object has no attribute 'all'
```

Le mock retourne un coroutine (AsyncMock non résolu ou mal chaîné) au lieu d'un faux `Result` SQLAlchemy avec `mappings()`.

### 3. `test_event_repository.py` : query builder (3 F) : asserts sur SQL obsolète

Le code réel (`api/db/query_builders/event_query_builder.py`) **inline le vecteur** au lieu d'utiliser un bind param, pour la compatibilité asyncpg (commentaire : « asyncpg cannot CAST text param to vector ») :

- `build_add_query` (ligne 77) : `embedding_sql = f"'{self._format_embedding_for_db(embedding)}'::vector"` → le SQL est `VALUES (:id, CAST(:content AS JSONB), CAST(:metadata AS JSONB), '{...}'::vector, :timestamp)` et `params` **ne contient plus `embedding`** (inline).
- `build_search_vector_query` (lignes 290, 363) : `vec_sql = f"'{...}'::vector"` → `embedding <-> '{...}'::vector AS similarity_score` et `params` n'a plus `vec_query` (inline), `dist_threshold` reste un param.

Les tests attendent l'ancien contrat :
- `test_build_add_query` : `assert "values (:id, cast(:content as jsonb), cast(:metadata as jsonb), :embedding, :timestamp)"` + `assert params["embedding"] == ...` → le SQL réel inline le vecteur et n'a pas `:embedding`.
- `test_build_search_vector_query_vector_only` / `_hybrid` : `assert "EMBEDDING <-> :VEC_QUERY AS SIMILARITY_SCORE"` + `params.get("vec_query")` → le SQL réel est `embedding <-> '{...}'::vector AS similarity_score`, pas de `vec_query`.

Preuve du run réel : les asserts échouent avec le SQL compilé réel affiché en diff.

### 4. `test_computed_metrics_repository.py` (3 E) : `TEST_DATABASE_URL` vide en contexte pytest

Les 3 tests (`test_create_computed_metrics`, `test_update_coupling_metrics`, `test_get_by_repository`) sont des tests d'intégration réelle : fixture `clean_db` → `test_engine` → `test_db_url` (`tests/conftest.py:88`) :

```python
test_db_url = get_settings().TEST_DATABASE_URL
if not test_db_url:
    raise ValueError("TEST_DATABASE_URL environment variable not set")
```

**ERROR at setup** pour les 3 : `get_settings().TEST_DATABASE_URL` est vide dans le process pytest du conteneur api (alors que l'env du conteneur affiche `TEST_DATABASE_URL=***` défini : la valeur lue par pydantic-settings au moment de l'instanciation diffère, probablement un ordre de chargement .env / env du conteneur, ou un `env_prefix`). À diagnostiquer : pourquoi le singleton settings ne voit pas la valeur alors que `docker exec env` la montre.

## Correctifs proposés

| Fichier | Correctif | Risque |
|---|---|---|
| `tests/db/test_database.py` | **T1** : patcher `get_settings` (ou `get_settings.cache_clear()` + setenv avant la 1re instanciation) pour que `DATABASE_URL` soit contrôlable ; **T2** : assert sur `postgresql+asyncpg://` ou normaliser le DSN du test. Le plus robuste : monkeypatch de `db.database.get_settings` (mock avec `DATABASE_URL` choisi). | Faible : tests unitaires purs, pas de DB. |
| `tests/db/repositories/test_event_repository.py` (search_vector ×3) | **T3** : mock `conn.execute` → retourner un faux résultat avec `.mappings()` → `.all()`/`.first()` résolus (AsyncMock correctement chaîné). Copier le pattern des autres tests du fichier qui passent (ex. `test_get_by_id`/`add` réussis). | Faible : tests unitaires mockés. |
| `tests/db/repositories/test_event_repository.py` (query builder ×3) | **T4** : aligner les asserts sur le SQL réel : `'{...}'::vector` inline, absence de `vec_query`/`embedding` dans params (inline), `dist_threshold` reste bindé. Vérifier aussi `_format_embedding_for_db` en sortie. | Faible : asserts textuels à jour. |
| `tests/db/repositories/test_computed_metrics_repository.py` (×3) | **T5** : (a) diagnostiquer pourquoi `get_settings().TEST_DATABASE_URL` est vide dans pytest alors que l'env du conteneur l'a (ordre de chargement, env_prefix) et corriger la config du conteneur ; OU (b) si la DB de test n'est pas garantie dispo, ajouter un skip propre (pattern de `tests/test_search_routes.py:311` : « skipping direct connection test ») au lieu d'un ERROR setup. | Moyen : touche aux fixtures session. |

## Stories / Tasks

| Story | Task | Statut |
|---|---|---|
| S1. test_database (2 F) | T1.1 Patcher `get_settings` pour contrôler `DATABASE_URL` | ⬜ |
| | T1.2 Asserts alignés sur format DSN réel (`postgresql+asyncpg://`) | ⬜ |
| S2. search_vector mocks (3 F) | T2.1 Mock `conn.execute` → résultat `.mappings().all()` résolu | ⬜ |
| | T2.2 Run vert du fichier event_repository complet | ⬜ |
| S3. query builder asserts (3 F) | T3.1 Asserts alignés sur SQL inline `'{...}'::vector` | ⬜ |
| | T3.2 Vérifier params (plus de `vec_query`/`embedding`, `dist_threshold` bindé) | ⬜ |
| S4. computed_metrics (3 E) | T4.1 Diagnostiquer TEST_DATABASE_URL vide en pytest (vs env conteneur) | ⬜ |
| | T4.2 Corriger la config OU skip propre (pattern test_search_routes) | ⬜ |
| S5. Validation | T5.1 Les 3 fichiers verts : 0 failed, 0 error | ⬜ |
| | T5.2 Collecte complète inchangée : 1643 tests, 0 erreur | ⬜ |
| | T5.3 Aucune régression sur les fichiers EPIC-57 (95/95) | ⬜ |

## Fichiers concernés

- `tests/db/test_database.py` (2 tests)
- `tests/db/repositories/test_event_repository.py` (6 tests)
- `tests/db/repositories/test_computed_metrics_repository.py` (3 tests)
- `tests/conftest.py` (fixture `test_db_url`, seulement si T4.1/T4.2 touche la config)
- Référence lecture seule : `api/db/database.py`, `api/db/query_builders/event_query_builder.py`, `api/db/repositories/event_repository.py`

## Validation (critères d'acceptation)

1. `pytest tests/db/ -q` → **0 failed, 0 error** (avant : 8 F + 3 E).
2. Le run complet hors e2e/integration se collecte toujours sans erreur (1643).
3. Les fichiers réparés dans EPIC-57 restent verts (95/95), aucun changement de code prod DB.

## Régressions attendues

- **Aucun changement de code prod** dans le périmètre de cette EPIC : uniquement des tests (et éventuellement la config du conteneur de test pour T4). Le comportement réel (inline vector pour asyncpg) est le comportement correct documenté par le commit `5555351` ; les tests doivent s'y aligner, pas l'inverse.
