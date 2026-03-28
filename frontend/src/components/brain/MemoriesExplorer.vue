<script setup lang="ts">
/**
 * MemoriesExplorer — Taxonomie hiérarchique + liste de memories
 */
import { computed } from 'vue'

const props = defineProps<{
  data: any
}>()

const emit = defineEmits<{
  select: [item: any]
}>()

// Taxonomie hiérarchique
const taxonomie = computed(() => {
  const memories = props.data.memories || []
  const tagGroups: Record<string, { tag: string; label: string; decay: string; halfLife: string; memories: any[] }> = {
    'sys:core': { tag: 'sys:core', label: 'Axiomes scellés', decay: '0', halfLife: '∞', memories: [] },
    'sys:anchor': { tag: 'sys:anchor', label: 'Scellements', decay: '0', halfLife: '∞', memories: [] },
    'sys:pattern': { tag: 'sys:pattern', label: 'Patterns validés', decay: '0.005', halfLife: '140j', memories: [] },
    'sys:extension': { tag: 'sys:extension', label: 'Symboles inventés', decay: '0.010', halfLife: '70j', memories: [] },
    'sys:history': { tag: 'sys:history', label: 'Historique', decay: '0.050', halfLife: '14j', memories: [] },
    'sys:drift': { tag: 'sys:drift', label: 'Dérives', decay: '0.020', halfLife: '35j', memories: [] },
    'trace:fresh': { tag: 'trace:fresh', label: 'Frictions', decay: '0.100', halfLife: '7j', memories: [] },
  }

  for (const m of memories) {
    for (const tag of (m.tags || [])) {
      const key = tag.toLowerCase()
      if (tagGroups[key]) {
        tagGroups[key].memories.push(m)
      }
    }
  }

  return [
    { group: 'PERMANENT', decay: 0, items: [tagGroups['sys:core'], tagGroups['sys:anchor']] },
    { group: 'LONG TERME', decay: 0.005, items: [tagGroups['sys:pattern']] },
    { group: 'MOYEN TERME', decay: 0.01, items: [tagGroups['sys:extension']] },
    { group: 'COURT TERME', decay: 0.02, items: [tagGroups['sys:history'], tagGroups['sys:drift'], tagGroups['trace:fresh']] },
  ]
})

// Selected tag
import { ref } from 'vue'
const selectedTag = ref<string | null>(null)

const filteredMemories = computed(() => {
  if (!selectedTag.value) return props.data.memories || []
  return (props.data.memories || []).filter((m: any) =>
    (m.tags || []).some((t: string) => t.toLowerCase() === selectedTag.value!.toLowerCase())
  )
})

function formatDate(iso: string): string {
  if (!iso) return '--'
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div>
    <!-- Taxonomie header -->
    <div class="mb-4">
      <div class="flex items-center gap-2 mb-3">
        <span class="scada-led scada-led-cyan"></span>
        <h2 class="scada-label text-cyan-400">Taxonomie Μ</h2>
        <span class="text-xs font-mono text-slate-500 ml-auto">{{ data.memoriesCount }} memories</span>
      </div>

      <!-- Hiérarchie temporelle -->
      <div class="space-y-2">
        <div v-for="group in taxonomie" :key="group.group">
          <div class="text-[10px] font-mono uppercase tracking-wider text-slate-600 mb-1">
            {{ group.group }} <span v-if="group.decay > 0" class="text-slate-700">(decay={{ group.decay }})</span>
          </div>
          <div class="flex gap-1 flex-wrap">
            <button
              v-for="item in group.items"
              :key="item.tag"
              class="text-[10px] font-mono px-2 py-1 rounded border transition-colors"
              :class="selectedTag === item.tag
                ? 'bg-cyan-900/30 border-cyan-600 text-cyan-400'
                : 'bg-slate-800/50 border-slate-700 text-slate-400 hover:border-cyan-600'"
              @click="selectedTag = selectedTag === item.tag ? null : item.tag"
            >
              {{ item.label }} ({{ item.memories.length }})
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Memories list -->
    <div class="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
      <div
        v-for="memory in filteredMemories"
        :key="memory.id"
        class="bg-slate-800/50 border border-slate-700 rounded px-3 py-2 cursor-pointer hover:border-cyan-600 transition-colors"
        @click="emit('select', memory)"
      >
        <div class="flex items-center gap-2 mb-1">
          <span class="scada-led scada-led-green"></span>
          <span class="font-mono text-xs text-cyan-400 truncate">{{ memory.title }}</span>
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

      <div v-if="filteredMemories.length === 0" class="text-center text-slate-600 py-8 text-sm font-mono">
        NO MEMORIES
      </div>
    </div>
  </div>
</template>
