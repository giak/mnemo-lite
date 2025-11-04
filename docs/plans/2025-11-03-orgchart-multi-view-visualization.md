# Orgchart Multi-View Visualization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the organizational chart into a multi-perspective visualization that reveals code complexity, architectural hubs, and structural hierarchy through visual encoding (color + size) without changing graph structure.

**Architecture:** Add three view modes (Complexity, Hubs, Hierarchy) with smooth transitions. Same graph nodes/edges/positions, only visual styling changes. Computed properties calculate node size/color based on active mode and metrics from node properties.

**Tech Stack:** Vue 3 Composition API, @antv/g6 v5.0.50, TypeScript

---

## Task 1: Add View Mode State Management

**Files:**
- Modify: `frontend/src/pages/Orgchart.vue:35-60`
- Create: `frontend/src/types/orgchart-types.ts`

**Step 1: Create types file**

Create `frontend/src/types/orgchart-types.ts`:

```typescript
export type ViewMode = 'complexity' | 'hubs' | 'hierarchy'

export interface ViewModeConfig {
  name: string
  description: string
  icon: string
}

export const VIEW_MODES: Record<ViewMode, ViewModeConfig> = {
  complexity: {
    name: 'Complexité',
    description: 'Technical debt hotspots',
    icon: '📊'
  },
  hubs: {
    name: 'Hubs',
    description: 'Architectural dependencies',
    icon: '🔗'
  },
  hierarchy: {
    name: 'Hiérarchie',
    description: 'Structure & depth',
    icon: '🌳'
  }
}
```

**Step 2: Add view mode state to Orgchart.vue**

In `frontend/src/pages/Orgchart.vue`, after line 39 (after `customMaxModules`), add:

```typescript
// View mode state
import type { ViewMode } from '@/types/orgchart-types'
import { VIEW_MODES } from '@/types/orgchart-types'

const viewMode = ref<ViewMode>('hierarchy')

// Load saved view mode from localStorage
onMounted(async () => {
  const savedViewMode = localStorage.getItem('orgchart_view_mode')
  if (savedViewMode && (savedViewMode === 'complexity' || savedViewMode === 'hubs' || savedViewMode === 'hierarchy')) {
    viewMode.value = savedViewMode as ViewMode
  }

  // ... existing onMounted code
})

// Save view mode to localStorage
watch(viewMode, (newMode) => {
  localStorage.setItem('orgchart_view_mode', newMode)
})
```

**Step 3: Verify TypeScript compilation**

```bash
cd frontend
pnpm vite build --mode development
```

Expected: SUCCESS with no TypeScript errors for new types

**Step 4: Commit**

```bash
git add frontend/src/types/orgchart-types.ts frontend/src/pages/Orgchart.vue
git commit -m "feat(orgchart): add view mode state management"
```

---

## Task 2: Add View Mode Selector UI

**Files:**
- Modify: `frontend/src/pages/Orgchart.vue:175-230` (toolbar section)

**Step 1: Add view mode selector after preset controls**

In `frontend/src/pages/Orgchart.vue` template, after the preset selector (around line 187), add:

```vue
<div class="h-4 w-px bg-slate-600"></div>

<!-- View Mode Selector -->
<div class="flex items-center gap-2">
  <span class="text-gray-400">Vue:</span>
  <div class="flex bg-slate-700 rounded overflow-hidden">
    <button
      v-for="(config, mode) in VIEW_MODES"
      :key="mode"
      @click="viewMode = mode as ViewMode"
      :class="[
        'px-3 py-1 text-xs transition-colors',
        viewMode === mode
          ? 'bg-cyan-600 text-white'
          : 'text-gray-300 hover:bg-slate-600'
      ]"
      :title="config.description"
    >
      {{ config.icon }} {{ config.name }}
    </button>
  </div>
</div>
```

**Step 2: Test UI in browser**

```bash
docker compose restart api
```

Navigate to http://localhost:8001/orgchart

Expected: Three view mode buttons (Complexité, Hubs, Hiérarchie) appear in toolbar, clicking changes active state

**Step 3: Verify localStorage persistence**

1. Select "Hubs" mode
2. Refresh page (F5)
3. Expected: "Hubs" mode still selected

