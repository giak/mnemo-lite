<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useCodeGraph } from '@/composables/useCodeGraph'
import OrgchartGraph from '@/components/OrgchartGraph.vue'
import ForceDirectedGraph from '@/components/ForceDirectedGraph.vue'
import DependencyMatrix from '@/components/DependencyMatrix.vue'
import type { ViewMode } from '@/types/orgchart-types'
import { VIEW_MODES } from '@/types/orgchart-types'

const {
  repositories,
  graphData,
  stats,
  loading,
  error,
  building,
  fetchRepositories,
  fetchStats,
  fetchModuleGraphData,
  buildGraph
} = useCodeGraph()

const repository = ref('CVgenerator')

// View mode state
const viewMode = ref<ViewMode>('hierarchy')

// Semantic zoom state (0-100%)
const zoomLevel = ref(30) // Default to 30% (Architecture zone)

// Advanced weights for scoring (default: adaptive)
const weights = ref({
  complexity: 0.4,
  loc: 0.3,
  connections: 0.3
})

// Modal state
const showWeightsModal = ref(false)

// Legend state
const legendExpanded = ref(true)

// Force graph to recreate on data changes
const graphKey = ref(0)

// Fullscreen state
const isFullscreen = ref(false)
const fullscreenContainer = ref<HTMLElement | null>(null)

// Save view mode to localStorage
watch(viewMode, (newMode) => {
  localStorage.setItem('orgchart_view_mode', newMode)
})

// Save zoom level to localStorage
watch(zoomLevel, (newLevel) => {
  localStorage.setItem('orgchart_zoom_level', String(newLevel))
})

// Save weights to localStorage
watch(weights, (newWeights) => {
  localStorage.setItem('orgchart_weights', JSON.stringify(newWeights))
}, { deep: true })

// Save legend expanded state to localStorage
watch(legendExpanded, (val) => {
  localStorage.setItem('orgchart_legend_expanded', String(val))
})

// Reset weights to adaptive defaults
const resetWeights = () => {
  weights.value = {
    complexity: 0.4,
    loc: 0.3,
    connections: 0.3
  }
}

// Toggle fullscreen
const toggleFullscreen = async () => {
  if (!fullscreenContainer.value) return

  try {
    if (!document.fullscreenElement) {
      await fullscreenContainer.value.requestFullscreen()
      isFullscreen.value = true
    } else {
      await document.exitFullscreen()
      isFullscreen.value = false
    }
  } catch (err) {
    console.error('Fullscreen error:', err)
  }
}

// Computed nodes and edges from graphData
const nodes = computed(() => graphData.value?.nodes || [])
const edges = computed(() => graphData.value?.edges || [])

// Legend content based on view mode
interface LegendColorItem {
  dot: string
  label: string
}

interface LegendContent {
  title: string
  colors: LegendColorItem[]
  size: string
}

const legendContent = computed((): LegendContent => {
  switch (viewMode.value) {
    case 'complexity':
      return {
        title: '📊 Complexity View',
        colors: [
          { dot: '#10b981', label: 'Low (≤10)' },
          { dot: '#fbbf24', label: 'Medium (11-20)' },
          { dot: '#f97316', label: 'High (21-30)' },
          { dot: '#ef4444', label: 'Very High (>30)' }
        ],
        size: 'Based on lines of code'
      }
    case 'hubs':
      return {
        title: '🔗 Hubs View',
        colors: [
          { dot: '#3b82f6', label: 'Depended Upon (many incoming)' },
          { dot: '#8b5cf6', label: 'Balanced' },
          { dot: '#f97316', label: 'Depends On Others (many outgoing)' }
        ],
        size: 'Based on total connections'
      }
    case 'force':
      return {
        title: '🌐 Architecture View',
        colors: [
          { dot: '#3b82f6', label: 'Cluster by folder' },
          { dot: '#10b981', label: 'Automatic grouping' }
        ],
        size: 'Based on chunk count'
      }
    case 'matrix':
      return {
        title: '📋 Matrix View',
        colors: [
          { dot: '#3b82f6', label: 'Dependency' },
          { dot: '#ef4444', label: 'Circular' },
          { dot: '#fbbf24', label: 'Self-reference' }
        ],
        size: 'Heatmap visualization'
      }
    case 'hierarchy':
    default:
      return {
        title: '🌳 Hierarchy View',
        colors: [
          { dot: '#a855f7', label: 'Root (depth 0)' },
          { dot: '#06b6d4', label: 'Level 1' },
          { dot: '#3b82f6', label: 'Level 2' },
          { dot: '#6366f1', label: 'Deeper levels' }
        ],
        size: 'Based on descendants count'
      }
  }
})

