<script setup lang="ts">
/**
 * EPIC-35 Story 35.4: Search Analytics Dashboard
 * Displays search statistics, top queries, and cache performance.
 */
import { ref, onMounted, onUnmounted } from 'vue'
import { API } from '@/config/api'

const loading = ref(false)
const error = ref<string | null>(null)
const lastUpdated = ref<Date | null>(null)

interface SearchStats {
  total_searches: number
  cache_hits: number
  cache_misses: number
  avg_response_time_ms: number
  top_queries: { query: string; count: number }[]
  zero_result_queries: { query: string; count: number }[]
  slow_queries: { query: string; time_ms: number }[]
}

const stats = ref<SearchStats>({
  total_searches: 0,
  cache_hits: 0,
  cache_misses: 0,
  avg_response_time_ms: 0,
  top_queries: [],
  zero_result_queries: [],
  slow_queries: []
})

async function fetchStats() {
  loading.value = true
  try {
    // Fetch from multiple sources
    const [cacheResp] = await Promise.all([
      fetch(`${API}/cache/stats`).catch(() => null)
    ])

    // Simulate analytics from available data
    // In production, this would come from a dedicated analytics endpoint
    const cacheStats = cacheResp ? await cacheResp.json() : null

    stats.value = {
      total_searches: 0, // Would come from analytics service
      cache_hits: cacheStats?.l1?.hits || 0,
      cache_misses: cacheStats?.l1?.misses || 0,
      avg_response_time_ms: 0,
      top_queries: [],
      zero_result_queries: [],
      slow_queries: []
    }

    lastUpdated.value = new Date()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to fetch analytics'
  } finally {
    loading.value = false
  }
}

function formatTime(date: Date | null): string {
  if (!date) return 'NEVER'
  return date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }).toUpperCase()
}

onMounted(() => {
  fetchStats()
})

const refreshInterval = setInterval(fetchStats, 60000)
onUnmounted(() => clearInterval(refreshInterval))
</script>

<template>
  <div class="bg-slate-950">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <!-- Header SCADA -->
      <div class="flex items-center justify-between mb-8">
        <div class="flex items-center gap-4">
          <span class="scada-led scada-led-cyan"></span>
          <div>
            <h1 class="text-3xl font-bold font-mono text-cyan-400 uppercase tracking-wider">Search Analytics</h1>
            <p class="mt-2 text-sm text-gray-400 font-mono uppercase tracking-wide">
              Search Performance & Usage Statistics
            </p>
          </div>
        </div>
        <div class="text-right">
          <button
            @click="fetchStats"
            :disabled="loading"
            class="scada-btn scada-btn-primary"
          >
            {{ loading ? 'REFRESHING...' : 'REFRESH' }}
          </button>
          <p class="mt-2 text-xs text-gray-500 font-mono uppercase">
            Last Check: {{ formatTime(lastUpdated) }}
          </p>
        </div>
      </div>

      <!-- Error Banner -->
      <div v-if="error" class="mb-6 bg-red-950/50 border-l-4 border-red-500 p-4">
        <div class="flex items-center gap-2">
          <span class="scada-led scada-led-red"></span>
          <span class="text-sm text-red-400 font-mono">{{ error }}</span>
        </div>
      </div>

      <!-- Cache Performance -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div class="scada-panel">
          <div class="flex items-center gap-2 mb-2">
            <span class="scada-led scada-led-green"></span>
            <span class="scada-label">Cache Hits</span>
          </div>
          <p class="scada-data text-3xl">{{ stats.cache_hits.toLocaleString() }}</p>
        </div>
        <div class="scada-panel">
          <div class="flex items-center gap-2 mb-2">
            <span class="scada-led scada-led-yellow"></span>
            <span class="scada-label">Cache Misses</span>
          </div>
          <p class="scada-data text-3xl">{{ stats.cache_misses.toLocaleString() }}</p>
        </div>
        <div class="scada-panel">
          <div class="flex items-center gap-2 mb-2">
            <span class="scada-led scada-led-cyan"></span>
            <span class="scada-label">Hit Rate</span>
          </div>
          <p class="scada-data text-3xl">
            {{ stats.cache_hits + stats.cache_misses > 0
              ? Math.round(stats.cache_hits / (stats.cache_hits + stats.cache_misses) * 100)
              : 0 }}%
          </p>
        </div>
      </div>

      <!-- Placeholder message -->
      <div class="scada-panel scada-panel-info">
        <div class="flex items-center gap-3">
          <span class="scada-led scada-led-cyan"></span>
          <div>
            <span class="scada-label">Analytics Backend Pending</span>
            <p class="text-sm text-gray-400 font-mono mt-1">
              Full search analytics (top queries, zero-results, slow queries) requires
              a dedicated analytics backend. Cache stats are available now.
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
