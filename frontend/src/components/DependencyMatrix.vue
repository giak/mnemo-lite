<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import type { GraphNode, GraphEdge } from '@/composables/useCodeGraph'

const props = defineProps<{
  nodes: GraphNode[]
  edges: GraphEdge[]
}>()

const containerRef = ref<HTMLDivElement>()
const hoveredRow = ref<number | null>(null)
const hoveredCol = ref<number | null>(null)
const searchFilter = ref('')
const folderFilter = ref<string>('all')

// Extract folder from file path
const getFolder = (node: GraphNode): string => {
  if (!node.file_path) return 'root'
  const parts = node.file_path.split('/')
  const srcIndex = parts.findIndex(p => p === 'src' || p === 'packages')
  if (srcIndex >= 0 && srcIndex < parts.length - 2) {
    return parts.slice(srcIndex, srcIndex + 2).join('/')
  }
  return parts.slice(0, Math.max(2, parts.length - 1)).join('/')
}

// Get unique folders
const folders = computed(() => {
  const folderSet = new Set<string>()
  props.nodes.forEach(node => {
    folderSet.add(getFolder(node))
  })
  return Array.from(folderSet).sort()
})

// Filter nodes based on search and folder
const filteredNodes = computed(() => {
  let nodes = props.nodes

  // Filter by folder
  if (folderFilter.value !== 'all') {
    nodes = nodes.filter(node => getFolder(node) === folderFilter.value)
  }

  // Filter by search
  if (searchFilter.value.trim()) {
    const search = searchFilter.value.toLowerCase()
    nodes = nodes.filter(node =>
      node.label.toLowerCase().includes(search) ||
      (node.file_path || '').toLowerCase().includes(search)
    )
  }

  return nodes.slice(0, 100) // Limit to 100 nodes for performance
})

// Build adjacency matrix
const matrixData = computed(() => {
  const nodes = filteredNodes.value
  const nodeIndexMap = new Map<string, number>()
  nodes.forEach((node, index) => {
    nodeIndexMap.set(node.id, index)
  })

  // Initialize matrix
  const matrix: number[][] = Array(nodes.length)
    .fill(0)
    .map(() => Array(nodes.length).fill(0))

  // Fill matrix from edges
  props.edges.forEach(edge => {
    const sourceIdx = nodeIndexMap.get(edge.source)
    const targetIdx = nodeIndexMap.get(edge.target)
    if (sourceIdx !== undefined && targetIdx !== undefined) {
      matrix[sourceIdx][targetIdx] = 1
    }
  })

  // Calculate stats
  let totalDeps = 0
  let circularDeps = 0
  for (let i = 0; i < nodes.length; i++) {
    for (let j = 0; j < nodes.length; j++) {
      if (matrix[i][j] === 1) {
        totalDeps++
        // Check for circular dependency
        if (matrix[j][i] === 1) {
          circularDeps++
        }
      }
    }
  }

  return {
    matrix,
    nodes,
    totalDeps,
    circularDeps: circularDeps / 2, // Divide by 2 because we count each pair twice
  }
})

// Cell size for the matrix
const cellSize = computed(() => {
  if (!containerRef.value) return 20
  const containerWidth = containerRef.value.offsetWidth - 200 // Reserve space for labels
  const count = matrixData.value.nodes.length
  return Math.max(8, Math.min(40, containerWidth / count))
})

// Get node label (shortened)
const getNodeLabel = (node: GraphNode): string => {
  const parts = node.label.split('/')
  return parts[parts.length - 1] || node.label
}

// Get cell color
const getCellColor = (value: number, row: number, col: number): string => {
  if (value === 0) return '#1e293b'

  // Highlight diagonal (self-reference)
  if (row === col) return '#fbbf24'

  // Check if circular dependency
  const isCircular = matrixData.value.matrix[col][row] === 1
  if (isCircular) return '#ef4444'

  return '#3b82f6'
}

// Get cell opacity
const getCellOpacity = (row: number, col: number): number => {
  if (hoveredRow.value === null && hoveredCol.value === null) return 1

  if (hoveredRow.value === row || hoveredCol.value === col) {
    return 1
  }

  return 0.2
}

// Calculate coupling score (outgoing + incoming)
const getNodeCoupling = (index: number): number => {
  let score = 0
  const matrix = matrixData.value.matrix

  // Outgoing dependencies
  for (let j = 0; j < matrix.length; j++) {
    if (matrix[index][j] === 1) score++
  }

  // Incoming dependencies
  for (let i = 0; i < matrix.length; i++) {
    if (matrix[i][index] === 1) score++
  }

  return score
}

