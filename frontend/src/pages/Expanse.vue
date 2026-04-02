<script setup lang="ts">
/**
 * Expanse Dashboard - SCADA Industrial Style
 * 3-column dashboard showing MCP data: memories, code chunks, pattern stats
 */
import { ref, computed } from 'vue'
import { useExpanse } from '@/composables/useExpanse'
import ExpanseTagModal from '@/components/ExpanseTagModal.vue'

const { data, loading, error, lastUpdated, refresh } = useExpanse({
  refreshInterval: 30000
})

// LED color per memory type
const ledColor: Record<string, string> = {
  reference: 'green',
  investigation: 'yellow',
  conversation: 'cyan',
  note: 'cyan',
  task: 'green'
}

// Modal state
const selectedTag = ref<string | null>(null)
const isModalOpen = ref(false)

function openTagModal(tag: string) {
  selectedTag.value = tag
  isModalOpen.value = true
}

function closeTagModal() {
  isModalOpen.value = false
  setTimeout(() => { selectedTag.value = null }, 300)
}

// Group code chunks by file name
const groupedChunks = computed(() => {
  const grouped: Record<string, number> = {}
  for (const chunk of data.value.codeChunks) {
    const fname = chunk.file_path?.split('/').pop() || 'unknown'
    grouped[fname] = (grouped[fname] || 0) + 1
  }
  return Object.entries(grouped).map(([file, count]) => ({ file, count }))
})

// Count memories per Expanse tag
function getTagCount(tag: string): number {
  return data.value.memories.filter(m => m.tags?.includes(tag)).length
}

const expanseTags = [
  'sys:pattern',
  'sys:protocol',
  'sys:drift',
  'sys:extension',
  'sys:history',
  'sys:trace',
  'trace:fresh',
  'sys:anchor',
  'sys:core'
]

const formattedTime = computed(() => {
  if (!lastUpdated.value) return '--:--:--'
  return lastUpdated.value.toLocaleTimeString()
})
</script>

<template>
  <div class="container mx-auto px-4 py-6">
    <!-- Page Header -->
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-4">
        <span class="scada-led scada-led-cyan"></span>
        <h1 class="text-3xl font-bold font-mono text-cyan-400 uppercase tracking-wider">Expanse Dashboard</h1>
      </div>

      <div class="flex items-center gap-4">
        <span class="scada-data text-slate-400 font-mono text-sm">
          LAST UPDATE: {{ formattedTime }}
        </span>
        <button
          @click="refresh"
          :disabled="loading"
          class="scada-btn scada-btn-primary flex items-center gap-2"
        >
          <span v-if="loading">LOADING</span>
          <span v-else>REFRESH</span>
          {{ loading ? 'LOADING...' : 'REFRESH' }}
        </button>
      </div>
    </div>

    <!-- Error Display -->
    <div v-if="error" class="mb-4">
      <div class="bg-red-900/50 border-2 border-red-600 text-red-300 px-4 py-3 rounded flex items-center gap-3">
        <span class="scada-led scada-led-red"></span>
        <span class="text-sm font-mono">{{ error }}</span>
      </div>
    </div>

    <!-- 3-Column Dashboard -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">

      <!-- Col 1: Memories Expanse -->
      <div class="scada-panel">
        <div class="flex items-center gap-3 mb-4">
          <span class="scada-led scada-led-green"></span>
          <h2 class="scada-label text-cyan-400">Memories</h2>
          <span class="scada-data text-slate-400 ml-auto">[{{ data.memories.length }}]</span>
        </div>

        <div class="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
          <div
            v-for="memory in data.memories"
            :key="memory.id"
            class="bg-slate-800/50 border border-slate-700 rounded px-3 py-2"
          >
            <div class="flex items-center gap-2 mb-1">
              <span
                class="scada-led"
                :class="`scada-led-${ledColor[memory.memory_type] || 'cyan'}`"
              ></span>
              <span class="font-mono text-cyan-400 text-sm truncate">{{ memory.title }}</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="scada-label text-xs text-slate-500 uppercase">{{ memory.memory_type }}</span>
              <div v-if="memory.tags?.length" class="flex gap-1 ml-auto flex-wrap">
                <span
                  v-for="tag in memory.tags.slice(0, 3)"
                  :key="tag"
                  class="text-[10px] font-mono px-1.5 py-0.5 bg-slate-700 text-slate-300 rounded"
                >
                  {{ tag }}
                </span>
              </div>
            </div>
          </div>

          <div v-if="data.memories.length === 0" class="scada-data text-slate-500 text-center py-8">
            NO DATA
          </div>
        </div>
      </div>

      <!-- Col 2: Code Chunks -->
      <div class="scada-panel">
        <div class="flex items-center gap-3 mb-4">
          <span class="scada-led scada-led-cyan"></span>
          <h2 class="scada-label text-cyan-400">Code Chunks</h2>
          <span class="scada-data text-slate-400 ml-auto">[{{ data.indexingStats.chunks_today }}]</span>
        </div>

        <div class="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
          <div
            v-for="item in groupedChunks"
            :key="item.file"
            class="bg-slate-800/50 border border-slate-700 rounded px-3 py-2 flex items-center justify-between"
          >
            <span class="font-mono text-sm text-slate-300 truncate">{{ item.file }}</span>
            <span class="scada-data text-cyan-400 text-sm font-mono">{{ item.count }}</span>
          </div>

          <div v-if="groupedChunks.length === 0" class="scada-data text-slate-500 text-center py-8">
            NO CHUNKS
          </div>
        </div>
      </div>

      <!-- Col 3: Pattern Stats -->
      <div class="scada-panel">
        <div class="flex items-center gap-3 mb-4">
          <span class="scada-led scada-led-yellow"></span>
          <h2 class="scada-label text-cyan-400">Patterns Stats</h2>
        </div>

        <div class="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
          <div
            v-for="tag in expanseTags"
            :key="tag"
            class="bg-slate-800/50 border border-slate-700 rounded px-3 py-2 flex items-center justify-between cursor-pointer hover:border-cyan-600 transition-colors"
            @click="openTagModal(tag)"
          >
            <span class="font-mono text-sm text-slate-300 uppercase">{{ tag }}</span>
            <span class="scada-data text-cyan-400 text-sm font-mono">
              {{ getTagCount(tag) }}
            </span>
          </div>

          <!-- Stats summary -->
          <div v-if="data.stats" class="border-t border-slate-700 pt-3 mt-4 space-y-2">
            <div class="flex items-center justify-between">
              <span class="scada-label text-slate-400 uppercase">Total Memories</span>
              <span class="scada-data text-cyan-400 text-lg font-mono font-bold">{{ data.stats.total }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="scada-label text-slate-400 uppercase">Today</span>
              <span class="scada-data text-green-400 text-sm font-mono">{{ data.stats.today }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="scada-label text-slate-400 uppercase">Embedding Rate</span>
              <span class="scada-data text-cyan-400 text-sm font-mono">{{ data.stats.embedding_rate }}%</span>
            </div>
          </div>

          <div v-if="!data.stats" class="scada-data text-slate-500 text-center py-8">
            NO STATS
          </div>
        </div>
      </div>
    </div>

    <!-- Tag Detail Modal -->
    <ExpanseTagModal
      :tag="selectedTag"
      :is-open="isModalOpen"
      @close="closeTagModal"
    />
  </div>
</template>
