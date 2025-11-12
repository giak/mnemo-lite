<script setup lang="ts">
/**
 * EPIC-27: Dashboard Page - SCADA Industrial Style
 * Main dashboard displaying system health and embedding statistics
 */

import { computed } from 'vue'
import { useDashboard } from '@/composables/useDashboard'
import DashboardCard from '@/components/DashboardCard.vue'

// Use dashboard composable with 30-second refresh
const { data, loading, errors, lastUpdated, refresh } = useDashboard({
  refreshInterval: 30000,
})

// Computed properties for card data
const healthStatus = computed(() => {
  if (!data.value.health) return 'info'
  return data.value.health.status === 'healthy' ? 'success' : 'warning'
})

const healthValue = computed(() => {
  if (!data.value.health) return undefined
  return data.value.health.status.toUpperCase()
})

const healthSubtitle = computed(() => {
  if (!data.value.health) return undefined
  const { api, database, redis } = data.value.health.services
  const services = []
  if (api) services.push('API')
  if (database) services.push('DB')
  if (redis) services.push('Redis')
  return `Services: ${services.join(', ')}`
})

const textEmbeddingsValue = computed(() => {
  if (!data.value.textEmbeddings) return undefined
  return data.value.textEmbeddings.count.toLocaleString()
})

const textEmbeddingsSubtitle = computed(() => {
  if (!data.value.textEmbeddings) return undefined
  return `${data.value.textEmbeddings.model} (${data.value.textEmbeddings.dimension}D)`
})

const codeEmbeddingsValue = computed(() => {
  if (!data.value.codeEmbeddings) return undefined
  return data.value.codeEmbeddings.count.toLocaleString()
})

const codeEmbeddingsSubtitle = computed(() => {
  if (!data.value.codeEmbeddings) return undefined
  return `${data.value.codeEmbeddings.model} (${data.value.codeEmbeddings.dimension}D)`
})

const lastUpdatedText = computed(() => {
  if (!lastUpdated.value) return 'NEVER'
  const now = new Date()
  const diff = Math.floor((now.getTime() - lastUpdated.value.getTime()) / 1000)

  if (diff < 60) return `${diff}S AGO`
  if (diff < 3600) return `${Math.floor(diff / 60)}MIN AGO`
  return `${Math.floor(diff / 3600)}H AGO`
})

const hasErrors = computed(() => errors.value.length > 0)
</script>