**Step 4: Commit**

```bash
git add frontend/src/pages/Orgchart.vue
git commit -m "feat(orgchart): add view mode selector UI with persistence"
```

---

## Task 3: Extend GraphNode Interface with Metrics

**Files:**
- Modify: `frontend/src/components/OrgchartGraph.vue:11-16`
- Modify: `frontend/src/composables/useCodeGraph.ts` (to fetch metrics)

**Step 1: Extend GraphNode interface**

In `frontend/src/components/OrgchartGraph.vue`, replace GraphNode interface (lines 11-16):

```typescript
interface GraphNode {
  id: string
  label: string
  type: string
  file_path?: string
  // Complexity metrics
  cyclomatic_complexity?: number
  lines_of_code?: number
  // Connection metrics (computed on backend or frontend)
  incoming_edges?: number
  outgoing_edges?: number
  total_edges?: number
  // Hierarchy metrics
  depth?: number
  descendants_count?: number
}
```

**Step 2: Update API response type in useCodeGraph.ts**

Check `frontend/src/composables/useCodeGraph.ts` to ensure it returns these properties.

If `fetchGraphData` needs updating to include metrics, modify the API call to request additional fields.

**Step 3: Verify type safety**

```bash
cd frontend
pnpm vite build --mode development
```

Expected: SUCCESS, no TypeScript errors about missing properties

**Step 4: Commit**

```bash
git add frontend/src/components/OrgchartGraph.vue frontend/src/composables/useCodeGraph.ts
git commit -m "feat(orgchart): extend GraphNode with complexity and connection metrics"
```

---

## Task 4: Create Visual Encoding Functions

**Files:**
- Create: `frontend/src/utils/orgchart-visual-encoding.ts`

**Step 1: Create visual encoding utilities**

Create `frontend/src/utils/orgchart-visual-encoding.ts`:

```typescript
import type { ViewMode } from '@/types/orgchart-types'

export interface NodeVisualStyle {
  fill: string
  size: [number, number]
}

// Complexity Mode: Green → Yellow → Orange → Red based on cyclomatic complexity
export function getComplexityColor(complexity: number = 0): string {
  if (complexity <= 10) return '#10b981'  // Green
  if (complexity <= 20) return '#fbbf24'  // Yellow
  if (complexity <= 30) return '#f97316'  // Orange
  return '#ef4444'  // Red
}

// Complexity Mode: Size based on LOC (min 100, max 400)
export function getComplexitySize(loc: number = 0): [number, number] {
  const clampedLoc = Math.max(50, Math.min(loc, 500))
  const width = 100 + (clampedLoc / 500) * 150  // 100-250px
  const height = 30 + (clampedLoc / 500) * 30   // 30-60px
  return [width, height]
}

// Hubs Mode: Blue (many incoming) → Violet (balanced) → Orange (many outgoing)
export function getHubsColor(incomingRatio: number): string {
  // incomingRatio = incoming / total (0 to 1)
  // 0.0-0.3: Orange (depends on others)
  // 0.3-0.7: Violet (balanced)
  // 0.7-1.0: Blue (depended upon)

  if (incomingRatio >= 0.7) {
    // Blue gradient
    const intensity = (incomingRatio - 0.7) / 0.3
    return `rgb(${59 - intensity * 30}, ${130 + intensity * 10}, ${246})`
  } else if (incomingRatio >= 0.3) {
    // Violet
    return '#8b5cf6'
  } else {
    // Orange gradient
    const intensity = (0.3 - incomingRatio) / 0.3
    return `rgb(${249}, ${151 - intensity * 50}, ${22 + intensity * 30})`
  }
}

// Hubs Mode: Size based on total connections (min 80, max 300)
export function getHubsSize(totalConnections: number = 0): [number, number] {
  const clampedTotal = Math.max(1, Math.min(totalConnections, 200))
  const width = 80 + (clampedTotal / 200) * 220  // 80-300px
  const height = 30 + (clampedTotal / 200) * 50  // 30-80px
  return [width, height]
}

// Hierarchy Mode: Color gradient based on depth (lighter at top, darker at bottom)
export function getHierarchyColor(depth: number = 0, nodeType: string): string {
  if (depth === 0) return '#8b5cf6'  // Root: Purple
  if (depth === 1) return '#06b6d4'  // Level 1 (Modules): Cyan

  // Levels 2+: Blue gradient getting darker
  // Level 2: #3b82f6 (lighter blue)
  // Level 3: #2563eb (medium blue)
  // Level 4+: #1e40af (darker blue)
  const blueLevels = ['#3b82f6', '#2563eb', '#1e40af', '#1e3a8a']
  const index = Math.min(depth - 2, blueLevels.length - 1)
  return blueLevels[index]
}

// Hierarchy Mode: Size based on descendants count (min 100, max 250)
export function getHierarchySize(descendantsCount: number = 0): [number, number] {
  const clampedCount = Math.max(0, Math.min(descendantsCount, 100))
  const width = 100 + (clampedCount / 100) * 150  // 100-250px
  const height = 30 + (clampedCount / 100) * 30   // 30-60px
  return [width, height]
}

// Main function: Calculate visual style based on view mode
export function calculateNodeStyle(
  node: any,
  viewMode: ViewMode
): NodeVisualStyle {
  switch (viewMode) {
    case 'complexity':
      return {
        fill: getComplexityColor(node.data.cyclomatic_complexity),
        size: getComplexitySize(node.data.lines_of_code)
      }

    case 'hubs':
      const totalEdges = node.data.total_edges || 1
      const incomingRatio = (node.data.incoming_edges || 0) / totalEdges
      return {
        fill: getHubsColor(incomingRatio),
        size: getHubsSize(totalEdges)
      }

    case 'hierarchy':
      return {
        fill: getHierarchyColor(node.data.depth, node.data.nodeType),
        size: getHierarchySize(node.data.descendants_count)
      }

    default:
      return {
        fill: '#64748b',
        size: [140, 40]
      }
  }
}
```

