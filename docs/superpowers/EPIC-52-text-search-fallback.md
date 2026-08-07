# 🔍 EPIC-52 : Recherche textuelle par défaut (fallback lexical `search_by_text`)

> **Status:** DONE
> **Priority:** P0 : Élimine la classe d'erreur n°1 (query libre → 0 résultat)
> **Date:** 2026-08-07
> **Effort:** ~1 h + tests

## Problem Statement

Une query libre sans `search_mode` renvoyait **0 résultat** : le défaut `tag` est volontaire (anti cold-start, commentaire CRITICAL FIX) mais le fallback cherchait un **tag égal à la requête entière** (`effective_tags = [query_stripped]`) au lieu de chercher dans le texte. Aucune recherche textuelle n'existait dans `search_by_tags` (pg_trgm réservé à la dédup, sur le titre uniquement, lignes 861-899).

## Cause racine (vérifiée)

- `memory_tools.py` : `search_mode: str = "tag"` (défaut délibéré, documenté CRITICAL FIX anti cold-start 10-50 s vs timeout MCP 30 s).
- Fallback : `effective_tags = tags if tags else ([query_stripped] if is_tag_only else [])` → cherchait un tag littéral = requête.
- Aucune méthode ILIKE/full-text dans `memory_repository`.

## Stories / Tasks

| Story | Task | Statut |
|---|---|---|
| S1. Recherche textuelle dans le repo | T1.1 Paramètre `query_text: Optional[str]` sur `search_by_tags` | ✅ |
| | T1.2 Clause `(title ILIKE :qtN OR content ILIKE :qtN)` par mot, paramétrée | ✅ |
| | T1.3 Échappement des wildcards `%`/`_` via `ESCAPE '\'` (correctif de revue) | ✅ |
| S2. Branchement dans le fallback MCP | T2.1 Query libre → `search_by_tags(query_text=...)`, `search_mode="text"` | ✅ |
| | T2.2 Requête au pattern de tag (`^[a-z][a-z0-9_-]*(:[a-z0-9_.-]+)+$`, tags multi-colons inclus) → `tag_only` (comportement historique préservé) | ✅ |
| | T2.3 Texte libre avec deux-points (« loi 76-528 : parrainages ») reste en `text` | ✅ |
| S3. Tests | T3.1 `test_query_without_search_mode_uses_text_fallback` | ✅ |
| | T3.2 `test_tags_without_query_stays_tag_only` | ✅ |
| | T3.3 `test_colon_free_text_uses_text_fallback` | ✅ |
| | T3.4 Mise à jour de 2 tests documentant l'ancien comportement (`tag_only` → `text`) | ✅ |
| | T3.5 `test_multi_colon_tag_uses_tag_lookup` (tags imbriqués `sys:pattern:candidate`, correctif de revue) | ✅ |

## Fichiers

- `api/db/repositories/memory_repository.py` : +12 lignes.
- `api/mnemo_mcp/tools/memory_tools.py` : fallback réécrit (heuristique regex).
- `tests/mnemo_mcp/test_memory_search_tool.py` : +4 tests, 2 mis à jour.

## Validation

- Smoke test SQL réel (via conteneur api) :
  - « parrainages » → 28 résultats, 0 conversation, mémoire consolidée `58cc0e69` (introuvable hier par chaîne exacte) en **position 1**.
  - « loi 76-528 : parrainages » → 1 résultat.
  - « 100% parrainage » → 3 résultats (le `%` est traité littéralement).
- Tests : 23 passés sur `tests/mnemo_mcp/test_memory_search_tool.py` ; 44 passés sur `tests/mnemo_mcp/` (2 échecs préexistants hard delete, confirmés par stash).

## Régressions

- Callers de `search_by_tags` : seulement 2 (dans memory_tools, les miens). Signature backward compatible (paramètre optionnel en fin).
- Le cache key n'inclut pas `search_mode` (préexistant, sans impact : l'exclusion dérive de `memory_type`, présent dans la clé).
