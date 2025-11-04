<script setup lang="ts">
/**
 * EPIC-25 Story 25.5: G6 Advanced Graph Visualization (v5)
 *
 * Features:
 * - Radial layout with depth visualization
 * - Click-to-focus with smooth animations
 * - Complexity encoding (size, color, opacity)
 * - Interactive exploration (drag, zoom, pan)
 */

import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { Graph } from '@antv/g6'

interface GraphNode {
  id: string
  label: string
  type: string
  file_path?: string
  start_line?: number
  end_line?: number
}

interface GraphEdge {
  id: string
  source: string
  target: string
  type: string
}

interface Props {
  nodes: GraphNode[]
  edges: GraphEdge[]
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false
})

const containerRef = ref<HTMLDivElement>()
let graph: Graph | null = null
const focusNodeId = ref<string | null>(null)
const selectedNode = ref<GraphNode | null>(null)
const hoveredNodeId = ref<string | null>(null)
const searchQuery = ref('')
const filterByType = ref<string[]>(['Class', 'Function', 'Method']) // All types enabled by default (case-sensitive)
// const showLabels = ref<'all' | 'focus' | 'none'>('all')
const currentLayout = ref<'dagre' | 'radial' | 'concentric' | 'force'>('dagre') // Default to dagre for code

// Calculate detailed stats for selected node
const getNodeStats = (nodeId: string) => {
  const node = props.nodes.find(n => n.id === nodeId)
  if (!node) return null

  const outgoingEdges = props.edges.filter(e => e.source === nodeId)
  const incomingEdges = props.edges.filter(e => e.target === nodeId)
  const complexity = outgoingEdges.length + incomingEdges.length

  return {
    node,
    complexity,
    outgoingCount: outgoingEdges.length,
    incomingCount: incomingEdges.length,
    outgoingNodes: outgoingEdges.map(e => props.nodes.find(n => n.id === e.target)).filter(Boolean),
    incomingNodes: incomingEdges.map(e => props.nodes.find(n => n.id === e.source)).filter(Boolean)
  }
}

// Computed stats for selected node (used in stats panel)
const selectedNodeStats = computed(() => {
  if (!selectedNode.value) return null
  return getNodeStats(selectedNode.value.id)
})

// Calculate complexity (number of connections) for each node
const calculateComplexity = (nodeId: string): number => {
  return props.edges.filter(
    e => e.source === nodeId || e.target === nodeId
  ).length
}

// Calculate depth from focus node using BFS
const calculateDepths = (focusId: string): Map<string, number> => {
  const depths = new Map<string, number>()
  depths.set(focusId, 0)

  const queue: string[] = [focusId]
  const visited = new Set<string>([focusId])

  while (queue.length > 0) {
    const current = queue.shift()!
    const currentDepth = depths.get(current)!

    // Find neighbors (both outbound and inbound)
    for (const edge of props.edges) {
      let neighbor: string | null = null

      if (edge.source === current && !visited.has(edge.target)) {
        neighbor = edge.target
      } else if (edge.target === current && !visited.has(edge.source)) {
        neighbor = edge.source
      }

      if (neighbor) {
        depths.set(neighbor, currentDepth + 1)
        visited.add(neighbor)
        queue.push(neighbor)
      }
    }
  }

  return depths
}

// Get node color by type
const getNodeColor = (type: string): string => {
  const baseColors: Record<string, string> = {
    Class: '#3b82f6',      // blue
    Function: '#10b981',   // green
    Method: '#8b5cf6',     // purple
    default: '#64748b'     // gray
  }

  return baseColors[type || 'default'] || baseColors.default
}

// Extract readable name from label
const extractNodeName = (node: GraphNode): string => {
  // FIXED: Use node.label directly - it already contains the function/class name
  // The previous logic was extracting filename instead, causing duplicates like "sorter" appearing 6 times
  if (!node.label) return 'Unknown'

  // Shorten very long labels
  if (node.label.length > 30) {
    return node.label.substring(0, 27) + '...'
  }

  return node.label
}