// Get coupling color
const getCouplingColor = (coupling: number): string => {
  if (coupling === 0) return '#64748b'
  if (coupling < 3) return '#10b981'
  if (coupling < 6) return '#f59e0b'
  return '#ef4444'
}

console.log('[DependencyMatrix] Data:', {
  totalNodes: props.nodes.length,
  filteredNodes: filteredNodes.value.length,
  totalDeps: matrixData.value.totalDeps,
  circularDeps: matrixData.value.circularDeps
})
</script>

<template>
  <div class="matrix-container">
    <!-- Controls -->
    <div class="controls">
      <div class="control-group">
        <label class="control-label scada-label">Recherche:</label>
        <input
          v-model="searchFilter"
          type="text"
          placeholder="Filter modules..."
          class="search-input"
        />
      </div>

      <div class="control-group">
        <label class="control-label scada-label">Dossier:</label>
        <select v-model="folderFilter" class="folder-select">
          <option value="all">Tous</option>
          <option v-for="folder in folders" :key="folder" :value="folder">
            {{ folder }}
          </option>
        </select>
      </div>
    </div>

    <!-- Stats -->
    <div class="stats-bar">
      <div class="stat-item">
        <span class="stat-label scada-label">Modules:</span>
        <span class="stat-value scada-data text-cyan-400">{{ matrixData.nodes.length }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label scada-label">Dependencies:</span>
        <span class="stat-value scada-data text-cyan-400">{{ matrixData.totalDeps }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label scada-label">Circular:</span>
        <span class="stat-value scada-data text-red-400">{{ matrixData.circularDeps }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label scada-label">Avg Coupling:</span>
        <span class="stat-value scada-data text-cyan-400">
          {{ matrixData.nodes.length > 0 ? (matrixData.totalDeps * 2 / matrixData.nodes.length).toFixed(1) : 0 }}
        </span>
      </div>
    </div>

    <!-- Legend -->
    <div class="legend">
      <div class="legend-item">
        <span class="scada-led" style="background: #3b82f6;"></span>
        <span class="font-mono uppercase">Dependency</span>
      </div>
      <div class="legend-item">
        <span class="scada-led scada-led-red"></span>
        <span class="font-mono uppercase">Circular</span>
      </div>
      <div class="legend-item">
        <span class="scada-led scada-led-yellow"></span>
        <span class="font-mono uppercase">Self-Ref</span>
      </div>
      <div class="legend-item">
        <span class="scada-led" style="background: #1e293b; border: 1px solid #475569;"></span>
        <span class="font-mono uppercase">None</span>
      </div>
    </div>

    <!-- Matrix -->
    <div ref="containerRef" class="matrix-wrapper">
      <div v-if="matrixData.nodes.length === 0" class="empty-state">
        <p>No modules match your filters</p>
        <p class="text-sm text-gray-500">Try adjusting search or folder filter</p>
      </div>

      <div v-else class="matrix-grid" :style="{ width: `${cellSize * matrixData.nodes.length + 200}px` }">
        <!-- Column labels (top) -->
        <div class="column-labels" :style="{ marginLeft: '200px', height: '150px' }">
          <div
            v-for="(node, colIdx) in matrixData.nodes"
            :key="`col-${colIdx}`"
            class="column-label"
            :class="{ highlighted: hoveredCol === colIdx }"
            :style="{
              width: `${cellSize}px`,
              left: `${colIdx * cellSize}px`
            }"
            @mouseenter="hoveredCol = colIdx"
            @mouseleave="hoveredCol = null"
          >
            <span>{{ getNodeLabel(node) }}</span>
          </div>
        </div>

        <!-- Matrix rows -->
        <div class="matrix-rows">
          <div
            v-for="(node, rowIdx) in matrixData.nodes"
            :key="`row-${rowIdx}`"
            class="matrix-row"
          >
            <!-- Row label (left) with coupling indicator -->
            <div
              class="row-label"
              :class="{ highlighted: hoveredRow === rowIdx }"
              @mouseenter="hoveredRow = rowIdx"
              @mouseleave="hoveredRow = null"
            >
              <div
                class="coupling-indicator"
                :style="{ backgroundColor: getCouplingColor(getNodeCoupling(rowIdx)) }"
                :title="`Coupling: ${getNodeCoupling(rowIdx)}`"
              ></div>
              <span class="row-label-text">{{ getNodeLabel(node) }}</span>
            </div>

            <!-- Matrix cells -->
            <div class="matrix-cells">
              <div
                v-for="(cell, colIdx) in matrixData.matrix[rowIdx]"
                :key="`cell-${rowIdx}-${colIdx}`"
                class="matrix-cell"
                :style="{
                  width: `${cellSize}px`,
                  height: `${cellSize}px`,
                  backgroundColor: getCellColor(cell, rowIdx, colIdx),
                  opacity: getCellOpacity(rowIdx, colIdx)
                }"
                :title="cell === 1 ? `${getNodeLabel(matrixData.nodes[rowIdx])} → ${getNodeLabel(matrixData.nodes[colIdx])}` : ''"
                @mouseenter="() => { hoveredRow = rowIdx; hoveredCol = colIdx }"
                @mouseleave="() => { hoveredRow = null; hoveredCol = null }"
              ></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Info note -->
    <div class="info-note">
      <div class="flex items-center gap-2">
        <span class="scada-led scada-led-cyan"></span>
        <p class="font-mono uppercase text-xs">Rows = Source | Columns = Target | Hover to Highlight Dependencies</p>
      </div>
      <p class="text-xs text-gray-500 font-mono uppercase">Limited to 100 Modules for Performance. Use Filters to Focus on Specific Areas.</p>
    </div>
  </div>
</template>

<style scoped>
.matrix-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  background: #0f172a;
  border-radius: 8px;
  min-height: 800px;
}

