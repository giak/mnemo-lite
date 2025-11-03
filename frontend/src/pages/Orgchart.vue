<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useCodeGraph } from '@/composables/useCodeGraph'
import OrgchartGraph from '@/components/OrgchartGraph.vue'
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
  fetchGraphData,
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
// @ts-expect-error - Will be used in Task 6 (modal UI)
const showWeightsModal = ref(false)

// Legend state
const legendExpanded = ref(true)

// Force graph to recreate on data changes
const graphKey = ref(0)

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
  if (savedViewMode && (savedViewMode === 'complexity' || savedViewMode === 'hubs' || savedViewMode === 'hierarchy')) {
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
        fetchGraphData(repository.value)
      ])
      console.log('[Orgchart] Initial data loaded:', {
        nodes: nodes.value.length,
        edges: edges.value.length
      })
    }
  }
})

const handleRepositoryChange = async () => {
  console.log('[Orgchart] Repository changed to:', repository.value)
  await Promise.all([
    fetchStats(repository.value),
    fetchGraphData(repository.value)
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
    fetchGraphData(repository.value)
  ])
}
</script>

<template>
  <div class="min-h-screen bg-slate-950">
    <div class="max-w-full mx-auto px-4 py-3">
      <!-- Ultra-Compact Toolbar -->
      <div class="bg-slate-800/50 rounded-lg px-4 py-2 flex items-center gap-4 border border-slate-700 text-xs">
        <!-- Title -->
        <div class="flex items-center gap-3">
          <span class="text-gray-400 uppercase tracking-wide">Organigramme</span>
        </div>

        <!-- Stats -->
        <div class="flex items-center gap-3">
          <div class="flex items-center gap-2">
            <span class="text-gray-400">N:</span>
            <span class="font-mono font-bold text-cyan-400">{{ stats?.total_nodes || 0 }}</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-gray-400">E:</span>
            <span class="font-mono font-bold text-emerald-400">{{ stats?.total_edges || 0 }}</span>
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

        <div class="flex-1"></div>

        <!-- Build Graph Button -->
        <button
          @click="handleBuildGraph"
          :disabled="building"
          class="px-3 py-1 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded text-xs transition-colors"
        >
          {{ building ? 'Building...' : 'Build' }}
        </button>
      </div>

      <!-- Error Message -->
      <div v-if="error" class="mt-4 bg-red-900/20 border border-red-700 rounded-lg px-4 py-3">
        <div class="flex items-start">
          <svg class="h-5 w-5 text-red-400 mt-0.5 mr-3" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
          </svg>
          <div>
            <h3 class="text-sm font-medium text-red-300 uppercase">Error</h3>
            <p class="mt-1 text-sm text-red-400">{{ error }}</p>
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
      <div v-else-if="nodes.length > 0" class="mt-4">
        <!-- Stats Info Card -->
        <div class="bg-slate-800/50 rounded-lg border border-slate-700 p-3 mb-4">
          <div class="flex items-center justify-center gap-6 text-xs">
            <div class="flex items-center gap-2">
              <span class="text-cyan-400 font-mono">→</span>
              <span class="text-gray-400">Entry points: <span class="text-cyan-400 font-semibold">{{ stats?.nodes_by_type?.Module || 0 }}</span></span>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-emerald-400 font-mono">→</span>
              <span class="text-gray-400">Import edges: <span class="text-emerald-400 font-semibold">{{ stats?.edges_by_type?.imports || 0 }}</span></span>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-purple-400 font-mono">→</span>
              <span class="text-gray-400">Total nodes: <span class="text-purple-400 font-semibold">{{ stats?.total_nodes || 0 }}</span></span>
            </div>
          </div>
        </div>

        <!-- Orgchart Component -->
        <div class="relative">
          <OrgchartGraph :key="graphKey" :nodes="nodes" :edges="edges" :view-mode="viewMode" />

          <!-- Legend Panel -->
          <div class="absolute bottom-4 right-4 bg-slate-800/95 rounded-lg shadow-xl border border-slate-700 text-xs">
            <!-- Header with collapse button -->
            <div
              class="flex items-center justify-between px-3 py-2 border-b border-slate-700 cursor-pointer hover:bg-slate-750 transition-colors"
              @click="legendExpanded = !legendExpanded"
            >
              <span class="font-semibold text-gray-200">{{ legendContent.title }}</span>
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
                <div class="text-gray-400 mb-1 font-semibold">Colors:</div>
                <div
                  v-for="color in legendContent.colors"
                  :key="color.label"
                  class="flex items-center gap-2 py-1"
                >
                  <div class="w-3 h-3 rounded-full flex-shrink-0" :style="{ backgroundColor: color.dot }"></div>
                  <span class="text-gray-300">{{ color.label }}</span>
                </div>
              </div>
              <div class="text-gray-400 border-t border-slate-700 pt-2 mt-2">
                <span class="font-semibold">Size:</span> <span class="text-gray-300">{{ legendContent.size }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- No Data State -->
      <div v-else class="mt-6 bg-slate-800/50 rounded-lg p-8 border border-slate-700">
        <div class="text-center">
          <svg class="mx-auto h-12 w-12 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
          </svg>
          <h3 class="mt-4 text-lg font-medium text-gray-300 uppercase">No Data Available</h3>
          <p class="mt-2 text-sm text-gray-500">
            Build the graph first to see the organizational chart
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