// Get layout configuration based on selected type
const getLayoutConfig = (layoutType: 'dagre' | 'radial' | 'concentric' | 'force', focus?: string) => {
  const baseConfig = {
    animated: true,
    animationDuration: 500
  }

  switch (layoutType) {
    case 'dagre':
      // Hierarchical top-down layout - BEST for code dependencies
      return {
        ...baseConfig,
        type: 'dagre',
        rankdir: 'TB', // Top to Bottom
        nodesep: 80,   // Horizontal spacing between nodes
        ranksep: 100,  // Vertical spacing between ranks
        controlPoints: true
      }

    case 'radial':
      // Radial layout with focus - Good for exploration
      return {
        ...baseConfig,
        type: 'radial',
        unitRadius: 140,
        linkDistance: 200,
        nodeSize: 30,
        focusNode: focus,
        preventOverlap: true,
        strictRadial: false,
        nodeSpacing: 50
      }

    case 'concentric':
      // Concentric circles - Shows importance/centrality
      return {
        ...baseConfig,
        type: 'concentric',
        minNodeSpacing: 80,
        preventOverlap: true,
        sweep: Math.PI * 2,
        equidistant: false,
        startAngle: Math.PI / 2,
        clockwise: false,
        sortBy: 'degree' // Most connected nodes in center
      }

    case 'force':
      // Force-directed - Natural clustering
      return {
        ...baseConfig,
        type: 'force',
        preventOverlap: true,
        nodeSize: 30,
        linkDistance: 150,
        nodeStrength: -30,
        edgeStrength: 0.6,
        collideStrength: 0.8
      }

    default:
      return { ...baseConfig, type: 'dagre' }
  }
}

