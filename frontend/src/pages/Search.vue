<script setup lang="ts">
/**
 * Search Page with Code and Memories tabs.
 * Supports URL-based tab persistence (?tab=memories)
 */

import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useCodeSearch } from '@/composables/useCodeSearch'
import { useMemorySearch } from '@/composables/useMemorySearch'

const route = useRoute()
const router = useRouter()

// Tab state
type TabType = 'code' | 'memories'
const activeTab = ref<TabType>('code')

// Initialize tab from URL
onMounted(() => {
  const tabParam = route.query.tab as string
  if (tabParam === 'memories') {
    activeTab.value = 'memories'
  }
})

// Sync tab to URL
watch(activeTab, (newTab) => {
  router.replace({ query: { ...route.query, tab: newTab } })
})

const switchTab = (tab: TabType) => {
  activeTab.value = tab
}

// Code search state
const codeSearch = useCodeSearch()
const codeQuery = ref('')
const selectedLanguage = ref<string>('')
const selectedChunkType = ref<string>('')
const languages = ['python', 'typescript', 'javascript', 'vue', 'markdown']
const chunkTypes = ['function', 'class', 'method', 'interface', 'type']

const handleCodeSearch = async () => {
  if (!codeQuery.value.trim()) {
    codeSearch.clear()
    return
  }
  const filters: any = {}
  if (selectedLanguage.value) filters.language = selectedLanguage.value
  if (selectedChunkType.value) filters.chunk_type = selectedChunkType.value

  await codeSearch.search(codeQuery.value, {
    lexical_weight: 0.5,
    vector_weight: 0.5,
    top_k: 50,
    enable_lexical: true,
    enable_vector: false,
    filters,
  })
}

const handleCodeClear = () => {
  codeQuery.value = ''
  selectedLanguage.value = ''
  selectedChunkType.value = ''
  codeSearch.clear()
}

// Memory search state
const memorySearch = useMemorySearch()
const memoryQuery = ref('')
const selectedMemoryType = ref<string>('')
const memoryTypes = [
  { value: '', label: 'Tous les types' },
  { value: 'investigation', label: 'Investigation' },
  { value: 'decision', label: 'Decision' },
  { value: 'note', label: 'Note' },
  { value: 'task', label: 'Task' },
  { value: 'reference', label: 'Reference' },
  { value: 'conversation', label: 'Conversation' },
]

const handleMemorySearch = async () => {
  if (!memoryQuery.value.trim()) {
    memorySearch.clear()
    return
  }
  await memorySearch.search(memoryQuery.value, {
    memoryType: selectedMemoryType.value || undefined,
    limit: 50,
  })
}

const handleMemoryClear = () => {
  memoryQuery.value = ''
  selectedMemoryType.value = ''
  memorySearch.clear()
}

const setInvestigationFilter = () => {
  selectedMemoryType.value = 'investigation'
  if (memoryQuery.value.trim()) {
    handleMemorySearch()
  }
}

// Copy feedback
const copyFeedback = ref<string | null>(null)
const showCopyFeedback = (message: string) => {
  copyFeedback.value = message
  setTimeout(() => {
    copyFeedback.value = null
  }, 2000)
}

const handleCopySingle = async (id: string) => {
  const success = await memorySearch.copySingleId(id)
  if (success) {
    showCopyFeedback('ID copie !')
  }
}

const handleCopySelected = async () => {
  const success = await memorySearch.copySelectedIds()
  if (success) {
    showCopyFeedback(`${memorySearch.selectedIds.value.size} IDs copies !`)
  }
}

// Helpers
const handleKeyPress = (event: KeyboardEvent, handler: () => void) => {
  if (event.key === 'Enter') handler()
}

const formatLineRange = (start: number, end: number) => {
  return start === end ? `L${start}` : `L${start}-${end}`
}

const truncateContent = (content: string, maxLength: number = 200) => {
  if (!content) return ''
  if (content.length <= maxLength) return content
  return content.slice(0, maxLength) + '...'
}

const getLineRange = (metadata: Record<string, any>) => {
  const startLine = metadata?.start_line
  const endLine = metadata?.end_line
  if (!startLine) return null
  return { start: startLine, end: endLine || startLine }
}

