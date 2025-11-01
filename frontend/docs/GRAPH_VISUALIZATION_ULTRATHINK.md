# Graph Visualization ULTRATHINK
**Date:** 2025-11-01
**Context:** EPIC-25 Story 25.5 - Advanced Interactive Code Graph

## 🎯 Vision Utilisateur

> "Il me faut un graph qui permette de visualiser correctement les choses, comme ce qui est **complexe**, **simple**, avec un **effet de profondeur** (une classe dépend d'une autre, cette dernière est en retrait, si on clique dessus, on la remet en avant, et ses enfants se réduisent)"

### Besoins Identifiés
1. **Complexité Visuelle** - Distinguer immédiatement code simple vs complexe
2. **Hiérarchie avec Profondeur** - Effet 3D/depth pour montrer dépendances
3. **Focus Interactif** - Click pour focus/défocus, navigation fluide
4. **Collapse/Expand** - Réduire/agrandir sous-graphes dynamiquement
5. **Exploration Intuitive** - Comprendre la structure sans effort

---

## 🧠 Brainstorm: Approches de Visualisation

### Approche 1: **Focus + Context avec Depth Simulation**

**Concept:**
- Node sélectionné = **au centre**, grande taille, opacité 100%
- Dépendances directes = **autour**, taille moyenne, opacité 80%
- Dépendances indirectes = **en périphérie**, petite taille, opacité 50%
- Animation fluide lors du click (transition 300ms)

**Codage Complexité:**
- **Taille du node** = f(nb de connections) → Plus de connexions = plus gros node
- **Couleur saturation** = f(cyclomatic complexity) → Plus complexe = couleur plus saturée
- **Stroke width** = f(centrality) → Plus central = bordure plus épaisse

**Interactions:**
- **Click node** → Recentrer, highlight path
- **Shift+Click** → Expand/collapse enfants
- **Double-click** → Navigate to code location
- **Hover** → Show metrics (complexity, dependencies count)

**Avantages:**
- ✅ Effet de profondeur visuel (size + opacity)
- ✅ Focus sur ce qui est important
- ✅ Performance (pas de vraie 3D)

**Inconvénients:**
- ❌ Perd contexte global lors du focus
- ❌ Difficile avec beaucoup de nodes (>200)

---

### Approche 2: **Hierarchical Layered DAG**

**Concept:**
- **Layers horizontaux** = Niveaux de dépendances
  - Layer 0: Nodes sans dépendances (feuilles)
  - Layer 1: Nodes qui dépendent de Layer 0
  - Layer N: Nodes qui dépendent de Layer N-1
- **Profondeur visuelle** = Position verticale + gradient background
- **Complexité** = Largeur du node (nb de dépendances)

**Layout Algorithm:**
```
1. Topological sort pour trouver l'ordre des layers
2. Minimize edge crossings (Sugiyama framework)
3. Position nodes pour minimiser longueur des edges
```

**Interactions:**
- **Click layer** → Collapse/expand tout le layer
- **Click node** → Highlight all paths from/to this node
- **Drag node** → Re-layout automatique