// Initialize G6 graph
const initGraph = async () => {
  if (!containerRef.value || props.nodes.length === 0) return

  // Filter nodes by type
  const filteredNodes = props.nodes.filter(node => filterByType.value.includes(node.type))

  // Filter edges to only include edges between visible nodes
  const filteredNodeIds = new Set(filteredNodes.map(n => n.id))
  const filteredEdges = props.edges.filter(edge =>
    filteredNodeIds.has(edge.source) && filteredNodeIds.has(edge.target)
  )

  if (filteredNodes.length === 0) return

  // Set initial focus to first node with most connections (from filtered nodes)
  const complexities = filteredNodes.map(n => ({
    id: n.id,
    complexity: filteredEdges.filter(e => e.source === n.id || e.target === n.id).length
  }))
  const mostComplex = complexities.sort((a, b) => b.complexity - a.complexity)[0]
  focusNodeId.value = mostComplex?.id || filteredNodes[0]?.id || 'root'

  // Calculate depths for opacity gradient
  const depths = calculateDepths(focusNodeId.value)

  // Transform data to G6 v5 format with depth-based styling
  const g6Data = {
    nodes: filteredNodes.map(node => {
      const complexity = calculateComplexity(node.id)
      const depth = depths.get(node.id) ?? 99
      const isRoot = node.id === focusNodeId.value

      // Opacity gradient: 1.0 at center, fading to 0.4 at depth 5+
      const opacity = isRoot ? 1.0 : Math.max(0.4, 1.0 - (depth * 0.12))

      // Size based on complexity, reduced for distant nodes
      const baseSize = Math.max(16, 18 + complexity * 2.5)
      const size = isRoot ? 35 : (depth > 3 ? baseSize * 0.85 : baseSize)

      return {
        id: node.id,
        data: {
          label: extractNodeName(node),
          nodeType: node.type,
          file_path: node.file_path,
          start_line: node.start_line,
          end_line: node.end_line,
          complexity,
          depth,
          originalLabel: node.label
        },
        style: {
          fill: getNodeColor(node.type),
          fillOpacity: opacity,
          stroke: isRoot ? '#fbbf24' : '#ffffff',
          strokeOpacity: opacity,
          lineWidth: isRoot ? 4 : 2,
          size,
        }
      }
    }),
    edges: filteredEdges.map(edge => {
      // Calculate edge opacity based on connected nodes' depths
      const sourceDepth = depths.get(edge.source) ?? 99
      const targetDepth = depths.get(edge.target) ?? 99
      const avgDepth = (sourceDepth + targetDepth) / 2
      const edgeOpacity = Math.max(0.25, 1.0 - (avgDepth * 0.15))

      return {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        data: {
          edgeType: edge.type
        },
        style: {
          stroke: '#f59e0b',
          strokeOpacity: edgeOpacity,
          lineWidth: 2,
          endArrow: true
        }
      }
    })
  }

  // Create graph instance with G6 v5 API
  graph = new Graph({
    container: containerRef.value,
    width: containerRef.value.offsetWidth,
    height: 850,
    data: g6Data,
    node: {
      type: 'circle',
      style: {
        labelText: (d: any) => d.data.label,
        labelFill: '#e2e8f0',
        labelFontSize: 11,
        labelPlacement: 'bottom',
        labelMaxWidth: 120,
        labelWordWrap: true
      }
    },
    edge: {
      type: 'quadratic' // Curved edges for better visibility
    },
    layout: getLayoutConfig(currentLayout.value, focusNodeId.value),
    behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element', 'click-select'],
    plugins: [
      {
        type: 'tooltip',
        trigger: 'hover',
        enable: (e: any) => e.targetType === 'node',
        getContent: (_e: any, items: any[]) => {
          const item = items[0]
          const stats = getNodeStats(item.id)
          if (!stats) return '<div>No data</div>'

          const typeColors: Record<string, string> = {
            Class: '#3b82f6',
            Function: '#10b981',
            Method: '#8b5cf6',
            default: '#64748b'
          }
          const color = typeColors[item.data.nodeType] || typeColors.default

          return `
            <div style="padding: 12px; min-width: 220px; background: #1e293b; border: 1px solid #334155; border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.4);">
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px;">
                <div style="width: 12px; height: 12px; border-radius: 50%; background: ${color};"></div>
                <strong style="color: #e2e8f0; font-size: 14px;">${item.data.label}</strong>
              </div>

              <div style="font-size: 11px; color: #94a3b8; margin-bottom: 8px;">
                <span style="display: inline-block; padding: 2px 6px; background: ${color}33; color: ${color}; border-radius: 3px; font-weight: 500;">
                  ${item.data.nodeType}
                </span>
              </div>

              <div style="color: #cbd5e1; font-size: 12px; line-height: 1.6;">
                <div style="margin-bottom: 4px;">
                  <span style="color: #64748b;">Complexity:</span>
                  <strong style="color: #f59e0b;">${stats.complexity}</strong>
                </div>
                <div style="margin-bottom: 4px;">
                  <span style="color: #64748b;">Depth:</span>
                  <strong style="color: #06b6d4;">${item.data.depth}</strong>
                </div>
                <div style="margin-bottom: 4px;">
                  <span style="color: #64748b;">Dependencies:</span>
                  <strong style="color: #10b981;">↓${stats.incomingCount}</strong> /
                  <strong style="color: #ef4444;">↑${stats.outgoingCount}</strong>
                </div>
              </div>

              ${item.data.file_path ? `
                <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #334155;">
                  <div style="font-size: 10px; color: #64748b; font-family: monospace; word-break: break-all;">
                    ${item.data.file_path}
                  </div>
                  ${item.data.start_line ? `
                    <div style="font-size: 10px; color: #64748b; margin-top: 2px;">
                      Lines ${item.data.start_line}-${item.data.end_line || '?'}
                    </div>
                  ` : ''}
                </div>
              ` : ''}
            </div>
          `
        }
      }
    ],
    autoFit: 'view'
  })

  await graph.render()

  // Click interaction to refocus and select node
  graph.on('node:click', (event: any) => {
    const nodeId = event.itemId
    if (nodeId) {
      // Update selected node for stats panel
      selectedNode.value = props.nodes.find(n => n.id === nodeId) || null

      // Refocus if different node
      if (nodeId !== focusNodeId.value) {
        focusNodeId.value = nodeId
        refocusGraph(nodeId)
      }
    }
  })

  // Hover interactions for highlighting
  graph.on('node:pointerenter', (event: any) => {
    const nodeId = event.itemId
    if (!nodeId) return

    hoveredNodeId.value = nodeId

    // Highlight the hovered node and its connections
    const connectedNodes = new Set<string>()
    const connectedEdges = new Set<string>()

    props.edges.forEach(edge => {
      if (edge.source === nodeId || edge.target === nodeId) {
        connectedEdges.add(edge.id)
        connectedNodes.add(edge.source)
        connectedNodes.add(edge.target)
      }
    })

    // Update node styles for highlighting
    const allNodes = graph?.getNodeData() || []
    allNodes.forEach((node: any) => {
      const isConnected = connectedNodes.has(node.id)
      const isHovered = node.id === nodeId

      graph?.updateNodeData([{
        id: node.id,
        style: {
          ...node.style,
          fillOpacity: isHovered || isConnected ? node.style.fillOpacity : node.style.fillOpacity * 0.3,
          strokeOpacity: isHovered || isConnected ? 1 : node.style.strokeOpacity * 0.3
        }
      }])
    })

    // Update edge styles for highlighting
    const allEdges = graph?.getEdgeData() || []
    allEdges.forEach((edge: any) => {
      const isConnected = connectedEdges.has(edge.id)

      graph?.updateEdgeData([{
        id: edge.id,
        style: {
          ...edge.style,
          strokeOpacity: isConnected ? 0.8 : edge.style.strokeOpacity * 0.2,
          lineWidth: isConnected ? 3 : 2
        }
      }])
    })
  })

  graph.on('node:pointerleave', (_event: any) => {
    hoveredNodeId.value = null

    // Reset all node and edge styles
    const depths = calculateDepths(focusNodeId.value!)

    const allNodes = graph?.getNodeData() || []
    allNodes.forEach((node: any) => {
      const depth = depths.get(node.id) ?? 99
      const isRoot = node.id === focusNodeId.value
      const opacity = isRoot ? 1.0 : Math.max(0.4, 1.0 - (depth * 0.12))

      graph?.updateNodeData([{
        id: node.id,
        style: {
          ...node.style,
          fillOpacity: opacity,
          strokeOpacity: opacity
        }
      }])
    })

    const allEdges = graph?.getEdgeData() || []
    allEdges.forEach((edge: any) => {
      const sourceDepth = depths.get(edge.source) ?? 99
      const targetDepth = depths.get(edge.target) ?? 99
      const avgDepth = (sourceDepth + targetDepth) / 2
      const edgeOpacity = Math.max(0.25, 1.0 - (avgDepth * 0.15))

      graph?.updateEdgeData([{
        id: edge.id,
        style: {
          ...edge.style,
          strokeOpacity: edgeOpacity,
          lineWidth: 2
        }
      }])
    })
  })

  console.log('[G6] Graph initialized:', {
    nodes: g6Data.nodes.length,
    edges: g6Data.edges.length,
    focus: focusNodeId.value
  })
}

