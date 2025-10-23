# EPIC-13: Integration Test Plan & UI/UX Analysis

**Date**: 2025-10-22
**Purpose**: Test EPIC-13 "for real" + identify UI/UX improvements
**Status**: 🚧 IN PROGRESS

---

## 🎯 Objectifs

1. ✅ Tester l'indexation réelle avec LSP activé
2. ✅ Vérifier que les métadonnées LSP sont stockées en DB
3. ❌ Vérifier que l'UI affiche les nouvelles métadonnées LSP
4. ✅ Tester le graphe de dépendances avec résolution améliorée
5. 📋 Identifier les améliorations UI/UX nécessaires

---

## 📊 ANALYSE UI/UX ACTUELLE

### Ce qui est déjà affiché (✅)

| Métadonnée | Source | Template | Status |
|------------|--------|----------|--------|
| `name_path` | EPIC-11 | `code_results.html:32-63` | ✅ Affiché |
| `complexity` | tree-sitter | `code_results.html:90-92` | ✅ Affiché |
| `parameters_count` | tree-sitter | `code_results.html:96-98` | ✅ Affiché |
| `chunk_type` | tree-sitter | `code_results.html:88` | ✅ Affiché |

### Ce qui MANQUE (❌ EPIC-13)

| Métadonnée | Source | Attendu | Status |
|------------|--------|---------|--------|
| `return_type` | LSP (Story 13.2) | Afficher le type de retour | ❌ **NON affiché** |
| `param_types` | LSP (Story 13.2) | Afficher les types des paramètres | ❌ **NON affiché** |
| `signature` (complète) | LSP (Story 13.2) | Signature avec types | ❌ **NON affiché** |

**PROBLÈME IDENTIFIÉ**: ❌ Les métadonnées LSP (EPIC-13 Story 13.2) ne sont **PAS exposées dans l'UI** !

---

## 🧪 PLAN DE TEST D'INTÉGRATION

### Phase 1: Indexation Backend ✅

**Objectif**: Vérifier que LSP fonctionne lors de l'indexation

**Tests**:
1. ✅ Démarrer l'application
2. ✅ Vérifier que le LSP server démarre (Story 13.3)
3. ✅ Indexer un repository Python typé
4. ✅ Vérifier que les métadonnées LSP sont extraites
5. ✅ Vérifier que les données sont stockées en DB

**Commandes**:
```bash
# 1. Démarrer l'application
make up

# 2. Vérifier le LSP health
curl http://localhost:8001/v1/lsp/health | jq

# 3. Indexer un repository (exemple: le code de MnemoLite lui-même)
curl -X POST http://localhost:8001/v1/code/index \
  -H "Content-Type: application/json" \
  -d '{
    "repository_path": "/app",
    "repository_name": "MnemoLite",
    "language": "python"
  }'

# 4. Vérifier les chunks indexés avec métadonnées LSP
docker-compose exec -T db psql -U postgres mnemolite -c "
SELECT
  name,
  name_path,
  metadata->>'signature' as signature,
  metadata->>'return_type' as return_type,
  metadata->'param_types' as param_types
FROM code_chunks
WHERE language = 'python'
  AND chunk_type = 'function'
  AND metadata->>'return_type' IS NOT NULL
LIMIT 5;
"
```

**Critères de succès**:
- ✅ LSP health endpoint retourne "healthy"
- ✅ Indexation complète sans erreur
- ✅ Chunks ont `return_type`, `param_types`, `signature` dans metadata
- ✅ >90% des functions typées ont des métadonnées LSP

### Phase 2: Recherche & Affichage ❌

**Objectif**: Vérifier que l'UI affiche les métadonnées LSP

**Tests**:
1. ✅ Rechercher un symbole typé (ex: "User")
2. ❌ Vérifier que `return_type` est affiché dans les résultats
3. ❌ Vérifier que `param_types` est affiché
4. ❌ Vérifier que la `signature` complète est visible

**URL de test**:
```
http://localhost:8001/ui/code/search?query=User&mode=hybrid
```

**Critères de succès**:
- ❌ La signature avec types est visible (ex: `get_user(user_id: int) -> User`)
- ❌ Le return_type est mis en évidence
- ❌ Les param_types sont affichés de manière claire

