/**
 * EPIC-25 Story 25.4: Code Search Composable
 * 
 * Composable for searching code using the hybrid search API.
 * Combines lexical (pg_trgm) and semantic (HNSW) search with RRF fusion.
 */

import { ref, computed } from 'vue'

export interface SearchResult {
  chunk_id: string
  source_code: string
  file_path: string
  language: string
  chunk_type: string
  name: string
  name_path?: string | null
  rrf_score: number
  rank: number
  metadata: Record<string, any>
  lexical_score?: number | null
  vector_similarity?: number | null
  vector_distance?: number | null
  contribution: Record<string, number>
  related_nodes: string[]
}

interface SearchFilters {
  language?: string
  chunk_type?: string
  repository?: string
  file_path?: string
}

interface SearchOptions {
  lexical_weight?: number
  vector_weight?: number
  top_k?: number
  enable_lexical?: boolean
  enable_vector?: boolean
  filters?: SearchFilters
}

interface UseCodeSearchReturn {
  results: ReturnType<typeof ref<SearchResult[]>>
  loading: ReturnType<typeof ref<boolean>>
  error: ReturnType<typeof ref<string | null>>
  totalResults: ReturnType<typeof computed<number>>
  search: (query: string, options?: SearchOptions) => Promise<void>
  clear: () => void
}

export function useCodeSearch(): UseCodeSearchReturn {
  const results = ref<SearchResult[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const totalResults = computed(() => results.value.length)

  const search = async (query: string, options: SearchOptions = {}) => {
    if (!query.trim()) {
      results.value = []
      error.value = null
      return
    }

    loading.value = true
    error.value = null

    try {
      const requestBody = {
        query: query.trim(),
        lexical_weight: options.lexical_weight ?? 0.5,
        vector_weight: options.vector_weight ?? 0.5,
        top_k: options.top_k ?? 50,
        enable_lexical: options.enable_lexical ?? true,
        enable_vector: options.enable_vector ?? false, // Disabled in mock mode
        filters: options.filters ?? {}
      }

      const response = await fetch('http://localhost:8001/v1/code/search/hybrid', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      })

      if (!response.ok) {
        throw new Error(`Search failed: ${response.status} ${response.statusText}`)
      }

      const data = await response.json()
      results.value = data.results || []
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred'
      error.value = errorMessage
      console.error('Code search error:', err)
      results.value = []
    } finally {
      loading.value = false
    }
  }

  const clear = () => {
    results.value = []
    error.value = null
    loading.value = false
  }

  return {
    results,
    loading,
    error,
    totalResults,
    search,
    clear,
  }
}
