<script setup lang="ts">
/**
 * EPIC-25 Story 25.3: Dashboard Page
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
  if (!lastUpdated.value) return 'Never'
  const now = new Date()
  const diff = Math.floor((now.getTime() - lastUpdated.value.getTime()) / 1000)

  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
})

const hasErrors = computed(() => errors.value.length > 0)
</script>

<template>
  <div class="min-h-screen bg-slate-950">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <!-- Header -->
      <div class="flex justify-between items-center mb-8">
        <div>
          <h1 class="text-3xl font-bold text-gray-100 uppercase tracking-wide">Dashboard</h1>
          <p class="mt-2 text-sm text-gray-400">
            System health and embedding statistics
          </p>
        </div>
        <div class="text-right">
          <button
            @click="refresh"
            :disabled="loading"
            class="px-4 py-2 bg-slate-700 text-gray-100 hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors border border-slate-600"
          >
            {{ loading ? 'Refreshing...' : 'Refresh' }}
          </button>
          <p class="mt-2 text-xs text-gray-500">
            Last updated: {{ lastUpdatedText }}
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
            <svg
              class="h-5 w-5 text-red-400"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fill-rule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                clip-rule="evenodd"
              />
            </svg>
          </div>
          <div class="ml-3">
            <h3 class="text-sm font-medium text-red-300 uppercase">
              Failed to load some data
            </h3>
            <div class="mt-2 text-sm text-red-400">
              <ul class="list-disc list-inside space-y-1">
                <li v-for="error in errors" :key="error.timestamp">
                  {{ error.endpoint }}: {{ error.message }}
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      <!-- Dashboard Cards Grid -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <!-- System Health Card -->
        <DashboardCard
          title="System Health"
          :value="healthValue"
          :subtitle="healthSubtitle"
          :status="healthStatus"
          :loading="loading && !data.health"
        />

        <!-- TEXT Embeddings Card -->
        <DashboardCard
          title="TEXT Embeddings"
          :value="textEmbeddingsValue"
          :subtitle="textEmbeddingsSubtitle"
          status="info"
          :loading="loading && !data.textEmbeddings"
        />

        <!-- CODE Embeddings Card -->
        <DashboardCard
          title="CODE Embeddings"
          :value="codeEmbeddingsValue"
          :subtitle="codeEmbeddingsSubtitle"
          status="info"
          :loading="loading && !data.codeEmbeddings"
        />
      </div>

      <!-- Details Section -->
      <div class="mt-8 grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- TEXT Embeddings Details -->
        <div
          v-if="data.textEmbeddings"
          class="bg-slate-900 border border-slate-800 p-6"
        >
          <h2 class="text-lg font-semibold text-gray-100 mb-4 uppercase tracking-wide">
            TEXT Embeddings Details
          </h2>
          <dl class="space-y-3">
            <div class="flex justify-between">
              <dt class="text-sm font-medium text-gray-400">Model</dt>
              <dd class="text-sm text-gray-200">
                {{ data.textEmbeddings.model }}
              </dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-sm font-medium text-gray-400">Count</dt>
              <dd class="text-sm text-gray-200">
                {{ data.textEmbeddings.count.toLocaleString() }}
              </dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-sm font-medium text-gray-400">Dimension</dt>
              <dd class="text-sm text-gray-200">
                {{ data.textEmbeddings.dimension }}
              </dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-sm font-medium text-gray-400">Last Indexed</dt>
              <dd class="text-sm text-gray-200">
                {{
                  data.textEmbeddings.lastIndexed
                    ? new Date(data.textEmbeddings.lastIndexed).toLocaleString()
                    : 'Never'
                }}
              </dd>
            </div>
          </dl>
        </div>

        <!-- CODE Embeddings Details -->
        <div
          v-if="data.codeEmbeddings"
          class="bg-slate-900 border border-slate-800 p-6"
        >
          <h2 class="text-lg font-semibold text-gray-100 mb-4 uppercase tracking-wide">
            CODE Embeddings Details
          </h2>
          <dl class="space-y-3">
            <div class="flex justify-between">
              <dt class="text-sm font-medium text-gray-400">Model</dt>
              <dd class="text-sm text-gray-200">
                {{ data.codeEmbeddings.model }}
              </dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-sm font-medium text-gray-400">Count</dt>
              <dd class="text-sm text-gray-200">
                {{ data.codeEmbeddings.count.toLocaleString() }}
              </dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-sm font-medium text-gray-400">Dimension</dt>
              <dd class="text-sm text-gray-200">
                {{ data.codeEmbeddings.dimension }}
              </dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-sm font-medium text-gray-400">Last Indexed</dt>
              <dd class="text-sm text-gray-200">
                {{
                  data.codeEmbeddings.lastIndexed
                    ? new Date(data.codeEmbeddings.lastIndexed).toLocaleString()
                    : 'Never'
                }}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      <!-- Info Footer -->
      <div class="mt-8 text-center text-sm text-gray-500">
        <p>
          Auto-refresh enabled (30s interval) |
          <a
            href="http://localhost:8001/docs"
            target="_blank"
            class="text-cyan-400 hover:text-cyan-300 underline"
          >
            API Documentation
          </a>
        </p>
      </div>
    </div>
  </div>
</template>
