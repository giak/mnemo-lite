<script setup lang="ts">
/**
 * EPIC-25 Story 25.5: Code Graph Page
 * Interactive code graph visualization using v-network-graph
 * Migrated from Cytoscape.js to v-network-graph for better Vue 3 integration
 */

import { ref, computed, onMounted, watch } from 'vue'
import { useCodeGraph } from '@/composables/useCodeGraph'
import type { Nodes, Edges, Configs, Layouts } from 'v-network-graph'
import G6Graph from '@/components/G6Graph.vue'

const { stats, graphData, loading, error, building, buildError, repositories, fetchStats, fetchGraphData, buildGraph, fetchRepositories } = useCodeGraph()

const repository = ref<string>('')
const useG6 = ref(true) // Toggle between v-network-graph and G6

// Extract human-readable name from file path
const extractNodeName = (node: any): string => {
  if (!node.file_path) return node.label

  // Extract filename from path
  const filename = node.file_path.split('/').pop() || node.label

  // Remove extension for cleaner display
  const nameWithoutExt = filename.replace(/\.(ts|tsx|js|jsx|py|java|go|rs)$/, '')

  // For methods/functions, show filename + line number
  if (node.type === 'method' || node.type === 'function') {
    return `${nameWithoutExt}:${node.start_line || '?'}`
  }

  // For classes, just show the filename
  return nameWithoutExt
}

// Extract grouping key for hierarchical layout
const getNodeGroup = (node: any): string => {
  if (!node.file_path) return 'ungrouped'
  return node.file_path
}

// Transform API data to v-network-graph format
const nodes = computed<Nodes>(() => {
  if (!graphData.value?.nodes) return {}

  const nodesMap: Nodes = {}
  for (const node of graphData.value.nodes) {
    nodesMap[node.id] = {
      name: extractNodeName(node),
      type: node.type,
      file_path: node.file_path,
      start_line: node.start_line,
      end_line: node.end_line,
      group: getNodeGroup(node),
      originalLabel: node.label
    }
  }
  return nodesMap
})

const edges = computed<Edges>(() => {
  if (!graphData.value?.edges) return {}

  const edgesMap: Edges = {}
  for (const edge of graphData.value.edges) {
    edgesMap[edge.id] = {
      source: edge.source,
      target: edge.target,
      type: edge.type
    }
  }

  // DEBUG: Log edges to verify transformation
  console.log(`[Graph] Transformed ${Object.keys(edgesMap).length} edges:`, Object.values(edgesMap).slice(0, 3))

  return edgesMap
})

// Generate hierarchical layout grouped by file with horizontal variation
// CRITICAL: Without positions, v-network-graph calculates expensive force-directed layout
const layouts = computed<Layouts>(() => {
  const layoutsMap: Layouts = { nodes: {} }

  // Group nodes by file
  const nodesByFile = new Map<string, string[]>()
  for (const [nodeId, node] of Object.entries(nodes.value)) {
    const file = node.file_path || 'unknown'
    if (!nodesByFile.has(file)) {
      nodesByFile.set(file, [])
    }
    nodesByFile.get(file)!.push(nodeId)
  }

  // Layout parameters
  const fileSpacingX = 300  // Horizontal space between file groups
  const nodeSpacingY = 80   // Vertical space between nodes in same file
  const nodeOffsetX = 60    // Horizontal variation within file (zigzag)
  const offsetX = 50
  const offsetY = 50

  // Position nodes: each file gets a column with zigzag pattern
  let fileIndex = 0
  for (const [_file, nodeIds] of nodesByFile.entries()) {
    const fileX = offsetX + fileIndex * fileSpacingX

    // Position nodes within this file with zigzag pattern for edge visibility
    nodeIds.forEach((nodeId, indexInFile) => {
      // Alternate left-right for visibility
      const xOffset = (indexInFile % 2 === 0) ? 0 : nodeOffsetX

      layoutsMap.nodes[nodeId] = {
        x: fileX + xOffset,
        y: offsetY + indexInFile * nodeSpacingY
      }
    })

    fileIndex++
  }

  console.log(`[Graph] Layout: ${nodesByFile.size} files, ${Object.keys(layoutsMap.nodes).length} nodes positioned`)

  return layoutsMap
})

