# AUDIT: Graph Visualization Feature (EPIC-25 Story 25.5)

**Date**: 2025-11-01
**Status**: ❌ **INCOMPLETE - CRITICAL ISSUES**

---

## 🔴 PROBLÈMES CRITIQUES IDENTIFIÉS

### 1. **Visualisation Vide - Aucun Node/Edge Affiché**

**Problème**: La page Graph ne montre RIEN même avec 740 nodes en base.

**Cause racine**:
- `Graph.vue` crée une instance Cytoscape VIDE
- Aucun appel API pour récupérer les nodes/edges
- Cytoscape n'est jamais populé avec les données

**Code problématique** (`src/pages/Graph.vue:24-82`):
```typescript
const initGraph = async () => {
  cy.value = cytoscape({
    container: graphContainer.value,
    // ... styles ...
  })

  // ❌ VIDE! Aucun node/edge ajouté
  // Seulement un placeholder si total_nodes === 0
  if (stats.value && stats.value.total_nodes === 0) {
    cy.value.add({ /* placeholder */ })
  }
}
```

---

### 2. **Manque Endpoint API pour Récupérer Graph Data**

**Problème**: Il n'existe PAS d'endpoint pour récupérer nodes + edges.

**Endpoints disponibles**:
- ✅ `GET /v1/code/graph/stats/{repository}` - Stats seulement
- ✅ `POST /v1/code/graph/build` - Build graph
- ❌ **MANQUE**: `GET /v1/code/graph/data/{repository}` - Nodes + Edges

**Ce qui devrait être retourné**:
```typescript
{
  nodes: [
    { id: "uuid", label: "MyClass", type: "class", file_path: "..." },
    { id: "uuid", label: "my_function", type: "function", ... }
  ],
  edges: [
    { source: "uuid", target: "uuid", type: "calls" },
    { source: "uuid", target: "uuid", type: "imports" }
  ]
}
```

---

### 3. **useCodeGraph Composable Incomplet**

**Problème**: Le composable ne peut QUE récupérer les stats.

**Manquant**:
```typescript
// ❌ N'existe pas
const fetchGraphData = async (repository: string) => {
  const response = await fetch(`/v1/code/graph/data/${repository}`)
  const { nodes, edges } = await response.json()
  return { nodes, edges }
}
```

---

### 4. **Bouton "Build Graph" Ne Rafraîchit Pas la Visualisation**

**Problème**: Cliquer sur "Build Graph" ne change rien visuellement.

**Raison**:
```typescript
const handleBuildGraph = async () => {
  await buildGraph(repository.value, 'python')
  // ❌ Ne recharge PAS les nodes/edges
  // ❌ Ne régénère PAS Cytoscape
}
```

**Ce qui devrait se passer**:
1. Build graph (✅ fonctionne)
2. Fetch nodes/edges (❌ manquant)
3. Populer Cytoscape (❌ manquant)
4. Relancer layout (❌ manquant)

---

### 5. **0 Edges Détectées**

**Problème**: Le graph construction ne détecte AUCUNE dépendance.

**Stats actuelles**:
```json
{
  "total_nodes": 740,
  "total_edges": 0,  // ❌ PROBLÈME
  "nodes_by_type": {
    "function": 600,
    "class": 140
  },
  "edges_by_type": {}  // ❌ VIDE
}
```

**Causes possibles**:
- Parser de dépendances ne fonctionne pas
- Imports/calls non détectés
- Résolution des noms échoue
- Bug dans `GraphConstructionService`

---

### 6. **Message "Graph Not Built" Incorrect**

**Problème**: Le message s'affiche même quand le graph EST construit.

**Code** (`src/pages/Graph.vue:224`):
```vue
<div v-if="stats.total_edges === 0">
  Graph Not Built
</div>
```

**Problème**: Se base sur `total_edges === 0` au lieu de `total_nodes === 0`.
- Avec 740 nodes mais 0 edges, le message s'affiche à tort

---

## 📋 FONCTIONNALITÉS MANQUANTES

### Frontend

1. ❌ **Endpoint GET nodes/edges**
2. ❌ **fetchGraphData()** dans useCodeGraph
3. ❌ **Populate Cytoscape** avec vraies données
4. ❌ **Layout algorithm** (force-directed, cola, cose)
5. ❌ **Zoom controls**
6. ❌ **Node interactions** (click, hover, tooltip)
7. ❌ **Filter controls** (type, file, search)
8. ❌ **Success message** après build
9. ❌ **Loading spinner** pendant fetch data
10. ❌ **Error boundary** si trop de nodes