**Step 2: Write unit tests**

Create `frontend/src/utils/__tests__/orgchart-visual-encoding.test.ts`:

```typescript
import { describe, it, expect } from 'vitest'
import {
  getComplexityColor,
  getComplexitySize,
  getHubsColor,
  getHubsSize,
  getHierarchyColor,
  getHierarchySize
} from '../orgchart-visual-encoding'

describe('orgchart-visual-encoding', () => {
  describe('Complexity Mode', () => {
    it('returns green for low complexity', () => {
      expect(getComplexityColor(5)).toBe('#10b981')
    })

    it('returns red for high complexity', () => {
      expect(getComplexityColor(40)).toBe('#ef4444')
    })

    it('scales size with LOC', () => {
      const [width1] = getComplexitySize(100)
      const [width2] = getComplexitySize(300)
      expect(width2).toBeGreaterThan(width1)
    })
  })

  describe('Hubs Mode', () => {
    it('returns blue for high incoming ratio', () => {
      const color = getHubsColor(0.9)
      expect(color).toContain('rgb')
      // Blue-ish color
    })

    it('returns orange for low incoming ratio', () => {
      const color = getHubsColor(0.1)
      expect(color).toContain('rgb')
      // Orange-ish color
    })
  })

  describe('Hierarchy Mode', () => {
    it('returns purple for root', () => {
      expect(getHierarchyColor(0, 'Root')).toBe('#8b5cf6')
    })

    it('returns cyan for level 1', () => {
      expect(getHierarchyColor(1, 'Module')).toBe('#06b6d4')
    })
  })
})
```

**Step 3: Run tests**

```bash
cd frontend
pnpm test orgchart-visual-encoding
```

Expected: All tests PASS

**Step 4: Commit**

```bash
git add frontend/src/utils/orgchart-visual-encoding.ts frontend/src/utils/__tests__/orgchart-visual-encoding.test.ts
git commit -m "feat(orgchart): add visual encoding functions for 3 view modes"
```

---

## Task 5: Integrate Visual Encoding into OrgchartGraph

**Files:**
- Modify: `frontend/src/components/OrgchartGraph.vue:220-245` (node style section)
- Modify: `frontend/src/components/OrgchartGraph.vue:31-35` (add viewMode prop)

**Step 1: Add viewMode prop**

In `frontend/src/components/OrgchartGraph.vue`, modify Props interface (around line 31):

