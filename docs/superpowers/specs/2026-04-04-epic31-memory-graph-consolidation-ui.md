# EPIC-31: Memory Graph Visualization & Consolidation UI

> **Statut:** DRAFT | **Date:** 2026-04-04 | **Auteur:** giak
> **Inspiration:** Réutilisation G6Graph existant + SCADA design system

---

## 1. Problem Statement

Les résultats d'EPIC-28/29/30 sont invisibles dans l'UI. L'utilisateur ne peut pas :
- Voir le graphe de relations entre mémoires
- Explorer visuellement les clusters de mémoires similaires
- Voir les suggestions de consolidation et agir dessus
- Comprendre comment les entités lient les mémoires entre elles

**Conséquences :**
- L'agent MCP est le seul consommateur des nouvelles fonctionnalités
- L'humain ne peut pas explorer le graphe de connaissances
- Les suggestions de consolidation restent invisibles sans appel MCP explicite

---

## 2. Solution Overview

Deux nouvelles sections UI réutilisant l'infrastructure existante :

1. **Memory Graph** — Visualisation du graphe de relations entre mémoires via G6Graph (réutilisé)
2. **Consolidation Suggestions** — Panneau de suggestions dans Expanse Memory avec action de consolidation

**Architecture REST** : Le frontend appelle des endpoints REST (pas MCP), qui wrap les services backend existants.

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Vue 3 + SCADA)                                   │
│                                                              │
│  /brain → Onglet "Memory Graph"                              │
│  ├─ Réutilise G6Graph.vue (layout force)                    │
│  ├─ Nodes = mémoires (colorées par type)                    │
│  ├─ Edges = relations (épaisseur = score)                   │
│  └─ Clic → détails mémoire (entités, concepts, tags)        │
│                                                              │
│  /expanse-memory → Section "Consolidation"                   │
│  ├─ Liste de groupes suggérés                               │
│  ├─ Score de similarité + entités partagées                 │
│  ├─ Preview contenu (200 chars)                             │
│  └─ Bouton "Consolider" → appelle consolidate_memory        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Backend (FastAPI)                                          │
│                                                              │
│  GET /api/v1/memories/graph?min_score=0.3&limit=100         │
│  → Retourne {nodes: [...], edges: [...]}                    │
│  → Utilise MemoryRelationshipService                        │
│  → Cache Redis TTL 10 min                                   │
│                                                              │
│  GET /api/v1/memories/consolidation/suggestions             │
│  → Retourne {groups: [...]}                                 │
│  → Utilise ConsolidationSuggestionService                   │
│  → Paramètres query: min_shared, max_age, etc.              │
│                                                              │
│  POST /api/v1/memories/consolidate                          │
│  → Wrapper REST pour consolidate_memory MCP tool            │
│  → Retourne résultat de consolidation                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Stories

### Story 31.1: REST Endpoints pour Memory Graph et Consolidation

**Objectif** : Ajouter 3 endpoints REST pour le frontend.

**Endpoints** :
```python
# api/routes/memory_graph_routes.py

@router.get("/memories/graph")
async def get_memory_graph(
    min_score: float = Query(0.3, ge=0.0, le=1.0),
    limit: int = Query(100, ge=1, le=500),
    engine: AsyncEngine = Depends(get_db_engine),
) -> Dict[str, Any]:
    """Retourne le graphe de relations entre mémoires."""
    # Réutilise le endpoint existant de memory_relationship_routes.py
    # Ajout de couleurs par type de mémoire pour le frontend
```

```python
@router.get("/memories/consolidation/suggestions")
async def get_consolidation_suggestions(
    min_shared_entities: int = 2,
    min_shared_concepts: int = 1,
    memory_types: List[str] = ["note"],
    tags: List[str] = ["sys:history"],
    max_age_days: int = 30,
    min_group_size: int = 3,
    max_groups: int = 5,
    similarity_threshold: float = 0.3,
    engine: AsyncEngine = Depends(get_db_engine),
    redis = Depends(get_redis),
) -> Dict[str, Any]:
    """Retourne les suggestions de consolidation."""
    # Wrap ConsolidationSuggestionService
```

```python
@router.post("/memories/consolidate")
async def consolidate_memories(
    request: ConsolidateRequest,
    engine: AsyncEngine = Depends(get_db_engine),
) -> Dict[str, Any]:
    """Consolide un groupe de mémoires."""
    # Wrap ConsolidateMemoryTool
```

**Fichiers** :
- Créer : `api/routes/memory_graph_routes.py`
- Modifier : `api/main.py` — inclure le nouveau router

---

### Story 31.2: Memory Graph UI — Onglet dans Brain

**Objectif** : Afficher le graphe de relations entre mémoires dans la page Brain.

**Composant** : `frontend/src/components/brain/MemoryGraph.vue`

**Spécifications** :
- Réutilise `G6Graph.vue` existant avec config mémoire
- Nodes colorées par type :
  - `decision` = bleu (`#3B82F6`)
  - `note` = vert (`#10B981`)
  - `investigation` = violet (`#8B5CF6`)
  - `sys:*` = cyan (`#06B6D4`)
- Edges :
  - Épaisseur = score (1px → 4px)
  - Couleur = type de relation :
    - `shared_entity` = orange (`#F97316`)
    - `shared_concept` = cyan (`#06B6D4`)
    - `shared_tag` = gris (`#6B7280`)
- Layout : `force` (regroupe les mémoires similaires)
- Clic sur nœud → panneau latéral avec détails (titre, entités, concepts, tags, date)
- Filtres : type de mémoire, score minimum, tags
- Auto-refresh toutes les 60s

