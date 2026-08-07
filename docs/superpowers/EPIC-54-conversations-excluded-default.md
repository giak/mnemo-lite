# 🚫 EPIC-54 : Exclusion des conversations de la recherche par défaut (P5-a)

> **Status:** DONE
> **Priority:** P1 : Nettoie la recherche forensique
> **Date:** 2026-08-07
> **Effort:** 15 min + tests

## Problem Statement

Les transcriptions de conversations autosauvées représentent **33 629 mémoires sur 39 634 (84,8 %)**. Elles polluaient les recherches hybrides et par défaut, sans verdict forensique. Décision produit : les conversations ne doivent pas remonter par défaut, sauf si `memory_type=conversation` est demandé explicitement.

## Cause racine (vérifiée)

- `conversations_routes.py:508` pose `memory_type="conversation"` (écritures sans tags `project:*`/`status:*`).
- Aucun filtre d'exclusion n'existait dans les where builders.

## Stories / Tasks

| Story | Task | Statut |
|---|---|---|
| S1. Champ de filtre | T1.1 `MemoryFilters.exclude_conversations: bool = False` | ✅ |
| S2. Application aux where builders | T2.1 `search_by_tags` : `memory_type != 'conversation'` | ✅ |
| | T2.2 `search_by_vector` (fallback vectoriel) | ✅ |
| | T2.3 4 sous-recherches du service hybride | ✅ |
| S3. Activation par défaut | T3.1 MCP `search_memory` : `exclude_conversations = memory_type is None` | ✅ |
| | T3.2 REST `_search_memories` : idem | ✅ |
| S4. Tests | T4.1 `test_fallback_excludes_conversations_by_default` | ✅ |
| | T4.2 `test_explicit_memory_type_disables_conversation_exclusion` | ✅ |

## Fichiers

- `api/mnemo_mcp/models/memory_models.py` : +4 lignes.
- `api/db/repositories/memory_repository.py` : exclusion dans 2 builders.
- `api/services/hybrid_memory_search_service.py` : exclusion dans 4 builders.
- `api/mnemo_mcp/tools/memory_tools.py` : activation (fallback + hybride).
- `api/routes/memories_routes.py` : activation REST.
- `tests/mnemo_mcp/test_memory_search_tool.py` : +2 tests.

## Validation

- Smoke test SQL réel : « parrainages » avec exclusion → 28 résultats, **0 conversation**.
- Tests verts (2 nouveaux + les 43 existants).

## Régressions

- Le listing par tags sans `memory_type` exclut aussi les conversations (décision produit documentée) : les conversations autosauvées n'ont pas de tags `project:*`/`status:*`, l'impact est nul en pratique.
- Aucun autre caller de `MemoryFilters` cassé (champ optionnel, pas de `extra="forbid"` dans le modèle).
- Duplication du bloc d'exclusion (6×) : cohérent avec le pattern préexistant des where builders (dette documentée, pas de refactor YAGNI).
