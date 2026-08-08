/**
 * EPIC-78: Explorer API client
 * Endpoints du Knowledge Explorer : /api/v1/memories/explorer/*
 */
import { api } from '@/api/client'
import type {
  ExplorerStats,
  ExplorerTree,
  ExplorerTreeItem,
  MemoryDetail,
  RelatedResponse,
  SearchFilters,
  SearchResultItem
} from '@/types/explorer'

/** Agrégats du socle de connaissances (distribution, sujets, statuts, timeline) */
export async function getExplorerStats(): Promise<ExplorerStats> {
  const resp = await api('/memories/explorer/stats')
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/**
 * Arborescence d'un sujet (enquêtes / faits vérifiés / autres).
 * Match insensible à la casse côté backend.
 */
export async function getExplorerTree(subject: string): Promise<ExplorerTree> {
  const resp = await api(`/memories/explorer/tree?subject=${encodeURIComponent(subject)}`)
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/**
 * Mémoires liées par proxy de tags partagés (endpoint /related-by-tags).
 * Score = somme des tags communs pondérés (sujet = 2, technique = 1).
 */
export async function getRelatedByTags(
  memoryId: string,
  limit = 20,
  minShared = 1
): Promise<RelatedResponse> {
  const resp = await api(
    `/memories/${encodeURIComponent(memoryId)}/related-by-tags` +
      `?limit=${limit}&min_shared=${minShared}`
  )
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/**
 * Recherche de mémoire source par titre (POST /memories/search, sémantique).
 * Réutilisé par le sélecteur de l'onglet Relations.
 */
/** Détail complet d'une mémoire (contenu, tags, entités, concepts) */
export async function getMemoryDetail(id: string): Promise<MemoryDetail> {
  const resp = await api(`/memories/${encodeURIComponent(id)}`)
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

export async function searchSourceMemories(query: string): Promise<ExplorerTreeItem[]> {
  const resp = await api('/memories/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: query.trim(), limit: 8 })
  })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  const data = await resp.json()
  return (data.results || []).map((r: Record<string, any>) => ({
    id: r.id,
    title: r.title,
    memory_type: r.memory_type,
    tags: r.tags || [],
    created_at: r.created_at || null
  }))
}

/** Résultat de recherche avancée : items + total réel du backend */
export interface SearchResponse {
  results: SearchResultItem[]
  total: number
}

/**
 * Recherche avancée (onglet Recherche) : requête sémantique + filtres combinés
 * type / tags / statut / période. GET /memories/search (filtres en query params).
 * Retourne le total réel du backend (et non results.length, plafonné par limit).
 */
export async function searchMemories(filters: SearchFilters): Promise<SearchResponse> {
  const params = new URLSearchParams()
  const q = filters.query.trim()
  if (q) params.set('query', q)
  params.set('limit', String(filters.limit ?? 50))
  if (filters.memory_type) params.set('memory_type', filters.memory_type)
  if (filters.status) params.set('status', filters.status)
  if (filters.tags.length > 0) params.set('tags', filters.tags.join(','))
  if (filters.created_from) params.set('created_after', filters.created_from)
  if (filters.created_to) params.set('created_before', filters.created_to)

  const resp = await api(`/memories/search?${params.toString()}`)
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  const data = await resp.json()
  const results: SearchResultItem[] = (data.results || []).map((r: Record<string, any>) => ({
    id: r.id,
    title: r.title,
    memory_type: r.memory_type,
    tags: r.tags || [],
    created_at: r.created_at || null,
    score: typeof r.score === 'number' ? r.score : null
  }))
  return { results, total: typeof data.total === 'number' ? data.total : results.length }
}