```typescript
import type { ViewMode } from '@/types/orgchart-types'

interface Props {
  nodes: GraphNode[]
  edges: GraphEdge[]
  config?: OrgchartConfig
  viewMode?: ViewMode  // NEW
}

const props = withDefaults(defineProps<Props>(), {
  viewMode: 'hierarchy'
})
```

**Step 2: Replace node style function**

In `frontend/src/components/OrgchartGraph.vue`, replace the node style section in initGraph (around lines 227-243):

```typescript
import { calculateNodeStyle } from '@/utils/orgchart-visual-encoding'

// ... in initGraph()
node: {
  type: 'rect',
  style: {
    // Dynamic size and color based on view mode
    ...((d: any) => calculateNodeStyle(d, props.viewMode)),

    radius: 4,
    labelText: (d: any) => {
      const label = d.data.label || ''
      return label.length > 18 ? label.substring(0, 15) + '...' : label
    },
    labelFill: '#e2e8f0',
    labelFontSize: 11,
    labelFontWeight: 500,
    labelPlacement: 'center',
    stroke: '#ffffff',
    lineWidth: 2
  }
}
```

**Step 3: Test visual changes**

```bash
pnpm vite build --mode development
docker compose restart api
```

Navigate to http://localhost:8001/orgchart and switch between view modes.

Expected: Node colors and sizes change smoothly when switching modes

**Step 4: Commit**

```bash
git add frontend/src/components/OrgchartGraph.vue
git commit -m "feat(orgchart): integrate visual encoding into graph rendering"
```

---

## Task 6: Pass viewMode Prop from Parent

**Files:**
- Modify: `frontend/src/pages/Orgchart.vue:286` (OrgchartGraph component)

**Step 1: Pass viewMode to child component**

In `frontend/src/pages/Orgchart.vue`, update the OrgchartGraph component call (around line 286):

```vue
<OrgchartGraph
  :key="graphKey"
  :nodes="nodes"
  :edges="edges"
  :config="orgchartConfig"
  :view-mode="viewMode"
/>
```

**Step 2: Test mode switching**

```bash
pnpm vite build --mode development
docker compose restart api
```

Navigate to http://localhost:8001/orgchart.

Test sequence:
1. Click "Complexité" → nodes should show green/yellow/orange/red colors
2. Click "Hubs" → nodes should show blue/violet/orange colors
3. Click "Hiérarchie" → nodes should show depth gradient (purple→cyan→blue)

Expected: Smooth color transitions (0.5s) when switching modes

**Step 3: Commit**

```bash
git add frontend/src/pages/Orgchart.vue
git commit -m "feat(orgchart): connect view mode selector to graph visualization"
```

---

## Task 7: Add Smooth Transition Animation

**Files:**
- Modify: `frontend/src/components/OrgchartGraph.vue:320-340` (watch section)

**Step 1: Watch viewMode prop for changes**

In `frontend/src/components/OrgchartGraph.vue`, after the existing watch for nodes/edges (around line 340), add:

```typescript
// Watch for view mode changes
watch(() => props.viewMode, async (newMode, oldMode) => {
  if (!graph || newMode === oldMode) return

  console.log('[Orgchart] View mode changed:', oldMode, '→', newMode)

  // Get all nodes
  const nodes = graph.getAllNodesData()

  // Update each node's style with transition
  nodes.forEach((node: any) => {
    const newStyle = calculateNodeStyle(node, newMode)

    graph.updateNodeData([{
      id: node.id,
      data: {
        ...node.data,
        style: {
          ...node.data.style,
          ...newStyle,
          // Add transition animation
          transition: ['fill', 'size'],
          transitionDuration: 500
        }
      }
    }])
  })

  // Re-render with new styles
  await graph.render()

  console.log('[Orgchart] View mode transition complete')
})
```

**Step 2: Test animation smoothness**

```bash
pnpm vite build --mode development
docker compose restart api
```

Switch between modes rapidly.

Expected: Smooth 0.5s animation for color and size changes, no flickering

**Step 3: Commit**

```bash
git add frontend/src/components/OrgchartGraph.vue
git commit -m "feat(orgchart): add smooth transition animation between view modes"
```

