<script setup lang="ts">
/**
 * EPIC-25 Story 25.4: Code Search Page
 * Simple code search interface with filters
 */

import { ref } from 'vue'
import { useCodeSearch } from '@/composables/useCodeSearch'

const { results, loading, error, totalResults, search, clear } = useCodeSearch()

// Search state
const query = ref('')
const selectedLanguage = ref<string>('')
const selectedChunkType = ref<string>('')

// Available filters
const languages = ['python', 'typescript', 'javascript', 'vue', 'markdown']
const chunkTypes = ['function', 'class', 'method', 'interface', 'type']

// Perform search
const handleSearch = async () => {
  if (!query.value.trim()) {
    clear()
    return
  }

  const filters: any = {}
  if (selectedLanguage.value) filters.language = selectedLanguage.value
  if (selectedChunkType.value) filters.chunk_type = selectedChunkType.value

  await search(query.value, {
    lexical_weight: 0.5,
    vector_weight: 0.5,
    top_k: 50,
    enable_lexical: true,
    enable_vector: false, // Disabled in mock mode
    filters,
  })
}

// Clear search
const handleClear = () => {
  query.value = ''
  selectedLanguage.value = ''
  selectedChunkType.value = ''
  clear()
}

// Handle Enter key
const handleKeyPress = (event: KeyboardEvent) => {
  if (event.key === 'Enter') {
    handleSearch()
  }
}

// Format line range
const formatLineRange = (start: number, end: number) => {
  return start === end ? `L${start}` : `L${start}-${end}`
}

// Truncate content for preview
const truncateContent = (content: string, maxLength: number = 200) => {
  if (!content) return ''
  if (content.length <= maxLength) return content
  return content.slice(0, maxLength) + '...'
}

// Get line range from metadata
const getLineRange = (metadata: Record<string, any>) => {
  const startLine = metadata?.start_line
  const endLine = metadata?.end_line
  if (!startLine) return null
  return { start: startLine, end: endLine || startLine }
}

// Get badge color for search type
const getSearchTypeBadge = (searchType: string) => {
  if (!searchType) return 'badge-info'
  if (searchType === 'hybrid') return 'badge-info'
  if (searchType === 'lexical') return 'badge-success'
  if (searchType === 'vector') return 'badge-warning'
  return 'badge-info'
}

// Get badge color for chunk type
const getChunkTypeBadge = (chunkType: string) => {
  if (!chunkType) return 'badge-info'
  if (chunkType === 'function' || chunkType === 'method') return 'badge-success'
  if (chunkType === 'class' || chunkType === 'interface') return 'badge-info'
  return 'badge-info'
}
</script>

