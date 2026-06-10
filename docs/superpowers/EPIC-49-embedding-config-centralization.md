# 🔧 EPIC-49 : Centralisation de la Configuration d'Embedding

> **Status:** DRAFT
> **Priority:** P0 — Bloque toute migration future de modèle
> **Inspiration:** Bug du 2026-06-10 — 30 min de debug pour un mismatch 768/1024
> **Effort:** ~8 points (~6h)
> **Date:** 2026-06-10
> **Philosophy:** Single Source of Truth, Fail Fast, Convention over Configuration

## Problem Statement

La configuration d'embedding est éparpillée dans **19 fichiers** à travers la codebase. Changer de modèle (ex: nomic→BGE-M3) nécessite de modifier 5 à 10 fichiers manuellement, avec des hardcodes de dimensions (768, 1024) et des noms de modèles dupliqués.

### Incident du 2026-06-10

30 minutes de debug parce que :
1. `vector_search_service.py` bloquait les vecteurs >768D (hardcodé `len(embedding) != 768`)
2. `.env` pointait vers `multilingual-e5-base` (768D) au lieu de BGE-M3 (1024D)
3. `docker-compose.yml` avait des defaults en 768
4. La DB stockait des embeddings 1024D mais l'API encodait les requêtes en 768D
5. Résultat : scores de recherche à 0.002 — bruit aléatoire

### Amplitude du problème

| Catégorie | Fichiers | Exemples de hardcodes |
|-----------|----------|----------------------|
| Services d'embedding | 5 | `dimension=768`, `EXPECTED_EMBEDDING_DIM=1024` |
| Services de recherche | 3 | `len(embedding) != 768`, dimension defaults |
| Injection/dependencies | 3 | `os.getenv("EMBEDDING_DIMENSION", "768")` |
| Config externe | 2 | `.env`, `docker-compose.yml` |
| Scripts standalone | 2 | `MODEL_NAME`, `ONNX_MODEL_PATH` |
| Autres (MCP, routes, cache) | 4 | `[0.1] * 768`, dimension checks |

## Target State

**Une seule variable** `EMBEDDING_MODEL=BAAI/bge-m3` dans `.env` propage automatiquement la dimension, le backend, et le modèle dans **tous** les services.

```
AVANT (fragmentation)                    APRÈS (centralisé)
┌──────────────────────┐                ┌──────────────────────┐
│ .env                 │                │ .env                 │
│ docker-compose.yml   │                │   EMBEDDING_MODEL    │
│ sentence_transformer │                │   = BAAI/bge-m3      │
│ vector_search (768!) │    ═══════►    └──────────┬───────────┘
│ memory_search (1024) │                          │
│ dual_embedding       │                ┌─────────▼───────────┐
│ dependencies.py      │                │ api/core/settings.py│
│ main.py              │                │  → dimension: 1024  │
│ memory_graph_routes  │                │  → backend: pytorch │
│ simple_cache [0.1]*768│               │  → validated        │
│ reindex_bge_m3       │                └─────────┬───────────┘
│ ... (9 autres)       │                          │ injecté dans
└──────────────────────┘                ┌─────────▼───────────┐
                                        │ TOUS les services   │
                                        │ via get_settings()  │
                                        └─────────────────────┘
```

## Architecture

```
api/core/                     ← Nouveau module
├── embedding_models.py       ← Registre statique KNOWN_MODELS
└── settings.py               ← Pydantic BaseSettings + validation
```

- **pydantic-settings** (déjà dans le projet)
- **@model_validator** pour auto-déduction dimension/backend
- **Crash au démarrage** si config incohérente (message explicite)
- **Singleton via lru_cache** — calculé une seule fois

## Stories

| # | Story | Points | Description |
|---|-------|--------|-------------|
| 49.1 | Créer `api/core/` avec registre + settings | 2 | `embedding_models.py` + `settings.py` + validation |
| 49.2 | Injecter dans les services fondamentaux | 3 | `dependencies.py`, `vector_search`, `memory_search`, `dual_embedding`, `sentence_transformer` |
| 49.3 | Nettoyer les hardcodes et configs externes | 2 | `.env`, `docker-compose.yml`, suppression des `768`/`1024` hardcodés |
| 49.4 | Adapter les scripts standalone | 1 | `reindex_bge_m3.py`, `reindex_memories_e5.py` |

## Success Criteria

1. ✅ Modifier `EMBEDDING_MODEL` dans `.env` → tous les services utilisent la bonne dimension
2. ✅ Crash au démarrage avec message clair si `EMBEDDING_MODEL=BAAI/bge-m3` mais `EMBEDDING_DIMENSION=768`
3. ✅ Zéro hardcode de `768`, `1024`, ou noms de modèles dans les services
4. ✅ Les scripts standalone (`reindex_bge_m3.py`) lisent la même config que l'API
5. ✅ Rétrocompatibilité : le `.env` et `docker-compose.yml` existants continuent de fonctionner
6. ✅ Tests : un switch de modèle (BGE-M3→nomic) fonctionne sans modifier le code
ENDDOFFILE

echo 'EPIC-49 created' && wc -l /home/giak/Work/MnemoLite/docs/superpowers/EPIC-49-embedding-config-centralization.md
