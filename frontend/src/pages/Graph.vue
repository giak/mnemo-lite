<script setup lang="ts">
/**
 * EPIC-25 Story 25.5: Code Graph Page
 * Interactive code graph visualization using v-network-graph
 * Migrated from Cytoscape.js to v-network-graph for better Vue 3 integration
 */

import { ref, computed, onMounted } from 'vue'
import { useCodeGraph } from '@/composables/useCodeGraph'
import type { Nodes, Edges, Configs, Layouts } from 'v-network-graph'
import G6Graph from '@/components/G6Graph.vue'

const { stats, graphData, loading, error, building, buildError, fetchStats, fetchGraphData, buildGraph } = useCodeGraph()

const repository = ref('CVGenerator')
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
  for (const [file, nodeIds] of nodesByFile.entries()) {
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
const configs = computed<Configs>(() => ({
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

// Fetch stats and graph data on mount
onMounted(async () => {
  await fetchStats(repository.value)
  // Load 80 nodes with hierarchical layout (grouped by file)
  await fetchGraphData(repository.value, 80)
})
</script>

<template>
  <div class="min-h-screen bg-slate-950">
    <div class="max-w-full mx-auto px-4 py-6">
      <!-- Header -->
      <div class="mb-6">
        <h1 class="text-3xl text-heading">Code Graph</h1>
        <p class="mt-2 text-sm text-gray-400">
          Visual representation of code dependencies and relationships
        </p>
      </div>

      <!-- Loading State -->
      <div v-if="loading" class="section">
        <div class="animate-pulse">
          <div class="h-4 bg-slate-700 w-1/4 mb-4"></div>
          <div class="h-64 bg-slate-700"></div>
        </div>
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="alert-error">
        <div class="flex items-start">
          <svg class="h-5 w-5 text-red-400 mt-0.5" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
          </svg>
          <div class="ml-3">
            <h3 class="text-sm font-medium text-red-300 uppercase">Graph Error</h3>
            <p class="mt-1 text-sm text-red-400">{{ error }}</p>
          </div>
        </div>
      </div>

      <!-- Graph Stats + Visualization -->
      <div v-else-if="stats" class="space-y-4">
        <!-- Stats Cards -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
          <!-- Total Nodes -->
          <div class="section">
            <div class="flex items-center justify-between">
              <div>
                <p class="label">Total Nodes</p>
                <p class="text-3xl font-bold text-cyan-400">{{ stats.total_nodes }}</p>
              </div>
              <svg class="h-10 w-10 text-cyan-500/30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
          </div>

          <!-- Total Edges -->
          <div class="section">
            <div class="flex items-center justify-between">
              <div>
                <p class="label">Total Edges</p>
                <p class="text-3xl font-bold text-emerald-400">{{ stats.total_edges }}</p>
              </div>
              <svg class="h-10 w-10 text-emerald-500/30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
          </div>

          <!-- Classes -->
          <div class="section">
            <div class="flex items-center justify-between">
              <div>
                <p class="label">Classes</p>
                <p class="text-3xl font-bold text-blue-400">{{ stats.nodes_by_type.class || 0 }}</p>
              </div>
              <svg class="h-10 w-10 text-blue-500/30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
          </div>

          <!-- Functions -->
          <div class="section">
            <div class="flex items-center justify-between">
              <div>
                <p class="label">Functions</p>
                <p class="text-3xl font-bold text-purple-400">{{ stats.nodes_by_type.function || 0 }}</p>
              </div>
              <svg class="h-10 w-10 text-purple-500/30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
              </svg>
            </div>
          </div>
        </div>

        <!-- Build Error Banner -->
        <div v-if="buildError" class="alert-error">
          <div class="flex items-start">
            <svg class="h-5 w-5 text-red-400 mt-0.5" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
            </svg>
            <div class="ml-3">
              <h3 class="text-sm font-medium text-red-300 uppercase">Build Error</h3>
              <p class="mt-1 text-sm text-red-400">{{ buildError }}</p>
            </div>
          </div>
        </div>

        <!-- Graph Visualization -->
        <div class="section">
          <div class="mb-4 flex items-center justify-between">
            <div>
              <h2 class="text-xl font-semibold text-heading">Graph Visualization</h2>
              <p class="text-sm text-gray-400 mt-1">
                {{ useG6 ? 'Radial layout with depth effect. Click nodes to refocus.' : 'Hierarchical view grouped by file. Each column represents a file. Hover for details.' }}
              </p>
            </div>
            <div class="flex items-center gap-3">
              <!-- Toggle between G6 and v-network-graph -->
              <div class="flex items-center gap-2 text-sm">
                <button
                  @click="useG6 = false"
                  class="px-3 py-1 rounded transition-colors"
                  :class="!useG6 ? 'bg-cyan-600 text-white' : 'bg-slate-700 text-gray-400 hover:bg-slate-600'"
                >
                  v-network-graph
                </button>
                <button
                  @click="useG6 = true"
                  class="px-3 py-1 rounded transition-colors"
                  :class="useG6 ? 'bg-cyan-600 text-white' : 'bg-slate-700 text-gray-400 hover:bg-slate-600'"
                >
                  G6 (Prototype)
                </button>
              </div>
              <button
                @click="handleBuildGraph"
                :disabled="building || loading"
                class="btn-primary"
              >
                <svg v-if="building" class="animate-spin -ml-1 mr-2 h-4 w-4 inline" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                {{ building ? 'Building...' : 'Build Graph' }}
              </button>
            </div>
          </div>

          <!-- G6 Graph (Prototype) -->
          <div v-if="useG6">
            <G6Graph
              v-if="graphData?.nodes && graphData.nodes.length > 0"
              :nodes="graphData.nodes"
              :edges="graphData.edges || []"
              :loading="loading"
            />
            <div v-else class="flex items-center justify-center h-[600px] bg-slate-900 border border-slate-700 rounded text-gray-400">
              No graph data available
            </div>
          </div>

          <!-- v-network-graph Container -->
          <div v-else class="w-full h-[600px] bg-slate-900 border border-slate-700 rounded overflow-hidden">
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
            <div class="flex items-center gap-6 text-sm text-gray-400">
              <div class="flex items-center gap-2">
                <div class="w-8 h-8 rounded bg-blue-500 border-2 border-white"></div>
                <span>Classes</span>
              </div>
              <div class="flex items-center gap-2">
                <div class="w-8 h-8 rounded-full bg-green-500 border-2 border-white"></div>
                <span>Functions</span>
              </div>
              <div class="flex items-center gap-2">
                <div class="w-8 h-8 rounded-full bg-purple-500 border-2 border-white"></div>
                <span>Methods</span>
              </div>
              <div class="flex items-center gap-2">
                <svg class="w-8 h-1" viewBox="0 0 32 4">
                  <line x1="0" y1="2" x2="32" y2="2" stroke="#475569" stroke-width="2" />
                  <polygon points="28,0 32,2 28,4" fill="#475569" />
                </svg>
                <span>Function calls</span>
              </div>
            </div>
            <div class="text-xs text-gray-500">
              💡 Tip: Nodes are grouped vertically by file. Labels show filename:line. Hover for full details. Drag to pan, scroll to zoom.
            </div>
          </div>

          <!-- Info Message -->
          <div v-if="stats.total_nodes === 0" class="mt-4 p-4 bg-amber-900/20 border border-amber-700/30 rounded">
            <div class="flex items-start">
              <svg class="h-5 w-5 text-amber-400 mt-0.5" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
              </svg>
              <div class="ml-3">
                <h3 class="text-sm font-medium text-amber-300">Graph Not Built</h3>
                <p class="mt-1 text-sm text-amber-400/80">
                  The code graph has not been built yet. Click the <strong>"Build Graph"</strong> button above to analyze code dependencies and generate the graph.
                </p>
              </div>
            </div>
          </div>

          <!-- No Edges Warning -->
          <div v-else-if="stats.total_nodes > 0 && stats.total_edges === 0" class="mt-4 p-4 bg-blue-900/20 border border-blue-700/30 rounded">
            <div class="flex items-start">
              <svg class="h-5 w-5 text-blue-400 mt-0.5" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
              </svg>
              <div class="ml-3">
                <h3 class="text-sm font-medium text-blue-300">No Dependencies Detected</h3>
                <p class="mt-1 text-sm text-blue-400/80">
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
