# 🔀 EPIC-59 : REST, unifier les POST de recherche morts sur la logique hybride unique

> **Status:** BACKLOG (proposé le 2026-08-07)
> **Priority:** P2 : le GET fonctionne, mais des endpoints trompeurs restent exposés
> **Date:** 2026-08-07
> **Effort:** 1 h

## Problem Statement

Trois voies de recherche REST sont mortes ou trompeuses alors qu'une seule fonction hybride fiable existe :

- `POST /v1/search/` → `{"detail": "Search failed"}` (levé dans `api/services/memory_search_service.py:290` : `ServiceError("Search failed due to repository error")`).
- `POST /v1/search/content`, `POST /v1/search/similarity` → `{"data": []}` même sur requête existante.
- `POST /api/v1/memories/search` (body JSON) → vide ou erreur dans certains cas.
- **Seule voie fiable** : `GET /api/v1/memories/search?query=...` qui délègue à `_search_memories`, la même logique que `search_memory` MCP.

Le skill global documente déjà « ne pas utiliser POST /v1/search/ » : c'est un **contournement procédural**, pas une solution. Deux implémentations divergentes de la recherche = deux sources de vérité, risque de régression silencieuse.

## Cause racine (vérifiée dans le code le 2026-08-07)

- `api/services/memory_search_service.py:290` : lève `ServiceError` quand la recherche échoue au niveau repo (les routes qui l'appellent n'ont pas le même chemin de fallback que `_search_memories`).
- `_search_memories` (utilisé par `GET /api/v1/memories/search` et le MCP) embarque le fallback textuel EPIC-52 + l'exclusion conversations EPIC-54 : les POST ne passent pas par cette fonction.

## Stories / Tasks

| Story | Task | Statut |
|---|---|---|
| S1. Unification | T1.1 Inventorier les routes de recherche existantes (grep `v1/search`, `memories/search` dans `api/routes/` et `api/server.py`) | ⬜ |
| | T1.2 Faire déléguer `POST /v1/search/`, `/content`, `/similarity` et `POST /api/v1/memories/search` à la même fonction que le GET (`_search_memories`) | ⬜ |
| | T1.3 Supprimer ou marquer déprécié le chemin `memory_search_service` divergent s'il devient orphelin | ⬜ |
| S2. Tests | T2.1 `test_post_search_returns_same_as_get` : POST et GET sur la même requête → mêmes résultats (id et ordre) | ⬜ |
| | T2.2 `test_post_search_empty_body_422` : validation des entrées | ⬜ |
| | T2.3 `test_post_memories_search_json_body` : le body JSON (tags, memory_type) fonctionne | ⬜ |

## Fichiers

- `api/routes/memories_routes.py` (ou équivalent) : délégation des POST.
- `api/services/memory_search_service.py` : si le service devient orphelin, le supprimer (DRY) ou le faire appeler `_search_memories`.
- `tests/api/test_memories_routes.py` (étendre) ou `tests/api/test_search_routes.py`.

## Validation

- `POST /v1/search/` et `GET /api/v1/memories/search` renvoient des résultats identiques sur une requête type (« parrainages », « sys:anchor »).
- Le skill `mnemolite-mem-first` peut retirer la règle « ne pas utiliser POST /v1/search/ » (documenté, dépendance externe).

## Régressions

- Unification = un seul code path : les divergences GET/POST disparaissent par construction.
- Vérifier qu'aucun client existant (frontend, scripts) ne dépend du comportement vide actuel des POST (grep des appels).