---

## Task 8: Adaptive Tooltips Based on View Mode

**Files:**
- Modify: `frontend/src/components/OrgchartGraph.vue:284-325` (tooltip plugin)

**Step 1: Create tooltip content function**

In `frontend/src/components/OrgchartGraph.vue`, before initGraph, add helper function:

```typescript
const getTooltipContent = (item: any, viewMode: ViewMode): string => {
  const typeColors: Record<string, string> = {
    Module: '#06b6d4',
    Class: '#3b82f6',
    Function: '#10b981',
    Method: '#8b5cf6',
    Interface: '#f59e0b',
    Config: '#ec4899',
    default: '#64748b'
  }
  const color = typeColors[item.data.nodeType] || typeColors.default

  // Base header (always shown)
  let content = `
    <div style="padding: 12px; min-width: 200px; background: #1e293b; border: 1px solid #334155; border-radius: 6px;">
      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
        <div style="width: 12px; height: 12px; border-radius: 50%; background: ${color};"></div>
        <strong style="color: #e2e8f0; font-size: 13px;">${item.data.label}</strong>
      </div>
      <div style="font-size: 10px; color: #94a3b8; margin-bottom: 6px;">
        <span style="display: inline-block; padding: 2px 6px; background: ${color}33; color: ${color}; border-radius: 3px;">
          ${item.data.nodeType}
        </span>
      </div>
  `

  // Mode-specific metrics
  if (viewMode === 'complexity') {
    const complexity = item.data.cyclomatic_complexity || 0
    const loc = item.data.lines_of_code || 0
    const complexityLevel = complexity > 40 ? 'High ⚠️' : complexity > 20 ? 'Medium' : 'Low'
    const refactoringNeeded = complexity > 40 ? '<div style="color: #ef4444; margin-top: 4px;">⚠️ Refactoring recommended</div>' : ''

    content += `
      <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #334155;">
        <div style="color: #94a3b8; font-size: 10px; margin-bottom: 4px;">
          📊 Complexité: <span style="color: #e2e8f0; font-weight: 600;">${complexity}</span> (${complexityLevel})
        </div>
        <div style="color: #94a3b8; font-size: 10px;">
          📏 Lines: <span style="color: #e2e8f0; font-weight: 600;">${loc}</span>
        </div>
        ${refactoringNeeded}
      </div>
    `
  } else if (viewMode === 'hubs') {
    const incoming = item.data.incoming_edges || 0
    const outgoing = item.data.outgoing_edges || 0
    const total = item.data.total_edges || incoming + outgoing
    const criticality = incoming > outgoing * 2 ? 'Critical dependency' : outgoing > incoming * 2 ? 'Heavy user' : 'Balanced'

    content += `
      <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #334155;">
        <div style="color: #94a3b8; font-size: 10px; margin-bottom: 4px;">
          🔗 Connections: <span style="color: #e2e8f0; font-weight: 600;">${total}</span>
        </div>
        <div style="color: #94a3b8; font-size: 10px; margin-bottom: 4px;">
          ↙️  Incoming: <span style="color: #e2e8f0; font-weight: 600;">${incoming}</span>
        </div>
        <div style="color: #94a3b8; font-size: 10px; margin-bottom: 4px;">
          ↗️  Outgoing: <span style="color: #e2e8f0; font-weight: 600;">${outgoing}</span>
        </div>
        <div style="color: #06b6d4; font-size: 9px; margin-top: 4px;">
          ${criticality}
        </div>
      </div>
    `
  } else if (viewMode === 'hierarchy') {
    const depth = item.data.depth || 0
    const descendants = item.data.descendants_count || 0

    content += `
      <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #334155;">
        <div style="color: #94a3b8; font-size: 10px; margin-bottom: 4px;">
          📦 Level: <span style="color: #e2e8f0; font-weight: 600;">${depth}</span>
        </div>
        <div style="color: #94a3b8; font-size: 10px;">
          🌳 Descendants: <span style="color: #e2e8f0; font-weight: 600;">${descendants}</span>
        </div>
      </div>
    `
  }

  // File path (always shown)
  if (item.data.file_path) {
    content += `
      <div style="font-size: 9px; color: #64748b; font-family: monospace; word-break: break-all; margin-top: 8px; padding-top: 8px; border-top: 1px solid #334155;">
        ${item.data.file_path}
      </div>
    `
  }

  content += `</div>`
  return content
}
```