// Refocus graph with new center node
const refocusGraph = async (newFocusId: string) => {
  if (!graph) return

  // Update node styles to highlight the new focus
  const nodeData = graph.getNodeData()
  nodeData.forEach((node: any) => {
    const isRoot = node.id === newFocusId
    const complexity = calculateComplexity(node.id)

    graph?.updateNodeData([{
      id: node.id,
      style: {
        fill: getNodeColor(node.data.nodeType),
        stroke: isRoot ? '#fbbf24' : '#ffffff',
        lineWidth: isRoot ? 4 : 2,
        size: isRoot ? 35 : Math.max(16, 18 + complexity * 2.5),
      }
    }])
  })

  // Update layout with new focus
  graph.setLayout(getLayoutConfig(currentLayout.value, newFocusId))

  await graph.layout()

  console.log('[G6] Refocused on:', newFocusId)
}

// Toggle type filter
const toggleFilter = (type: string) => {
  const index = filterByType.value.indexOf(type)
  if (index === -1) {
    filterByType.value.push(type)
  } else {
    // Don't allow removing all filters
    if (filterByType.value.length > 1) {
      filterByType.value.splice(index, 1)
    }
  }

  // Refresh graph with filtered data
  if (graph) {
    graph.destroy()
  }
  initGraph()
}

