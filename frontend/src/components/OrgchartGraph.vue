<script setup lang="ts">
/**
 * Organizational Chart Visualization using G6 CompactBox Layout
 *
 * Displays code hierarchy from entry points (modules) down through imports
 */

import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { Graph } from '@antv/g6'
import type { GraphNode, GraphEdge } from '@/composables/useCodeGraph'
import type { ViewMode } from '@/types/orgchart-types'
import { calculateNodeStyle } from '@/utils/orgchart-visual-encoding'
import { filterNodesByScore } from '@/utils/semantic-zoom-scoring'

interface OrgchartConfig {
  depth: number
  maxChildren: number
  maxModules: number
}

interface Props {
  nodes: GraphNode[]
  edges: GraphEdge[]
  config?: OrgchartConfig
  viewMode?: ViewMode
  zoomLevel?: number        // NEW: 0-100%
  weights?: {               // NEW: Scoring weights
    complexity: number
    loc: number
    connections: number
  }
}

const props = withDefaults(defineProps<Props>(), {
  viewMode: 'hierarchy'
})

const containerRef = ref<HTMLElement | null>(null)
let graph: Graph | null = null
const previousNodeIds = ref<Set<string>>(new Set())

const getNodeColor = (type?: string): string => {
  const colors: Record<string, string> = {
    Root: '#8b5cf6',        // Purple - Virtual root
    Module: '#06b6d4',      // Cyan - Entry points
    Class: '#3b82f6',       // Blue
    Function: '#10b981',    // Green
    Method: '#8b5cf6',      // Purple
    Interface: '#f59e0b',   // Amber
    Config: '#ec4899',      // Pink
    default: '#64748b'      // Gray
  }
  return colors[type ?? 'default'] ?? colors.default
}

const getModuleLabel = (node: GraphNode): string => {
  const baseLabel = node.label || 'Unknown'
  if (node.type !== 'Module') return baseLabel
  if (!node.file_path) return baseLabel

  const parts = node.file_path.split('/')
  const srcIndex = parts.lastIndexOf('src')

  if (srcIndex >= 0 && srcIndex < parts.length - 2) {
    const subFolder = parts[srcIndex + 1]
    return `${baseLabel} [${subFolder}]`
  }

  return baseLabel
}