**Avantages:**
- ✅ Structure claire
- ✅ Facile de voir flux de dépendances
- ✅ Scalable (jusqu'à 500+ nodes)

**Inconvénients:**
- ❌ Pas flexible pour code non-DAG (cycles)
- ❌ Layout rigide

---

### Approche 3: **Radial Tree avec Zoom Sémantique**

**Concept:**
- **Centre** = Node sélectionné (root)
- **Cercles concentriques** = Niveaux de dépendances
  - Cercle 1: Dépendances directes
  - Cercle 2: Dépendances transitives
  - Cercle N: Dépendances N-hops
- **Angular position** = Groupement par module/file
- **Zoom sémantique** = Aggregation automatique quand trop de nodes

**Complexité Encoding:**
- **Arc size** = Nb de dependencies
- **Color intensity** = Complexity score
- **Radial distance** = Dependency depth

**Interactions:**
- **Click node** → Devient nouveau centre, re-layout animé
- **Scroll** → Zoom in/out avec aggregation
- **Hover sector** → Preview nodes dans ce secteur

**Avantages:**
- ✅ Excellent effet de profondeur visuel
- ✅ Navigation très intuitive
- ✅ Bonne gestion de la complexité

**Inconvénients:**
- ❌ Difficile de comparer nodes distants
- ❌ Perd structure globale

---

### Approche 4: **Force-Directed avec Clustering & Fisheye**

**Concept:**
- **Force-directed layout** avec contraintes:
  - Attraction entre nodes du même fichier
  - Répulsion entre clusters
  - Gravity vers centre
- **Clustering automatique** par module/complexité
- **Fisheye distortion** au survol (zoom local)

**Complexité Encoding:**
- **Node size** = Cyclomatic complexity
- **Cluster color** = Module/file
- **Edge thickness** = Call frequency (si metrics disponibles)

**Interactions:**
- **Click node** → Pin/unpin position
- **Click cluster** → Collapse/expand
- **Drag** → Re-position avec force simulation
- **Fisheye hover** → Zoom local sans perdre contexte

**Avantages:**
- ✅ Très flexible
- ✅ Adapte automatiquement au data
- ✅ Clustering aide à comprendre structure

**Inconvénients:**
- ❌ Peut être instable (nodes qui bougent)
- ❌ Layout non-déterministe
- ❌ Performance (force simulation coûteuse)

---

### Approche 5: **Treemap + Arc Diagram Hybride** (🌟 INNOVANT)

**Concept:**
- **Treemap (haut)** = Hiérarchie du code (files, classes, methods)
  - Taille = Complexity ou LOC
  - Couleur = Type (class/function)
  - Depth = Nested rectangles
- **Arc Diagram (bas)** = Dependencies entre nodes
  - Arcs reliant les rectangles du treemap
  - Height de l'arc = Coupling strength

**Profondeur:**
- **Nested treemap** pour hiérarchie
- **Arc elevation** pour dépendances

**Interactions:**
- **Click rectangle** → Zoom in treemap, filter arcs
- **Hover arc** → Highlight source + target
- **Breadcrumb** → Navigate back up

**Avantages:**
- ✅✅ EXCELLENT pour hiérarchie + dependencies
- ✅ Très clair visuellement
- ✅ Dual-view complementary

**Inconvénients:**
- ❌ Complexe à implémenter
- ❌ Nécessite beaucoup d'espace vertical

---

## 🔬 Analyse Comparative

| Approche | Profondeur | Complexité | Focus | Performance | Implémentation |
|----------|-----------|-----------|-------|-------------|----------------|
| 1. Focus+Context | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| 2. Layered DAG | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| 3. Radial Tree | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| 4. Force+Cluster | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| 5. Treemap+Arc | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ |

---

## 🎨 Recommandation: **Hybrid Radial + Force-Directed**

### Architecture Proposée

**Mode 1: Radial View (Default)**
- Visualisation rapide de la hiérarchie
- Node sélectionné au centre
- Dépendances en cercles concentriques
- Click pour re-center

**Mode 2: Force-Directed View (Exploration)**
- Vue complète du graph
- Clustering par fichier
- Fisheye au survol
- Drag & drop interactif

**Mode 3: Minimap** (toujours visible)
- Petit aperçu du graph complet
- Rectangle indiquant viewport actuel
- Click pour navigation rapide

### Visual Encoding Complet

**Complexité:**
1. **Node Size** = `scale(nbDependencies)` (range: 16px-48px)
2. **Color Saturation** = `scale(cyclomaticComplexity)` (range: 40%-100%)
3. **Stroke Width** = `scale(betweennessCentrality)` (range: 1px-4px)
4. **Glow Effect** = High complexity nodes (filter: drop-shadow)

**Profondeur:**
1. **Radial Distance** = Dependency depth (0=center, 1=ring1, 2=ring2...)
2. **Opacity** = `1.0 - (depth * 0.15)` (max depth=5)
3. **Blur** = `depth * 0.5px` (simule perspective)
4. **Z-Index layering** = Focused nodes on top

**Interactions:**
1. **Click** → Focus + re-center avec animation
2. **Shift+Click** → Expand/collapse children
3. **Ctrl+Click** → Multi-select
4. **Double-click** → Open in editor (future)
5. **Right-click** → Context menu (show callers, callees, path to...)
6. **Scroll** → Zoom (with scale limits)
7. **Drag** → Pan OR drag node (mode toggle)
8. **Hover** → Highlight neighbors + show metrics tooltip

---

## 🛠️ Technologies Recommandées

### Option A: **D3.js** (Full Control)
**Pros:**
- Contrôle total sur rendering
- Force simulation performante
- Excellent pour animations
- Large communauté

**Cons:**
- Beaucoup de code à écrire
- Courbe d'apprentissage
- Intégration Vue 3 nécessite attention

**Estimation:** 2-3 jours développement

### Option B: **Vis.js Network** (Quick Start)
**Pros:**
- Hierarchical layout built-in
- Clustering automatique
- Interactions natives
- Bonne performance

**Cons:**
- Moins flexible que D3
- Styling limité
- Pas de radial layout natif

**Estimation:** 1 jour développement

### Option C: **G6 (AntV)** (🌟 BEST FIT)
**Pros:**
- ✅ Spécialement conçu pour graph visualization
- ✅ Force, Radial, Dagre layouts built-in
- ✅ Focus/context natif
- ✅ Excellent performance (WebGL optional)
- ✅ Fisheye lens plugin
- ✅ Clustering automatique
- ✅ TypeScript support

**Cons:**
- Documentation en chinois (traduite)
- Moins connu en occident
- Bundle size ~200KB

**Estimation:** 1-2 jours développement

**G6 Sample Code:**
```typescript
import G6 from '@antv/g6'

const graph = new G6.Graph({
  container: 'container',
  width: 800,
  height: 600,
  layout: {
    type: 'radial',
    unitRadius: 70,
    linkDistance: 100,
    focusNode: selectedNodeId,
  },
  modes: {
    default: ['drag-canvas', 'zoom-canvas', 'drag-node', 'click-select'],
  },
  plugins: [
    new G6.Fisheye({ radius: 150 }),
  ],
})

// Node complexity encoding
graph.node(node => {
  const complexity = getComplexity(node)
  return {
    size: 20 + complexity * 5,
    style: {
      fill: getColorBySaturation(node.type, complexity),
      lineWidth: getCentrality(node) * 2,
    },
  }
})
```

---

## 📋 Plan d'Implémentation (avec G6)

### Phase 1: Fix Edges (Aujourd'hui - 1h)
- ✅ Debug pourquoi edges ne s'affichent pas
- ✅ Vérifier edge config v-network-graph
- ✅ Fix et valider

### Phase 2: Prototype Radial (Demain - 4h)
- Install @antv/g6
- Create G6Graph.vue component
- Implement radial layout
- Basic interactions (click to focus)
- Compare avec v-network-graph actuel

### Phase 3: Complexity Encoding (2h)
- Calculate node metrics (dependency count)
- Encode into size/color/stroke
- Add metrics tooltip
- Legend with encoding explanation

### Phase 4: Advanced Interactions (3h)
- Collapse/expand children
- Multi-select
- Context menu
- Minimap
- Keyboard shortcuts

### Phase 5: Polish (2h)
- Smooth animations
- Loading states
- Error handling
- Responsive design
- Performance optimization

**Total Estimation: 12 heures (~1.5 jours)**

---

## 🎯 Quick Win Alternative: Améliorer v-network-graph d'abord

Si migration vers G6 trop risquée maintenant, on peut améliorer v-network-graph:

**Améliorations Possibles:**
1. ✅ **Fix edges** (priorité 1)
2. ✅ **Node size = complexity** (déjà nodes)
3. ✅ **Click to highlight neighbors** (event handler)
4. ✅ **Opacity gradient par depth** (calculate depth from edges)
5. ✅ **Better layout** (radial via custom positions)

**Code Sample:**
```typescript
// Calculate depth from selected node
const calculateDepth = (selectedId: string, edges: Edges): Map<string, number> => {
  const depths = new Map<string, number>()
  depths.set(selectedId, 0)

  // BFS to assign depths
  const queue = [selectedId]
  const visited = new Set<string>()

  while (queue.length > 0) {
    const current = queue.shift()!
    const currentDepth = depths.get(current)!

    // Find all neighbors
    for (const edge of Object.values(edges)) {
      if (edge.source === current && !visited.has(edge.target)) {
        depths.set(edge.target, currentDepth + 1)
        queue.push(edge.target)
        visited.add(edge.target)
      }
    }
  }

  return depths
}

// Apply depth-based styling
const selectedNode = ref<string | null>(null)
const nodeDepths = computed(() => {
  if (!selectedNode.value) return new Map()
  return calculateDepth(selectedNode.value, edges.value)
})

// Update node styles based on depth
configs.value = {
  node: {
    normal: {
      color: (node) => {
        const depth = nodeDepths.value.get(node.id) ?? 5
        return depth === 0 ? '#fbbf24' : getColorByDepth(depth)
      },
      opacity: (node) => {
        const depth = nodeDepths.value.get(node.id) ?? 5
        return Math.max(0.3, 1.0 - depth * 0.15)
      }
    }
  }
}
```

---

## 🚀 Décision Recommandée

**Court Terme (Aujourd'hui):**
1. Fix edges dans v-network-graph (debug + fix)
2. Add click-to-highlight neighbors
3. Add depth-based opacity

**Moyen Terme (Cette semaine):**
1. Prototype avec G6 radial layout
2. Side-by-side comparison
3. User testing
4. Décision: migrate ou améliore v-network-graph

**Long Terme (Prochain sprint):**
1. Full implementation approche choisie
2. Complexity metrics integration
3. Advanced interactions
4. Documentation

---

## 📊 Métriques de Succès

**Visualisation réussie si:**
- ✅ User peut identifier nodes complexes en <5 secondes
- ✅ User peut naviguer hiérarchie sans se perdre
- ✅ User comprend dépendances entre 2 nodes
- ✅ Pas de freeze browser (60fps pour <500 nodes)
- ✅ Interactions fluides (<200ms response time)

**A mesurer:**
- Time to find specific node
- Time to understand dependency chain
- User confusion rate
- Performance metrics (FPS, render time)
- User preference (survey: quelle approche préférez-vous?)

---

**Prochaine étape:** Fix edges maintenant, puis décider si prototype G6 ou améliore v-network-graph.