.controls {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  padding: 12px;
  background: rgba(30, 41, 59, 0.5);
  border: 2px solid #334155;
  border-radius: 6px;
}

.control-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.control-label {
  font-size: 12px;
  color: #94a3b8;
  font-weight: 500;
}

.search-input,
.folder-select {
  padding: 6px 12px;
  background: #1e293b;
  border: 1px solid #475569;
  border-radius: 4px;
  color: #e2e8f0;
  font-size: 12px;
  min-width: 200px;
}

.search-input:focus,
.folder-select:focus {
  outline: none;
  border-color: #3b82f6;
}

.stats-bar {
  display: flex;
  gap: 24px;
  padding: 12px;
  background: rgba(30, 41, 59, 0.5);
  border: 2px solid #334155;
  border-radius: 6px;
}

.stat-item {
  display: flex;
  gap: 8px;
  font-size: 13px;
}

.stat-label {
  color: #94a3b8;
}

.stat-value {
  color: #06b6d4;
  font-weight: 600;
}

.legend {
  display: flex;
  gap: 16px;
  padding: 8px 12px;
  background: rgba(30, 41, 59, 0.5);
  border: 2px solid #334155;
  border-radius: 6px;
  font-size: 11px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #cbd5e1;
}

.legend-box {
  width: 16px;
  height: 16px;
  border-radius: 2px;
  border: 1px solid #475569;
}

.matrix-wrapper {
  overflow: auto;
  flex: 1;
  background: #0a0f1e;
  border-radius: 6px;
  padding: 16px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 400px;
  color: #64748b;
  gap: 8px;
}

.matrix-grid {
  position: relative;
  min-width: 100%;
}

.column-labels {
  position: relative;
  display: flex;
  margin-bottom: 8px;
}

.column-label {
  position: absolute;
  top: 0;
  transform-origin: left top;
  transform: rotate(-60deg);
  white-space: nowrap;
  font-size: 10px;
  color: #cbd5e1;
  cursor: pointer;
  transition: color 0.2s;
}

.column-label.highlighted {
  color: #3b82f6;
  font-weight: 600;
}

.matrix-rows {
  display: flex;
  flex-direction: column;
}

.matrix-row {
  display: flex;
  align-items: center;
}

.row-label {
  width: 200px;
  padding: 4px 8px;
  font-size: 10px;
  color: #cbd5e1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: pointer;
  transition: color 0.2s;
  display: flex;
  align-items: center;
  gap: 6px;
}

.row-label.highlighted {
  color: #3b82f6;
  font-weight: 600;
}

.coupling-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.row-label-text {
  overflow: hidden;
  text-overflow: ellipsis;
}

.matrix-cells {
  display: flex;
  flex-wrap: nowrap;
}

.matrix-cell {
  border: 1px solid #0f172a;
  cursor: pointer;
  transition: opacity 0.2s, transform 0.1s;
  flex-shrink: 0;
}

.matrix-cell:hover {
  transform: scale(1.1);
  border-color: #64748b;
  z-index: 10;
}

.info-note {
  padding: 8px 12px;
  background: rgba(59, 130, 246, 0.1);
  border: 2px solid rgba(59, 130, 246, 0.3);
  border-radius: 6px;
  font-size: 12px;
  color: #94a3b8;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.text-red-400 {
  color: #f87171;
}

.text-sm {
  font-size: 0.875rem;
}

.text-xs {
  font-size: 0.75rem;
}

.text-gray-500 {
  color: #64748b;
}
</style>