<template>
  <div class="bg-slate-950">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <!-- Header avec LED SCADA -->
      <div class="mb-8 flex items-center gap-4">
        <span class="scada-led scada-led-cyan"></span>
        <div>
          <h1 class="text-3xl font-bold font-mono text-cyan-400 uppercase tracking-wider">Code Search</h1>
          <p class="mt-2 text-sm text-gray-400 font-mono uppercase tracking-wide">
            Hybrid Search: Lexical + Semantic
          </p>
        </div>
      </div>

      <!-- Search Bar -->
      <div class="section mb-6">
        <div class="space-y-4">
          <!-- Query Input -->
          <div>
            <label class="label">Search Query</label>
            <div class="flex gap-3">
              <input
                v-model="query"
                @keypress="handleKeyPress"
                type="text"
                class="input flex-1"
                placeholder="Enter search query (e.g., 'async def', 'models.User', 'authentication')"
              />
              <button
                @click="handleSearch"
                :disabled="loading || !query.trim()"
                class="btn-primary"
              >
                {{ loading ? 'Searching...' : 'Search' }}
              </button>
              <button
                @click="handleClear"
                :disabled="loading"
                class="btn-ghost"
              >
                Clear
              </button>
            </div>
          </div>

          <!-- Filters -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <!-- Language Filter -->
            <div>
              <label class="label">Language</label>
              <select v-model="selectedLanguage" class="input">
                <option value="">All Languages</option>
                <option v-for="lang in languages" :key="lang" :value="lang">
                  {{ lang }}
                </option>
              </select>
            </div>

            <!-- Chunk Type Filter -->
            <div>
              <label class="label">Chunk Type</label>
              <select v-model="selectedChunkType" class="input">
                <option value="">All Types</option>
                <option v-for="type in chunkTypes" :key="type" :value="type">
                  {{ type }}
                </option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <!-- Error Banner -->
      <div v-if="error" class="alert-error">
        <div class="flex items-start">
          <svg class="h-5 w-5 text-red-400 mt-0.5" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
          </svg>
          <div class="ml-3">
            <h3 class="text-sm font-medium text-red-300 uppercase">Search Error</h3>
            <p class="mt-1 text-sm text-red-400">{{ error }}</p>
          </div>
        </div>
      </div>

      <!-- Results Info -->
      <div v-if="totalResults > 0" class="mb-4">
        <p class="text-sm text-gray-400">
          Found <span class="text-cyan-400 font-semibold">{{ totalResults }}</span> results
        </p>
      </div>

      <!-- Loading State -->
      <div v-if="loading" class="section">
        <div class="animate-pulse space-y-4">
          <div class="h-4 bg-slate-700 w-3/4"></div>
          <div class="h-4 bg-slate-700 w-1/2"></div>
          <div class="h-20 bg-slate-700"></div>
        </div>
      </div>

      <!-- Results List -->
      <div v-else-if="totalResults > 0" class="space-y-4">
        <div
          v-for="result in results"
          :key="result.chunk_id"
          class="section hover:border-cyan-500/30 transition-colors"
        >
          <!-- File Path Header -->
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
              <span v-if="result.chunk_type" :class="['text-xs', getChunkTypeBadge(result.chunk_type)]">
                {{ result.chunk_type }}
              </span>
              <span v-if="result.language" class="badge-info text-xs">
                {{ result.language }}
              </span>
              <span v-if="result.lexical_score" class="text-xs badge-success">
                lexical
              </span>
            </div>
          </div>

          <!-- Name Path (if available) -->
          <div v-if="result.name_path" class="mb-2">
            <span class="text-xs text-gray-500">Path: </span>
            <span class="text-xs text-emerald-400 font-mono">
              {{ result.name_path }}
            </span>
          </div>

          <!-- Code Content -->
          <div class="bg-slate-900 border border-slate-700 p-4 overflow-x-auto">
            <pre class="text-sm text-gray-300 font-mono whitespace-pre-wrap">{{ truncateContent(result.source_code, 400) }}</pre>
          </div>

          <!-- Score -->
          <div v-if="result.rrf_score !== undefined && result.rrf_score !== null" class="mt-2 text-right">
            <span class="text-xs text-gray-500">
              RRF Score: <span class="text-cyan-400">{{ result.rrf_score.toFixed(4) }}</span>
            </span>
          </div>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else-if="!loading && query" class="section text-center py-12">
        <svg class="mx-auto h-12 w-12 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <h3 class="mt-4 text-lg font-medium text-gray-300 uppercase">No Results Found</h3>
        <p class="mt-2 text-sm text-gray-500">
          Try adjusting your search query or filters
        </p>
      </div>

      <!-- Initial State -->
      <div v-else class="section text-center py-12">
        <svg class="mx-auto h-12 w-12 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <h3 class="mt-4 text-lg font-medium text-gray-300 uppercase">Search Code</h3>
        <p class="mt-2 text-sm text-gray-500">
          Enter a search query to find code across your repositories
        </p>
        <div class="mt-4 text-xs text-gray-600 max-w-md mx-auto">
          <p class="mb-2">Search examples:</p>
          <ul class="text-left space-y-1">
            <li>• <span class="text-cyan-400 font-mono">async def</span> - Find async functions</li>
            <li>• <span class="text-cyan-400 font-mono">models.User</span> - Find User model references</li>
            <li>• <span class="text-cyan-400 font-mono">authentication</span> - Semantic search for auth code</li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>
