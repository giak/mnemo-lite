/**
 * Unit tests for useDashboard composable
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { useDashboard } from '../useDashboard'
import { nextTick } from 'vue'

// Mock fetch
global.fetch = vi.fn()

describe('useDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('should initialize with default values', () => {
    const { data, loading, errors, lastUpdated } = useDashboard({ refreshInterval: 0 })

    expect(data.value).toEqual({
      health: null,
      textEmbeddings: null,
      codeEmbeddings: null,
    })
    expect(loading.value).toBe(false)
    expect(errors.value).toEqual([])
    expect(lastUpdated.value).toBeNull()
  })

  it('should fetch dashboard data successfully', async () => {
    const mockHealthData = {
      status: 'healthy',
      services: { api: true, database: true, redis: true },
    }
    const mockTextData = {
      model: 'all-MiniLM-L6-v2',
      dimension: 384,
      count: 1000,
      lastIndexed: '2025-11-01T00:00:00Z',
    }
    const mockCodeData = {
      model: 'microsoft/codebert-base',
      dimension: 768,
      count: 500,
      lastIndexed: '2025-11-01T00:00:00Z',
    }

    global.fetch = vi.fn((url: string) => {
      if (url.includes('/health')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockHealthData),
        })
      }
      if (url.includes('/embeddings/text')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockTextData),
        })
      }
      if (url.includes('/embeddings/code')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockCodeData),
        })
      }
      return Promise.reject(new Error('Unknown endpoint'))
    }) as any

    const { data, loading, errors, refresh } = useDashboard({ refreshInterval: 0 })

    expect(loading.value).toBe(false)

    await refresh()
    await nextTick()

    expect(loading.value).toBe(false)
    expect(data.value.health).toEqual(mockHealthData)
    expect(data.value.textEmbeddings).toEqual(mockTextData)
    expect(data.value.codeEmbeddings).toEqual(mockCodeData)
    expect(errors.value).toEqual([])
  })

  it('should handle fetch errors', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
      })
    ) as any

    const { data, errors, refresh } = useDashboard({ refreshInterval: 0 })

    await refresh()
    await nextTick()

    expect(errors.value.length).toBeGreaterThan(0)
    expect(errors.value[0].endpoint).toBeTruthy()
    expect(errors.value[0].message).toContain('500')
    expect(data.value.health).toBeNull()
  })

  it('should handle network errors', async () => {
    global.fetch = vi.fn(() => Promise.reject(new Error('Network error'))) as any

    const { errors, refresh } = useDashboard({ refreshInterval: 0 })

    await refresh()
    await nextTick()

    expect(errors.value.length).toBeGreaterThan(0)
    expect(errors.value[0].message).toContain('Network error')
  })

  it('should update lastUpdated timestamp after refresh', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ status: 'healthy' }),
      })
    ) as any

    const { lastUpdated, refresh } = useDashboard({ refreshInterval: 0 })

    expect(lastUpdated.value).toBeNull()

    await refresh()
    await nextTick()

    expect(lastUpdated.value).toBeInstanceOf(Date)
    expect(lastUpdated.value!.getTime()).toBeLessThanOrEqual(Date.now())
  })
})