onMounted(async () => {
  // Load saved legend state from localStorage
  const savedLegendState = localStorage.getItem('orgchart_legend_expanded')
  if (savedLegendState !== null) {
    legendExpanded.value = savedLegendState === 'true'
  }

  // Load saved view mode from localStorage
  const savedViewMode = localStorage.getItem('orgchart_view_mode')
  if (savedViewMode && (savedViewMode === 'complexity' || savedViewMode === 'hubs' || savedViewMode === 'hierarchy' || savedViewMode === 'force' || savedViewMode === 'matrix')) {
    viewMode.value = savedViewMode as ViewMode
  }

  // Load saved zoom level
  const savedZoom = localStorage.getItem('orgchart_zoom_level')
  if (savedZoom !== null) {
    const parsed = parseInt(savedZoom, 10)
    if (!isNaN(parsed) && parsed >= 0 && parsed <= 100) {
      zoomLevel.value = parsed
    }
  }

  // Load saved weights
  const savedWeights = localStorage.getItem('orgchart_weights')
  if (savedWeights) {
    try {
      const parsed = JSON.parse(savedWeights)
      if (parsed.complexity !== undefined && parsed.loc !== undefined && parsed.connections !== undefined) {
        weights.value = parsed
      }
    } catch (e) {
      console.error('Failed to load weights:', e)
    }
  }

  console.log('[Orgchart] Mounting...')

  // Fetch available repositories
  console.log('[Orgchart] Fetching repositories...')
  await fetchRepositories()
  console.log('[Orgchart] Available repositories:', repositories.value)

  // Load initial repository
  if (repositories.value && repositories.value.length > 0) {
    const firstRepo = repositories.value[0]
    if (firstRepo) {
      repository.value = firstRepo
      console.log('[Orgchart] Loading repository:', repository.value)
      await Promise.all([
        fetchStats(repository.value),
        fetchModuleGraphData(repository.value)
      ])
      console.log('[Orgchart] Initial data loaded:', {
        nodes: nodes.value.length,
        edges: edges.value.length
      })
    }
  }

  // Listen for fullscreen changes (e.g., ESC key)
  document.addEventListener('fullscreenchange', () => {
    isFullscreen.value = !!document.fullscreenElement
  })
})

const handleRepositoryChange = async () => {
  console.log('[Orgchart] Repository changed to:', repository.value)
  await Promise.all([
    fetchStats(repository.value),
    fetchModuleGraphData(repository.value)
  ])
  console.log('[Orgchart] Graph data loaded:', {
    nodes: nodes.value.length,
    edges: edges.value.length
  })
}

const handleBuildGraph = async () => {
  await buildGraph(repository.value)
  await Promise.all([
    fetchStats(repository.value),
    fetchModuleGraphData(repository.value)
  ])
}
</script>

