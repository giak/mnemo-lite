/**
 * Expanse Memory Composable
 * Fetches Expanse-specific cognitive state from MnemoLite API
 */

import { ref, onMounted, onUnmounted } from 'vue'

const API = 'http://localhost:8001/api/v1'

export interface ExpanseTag {
  tag: string
  label: string
  group: string
  decay: number
  halfLife: string
  count: number
  memories: any[]
}

export interface ExpanseMemoryData {
  // Stats
  totalMemories: number
  totalChunks: number
  totalNodes: number

  // Taxonomie (11 tags)
  tags: ExpanseTag[]

  // Cycle de vie
  lifecycle: {
    sealed: number
    candidate: number
    doubt: number
    consolidated: number
    consumed: number
  }

  // Santé
  health: {
    drifts: number
    traces: number
    consolidationNeeded: boolean
    decayPresets: number
  }

  // Memories par tag sélectionné
  filteredMemories: any[]
}

const EXPANSE_TAGS: { tag: string; label: string; group: string; decay: number; halfLife: string }[] = [
  { tag: 'sys:core', label: 'Axiomes', group: 'PERMANENT', decay: 0, halfLife: '∞' },
  { tag: 'sys:anchor', label: 'Scellements', group: 'PERMANENT', decay: 0, halfLife: '∞' },
  { tag: 'sys:pattern', label: 'Patterns', group: 'LONG TERME', decay: 0.005, halfLife: '140j' },
  { tag: 'sys:protocol', label: 'Protocols', group: 'LONG TERME', decay: 0.002, halfLife: '1an' },
  { tag: 'sys:extension', label: 'Extensions', group: 'MOYEN TERME', decay: 0.01, halfLife: '70j' },
  { tag: 'sys:history', label: 'Historique', group: 'COURT TERME', decay: 0.05, halfLife: '14j' },
  { tag: 'sys:drift', label: 'Dérives', group: 'COURT TERME', decay: 0.02, halfLife: '35j' },
  { tag: 'sys:trace', label: 'Traces', group: 'COURT TERME', decay: 0.08, halfLife: '9j' },
  { tag: 'trace:fresh', label: 'Frictions', group: 'COURT TERME', decay: 0.1, halfLife: '7j' },
  { tag: 'sys:user:profile', label: 'Profil', group: 'LONG TERME', decay: 0.005, halfLife: '140j' },
  { tag: 'sys:project', label: 'Projet', group: 'MOYEN TERME', decay: 0.01, halfLife: '70j' },
]

export function useExpanseMemory(options: { refreshInterval?: number } = {}) {
  const { refreshInterval = 30000 } = options

  const data = ref<ExpanseMemoryData>({
    totalMemories: 0,
    totalChunks: 0,
    totalNodes: 0,
    tags: [],
    lifecycle: { sealed: 0, candidate: 0, doubt: 0, consolidated: 0, consumed: 0 },
    health: { drifts: 0, traces: 0, consolidationNeeded: false, decayPresets: 0 },
    filteredMemories: []
  })

  const loading = ref(false)
  const error = ref<string | null>(null)
  const lastUpdated = ref<Date | null>(null)
  const selectedTag = ref<string | null>(null)

  let intervalId: number | null = null

  async function safeFetch(url: string): Promise<any> {
    try {
      const resp = await fetch(url)
      if (!resp.ok) return null
      return await resp.json()
    } catch { return null }
  }

  async function safePost(url: string, body: any): Promise<any> {
    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      })
      if (!resp.ok) return null
      return await resp.json()
    } catch { return null }
  }

  async function fetchAll(): Promise<void> {
    loading.value = true
    error.value = null

    // Fetch stats + all tag searches IN PARALLEL
    const searchPromises = EXPANSE_TAGS.map(t =>
      safePost(`${API}/memories/search`, { query: t.tag, tags: [t.tag], limit: 20 })
    )

    const [statsResult, chunksResult, ...tagResults] = await Promise.all([
      safeFetch(`${API}/memories/stats`),
      safeFetch(`${API}/memories/code-chunks/recent?limit=10`),
      ...searchPromises
    ])

    // Merge all tag results, deduplicate by id
    const allMemories: any[] = []
    const seen = new Set<string>()
    for (const result of tagResults) {
      for (const m of (result?.results || [])) {
        if (!seen.has(m.id)) {
          seen.add(m.id)
          allMemories.push(m)
        }
      }
    }

    // Build tag data
    const tags: ExpanseTag[] = EXPANSE_TAGS.map(t => ({
      ...t,
      count: allMemories.filter(m => (m.tags || []).some((tag: string) => tag.toLowerCase() === t.tag.toLowerCase())).length,
      memories: allMemories.filter(m => (m.tags || []).some((tag: string) => tag.toLowerCase() === t.tag.toLowerCase()))
    }))

    // Lifecycle counts
    const sealed = tags.find(t => t.tag === 'sys:pattern')?.memories.filter(m => (m.tags || []).includes('sys:anchor')).length || 0
    const candidate = allMemories.filter(m => (m.tags || []).some((t: string) => t.includes('candidate'))).length
    const doubt = allMemories.filter(m => (m.tags || []).some((t: string) => t.includes('doubt'))).length

    // Health
    const drifts = tags.find(t => t.tag === 'sys:drift')?.count || 0
    const traces = tags.find(t => t.tag === 'trace:fresh')?.count || 0
    const history = tags.find(t => t.tag === 'sys:history')?.count || 0

    data.value = {
      totalMemories: statsResult?.total || allMemories.length,
      totalChunks: statsResult?.total_chunks || 0,
      totalNodes: 0,
      tags,
      lifecycle: {
        sealed: tags.find(t => t.tag === 'sys:pattern')?.count || 0,
        candidate,
        doubt,
        consolidated: 0,
        consumed: 0
      },
      health: {
        drifts,
        traces,
        consolidationNeeded: history > 20,
        decayPresets: 7
      },
      filteredMemories: []
    }

    loading.value = false
    lastUpdated.value = new Date()
  }

  async function fetchByTag(tag: string): Promise<void> {
    selectedTag.value = tag
    const result = await safePost(`${API}/memories/search`, { query: tag, tags: [tag], limit: 30 })
    data.value.filteredMemories = result?.results || []
  }

  onMounted(() => {
    fetchAll()
    intervalId = window.setInterval(fetchAll, refreshInterval)
  })

  onUnmounted(() => {
    if (intervalId !== null) {
      clearInterval(intervalId)
      intervalId = null
    }
  })

  return { data, loading, error, lastUpdated, refresh: fetchAll, selectedTag, fetchByTag }
}
