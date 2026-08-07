# 🤖 EPIC-56 : Modèle CODE, dimension 1024 vs 768, échec de préchargement au boot

> **Status:** DONE (validé le 2026-08-07)
> **Priority:** P1 : seul bug préexistant documenté touchant la recherche de code
> **Date:** 2026-08-07
> **Effort:** 30 min à 1 h (réalisé en ~40 min, option B : 1 ligne + 2 tests)

## Problem Statement

À chaque boot de l'API, le préchargement du modèle CODE échouait :

```
ValueError: CODE model dimension mismatch: expected 1024, got 768
RuntimeError: Model pre-loading failed: Failed to load CODE model: ...
```

L'API continuait en dev (« Continuing in development mode without pre-loaded model »), mais **toute recherche de code était silencieusement dégradée** : le service hybride se créait à la demande avec `_code_model = None`, la composante code du dual embedding était inopérante.

## Cause racine (tranchée par diagnostic réel, H1 VRAIE)

`api/services/dual_embedding_service.py`, `_load_code_model_sync` (lignes ~211-232) : le check de dimension comparait le modèle CODE à `self.text_dimension` (1024, bge-m3) au lieu de `self.code_dimension` (768, jina-v2-base-code).

**Chaîne de preuves (diagnostic T1.1/T1.2, toutes concordantes) :**
- **T1.1** : chargement réel de `jinaai/jina-embeddings-v2-base-code` depuis le cache HF du conteneur → `DIMENSION_REELLE: 768`.
- **T1.2** : `api/core/embedding_models.py:82` : `KNOWN_MODELS[jina-embeddings-v2-base-code].dimension = 768` ; settings auto-infère `CODE_EMBEDDING_DIMENSION = 768` (settings.py ~254-258) ; `api/dependencies.py:284` transmet `code_dimension=768` ; colonne DB `code_chunks.embedding_code vector(768)` ; docstring du service : 768D.
- **H2 écartée** : pas de révision HF flottante (le modèle réel sort du 768, conforme à la spec). Aucun épinglage de révision nécessaire (T2.1 non retenu, YAGNI).

## Correctif appliqué (T2.2, option B)

`api/services/dual_embedding_service.py` : `if len(test_emb) != self.text_dimension:` → `if len(test_emb) != self.code_dimension:` (message d'erreur aligné sur `code_dimension`). Les modèles TEXT/CODE restent 768D réels ; le check de dimension reste actif (anti-régression).

## Stories / Tasks

| Story | Task | Statut |
|---|---|---|
| S1. Diagnostic tranché | T1.1 Snippet dimension réelle du modèle code | ✅ 768 |
| | T1.2 Vérification `code_dimension` auto-déduit vs check | ✅ H1 vraie, H2 écartée |
| S2. Correctif (selon S1) | T2.1 Épingler révision HF | ⬜ Non retenu (H2 écartée) |
| | T2.2 Corriger le check → `code_dimension` | ✅ 1 ligne |
| | T2.3 Lazy-loading au premier appel | ⬜ Non retenu (KISS) |
| S3. Tests | T3.1 `_load_code_model_sync` accepte 768 quand `code_dimension=768` | ✅ passe |
| | T3.2 Le check reste actif (mauvaise dimension → raise) | ✅ passe |
| S4. Validation | T4.1 Boot sans « dimension mismatch » + preload réel | ✅ voir ci-dessous |
| | T4.2 Recherche de code réelle, résultats non vides | ✅ 3 résultats |

## Fichiers modifiés

- `api/services/dual_embedding_service.py` : check de dimension (1 ligne + message).
- `tests/services/test_dual_embedding_service.py` : +2 tests (`test_code_model_load_accepts_768_when_code_dimension_768`, `test_code_model_load_rejects_wrong_dimension`).

## Validation (preuves réelles, 2026-08-07)

- **Tests ciblés** : 4 passes sur le sous-ensemble code (`code_model_load` ×2 + `lazy_loading_code_model` + `code_domain`). Delta fichier complet : **13 failed / 11 passed → 11 failed / 15 passed** (le fix répare 2 tests code existants).
- **T4.1 preload réel** : reproduction exacte du code du lifespan dans le conteneur (`preload_models()` avec les settings réels) → `PRELOAD_OK`, `code_model_loaded: True`, `text_model_loaded: True`.
- **T4.1 boot réel** (restart `mnemo-api`) : `GET /health` healthy ; circuit breakers `embedding_text` + `embedding_code` à `success_count: 1`, `failure_count: 0`, `state_changed_at` au boot (16:34:00) : la preuve que le préchargement a réussi pendant le boot (`record_success()` n'est appelé qu'après chargement). Aucun « dimension mismatch » dans les logs.
- **T4.2 recherche code** : encode réel `def authenticate(...)` → `EMBED_CODE_DIM: 768`, recherche vectorielle sur `code_chunks.embedding_code` → **3 résultats pertinents** (scores ≈ 0.37).

## Régressions

- Le modèle code n'est utilisé que dans `DualEmbeddingService` (`_ensure_code_model` aux lignes 523, 645, 797 ; `_code_model` aux lignes 651, 803). Le chemin texte (bge-m3) est strictement inchangé.
- **11 échecs préexistants documentés (hors périmètre, traités dans EPIC-57)** : tous côté TEXT/fixture du fichier de test : `mock_sentence_transformer.encode()` renvoie 768 alors que `dual_service` est instancié avec `text_dimension=1024` (le check TEXT lève) ; `test_get_stats` attend `stats["text_dimension"]` (KeyError, clé absente du dict) ; `test_initialization_with_env_defaults`. Échecs présents sur le code d'origine avant tout fix (baseline 13 failed).
- Note forensique : les logs structlog du préchargement n'apparaissent pas dans `docker logs` (buffering stdout pendant le lifespan) ; la preuve du succès passe par les circuit breakers (health) et le preload direct.