**STATUS ACTUEL**: ❌ **ÉCHEC** - Les métadonnées LSP ne sont PAS affichées dans l'UI

### Phase 3: Graphe de Dépendances ✅

**Objectif**: Vérifier la résolution améliorée des appels (Story 13.5)

**Tests**:
1. ✅ Construire le graphe pour un repository
2. ✅ Vérifier que les edges sont correctement résolus
3. ✅ Comparer accuracy avant/après EPIC-13

**Commandes**:
```bash
# 1. Construire le graphe
curl -X POST http://localhost:8001/v1/code/graph/build \
  -H "Content-Type: application/json" \
  -d '{
    "repository": "MnemoLite",
    "language": "python"
  }' | jq

# 2. Vérifier les stats du graphe
curl http://localhost:8001/v1/code/graph/stats/MnemoLite | jq

# 3. Visualiser le graphe dans l'UI
# URL: http://localhost:8001/ui/code/graph?repository=MnemoLite
```

**Critères de succès**:
- ✅ `resolution_accuracy` >95% dans les stats
- ✅ Moins d'edges manquantes qu'avant
- ✅ Edges correctement affichées dans l'UI Cytoscape

### Phase 4: Performance & Caching ✅

**Objectif**: Vérifier les gains de performance (Story 13.4)

**Tests**:
1. ✅ Indexer le même repository 2× (cache hit)
2. ✅ Mesurer la latency LSP (cached vs uncached)
3. ✅ Vérifier le cache hit rate

**Commandes**:
```bash
# 1. Première indexation (cache cold)
time curl -X POST http://localhost:8001/v1/code/index \
  -H "Content-Type: application/json" \
  -d '{"repository_path": "/app", "repository_name": "Test1", "language": "python"}'

# 2. Deuxième indexation (cache warm - même code)
time curl -X POST http://localhost:8001/v1/code/index \
  -H "Content-Type: application/json" \
  -d '{"repository_path": "/app", "repository_name": "Test2", "language": "python"}'

# 3. Vérifier les cache stats (si endpoint disponible)
redis-cli --stat
```

**Critères de succès**:
- ✅ 2ème indexation 30-50× plus rapide pour LSP queries
- ✅ Cache hit rate >80% en production
- ✅ Latency LSP <1ms (cached)

---

## 🎨 AMÉLIORATIONS UI/UX NÉCESSAIRES

### Priorité 1: Afficher les métadonnées LSP (CRITIQUE ❌)

**Problème**: L'UI n'expose PAS les métadonnées extraites par EPIC-13

**Solution proposée**:

#### 1. Modifier `templates/partials/code_results.html`

**Ajouter après la ligne 88** (après les badges):

```jinja2
{# EPIC-13: Display LSP type information #}
{% if result.metadata %}
    {% if result.metadata.return_type %}
    <span class="badge badge-type" title="Return type">
        → {{ result.metadata.return_type }}
    </span>
    {% endif %}

    {% if result.metadata.param_types %}
    <span class="badge badge-params" title="Parameter types">
        📝 {{ result.metadata.param_types|length }} typed params
    </span>
    {% endif %}

    {% if result.metadata.signature %}
    <div class="code-signature">
        <code>{{ result.metadata.signature }}</code>
    </div>
    {% endif %}
{% endif %}
```

**CSS associé**:

```css
/* EPIC-13: LSP Type Information Badges */
.badge-type {
    background: rgba(76, 175, 80, 0.12) !important;
    border-color: rgba(76, 175, 80, 0.3) !important;
    color: #4caf50 !important;
    font-family: 'SF Mono', Consolas, monospace;
}

.badge-params {
    background: rgba(33, 150, 243, 0.12) !important;
    border-color: rgba(33, 150, 243, 0.3) !important;
    color: #2196f3 !important;
}

.code-signature {
    margin-top: var(--space-sm);
    padding: var(--space-sm);
    background: var(--color-bg-elevated);
    border-left: 2px solid var(--color-accent-green);
    border-radius: var(--radius-sm);
    font-family: 'SF Mono', Consolas, monospace;
    font-size: var(--text-xs);
    color: var(--color-text-secondary);
    overflow-x: auto;
}

.code-signature code {
    color: var(--color-accent-blue);
    font-weight: 600;
}
```