<template>
  <div class="bg-slate-950">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <!-- Header avec style SCADA -->
      <div class="flex items-center justify-between mb-8">
        <div class="flex items-center gap-4">
          <span class="scada-led scada-led-cyan"></span>
          <div>
            <h1 class="text-3xl font-bold font-mono text-cyan-400 uppercase tracking-wider">Dashboard</h1>
            <p class="mt-2 text-sm text-gray-400 font-mono uppercase tracking-wide">
              System Health & Embedding Statistics
            </p>
          </div>
        </div>
        <div class="text-right">
          <button
            @click="refresh"
            :disabled="loading"
            class="scada-btn scada-btn-primary"
          >
            {{ loading ? 'REFRESHING...' : 'REFRESH' }}
          </button>
          <p class="mt-2 text-xs text-gray-500 font-mono uppercase">
            Last Updated: {{ lastUpdatedText }}
          </p>
        </div>
      </div>

      <!-- Error Banner -->
      <div
        v-if="hasErrors"
        class="mb-6 bg-red-950/50 border-l-4 border-red-500 p-4"
      >
        <div class="flex">
          <div class="flex-shrink-0">
            <span class="scada-led scada-led-red"></span>
          </div>
          <div class="ml-3">
            <h3 class="text-sm scada-status-danger">
              Failed to Load Some Data
            </h3>
            <div class="mt-2 text-sm text-red-400">
              <ul class="list-disc list-inside space-y-1 font-mono">
                <li v-for="error in errors" :key="error.timestamp">
                  {{ error.endpoint }}: {{ error.message }}
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      <!-- Dashboard Cards Grid (utilise les DashboardCard SCADA déjà migrés) -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <DashboardCard
          title="System Health"
          :value="healthValue"
          :subtitle="healthSubtitle"
          :status="healthStatus"
          :loading="loading && !data.health"
        />

        <DashboardCard
          title="TEXT Embeddings"
          :value="textEmbeddingsValue"
          :subtitle="textEmbeddingsSubtitle"
          status="info"
          :loading="loading && !data.textEmbeddings"
        />

        <DashboardCard
          title="CODE Embeddings"
          :value="codeEmbeddingsValue"
          :subtitle="codeEmbeddingsSubtitle"
          status="info"
          :loading="loading && !data.codeEmbeddings"
        />
      </div>

      <!-- Details Section avec style SCADA -->
      <div class="mt-8 grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- TEXT Embeddings Details -->
        <div
          v-if="data.textEmbeddings"
          class="scada-panel"
        >
          <h2 class="text-lg scada-label text-cyan-400 mb-4 pb-3 border-b-2 border-slate-700">
            TEXT Embeddings Details
          </h2>
          <dl class="space-y-3">
            <div class="flex justify-between border-b border-slate-700 pb-2">
              <dt class="scada-label">Model</dt>
              <dd class="text-sm text-gray-200 font-mono">
                {{ data.textEmbeddings.model }}
              </dd>
            </div>
            <div class="flex justify-between border-b border-slate-700 pb-2">
              <dt class="scada-label">Count</dt>
              <dd class="scada-data text-base">
                {{ data.textEmbeddings.count.toLocaleString() }}
              </dd>
            </div>
            <div class="flex justify-between border-b border-slate-700 pb-2">
              <dt class="scada-label">Dimension</dt>
              <dd class="scada-data text-base">
                {{ data.textEmbeddings.dimension }}
              </dd>
            </div>
            <div class="flex justify-between">
              <dt class="scada-label">Last Indexed</dt>
              <dd class="text-sm text-gray-200 font-mono uppercase">
                {{
                  data.textEmbeddings.lastIndexed
                    ? new Date(data.textEmbeddings.lastIndexed).toLocaleString()
                    : 'NEVER'
                }}
              </dd>
            </div>
          </dl>
        </div>

        <!-- CODE Embeddings Details -->
        <div
          v-if="data.codeEmbeddings"
          class="scada-panel"
        >
          <h2 class="text-lg scada-label text-cyan-400 mb-4 pb-3 border-b-2 border-slate-700">
            CODE Embeddings Details
          </h2>
          <dl class="space-y-3">
            <div class="flex justify-between border-b border-slate-700 pb-2">
              <dt class="scada-label">Model</dt>
              <dd class="text-sm text-gray-200 font-mono">
                {{ data.codeEmbeddings.model }}
              </dd>
            </div>
            <div class="flex justify-between border-b border-slate-700 pb-2">
              <dt class="scada-label">Count</dt>
              <dd class="scada-data text-base">
                {{ data.codeEmbeddings.count.toLocaleString() }}
              </dd>
            </div>
            <div class="flex justify-between border-b border-slate-700 pb-2">
              <dt class="scada-label">Dimension</dt>
              <dd class="scada-data text-base">
                {{ data.codeEmbeddings.dimension }}
              </dd>
            </div>
            <div class="flex justify-between">
              <dt class="scada-label">Last Indexed</dt>
              <dd class="text-sm text-gray-200 font-mono uppercase">
                {{
                  data.codeEmbeddings.lastIndexed
                    ? new Date(data.codeEmbeddings.lastIndexed).toLocaleString()
                    : 'NEVER'
                }}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      <!-- Info Footer -->
      <div class="mt-8 text-center text-sm text-gray-500 font-mono">
        <p>
          AUTO-REFRESH ENABLED (30S INTERVAL) |
          <a
            href="http://localhost:8001/docs"
            target="_blank"
            class="text-cyan-400 hover:text-cyan-300 underline"
          >
            API DOCUMENTATION
          </a>
        </p>
      </div>
    </div>
  </div>
</template>
