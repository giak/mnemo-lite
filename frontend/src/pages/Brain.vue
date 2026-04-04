<script setup lang="ts">
/**
 * Brain.vue — MnemoLite Brain Layout
 * 3-column CSS Grid: Groups (left) | Content (center) | Sidebar (right)
 */
import { ref, computed } from 'vue'
import { useBrain } from '@/composables/useBrain'
import GroupTabs from '@/components/brain/GroupTabs.vue'
import MemoriesExplorer from '@/components/brain/MemoriesExplorer.vue'
import CodeExplorer from '@/components/brain/CodeExplorer.vue'
import EventsTimeline from '@/components/brain/EventsTimeline.vue'
import AlertsDashboard from '@/components/brain/AlertsDashboard.vue'
import MetricsDashboard from '@/components/brain/MetricsDashboard.vue'
import GraphExplorer from '@/components/brain/GraphExplorer.vue'
import ComputedMetrics from '@/components/brain/ComputedMetrics.vue'
import MemoryGraph from '@/components/brain/MemoryGraph.vue'
import ConsolidationSuggestions from '@/components/brain/ConsolidationSuggestions.vue'
import CacheStats from '@/components/brain/CacheStats.vue'
import BatchStatus from '@/components/brain/BatchStatus.vue'
import BrainSidebar from '@/components/brain/BrainSidebar.vue'

const { data, loading, error, lastUpdated, refresh } = useBrain({
  refreshInterval: 30000
})

// Active group
const activeGroup = ref<'memory' | 'system' | 'intelligence'>('memory')

// Active tab within group
const activeTab = ref<string>('memories')

// Selected item for sidebar
const selectedItem = ref<any>(null)
const selectedItemType = ref<string>('')

function selectGroup(group: 'memory' | 'system' | 'intelligence') {
  activeGroup.value = group
  selectedItem.value = null
  selectedItemType.value = ''
  // Default tab per group
  if (group === 'memory') activeTab.value = 'memories'
  if (group === 'system') activeTab.value = 'alerts'
  if (group === 'intelligence') activeTab.value = 'graph'
}

function selectTab(tab: string) {
  activeTab.value = tab
  selectedItem.value = null
  selectedItemType.value = ''
}

function selectItem(item: any, type: string) {
  selectedItem.value = item
  selectedItemType.value = type
}

// Groups config
const groups = computed(() => [
  {
    id: 'memory' as const,
    label: 'MÉMOIRE',
    modules: ['Μ', 'Λ', 'Φ'],
    count: data.value.memoriesCount + data.value.chunksCount + data.value.eventsCount,
    tabs: ['memories', 'code', 'events', 'vocabf']
  },
  {
    id: 'system' as const,
    label: 'SYSTÈME',
    modules: ['Ξ', 'Ψ'],
    count: data.value.alertsCount + data.value.metricsCount,
    tabs: ['alerts', 'metrics', 'errors', 'decay', 'cache', 'lsp', 'autosave', 'batch']
  },
  {
    id: 'intelligence' as const,
    label: 'INTELLIGENCE',
    modules: ['Ω'],
    count: data.value.nodesCount + data.value.edgesCount + data.value.computedMetricsCount,
    tabs: ['graph', 'computed', 'memory-graph', 'consolidation', 'weights', 'search']
  }
])

const currentGroup = computed(() => groups.value.find(g => g.id === activeGroup.value)!)
</script>

