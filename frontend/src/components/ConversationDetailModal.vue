<script setup lang="ts">
import { ref, watch } from 'vue'
import type { MemoryDetail } from '@/types/memories'

interface Props {
  memoryId: string | null
  isOpen: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  close: []
}>()

const memory = ref<MemoryDetail | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

// Fetch memory details when modal opens
watch(() => props.isOpen, async (isOpen) => {
  if (isOpen && props.memoryId) {
    await fetchMemoryDetail()
  } else {
    memory.value = null
    error.value = null
  }
})

async function fetchMemoryDetail() {
  if (!props.memoryId) return

  loading.value = true
  error.value = null

  try {
    const response = await fetch(`http://localhost:8001/api/v1/memories/${props.memoryId}`)

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('Conversation not found')
      }
      throw new Error('Failed to load conversation')
    }

    memory.value = await response.json()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unknown error'
    console.error('Failed to fetch memory detail:', err)
  } finally {
    loading.value = false
  }
}

function handleClose() {
  emit('close')
}

function handleBackdropClick(event: MouseEvent) {
  if (event.target === event.currentTarget) {
    handleClose()
  }
}

function formatDate(isoString: string): string {
  const date = new Date(isoString)
  return date.toLocaleString('fr-FR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function extractSessionId(tags: string[]): string {
  const sessionTag = tags.find(tag => tag.startsWith('session:'))
  if (!sessionTag) return 'Unknown'
  return sessionTag.replace('session:', '').substring(0, 8)
}
</script>

<template>
  <!-- Modal backdrop -->
  <Transition name="modal-backdrop">
    <div
      v-if="isOpen"
      class="fixed inset-0 bg-black bg-opacity-75 z-50 flex items-center justify-center p-4"
      @click="handleBackdropClick"
    >
      <!-- Modal content -->
      <Transition name="modal-content">
        <div
          v-if="isOpen"
          class="bg-slate-800 rounded-lg shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col"
          @click.stop
        >
          <!-- Header -->
          <div class="flex items-start justify-between p-6 border-b border-slate-700">
            <div class="flex-1 pr-4">
              <h2 class="text-2xl font-bold text-cyan-400 mb-2">
                {{ memory?.title || 'Loading...' }}
              </h2>
              <div v-if="memory" class="flex flex-wrap gap-2 text-sm text-gray-400">
                <span>📅 {{ formatDate(memory.created_at) }}</span>
                <span>•</span>
                <span>Session: {{ extractSessionId(memory.tags) }}</span>
                <span v-if="memory.author">•</span>
                <span v-if="memory.author">👤 {{ memory.author }}</span>
                <span>•</span>
                <span :class="memory.has_embedding ? 'text-green-400' : 'text-red-400'">
                  {{ memory.has_embedding ? '✅ Embedded' : '❌ No embedding' }}
                </span>
              </div>
            </div>
            <button
              @click="handleClose"
              class="text-gray-400 hover:text-white transition-colors p-2 rounded-lg hover:bg-slate-700"
              aria-label="Close modal"
            >
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <!-- Content -->
          <div class="flex-1 overflow-y-auto p-6">
            <!-- Loading state -->
            <div v-if="loading" class="flex items-center justify-center py-12">
              <div class="animate-spin rounded-full h-12 w-12 border-4 border-cyan-400 border-t-transparent"></div>
              <span class="ml-3 text-gray-400">Loading conversation...</span>
            </div>

            <!-- Error state -->
            <div v-else-if="error" class="bg-red-900/20 border border-red-700 rounded-lg p-4 text-red-400">
              <div class="flex items-center">
                <svg class="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
                </svg>
                <span>{{ error }}</span>
              </div>
            </div>

            <!-- Memory content -->
            <div v-else-if="memory" class="space-y-4">
              <!-- Tags -->
              <div v-if="memory.tags.length > 0" class="flex flex-wrap gap-2">
                <span
                  v-for="tag in memory.tags"
                  :key="tag"
                  class="px-2 py-1 text-xs rounded bg-slate-700 text-gray-300 border border-slate-600"
                >
                  #{{ tag }}
                </span>
              </div>

              <!-- Content -->
              <div class="bg-slate-900 rounded-lg p-4 border border-slate-700">
                <h3 class="text-sm font-semibold text-gray-400 mb-3">💬 Conversation Content</h3>
                <div class="prose prose-invert max-w-none">
                  <pre class="whitespace-pre-wrap text-gray-300 text-sm leading-relaxed font-mono">{{ memory.content }}</pre>
                </div>
              </div>

              <!-- Metadata -->
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <div class="bg-slate-900 rounded-lg p-4 border border-slate-700">
                  <div class="text-gray-400 mb-1">Memory Type</div>
                  <div class="text-white font-medium">{{ memory.memory_type }}</div>
                </div>

                <div v-if="memory.updated_at" class="bg-slate-900 rounded-lg p-4 border border-slate-700">
                  <div class="text-gray-400 mb-1">Last Updated</div>
                  <div class="text-white font-medium">{{ formatDate(memory.updated_at) }}</div>
                </div>

                <div class="bg-slate-900 rounded-lg p-4 border border-slate-700">
                  <div class="text-gray-400 mb-1">Memory ID</div>
                  <div class="text-white font-mono text-xs break-all">{{ memory.id }}</div>
                </div>

                <div v-if="memory.project_id" class="bg-slate-900 rounded-lg p-4 border border-slate-700">
                  <div class="text-gray-400 mb-1">Project ID</div>
                  <div class="text-white font-mono text-xs break-all">{{ memory.project_id }}</div>
                </div>
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div class="border-t border-slate-700 p-4 flex justify-end">
            <button
              @click="handleClose"
              class="px-6 py-2 bg-cyan-600 hover:bg-cyan-700 text-white rounded-lg transition-colors font-medium"
            >
              Close
            </button>
          </div>
        </div>
      </Transition>
    </div>
  </Transition>
</template>

<style scoped>
/* Modal backdrop transitions */
.modal-backdrop-enter-active,
.modal-backdrop-leave-active {
  transition: opacity 0.3s ease;
}

.modal-backdrop-enter-from,
.modal-backdrop-leave-to {
  opacity: 0;
}

/* Modal content transitions */
.modal-content-enter-active,
.modal-content-leave-active {
  transition: all 0.3s ease;
}

.modal-content-enter-from {
  opacity: 0;
  transform: scale(0.95) translateY(-20px);
}

.modal-content-leave-to {
  opacity: 0;
  transform: scale(0.95) translateY(20px);
}

/* Custom scrollbar for dark theme */
.overflow-y-auto {
  scrollbar-width: thin;
  scrollbar-color: #475569 #1e293b;
}

.overflow-y-auto::-webkit-scrollbar {
  width: 8px;
}

.overflow-y-auto::-webkit-scrollbar-track {
  background: #1e293b;
}

.overflow-y-auto::-webkit-scrollbar-thumb {
  background-color: #475569;
  border-radius: 4px;
}

.overflow-y-auto::-webkit-scrollbar-thumb:hover {
  background-color: #64748b;
}
</style>
