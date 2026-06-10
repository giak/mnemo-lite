# EPIC-49 — Plan : Centralisation Configuration Embedding

> **Status:** DRAFT
> **Date:** 2026-06-10
> **Points:** ~8
> **Stories:** 4

## Contexte

Audit du 2026-06-10 : 19 fichiers dispersent la config d'embedding. Un changement de modèle (nomic→BGE-M3) a nécessité 30 min de debug pour un mismatch 768/1024 entre l'API et la DB. La cause racine : des hardcodes de dimensions (`768`, `1024`) et des `os.getenv` éparpillés sans validation centralisée.

## Current vs Target

| Composant | Current (fragmenté) | Target (centralisé) |
|-----------|--------------------|--------------------|
| Source de vérité | 5+ (`.env`, `docker-compose`, `sentence_transformer`, `vector_search`, `memory_search`) | 1 (`api/core/settings.py`) |
| Changement de modèle | Modifier 5-10 fichiers | Modifier 1 variable `.env` |
| Détection mismatch | Scores à 0.002, debug manuel | Crash immédiat avec message explicite |
| Hardcodes `768`/`1024` | 19 fichiers | 0 |
| Validation config | Aucune | Pydantic `@model_validator` |

## Stories

### Story 49.1 — Créer `api/core/` (2 pts)

**Phase:** P0 | **Priority:** Bloquant

**Problem:** Aucun module centralisé n'existe pour la config d'embedding.

**Solution:** Créer le module `api/core/` avec :
- `embedding_models.py` : registre statique `KNOWN_MODELS` (modèle → dimension, backend)
- `settings.py` : `AppSettings(BaseSettings)` avec `@model_validator` pour auto-déduction et validation
- Singleton via `@lru_cache` : `get_settings()`

**Validation:**
- `EMBEDDING_MODEL=BAAI/bge-m3` sans `EMBEDDING_DIMENSION` → auto-déduit 1024
- `EMBEDDING_MODEL=BAAI/bge-m3` avec `EMBEDDING_DIMENSION=768` → lève `ValueError`
- `EMBEDDING_MODEL=unknown-model` sans `EMBEDDING_DIMENSION` → lève `ValueError`

### Story 49.2 — Injecter dans les services (3 pts)

**Phase:** P0 | **Priority:** Bloquant

**Problem:** Les services lisent leur config via `os.getenv` ou des hardcodes.

**Solution:** Remplacer dans l'ordre :
1. `api/dependencies.py` — instancier `settings = get_settings()` et l'injecter
2. `api/services/vector_search_service.py` — remplacer `len(embedding) != 768` par `len(embedding) != self.dimension`
3. `api/services/memory_search_service.py` — remplacer `EXPECTED_EMBEDDING_DIM = 1024` par `settings.EMBEDDING_DIMENSION`
4. `api/services/sentence_transformer_embedding_service.py` — utiliser `settings.EMBEDDING_MODEL`
5. `api/services/dual_embedding_service.py` — utiliser `settings.EMBEDDING_DIMENSION` et `settings.CODE_EMBEDDING_DIMENSION`
6. `api/services/embedding_service.py` — utiliser `settings.EMBEDDING_DIMENSION`
7. `api/main.py` — remplacer les `os.getenv` fallbacks
8. `api/routes/memory_graph_routes.py` — idem

**Validation:**
- Tous les services lisent la même dimension depuis `get_settings()`
- Plus aucun `os.getenv("EMBEDDING_DIMENSION")` hors de `settings.py`

### Story 49.3 — Nettoyer configs externes (2 pts)

**Phase:** P0 | **Priority:** Important

**Problem:** `.env` et `docker-compose.yml` contiennent des valeurs redondantes/contradictoires.

**Solution:**
1. `.env` : supprimer `EMBEDDING_DIMENSION=1024` (auto-déduit), garder `EMBEDDING_MODEL=BAAI/bge-m3`
2. `docker-compose.yml` : supprimer `EMBEDDING_DIMENSION` du defaults, garder `EMBEDDING_MODEL`
3. Supprimer les constantes `EMBEDDING_MODELS` dans les services qui dupliquent le registre
4. Supprimer `simple_cache_service.py` → `[0.1] * 768` → utiliser `settings.EMBEDDING_DIMENSION`

**Validation:**
- `.env` minimal, docker-compose sans override de dimension
- Zéro duplication de la liste des modèles

### Story 49.4 — Scripts standalone (1 pt)

**Phase:** P1 | **Priority:** Standard

**Problem:** `reindex_bge_m3.py` a ses propres constantes (`MODEL_NAME`, `ONNX_MODEL_PATH`).

**Solution:**
1. Importer `get_settings()` dans `reindex_bge_m3.py`
2. Utiliser `settings.EMBEDDING_MODEL` au lieu de `MODEL_NAME`
3. Garder `ONNX_MODEL_PATH` et `USE_ONNX` comme config spécifique au script
4. Appliquer le même pattern à `reindex_memories_e5.py`, `backfill_memory_embeddings.py`

## Risques et Rollback

| Risque | Probabilité | Impact | Mitigation |
|--------|-----------|--------|-----------|
| Oubli d'un fichier avec hardcode | Moyenne | Faible | grep exhaustif pré-migration |
| Import circulaire `core/` → services | Faible | Bloquant | `core/` n'importe aucun service |
| Rétrocompatibilité `.env` existant | Faible | Moyen | Pydantic valide, ne crashe que si incohérent |
| DualEmbeddingService dimensions mixtes | Faible | Moyen | Testé via les tests existants |

**Rollback:** `git revert` du commit. Les changements sont isolés dans `api/core/` + modifications des services.

## Ordre d'exécution

```
49.1 (core/) → 49.2 (services) → 49.3 (nettoyage) → 49.4 (scripts)
     ↓                ↓                  ↓                ↓
  Création       Injection          Suppression       Adaptation
  registre +     dans tous les      des hardcodes     scripts
  settings       services           + .env cleanup    standalone
```
