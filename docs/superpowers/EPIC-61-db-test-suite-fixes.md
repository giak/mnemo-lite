# 🗄️ EPIC-61 : Suite de tests DB fiable (mocks async, TEST_DATABASE_URL, asserts SQL drifés)

> **Status:** ✅ DONE (implémenté et validé le 2026-08-07 : 42/42 sur les 3 fichiers, 77/77 sur tests/db/)
> **Priority:** P1 : 11 tests DB cassés (8 failed + 3 errors), révélés par le run complet d'EPIC-57, préexistants prouvés par stash
> **Date:** 2026-08-07
> **Effort:** estimé 1 h à 1 h 30 (réalisé en session : diagnostic + fix + validation)

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

## Causes racines réelles (diagnostic 2026-08-07, vérifié par repro dans le conteneur)

### T1. test_database (2 F) : singleton `get_settings` non rafraîchi

Hypothèse initiale confirmée et affinée : le monkeypatch env est inopérant car `get_settings()` est un `lru_cache` instancié avant le test. **Fix appliqué** (pattern déjà utilisé par `test_dsn_priority_order` qui passait) : `get_settings.cache_clear()` après chaque mutation d'env (`mock_env_vars` + `default_dsn`). `test_database_init_with_default_dsn` retombe alors sur le fallback codé en dur → l'assert `"postgresql://" in db.dsn` redevient vrai.

### T2. search_vector (3 F) : mock branché sur `connect()` mais le code utilise `engine.begin()`

**Cause racine réelle (différente de l'hypothèse T3 initiale)** : le code (`event_repository.py:275`) fait `async with self.engine.begin() as conn:` mais les tests configurent `mock_engine.connect.return_value.__aenter__.return_value = mock_connection` → `conn` n'est jamais `mock_connection` (c'est un AsyncMock par défaut dont `.execute()` retourne une coroutine). Preuve par repro dans le conteneur : `conn is mc: False` → `db_result` = coroutine → `'coroutine' object has no attribute 'all'`.

**Deuxième cause superposée** : depuis l'ajout de `SET LOCAL ivfflat.probes = 100`, `search_vector` exécute `conn.execute` **3 fois** quand `vector is not None` (SET LOCAL, search, count) au lieu de 2. Fix : `mock_engine.begin.return_value.__aenter__.return_value = mock_connection` + `side_effect` à 3 éléments pour vector_only/hybrid + `await_count == 3` + indexes 1 et 2 dans `await_args_list`. Metadata_only (vector=None) garde 2 appels.

### T3. query builder (3 F) : asserts sur l'ancien contrat

Hypothèse initiale confirmée : le builder inline le vecteur (`'{...}'::vector`) pour asyncpg. Fix : asserts alignés sur le SQL réel (`VALUES (... '{expected_vec}'::vector, :timestamp)`), suppression des asserts `params["embedding"]` / `params["vec_query"]` remplacés par `assert "embedding" not in params` / `assert "vec_query" not in params` (inline), `dist_threshold` reste bindé.

### T4. computed_metrics (3 E) : pollution du singleton par `patch.dict(clear=True)`

**Cause racine réelle** : ce ne sont PAS les 3 tests qui sont en cause, mais `test_dsn_priority_order` (tests/db/test_database.py, exécuté avant computed_metrics dans le run) : son dernier bloc `patch.dict(os.environ, {}, clear=True)` + `cache_clear()` reconstruit le singleton settings avec un env **vidé** (sans `TEST_DATABASE_URL`), et ce snapshot reste dans le lru_cache → `test_db_url` (session-scoped, tests/conftest.py:99) lève `ValueError` au setup des 3 tests. Fix : `get_settings.cache_clear()` après le bloc, pour re-populer le cache avec l'env réel du conteneur.

## Correctifs appliqués

| Fichier | Correctif appliqué | Résultat |
|---|---|---|
| `tests/db/test_database.py` | `get_settings.cache_clear()` dans `mock_env_vars` + après `delenv` dans `default_dsn` + restauration du cache en fin de `test_dsn_priority_order` (anti-pollution session) | 17/17 |
| `tests/db/repositories/test_event_repository.py` (search_vector ×3) | `mock_engine.begin.return_value.__aenter__.return_value = mock_connection` + side_effect 3 éléments (SET LOCAL) + await_count 3 + indexes 1/2 | 19/19 |
| `tests/db/repositories/test_event_repository.py` (query builder ×3) | Asserts alignés sur SQL inline `'{...}'::vector`, suppression des params obsolètes | idem |
| `tests/db/repositories/test_computed_metrics_repository.py` (×3) | Aucune modif des tests : le fix est la restauration du cache settings dans test_database.py (pollution inter-fichiers) | 3/3 |

## Stories / Tasks

| Story | Task | Statut |
|---|---|---|
| S1. test_database (2 F) | T1.1 `get_settings.cache_clear()` après mutations env (fixture + tests) | ✅ |
| | T1.2 Asserts DSN valides via fallback réel (post-`cache_clear`) | ✅ |
| S2. search_vector mocks (3 F) | T2.1 Mock `engine.begin()` (pas `connect()`), cause racine réelle | ✅ |
| | T2.2 side_effect 3 éléments (SET LOCAL) + await_count 3 + indexes 1/2 | ✅ |
| S3. query builder asserts (3 F) | T3.1 Asserts alignés sur SQL inline `'{...}'::vector` | ✅ |
| | T3.2 `embedding`/`vec_query` absents de params, `dist_threshold` bindé | ✅ |
| S4. computed_metrics (3 E) | T4.1 Diagnostic : pollution du singleton par `patch.dict(clear=True)` de test_dsn_priority_order | ✅ |
| | T4.2 Restauration du cache settings en fin de test_dsn_priority_order (anti-pollution session) | ✅ |
| S5. Validation | T5.1 Les 3 fichiers verts : **42/42** (0 failed, 0 error) | ✅ |
| | T5.2 `tests/db/` complet : **77/77** | ✅ |
| | T5.3 Aucun changement de code prod DB (uniquement tests) | ✅ |

## Fichiers concernés

- `tests/db/test_database.py` (2 tests)
- `tests/db/repositories/test_event_repository.py` (6 tests)
- `tests/db/repositories/test_computed_metrics_repository.py` (3 tests)
- `tests/conftest.py` (fixture `test_db_url`, seulement si T4.1/T4.2 touche la config)
- Référence lecture seule : `api/db/database.py`, `api/db/query_builders/event_query_builder.py`, `api/db/repositories/event_repository.py`

## Validation (résultats réels 2026-08-07)

1. ✅ `pytest tests/db/ -q` → **77 passed, 0 failed, 0 error** (avant : 8 F + 3 E).
2. ✅ Les 3 fichiers ciblés → **42 passed** (2 runs stables).
3. ✅ Aucun changement de code prod DB (3 fichiers de tests modifiés uniquement).

## Hors périmètre (préexistants documentés, EPIC-57)

- `tests/test_search_routes.py::test_search_vector_only_found` : drift dimension colonne `vector(768)` vs service 1024 (bge-m3), préexistant prouvé par stash en EPIC-57.
- `tests/test_pgvector_optimizations.py::test_halfvec_search_returns_results` : même famille (vecteur 1024 requis par le service vs fixture 768), préexistant vérifié par stash (1 failed sur HEAD).

## Régressions attendues

- **Aucun changement de code prod** dans le périmètre de cette EPIC : uniquement 3 fichiers de tests. Le comportement réel (inline vector pour asyncpg, `engine.begin()` avec SET LOCAL) est le comportement correct ; les tests s'y alignent, pas l'inverse.
