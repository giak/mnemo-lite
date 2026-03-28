<script setup lang="ts">
/**
 * GroupTabs — Onglets par groupe (Μ+Λ+Φ, Ξ, Ω)
 */
defineProps<{
  group: 'memory' | 'system' | 'intelligence'
  tabs: string[]
  activeTab: string
  data: any
}>()

const emit = defineEmits<{
  select: [tab: string]
}>()

const tabLabels: Record<string, string> = {
  memories: 'Memories',
  code: 'Code Chunks',
  events: 'Events',
  vocabf: 'Vocabf',
  alerts: 'Alerts',
  metrics: 'Metrics',
  errors: 'Errors',
  decay: 'Decay',
  cache: 'Cache',
  lsp: 'LSP',
  autosave: 'Autosave',
  batch: 'Batch',
  graph: 'Graph',
  computed: 'Metrics',
  weights: 'Weights',
  search: 'Search'
}

const tabIcons: Record<string, string> = {
  memories: '🧠',
  code: '💻',
  events: '📅',
  vocabf: '📖',
  alerts: '🔴',
  metrics: '📈',
  errors: '⚠️',
  decay: '⏳',
  cache: '💾',
  lsp: '🔧',
  autosave: '🔄',
  batch: '📦',
  graph: '🔗',
  computed: '📊',
  weights: '⚖️',
  search: '🔍'
}

function getTabCount(tab: string, data: any): number {
  const counts: Record<string, number> = {
    memories: data.memoriesCount || 0,
    code: data.chunksCount || 0,
    events: data.eventsCount || 0,
    vocabf: data.vocabfWords?.length || 0,
    alerts: data.alertsCount || 0,
    metrics: data.metricsCount || 0,
    errors: data.indexingErrors?.length || 0,
    decay: data.decayConfig?.length || 0,
    cache: 0,
    lsp: 0,
    autosave: 0,
    batch: 0,
    graph: (data.nodesCount || 0) + (data.edgesCount || 0),
    computed: data.computedMetricsCount || 0,
    weights: data.edgeWeightsCount || 0,
    search: data.searchResults?.length || 0
  }
  return counts[tab] || 0
}
</script>

<template>
  <div class="space-y-1">
    <div
      v-for="tab in tabs"
      :key="tab"
      class="flex items-center gap-2 px-3 py-2 rounded cursor-pointer transition-colors text-xs font-mono"
      :class="activeTab === tab
        ? 'bg-cyan-900/30 text-cyan-400 border border-cyan-600'
        : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800/50 border border-transparent'"
      @click="emit('select', tab)"
    >
      <span>{{ tabIcons[tab] || '•' }}</span>
      <span class="uppercase tracking-wider">{{ tabLabels[tab] || tab }}</span>
      <span class="ml-auto text-[10px]" :class="activeTab === tab ? 'text-cyan-300' : 'text-slate-600'">
        {{ getTabCount(tab, data).toLocaleString() }}
      </span>
    </div>
  </div>
</template>
