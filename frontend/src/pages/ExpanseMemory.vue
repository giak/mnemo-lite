<script setup lang="ts">
/**
 * Expanse Memory — État cognitif complet de la mémoire d'Expanse
 * 4 sections: Taxonomie, Cycle de vie, Santé, Memories filtrées
 */
import { computed } from 'vue'
import { useExpanseMemory } from '@/composables/useExpanseMemory'

const { data, loading, error, lastUpdated, refresh, selectedTag, fetchByTag } = useExpanseMemory({
  refreshInterval: 30000
})

// Taxonomie par groupe
const taxonomieByGroup = computed(() => {
  const groups: Record<string, any[]> = { 'PERMANENT': [], 'LONG TERME': [], 'MOYEN TERME': [], 'COURT TERME': [] }
  for (const tag of data.value.tags) {
    if (groups[tag.group]) groups[tag.group].push(tag)
  }
  return Object.entries(groups).filter(([, items]) => items.length > 0)
})

// Group colors
const groupColors: Record<string, string> = {
  'PERMANENT': 'border-purple-500 bg-purple-900/20',
  'LONG TERME': 'border-blue-500 bg-blue-900/20',
  'MOYEN TERME': 'border-cyan-500 bg-cyan-900/20',
  'COURT TERME': 'border-amber-500 bg-amber-900/20'
}

const tagLedColors: Record<string, string> = {
  'sys:core': 'scada-led-green',
  'sys:anchor': 'scada-led-green',
  'sys:pattern': 'scada-led-cyan',
  'sys:extension': 'scada-led-cyan',
  'sys:history': 'scada-led-yellow',
  'sys:drift': 'scada-led-red',
  'trace:fresh': 'scada-led-yellow',
}

function formatDate(iso: string): string {
  if (!iso) return '--'
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}

const formattedTime = computed(() => {
  if (!lastUpdated.value) return '--:--:--'
  return lastUpdated.value.toLocaleTimeString()
})
</script>

