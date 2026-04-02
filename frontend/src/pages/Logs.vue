<script setup lang="ts">
/**
 * EPIC-28 Story 28.3: Logs Page — SCADA Style
 * System log viewer with OpenObserve integration link.
 *
 * OpenObserve runs on localhost:5080 and collects all container logs.
 * This page provides quick access + system status overview.
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { API_BASE } from '@/config/api'

const apiStatus = ref<string>('checking')
const mcpStatus = ref<string>('checking')
const dbStatus = ref<string>('checking')
const redisStatus = ref<string>('checking')
const lastChecked = ref<Date | null>(null)
const loading = ref(false)

const openObserveUrl = 'http://localhost:5080'

async function checkServices() {
  loading.value = true
  try {
    // API health (includes DB and Redis status)
    try {
      const resp = await fetch('/health')
      if (resp.ok) {
        const data = await resp.json()
        apiStatus.value = data.status === 'healthy' ? 'healthy' : 'degraded'
        dbStatus.value = data.services?.postgres?.status === 'ok' ? 'healthy' : 'down'
        redisStatus.value = data.services?.redis?.status === 'ok' ? 'healthy' : 'down'
      } else {
        apiStatus.value = 'degraded'
      }
    } catch {
      apiStatus.value = 'down'
      dbStatus.value = 'unknown'
      redisStatus.value = 'unknown'
    }

    // MCP health
    try {
      const resp = await fetch('/mcp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jsonrpc: '2.0', method: 'initialize', params: { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'logs-page', version: '1.0' } }, id: 1 })
      })
      mcpStatus.value = resp.ok ? 'healthy' : 'degraded'
    } catch {
      mcpStatus.value = 'down'
    }

    lastChecked.value = new Date()
  } finally {
    loading.value = false
  }
}
    } catch {
      apiStatus.value = 'down'
      dbStatus.value = 'unknown'
      redisStatus.value = 'unknown'
    }

    // MCP health
    try {
      const resp = await fetch('/mcp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jsonrpc: '2.0', method: 'initialize', params: { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'logs-page', version: '1.0' } }, id: 1 })
      })
      mcpStatus.value = resp.ok ? 'healthy' : 'degraded'
    } catch {
      mcpStatus.value = 'down'
    }

    lastChecked.value = new Date()
  } finally {
    loading.value = false
  }
}

function statusLed(status: string): string {
  switch (status) {
    case 'healthy': return 'scada-led-green'
    case 'degraded': return 'scada-led-yellow'
    case 'down': return 'scada-led-red'
    default: return 'scada-led-gray'
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case 'healthy': return 'HEALTHY'
    case 'degraded': return 'DEGRADED'
    case 'down': return 'DOWN'
    default: return 'UNKNOWN'
  }
}

function formatTime(date: Date | null): string {
  if (!date) return 'NEVER'
  return date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }).toUpperCase()
}

onMounted(() => {
  checkServices()
})

const refreshInterval = setInterval(checkServices, 30000)
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
            <h1 class="text-3xl font-bold font-mono text-cyan-400 uppercase tracking-wider">Logs</h1>
            <p class="mt-2 text-sm text-gray-400 font-mono uppercase tracking-wide">
              System Log Viewer & Service Health
            </p>
          </div>
        </div>
        <div class="text-right">
          <button
            @click="checkServices"
            :disabled="loading"
            class="scada-btn scada-btn-primary"
          >
            {{ loading ? 'CHECKING...' : 'REFRESH' }}
          </button>
          <p class="mt-2 text-xs text-gray-500 font-mono uppercase">
            Last Check: {{ formatTime(lastChecked) }}
          </p>
        </div>
      </div>

      <!-- Service Health Grid -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <!-- API -->
        <div class="scada-panel">
          <div class="flex items-center gap-2 mb-2">
            <span :class="statusLed(apiStatus)" class="scada-led"></span>
            <span class="scada-label">API</span>
          </div>
          <p class="scada-data text-lg">{{ statusLabel(apiStatus) }}</p>
          <p class="text-xs text-gray-500 font-mono mt-1">:8001</p>
        </div>

        <!-- MCP -->
        <div class="scada-panel">
          <div class="flex items-center gap-2 mb-2">
            <span :class="statusLed(mcpStatus)" class="scada-led"></span>
            <span class="scada-label">MCP</span>
          </div>
          <p class="scada-data text-lg">{{ statusLabel(mcpStatus) }}</p>
          <p class="text-xs text-gray-500 font-mono mt-1">:8002</p>
        </div>

        <!-- Database -->
        <div class="scada-panel">
          <div class="flex items-center gap-2 mb-2">
            <span :class="statusLed(dbStatus)" class="scada-led"></span>
            <span class="scada-label">Database</span>
          </div>
          <p class="scada-data text-lg">{{ statusLabel(dbStatus) }}</p>
          <p class="text-xs text-gray-500 font-mono mt-1">:5432</p>
        </div>

        <!-- Redis -->
        <div class="scada-panel">
          <div class="flex items-center gap-2 mb-2">
            <span :class="statusLed(redisStatus)" class="scada-led"></span>
            <span class="scada-label">Redis</span>
          </div>
          <p class="scada-data text-lg">{{ statusLabel(redisStatus) }}</p>
          <p class="text-xs text-gray-500 font-mono mt-1">:6379</p>
        </div>
      </div>

      <!-- OpenObserve Link -->
      <div class="scada-panel scada-panel-info mb-8">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <span class="scada-led scada-led-cyan"></span>
            <div>
              <span class="scada-label">OpenObserve Log Aggregator</span>
              <p class="text-sm text-gray-400 font-mono mt-1">
                Centralized log collection from all containers. Query logs by container, level, or time range.
              </p>
            </div>
          </div>
          <a
            :href="openObserveUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="scada-btn scada-btn-primary"
          >
            OPEN OPENOBSERVE
          </a>
        </div>
      </div>

      <!-- Container Log Links -->
      <div class="scada-panel">
        <h2 class="scada-label text-cyan-400 mb-4">Container Quick Links</h2>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          <a
            :href="`${openObserveUrl}/web/logs?stream_type=logs&stream=mnemo-api`"
            target="_blank"
            rel="noopener noreferrer"
            class="flex items-center gap-3 p-3 bg-slate-800/50 border border-slate-700 rounded hover:border-cyan-600 hover:bg-slate-800/80 transition-colors"
          >
            <span class="scada-led scada-led-cyan"></span>
            <div>
              <span class="text-sm font-mono text-cyan-400">mnemo-api</span>
              <p class="text-xs text-gray-500 font-mono">FastAPI application logs</p>
            </div>
          </a>
          <a
            :href="`${openObserveUrl}/web/logs?stream_type=logs&stream=mnemo-mcp`"
            target="_blank"
            rel="noopener noreferrer"
            class="flex items-center gap-3 p-3 bg-slate-800/50 border border-slate-700 rounded hover:border-cyan-600 hover:bg-slate-800/80 transition-colors"
          >
            <span class="scada-led scada-led-green"></span>
            <div>
              <span class="text-sm font-mono text-cyan-400">mnemo-mcp</span>
              <p class="text-xs text-gray-500 font-mono">MCP server logs</p>
            </div>
          </a>
          <a
            :href="`${openObserveUrl}/web/logs?stream_type=logs&stream=mnemo-worker`"
            target="_blank"
            rel="noopener noreferrer"
            class="flex items-center gap-3 p-3 bg-slate-800/50 border border-slate-700 rounded hover:border-cyan-600 hover:bg-slate-800/80 transition-colors"
          >
            <span class="scada-led scada-led-yellow"></span>
            <div>
              <span class="text-sm font-mono text-cyan-400">mnemo-worker</span>
              <p class="text-xs text-gray-500 font-mono">Background worker logs</p>
            </div>
          </a>
        </div>
      </div>
    </div>
  </div>
</template>