// Zoom controls
const zoomIn = () => {
  if (graph) {
    const currentZoom = graph.getZoom()
    graph.zoomTo(currentZoom * 1.2, { duration: 300 })
  }
}

const zoomOut = () => {
  if (graph) {
    const currentZoom = graph.getZoom()
    graph.zoomTo(currentZoom * 0.8, { duration: 300 })
  }
}

const resetView = () => {
  if (graph) {
    graph.fitView({ duration: 500 } as any)
  }
}

// Change layout algorithm
const changeLayout = async (layoutType: 'dagre' | 'radial' | 'concentric' | 'force') => {
  if (!graph) return

  currentLayout.value = layoutType

  // Apply new layout
  graph.setLayout(getLayoutConfig(layoutType, focusNodeId.value || undefined))
  await graph.layout()

  // Fit view after layout
  setTimeout(() => {
    graph?.fitView({ duration: 500 } as any)
  }, 600)

  console.log('[G6] Layout changed to:', layoutType)
}

// Cleanup
onUnmounted(() => {
  if (graph) {
    graph.destroy()
    graph = null
  }
})

// Watch for data changes
watch(() => [props.nodes, props.edges], async () => {
  // Properly destroy existing graph before creating new one
  if (graph) {
    try {
      graph.destroy()
      graph = null

      // Wait a tick for DOM cleanup
      await nextTick()

      // Clear the container
      if (containerRef.value) {
        containerRef.value.innerHTML = ''
      }
    } catch (e) {
      console.error('[G6] Error destroying graph:', e)
    }
  }

  // Small delay to ensure cleanup is complete
  await new Promise(resolve => setTimeout(resolve, 50))

  // Initialize new graph
  initGraph()
}, { deep: true })

// Initialize on mount
onMounted(() => {
  initGraph()
})
</script>

