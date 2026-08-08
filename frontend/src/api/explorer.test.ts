/**
 * Unit tests for the Explorer API client (EPIC-78).
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { getExplorerStats, getExplorerTree, getRelatedByTags, searchSourceMemories, getMemoryDetail } from './explorer'

describe('getExplorerStats', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('should call the explorer stats endpoint and return parsed data', async () => {
    const payload = {
      by_type: { investigation: 4808, note: 865, quintessence: 94, article: 52 },
      status: { confirmed: 153, fact_checked: 18, total: 5957 },
      top_subjects: [{ tag: '14-juillet-2026', count: 318 }],
      timeline: [{ month: '2026-08', count: 42 }]
    }
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(payload) })
    ) as any

    const stats = await getExplorerStats()

    expect(global.fetch).toHaveBeenCalledTimes(1)
    // VITE_API_URL peut être renseigné (.env) : on vérifie le chemin, pas l'hôte
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/memories/explorer/stats')
    )
    expect(stats.status.confirmed).toBe(153)
    expect(stats.by_type.investigation).toBe(4808)
    expect(stats.top_subjects[0]!.tag).toBe('14-juillet-2026')
    expect(stats.timeline[0]!.month).toBe('2026-08')
  })

  it('should throw on non-OK response', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: false, status: 500 })
    ) as any

    await expect(getExplorerStats()).rejects.toThrow('HTTP 500')
  })
})

describe('getExplorerTree', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('should call the tree endpoint with the subject and return parsed data', async () => {
    const payload = {
      subject: '14-juillet-2026',
      total: 2,
      investigations: [{ id: 'a1', title: 'Enquete A', memory_type: 'investigation', tags: [], created_at: null }],
      facts: [{ id: 'b1', title: 'Fait B', memory_type: 'quintessence', tags: ['status:CONFIRME'], created_at: null }],
      others: []
    }
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(payload) })
    ) as any

    const tree = await getExplorerTree('14-juillet-2026')

    expect(global.fetch).toHaveBeenCalledTimes(1)
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/memories/explorer/tree?subject=14-juillet-2026')
    )
    expect(tree.total).toBe(2)
    expect(tree.investigations[0]!.title).toBe('Enquete A')
    expect(tree.facts[0]!.tags).toContain('status:CONFIRME')
  })

  it('should URL-encode special characters in the subject', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({ subject: 'a b', total: 0, investigations: [], facts: [], others: [] }) })
    ) as any

    await getExplorerTree('a b/c')

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('subject=a%20b%2Fc')
    )
  })

  it('should throw on non-OK response', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: false, status: 404 })
    ) as any

    await expect(getExplorerTree('nimporte-quoi')).rejects.toThrow('HTTP 404')
  })
})

describe('getRelatedByTags', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('should call related-by-tags with limit and min_shared and return parsed data', async () => {
    const payload = {
      memory_id: 'mid-1',
      total: 2,
      related: [
        { id: 'r1', title: 'ARCOM', memory_type: 'investigation', shared_tags: ['arcom'], score: 6 },
        { id: 'r2', title: 'SREN', memory_type: 'investigation', shared_tags: ['loi'], score: 4 }
      ]
    }
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(payload) })
    ) as any

    const resp = await getRelatedByTags('mid-1', 20, 2)

    expect(global.fetch).toHaveBeenCalledTimes(1)
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/memories/mid-1/related-by-tags?limit=20&min_shared=2')
    )
    expect(resp.total).toBe(2)
    expect(resp.related[0]!.score).toBe(6)
    expect(resp.related[1]!.shared_tags).toContain('loi')
  })

  it('should throw on non-OK response', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: false, status: 500 })
    ) as any

    await expect(getRelatedByTags('mid-1')).rejects.toThrow('HTTP 500')
  })
})

describe('searchSourceMemories', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('should POST to /memories/search and map results', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            total: 1,
            results: [
              {
                id: 'm1',
                title: 'Parrainages 2022',
                memory_type: 'investigation',
                tags: ['parrainages'],
                created_at: '2026-08-01',
                score: 0.9
              }
            ]
          })
      })
    ) as any

    const results = await searchSourceMemories('parrainages')

    const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]!
    expect(call[0]).toContain('/api/v1/memories/search')
    expect(call[1].method).toBe('POST')
    expect(JSON.parse(call[1].body)).toEqual({ query: 'parrainages', limit: 8 })
    expect(results).toHaveLength(1)
    expect(results[0]!.title).toBe('Parrainages 2022')
    expect(results[0]!.memory_type).toBe('investigation')
  })

  it('should throw on non-OK response', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: false, status: 500 })
    ) as any

    await expect(searchSourceMemories('x')).rejects.toThrow('HTTP 500')
  })
})

describe('getMemoryDetail', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('should fetch the memory detail and return parsed data', async () => {
    const payload = {
      id: 'm1',
      title: 'Parrainages 2022',
      content: '# Titre\n\nContenu.',
      memory_type: 'investigation',
      tags: ['fact-check', 'status:CONFIRME'],
      author: null,
      created_at: '2026-08-01',
      updated_at: null,
      project_id: null,
      entities: ['ARCOM'],
      concepts: ['parrainages'],
      has_embedding: true
    }
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(payload) })
    ) as any

    const detail = await getMemoryDetail('m1')

    expect(global.fetch).toHaveBeenCalledTimes(1)
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/memories/m1')
    )
    expect(detail.content).toContain('Contenu')
    expect(detail.tags).toContain('status:CONFIRME')
    expect(detail.entities).toContain('ARCOM')
    expect(detail.concepts).toContain('parrainages')
    expect(detail.has_embedding).toBe(true)
  })

  it('should throw on non-OK response', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: false, status: 404 })
    ) as any

    await expect(getMemoryDetail('missing')).rejects.toThrow('HTTP 404')
  })
})
