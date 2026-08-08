/**
 * EPIC-78: Explorer API client
 * Endpoints du Knowledge Explorer : /api/v1/memories/explorer/*
 */
import { api } from '@/api/client'
import type { ExplorerStats } from '@/types/explorer'

/** Agrégats du socle de connaissances (distribution, sujets, statuts, timeline) */
export async function getExplorerStats(): Promise<ExplorerStats> {
  const resp = await api('/memories/explorer/stats')
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}