**Step 2: Update tooltip plugin**

Replace the tooltip getContent function (around line 287) with:

```typescript
{
  type: 'tooltip',
  enable: true,
  getContent: (_evt: any, items: any[]) => {
    const item = items[0]
    if (!item) return ''
    return getTooltipContent(item, props.viewMode)
  }
}
```

**Step 3: Test tooltips in each mode**

```bash
pnpm vite build --mode development
docker compose restart api
```

Test sequence:
1. Switch to "Complexité" → hover nodes → should show complexity + LOC
2. Switch to "Hubs" → hover nodes → should show incoming/outgoing connections
3. Switch to "Hiérarchie" → hover nodes → should show depth + descendants

Expected: Tooltips adapt to show relevant metrics for each mode

**Step 4: Commit**

```bash
git add frontend/src/components/OrgchartGraph.vue
git commit -m "feat(orgchart): add adaptive tooltips based on view mode"
```

---

## Task 9: Calculate Connection Metrics on Frontend

**Files:**
- Modify: `frontend/src/components/OrgchartGraph.vue:72-90` (initGraph preprocessing)

**Step 1: Add connection metrics calculation**

In `frontend/src/components/OrgchartGraph.vue`, before building the tree (around line 120), add:

```typescript
// Calculate connection metrics for each node
const nodeConnectionMetrics = new Map<string, {
  incoming: number
  outgoing: number
  total: number
}>()

// Initialize metrics
props.nodes.forEach(node => {
  nodeConnectionMetrics.set(node.id, {
    incoming: 0,
    outgoing: 0,
    total: 0
  })
})

// Count connections from edges
props.edges.forEach(edge => {
  // Outgoing for source
  const sourceMetrics = nodeConnectionMetrics.get(edge.source)
  if (sourceMetrics) {
    sourceMetrics.outgoing++
    sourceMetrics.total++
  }

  // Incoming for target
  const targetMetrics = nodeConnectionMetrics.get(edge.target)
  if (targetMetrics) {
    targetMetrics.incoming++
    targetMetrics.total++
  }
})

console.log('[Orgchart] Calculated connection metrics for', nodeConnectionMetrics.size, 'nodes')
```

**Step 2: Add metrics to node data**

In the buildNode function (around line 177), update the return statement:

```typescript
const metrics = nodeConnectionMetrics.get(nodeId) || { incoming: 0, outgoing: 0, total: 0 }

return {
  id: node.id,
  data: {
    label: getModuleLabel(node),
    nodeType: node.type,
    file_path: node.file_path,
    depth,
    // Add metrics from node properties
    cyclomatic_complexity: (node as any).cyclomatic_complexity,
    lines_of_code: (node as any).lines_of_code,
    // Add calculated connection metrics
    incoming_edges: metrics.incoming,
    outgoing_edges: metrics.outgoing,
    total_edges: metrics.total,
    // Descendants count (calculated recursively)
    descendants_count: childNodes.length > 0 ? childNodes.reduce((sum, child) => {
      return sum + 1 + (child.data.descendants_count || 0)
    }, 0) : 0
  },
  children: childNodes.length > 0 ? childNodes : undefined
}
```

**Step 3: Verify metrics in console**

```bash
pnpm vite build --mode development
docker compose restart api
```

Open browser console, should see:
```
[Orgchart] Calculated connection metrics for 724 nodes
```

**Step 4: Commit**

```bash
git add frontend/src/components/OrgchartGraph.vue
git commit -m "feat(orgchart): calculate connection and hierarchy metrics on frontend"
```

---

## Task 10: Add View Mode Legend

**Files:**
- Modify: `frontend/src/pages/Orgchart.vue:270-285` (add legend card)

**Step 1: Create legend component**

In `frontend/src/pages/Orgchart.vue` template, after the stats card (around line 283), add:

