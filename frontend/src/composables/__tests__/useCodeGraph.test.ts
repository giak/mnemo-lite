/**
 * Unit tests for useCodeGraph composable
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useCodeGraph } from '../useCodeGraph'
import { nextTick } from 'vue'

// Mock fetch
global.fetch = vi.fn()

describe('useCodeGraph', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should initialize with default values', () => {
    const { stats, loading, error } = useCodeGraph()

    expect(stats.value).toBeNull()
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it('should fetch graph stats successfully', async () => {
    const mockStats = {
      repository: 'MnemoLite',
      total_nodes: 74,
      total_edges: 0,
      nodes_by_type: { class: 14, function: 60 },
      edges_by_type: {},
    }

    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockStats),
      })
    ) as any

    const { stats, loading, error, fetchStats } = useCodeGraph()

    expect(loading.value).toBe(false)

    await fetchStats('MnemoLite')
    await nextTick()

    expect(loading.value).toBe(false)
    expect(stats.value).toEqual(mockStats)
    expect(error.value).toBeNull()
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8001/v1/code/graph/stats/MnemoLite'
    )
  })

  it('should handle HTTP errors', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 404,
        statusText: 'Not Found',
      })
    ) as any

    const { stats, loading, error, fetchStats } = useCodeGraph()

    await fetchStats('NonExistentRepo')
    await nextTick()

    expect(loading.value).toBe(false)
    expect(stats.value).toBeNull()
    expect(error.value).toContain('404')
    expect(error.value).toContain('Not Found')
  })

  it('should handle network errors', async () => {
    global.fetch = vi.fn(() => Promise.reject(new Error('Network failure'))) as any

    const { stats, loading, error, fetchStats } = useCodeGraph()

    await fetchStats('MnemoLite')
    await nextTick()

    expect(loading.value).toBe(false)
    expect(stats.value).toBeNull()
    expect(error.value).toBe('Network failure')
  })

  it('should set loading state correctly during fetch', async () => {
    let resolveFetch: any
    const fetchPromise = new Promise((resolve) => {
      resolveFetch = resolve
    })

    global.fetch = vi.fn(() => fetchPromise) as any

    const { loading, fetchStats } = useCodeGraph()

    expect(loading.value).toBe(false)

    const fetchPromiseResult = fetchStats('MnemoLite')

    // Check loading state is true during fetch
    expect(loading.value).toBe(true)

    // Resolve the fetch
    resolveFetch({
      ok: true,
      json: () =>
        Promise.resolve({
          repository: 'MnemoLite',
          total_nodes: 10,
          total_edges: 5,
          nodes_by_type: {},
          edges_by_type: {},
        }),
    })

    await fetchPromiseResult
    await nextTick()

    // Check loading state is false after fetch
    expect(loading.value).toBe(false)
  })

  it('should use default repository parameter', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            repository: 'MnemoLite',
            total_nodes: 0,
            total_edges: 0,
            nodes_by_type: {},
            edges_by_type: {},
          }),
      })
    ) as any

    const { fetchStats } = useCodeGraph()

    // Call without parameter, should default to 'MnemoLite'
    await fetchStats()
    await nextTick()

    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8001/v1/code/graph/stats/MnemoLite'
    )
  })
})
