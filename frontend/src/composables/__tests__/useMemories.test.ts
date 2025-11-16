/**
 * Unit tests for useMemories composable - infinite scroll
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { useMemories } from '../useMemories'
import { nextTick } from 'vue'

// Mock fetch
global.fetch = vi.fn()

describe('useMemories infinite scroll', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('should load initial 20 memories', async () => {
    // Mock fetch to return 20 memories
    global.fetch = vi.fn((url: string) => {
      if (url.includes('/recent')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(Array(20).fill({ id: 'test' }))
        })
      }
      // Mock other endpoints
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({})
      })
    }) as any

    const { data, refresh } = useMemories({ refreshInterval: 0 })
    await refresh()
    await nextTick()

    expect(data.value.recentMemories.length).toBe(20)
  })

  it('should append more memories on loadMore', async () => {
    global.fetch = vi.fn((url: string) => {
      if (url.includes('/recent')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(Array(20).fill({ id: 'test' }))
        })
      }
      // Mock other endpoints
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({})
      })
    }) as any

    const { data, loadMore, refresh } = useMemories({ refreshInterval: 0 })
    await refresh()
    await nextTick()

    expect(data.value.recentMemories.length).toBe(20)

    await loadMore()
    await nextTick()

    expect(data.value.recentMemories.length).toBe(40)
  })

  it('should set hasMore to false when fewer than pageSize returned', async () => {
    global.fetch = vi.fn((url: string) => {
      if (url.includes('/recent')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(Array(5).fill({ id: 'test' }))  // Only 5 returned
        })
      }
      // Mock other endpoints
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({})
      })
    }) as any

    const { hasMore, refresh } = useMemories({ refreshInterval: 0 })
    await refresh()
    await nextTick()

    expect(hasMore.value).toBe(false)
  })
})