**Composable** : `frontend/src/composables/useMemoryGraph.ts`
```typescript
export function useMemoryGraph() {
  const graphData = ref<{ nodes: MemoryNode[], edges: MemoryEdge[] }>({ nodes: [], edges: [] })
  const loading = ref(false)
  const error = ref<string | null>(null)
  
  async function fetchGraph(minScore = 0.3, limit = 100) {
    loading.value = true
    try {
      const res = await fetch(`${API}/memories/graph?min_score=${minScore}&limit=${limit}`)
      if (!res.ok) throw new Error('Failed to fetch memory graph')
      graphData.value = await res.json()
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }
  
  return { graphData, loading, error, fetchGraph }
}
```

**Fichiers** :
- Créer : `frontend/src/components/brain/MemoryGraph.vue`
- Créer : `frontend/src/composables/useMemoryGraph.ts`
- Modifier : `frontend/src/pages/Brain.vue` — ajouter l'onglet "Memory Graph"

---

### Story 31.3: Consolidation Suggestions UI — Section dans Expanse Memory

**Objectif** : Afficher les suggestions de consolidation dans Expanse Memory.

**Composant** : `frontend/src/components/brain/ConsolidationSuggestions.vue`

**Spécifications** :
- Liste de groupes suggérés (style SCADA `.scada-panel`)
- Chaque groupe affiche :
  - Titre suggéré (modifiable)
  - Score de similarité (badge coloré : vert >0.6, orange >0.4, rouge <0.4)
  - Entités partagées (badges `.badge-cyan`)
  - Concepts partagés (badges `.badge-purple`)
  - Preview des mémoires (titre + 200 chars)
  - Bouton "Consolider" (`.scada-btn-primary`)
- Clic "Consolider" → modal de confirmation avec champ résumé (pré-rempli avec hint)
- Après consolidation → refresh de la liste

**Composable** : `frontend/src/composables/useConsolidation.ts`
```typescript
export function useConsolidation() {
  const suggestions = ref<ConsolidationGroup[]>([])
  const loading = ref(false)
  
  async function fetchSuggestions(params = {}) {
    loading.value = true
    try {
      const res = await fetch(`${API}/memories/consolidation/suggestions?${new URLSearchParams(params)}`)
      suggestions.value = (await res.json()).groups
    } finally {
      loading.value = false
    }
  }
  
  async function consolidate(group: ConsolidationGroup, summary: string) {
    const res = await fetch(`${API}/memories/consolidate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: group.suggested_title,
        summary,
        source_ids: group.source_ids,
        tags: group.suggested_tags,
      }),
    })
    return await res.json()
  }
  
  return { suggestions, loading, fetchSuggestions, consolidate }
}
```

**Fichiers** :
- Créer : `frontend/src/components/brain/ConsolidationSuggestions.vue`
- Créer : `frontend/src/composables/useConsolidation.ts`
- Modifier : `frontend/src/pages/ExpanseMemory.vue` — ajouter section "Consolidation"

---

### Story 31.4: Types TypeScript et intégration API

**Objectif** : Définir les types TypeScript pour les nouvelles données.

**Fichiers** :
- Créer : `frontend/src/types/memory-graph.ts`

```typescript
export interface MemoryNode {
  id: string
  title: string
  memory_type: string
  size: number
  tags: string[]
  entities?: string[]
  concepts?: string[]
}

export interface MemoryEdge {
  source: string
  target: string
  score: number
  types: string[]
  shared_entities?: string[]
  shared_concepts?: string[]
}

export interface MemoryGraphData {
  nodes: MemoryNode[]
  edges: MemoryEdge[]
  total_nodes: number
  total_edges: number
}

export interface ConsolidationGroup {
  source_ids: string[]
  titles: string[]
  content_previews: string[]
  shared_entities: string[]
  shared_concepts: string[]
  avg_similarity: number
  suggested_title: string
  suggested_tags: string[]
  suggested_summary_hint: string
}
```

**Fichiers** :
- Créer : `frontend/src/types/memory-graph.ts`

---

## 5. Ordre d'implémentation

1. **Story 31.4** — Types TypeScript
2. **Story 31.1** — REST Endpoints
3. **Story 31.2** — Memory Graph UI
4. **Story 31.3** — Consolidation Suggestions UI

---

## 6. Matrice de dégradation

| Scénario | Comportement |
|----------|-------------|
| Endpoint graph HS | Affiche message d'erreur SCADA `.alert-error` |
| Pas de relations | Affiche message "Aucune relation trouvée" |
| Consolidation échoue | Toast erreur + retry button |
| Redis cache HS | Calcul direct (plus lent mais correct) |

---

## 7. Métriques de succès

| Métrique | Cible | Mesure |
|----------|-------|--------|
| Latence chargement graphe | < 1s | P95 response time |
| Latence suggestions | < 2s | P95 response time |
| Taux d'utilisation | > 30% des sessions | Analytics frontend |
| Taux de consolidation | > 20% des suggestions | Backend metrics |

---

## 8. Risques et mitigations

| Risque | Probabilité | Impact | Mitigation |
|--------|------------|--------|------------|
| G6Graph trop lent avec >500 nœuds | Moyenne | Moyen | Limiter à 100 nœuds par défaut, pagination |
| Suggestions peu pertinentes | Faible | Moyen | Seuil similarity_threshold configurable |
| Modal consolidation trop complexe | Faible | Faible | Pré-remplir le résumé avec le hint |
| Conflit de style SCADA | Faible | Faible | Réutiliser les classes existantes |

---

## 9. Dépendances

- **EPIC-28** : Entity extraction (entités/concepts pour le graphe)
- **EPIC-29** : Memory relationships (edges du graphe)
- **EPIC-30** : Consolidation suggestions (données pour l'UI)
- **G6Graph existant** : Réutilisé pour la visualisation
- **SCADA Design System** : Réutilisé pour le styling
