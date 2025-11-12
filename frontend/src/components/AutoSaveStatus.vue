<script setup lang="ts">
/**
 * EPIC-24 Task 5: AutoSave Status Component - SCADA Industrial Style
 * Displays real-time auto-save system metrics from queue monitoring
 */

import { ref, computed, onMounted, onUnmounted } from 'vue'
import DashboardCard from '@/components/DashboardCard.vue'

interface AutoSaveMetrics {
  queue_size: number
  pending: number
  last_save: string | null
  error_count: number
  saves_per_hour: number
  status: 'healthy' | 'warning' | 'error'
}

const metrics = ref<AutoSaveMetrics | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
let refreshInterval: number | null = null

// Fetch metrics from API
async function fetchMetrics() {
  try {
    const response = await fetch('http://localhost:8001/v1/conversations/metrics')
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    metrics.value = await response.json()
    error.value = null
  } catch (e) {
    console.error('Failed to fetch auto-save metrics:', e)
    error.value = e instanceof Error ? e.message : 'Unknown error'
  } finally {
    loading.value = false
  }
}

// Computed properties for UI display
const queueStatus = computed(() => {
  if (!metrics.value) return 'info'
  return metrics.value.status === 'healthy' ? 'success' :
         metrics.value.status === 'warning' ? 'warning' : 'error'
})

const queueValue = computed(() => {
  if (!metrics.value) return '-'
  return `${metrics.value.queue_size} / ${metrics.value.pending}`
})

const queueSubtitle = computed(() => {
  if (!metrics.value) return undefined
  return `${metrics.value.queue_size} total, ${metrics.value.pending} pending`
})

const lastSaveText = computed(() => {
  if (!metrics.value || !metrics.value.last_save) return 'NEVER'

  const saveTime = new Date(metrics.value.last_save)
  const now = new Date()
  const diff = Math.floor((now.getTime() - saveTime.getTime()) / 1000)

  if (diff < 60) return `${diff}S AGO`
  if (diff < 3600) return `${Math.floor(diff / 60)}MIN AGO`
  if (diff < 86400) return `${Math.floor(diff / 3600)}H AGO`
  return `${Math.floor(diff / 86400)}D AGO`
})

const savesPerHourValue = computed(() => {
  if (!metrics.value) return '-'
  return `${metrics.value.saves_per_hour}/H`
})

const savesPerHourSubtitle = computed(() => {
  if (!metrics.value) return undefined
  return `${metrics.value.saves_per_hour} conversations in last hour`
})

// Lifecycle hooks
onMounted(() => {
  fetchMetrics()
  // Refresh every 10 seconds
  refreshInterval = window.setInterval(fetchMetrics, 10000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<template>
  <div class="space-y-4">
    <!-- Title with SCADA style -->
    <div class="flex items-center gap-3 mb-6">
      <span :class="queueStatus === 'success' ? 'scada-led scada-led-green' :
                     queueStatus === 'warning' ? 'scada-led scada-led-yellow' :
                     'scada-led scada-led-red'"></span>
      <h2 class="text-2xl font-bold font-mono text-cyan-400 uppercase tracking-wider">
        Auto-Save Queue
      </h2>
    </div>

    <!-- Error message -->
    <div v-if="error" class="scada-panel border-red-500">
      <div class="flex items-center gap-3">
        <span class="scada-led scada-led-red"></span>
        <p class="scada-label text-red-400">ERROR: {{ error }}</p>
      </div>
    </div>

    <!-- Metrics Grid -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <!-- Queue Size -->
      <DashboardCard
        title="QUEUE STATUS"
        :value="queueValue"
        :subtitle="queueSubtitle"
        :status="queueStatus"
        :loading="loading"
      />

      <!-- Last Save -->
      <DashboardCard
        title="LAST SAVE"
        :value="lastSaveText"
        subtitle="Most recent conversation"
        :status="metrics?.last_save ? 'success' : 'warning'"
        :loading="loading"
      />

      <!-- Saves Per Hour -->
      <DashboardCard
        title="THROUGHPUT"
        :value="savesPerHourValue"
        :subtitle="savesPerHourSubtitle"
        status="info"
        :loading="loading"
      />
    </div>
  </div>
</template>