```vue
<!-- Legend Card (adapts to view mode) -->
<div class="bg-slate-800/50 rounded-lg border border-slate-700 p-3 mb-4">
  <div class="text-xs text-gray-400 mb-2 font-semibold uppercase tracking-wide">
    {{ VIEW_MODES[viewMode].icon }} {{ VIEW_MODES[viewMode].name }} - Légende
  </div>

  <!-- Complexity Mode Legend -->
  <div v-if="viewMode === 'complexity'" class="flex flex-wrap gap-3 text-xs">
    <div class="flex items-center gap-2">
      <div class="w-4 h-4 rounded" style="background: #10b981;"></div>
      <span class="text-gray-300">Faible (0-10)</span>
    </div>
    <div class="flex items-center gap-2">
      <div class="w-4 h-4 rounded" style="background: #fbbf24;"></div>
      <span class="text-gray-300">Moyen (11-20)</span>
    </div>
    <div class="flex items-center gap-2">
      <div class="w-4 h-4 rounded" style="background: #f97316;"></div>
      <span class="text-gray-300">Élevé (21-30)</span>
    </div>
    <div class="flex items-center gap-2">
      <div class="w-4 h-4 rounded" style="background: #ef4444;"></div>
      <span class="text-gray-300">Critique (31+)</span>
    </div>
    <div class="ml-4 text-gray-500">
      <span>Taille = Lines of Code</span>
    </div>
  </div>

  <!-- Hubs Mode Legend -->
  <div v-else-if="viewMode === 'hubs'" class="flex flex-wrap gap-3 text-xs">
    <div class="flex items-center gap-2">
      <div class="w-4 h-4 rounded" style="background: rgb(59, 130, 246);"></div>
      <span class="text-gray-300">Dépendance (utilisé partout)</span>
    </div>
    <div class="flex items-center gap-2">
      <div class="w-4 h-4 rounded" style="background: #8b5cf6;"></div>
      <span class="text-gray-300">Équilibré</span>
    </div>
    <div class="flex items-center gap-2">
      <div class="w-4 h-4 rounded" style="background: rgb(249, 151, 22);"></div>
      <span class="text-gray-300">Consommateur (utilise beaucoup)</span>
    </div>
    <div class="ml-4 text-gray-500">
      <span>Taille = Nombre de connections</span>
    </div>
  </div>

  <!-- Hierarchy Mode Legend -->
  <div v-else-if="viewMode === 'hierarchy'" class="flex flex-wrap gap-3 text-xs">
    <div class="flex items-center gap-2">
      <div class="w-4 h-4 rounded" style="background: #8b5cf6;"></div>
      <span class="text-gray-300">Root</span>
    </div>
    <div class="flex items-center gap-2">
      <div class="w-4 h-4 rounded" style="background: #06b6d4;"></div>
      <span class="text-gray-300">Modules (Level 1)</span>
    </div>
    <div class="flex items-center gap-2">
      <div class="w-4 h-4 rounded" style="background: #3b82f6;"></div>
      <span class="text-gray-300">Classes (Level 2)</span>
    </div>
    <div class="flex items-center gap-2">
      <div class="w-4 h-4 rounded" style="background: #1e40af;"></div>
      <span class="text-gray-300">Deep (Level 3+)</span>
    </div>
    <div class="ml-4 text-gray-500">
      <span>Taille = Nombre de descendants</span>
    </div>
  </div>
</div>
```

**Step 2: Test legend visibility**

```bash
pnpm vite build --mode development
docker compose restart api
```

Switch between modes, legend should update accordingly.

**Step 3: Commit**

```bash
git add frontend/src/pages/Orgchart.vue
git commit -m "feat(orgchart): add adaptive legend for each view mode"
```

---

## Task 11: Final Integration Testing

**Step 1: Full workflow test**

```bash
pnpm vite build --mode development
docker compose restart api
```

Navigate to http://localhost:8001/orgchart