// v-network-graph configuration
const configs: any = computed<Configs>(() => ({
  view: {
    autoPanAndZoomOnLoad: 'fit-content',
    panEnabled: true,
    zoomEnabled: true
  },
  node: {
    selectable: true,
    draggable: true,
    normal: {
      type: (node) => {
        // Use different shapes for different node types
        return node.type === 'class' ? 'rect' : 'circle'
      },
      radius: (node) => {
        // Classes are bigger
        return node.type === 'class' ? 24 : 20
      },
      width: 48, // For rect shape (classes)
      height: 48,
      color: (node) => {
        switch (node.type) {
          case 'class':
            return '#3b82f6' // blue
          case 'function':
            return '#10b981' // green
          case 'method':
            return '#8b5cf6' // purple
          default:
            return '#64748b' // gray
        }
      },
      strokeWidth: 2,
      strokeColor: '#ffffff'
    },
    hover: {
      color: '#fbbf24' // amber on hover
    },
    label: {
      visible: true, // Show labels with extracted names
      fontFamily: 'ui-monospace, monospace',
      fontSize: 11,
      color: '#e2e8f0',
      margin: 6,
      direction: 'south', // Position label below node
      background: {
        visible: true,
        color: '#1e293b',
        padding: {
          vertical: 2,
          horizontal: 4
        },
        borderRadius: 3
      }
    },
    // Show detailed info on hover via custom tooltip content
    tooltip: {
      enabled: true,
      content: (nodeId: string) => {
        const node = nodes.value[nodeId]
        if (!node) return ''
        return `
          <div style="padding: 4px 8px; max-width: 300px;">
            <div style="font-weight: bold; margin-bottom: 4px;">${node.name}</div>
            <div style="font-size: 11px; color: #94a3b8;">Type: ${node.type}</div>
            <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">File: ${node.file_path || 'unknown'}</div>
            ${node.start_line ? `<div style="font-size: 11px; color: #94a3b8;">Lines: ${node.start_line}-${node.end_line || '?'}</div>` : ''}
          </div>
        `
      }
    },
    focusring: {
      visible: true,
      width: 4,
      padding: 3,
      color: '#fbbf24'
    }
  },
  edge: {
    selectable: true,
    normal: {
      width: 3, // THICK for visibility
      color: '#f59e0b', // BRIGHT amber/orange - very visible!
      dasharray: (edge) => edge.type === 'calls' ? '0' : '4 2',
      linecap: 'round'
    },
    hover: {
      width: 5,
      color: '#fbbf24'
    },
    selected: {
      width: 5,
      color: '#22d3ee', // cyan
      dasharray: '0'
    },
    marker: {
      target: {
        type: 'arrow',
        width: 10,
        height: 10,
        margin: -1,
        color: null // Inherit edge color
      }
    },
    gap: 3, // Less gap for better connection visibility
    type: 'curve' // Curved edges are more visible than straight
  }
}))

// Build graph handler
const handleBuildGraph = async () => {
  await buildGraph(repository.value, 'python')
  // Refresh visualization after build
  await fetchGraphData(repository.value, 500)
}

// Watch repository changes and reload data
watch(repository, async (newRepo) => {
  if (newRepo) {
    console.log('[Graph] Loading repository:', newRepo)
    await fetchStats(newRepo)
    await fetchGraphData(newRepo, 80)
    console.log('[Graph] Graph data loaded:', {
      nodes: graphData.value?.nodes?.length || 0,
      edges: graphData.value?.edges?.length || 0,
      hasData: !!graphData.value
    })
  }
})

// Fetch repositories on mount
onMounted(async () => {
  console.log('[Graph] Fetching repositories...')
  await fetchRepositories()
  console.log('[Graph] Available repositories:', repositories.value)

  // Select first repository by default
  if (repositories.value && repositories.value.length > 0) {
    repository.value = repositories.value[0] || ''
    // Explicitly load data for first repository
    await fetchStats(repository.value)
    await fetchGraphData(repository.value, 80)
    console.log('[Graph] Initial data loaded:', {
      nodes: graphData.value?.nodes?.length || 0,
      edges: graphData.value?.edges?.length || 0,
      hasData: !!graphData.value,
      graphData: graphData.value
    })
  }
})
</script>