<template>
  <div
    ref="fullscreenContainer"
    class="h-full bg-slate-950 overflow-hidden flex flex-col"
    :class="{ 'fullscreen-container': isFullscreen }"
  >
    <div class="max-w-full mx-auto px-4 py-3 flex-shrink-0">
      <!-- Ultra-Compact Toolbar -->
      <div class="bg-slate-800/50 rounded-lg px-4 py-2 flex items-center gap-4 border-2 border-slate-700 text-xs">
        <!-- Title -->
        <div class="flex items-center gap-3">
          <span class="scada-led scada-led-cyan"></span>
          <span class="text-gray-400 uppercase tracking-wide font-mono">Organigramme</span>
        </div>

        <!-- Stats -->
        <div class="flex items-center gap-3">
          <div class="flex items-center gap-2">
            <span class="scada-label">N:</span>
            <span class="scada-data text-cyan-400">{{ stats?.total_nodes || 0 }}</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="scada-label">E:</span>
            <span class="scada-data text-emerald-400">{{ stats?.total_edges || 0 }}</span>
          </div>
        </div>

        <div class="h-4 w-px bg-slate-600"></div>

        <!-- Repository Selector -->
        <select
          v-model="repository"
          @change="handleRepositoryChange"
          class="bg-slate-700 text-gray-200 border border-slate-600 rounded px-3 py-1 text-xs"
        >
          <option v-for="repo in repositories" :key="repo" :value="repo">{{ repo }}</option>
        </select>

        <div class="h-4 w-px bg-slate-600"></div>

        <!-- View Mode Selector -->
        <div class="flex items-center gap-2">
          <span class="scada-label">Vue:</span>
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

        <div class="h-4 w-px bg-slate-600"></div>

        <!-- Semantic Zoom Slider -->
        <div class="flex items-center gap-3">
          <span class="scada-label">Zoom:</span>
          <div class="flex flex-col gap-1 w-48">
            <!-- Slider with visual zones -->
            <input
              v-model.number="zoomLevel"
              type="range"
              min="0"
              max="100"
              step="1"
              class="w-full h-2 rounded-lg appearance-none cursor-pointer zoom-slider"
              :style="{
                background: `linear-gradient(to right,
                  #ef4444 0%, #f97316 25%,
                  #fbbf24 25%, #fbbf24 50%,
                  #86efac 50%, #86efac 75%,
                  #22c55e 75%, #22c55e 100%)`
              }"
            />
            <!-- Zone labels -->
            <div class="flex justify-between text-[9px] text-gray-500 font-mono uppercase">
              <span>Macro</span>
              <span>Archi</span>
              <span>Détails</span>
              <span>Complet</span>
            </div>
          </div>
          <!-- Current value -->
          <span class="scada-data text-cyan-400 text-xs min-w-[3rem]">{{ zoomLevel }}%</span>

          <!-- Advanced settings button -->
          <button
            @click="showWeightsModal = true"
            class="p-1 text-gray-400 hover:text-cyan-400 transition-colors"
            title="Réglages avancés"
          >
            ⚙️
          </button>
        </div>

        <div class="flex-1"></div>

        <!-- Build Graph Button -->
        <button
          @click="handleBuildGraph"
          :disabled="building"
          class="scada-btn scada-btn-primary text-xs"
        >
          {{ building ? 'BUILDING...' : 'BUILD' }}
        </button>

        <!-- Fullscreen Button -->
        <button
          @click="toggleFullscreen"
          class="scada-btn scada-btn-ghost text-xs"
          :title="isFullscreen ? 'Quitter plein écran (ESC)' : 'Plein écran'"
        >
          {{ isFullscreen ? '🗗' : '⛶' }}
        </button>
      </div>

      <!-- Error Message -->
      <div v-if="error" class="mt-4 bg-red-900/20 border-2 border-red-700 rounded-lg px-4 py-3">
        <div class="flex items-start gap-3">
          <span class="scada-led scada-led-red"></span>
          <div>
            <h3 class="text-sm font-medium text-red-300 uppercase font-mono">Graph Error</h3>
            <p class="mt-1 text-sm text-red-400 font-mono">{{ error }}</p>
          </div>
        </div>
      </div>

      <!-- Loading State -->
      <div v-if="loading" class="mt-6 bg-slate-800/50 rounded-lg p-8 border border-slate-700">
        <div class="flex flex-col items-center justify-center">
          <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-500 mb-4"></div>
          <p class="text-gray-400">Loading organizational chart...</p>
        </div>
      </div>

      <!-- Orgchart Visualization -->
      <div v-else-if="nodes.length > 0" class="mt-4 flex-1 flex flex-col overflow-hidden">
        <!-- Stats Info Card -->
        <div class="bg-slate-800/50 rounded-lg border-2 border-slate-700 p-3 mb-4 flex-shrink-0">
          <div class="flex items-center justify-center gap-6 text-xs">
            <div class="flex items-center gap-2">
              <span class="scada-label">Entry Points:</span>
              <span class="scada-data text-cyan-400">{{ stats?.nodes_by_type?.Module || 0 }}</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="scada-label">Import Edges:</span>
              <span class="scada-data text-emerald-400">{{ stats?.edges_by_type?.imports || 0 }}</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="scada-label">Total Nodes:</span>
              <span class="scada-data text-purple-400">{{ stats?.total_nodes || 0 }}</span>
            </div>
          </div>
        </div>

        <!-- Visualization Components -->
        <div class="relative flex-1 overflow-hidden">
          <!-- Orgchart (Hierarchy, Complexity, Hubs views) -->
          <OrgchartGraph
            v-if="viewMode === 'hierarchy' || viewMode === 'complexity' || viewMode === 'hubs'"
            :key="graphKey"
            :nodes="nodes"
            :edges="edges"
            :view-mode="viewMode"
            :zoom-level="zoomLevel"
            :weights="weights"
            class="h-full"
          />

          <!-- Force-Directed Graph (Architecture view) -->
          <ForceDirectedGraph
            v-else-if="viewMode === 'force'"
            :nodes="nodes"
            :edges="edges"
            class="h-full"
          />

          <!-- Dependency Matrix (Matrix view) -->
          <DependencyMatrix
            v-else-if="viewMode === 'matrix'"
            :nodes="nodes"
            :edges="edges"
            class="h-full"
          />

          <!-- Legend Panel (only for Orgchart views) -->
          <div
            v-if="viewMode === 'hierarchy' || viewMode === 'complexity' || viewMode === 'hubs'"
            class="absolute bottom-4 right-4 bg-slate-800/95 rounded-lg shadow-xl border-2 border-slate-700 text-xs"
          >
            <!-- Header with collapse button -->
            <div
              class="flex items-center justify-between px-3 py-2 border-b-2 border-slate-700 cursor-pointer hover:bg-slate-750 transition-colors"
              @click="legendExpanded = !legendExpanded"
            >
              <div class="flex items-center gap-2">
                <span class="scada-led scada-led-cyan"></span>
                <span class="font-semibold text-gray-200 font-mono uppercase">{{ legendContent.title }}</span>
              </div>
              <svg
                class="w-4 h-4 text-gray-400 transition-transform"
                :class="{ 'rotate-180': !legendExpanded }"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
              </svg>
            </div>

            <!-- Collapsible content -->
            <div v-if="legendExpanded" class="px-3 py-2">
              <div class="mb-2">
                <div class="scada-label mb-1">Colors:</div>
                <div
                  v-for="color in legendContent.colors"
                  :key="color.label"
                  class="flex items-center gap-2 py-1"
                >
                  <div class="w-3 h-3 rounded-full flex-shrink-0" :style="{ backgroundColor: color.dot }"></div>
                  <span class="text-gray-300 font-mono text-[11px]">{{ color.label }}</span>
                </div>
              </div>
              <div class="text-gray-400 border-t-2 border-slate-700 pt-2 mt-2">
                <span class="scada-label">Size:</span> <span class="text-gray-300 font-mono text-[11px]">{{ legendContent.size }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- No Data State -->
      <div v-else class="mt-6 bg-slate-800/50 rounded-lg p-8 border-2 border-slate-700">
        <div class="text-center">
          <div class="flex justify-center mb-4">
            <span class="scada-led scada-led-yellow" style="width: 24px; height: 24px;"></span>
          </div>
          <h3 class="mt-4 text-lg font-medium text-gray-300 uppercase font-mono">No Data Available</h3>
          <p class="mt-2 text-sm text-gray-500 font-mono">
            Build the graph first to see the organizational chart
          </p>
        </div>
      </div>
    </div>

    <!-- Advanced Weights Modal -->
    <Teleport to="body">
      <div
        v-if="showWeightsModal"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
        @click.self="showWeightsModal = false"
      >
        <div class="bg-slate-800 rounded-lg shadow-2xl border-2 border-slate-700 p-6 w-96">
          <!-- Header -->
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-2">
              <span class="scada-led scada-led-cyan"></span>
              <h3 class="text-lg font-semibold text-gray-200 font-mono uppercase">Réglages Avancés</h3>
            </div>
            <button
              @click="showWeightsModal = false"
              class="text-gray-400 hover:text-white transition-colors"
            >
              ✕
            </button>
          </div>

          <!-- Weight Sliders -->
          <div class="space-y-4">
            <div>
              <div class="flex justify-between mb-1">
                <label class="scada-label text-sm">Complexité</label>
                <span class="scada-data text-cyan-400 text-xs">{{ (weights.complexity * 100).toFixed(0) }}%</span>
              </div>
              <input
                v-model.number="weights.complexity"
                type="range"
                min="0"
                max="1"
                step="0.05"
                class="w-full h-2 rounded-lg appearance-none cursor-pointer bg-slate-700"
              />
            </div>

            <div>
              <div class="flex justify-between mb-1">
                <label class="scada-label text-sm">Lignes de Code</label>
                <span class="scada-data text-cyan-400 text-xs">{{ (weights.loc * 100).toFixed(0) }}%</span>
              </div>
              <input
                v-model.number="weights.loc"
                type="range"
                min="0"
                max="1"
                step="0.05"
                class="w-full h-2 rounded-lg appearance-none cursor-pointer bg-slate-700"
              />
            </div>

            <div>
              <div class="flex justify-between mb-1">
                <label class="scada-label text-sm">Connections</label>
                <span class="scada-data text-cyan-400 text-xs">{{ (weights.connections * 100).toFixed(0) }}%</span>
              </div>
              <input
                v-model.number="weights.connections"
                type="range"
                min="0"
                max="1"
                step="0.05"
                class="w-full h-2 rounded-lg appearance-none cursor-pointer bg-slate-700"
              />
            </div>

            <!-- Total indicator -->
            <div class="pt-2 border-t-2 border-slate-700">
              <div class="flex justify-between text-xs">
                <span class="scada-label">Total:</span>
                <span
                  :class="[
                    'scada-data',
                    Math.abs((weights.complexity + weights.loc + weights.connections) - 1) < 0.01
                      ? 'text-green-400'
                      : 'text-orange-400'
                  ]"
                >
                  {{ ((weights.complexity + weights.loc + weights.connections) * 100).toFixed(0) }}%
                </span>
              </div>
              <p class="text-[10px] text-gray-500 mt-1 font-mono">
                Note: Le total n'a pas besoin d'être 100%, les poids sont relatifs.
              </p>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex gap-2 mt-6">
            <button
              @click="resetWeights"
              class="flex-1 scada-btn bg-slate-700 hover:bg-slate-600 text-white text-sm"
            >
              RESET DÉFAUTS
            </button>
            <button
              @click="showWeightsModal = false"
              class="flex-1 scada-btn scada-btn-primary text-sm"
            >
              APPLIQUER
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
/* Semantic zoom slider styling */
.zoom-slider::-webkit-slider-thumb {
  appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #06b6d4;
  cursor: pointer;
  border: 2px solid #fff;
  box-shadow: 0 2px 4px rgba(0,0,0,0.3);
}

.zoom-slider::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #06b6d4;
  cursor: pointer;
  border: 2px solid #fff;
  box-shadow: 0 2px 4px rgba(0,0,0,0.3);
}

/* Fullscreen styles */
.fullscreen-container {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: 9999;
}
</style>