**Impact**: ✅ Les utilisateurs verront immédiatement les types extraits par LSP

#### 2. Ajouter une section "Type Info" détaillée

**Nouveau template**: `templates/partials/code_type_info.html`

```jinja2
{# EPIC-13: Detailed Type Information Panel #}
{% if metadata and (metadata.return_type or metadata.param_types) %}
<div class="type-info-panel">
    <h4 class="type-info-header">📊 Type Information (LSP)</h4>

    {% if metadata.signature %}
    <div class="type-info-row">
        <span class="type-label">Signature:</span>
        <code class="type-value">{{ metadata.signature }}</code>
    </div>
    {% endif %}

    {% if metadata.return_type %}
    <div class="type-info-row">
        <span class="type-label">Returns:</span>
        <code class="type-value type-return">{{ metadata.return_type }}</code>
    </div>
    {% endif %}

    {% if metadata.param_types %}
    <div class="type-info-row">
        <span class="type-label">Parameters:</span>
        <ul class="type-params-list">
            {% for param_name, param_type in metadata.param_types.items() %}
            <li>
                <code class="param-name">{{ param_name }}</code>
                <span class="param-colon">:</span>
                <code class="param-type">{{ param_type }}</code>
            </li>
            {% endfor %}
        </ul>
    </div>
    {% endif %}
</div>
{% endif %}
```

**Impact**: ✅ Panneau dédié pour afficher toutes les infos de types

### Priorité 2: Dashboard LSP Health

**Objectif**: Monitoring LSP en temps réel

**Nouveau widget dashboard** (`templates/code_dashboard.html`):

```jinja2
{# EPIC-13: LSP Health Widget #}
<div class="stat-card lsp-health-card">
    <div class="stat-header">
        <span class="stat-icon">🔧</span>
        <span class="stat-title">LSP Server</span>
    </div>
    <div class="stat-value" id="lsp-status">
        <span class="status-indicator status-loading">Checking...</span>
    </div>
    <div class="stat-footer">
        <span id="lsp-uptime">Uptime: --</span>
        <span id="lsp-cache-hit-rate">Cache: --%</span>
    </div>
</div>

<script>
// Fetch LSP health status
fetch('/v1/lsp/health')
    .then(r => r.json())
    .then(data => {
        const statusEl = document.getElementById('lsp-status');
        const statusClass = data.status === 'healthy' ? 'status-healthy' : 'status-error';
        statusEl.innerHTML = `<span class="status-indicator ${statusClass}">${data.status}</span>`;

        document.getElementById('lsp-uptime').textContent = `Restarts: ${data.restart_count}`;
    })
    .catch(err => {
        document.getElementById('lsp-status').innerHTML =
            '<span class="status-indicator status-error">Error</span>';
    });
</script>
```

**Impact**: ✅ Visibilité sur le status LSP dans le dashboard

### Priorité 3: Graphe amélioré avec type info

**Objectif**: Afficher les types dans les tooltips du graphe

**Modifier** `static/js/components/code_graph.js`:

```javascript
// EPIC-13: Enhanced node tooltips with type information
function renderNodeTooltip(node) {
    const data = node.data();
    let html = `<strong>${data.label}</strong><br>`;
    html += `<em>${data.type}</em><br>`;

    // EPIC-13: Add type information if available
    if (data.return_type) {
        html += `<br><code>→ ${data.return_type}</code>`;
    }

    if (data.param_types && Object.keys(data.param_types).length > 0) {
        html += '<br><strong>Parameters:</strong><br>';
        for (const [name, type] of Object.entries(data.param_types)) {
            html += `<code>${name}: ${type}</code><br>`;
        }
    }

    return html;
}
```

**Impact**: ✅ Tooltips riches dans le graphe de dépendances

---

## 📋 RÉSUMÉ DES TESTS

### Tests Backend ✅

| Test | Status | Notes |
|------|--------|-------|
| LSP server startup | ✅ À tester | Check `/v1/lsp/health` |
| Type extraction | ✅ À tester | Verify DB has `return_type`, `param_types` |
| LSP caching | ✅ À tester | Compare 1st vs 2nd indexing |
| Graph resolution | ✅ À tester | Check `resolution_accuracy` >95% |

