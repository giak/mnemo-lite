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

// Preset configurations
interface OrgchartConfig {
  depth: number
  maxChildren: number
  maxModules: number
}

const ORGCHART_PRESETS: Record<string, OrgchartConfig> = {
  'overview': { depth: 3, maxChildren: 10, maxModules: 3 },
  'detailed': { depth: 6, maxChildren: 25, maxModules: 5 },
  'deep-dive': { depth: 10, maxChildren: 50, maxModules: 15 },
  'custom': { depth: 6, maxChildren: 25, maxModules: 5 }
}

// State
const selectedPreset = ref<string>('detailed')
const customDepth = ref(6)
const customMaxChildren = ref(25)
const customMaxModules = ref(5)

// View mode state
const viewMode = ref<ViewMode>('hierarchy')

// Computed config based on preset
const orgchartConfig = computed((): OrgchartConfig => {
  if (selectedPreset.value === 'custom') {
    return {
      depth: customDepth.value,
      maxChildren: customMaxChildren.value,
      maxModules: customMaxModules.value
    }
  }
  const preset = ORGCHART_PRESETS[selectedPreset.value]
  if (!preset) {
    return ORGCHART_PRESETS.detailed
  }
  return preset
})

// Force graph to use new config
const graphKey = ref(0)
const applyConfig = () => {
  graphKey.value++
}


// Save preset to localStorage
watch(selectedPreset, (newPreset) => {
  localStorage.setItem('orgchart_preset', newPreset)
})

// Save custom config to localStorage
watch([customDepth, customMaxChildren, customMaxModules], () => {
  localStorage.setItem('orgchart_custom_config', JSON.stringify({
    depth: customDepth.value,
    maxChildren: customMaxChildren.value,
    maxModules: customMaxModules.value
  }))
})

// Save view mode to localStorage
watch(viewMode, (newMode) => {
  localStorage.setItem('orgchart_view_mode', newMode)
})

// Computed nodes and edges from graphData
const nodes = computed(() => graphData.value?.nodes || [])
const edges = computed(() => graphData.value?.edges || [])

onMounted(async () => {
  // Load saved view mode from localStorage
  const savedViewMode = localStorage.getItem('orgchart_view_mode')
  if (savedViewMode && (savedViewMode === 'complexity' || savedViewMode === 'hubs' || savedViewMode === 'hierarchy')) {
    viewMode.value = savedViewMode as ViewMode
  }

  // Load saved preset from localStorage
  const savedPreset = localStorage.getItem('orgchart_preset')
  if (savedPreset && ORGCHART_PRESETS[savedPreset]) {
    selectedPreset.value = savedPreset
  }

  const savedCustom = localStorage.getItem('orgchart_custom_config')
  if (savedCustom) {
    try {
      const config = JSON.parse(savedCustom)
      customDepth.value = config.depth
      customMaxChildren.value = config.maxChildren
      customMaxModules.value = config.maxModules
    } catch (e) {
      console.error('Failed to load custom config:', e)
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

        <!-- Preset Selector -->
        <div class="flex items-center gap-2">
          <span class="text-gray-400">Preset:</span>
          <select
            v-model="selectedPreset"
            class="bg-slate-700 text-gray-200 border border-slate-600 rounded px-3 py-1 text-xs"
          >
            <option value="overview">Overview</option>
            <option value="detailed">Detailed</option>
            <option value="deep-dive">Deep Dive</option>
            <option value="custom">Custom</option>
          </select>
        </div>

        <!-- Custom Controls (only show when Custom preset is selected) -->
        <template v-if="selectedPreset === 'custom'">
          <div class="flex items-center gap-2">
            <span class="text-gray-400">D:</span>
            <input
              v-model.number="customDepth"
              type="range"
              min="1"
              max="15"
              class="w-20 h-1"
            />
            <span class="font-mono text-cyan-400">{{ customDepth }}</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-gray-400">C:</span>
            <input
              v-model.number="customMaxChildren"
              type="range"
              min="5"
              max="100"
              class="w-20 h-1"
            />
            <span class="font-mono text-cyan-400">{{ customMaxChildren }}</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-gray-400">M:</span>
            <input
              v-model.number="customMaxModules"
              type="range"
              min="1"
              max="20"
              class="w-20 h-1"
            />
            <span class="font-mono text-cyan-400">{{ customMaxModules }}</span>
          </div>
          <button
            @click="applyConfig"
            class="px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-xs transition-colors"
          >
            Apply
          </button>
        </template>

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
        <OrgchartGraph :key="graphKey" :nodes="nodes" :edges="edges" :config="orgchartConfig" />
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
