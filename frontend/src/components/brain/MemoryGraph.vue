<script setup lang="ts">
import { ref, onMounted } from 'vue'
import G6Graph from '../G6Graph.vue'
import type { MemoryNode, MemoryGraphData } from '../../types/memory-graph'
import { api } from '@/api/client'

const graphData = ref<MemoryGraphData>({ nodes: [], edges: [], total_nodes: 0, total_edges: 0 })
const loading = ref(false)
const error = ref<string | null>(null)
const minScore = ref(0.3)
const selectedNode = ref<MemoryNode | null>(null)

const nodeTypeColors: Record<string, string> = {
  decision: '#3B82F6',
  note: '#10B981',
  investigation: '#8B5CF6',
}

const edgeTypeColors: Record<string, string> = {
  shared_entity: '#F97316',
  shared_concept: '#06B6D4',
  shared_tag: '#6B7280',
}

async function fetchGraph() {
  loading.value = true
  error.value = null
  try {
    const res = await api(`/memories/graph?min_score=${minScore.value}&limit=100`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    graphData.value = await res.json()
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function handleNodeClick(node: any) {
  const found = graphData.value.nodes.find(n => n.id === node.id)
  if (found) selectedNode.value = found
}

function getNodeStyle(node: any) {
  const color = nodeTypeColors[node.memory_type] || '#6B7280'
  return {
    fill: color,
    stroke: '#fff',
    lineWidth: 2,
    size: Math.max(20, Math.min(60, (node.size || 1) * 10)),
  }
}

function getEdgeStyle(edge: any) {
  const primaryType = edge.types?.[0] || 'shared_entity'
  const color = edgeTypeColors[primaryType] || '#6B7280'
  return {
    stroke: color,
    lineWidth: Math.max(1, Math.min(4, edge.score * 4)),
    opacity: 0.6 + edge.score * 0.4,
  }
}

onMounted(fetchGraph)
</script>

<template>
  <div class="scada-panel p-4">
    <div class="flex items-center justify-between mb-4">
      <h2 class="scada-label text-lg">
        Memory Graph
      </h2>
      <div class="flex items-center gap-2">
        <label class="scada-label text-xs">Min Score:</label>
        <input
          v-model.number="minScore"
          type="range"
          min="0"
          max="1"
          step="0.1"
          class="w-24"
          @change="fetchGraph"
        >
        <span class="scada-data text-xs">{{ minScore.toFixed(1) }}</span>
        <button
          class="scada-btn scada-btn-ghost text-xs"
          :disabled="loading"
          @click="fetchGraph"
        >
          {{ loading ? '...' : '↻' }}
        </button>
      </div>
    </div>

    <div
      v-if="error"
      class="alert-error p-2 mb-4 text-sm"
    >
      {{ error }}
    </div>
    <div
      v-else-if="graphData.nodes.length === 0"
      class="alert-info p-2 mb-4 text-sm"
    >
      No memory relationships found. Try lowering the minimum score.
    </div>

    <div class="grid grid-cols-[1fr_280px] gap-4">
      <div class="min-h-[500px]">
        <G6Graph
          v-if="graphData.nodes.length > 0"
          :nodes="graphData.nodes.map(n => ({ id: n.id, label: n.title, type: n.memory_type, ...getNodeStyle(n) }))"
          :edges="graphData.edges.map((e, i) => ({ id: `${e.source}-${e.target}-${i}`, source: e.source, target: e.target, type: e.types[0] || 'shared_entity', ...getEdgeStyle(e) }))"
          layout="force"
          @node-click="handleNodeClick"
        />
      </div>

      <div
        v-if="selectedNode"
        class="scada-panel p-3"
      >
        <h3 class="scada-label text-sm mb-2">
          {{ selectedNode.title }}
        </h3>
        <div class="space-y-2 text-xs">
          <div><span class="scada-label">Type:</span> <span class="scada-data">{{ selectedNode.memory_type }}</span></div>
          <div><span class="scada-label">Tags:</span> <span class="scada-data">{{ selectedNode.tags?.join(', ') || '—' }}</span></div>
          <div v-if="selectedNode.entities?.length">
            <span class="scada-label">Entities:</span>
            <div class="flex flex-wrap gap-1 mt-1">
              <span
                v-for="e in selectedNode.entities"
                :key="e"
                class="badge-cyan px-1 py-0.5 text-[10px]"
              >{{ e }}</span>
            </div>
          </div>
          <div v-if="selectedNode.concepts?.length">
            <span class="scada-label">Concepts:</span>
            <div class="flex flex-wrap gap-1 mt-1">
              <span
                v-for="c in selectedNode.concepts"
                :key="c"
                class="badge-purple px-1 py-0.5 text-[10px]"
              >{{ c }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="flex gap-4 mt-4 text-xs">
      <div class="flex items-center gap-1">
        <span
          class="w-3 h-3 rounded-full"
          style="background:#3B82F6"
        /> Decision
      </div>
      <div class="flex items-center gap-1">
        <span
          class="w-3 h-3 rounded-full"
          style="background:#10B981"
        /> Note
      </div>
      <div class="flex items-center gap-1">
        <span
          class="w-3 h-3 rounded-full"
          style="background:#8B5CF6"
        /> Investigation
      </div>
      <div class="flex items-center gap-1">
        <span
          class="w-3 h-1"
          style="background:#F97316"
        /> Shared Entity
      </div>
      <div class="flex items-center gap-1">
        <span
          class="w-3 h-1"
          style="background:#06B6D4"
        /> Shared Concept
      </div>
    </div>
  </div>
</template>
