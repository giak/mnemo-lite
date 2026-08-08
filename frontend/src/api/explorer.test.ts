/**
 * Unit tests for the Explorer API client (EPIC-78).
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { getExplorerStats } from './explorer'

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