<template>
  <div class="min-h-screen bg-[#0a0f1e] text-gray-100">
    <!-- Header -->
    <div class="flex items-center justify-between px-6 py-4 border-b-2 border-slate-700">
      <div class="flex items-center gap-4">
        <span class="scada-led scada-led-cyan"></span>
        <h1 class="text-2xl font-bold font-mono text-cyan-400 uppercase tracking-wider">Μ Expanse Memory</h1>
        <span class="scada-data text-slate-400 text-sm">
          {{ data.totalMemories.toLocaleString() }} memories | {{ data.totalChunks.toLocaleString() }} chunks
        </span>
      </div>
      <div class="flex items-center gap-4">
        <span class="text-xs font-mono text-slate-500">{{ formattedTime }}</span>
        <button @click="refresh" :disabled="loading" class="scada-btn scada-btn-primary">
          {{ loading ? '⏳' : '🔄' }}
        </button>
      </div>
    </div>

    <!-- Error -->
    <div v-if="error" class="mx-6 mt-4 bg-red-900/50 border-2 border-red-600 text-red-300 px-4 py-3 rounded">
      <span class="text-sm font-mono">{{ error }}</span>
    </div>

    <div class="p-6 space-y-6">

      <!-- Section 1: Taxonomie visuelle -->
      <div class="scada-panel">
        <div class="flex items-center gap-2 mb-4">
          <span class="scada-led scada-led-cyan"></span>
          <h2 class="scada-label text-cyan-400">Taxonomie (11 tags)</h2>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div v-for="[group, items] in taxonomieByGroup" :key="group">
            <div class="text-[10px] font-mono uppercase tracking-wider text-slate-600 mb-2">
              {{ group }}
            </div>
            <div class="space-y-2">
              <div
                v-for="tag in items"
                :key="tag.tag"
                class="border rounded-lg p-3 cursor-pointer transition-colors"
                :class="selectedTag === tag.tag
                  ? 'border-cyan-500 bg-cyan-900/30'
                  : groupColors[group] + ' hover:border-cyan-600'"
                @click="fetchByTag(tag.tag)"
              >
                <div class="flex items-center gap-2 mb-1">
                  <span class="scada-led" :class="tagLedColors[tag.tag] || 'scada-led-cyan'"></span>
                  <span class="text-xs font-mono font-bold" :class="selectedTag === tag.tag ? 'text-cyan-400' : 'text-slate-300'">
                    {{ tag.label }}
                  </span>
                  <span class="ml-auto scada-data text-lg font-bold" :class="tag.count > 0 ? 'text-cyan-400' : 'text-slate-600'">
                    {{ tag.count }}
                  </span>
                </div>
                <div class="flex items-center gap-2 text-[10px] font-mono text-slate-500">
                  <span>{{ tag.tag }}</span>
                  <span class="ml-auto">decay={{ tag.decay }} | {{ tag.halfLife }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Section 2: Cycle de vie -->
      <div class="scada-panel">
        <div class="flex items-center gap-2 mb-4">
          <span class="scada-led scada-led-yellow"></span>
          <h2 class="scada-label text-cyan-400">Cycle de Vie</h2>
        </div>
        <div class="flex items-center gap-6 text-sm font-mono">
          <div class="flex items-center gap-2">
            <div class="px-3 py-2 rounded border border-amber-500 bg-amber-900/20">
              <div class="text-[10px] text-slate-500 uppercase">Candidate</div>
              <div class="scada-data text-amber-400 text-lg">{{ data.lifecycle.candidate }}</div>
            </div>
            <span class="text-slate-600 text-xl">──seal──→</span>
          </div>
          <div class="flex items-center gap-2">
            <div class="px-3 py-2 rounded border border-green-500 bg-green-900/20">
              <div class="text-[10px] text-slate-500 uppercase">Sealed</div>
              <div class="scada-data text-green-400 text-lg">{{ data.lifecycle.sealed }}</div>
            </div>
            <span class="text-slate-600 text-xl">──→</span>
          </div>
          <div class="flex items-center gap-2">
            <div class="px-3 py-2 rounded border border-purple-500 bg-purple-900/20">
              <div class="text-[10px] text-slate-500 uppercase">Anchor</div>
              <div class="scada-data text-purple-400 text-lg">{{ data.lifecycle.sealed }}</div>
            </div>
          </div>
          <span class="text-slate-700 text-xl">|</span>
          <div class="flex items-center gap-2">
            <div class="px-3 py-2 rounded border border-red-500 bg-red-900/20">
              <div class="text-[10px] text-slate-500 uppercase">Doubt</div>
              <div class="scada-data text-red-400 text-lg">{{ data.lifecycle.doubt }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Section 3: Santé -->
      <div class="scada-panel">
        <div class="flex items-center gap-2 mb-4">
          <span class="scada-led" :class="data.health.drifts > 0 ? 'scada-led-red' : 'scada-led-green'"></span>
          <h2 class="scada-label text-cyan-400">Santé</h2>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div class="bg-slate-800/50 border border-slate-700 rounded p-3">
            <div class="text-[10px] font-mono text-slate-500 uppercase">Drifts</div>
            <div class="scada-data text-2xl" :class="data.health.drifts > 0 ? 'text-red-400' : 'text-green-400'">
              {{ data.health.drifts }}
            </div>
          </div>
          <div class="bg-slate-800/50 border border-slate-700 rounded p-3">
            <div class="text-[10px] font-mono text-slate-500 uppercase">Traces</div>
            <div class="scada-data text-2xl text-amber-400">{{ data.health.traces }}</div>
          </div>
          <div class="bg-slate-800/50 border border-slate-700 rounded p-3">
            <div class="text-[10px] font-mono text-slate-500 uppercase">Consolidation</div>
            <div class="scada-data text-2xl" :class="data.health.consolidationNeeded ? 'text-amber-400' : 'text-green-400'">
              {{ data.health.consolidationNeeded ? 'REQUISE' : 'OK' }}
            </div>
          </div>
          <div class="bg-slate-800/50 border border-slate-700 rounded p-3">
            <div class="text-[10px] font-mono text-slate-500 uppercase">Decay Presets</div>
            <div class="scada-data text-2xl text-cyan-400">{{ data.health.decayPresets }}</div>
          </div>
        </div>
      </div>

      <!-- Section 4: Memories filtrées -->
      <div class="scada-panel" v-if="selectedTag">
        <div class="flex items-center gap-2 mb-4">
          <span class="scada-led scada-led-cyan"></span>
          <h2 class="scada-label text-cyan-400">Memories — {{ selectedTag }}</h2>
          <span class="scada-data text-slate-400 text-sm ml-auto">{{ data.filteredMemories.length }}</span>
        </div>
        <div class="space-y-2 max-h-[40vh] overflow-y-auto pr-1">
          <div
            v-for="memory in data.filteredMemories"
            :key="memory.id"
            class="bg-slate-800/50 border border-slate-700 rounded px-3 py-2"
          >
            <div class="flex items-center gap-2 mb-1">
              <span class="scada-led scada-led-green"></span>
              <span class="text-xs font-mono text-cyan-400 truncate">{{ memory.title }}</span>
              <span class="ml-auto text-[10px] font-mono text-slate-500">{{ memory.memory_type }}</span>
            </div>
            <div class="flex items-center gap-1 flex-wrap">
              <span
                v-for="tag in (memory.tags || []).slice(0, 3)"
                :key="tag"
                class="text-[9px] font-mono px-1 py-0.5 bg-slate-700 text-slate-400 rounded"
              >{{ tag }}</span>
              <span class="ml-auto text-[9px] font-mono text-slate-600">{{ formatDate(memory.created_at) }}</span>
            </div>
          </div>
          <div v-if="data.filteredMemories.length === 0" class="text-center text-slate-600 py-8 text-sm font-mono">
            NO MEMORIES WITH THIS TAG
          </div>
        </div>
      </div>

    </div>
  </div>
</template>
