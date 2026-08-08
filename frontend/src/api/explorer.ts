/**
 * EPIC-78: Explorer API client
 * Endpoints du Knowledge Explorer : /api/v1/memories/explorer/*
 */
import { api } from '@/api/client'
import type { ExplorerStats, ExplorerTree, ExplorerTreeItem, RelatedResponse } from '@/types/explorer'

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