<template>
  <div class="min-h-screen bg-[#0a0f1e] text-gray-100">
    <!-- Header -->
    <div class="flex items-center justify-between px-6 py-4 border-b-2 border-slate-700">
      <div class="flex items-center gap-4">
        <span class="scada-led scada-led-cyan"></span>
        <h1 class="text-2xl font-bold font-mono text-cyan-400 uppercase tracking-wider">Brain</h1>
        <span class="scada-data text-slate-400 text-sm">{{ data.totalRows.toLocaleString() }} rows</span>
      </div>
      <div class="flex items-center gap-4">
        <span v-if="lastUpdated" class="text-xs font-mono text-slate-500">
          {{ lastUpdated.toLocaleTimeString() }}
        </span>
        <button @click="refresh" :disabled="loading" class="scada-btn scada-btn-primary">
          {{ loading ? 'LOADING' : 'REFRESH' }}
        </button>
      </div>
    </div>

    <!-- Error -->
    <div v-if="error" class="mx-6 mt-4 bg-red-900/50 border-2 border-red-600 text-red-300 px-4 py-3 rounded">
      <span class="text-sm font-mono">{{ error }}</span>
    </div>

    <!-- Main Grid -->
    <div class="grid grid-cols-[220px_1fr_320px] gap-0 min-h-[calc(100vh-80px)]">

      <!-- Col 1: Groups -->
      <div class="border-r-2 border-slate-700 p-4 space-y-2">
        <div
          v-for="group in groups"
          :key="group.id"
          class="cursor-pointer rounded-lg p-3 transition-colors"
          :class="activeGroup === group.id
            ? 'bg-slate-800 border-2 border-cyan-600'
            : 'bg-slate-800/30 border-2 border-transparent hover:border-slate-600'"
          @click="selectGroup(group.id)"
        >
          <div class="flex items-center gap-2 mb-1">
            <span class="scada-led" :class="activeGroup === group.id ? 'scada-led-cyan' : 'scada-led-green'"></span>
            <span class="font-mono text-sm font-bold" :class="activeGroup === group.id ? 'text-cyan-400' : 'text-slate-400'">
              {{ group.label }}
            </span>
          </div>
          <div class="flex items-center gap-1 text-[10px] font-mono text-slate-500 ml-5">
            <span v-for="m in group.modules" :key="m" class="px-1 bg-slate-700 rounded">{{ m }}</span>
            <span class="ml-auto text-slate-600">{{ group.count.toLocaleString() }}</span>
          </div>
        </div>

        <!-- Group sub-modules -->
        <div v-if="activeGroup" class="mt-4 pt-4 border-t border-slate-700">
          <GroupTabs
            :group="activeGroup"
            :tabs="currentGroup.tabs"
            :active-tab="activeTab"
            :data="data"
            @select="selectTab"
          />
        </div>
      </div>

      <!-- Col 2: Content -->
      <div class="overflow-y-auto p-4">
        <!-- Μ+Λ+Φ: MEMORY -->
        <MemoriesExplorer v-if="activeGroup === 'memory' && activeTab === 'memories'" :data="data" @select="(item) => selectItem(item, 'memory')" />
        <CodeExplorer v-if="activeGroup === 'memory' && activeTab === 'code'" :data="data" @select="(item) => selectItem(item, 'chunk')" />
        <EventsTimeline v-if="activeGroup === 'memory' && activeTab === 'events'" :data="data" @select="(item) => selectItem(item, 'event')" />

        <!-- Ξ: SYSTEM -->
        <AlertsDashboard v-if="activeGroup === 'system' && activeTab === 'alerts'" :data="data" @select="(item) => selectItem(item, 'alert')" />
        <MetricsDashboard v-if="activeGroup === 'system' && activeTab === 'metrics'" :data="data" />
        <CacheStats v-if="activeGroup === 'system' && activeTab === 'cache'" :data="data" />
        <BatchStatus v-if="activeGroup === 'system' && activeTab === 'batch'" :data="data" />

        <!-- Ω: INTELLIGENCE -->
        <GraphExplorer v-if="activeGroup === 'intelligence' && activeTab === 'graph'" :data="data" @select="(item) => selectItem(item, 'node')" />
        <ComputedMetrics v-if="activeGroup === 'intelligence' && activeTab === 'computed'" :data="data" />
        <MemoryGraph v-if="activeGroup === 'intelligence' && activeTab === 'memory-graph'" />
        <ConsolidationSuggestions v-if="activeGroup === 'intelligence' && activeTab === 'consolidation'" />
      </div>

      <!-- Col 3: Sidebar -->
      <div class="border-l-2 border-slate-700 overflow-y-auto p-4">
        <BrainSidebar
          :item="selectedItem"
          :type="selectedItemType"
          :data="data"
        />
      </div>
    </div>
  </div>
</template>
