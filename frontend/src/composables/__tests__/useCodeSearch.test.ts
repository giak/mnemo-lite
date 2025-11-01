/**
 * Unit tests for useCodeSearch composable
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useCodeSearch } from '../useCodeSearch'
import { nextTick } from 'vue'

// Mock fetch
global.fetch = vi.fn()

describe('useCodeSearch', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should initialize with empty state', () => {
    const { results, loading, error, totalResults } = useCodeSearch()

    expect(results.value).toEqual([])
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
    expect(totalResults.value).toBe(0)
  })

  it('should perform successful search', async () => {
    const mockResults = [
      {
        chunk_id: '1',
        content: 'async def fetch_data():',
        file_path: 'api/services/data.py',
        language: 'python',
        chunk_type: 'function',
        name_path: ['fetch_data'],
        line_start: 10,
        line_end: 20,
        score: 0.95,
        search_type: 'hybrid',
      },
    ]

    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ results: mockResults }),
      })
    ) as any

    const { results, loading, error, search } = useCodeSearch()

    expect(loading.value).toBe(false)

    await search('async def')
    await nextTick()

    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
    expect(results.value).toEqual(mockResults)
  })

  it('should handle search with filters', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ results: [] }),
      })
    ) as any

    const { search } = useCodeSearch()

    await search('test query', {
      filters: {
        language: 'python',
        chunk_type: 'function',
      },
    })
    await nextTick()

    const callBody = JSON.parse((global.fetch as any).mock.calls[0][1].body)
    expect(callBody).toMatchObject({
      query: 'test query',
      filters: {
        language: 'python',
        chunk_type: 'function',
      },
    })
  })

  it('should clear results when searching with empty query', async () => {
    const { results, error, search } = useCodeSearch()

    results.value = [
      {
        chunk_id: '1',
        content: 'test',
        file_path: 'test.py',
        language: 'python',
        chunk_type: 'function',
        line_start: 1,
        line_end: 2,
        score: 1.0,
        search_type: 'hybrid',
      },
    ]

    await search('')
    await nextTick()

    expect(results.value).toEqual([])
    expect(error.value).toBeNull()
    expect(global.fetch).not.toHaveBeenCalled()
  })

  it('should handle HTTP errors', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
      })
    ) as any

    const { results, error, search } = useCodeSearch()

    await search('test query')
    await nextTick()

    expect(error.value).toContain('500')
    expect(error.value).toContain('Internal Server Error')
    expect(results.value).toEqual([])
  })

  it('should handle network errors', async () => {
    global.fetch = vi.fn(() => Promise.reject(new Error('Network failure'))) as any

    const { results, error, search } = useCodeSearch()

    await search('test query')
    await nextTick()

    expect(error.value).toContain('Network failure')
    expect(results.value).toEqual([])
  })

  it('should clear all state', () => {
    const { results, error, loading, clear } = useCodeSearch()

    results.value = [
      {
        chunk_id: '1',
        content: 'test',
        file_path: 'test.py',
        language: 'python',
        chunk_type: 'function',
        line_start: 1,
        line_end: 2,
        score: 1.0,
        search_type: 'hybrid',
      },
    ]
    error.value = 'Some error'
    loading.value = true

    clear()

    expect(results.value).toEqual([])
    expect(error.value).toBeNull()
    expect(loading.value).toBe(false)
  })

  it('should calculate totalResults correctly', () => {
    const { results, totalResults } = useCodeSearch()

    expect(totalResults.value).toBe(0)

    results.value = [
      {
        chunk_id: '1',
        content: 'test',
        file_path: 'test.py',
        language: 'python',
        chunk_type: 'function',
        line_start: 1,
        line_end: 2,
        score: 1.0,
        search_type: 'hybrid',
      },
      {
        chunk_id: '2',
        content: 'test2',
        file_path: 'test2.py',
        language: 'python',
        chunk_type: 'class',
        line_start: 1,
        line_end: 2,
        score: 0.9,
        search_type: 'vector',
      },
    ]

    expect(totalResults.value).toBe(2)
  })
})