const initGraph = async () => {
  if (!containerRef.value || props.nodes.length === 0) {
    console.warn('[Orgchart] No container or nodes')
    return
  }

  // Destroy existing graph to prevent duplicates
  if (graph) {
    console.log('[Orgchart] Destroying existing graph')
    graph.destroy()
    graph = null
    // Clear container to remove any leftover DOM elements
    if (containerRef.value) {
      containerRef.value.innerHTML = ''
    }
  }

  console.log('[Orgchart] Initializing with:', {
    nodes: props.nodes.length,
    edges: props.edges.length
  })

  // Debug: Log edge types
  const edgeTypes = new Set(props.edges.map(e => e.type))
  console.log('[Orgchart] Available edge types:', Array.from(edgeTypes))
  console.log('[Orgchart] Sample edges:', props.edges.slice(0, 3))

  // Filter to only show import relationships for hierarchy
  const importEdges = props.edges.filter(e => e.type === 'imports')
  console.log('[Orgchart] Import edges:', importEdges.length)

  // Debug: Log node types
  const nodeTypes = new Set(props.nodes.map(n => n.type))
  console.log('[Orgchart] Available node types:', Array.from(nodeTypes))
  console.log('[Orgchart] Sample nodes:', props.nodes.slice(0, 3))

  // Apply semantic zoom filtering
  const currentZoom = props.zoomLevel ?? 100  // Default to 100% (show all)
  const currentWeights = props.weights ?? { complexity: 0.4, loc: 0.3, connections: 0.3 }
  const currentViewMode = props.viewMode || 'hierarchy'

  console.log('[Orgchart] Applying semantic zoom:', {
    zoomLevel: currentZoom,
    weights: currentWeights,
    totalNodes: props.nodes.length
  })

  const filteredNodes = currentZoom === 100
    ? props.nodes
    : filterNodesByScore(props.nodes, props.edges, currentZoom, currentViewMode, currentWeights)

  console.log('[Orgchart] Filtered nodes:', {
    original: props.nodes.length,
    filtered: filteredNodes.length,
    percentage: (filteredNodes.length / props.nodes.length * 100).toFixed(1) + '%'
  })

  // Find entry points (modules)
  const entryPointIds = new Set(
    filteredNodes.filter(n => n.type === 'Module').map(n => n.id)
  )
  console.log('[Orgchart] Entry points (Modules):', entryPointIds.size)

  // Build tree data structure from entry points
  const buildTree = () => {
    // Start with entry points
    const roots = filteredNodes.filter(n => entryPointIds.has(n.id))

    if (roots.length === 0) {
      console.log('[Orgchart] No modules found, finding most connected nodes...')

      // If no modules, use most connected nodes as roots
      const connectionCounts = new Map<string, number>()
      importEdges.forEach(e => {
        connectionCounts.set(e.source, (connectionCounts.get(e.source) || 0) + 1)
      })

      if (connectionCounts.size === 0) {
        console.log('[Orgchart] No import connections, using all edge sources')
        // Try with all edge types if no imports
        props.edges.forEach(e => {
          connectionCounts.set(e.source, (connectionCounts.get(e.source) || 0) + 1)
        })
      }

      const sorted = Array.from(connectionCounts.entries()).sort((a, b) => b[1] - a[1])
      console.log('[Orgchart] Top connected nodes:', sorted.slice(0, 5))

      const topRootId = sorted[0]?.[0]
      if (topRootId) {
        const topRoot = filteredNodes.find(n => n.id === topRootId)
        if (topRoot) {
          console.log('[Orgchart] Using top connected node as root:', topRoot.label)
          return [topRoot]
        }
      }

      console.log('[Orgchart] Falling back to first node')
      return filteredNodes.slice(0, 1) // Fallback to first node
    }

    console.log('[Orgchart] Found module roots:', roots.map(r => r.label))
    return roots
  }

  const roots = buildTree()

  // Transform to G6 tree format
  const nodeMap = new Map(filteredNodes.map(n => [n.id, n]))
  const filteredNodeIds = new Set(filteredNodes.map(n => n.id))
  const childrenMap = new Map<string, string[]>()

  // Build parent-child relationships from edges, but ONLY between filtered nodes
  // This ensures we don't try to render nodes that were filtered out
  props.edges.forEach(edge => {
    // Only include edge if BOTH source and target are in filtered nodes
    if (filteredNodeIds.has(edge.source) && filteredNodeIds.has(edge.target)) {
      if (!childrenMap.has(edge.source)) {
        childrenMap.set(edge.source, [])
      }
      childrenMap.get(edge.source)!.push(edge.target)
    }
  })

  console.log('[Orgchart] ChildrenMap edges (filtered):', Array.from(childrenMap.entries()).reduce((sum, [_, children]) => sum + children.length, 0))

  // Calculate connection metrics from all edges
  const edgeCounts = new Map<string, { incoming: number; outgoing: number }>()
  props.edges.forEach(edge => {
    // Count outgoing edges for source
    if (!edgeCounts.has(edge.source)) {
      edgeCounts.set(edge.source, { incoming: 0, outgoing: 0 })
    }
    edgeCounts.get(edge.source)!.outgoing++

    // Count incoming edges for target
    if (!edgeCounts.has(edge.target)) {
      edgeCounts.set(edge.target, { incoming: 0, outgoing: 0 })
    }
    edgeCounts.get(edge.target)!.incoming++
  })

  // Removed config-based limits - semantic zoom now controls visibility
  const maxDepth = 50 // Allow deep trees (semantic zoom filters at leaves)
  const maxChildrenPerNode = 1000 // No arbitrary limit (semantic zoom filters at leaves)
  const maxModulesToShow = 100 // Show all entry points
  const visited = new Set<string>()

  const buildNode = (nodeId: string, depth: number): any => {
    if (depth > maxDepth || visited.has(nodeId)) return null
    visited.add(nodeId)

    const node = nodeMap.get(nodeId)
    if (!node) return null

    const children = childrenMap.get(nodeId) || []
    const childNodes = children
      .map(childId => buildNode(childId, depth + 1))
      .filter(Boolean)
      .slice(0, maxChildrenPerNode)

    // Calculate descendants count recursively
    const descendantsCount = childNodes.reduce((sum, child) =>
      sum + 1 + (child.data.descendants_count || 0), 0
    )

    // Get edge counts for this node
    const counts = edgeCounts.get(nodeId) || { incoming: 0, outgoing: 0 }

    return {
      id: node.id,
      data: {
        label: getModuleLabel(node),
        nodeType: node.type,
        file_path: node.file_path,
        depth,
        // Complexity metrics from backend
        cyclomatic_complexity: node.cyclomatic_complexity,
        lines_of_code: node.lines_of_code,
        // Connection metrics calculated from edges
        incoming_edges: counts.incoming,
        outgoing_edges: counts.outgoing,
        total_edges: counts.incoming + counts.outgoing,
        // Hierarchy metrics calculated recursively
        descendants_count: descendantsCount
      },
      children: childNodes.length > 0 ? childNodes : undefined
    }
  }

  // Create virtual root to show all modules
  const rootChildren = roots.slice(0, maxModulesToShow).map(root => buildNode(root.id, 1)).filter(Boolean)

  // Calculate metrics for virtual root
  const rootDescendants = rootChildren.reduce((sum, child) =>
    sum + 1 + (child.data.descendants_count || 0), 0
  )
  const rootCounts = edgeCounts.get('__root__') || { incoming: 0, outgoing: 0 }

  const virtualRoot = {
    id: '__root__',
    data: {
      label: `${roots[0]?.label || 'Package'} Package`,
      nodeType: 'Root',
      file_path: undefined,
      depth: 0,
      // Virtual root doesn't have complexity metrics
      cyclomatic_complexity: undefined,
      lines_of_code: undefined,
      // Connection metrics (usually 0 for virtual root)
      incoming_edges: rootCounts.incoming,
      outgoing_edges: rootCounts.outgoing,
      total_edges: rootCounts.incoming + rootCounts.outgoing,
      // Hierarchy metric aggregated from children
      descendants_count: rootDescendants
    },
    children: rootChildren
  }

  const treeData = virtualRoot

  console.log('[Orgchart] Tree data:', {
    hasData: !!treeData,
    rootLabel: treeData?.data?.label,
    childrenCount: treeData?.children?.length || 0,
    nodesInTree: visited.size,
    filteredNodesTotal: filteredNodes.length,
    coverage: `${(visited.size / filteredNodes.length * 100).toFixed(1)}%`
  })

  if (visited.size < filteredNodes.length) {
    const unvisitedNodes = filteredNodes.filter(n => !visited.has(n.id))
    console.warn('[Orgchart] Unvisited nodes (not connected to tree):', {
      count: unvisitedNodes.length,
      types: unvisitedNodes.map(n => n.type).reduce((acc, type) => {
        acc[type] = (acc[type] || 0) + 1
        return acc
      }, {} as Record<string, number>),
      sample: unvisitedNodes.slice(0, 5).map(n => ({ id: n.id, label: n.label, type: n.type }))
    })
  }

  // Debug: Log sample node metrics
  if (treeData?.children?.[0]) {
    const sampleNode = treeData.children[0]
    console.log('[Orgchart] Sample node metrics:', {
      id: sampleNode.id,
      label: sampleNode.data.label,
      depth: sampleNode.data.depth,
      complexity: sampleNode.data.cyclomatic_complexity,
      loc: sampleNode.data.lines_of_code,
      incoming: sampleNode.data.incoming_edges,
      outgoing: sampleNode.data.outgoing_edges,
      total_edges: sampleNode.data.total_edges,
      descendants: sampleNode.data.descendants_count
    })
  }

  if (!treeData) {
    console.warn('[Orgchart] No tree data generated')
    return
  }

  console.log('[Orgchart] Creating G6 graph...')

  // Flatten tree to graph format
  const flattenTree = (node: any, nodes: any[] = [], edges: any[] = []) => {
    nodes.push({
      id: node.id,
      data: node.data
    })

    if (node.children) {
      node.children.forEach((child: any) => {
        edges.push({
          id: `${node.id}-${child.id}`,
          source: node.id,
          target: child.id
        })
        flattenTree(child, nodes, edges)
      })
    }

    return { nodes, edges }
  }

  const flatData = flattenTree(treeData)

  console.log('[Orgchart] Flattened data:', {
    nodes: flatData.nodes.length,
    edges: flatData.edges.length
  })

  // Create graph with hierarchical layout
  graph = new Graph({
    container: containerRef.value,
    width: containerRef.value.offsetWidth,
    height: 1200,  // Increased from 800 for larger tree
    data: flatData,
    animation: {
      duration: 500,
      easing: 'ease-in-out'
    },
    node: {
      type: 'rect',
      style: {
        size: (d: any) => {
          const currentViewMode = props.viewMode || 'hierarchy'
          // Get the original node from nodeMap to access full GraphNode data
          const originalNode = nodeMap.get(d.id)
          if (!originalNode) return [140, 40]

          const style = calculateNodeStyle({ data: originalNode }, currentViewMode)
          return style.size
        },
        radius: 4,
        labelText: (d: any) => {
          const label = d.data.label || ''
          return label.length > 18 ? label.substring(0, 15) + '...' : label
        },
        labelFill: '#e2e8f0',
        labelFontSize: 11,
        labelFontWeight: 500,
        labelPlacement: 'center',
        fill: (d: any) => {
          const currentViewMode = props.viewMode || 'hierarchy'
          // Get the original node from nodeMap to access full GraphNode data
          const originalNode = nodeMap.get(d.id)
          if (!originalNode) return getNodeColor(d.data.nodeType)

          const style = calculateNodeStyle({ data: originalNode }, currentViewMode)
          return style.fill
        },
        stroke: '#ffffff',
        lineWidth: 2
      }
    },
    edge: {
      type: 'line',
      style: {
        stroke: '#64748b',
        lineWidth: 2,
        endArrow: true
      }
    },
    layout: {
      type: 'dagre',
      rankdir: 'TB',
      nodesep: 60,    // Horizontal spacing between nodes
      ranksep: 80     // Vertical spacing between levels
    },
    behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element'],
    plugins: [
      {
        type: 'tooltip',
        enable: true,
        getContent: (_evt: any, items: any[]) => {
          const item = items[0]
          if (!item) return ''

          const currentViewMode = props.viewMode || 'hierarchy'

          // Get the original node from nodeMap to access full GraphNode data
          const originalNode = nodeMap.get(item.id)

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

          // Generate metrics section based on view mode
          const getMetricsSection = (): string => {
            if (!originalNode) return ''

            switch (currentViewMode) {
              case 'complexity': {
                const complexity = originalNode.cyclomatic_complexity
                const loc = originalNode.lines_of_code
                if (complexity === undefined && loc === undefined) return ''

                return `
                  <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #334155;">
                    ${complexity !== undefined ? `
                      <div style="font-size: 10px; color: #94a3b8; margin-bottom: 4px;">
                        <span style="margin-right: 4px;">📊</span>
                        <span>Cyclomatic Complexity: <strong style="color: #e2e8f0;">${complexity}</strong></span>
                      </div>
                    ` : ''}
                    ${loc !== undefined ? `
                      <div style="font-size: 10px; color: #94a3b8;">
                        <span style="margin-right: 4px;">📏</span>
                        <span>Lines of Code: <strong style="color: #e2e8f0;">${loc}</strong></span>
                      </div>
                    ` : ''}
                  </div>
                `
              }

              case 'hubs': {
                const incoming = originalNode.incoming_edges
                const outgoing = originalNode.outgoing_edges
                const total = originalNode.total_edges
                if (incoming === undefined && outgoing === undefined && total === undefined) return ''

                return `
                  <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #334155;">
                    ${incoming !== undefined ? `
                      <div style="font-size: 10px; color: #94a3b8; margin-bottom: 4px;">
                        <span style="margin-right: 4px;">⬇️</span>
                        <span>Incoming: <strong style="color: #e2e8f0;">${incoming}</strong></span>
                      </div>
                    ` : ''}
                    ${outgoing !== undefined ? `
                      <div style="font-size: 10px; color: #94a3b8; margin-bottom: 4px;">
                        <span style="margin-right: 4px;">⬆️</span>
                        <span>Outgoing: <strong style="color: #e2e8f0;">${outgoing}</strong></span>
                      </div>
                    ` : ''}
                    ${total !== undefined ? `
                      <div style="font-size: 10px; color: #94a3b8;">
                        <span style="margin-right: 4px;">🔗</span>
                        <span>Total: <strong style="color: #e2e8f0;">${total}</strong></span>
                      </div>
                    ` : ''}
                  </div>
                `
              }

              case 'hierarchy': {
                const depth = originalNode.depth
                const descendants = originalNode.descendants_count
                if (depth === undefined && descendants === undefined) return ''

                return `
                  <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #334155;">
                    ${depth !== undefined ? `
                      <div style="font-size: 10px; color: #94a3b8; margin-bottom: 4px;">
                        <span style="margin-right: 4px;">🌳</span>
                        <span>Depth: <strong style="color: #e2e8f0;">${depth}</strong></span>
                      </div>
                    ` : ''}
                    ${descendants !== undefined ? `
                      <div style="font-size: 10px; color: #94a3b8;">
                        <span style="margin-right: 4px;">👥</span>
                        <span>Descendants: <strong style="color: #e2e8f0;">${descendants}</strong> nodes</span>
                      </div>
                    ` : ''}
                  </div>
                `
              }

              default:
                return ''
            }
          }

          return `
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
              ${getMetricsSection()}
              ${item.data.file_path ? `
                <div style="font-size: 9px; color: #64748b; font-family: monospace; word-break: break-all; margin-top: 8px; padding-top: 8px; border-top: 1px solid #334155;">
                  📁 ${item.data.file_path}
                </div>
              ` : ''}
            </div>
          `
        }
      }
    ]
  })

  try {
    await graph.render()
    console.log('[Orgchart] Graph rendered successfully')

    // Auto-fit to show entire tree
    graph.fitView()
    console.log('[Orgchart] Fitted to view')

    console.log('[Orgchart] Tree initialized with root:', roots[0]?.label || 'unknown')

    // Track initial node IDs for animation
    const currentZoom = props.zoomLevel ?? 100
    const currentWeights = props.weights ?? { complexity: 0.4, loc: 0.3, connections: 0.3 }
    const currentViewMode = props.viewMode || 'hierarchy'

    const initialFilteredNodes = currentZoom === 100
      ? props.nodes
      : filterNodesByScore(props.nodes, props.edges, currentZoom, currentViewMode, currentWeights)

    previousNodeIds.value = new Set(initialFilteredNodes.map(n => n.id))
  } catch (error) {
    console.error('[Orgchart] Error rendering graph:', error)
  }
}

