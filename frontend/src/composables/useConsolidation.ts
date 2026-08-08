import { ref } from 'vue'
import type { ConsolidationGroup, ConsolidateResponse } from '../types/memory-graph'
import { API } from '../config/api'

export function useConsolidation() {
  const suggestions = ref<ConsolidationGroup[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchSuggestions(params: Record<string, any> = {}) {
    loading.value = true
    error.value = null
    try {
      const query = new URLSearchParams(params).toString()
      const res = await fetch(`${API}/memories/consolidation/suggestions?${query}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      suggestions.value = data.groups
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function consolidate(group: ConsolidationGroup, summary: string): Promise<ConsolidateResponse> {
    const res = await fetch(`${API}/memories/consolidate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: group.suggested_title,
        summary,
        source_ids: group.source_ids,
        tags: group.suggested_tags,
      }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  }

  return { suggestions, loading, error, fetchSuggestions, consolidate }
}
