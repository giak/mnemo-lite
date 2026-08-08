<script setup lang="ts">
/**
 * EPIC-25 Story 25.5: Code Graph Page
 * Interactive code graph visualization using @antv/g6 (G6Graph component)
 * EPIC-73 : v-network-graph retiré, G6 unique
 */

import { ref, onMounted, watch } from 'vue'
import { useCodeGraph } from '@/composables/useCodeGraph'
import G6Graph from '@/components/G6Graph.vue'

const { stats, graphData, loading, error, building, buildError, repositories, fetchStats, fetchGraphData, buildGraph, fetchRepositories } = useCodeGraph()

const repository = ref<string>('')

// Build graph handler
const handleBuildGraph = async () => {
  await buildGraph(repository.value, 'python')
  // Refresh visualization after build
  await fetchGraphData(repository.value, 500)
}

// Watch repository changes and reload data
watch(repository, async (newRepo) => {
  if (newRepo) {
    console.log('[Graph] Loading repository:', newRepo)
    await fetchStats(newRepo)
    await fetchGraphData(newRepo, 80)
    console.log('[Graph] Graph data loaded:', {
      nodes: graphData.value?.nodes?.length || 0,
      edges: graphData.value?.edges?.length || 0,
      hasData: !!graphData.value
    })
  }
})

// Fetch repositories on mount
onMounted(async () => {
  console.log('[Graph] Fetching repositories...')
  await fetchRepositories()
  console.log('[Graph] Available repositories:', repositories.value)

  // Select first repository by default
  if (repositories.value && repositories.value.length > 0) {
    repository.value = repositories.value[0] || ''
    // Explicitly load data for first repository
    await fetchStats(repository.value)
    await fetchGraphData(repository.value, 80)
    console.log('[Graph] Initial data loaded:', {
      nodes: graphData.value?.nodes?.length || 0,
      edges: graphData.value?.edges?.length || 0,
      hasData: !!graphData.value,
      graphData: graphData.value
    })
  }
})
</script>

<template>
  <div class="bg-slate-950">
    <div class="max-w-full mx-auto px-4 py-3">
      <!-- Loading State -->
      <div
        v-if="loading"
        class="section"
      >
        <div class="animate-pulse">
          <div class="h-4 bg-slate-700 w-1/4 mb-4" />
          <div class="h-64 bg-slate-700" />
        </div>
      </div>

      <!-- Error State -->
      <div
        v-else-if="error"
        class="alert-error"
      >
        <div class="flex items-start gap-3">
          <span class="scada-led scada-led-red" />
          <div>
            <h3 class="text-sm font-medium text-red-300 uppercase font-mono">
              Graph Error
            </h3>
            <p class="mt-1 text-sm text-red-400 font-mono">
              {{ error }}
            </p>
          </div>
        </div>
      </div>

      <!-- Graph Stats + Visualization -->
      <div
        v-else-if="stats"
        class="space-y-2"
      >
        <!-- Ultra-Compact Toolbar: Everything on one line -->
        <div class="bg-slate-800/50 rounded-lg px-4 py-2 flex items-center gap-4 border-2 border-slate-700 text-xs">
          <!-- Stats -->
          <div class="flex items-center gap-3">
            <div class="flex items-center gap-2">
              <span class="scada-led scada-led-cyan" />
              <span class="text-gray-500 uppercase tracking-wide font-mono">Graph</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="scada-label">N:</span>
              <span class="scada-data text-cyan-400">{{ stats.total_nodes }}</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="scada-label">E:</span>
              <span class="scada-data text-emerald-400">{{ stats.total_edges }}</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="scada-label">C:</span>
              <span class="scada-data text-blue-400">{{ stats.nodes_by_type.Class || 0 }}</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="scada-label">F:</span>
              <span class="scada-data text-purple-400">{{ stats.nodes_by_type.Function || 0 }}</span>
            </div>
          </div>

          <div class="h-4 w-px bg-slate-600" />

          <!-- Repository Selector -->
          <select
            v-model="repository"
            class="bg-slate-700 text-gray-200 border border-slate-600 rounded px-3 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option
              value=""
              disabled
            >
              Select repository...
            </option>
            <option
              v-for="repo in repositories"
              :key="repo"
              :value="repo"
            >
              {{ repo }}
            </option>
          </select>

          <div class="flex-1" />

          <!-- Build Graph Button -->
          <button
            :disabled="building || loading"
            class="scada-btn scada-btn-primary text-xs"
            @click="handleBuildGraph"
          >
            <svg
              v-if="building"
              class="animate-spin -ml-1 mr-1 h-3 w-3 inline"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                class="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                stroke-width="4"
              />
              <path
                class="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            {{ building ? 'BUILDING...' : 'BUILD' }}
          </button>
        </div>

        <!-- Build Error Banner -->
        <div
          v-if="buildError"
          class="alert-error"
        >
          <div class="flex items-start gap-3">
            <span class="scada-led scada-led-red" />
            <div>
              <h3 class="text-sm font-medium text-red-300 uppercase font-mono">
                Build Error
              </h3>
              <p class="mt-1 text-sm text-red-400 font-mono">
                {{ buildError }}
              </p>
            </div>
          </div>
        </div>

        <!-- Graph Visualization -->
        <div class="section">
          <!-- Debug info -->
          <div class="text-xs text-gray-500 mb-2">
            Debug: graphData={{ !!graphData }}, nodes={{ graphData?.nodes?.length || 0 }}, edges={{ graphData?.edges?.length || 0 }}
          </div>

          <G6Graph
            v-if="graphData?.nodes && graphData.nodes.length > 0"
            :nodes="graphData.nodes"
            :edges="graphData.edges || []"
            :loading="loading"
          />
          <div
            v-else
            class="flex flex-col items-center justify-center h-[calc(100vh-120px)] bg-slate-900 border border-slate-700 rounded text-gray-400"
          >
            <p>No graph data available</p>
            <p class="text-xs mt-2">
              graphData: {{ graphData ? 'exists' : 'null' }}
            </p>
            <p class="text-xs">
              nodes: {{ graphData?.nodes?.length || 0 }}
            </p>
          </div>

          <!-- Info Message -->
          <div
            v-if="stats.total_nodes === 0"
            class="mt-4 p-4 bg-amber-900/20 border-2 border-amber-700/30 rounded"
          >
            <div class="flex items-start gap-3">
              <span class="scada-led scada-led-yellow" />
              <div>
                <h3 class="text-sm font-medium text-amber-300 font-mono uppercase">
                  Graph Not Built
                </h3>
                <p class="mt-1 text-sm text-amber-400/80 font-mono">
                  The code graph has not been built yet. Click the <strong>"BUILD GRAPH"</strong> button above to analyze code dependencies and generate the graph.
                </p>
              </div>
            </div>
          </div>

          <!-- No Edges Warning -->
          <div
            v-else-if="stats.total_nodes > 0 && stats.total_edges === 0"
            class="mt-4 p-4 bg-blue-900/20 border-2 border-blue-700/30 rounded"
          >
            <div class="flex items-start gap-3">
              <span class="scada-led scada-led-cyan" />
              <div>
                <h3 class="text-sm font-medium text-blue-300 font-mono uppercase">
                  No Dependencies Detected
                </h3>
                <p class="mt-1 text-sm text-blue-400/80 font-mono">
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
