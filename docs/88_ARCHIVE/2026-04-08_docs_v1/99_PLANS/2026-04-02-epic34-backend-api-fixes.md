# EPIC-34: Backend API Completeness

**Status**: ✅ COMPLETE | **Created**: 2026-04-02 | **Completed**: 2026-04-02 | **Commits**: 3

---

## Context

Audit final via Playwright révèle que 9/11 pages sont fonctionnelles.
Les 2 pages "cassées" ont des problèmes mineurs, pas des bugs critiques.

### État actuel des pages

| Page | Status | Erreurs | Cause |
|------|--------|---------|-------|
| /dashboard | ✅ OK | 0 | — |
| /search | ✅ OK | 0 | — |
| /memories | ✅ OK | 0 | Emojis = contenu utilisateur |
| /projects | ✅ OK | 0 | — |
| /expanse | ✅ OK | 0 | — |
| /expanse-memory | ✅ OK | 0 | — |
| /monitoring | ✅ OK | 0 | — |
| /alerts | ✅ OK | 0 | — |
| /brain | ✅ OK | 1 (404) | decay/config endpoint manquant |
| /graph | ✅ OK | 0 | — |
| /logs | ⚠️ 1 erreur | 1 (406) | MCP stream = 406 (normal) |

### Endpoints API testés (13/14 fonctionnels)

| Endpoint | Status | Utilisé par |
|----------|--------|-------------|
| `/api/v1/memories/recent` | ✅ 200 | Brain |
| `/api/v1/memories/stats` | ✅ 200 | Dashboard, Brain |
| `/api/v1/memories/code-chunks/recent` | ✅ 200 | Brain |
| `/v1/events/cache/stats` | ✅ 200 | Brain |
| `/api/v1/alerts/recent` | ✅ 200 | Alerts, Brain |
| `/api/v1/alerts/summary` | ✅ 200 | Alerts, Brain, Navbar |
| `/api/v1/monitoring/latency` | ✅ 200 | Monitoring, Brain |
| `/api/v1/memories/decay/config` | ❌ 404 | Brain |
| `/v1/cache/stats` | ✅ 200 | Brain |
| `/v1/autosave/stats` | ✅ 200 | Dashboard |
| `/v1/code/graph/repositories` | ✅ 200 | Graph, Brain |
| `/v1/code/graph/data/{repo}` | ✅ 200 | Graph, Brain |
| `/v1/code/graph/metrics/{repo}` | ✅ 200 | Graph, Brain |
| `/health` | ✅ 200 | Logs |

---

## Stories

### Story 34.1: Créer l'endpoint decay/config
**Priority**: P1 | **Effort**: 1 pt | **Value**: Medium

**Problème** : `GET /api/v1/memories/decay/config` retourne 404.
Le Brain page appelle cet endpoint pour afficher la configuration de decay.

**Solution** : Créer un endpoint GET qui retourne les règles de decay depuis `memory_decay_config`.

**Fichiers** :
- `api/routes/memories_routes.py` — Ajouter `@router.get("/decay/config")`
- Ou `api/routes/monitoring_routes_advanced.py` — Plus logique pour la config

**Implémentation** :
```python
@router.get("/memories/decay/config")
async def get_decay_config():
    """Return all decay configuration rules."""
    engine = await get_db_engine()
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT tag_pattern, decay_rate, half_life_days,
                   auto_consolidate_threshold, priority_boost
            FROM memory_decay_config
            ORDER BY decay_rate ASC
        """))
        rows = result.fetchall()
    return {
        "data": [
            {
                "tag_pattern": r[0],
                "decay_rate": r[1],
                "half_life_days": r[2],
                "auto_consolidate_threshold": r[3],
                "priority_boost": r[4],
            }
            for r in rows
        ]
    }
```

---

### Story 34.2: Fixer Redis health check
**Priority**: P2 | **Effort**: 1 pt | **Value**: Medium

**Problème** : Le health endpoint montre Redis "DOWN" avec erreur :
`cannot import name 'get_redis' from 'dependencies'`

**Solution** : Corriger l'import dans `dependencies.py` ou `health_routes.py`.

**Fichiers** :
- `api/dependencies.py` — Ajouter/exporter `get_redis`
- Ou `api/routes/health_routes.py` — Utiliser le bon import

---

### Story 34.3: MCP health endpoint — éviter le 406
**Priority**: P3 | **Effort**: 0.5 pt | **Value**: Low

**Problème** : La page Logs fait un POST sur `/mcp` avec `Accept: */*` mais
le MCP streamable HTTP retourne 406 Not Acceptable.

**Solution** : La Logs page devrait utiliser un endpoint health dédié
plutôt que d'appeler directement le MCP stream.

**Fichiers** :
- `api/routes/health_routes.py` — Ajouter un champ `mcp` au health check
- Ou `frontend/src/pages/Logs.vue` — Supprimer le check MCP direct

---

### Story 34.4: Ajouter un endpoint /api/v1/system/status
**Priority**: P3 | **Effort**: 1.5 pts | **Value**: Medium

**Problème** : Plusieurs pages font des appels multiples pour obtenir
des infos système (health, cache stats, indexing status).

**Solution** : Un endpoint unique qui retourne tout le status système.

**Implémentation** :
```python
@router.get("/system/status")
async def get_system_status():
    """Unified system status endpoint."""
    return {
        "health": await get_health(),
        "cache": await get_cache_stats(),
        "indexing": await get_indexing_status(),
        "memory": await get_memory_health(),
        "uptime": get_uptime(),
    }
```

---

## Ordre d'exécution

```
34.1 → decay/config endpoint (1 pt)
34.2 → Redis health fix (1 pt)
34.3 → MCP health 406 (0.5 pt)
34.4 → /system/status endpoint (1.5 pt)
```

---

## Critères de complétion

- [x] 14/14 endpoints API fonctionnels
- [x] 11/11 pages OK (Playwright audit, 0 erreurs console)
- [x] Redis health = ok dans /health
- [x] Brain page = 0 erreurs console
- [x] Logs page = tous services HEALTHY (sauf MCP = stream SSE, normal)

---

## Métriques de succès

| Métrique | Avant | Après | Cible |
|----------|-------|-------|-------|
| Endpoints OK | 13/14 | 14/14 | 100% ✅ |
| Pages OK (Playwright) | 9/11 | 11/11 | 100% ✅ |
| Erreurs console | 2 | 0 | 0 ✅ |
| Redis health | DOWN | OK | OK ✅ |