### Backend

1. ❌ **GET /v1/code/graph/data/{repository}** endpoint
2. ❌ **Pagination** pour grands graphs
3. ❌ **Filtering** (par type, file, depth)
4. ❌ **Fix edge detection** (0 edges = problème parser)

---

## 🎯 PLAN DE CORRECTION

### Phase 1: Backend - Endpoint Graph Data (Priorité HAUTE)

**Fichier**: `api/routes/code_graph_routes.py`

```python
@router.get("/data/{repository}")
async def get_graph_data(
    repository: str,
    limit: int = 500,
    engine: AsyncEngine = Depends(get_db_engine)
):
    """Get graph nodes and edges for visualization."""
    async with engine.begin() as conn:
        # Fetch nodes
        nodes_result = await conn.execute(
            select(CodeGraphNode)
            .where(CodeGraphNode.repository == repository)
            .limit(limit)
        )
        nodes = [node_to_dict(n) for n in nodes_result]

        # Fetch edges
        edges_result = await conn.execute(
            select(CodeGraphEdge)
            .where(CodeGraphEdge.repository == repository)
            .limit(limit * 2)
        )
        edges = [edge_to_dict(e) for e in edges_result]

        return {"nodes": nodes, "edges": edges}
```

### Phase 2: Frontend - Fetch & Display (Priorité HAUTE)

**useCodeGraph.ts**:
```typescript
const fetchGraphData = async (repository: string, limit: number = 500) => {
  const response = await fetch(
    `http://localhost:8001/v1/code/graph/data/${repository}?limit=${limit}`
  )
  return await response.json()
}
```

**Graph.vue**:
```typescript
const populateGraph = async () => {
  const { nodes, edges } = await fetchGraphData(repository.value)

  if (!cy.value) return

  // Clear existing
  cy.value.elements().remove()

  // Add nodes
  cy.value.add(nodes.map(n => ({
    group: 'nodes',
    data: { id: n.id, label: n.label, type: n.type }
  })))

  // Add edges
  cy.value.add(edges.map(e => ({
    group: 'edges',
    data: { source: e.source, target: e.target }
  })))

  // Run layout
  cy.value.layout({ name: 'cose' }).run()
}

onMounted(async () => {
  await fetchStats(repository.value)
  await nextTick()
  initGraph()
  await populateGraph() // ← AJOUTER
})
```

### Phase 3: Fix Edge Detection (Priorité MOYENNE)

Investiguer pourquoi 0 edges sont détectées:
- Vérifier `GraphConstructionService`
- Vérifier parsers d'imports/calls
- Vérifier résolution de noms

### Phase 4: UX Improvements (Priorité BASSE)

- Success toast après build
- Better layouts (cola, cose-bilkent)
- Zoom/pan controls
- Node tooltips
- Search/filter

---

## ✅ CE QUI FONCTIONNE

1. ✅ API stats endpoint
2. ✅ Graph build endpoint (avec fix language)
3. ✅ Stats cards display (nodes count, types)
4. ✅ Cytoscape setup (styles, container)
5. ✅ Build button UX (spinner, disabled)
6. ✅ Error handling (buildError banner)

---

## 📊 IMPACT

**Sévérité**: 🔴 **CRITIQUE**
**User Impact**: La fonctionnalité est **complètement non-fonctionnelle**
- Les utilisateurs ne voient RIEN
- Le bouton Build ne produit aucun résultat visible
- Message confus "Graph Not Built" même après build

**Effort estimé**:
- Backend endpoint: **2h**
- Frontend fetch + display: **2h**
- Testing: **1h**
- **Total: ~5h**

---

## 🏁 RECOMMANDATIONS

1. **URGENT**: Implémenter GET /data endpoint + fetch dans frontend
2. **IMPORTANT**: Fixer la détection d'edges (0 edges = graph inutile)
3. **MOYEN**: Améliorer UX (layouts, controls, tooltips)
4. **DOCUMENTATION**: Ajouter guide d'utilisation dans l'UI

---

**Conclusion**: Story 25.5 est marquée "complète" mais est **fondamentalement non-fonctionnelle**. Une refonte complète de la visualisation est nécessaire.
