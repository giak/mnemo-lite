<script setup lang="ts">
/**
 * Expanse Tag Detail Modal
 * Shows memories with a specific Expanse tag
 */
import { ref, watch } from 'vue'

interface Props {
  tag: string | null
  isOpen: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  close: []
}>()

interface TagMemory {
  id: string
  title: string
  memory_type: string
  content_preview: string
  created_at: string
  tags: string[]
}

const memories = ref<TagMemory[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

watch(() => props.isOpen, async (isOpen) => {
  if (isOpen && props.tag) {
    await fetchMemories()
  } else {
    memories.value = []
    error.value = null
  }
})

async function fetchMemories() {
  if (!props.tag) return
  loading.value = true
  error.value = null
  try {
    const response = await fetch('http://localhost:8001/api/v1/memories/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: props.tag, tags: [props.tag], limit: 20 })
    })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const result = await response.json()
    memories.value = result.results || []
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unknown error'
  } finally {
    loading.value = false
  }
}

function handleClose() {
  emit('close')
}

function handleBackdropClick(event: MouseEvent) {
  if (event.target === event.currentTarget) handleClose()
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false
  })
}
</script>

<template>
  <Transition name="modal-backdrop">
    <div
      v-if="isOpen"
      class="fixed inset-0 bg-black bg-opacity-75 z-50 flex items-center justify-center p-4"
      @click="handleBackdropClick"
    >
      <Transition name="modal-content">
        <div
          v-if="isOpen"
          class="scada-panel-dark rounded-lg shadow-2xl max-w-3xl w-full max-h-[80vh] overflow-hidden flex flex-col"
          @click.stop
        >
          <!-- Header -->
          <div class="flex items-center justify-between p-4 border-b-2 border-slate-700">
            <div class="flex items-center gap-3">
              <span class="scada-led scada-led-cyan"></span>
              <h2 class="text-lg font-bold text-cyan-400 font-mono uppercase tracking-wide">
                {{ tag }}
              </h2>
              <span class="scada-data text-slate-400 text-sm ml-2">[{{ memories.length }}]</span>
            </div>
            <button
              @click="handleClose"
              class="text-gray-400 hover:text-white transition-colors p-1 rounded hover:bg-slate-700"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <!-- Content -->
          <div class="flex-1 overflow-y-auto p-4">
            <!-- Loading -->
            <div v-if="loading" class="flex items-center justify-center py-12">
              <div class="animate-spin rounded-full h-8 w-8 border-4 border-cyan-400 border-t-transparent"></div>
              <span class="ml-3 text-gray-400 font-mono text-sm uppercase">Loading...</span>
            </div>

            <!-- Error -->
            <div v-else-if="error" class="bg-red-900/50 border-2 border-red-600 rounded p-3 text-red-300 text-sm font-mono">
              {{ error }}
            </div>

            <!-- Memories list -->
            <div v-else class="space-y-3">
              <div
                v-for="memory in memories"
                :key="memory.id"
                class="bg-slate-800/50 border border-slate-700 rounded p-3"
              >
                <div class="flex items-start justify-between mb-1">
                  <span class="font-mono text-cyan-400 text-sm font-bold">{{ memory.title }}</span>
                  <span class="text-[10px] font-mono text-slate-500 uppercase ml-2 flex-shrink-0">{{ memory.memory_type }}</span>
                </div>
                <div v-if="memory.content_preview" class="text-xs font-mono text-slate-400 mt-1 line-clamp-3">
                  {{ memory.content_preview.substring(0, 200) }}
                </div>
                <div class="flex items-center gap-2 mt-2">
                  <span class="text-[10px] font-mono text-slate-500">{{ formatDate(memory.created_at) }}</span>
                  <div class="flex gap-1 ml-auto">
                    <span
                      v-for="t in memory.tags?.slice(0, 3)"
                      :key="t"
                      class="text-[10px] font-mono px-1 py-0.5 bg-slate-700 text-slate-400 rounded"
                    >{{ t }}</span>
                  </div>
                </div>
              </div>

              <div v-if="memories.length === 0" class="text-center text-slate-600 py-8 text-sm font-mono">
                NO MEMORIES WITH THIS TAG
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div class="border-t-2 border-slate-700 p-3 flex justify-end">
            <button @click="handleClose" class="scada-btn scada-btn-primary text-sm">
              CLOSE
            </button>
          </div>
        </div>
      </Transition>
    </div>
  </Transition>
</template>

<style scoped>
.modal-backdrop-enter-active, .modal-backdrop-leave-active { transition: opacity 0.3s ease; }
.modal-backdrop-enter-from, .modal-backdrop-leave-to { opacity: 0; }
.modal-content-enter-active, .modal-content-leave-active { transition: all 0.3s ease; }
.modal-content-enter-from { opacity: 0; transform: scale(0.95); }
.modal-content-leave-to { opacity: 0; transform: scale(0.95); }
.overflow-y-auto { scrollbar-width: thin; scrollbar-color: #475569 #1e293b; }
.overflow-y-auto::-webkit-scrollbar { width: 8px; }
.overflow-y-auto::-webkit-scrollbar-track { background: #1e293b; }
.overflow-y-auto::-webkit-scrollbar-thumb { background-color: #475569; border-radius: 4px; }
</style>