// Watch for data changes and viewMode changes
watch(() => [props.nodes, props.edges, props.viewMode, props.zoomLevel, props.weights] as const, async (newVal, oldVal) => {
  const [newNodes, newEdges, newViewMode, newZoomLevel, newWeights] = newVal
  const [oldNodes, oldEdges, oldViewMode, oldZoomLevel, oldWeights] = oldVal || [null, null, null, null, null]

  // Detect if only zoom level changed
  const onlyZoomChanged = newZoomLevel !== oldZoomLevel &&
    newNodes === oldNodes &&
    newEdges === oldEdges &&
    newViewMode === oldViewMode &&
    newWeights === oldWeights

  // Detect if only viewMode changed (for existing animation)
  const onlyViewModeChanged = newViewMode !== oldViewMode &&
    newNodes === oldNodes &&
    newEdges === oldEdges &&
    newZoomLevel === oldZoomLevel &&
    newWeights === oldWeights

  if ((onlyViewModeChanged || onlyZoomChanged) && graph) {
    try {
      console.log('[Orgchart] ViewMode or Zoom changed, updating styles with animation...')

      const nodeMap = new Map(props.nodes.map(n => [n.id, n]))
      const graphNodes = graph.getNodeData()

      // Calculate which nodes to show/hide based on new zoom
      const currentZoom = props.zoomLevel ?? 100
      const currentWeights = props.weights ?? { complexity: 0.4, loc: 0.3, connections: 0.3 }
      const currentViewMode = props.viewMode || 'hierarchy'

      const filteredNodes = currentZoom === 100
        ? props.nodes
        : filterNodesByScore(props.nodes, props.edges, currentZoom, currentViewMode, currentWeights)

      const newNodeIds = new Set(filteredNodes.map(n => n.id))

      // Nodes to fade out (were visible, now hidden)
      const nodesToHide = Array.from(previousNodeIds.value).filter(id => !newNodeIds.has(id))

      // Nodes to fade in (were hidden, now visible)
      const nodesToShow = Array.from(newNodeIds).filter(id => !previousNodeIds.value.has(id))

      console.log('[Orgchart] Animation:', {
        toHide: nodesToHide.length,
        toShow: nodesToShow.length,
        total: newNodeIds.size
      })

      // Phase 1: Fade out nodes that should be hidden (150ms)
      if (nodesToHide.length > 0) {
        nodesToHide.forEach(nodeId => {
          graph!.updateNodeData([{
            id: nodeId,
            style: {
              opacity: 0,
              size: [100, 30]  // Shrink slightly
            }
          }])
        })
        await graph.draw()
        await new Promise(resolve => setTimeout(resolve, 150))
      }

      // Phase 2: Update visible nodes styles (for viewMode changes)
      const nodesToUpdate = graphNodes
        .filter((gn: any) => newNodeIds.has(gn.id))
        .map((graphNode: any) => {
          if (graphNode.id === '__root__') {
            return {
              id: graphNode.id,
              style: {
                size: [140, 40],
                fill: '#8b5cf6',
                opacity: 1
              }
            }
          }

          const originalNode = nodeMap.get(graphNode.id)
          if (!originalNode) return null

          const newStyle = calculateNodeStyle({ data: originalNode }, currentViewMode)
          return {
            id: graphNode.id,
            style: {
              size: newStyle.size,
              fill: newStyle.fill,
              opacity: 1
            }
          }
        })
        .filter(Boolean)

      if (nodesToUpdate.length > 0) {
        graph!.updateNodeData(nodesToUpdate as any[])
        await graph.draw()
      }

      // Phase 3: Fade in new nodes (150ms)
      if (nodesToShow.length > 0) {
        await new Promise(resolve => setTimeout(resolve, 150))
        // New nodes should already be visible from Phase 2, just ensure opacity
        const nodesToFadeIn = nodesToShow
          .map(nodeId => {
            const originalNode = nodeMap.get(nodeId)
            if (!originalNode) return null
            const style = calculateNodeStyle({ data: originalNode }, currentViewMode)
            return {
              id: nodeId,
              style: {
                ...style,
                opacity: 1
              }
            }
          })
          .filter(Boolean)

        if (nodesToFadeIn.length > 0) {
          graph!.updateNodeData(nodesToFadeIn as any[])
          await graph.draw()
        }
      }

      // Update tracking
      previousNodeIds.value = newNodeIds

      console.log('[Orgchart] Styles updated with animation')
    } catch (e) {
      console.error('[Orgchart] Error during animation:', e)
      // Fallback to full rebuild
      console.log('[Orgchart] Falling back to full rebuild')
      if (graph) {
        graph.destroy()
        graph = null
        await nextTick()
        if (containerRef.value) {
          containerRef.value.innerHTML = ''
        }
        await new Promise(resolve => setTimeout(resolve, 50))
        initGraph()
      }
    }
  } else {
    // Data changed or first render: full rebuild
    if (graph) {
      try {
        graph.destroy()
        graph = null

        await nextTick()

        if (containerRef.value) {
          containerRef.value.innerHTML = ''
        }
      } catch (e) {
        console.error('[Orgchart] Error destroying graph:', e)
      }
    }

    await new Promise(resolve => setTimeout(resolve, 50))
    initGraph()
  }
}, { deep: true })

// Initialize on mount
onMounted(() => {
  initGraph()
})

// Cleanup on unmount
onUnmounted(() => {
  if (graph) {
    graph.destroy()
    graph = null
  }
})
</script>

<template>
  <div class="orgchart-wrapper">
    <div ref="containerRef" class="orgchart-container"></div>
  </div>
</template>

<style scoped>
.orgchart-wrapper {
  width: 100%;
  background: #0f172a;
  border-radius: 0.5rem;
  overflow: hidden;
}

.orgchart-container {
  width: 100%;
  height: 1200px;  /* Increased from 800px for larger tree */
  position: relative;
}
</style>