<template>
  <div class="min-h-screen bg-slate-950">
    <div class="max-w-full mx-auto px-4 py-3">

      <!-- Loading State -->
      <div v-if="loading" class="section">
        <div class="animate-pulse">
          <div class="h-4 bg-slate-700 w-1/4 mb-4"></div>
          <div class="h-64 bg-slate-700"></div>
        </div>
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="alert-error">
        <div class="flex items-start gap-3">
          <span class="scada-led scada-led-red"></span>
          <div>
            <h3 class="text-sm font-medium text-red-300 uppercase font-mono">Graph Error</h3>
            <p class="mt-1 text-sm text-red-400 font-mono">{{ error }}</p>
          </div>
        </div>
      </div>

      <!-- Graph Stats + Visualization -->
      <div v-else-if="stats" class="space-y-2">
        <!-- Ultra-Compact Toolbar: Everything on one line -->
        <div class="bg-slate-800/50 rounded-lg px-4 py-2 flex items-center gap-4 border-2 border-slate-700 text-xs">
          <!-- Stats -->
          <div class="flex items-center gap-3">
            <div class="flex items-center gap-2">
              <span class="scada-led scada-led-cyan"></span>
              <span class="text-gray-500 uppercase tracking-wide font-mono">Graph</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="scada-label">N:</span>
              <span class="scada-data text-cyan-400">{{ stats.total_nodes }}</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="scada-label">E:</span>
              <span class="scada-data text-emerald-400">{{ stats.total_edges }}</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="scada-label">C:</span>
              <span class="scada-data text-blue-400">{{ stats.nodes_by_type.Class || 0 }}</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="scada-label">F:</span>
              <span class="scada-data text-purple-400">{{ stats.nodes_by_type.Function || 0 }}</span>
            </div>
          </div>

          <div class="h-4 w-px bg-slate-600"></div>

          <!-- Repository Selector -->
          <select
            v-model="repository"
            class="bg-slate-700 text-gray-200 border border-slate-600 rounded px-3 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="" disabled>Select repository...</option>
            <option v-for="repo in repositories" :key="repo" :value="repo">
              {{ repo }}
            </option>
          </select>

          <div class="h-4 w-px bg-slate-600"></div>

          <!-- Layout Toggle -->
          <div class="flex items-center gap-1">
            <span class="scada-label mr-1">View:</span>
            <button
              @click="useG6 = false"
              class="px-2 py-1 rounded text-xs transition-colors font-mono uppercase"
              :class="!useG6 ? 'bg-cyan-600 text-white' : 'bg-slate-700 text-gray-400 hover:bg-slate-600'"
            >
              Network
            </button>
            <button
              @click="useG6 = true"
              class="px-2 py-1 rounded text-xs transition-colors font-mono uppercase"
              :class="useG6 ? 'bg-cyan-600 text-white' : 'bg-slate-700 text-gray-400 hover:bg-slate-600'"
            >
              G6
            </button>
          </div>

          <div class="flex-1"></div>

          <!-- Build Graph Button -->
          <button
            @click="handleBuildGraph"
            :disabled="building || loading"
            class="scada-btn scada-btn-primary text-xs"
          >
            <svg v-if="building" class="animate-spin -ml-1 mr-1 h-3 w-3 inline" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {{ building ? 'BUILDING...' : 'BUILD' }}
          </button>
        </div>


        <!-- Build Error Banner -->
        <div v-if="buildError" class="alert-error">
          <div class="flex items-start gap-3">
            <span class="scada-led scada-led-red"></span>
            <div>
              <h3 class="text-sm font-medium text-red-300 uppercase font-mono">Build Error</h3>
              <p class="mt-1 text-sm text-red-400 font-mono">{{ buildError }}</p>
            </div>
          </div>
        </div>

        <!-- Graph Visualization -->
        <div class="section">

          <!-- G6 Graph (Prototype) -->
          <div v-if="useG6">
            <!-- Debug info -->
            <div class="text-xs text-gray-500 mb-2">
              Debug: graphData={{ !!graphData }}, nodes={{ graphData?.nodes?.length || 0 }}, edges={{ graphData?.edges?.length || 0 }}
            </div>

            <G6Graph
              v-if="graphData?.nodes && graphData.nodes.length > 0"
              :nodes="graphData.nodes"
              :edges="graphData.edges || []"
              :loading="loading"
            />
            <div v-else class="flex flex-col items-center justify-center h-[calc(100vh-120px)] bg-slate-900 border border-slate-700 rounded text-gray-400">
              <p>No graph data available</p>
              <p class="text-xs mt-2">graphData: {{ graphData ? 'exists' : 'null' }}</p>
              <p class="text-xs">nodes: {{ graphData?.nodes?.length || 0 }}</p>
            </div>
          </div>

          <!-- v-network-graph Container -->
          <div v-else class="w-full h-[calc(100vh-120px)] bg-slate-900 border border-slate-700 rounded overflow-hidden">
            <v-network-graph
              v-if="Object.keys(nodes).length > 0"
              :nodes="nodes"
              :edges="edges"
              :layouts="layouts"
              :configs="configs"
              class="w-full h-full"
            />
            <div v-else class="flex items-center justify-center h-full text-gray-400">
              No graph data available
            </div>
          </div>

          <!-- Legend (v-network-graph only) -->
          <div v-if="!useG6" class="mt-4 space-y-3">
            <div class="flex items-center gap-6 text-sm font-mono">
              <div class="flex items-center gap-2">
                <div class="w-8 h-8 rounded bg-blue-500 border-2 border-white"></div>
                <span class="uppercase">Classes</span>
              </div>
              <div class="flex items-center gap-2">
                <div class="w-8 h-8 rounded-full bg-green-500 border-2 border-white"></div>
                <span class="uppercase">Functions</span>
              </div>
              <div class="flex items-center gap-2">
                <div class="w-8 h-8 rounded-full bg-purple-500 border-2 border-white"></div>
                <span class="uppercase">Methods</span>
              </div>
              <div class="flex items-center gap-2">
                <svg class="w-8 h-1" viewBox="0 0 32 4">
                  <line x1="0" y1="2" x2="32" y2="2" stroke="#475569" stroke-width="2" />
                  <polygon points="28,0 32,2 28,4" fill="#475569" />
                </svg>
                <span class="uppercase">Function Calls</span>
              </div>
            </div>
            <div class="flex items-center gap-2 text-xs text-gray-500">
              <span class="scada-led scada-led-cyan"></span>
              <span class="font-mono uppercase">Tip: Nodes Grouped by File • Labels Show Filename:Line • Hover for Details • Drag to Pan, Scroll to Zoom</span>
            </div>
          </div>

          <!-- Info Message -->
          <div v-if="stats.total_nodes === 0" class="mt-4 p-4 bg-amber-900/20 border-2 border-amber-700/30 rounded">
            <div class="flex items-start gap-3">
              <span class="scada-led scada-led-yellow"></span>
              <div>
                <h3 class="text-sm font-medium text-amber-300 font-mono uppercase">Graph Not Built</h3>
                <p class="mt-1 text-sm text-amber-400/80 font-mono">
                  The code graph has not been built yet. Click the <strong>"BUILD GRAPH"</strong> button above to analyze code dependencies and generate the graph.
                </p>
              </div>
            </div>
          </div>

          <!-- No Edges Warning -->
          <div v-else-if="stats.total_nodes > 0 && stats.total_edges === 0" class="mt-4 p-4 bg-blue-900/20 border-2 border-blue-700/30 rounded">
            <div class="flex items-start gap-3">
              <span class="scada-led scada-led-cyan"></span>
              <div>
                <h3 class="text-sm font-medium text-blue-300 font-mono uppercase">No Dependencies Detected</h3>
                <p class="mt-1 text-sm text-blue-400/80 font-mono">
                  Graph shows {{ stats.total_nodes }} nodes but no edges. This means no code dependencies (imports/calls) were detected between functions and classes.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
