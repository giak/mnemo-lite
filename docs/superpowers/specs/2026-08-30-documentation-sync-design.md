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

### Liste des 34 outils MCP réels (vérifiée sur le code)

La catégorisation ci-dessous est fondée sur le **fichier de définition réel** de
chaque outil (composant `BaseMCPComponent` dans `tools/*.py` ou déclaration inline
`@mcp.tool()` dans `server.py`/`register_*`). Ce n'est pas une taxonomie officielle
du code — chaque doc actuelle a sa propre taxonomie — mais elle sert de base
objective pour les corrections.

- **Mémoire (11)** — `memory_tools.py` : write_memory, read_memory, update_memory,
  delete_memory, search_memory, get_system_snapshot, mark_consumed, rate_memory,
  consolidate_memory, configure_decay, export_memories
- **Indexation (7)** — `indexing_tools.py` : index_project, index_incremental,
  index_markdown_workspace, reindex_file, get_indexing_status, get_indexing_errors,
  retry_indexing
- **Graphe code (4)** — `graph_tools.py` : get_graph_stats, traverse_graph,
  find_path, get_module_data
- **Analytics (4)** — `analytics_tools.py` : get_indexing_stats, get_memory_health,
  get_cache_stats, clear_cache
- **Entités (2)** — `server.py`/`register_entity_tools` : extract_entities,
  search_by_entity
- **Relations mémoire (2)** — `server.py`/`register_relationship_tools` :
  get_memory_graph, get_related_memories
- **Recherche code (1)** — `search_tool.py` : search_code
- **Config (1)** — `config_tools.py` : switch_project
- **Consolidation avancée (1)** — `server.py`/`register_consolidation_tools` :
  suggest_consolidation
- **Test (1)** — `test_tool.py` : ping

## Écarts identifiés par document

| Document | Anomalie vérifiée | Action |
|----------|-------------------|--------|
| `docs/MCP.md` | Annonce 31 outils ; manque `get_memory_graph`, `get_related_memories`, `suggest_consolidation` ; pas de catégorie Relationship/Consolidation | Réécrire la liste exacte (34) + catégories réelles + 12 ressources + transport Streamable HTTP |
| `docs/ARCHITECTURE.md` | TdM ligne 21 dit "MCP - 33 Outils", section ligne 705 dit "MCP - 31 Outils" (incohérence), corps dit "31 outils" (lignes 38, 50, 114, 962), ligne 114 "31 outils pour LLM" ; réel = 34 | Corriger les comptes (31/33 → 34) en 6 emplacements (21, 38, 50, 114, 705, 962) |
| `docs/QUICKSTART.md` | "31 outils" (ligne 24) | Corriger → 34 |
| `docs/README.md` | Ligne 16 "31 tools" (Features) ; ligne 39 "33 outils" (lien MCP.md) | Corriger → 34 |
| `README.md` (racine) | Ligne 41 header "31 tools" **et tableau qui ne liste que 29 outils** (manque `extract_entities`, `search_by_entity`, `get_memory_graph`, `get_related_memories`, `suggest_consolidation`), avec catégorisation erronée (`switch_project` classé "Analytics", `clear_cache`/`get_indexing_stats` classés "Indexing Ops") ; **ligne 90 "Protocole MCP (SSE)" — transport erroné** | Corriger le header (→34), compléter le tableau (5 outils manquants), recatégoriser, corriger le transport |
| `AGENTS.md` | Lignes 66-71 : total liste = 30 outils ; manque `extract_entities`, `search_by_entity`, `get_memory_graph`, `get_related_memories` ; `switch_project`+`ping` classés "Config (2)" | Synchroniser le tableau → 34 outils, catégories fidèles aux modules (Config: switch_project ; Test: ping) |
| `docs/API.md` | ~20 endpoints documentés / 120 réels ; paths memories corrects mais groupes entiers manquants (explorer, performance, monitoring advanced + alert-rules, graph, relationships `related`/`compute-relationships`, conversations, cache admin) | Reformuler en résumé exact des endpoints clés + renvoi Swagger ; ajouter groupes majeurs manquants |
| `MCP_SETUP.md` (racine) | **Transport déclaré SSE en 3 emplacements (lignes 34, 72, 510) alors que réel = Streamable HTTP** ; "31 tools" (lignes 18, 110) ; section signatures limitée à 8 outils | Réparer (transport, comptes) |
| `AUTOMATION_MNEMOLITE_SETUP.md` (racine) | Daté 2025-11-08, antérieur au refactor MCP v5 ; document d'ingénierie du workflow hooks (setup-new-project.sh, mnemo-init.sh), ne documente pas l'état courant | Archiver dans `docs/88_ARCHIVE/` |

**Note sur les catégories :** le code ne définit pas de taxonomie officielle ; chaque doc
a la sienne. La catégorisation de référence utilisée pour les corrections est celle
fondée sur les modules de définition (voir section précédente).

## Stratégie (validée)

1. **`docs/MCP.md` = référence MCP** : liste exacte des 34 outils par catégorie
   réelle fondée sur les modules (Mémoire 11, Indexation 7, Graphe code 4, Analytics 4,
   Entités 2, Relations mémoire 2, Recherche code 1, Config 1, Consolidation 1, Test 1),
   les 12 ressources MCP, le transport Streamable HTTP à :8002, et le nombre d'outils exact.
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
ressources ; ~120 routes HTTP) et `grep` sur toute la doc active pour s'assurer
qu'aucune mention "31 outils" / "33 outils" / "SSE (Server-Sent Events)" ne subsiste.

Commandes de vérification (source de vérité = code) :
- Outils MCP : `grep -rn '@mcp.tool(' api/mnemo_mcp/server.py` → attendu 34 déf
- Ressources : `grep -rn '@mcp.resource(' api/mnemo_mcp/server.py` → attendu 12 URIs
- Mentions obsolètes à éliminer :
  - `31 outils|31 tools` → 0 occurrence
  - `33 outils|33 tools` → 0 occurrence
  - `SSE|Server-Sent` → 0 occurrence (sauf dans AUTOMATION_MNEMOLITE_SETUP.md archivé si présent)