const getMemoryTypeIcon = (type: string) => {
  const icons: Record<string, string> = {
    investigation: '🔬',
    decision: '📋',
    note: '📝',
    task: '✅',
    reference: '📚',
    conversation: '💬',
  }
  return icons[type] || '📄'
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString('fr-FR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

const allSelected = computed(() => {
  if (memorySearch.results.value.length === 0) return false
  return memorySearch.results.value.every((r) => memorySearch.isSelected(r.id))
})

const toggleSelectAll = () => {
  if (allSelected.value) {
    memorySearch.deselectAll()
  } else {
    memorySearch.selectAll()
  }
}
</script>

<template>
  <div class="bg-slate-950">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <!-- Header -->
      <div class="mb-8 flex items-center gap-4">
        <span class="scada-led scada-led-cyan"></span>
        <div>
          <h1 class="text-3xl font-bold font-mono text-cyan-400 uppercase tracking-wider">Search</h1>
          <p class="mt-2 text-sm text-gray-400 font-mono uppercase tracking-wide">
            Code & Memories Hybrid Search
          </p>
        </div>
      </div>

      <!-- Tabs -->
      <div class="mb-6 border-b border-slate-700">
        <nav class="flex gap-4">
          <button
            @click="switchTab('code')"
            :class="[
              'px-4 py-2 font-mono text-sm uppercase tracking-wide border-b-2 transition-colors',
              activeTab === 'code'
                ? 'border-cyan-400 text-cyan-400'
                : 'border-transparent text-gray-400 hover:text-gray-300'
            ]"
          >
            Code
          </button>
          <button
            @click="switchTab('memories')"
            :class="[
              'px-4 py-2 font-mono text-sm uppercase tracking-wide border-b-2 transition-colors',
              activeTab === 'memories'
                ? 'border-cyan-400 text-cyan-400'
                : 'border-transparent text-gray-400 hover:text-gray-300'
            ]"
          >
            Memories
          </button>
        </nav>
      </div>

      <!-- Copy Feedback Toast -->
      <Transition name="fade">
        <div
          v-if="copyFeedback"
          class="fixed top-4 right-4 bg-emerald-600 text-white px-4 py-2 rounded shadow-lg z-50 font-mono text-sm"
        >
          {{ copyFeedback }}
        </div>
      </Transition>

      <!-- CODE TAB -->
      <div v-if="activeTab === 'code'">
        <!-- Search Bar -->
        <div class="section mb-6">
          <div class="space-y-4">
            <div>
              <label class="label">Search Query</label>
              <div class="flex gap-3">
                <input
                  v-model="codeQuery"
                  @keypress="handleKeyPress($event, handleCodeSearch)"
                  type="text"
                  class="input flex-1"
                  placeholder="Enter search query (e.g., 'async def', 'models.User')"
                />
                <button
                  @click="handleCodeSearch"
                  :disabled="codeSearch.loading.value || !codeQuery.trim()"
                  class="btn-primary"
                >
                  {{ codeSearch.loading.value ? 'Searching...' : 'Search' }}
                </button>
                <button @click="handleCodeClear" :disabled="codeSearch.loading.value" class="btn-ghost">
                  Clear
                </button>
              </div>
            </div>

            <!-- Filters -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label class="label">Language</label>
                <select v-model="selectedLanguage" class="input">
                  <option value="">All Languages</option>
                  <option v-for="lang in languages" :key="lang" :value="lang">{{ lang }}</option>
                </select>
              </div>
              <div>
                <label class="label">Chunk Type</label>
                <select v-model="selectedChunkType" class="input">
                  <option value="">All Types</option>
                  <option v-for="type in chunkTypes" :key="type" :value="type">{{ type }}</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        <!-- Code Results -->
        <div v-if="codeSearch.error.value" class="alert-error mb-4">
          {{ codeSearch.error.value }}
        </div>

        <div v-if="codeSearch.totalResults.value > 0" class="mb-4">
          <p class="text-sm text-gray-400">
            Found <span class="text-cyan-400 font-semibold">{{ codeSearch.totalResults.value }}</span> results
          </p>
        </div>

        <div v-if="codeSearch.loading.value" class="section">
          <div class="animate-pulse space-y-4">
            <div class="h-4 bg-slate-700 w-3/4"></div>
            <div class="h-4 bg-slate-700 w-1/2"></div>
            <div class="h-20 bg-slate-700"></div>
          </div>
        </div>

        <div v-else-if="codeSearch.totalResults.value > 0" class="space-y-4">
          <div
            v-for="result in codeSearch.results.value"
            :key="result.chunk_id"
            class="section hover:border-cyan-500/30 transition-colors"
          >
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center gap-2 flex-1 min-w-0">
                <span class="text-sm text-cyan-400 font-mono truncate">
                  {{ result.file_path || 'Unknown file' }}
                </span>
                <span v-if="getLineRange(result.metadata)" class="text-xs text-gray-500">
                  {{ formatLineRange(getLineRange(result.metadata)!.start, getLineRange(result.metadata)!.end) }}
                </span>
              </div>
              <div class="flex gap-2 flex-shrink-0">
                <span v-if="result.chunk_type" class="badge-info text-xs">{{ result.chunk_type }}</span>
                <span v-if="result.language" class="badge-info text-xs">{{ result.language }}</span>
              </div>
            </div>
            <div class="bg-slate-900 border border-slate-700 p-4 overflow-x-auto">
              <pre class="text-sm text-gray-300 font-mono whitespace-pre-wrap">{{ truncateContent(result.source_code, 400) }}</pre>
            </div>
          </div>
        </div>

        <div v-else-if="!codeSearch.loading.value && codeQuery" class="section text-center py-12">
          <h3 class="text-lg font-medium text-gray-300 uppercase">No Results Found</h3>
          <p class="mt-2 text-sm text-gray-500">Try adjusting your search query or filters</p>
        </div>

        <div v-else class="section text-center py-12">
          <h3 class="text-lg font-medium text-gray-300 uppercase">Search Code</h3>
          <p class="mt-2 text-sm text-gray-500">Enter a search query to find code across your repositories</p>
        </div>
      </div>

      <!-- MEMORIES TAB -->
      <div v-if="activeTab === 'memories'">
        <!-- Search Bar -->
        <div class="section mb-6">
          <div class="space-y-4">
            <div>
              <label class="label">Semantic Search</label>
              <div class="flex gap-3">
                <input
                  v-model="memoryQuery"
                  @keypress="handleKeyPress($event, handleMemorySearch)"
                  type="text"
                  class="input flex-1"
                  placeholder="Recherche semantique (ex: 'Duclos ObsDelphi', 'decision architecture')"
                />
                <button
                  @click="handleMemorySearch"
                  :disabled="memorySearch.loading.value || !memoryQuery.trim()"
                  class="btn-primary"
                >
                  {{ memorySearch.loading.value ? 'Searching...' : 'Search' }}
                </button>
                <button @click="handleMemoryClear" :disabled="memorySearch.loading.value" class="btn-ghost">
                  Clear
                </button>
              </div>
            </div>

            <!-- Filters -->
            <div class="flex items-center gap-4">
              <div class="flex-1 max-w-xs">
                <label class="label">Type</label>
                <select v-model="selectedMemoryType" class="input">
                  <option v-for="t in memoryTypes" :key="t.value" :value="t.value">{{ t.label }}</option>
                </select>
              </div>
              <div class="pt-6">
                <button
                  @click="setInvestigationFilter"
                  :class="[
                    'px-4 py-2 font-mono text-sm uppercase tracking-wide border rounded transition-colors',
                    selectedMemoryType === 'investigation'
                      ? 'bg-amber-600 border-amber-500 text-white'
                      : 'bg-transparent border-amber-600 text-amber-400 hover:bg-amber-600/20'
                  ]"
                >
                  Investigations
                </button>
              </div>
            </div>

            <!-- Selection Actions -->
            <div v-if="memorySearch.results.value.length > 0" class="flex items-center justify-between pt-2 border-t border-slate-700">
              <label class="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
                <input
                  type="checkbox"
                  :checked="allSelected"
                  @change="toggleSelectAll"
                  class="form-checkbox bg-slate-800 border-slate-600 text-cyan-500 rounded"
                />
                Tout selectionner ({{ memorySearch.results.value.length }})
              </label>
              <button
                v-if="memorySearch.selectedIds.value.size > 0"
                @click="handleCopySelected"
                class="btn-ghost text-emerald-400 hover:text-emerald-300"
              >
                Copier {{ memorySearch.selectedIds.value.size }} IDs
              </button>
            </div>
          </div>
        </div>

        <!-- Memory Results -->
        <div v-if="memorySearch.error.value" class="alert-error mb-4">
          {{ memorySearch.error.value }}
        </div>

        <div v-if="memorySearch.totalResults.value > 0" class="mb-4">
          <p class="text-sm text-gray-400">
            Found <span class="text-cyan-400 font-semibold">{{ memorySearch.totalResults.value }}</span> memories
          </p>
        </div>

        <div v-if="memorySearch.loading.value" class="section">
          <div class="animate-pulse space-y-4">
            <div class="h-4 bg-slate-700 w-3/4"></div>
            <div class="h-4 bg-slate-700 w-1/2"></div>
            <div class="h-20 bg-slate-700"></div>
          </div>
        </div>

        <div v-else-if="memorySearch.totalResults.value > 0" class="space-y-4">
          <div
            v-for="result in memorySearch.results.value"
            :key="result.id"
            :class="[
              'section transition-colors',
              memorySearch.isSelected(result.id) ? 'border-cyan-500/50 bg-cyan-950/20' : 'hover:border-cyan-500/30'
            ]"
          >
            <!-- Header -->
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center gap-3 flex-1 min-w-0">
                <input
                  type="checkbox"
                  :checked="memorySearch.isSelected(result.id)"
                  @change="memorySearch.toggleSelection(result.id)"
                  class="form-checkbox bg-slate-800 border-slate-600 text-cyan-500 rounded"
                />
                <span class="text-sm text-cyan-400 font-mono truncate font-semibold">
                  {{ result.title }}
                </span>
              </div>
              <button
                @click="handleCopySingle(result.id)"
                class="text-gray-500 hover:text-emerald-400 transition-colors p-1"
                title="Copier l'ID"
              >
                📋
              </button>
            </div>

            <!-- Metadata -->
            <div class="flex items-center gap-3 mb-2 text-xs text-gray-500">
              <span class="flex items-center gap-1">
                {{ getMemoryTypeIcon(result.memory_type) }}
                <span class="text-gray-400">{{ result.memory_type }}</span>
              </span>
              <span>|</span>
              <span>{{ formatDate(result.created_at) }}</span>
              <span>|</span>
              <span class="text-cyan-400">Score: {{ result.score.toFixed(3) }}</span>
            </div>

            <!-- Tags -->
            <div v-if="result.tags && result.tags.length > 0" class="mb-2">
              <span
                v-for="tag in result.tags"
                :key="tag"
                class="inline-block text-xs bg-slate-700 text-gray-300 px-2 py-0.5 rounded mr-1"
              >
                #{{ tag }}
              </span>
            </div>

            <!-- Content Preview -->
            <div class="bg-slate-900 border border-slate-700 p-3 rounded">
              <p class="text-sm text-gray-400 leading-relaxed">
                {{ truncateContent(result.content_preview, 200) }}
              </p>
            </div>
          </div>
        </div>

        <div v-else-if="!memorySearch.loading.value && memoryQuery" class="section text-center py-12">
          <h3 class="text-lg font-medium text-gray-300 uppercase">No Results Found</h3>
          <p class="mt-2 text-sm text-gray-500">Try adjusting your search query or type filter</p>
        </div>

        <div v-else class="section text-center py-12">
          <h3 class="text-lg font-medium text-gray-300 uppercase">Search Memories</h3>
          <p class="mt-2 text-sm text-gray-500">
            Recherche semantique dans vos notes, decisions, et investigations
          </p>
          <div class="mt-4 text-xs text-gray-600 max-w-md mx-auto">
            <p class="mb-2">Exemples de recherche :</p>
            <ul class="text-left space-y-1">
              <li>* <span class="text-cyan-400 font-mono">Duclos ObsDelphi</span> - Find investigation</li>
              <li>* <span class="text-cyan-400 font-mono">decision cache Redis</span> - Architecture decisions</li>
              <li>* <span class="text-cyan-400 font-mono">async patterns</span> - Coding patterns</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
