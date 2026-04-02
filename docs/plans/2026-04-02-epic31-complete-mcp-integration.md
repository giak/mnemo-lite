# EPIC-31: Complete MCP Integration — Phase 2

**Status**: DRAFT | **Created**: 2026-04-02 | **Effort**: ~12 points | **Stories**: 4

---

## Context

EPIC-23 (MCP Integration) est à 48%. La Phase 1 est complète (16 outils MCP, 358 tests passing).
La Phase 2 ajoute les capacités avancées nécessaires pour les workflows d'agents AI complets.

### Ce qui existe déjà (Phase 1)
- ✅ 16 outils MCP (search_code, search_memory, write/update/delete/read_memory, index_project, etc.)
- ✅ System snapshot (core, patterns, extensions, protocols, traces, profile, project)
- ✅ Health metrics dans le snapshot
- ✅ Configuration tools (switch_project, list_projects)
- ✅ Analytics tools (clear_cache)
- ✅ 358/358 tests passing

### Ce qui manque (Phase 2)
- ❌ Code graph resources MCP (traverse, path, module analysis)
- ❌ Analytics tools avancés (cache stats, indexing stats)
- ❌ Indexing observability (progress, errors, retry)
- ❌ Security/auth layer (API keys, rate limiting)

---

## Stories

### Story 31.1: Code Graph MCP Resources
**Priority**: P0 | **Effort**: 3 pts | **Value**: High

Exposer les capacités du graphe de code via MCP pour les agents.

**Outils à créer** :
- `get_graph_stats(repository)` — Statistiques du graphe (nodes, edges, modules)
- `traverse_graph(node_id, direction, depth)` — Navigation dans le graphe
- `find_path(source_id, target_id)` — Chemin entre deux nodes
- `get_module_data(repository, module_path)` — Données d'un module

**Fichiers à créer** :
- `api/mnemo_mcp/tools/graph_tools.py`
- `api/mnemo_mcp/models/graph_models.py` (si pas existant)

**Fichiers à modifier** :
- `api/mnemo_mcp/server.py` — Enregistrer les nouveaux outils

---

### Story 31.2: Analytics MCP Tools
**Priority**: P1 | **Effort**: 2 pts | **Value**: Medium

Outils d'analytics pour les agents.

**Outils à créer** :
- `get_cache_stats()` — Statistiques du cache L1/L2
- `get_indexing_stats(repository)` — Statistiques d'indexation
- `get_search_stats()` — Statistiques de recherche (popular queries, hit rate)
- `get_memory_health()` — Santé de la mémoire (embeddings, decay, consolidation)

**Fichiers à créer** :
- `api/mnemo_mcp/tools/analytics_tools.py`

---

### Story 31.3: Indexing Observability
**Priority**: P0 | **Effort**: 3 pts | **Value**: High

Suivi en temps réel de l'indexation pour les agents.

**Outils à créer** :
- `get_indexing_status(repository)` — Status actuel (idle, scanning, indexing, done, error)
- `get_indexing_errors(repository)` — Erreurs récentes d'indexation
- `retry_indexing(repository, file_paths)` — Relancer l'indexation de fichiers spécifiques

**Fichiers à créer** :
- `api/mnemo_mcp/tools/indexing_observability_tools.py`

**Fichiers à modifier** :
- `api/mnemo_mcp/server.py` — Enregistrer les nouveaux outils

---

### Story 31.4: MCP Security & Auth Layer
**Priority**: P1 | **Effort**: 4 pts | **Value**: High

Sécuriser l'accès MCP pour la production.

**Fonctionnalités** :
- API key authentication (mode `api_key`)
- Rate limiting par clé API
- CORS configuration
- Audit logging des appels d'outils
- Tool-level permissions (certains outils réservés aux admins)

**Fichiers à créer** :
- `api/mnemo_mcp/middleware/auth.py`
- `api/mnemo_mcp/middleware/rate_limit.py`
- `api/mnemo_mcp/config/security_config.py`

**Fichiers à modifier** :
- `api/mnemo_mcp/server.py` — Intégrer les middlewares
- `api/mnemo_mcp/tools/memory_tools.py` — Permissions par outil

---

## Critères de complétion

- [ ] 4 nouveaux outils graph MCP fonctionnels
- [ ] 4 outils analytics MCP fonctionnels
- [ ] Indexing observability en temps réel
- [ ] Auth API key + rate limiting
- [ ] EPIC-23 à 100% complet
- [ ] Tests pour tous les nouveaux outils

---

## Ordre d'exécution

```
31.1 (Graph Resources) → 31.3 (Indexing Observability) → 31.2 (Analytics) → 31.4 (Security)
```

Les outils graph et indexing sont les plus utiles pour les agents. La sécurité vient en dernier car c'est un changement d'architecture.