<template>
  <div class="g6-graph-wrapper">
    <!-- Ultra-Compact Controls Bar -->
    <div class="mb-2 bg-slate-800/30 rounded px-3 py-1.5 flex items-center gap-3 border border-slate-700/50">
      <!-- Search (compact) -->
      <div class="flex-1 max-w-xs">
        <div class="relative">
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search..."
            class="w-full px-2 py-1 pl-7 text-xs bg-slate-700 border-0 rounded text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
          />
          <svg class="absolute left-2 top-1.5 w-3 h-3 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
      </div>

      <!-- Type Filters (ultra-compact) -->
      <div class="flex items-center gap-1">
        <button
          @click="toggleFilter('Class')"
          class="px-1.5 py-0.5 text-[10px] rounded transition-colors font-medium"
          :class="filterByType.includes('Class') ? 'bg-blue-500 text-white' : 'bg-slate-700 text-gray-400'"
          title="Toggle Classes"
        >
          C
        </button>
        <button
          @click="toggleFilter('Function')"
          class="px-1.5 py-0.5 text-[10px] rounded transition-colors font-medium"
          :class="filterByType.includes('Function') ? 'bg-green-500 text-white' : 'bg-slate-700 text-gray-400'"
          title="Toggle Functions"
        >
          F
        </button>
        <button
          @click="toggleFilter('Method')"
          class="px-1.5 py-0.5 text-[10px] rounded transition-colors font-medium"
          :class="filterByType.includes('Method') ? 'bg-purple-500 text-white' : 'bg-slate-700 text-gray-400'"
          title="Toggle Methods"
        >
          M
        </button>
      </div>

      <div class="h-4 w-px bg-slate-600"></div>

      <!-- Layout Switcher (NEW) -->
      <div class="flex items-center gap-1">
        <span class="text-[10px] text-gray-500 mr-1">Layout:</span>
        <button
          @click="changeLayout('dagre')"
          class="px-2 py-0.5 text-[10px] rounded transition-colors font-medium"
          :class="currentLayout === 'dagre' ? 'bg-cyan-500 text-white' : 'bg-slate-700 text-gray-400 hover:bg-slate-600'"
          title="Hierarchical tree layout (best for code)"
        >
          Tree
        </button>
        <button
          @click="changeLayout('radial')"
          class="px-2 py-0.5 text-[10px] rounded transition-colors font-medium"
          :class="currentLayout === 'radial' ? 'bg-cyan-500 text-white' : 'bg-slate-700 text-gray-400 hover:bg-slate-600'"
          title="Radial layout with focus"
        >
          Radial
        </button>
        <button
          @click="changeLayout('concentric')"
          class="px-2 py-0.5 text-[10px] rounded transition-colors font-medium"
          :class="currentLayout === 'concentric' ? 'bg-cyan-500 text-white' : 'bg-slate-700 text-gray-400 hover:bg-slate-600'"
          title="Concentric circles (shows importance)"
        >
          Circle
        </button>
        <button
          @click="changeLayout('force')"
          class="px-2 py-0.5 text-[10px] rounded transition-colors font-medium"
          :class="currentLayout === 'force' ? 'bg-cyan-500 text-white' : 'bg-slate-700 text-gray-400 hover:bg-slate-600'"
          title="Force-directed (natural clustering)"
        >
          Force
        </button>
      </div>

      <!-- Focus indicator (if active) -->
      <div v-if="focusNodeId" class="text-[10px] text-gray-500 px-2 py-0.5 bg-slate-700 rounded">
        <span class="text-amber-400 font-mono">{{ focusNodeId.slice(0, 6) }}</span>
      </div>

      <div class="flex-1"></div>

      <!-- Zoom Controls (ultra-compact) -->
      <div class="flex items-center gap-0.5">
        <button
          @click="zoomIn"
          class="p-1 bg-slate-700 hover:bg-slate-600 text-gray-300 rounded transition-colors"
          title="Zoom In"
        >
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v6m3-3H7" />
          </svg>
        </button>
        <button
          @click="zoomOut"
          class="p-1 bg-slate-700 hover:bg-slate-600 text-gray-300 rounded transition-colors"
          title="Zoom Out"
        >
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM7 10h6" />
          </svg>
        </button>
        <button
          @click="resetView"
          class="p-1 bg-slate-700 hover:bg-slate-600 text-gray-300 rounded transition-colors"
          title="Reset View"
        >
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Main Content: Graph + Stats Panel -->
    <div class="flex gap-4">
      <!-- Graph Container -->
      <div class="flex-1 relative">
        <!-- Depth Rings Background -->
        <svg class="depth-rings-overlay absolute inset-0 pointer-events-none" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet">
          <defs>
            <radialGradient id="depthGradient" cx="50%" cy="50%">
              <stop offset="0%" style="stop-color:#fbbf24;stop-opacity:0.08" />
              <stop offset="20%" style="stop-color:#06b6d4;stop-opacity:0.05" />
              <stop offset="40%" style="stop-color:#8b5cf6;stop-opacity:0.03" />
              <stop offset="60%" style="stop-color:#3b82f6;stop-opacity:0.02" />
              <stop offset="80%" style="stop-color:#64748b;stop-opacity:0.01" />
              <stop offset="100%" style="stop-color:#1e293b;stop-opacity:0" />
            </radialGradient>
          </defs>
          <!-- Concentric circles representing depth levels -->
          <circle cx="50" cy="50" r="8" fill="none" stroke="#fbbf24" stroke-width="0.15" stroke-opacity="0.15" />
          <circle cx="50" cy="50" r="16" fill="none" stroke="#06b6d4" stroke-width="0.12" stroke-opacity="0.12" />
          <circle cx="50" cy="50" r="24" fill="none" stroke="#8b5cf6" stroke-width="0.1" stroke-opacity="0.1" />
          <circle cx="50" cy="50" r="32" fill="none" stroke="#3b82f6" stroke-width="0.08" stroke-opacity="0.08" />
          <circle cx="50" cy="50" r="40" fill="none" stroke="#64748b" stroke-width="0.06" stroke-opacity="0.06" />
          <circle cx="50" cy="50" r="48" fill="none" stroke="#475569" stroke-width="0.04" stroke-opacity="0.04" />

          <!-- Radial gradient background -->
          <circle cx="50" cy="50" r="50" fill="url(#depthGradient)" />

          <!-- Depth level labels -->
          <text x="50" y="8" font-size="1.5" fill="#fbbf24" fill-opacity="0.3" text-anchor="middle" font-family="monospace">D0</text>
          <text x="50" y="16" font-size="1.3" fill="#06b6d4" fill-opacity="0.25" text-anchor="middle" font-family="monospace">D1</text>
          <text x="50" y="24" font-size="1.2" fill="#8b5cf6" fill-opacity="0.2" text-anchor="middle" font-family="monospace">D2</text>
          <text x="50" y="32" font-size="1.1" fill="#3b82f6" fill-opacity="0.15" text-anchor="middle" font-family="monospace">D3</text>
        </svg>

        <div
          ref="containerRef"
          class="g6-container border border-slate-700 rounded relative z-10"
          :class="{ 'opacity-50': loading }"
          style="background: linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.95));"
        ></div>

        <!-- Legend -->
        <div class="mt-4 space-y-2 text-xs text-gray-400">
          <div class="flex items-center gap-4">
            <div class="flex items-center gap-2">
              <div class="w-6 h-6 rounded-full bg-blue-500 border-2 border-white"></div>
              <span>Classes</span>
            </div>
            <div class="flex items-center gap-2">
              <div class="w-6 h-6 rounded-full bg-green-500 border-2 border-white"></div>
              <span>Functions</span>
            </div>
            <div class="flex items-center gap-2">
              <div class="w-6 h-6 rounded-full bg-purple-500 border-2 border-white"></div>
              <span>Methods</span>
            </div>
          </div>
          <div class="text-gray-500">
            <strong>Size</strong> = Complexity. <strong>Opacity</strong> = Depth. <strong>Gold ring</strong> = Focus. <strong>Curved edges</strong> = Dependencies.
          </div>
        </div>
      </div>

      <!-- Stats Panel -->
      <div v-if="selectedNodeStats" class="w-80 flex-shrink-0">
        <div class="bg-slate-800 border border-slate-700 rounded-lg p-4 sticky top-4">
          <!-- Header with close button -->
          <div class="flex items-start justify-between mb-4">
            <div class="flex items-center gap-3">
              <div
                class="w-10 h-10 rounded-full flex items-center justify-center text-white font-bold"
                :class="{
                  'bg-blue-500': selectedNode?.type === 'Class',
                  'bg-green-500': selectedNode?.type === 'Function',
                  'bg-purple-500': selectedNode?.type === 'Method',
                  'bg-gray-500': !['Class', 'Function', 'Method'].includes(selectedNode?.type || '')
                }"
              >
                {{ selectedNode?.type?.charAt(0).toUpperCase() }}
              </div>
              <div class="flex-1">
                <h4 class="text-sm font-semibold text-gray-200">{{ extractNodeName(selectedNode!) }}</h4>
                <span
                  class="inline-block mt-1 px-2 py-0.5 text-xs rounded"
                  :class="{
                    'bg-blue-500/20 text-blue-400': selectedNode?.type === 'Class',
                    'bg-green-500/20 text-green-400': selectedNode?.type === 'Function',
                    'bg-purple-500/20 text-purple-400': selectedNode?.type === 'Method',
                    'bg-gray-500/20 text-gray-400': !['Class', 'Function', 'Method'].includes(selectedNode?.type || '')
                  }"
                >
                  {{ selectedNode?.type }}
                </span>
              </div>
            </div>
            <button
              @click="selectedNode = null"
              class="text-gray-500 hover:text-gray-300 transition-colors"
              title="Close"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <!-- Metrics Grid -->
          <div class="grid grid-cols-2 gap-3 mb-4">
            <div class="bg-slate-900 rounded p-3">
              <div class="text-xs text-gray-500 mb-1">Complexity</div>
              <div class="text-xl font-bold text-amber-400">{{ selectedNodeStats.complexity }}</div>
            </div>
            <div class="bg-slate-900 rounded p-3">
              <div class="text-xs text-gray-500 mb-1">Depth</div>
              <div class="text-xl font-bold text-cyan-400">
                {{ calculateDepths(focusNodeId!).get(selectedNode!.id) ?? '?' }}
              </div>
            </div>
          </div>

          <!-- Dependencies -->
          <div class="space-y-3">
            <div>
              <div class="flex items-center gap-2 mb-2">
                <svg class="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                </svg>
                <span class="text-xs font-semibold text-gray-300">Incoming ({{ selectedNodeStats.incomingCount }})</span>
              </div>
              <div v-if="selectedNodeStats.incomingCount > 0" class="space-y-1 max-h-32 overflow-y-auto">
                <div
                  v-for="node in selectedNodeStats.incomingNodes.slice(0, 5)"
                  :key="node?.id"
                  class="text-xs text-gray-400 pl-6 py-1 hover:text-gray-200 transition-colors font-mono truncate"
                >
                  {{ node ? extractNodeName(node) : 'Unknown' }}
                </div>
                <div v-if="selectedNodeStats.incomingCount > 5" class="text-xs text-gray-500 pl-6">
                  +{{ selectedNodeStats.incomingCount - 5 }} more...
                </div>
              </div>
              <div v-else class="text-xs text-gray-600 pl-6">No incoming dependencies</div>
            </div>

            <div>
              <div class="flex items-center gap-2 mb-2">
                <svg class="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 10l7-7m0 0l7 7m-7-7v18" />
                </svg>
                <span class="text-xs font-semibold text-gray-300">Outgoing ({{ selectedNodeStats.outgoingCount }})</span>
              </div>
              <div v-if="selectedNodeStats.outgoingCount > 0" class="space-y-1 max-h-32 overflow-y-auto">
                <div
                  v-for="node in selectedNodeStats.outgoingNodes.slice(0, 5)"
                  :key="node?.id"
                  class="text-xs text-gray-400 pl-6 py-1 hover:text-gray-200 transition-colors font-mono truncate"
                >
                  {{ node ? extractNodeName(node) : 'Unknown' }}
                </div>
                <div v-if="selectedNodeStats.outgoingCount > 5" class="text-xs text-gray-500 pl-6">
                  +{{ selectedNodeStats.outgoingCount - 5 }} more...
                </div>
              </div>
              <div v-else class="text-xs text-gray-600 pl-6">No outgoing dependencies</div>
            </div>
          </div>

          <!-- File Info -->
          <div v-if="selectedNode?.file_path" class="mt-4 pt-4 border-t border-slate-700">
            <div class="text-xs text-gray-500 mb-1">File Location</div>
            <div class="text-xs text-gray-300 font-mono break-all">
              {{ selectedNode.file_path }}
            </div>
            <div v-if="selectedNode.start_line" class="text-xs text-gray-500 mt-1">
              Lines {{ selectedNode.start_line }}-{{ selectedNode.end_line || '?' }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.g6-graph-wrapper {
  width: 100%;
}

.g6-container {
  width: 100%;
  height: 850px;
  position: relative;
}

.depth-rings-overlay {
  width: 100%;
  height: 850px;
  position: absolute;
  top: 0;
  left: 0;
  z-index: 0;
  opacity: 0.6;
  border-radius: 0.5rem;
}
</style>
