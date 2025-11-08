<script setup lang="ts">
import { ref, computed, onMounted, watch, onBeforeUnmount, nextTick } from 'vue'
import { Graph } from '@antv/g6'
import type { GraphNode, GraphEdge } from '@/composables/useCodeGraph'
import { useFullscreenResize } from '@/composables/useFullscreenResize'

const props = defineProps<{
  nodes: GraphNode[]
  edges: GraphEdge[]
}>()

const containerRef = ref<HTMLDivElement>()
let graphInstance: Graph | null = null

// Setup resize handling with ResizeObserver (modern API)
const { calculateSize } = useFullscreenResize(containerRef, (width, height) => {
  if (graphInstance) {
    graphInstance.changeSize(width, height)
  }
})

// Extract folder from file path for clustering
const getFolder = (node: GraphNode): string => {
  if (!node.file_path) return 'root'
  const parts = node.file_path.split('/')
  // Get the part after 'packages' or 'src'
  const srcIndex = parts.findIndex(p => p === 'src' || p === 'packages')
  if (srcIndex >= 0 && srcIndex < parts.length - 2) {
    return parts.slice(srcIndex, srcIndex + 2).join('/')
  }
  return parts.slice(0, Math.max(2, parts.length - 1)).join('/')
}

// Cluster colors based on folder
const clusterColors = [
  '#3b82f6', // blue
  '#10b981', // green
  '#f59e0b', // amber
  '#8b5cf6', // purple
  '#ef4444', // red
  '#06b6d4', // cyan
  '#ec4899', // pink
  '#f97316', // orange
]

const preparedData = computed(() => {
  if (!props.nodes || props.nodes.length === 0) {
    return { nodes: [], edges: [], clusters: new Map<string, number>() }
  }

  // Group nodes by folder for clustering
  const folderMap = new Map<string, number>()
  const clusters = new Map<string, number>()

  props.nodes.forEach(node => {
    const folder = getFolder(node)
    if (!folderMap.has(folder)) {
      folderMap.set(folder, folderMap.size)
    }
    clusters.set(node.id, folderMap.get(folder)!)
  })

  // Prepare G6 data format
  const g6Nodes = props.nodes.map((node) => {
    const clusterId = clusters.get(node.id) || 0
    const color = clusterColors[clusterId % clusterColors.length]

    return {
      id: node.id,
      label: node.label.split('/').pop() || node.label,
      cluster: clusterId,
      style: {
        fill: color,
        stroke: '#fff',
        lineWidth: 2,
      },
      // Size based on chunk_count or importance
      size: Math.max(15, Math.min(40, (node.metadata?.chunk_count || 1) * 3)),
      data: node
    }
  })

  const g6Edges = props.edges.map(edge => ({
    source: edge.source,
    target: edge.target,
    style: {
      stroke: '#64748b',
      lineWidth: 1,
      opacity: 0.6,
      endArrow: true,
    }
  }))

  console.log('[ForceDirectedGraph] Prepared:', {
    nodes: g6Nodes.length,
    edges: g6Edges.length,
    clusters: folderMap.size
  })

  return { nodes: g6Nodes, edges: g6Edges, clusters: folderMap }
})