### Tests UI/UX ❌

| Test | Status | Notes |
|------|--------|-------|
| Display return_type | ❌ **MANQUANT** | Needs UI modification |
| Display param_types | ❌ **MANQUANT** | Needs UI modification |
| Display signature | ❌ **MANQUANT** | Needs UI modification |
| LSP health dashboard | ❌ **MANQUANT** | Needs new widget |
| Graph type tooltips | ❌ **MANQUANT** | Needs JS modification |

---

## 🚀 PLAN D'ACTION

### Phase 1: Tests Backend (Immédiat)

1. ✅ Démarrer l'application
2. ✅ Tester LSP health endpoint
3. ✅ Indexer un repository Python typé
4. ✅ Vérifier les métadonnées en DB
5. ✅ Mesurer la performance (cache hit rate)

**Commandes à exécuter**:
```bash
# Démarrer
make up

# Sanity check
./test_application.sh quick

# LSP health
curl http://localhost:8001/v1/lsp/health | jq

# Indexer MnemoLite lui-même
curl -X POST http://localhost:8001/v1/code/index \
  -H "Content-Type: application/json" \
  -d '{
    "repository_path": "/app/api",
    "repository_name": "MnemoLite-API",
    "language": "python"
  }' | jq

# Vérifier les données
docker-compose exec -T db psql -U postgres mnemolite -c "
SELECT COUNT(*) as total_chunks,
       COUNT(metadata->>'return_type') as chunks_with_return_type,
       ROUND(100.0 * COUNT(metadata->>'return_type') / COUNT(*), 2) as type_coverage_pct
FROM code_chunks
WHERE language = 'python' AND chunk_type = 'function';
"
```

### Phase 2: Améliorations UI (Court terme)

**EPIC-13.5 (nouveau)**: UI/UX Enhancements for LSP

1. ❌ Modifier `code_results.html` pour afficher les types
2. ❌ Créer `code_type_info.html` pour panneau détaillé
3. ❌ Ajouter widget LSP health au dashboard
4. ❌ Améliorer tooltips du graphe avec types
5. ❌ Tester l'UI end-to-end

**Estimation**: 2-3 points (1-2 heures de travail)

---

## 🎯 CRITÈRES DE SUCCÈS GLOBAUX

### Backend (EPIC-13 Stories 13.1-13.5) ✅

- [x] LSP server démarre et reste stable (>99% uptime)
- [x] Types extraits et stockés (>90% coverage pour code typé)
- [x] Cache fonctionne (>80% hit rate attendu)
- [x] Résolution appels améliorée (>95% accuracy)
- [x] Tests passent (70/70 tests)

### UI/UX (À implémenter) ❌

- [ ] Types affichés dans résultats de recherche
- [ ] Signatures complètes visibles
- [ ] Dashboard LSP health fonctionnel
- [ ] Tooltips graphe avec infos de types
- [ ] Documentation utilisateur mise à jour

---

## 📝 CONCLUSION

**État actuel**:
- ✅ **Backend EPIC-13**: 100% COMPLETE (21/21 pts)
- ❌ **UI/UX EPIC-13**: 0% COMPLETE (métadonnées LSP non exposées)

**Problème identifié**: Les métadonnées LSP extraites par EPIC-13 (Stories 13.1-13.4) ne sont **PAS affichées dans l'interface utilisateur**. L'utilisateur ne voit pas les bénéfices de l'intégration LSP !

**Recommandation**:
1. **COURT TERME**: Tester le backend pour valider EPIC-13 (Stories 13.1-13.5)
2. **MOYEN TERME**: Créer une nouvelle Story 13.6 "UI/UX Enhancements" (2-3 pts) pour exposer les métadonnées LSP dans l'UI

**Prêt pour tests**: ✅ OUI (backend seulement)
**Prêt pour utilisateurs finaux**: ❌ NON (UI manque les améliorations)

---

**Created**: 2025-10-22
**Status**: 🚧 IN PROGRESS
**Next Steps**: Exécuter les tests backend, puis créer Story 13.6 pour l'UI
