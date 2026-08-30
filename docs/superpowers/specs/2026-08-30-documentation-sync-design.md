# Design — Synchronisation de la documentation MnemoLite avec l'état réel du code

**Date:** 2026-08-30
**Statut:** Validé (brainstorming)

## Contexte et Problème

Plusieurs documents de documentation active (hors `docs/88_ARCHIVE/`) ne sont plus
alignés avec l'état réel du code. Le désalignement a été **vérifié par outils**
(regex sur les déclarations réelles `@mcp.tool()`, extraction des routes FastAPI
via `include_router` et prefixes), pas supposé.

### Réalité vérifiée du code

- **Outils MCP enregistrés : 34** (déclarés par `@mcp.tool()` dans
  `api/mnemo_mcp/tools/*.py` et `api/mnemo_mcp/server.py`).
- **Ressources MCP enregistrées : 12** (`@mcp.resource()`).
- **Routes HTTP : ~120** (montées dans `api/main.py` via `include_router`).
- **Transport MCP : Streamable HTTP** (`mcp.streamable_http_app()`,
  `stateless_http=True`).
- **Version produit : v5.0.0-dev**, MCP SDK 1.12.3.

### Liste des 34 outils MCP réels

Catégorisation réelle (regroupement documentaire) :

- **Mémoire (12)** : write_memory, read_memory, update_memory, delete_memory,
  search_memory, get_system_snapshot, mark_consumed, rate_memory,
  consolidate_memory, suggest_consolidation, configure_decay, export_memories
- **Entités (2)** : extract_entities, search_by_entity
- **Relationship (2)** : get_memory_graph, get_related_memories
- **Indexation (7)** : index_project, index_incremental, index_markdown_workspace,
  reindex_file, get_indexing_status, get_indexing_errors, retry_indexing
- **Recherche code (1)** : search_code
- **Graphe code (4)** : get_graph_stats, traverse_graph, find_path, get_module_data
- **Analytics (4)** : get_indexing_stats, get_memory_health, get_cache_stats, clear_cache
- **Projet (2)** : switch_project, ping

## Écarts identifiés par document

| Document | Anomalie vérifiée | Action |
|----------|-------------------|--------|
| `docs/MCP.md` | Annonce 31 outils ; manque `get_memory_graph`, `get_related_memories`, `suggest_consolidation` ; pas de catégorie Relationship | Réécrire la liste exacte (34) + catégories réelles + 12 ressources + transport Streamable HTTP |
| `docs/ARCHITECTURE.md` | TdM dit "33 Outils", corps dit "31 outils" (incohérence interne) ; réel = 34 | Corriger les comptes (31/33 → 34) |
| `docs/QUICKSTART.md` | "31 outils" | Corriger → 34 |
| `docs/README.md` | "31 tools" dans Features, "33 outils" dans lien MCP | Corriger → 34 |
| `AGENTS.md` | Tableau 30 outils ; manque `extract_entities`, `search_by_entity`, `get_memory_graph`, `get_related_memories` | Synchroniser le tableau MCP → 34 regroupés par catégorie |
| `docs/API.md` | ~20 endpoints documentés / 120 réels ; paths memories corrects mais groupes entiers manquants (explorer, performance, monitoring advanced + alert-rules, graph, relationships `related`/`compute-relationships`, conversations, cache admin) | Reformuler en résumé exact des endpoints clés + renvoi Swagger ; ajouter groupes majeurs manquants |
| `MCP_SETUP.md` (racine) | **Transport déclaré SSE alors que réel = Streamable HTTP** ; "31 tools" ; section signatures limitée à 8 outils | Réparer (transport, comptes) |
| `AUTOMATION_MNEMOLITE_SETUP.md` (racine) | Daté 2025-11-08, antérieur au refactor MCP v5 ; document d'ingénierie du workflow hooks (setup-new-project.sh, mnemo-init.sh), ne documente pas l'état courant | Archiver dans `docs/88_ARCHIVE/` |

## Stratégie (validée)

1. **`docs/MCP.md` = référence MCP** : liste exacte des 34 outils par catégorie
   réelle (Mémoire, Entités, Relationship, Indexation, Recherche, Graphe,
   Analytics, Projet), les 12 ressources MCP, le transport Streamable HTTP à :8002,
   et le nombre d'outils exact.
2. **`AGENTS.md`** : synchroniser le tableau d'outils MCP (30 → 34) en respectant
   le format table existant.
3. **`docs/API.md`** : résumé exact des endpoints clés + renvoi explicite vers
   Swagger (`http://localhost:8001/docs`) pour l'exhaustif ; corriger les endpoints
   documentés pour les rendre exacts ; ajouter les groupes majeurs manquants
   (explorer, performance, monitoring, graph, relationships, conversations, cache).
4. **`docs/ARCHITECTURE.md`** : corriger les comptes d'outils MCP (31/33 → 34)
   et fiabiliser les incohérences restantes.
5. **`docs/QUICKSTART.md`** : corriger "31 outils" → 34.
6. **Racine `MCP_SETUP.md`** : réparer le transport (SSE → Streamable HTTP) et les
   comptes d'outils. **`AUTOMATION_MNEMOLITE_SETUP.md`** : archiver dans
   `docs/88_ARCHIVE/` (document d'ingénierie obsolète).
7. **README racine / `docs/README.md`** : corriger les comptes (31/33 → 34) si
   présents, vérifier cohérence globale.

## Périmètre explicite (limites)

- Ne **pas** toucher `docs/88_ARCHIVE/` (sauf ajout de l'archive d'AUTOMATION).
- Ne **pas** réécrire `docs/superpowers/` (notes épiques historiques).
- Ne **pas** modifier le code applicatif ni les tests ; seule la documentation
  change. Aucune modification de `Makefile`, configs, etc.
- `docs/API.md` reste un résumé, pas une référence exhaustive (renvoi Swagger).

## Non-ambiguïtés à lever

- Le nombre canonique d'outils MCP est **34** (vérifié sur le code) et s'applique
  à toutes les docs (REM / AGENTS / QUICKSTART / ARCHITECTURE / MCP_SETUP).
- Le transport MCP documenté partout est **Streamable HTTP** (SSE est obsolète).

## Vérification finale

Après modification : re-exécuter les scripts de comptage (34 outils MCP ; 12
ressources ; 120 routes) et `grep` sur les docs pour s'assurer qu'aucune mention
"31 outils" / "33 outils" / "SSE (Server-Sent Events)" ne subsiste dans la doc
active.