const initGraph = async () => {
  if (!containerRef.value || preparedData.value.nodes.length === 0) return

  // Destroy existing instance
  if (graphInstance) {
    graphInstance.destroy()
  }

  // Calculate optimal canvas size using composable
  const size = calculateSize()
  if (!size) {
    console.error('[ForceDirectedGraph] Failed to calculate canvas size')
    return
  }

  console.log('[ForceDirectedGraph] Initializing with dimensions:', size)

  graphInstance = new Graph({
    container: containerRef.value,
    width: size.width,
    height: size.height,
    data: {
      nodes: preparedData.value.nodes,
      edges: preparedData.value.edges
    },
    node: {
      type: 'circle',
      style: {
        size: (d: any) => d.size || 20,
        fill: (d: any) => d.style?.fill || '#3b82f6',
        stroke: (d: any) => d.style?.stroke || '#fff',
        lineWidth: (d: any) => d.style?.lineWidth || 2,
        labelText: (d: any) => d.label,
        labelFill: '#e2e8f0',
        labelFontSize: 10,
        labelPlacement: 'bottom',
        labelBackground: true,
        labelBackgroundFill: '#1e293b',
        labelBackgroundRadius: 2,
        labelPadding: [2, 4, 2, 4]
      }
    },
    edge: {
      type: 'line',
      style: {
        stroke: '#64748b',
        lineWidth: 1,
        opacity: 0.6,
        endArrow: true
      }
    },
    layout: {
      type: 'force-atlas2',
      kr: 50,
      kg: 8,
      ks: 0.1,
      tao: 0.8,
      mode: 'normal',
      preventOverlap: true,
      maxIteration: 1000,
      barnesHut: true,
    },
    behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element'],
    plugins: [
      {
        type: 'tooltip',
        trigger: 'hover',
        enable: (e: any) => e.targetType === 'node',
        getContent: (_e: any, items: any[]) => {
          const item = items[0]
          const node = item?.data?.data as GraphNode | undefined
          if (!node) return '<div>No data</div>'

          return `
            <div style="padding: 8px; background: #1e293b; border: 1px solid #475569; border-radius: 4px; font-size: 12px; max-width: 300px;">
              <div style="font-weight: bold; margin-bottom: 4px; color: #e2e8f0;">${node.label}</div>
              <div style="color: #94a3b8;">Imports: ${node.metadata?.imports?.length || 0}</div>
              <div style="color: #94a3b8;">Chunks: ${node.metadata?.chunk_count || 0}</div>
              <div style="color: #64748b; margin-top: 4px; font-size: 10px;">${node.file_path || ''}</div>
            </div>
          `
        }
      }
    ],
    autoFit: 'view'
  })

  await graphInstance.render()
}

// Initialize on mount - G6 autoResize handles resize events
onMounted(() => {
  initGraph()
})

// Cleanup on unmount
onBeforeUnmount(() => {
  if (graphInstance) {
    graphInstance.destroy()
  }
})

watch(() => [props.nodes, props.edges], async () => {
  await nextTick()
  initGraph()
}, { deep: true })
</script>

<template>
  <div class="force-graph-container">
    <div ref="containerRef" class="graph-canvas"></div>

    <!-- Cluster Legend -->
    <div v-if="preparedData.clusters.size > 0" class="cluster-legend">
      <div class="legend-title flex items-center gap-2">
        <span class="scada-led scada-led-cyan"></span>
        <span class="font-mono uppercase">Clusters by Folder</span>
      </div>
      <div class="legend-items">
        <div
          v-for="[folder, index] in Array.from(preparedData.clusters.entries()).slice(0, 8)"
          :key="folder"
          class="legend-item"
        >
          <div
            class="legend-dot"
            :style="{ backgroundColor: clusterColors[index % clusterColors.length] }"
          ></div>
          <span class="legend-label font-mono">{{ folder }}</span>
        </div>
        <div v-if="preparedData.clusters.size > 8" class="legend-item">
          <span class="legend-label text-gray-500 font-mono">+{{ preparedData.clusters.size - 8 }} more...</span>
        </div>
      </div>
    </div>

    <!-- Stats Overlay -->
    <div class="stats-overlay">
      <div class="stat-item">
        <span class="stat-label scada-label">Nodes:</span>
        <span class="stat-value scada-data text-cyan-400">{{ preparedData.nodes.length }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label scada-label">Edges:</span>
        <span class="stat-value scada-data text-cyan-400">{{ preparedData.edges.length }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label scada-label">Clusters:</span>
        <span class="stat-value scada-data text-cyan-400">{{ preparedData.clusters.size }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.force-graph-container {
  position: relative;
  width: 100%;
  height: 100%;
  background: #0f172a;
  border-radius: 8px;
  overflow: hidden;
}

.graph-canvas {
  width: 100%;
  height: 100%;
}

.cluster-legend {
  position: absolute;
  top: 16px;
  right: 16px;
  background: rgba(30, 41, 59, 0.95);
  border: 2px solid #475569;
  border-radius: 8px;
  padding: 12px;
  max-width: 250px;
}

.legend-title {
  font-size: 12px;
  font-weight: 600;
  color: #e2e8f0;
  margin-bottom: 8px;
}

.legend-items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
}

.legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
}

.legend-label {
  color: #cbd5e1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stats-overlay {
  position: absolute;
  bottom: 16px;
  left: 16px;
  display: flex;
  gap: 16px;
  background: rgba(30, 41, 59, 0.95);
  border: 2px solid #475569;
  border-radius: 8px;
  padding: 8px 12px;
}

.stat-item {
  display: flex;
  gap: 6px;
  font-size: 12px;
}

.stat-label {
  color: #94a3b8;
}

.stat-value {
  color: #06b6d4;
  font-weight: 600;
}
</style>
