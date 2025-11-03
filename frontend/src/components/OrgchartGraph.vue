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
}

const props = defineProps<Props>()

const containerRef = ref<HTMLElement | null>(null)
let graph: Graph | null = null

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
  return colors[type || 'default'] || colors.default
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

  // Find entry points (modules)
  const entryPointIds = new Set(
    props.nodes.filter(n => n.type === 'Module').map(n => n.id)
  )
  console.log('[Orgchart] Entry points (Modules):', entryPointIds.size)

  // Build tree data structure from entry points
  const buildTree = () => {
    // Start with entry points
    const roots = props.nodes.filter(n => entryPointIds.has(n.id))

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
        const topRoot = props.nodes.find(n => n.id === topRootId)
        if (topRoot) {
          console.log('[Orgchart] Using top connected node as root:', topRoot.label)
          return [topRoot]
        }
      }

      console.log('[Orgchart] Falling back to first node')
      return props.nodes.slice(0, 1) // Fallback to first node
    }

    console.log('[Orgchart] Found module roots:', roots.map(r => r.label))
    return roots
  }

  const roots = buildTree()

  // Transform to G6 tree format
  const nodeMap = new Map(props.nodes.map(n => [n.id, n]))
  const childrenMap = new Map<string, string[]>()

  // Build parent-child relationships from import edges
  importEdges.forEach(edge => {
    if (!childrenMap.has(edge.source)) {
      childrenMap.set(edge.source, [])
    }
    childrenMap.get(edge.source)!.push(edge.target)
  })

  // Use config from props or defaults
  const maxDepth = props.config?.depth || 6
  const maxChildrenPerNode = props.config?.maxChildren || 25
  const maxModulesToShow = props.config?.maxModules || 5
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

    return {
      id: node.id,
      data: {
        label: getModuleLabel(node),
        nodeType: node.type,
        file_path: node.file_path,
        depth
      },
      children: childNodes.length > 0 ? childNodes : undefined
    }
  }

  // Create virtual root to show all modules
  const virtualRoot = {
    id: '__root__',
    data: {
      label: `${roots[0]?.label || 'Package'} Package`,
      nodeType: 'Root',
      file_path: undefined,
      depth: 0
    },
    children: roots.slice(0, maxModulesToShow).map(root => buildNode(root.id, 1)).filter(Boolean)
  }

  const treeData = virtualRoot

  console.log('[Orgchart] Tree data:', {
    hasData: !!treeData,
    rootLabel: treeData?.data?.label,
    childrenCount: treeData?.children?.length || 0
  })

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
              ${item.data.file_path ? `
                <div style="font-size: 9px; color: #64748b; font-family: monospace; word-break: break-all; margin-top: 8px; padding-top: 8px; border-top: 1px solid #334155;">
                  ${item.data.file_path}
                </div>
              ` : ''}
              <div style="font-size: 9px; color: #64748b; margin-top: 4px;">
                Depth: ${item.data.depth}
              </div>
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
  } catch (error) {
    console.error('[Orgchart] Error rendering graph:', error)
  }
}

// Watch for data changes and viewMode changes
watch(() => [props.nodes, props.edges, props.viewMode] as const, async (newVal, oldVal) => {
  const [newNodes, newEdges, newViewMode] = newVal
  const [oldNodes, oldEdges, oldViewMode] = oldVal

  // Check if only viewMode changed (not data)
  const onlyViewModeChanged = newViewMode !== oldViewMode &&
    newNodes === oldNodes &&
    newEdges === oldEdges

  if (onlyViewModeChanged && graph) {
    // Smooth transition: update node styles without destroying graph
    console.log('[Orgchart] ViewMode changed, updating styles with animation...')

    const nodeMap = new Map(props.nodes.map(n => [n.id, n]))
    const graphNodes = graph.getNodeData()
    const nodesToUpdate = graphNodes.map((graphNode: any) => {
      const originalNode = nodeMap.get(graphNode.id)
      if (!originalNode) return null

      const newStyle = calculateNodeStyle({ data: originalNode }, newViewMode || 'hierarchy')

      return {
        id: graphNode.id,
        style: {
          size: newStyle.size,
          fill: newStyle.fill
        }
      }
    }).filter(Boolean)

    if (nodesToUpdate.length > 0) {
      // Update all nodes at once
      nodesToUpdate.forEach((nodeUpdate: any) => {
        graph!.updateNodeData([nodeUpdate])
      })

      // Trigger animated redraw
      await graph.draw()
      console.log('[Orgchart] Styles updated with animation')
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