**Test Checklist:**
- [ ] Page loads with default "Hiérarchie" mode
- [ ] Click "Complexité" → nodes turn green/yellow/orange/red
- [ ] Hover nodes → tooltip shows complexity + LOC
- [ ] Large LOC nodes are visibly bigger
- [ ] Legend updates to show complexity scale
- [ ] Click "Hubs" → nodes turn blue/violet/orange
- [ ] Hover nodes → tooltip shows incoming/outgoing connections
- [ ] Highly connected nodes are visibly bigger
- [ ] Legend updates to show hub categories
- [ ] Click "Hiérarchie" → nodes show depth gradient
- [ ] Hover nodes → tooltip shows depth + descendants
- [ ] Nodes with many descendants are bigger
- [ ] Legend updates to show hierarchy levels
- [ ] Refresh page → selected mode persists (localStorage)
- [ ] Transitions are smooth (0.5s animation)

**Step 2: Performance check**

With 724 nodes:
- Mode switching should take < 1 second
- No lag or stuttering during transition
- Memory usage should be stable (no leaks)

**Step 3: Create test report**

Create `docs/testing/orgchart-multi-view-test-report.md`:

```markdown
# Orgchart Multi-View Visualization Test Report

Date: 2025-11-03
Tester: [Your Name]

## Test Environment
- Browser: Chrome/Firefox/Safari
- Dataset: CVgenerator (724 nodes, 617 edges)

## Test Results

### Complexity Mode
- [ ] Color gradient working (green → red)
- [ ] Size scaling with LOC working
- [ ] Tooltip shows complexity + LOC
- [ ] Legend accurate
- Notes: ____

### Hubs Mode
- [ ] Color gradient working (blue → violet → orange)
- [ ] Size scaling with connections working
- [ ] Tooltip shows incoming/outgoing
- [ ] Legend accurate
- Notes: ____

### Hierarchy Mode
- [ ] Depth gradient working (purple → cyan → blue)
- [ ] Size scaling with descendants working
- [ ] Tooltip shows depth + descendants
- [ ] Legend accurate
- Notes: ____

### Performance
- Mode switch time: ____ ms
- Animation smoothness: ____/10
- Memory stable: Yes/No

## Issues Found
1. ____
2. ____

## Recommendations
1. ____
2. ____
```

**Step 4: Commit final version**

```bash
git add docs/testing/orgchart-multi-view-test-report.md
git commit -m "test(orgchart): add multi-view visualization test report"
```

---

## Task 12: Documentation

**Step 1: Update feature documentation**

Create `docs/features/orgchart-multi-view.md`:

```markdown
# Orgchart Multi-View Visualization

## Overview

The organizational chart supports three view modes that reveal different aspects of the codebase through visual encoding (color + size).

## View Modes

### 1. Complexity Mode 📊
**Purpose:** Identify technical debt hotspots

**Visual Encoding:**
- **Color:** Cyclomatic complexity gradient
  - Green (0-10): Simple, maintainable
  - Yellow (11-20): Medium complexity
  - Orange (21-30): High complexity
  - Red (31+): Critical, needs refactoring
- **Size:** Lines of Code (LOC)
  - Larger nodes = more code

**Use Cases:**
- Find modules needing refactoring
- Prioritize code review efforts
- Track technical debt

### 2. Hubs Mode 🔗
**Purpose:** Reveal architectural dependencies and risks

**Visual Encoding:**
- **Color:** Connection ratio (incoming/outgoing)
  - Blue: Depended upon (critical dependency)
  - Violet: Balanced
  - Orange: Heavy user (depends on many others)
- **Size:** Total connections
  - Larger nodes = more connected

**Use Cases:**
- Identify single points of failure
- Spot "god objects" (over-connected)
- Understand dependency flow

### 3. Hierarchy Mode 🌳
**Purpose:** Explore structural depth and importance

**Visual Encoding:**
- **Color:** Depth in hierarchy
  - Purple: Root
  - Cyan: Modules (Level 1)
  - Blue gradient: Deeper levels
- **Size:** Number of descendants
  - Larger nodes = more sub-components

**Use Cases:**
- Understand module structure
- Find super-modules (many children)
- Analyze architectural layering

## Usage

1. Navigate to `/orgchart`
2. Select view mode using toolbar buttons
3. Hover nodes for detailed metrics
4. Refer to legend for color/size interpretation

## Technical Details

- **Implementation:** Vue 3 + @antv/g6 v5
- **Transition:** 0.5s smooth animation
- **State Persistence:** localStorage
- **Metrics Source:** PostgreSQL graph_nodes properties + frontend calculation
