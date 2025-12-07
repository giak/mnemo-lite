/**
 * Unit tests for useMemorySearch composable
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useMemorySearch } from '../useMemorySearch'
import { nextTick } from 'vue'

// Mock fetch
global.fetch = vi.fn()

describe('useMemorySearch', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should initialize with empty state', () => {
    const { results, loading, error, totalResults, selectedIds } = useMemorySearch()

    expect(results.value).toEqual([])
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
    expect(totalResults.value).toBe(0)
    expect(selectedIds.value.size).toBe(0)
  })

  it('should perform successful search', async () => {
    const mockResults = [
      {
        id: '550e8400-e29b-41d4-a716-446655440001',
        title: 'Investigation Duclos',
        content_preview: 'Enquête sur les liens...',
        memory_type: 'investigation',
        tags: ['politique'],
        author: 'Claude',
        created_at: '2024-12-05T14:30:00Z',
        score: 0.89,
      },
    ]

    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          results: mockResults,
          total: 1,
          query: 'Duclos',
          search_time_ms: 45,
        }),
      })
    ) as any

    const { results, loading, error, search } = useMemorySearch()

    await search('Duclos')
    await nextTick()

    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
    expect(results.value).toEqual(mockResults)
  })

  it('should search with memory_type filter', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ results: [], total: 0 }),
      })
    ) as any

    const { search } = useMemorySearch()

    await search('test', { memoryType: 'investigation' })
    await nextTick()

    const callBody = JSON.parse((global.fetch as any).mock.calls[0][1].body)
    expect(callBody.memory_type).toBe('investigation')
  })

  it('should toggle selection', () => {
    const { selectedIds, toggleSelection, isSelected } = useMemorySearch()

    expect(isSelected('id-1')).toBe(false)

    toggleSelection('id-1')
    expect(isSelected('id-1')).toBe(true)
    expect(selectedIds.value.size).toBe(1)

    toggleSelection('id-1')
    expect(isSelected('id-1')).toBe(false)
    expect(selectedIds.value.size).toBe(0)
  })

  it('should select all visible results', async () => {
    const mockResults = [
      { id: 'id-1', title: 'A', content_preview: '', memory_type: 'note', tags: [], score: 0.9, created_at: '' },
      { id: 'id-2', title: 'B', content_preview: '', memory_type: 'note', tags: [], score: 0.8, created_at: '' },
    ]

    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ results: mockResults, total: 2 }),
      })
    ) as any

    const { results, selectedIds, selectAll, search } = useMemorySearch()

    await search('test')
    await nextTick()

    selectAll()

    expect(selectedIds.value.size).toBe(2)
    expect(selectedIds.value.has('id-1')).toBe(true)
    expect(selectedIds.value.has('id-2')).toBe(true)
  })

  it('should copy selected IDs as newline-separated string', () => {
    const { selectedIds, copySelectedIds } = useMemorySearch()

    selectedIds.value.add('id-1')
    selectedIds.value.add('id-2')

    // Mock clipboard
    const writeTextMock = vi.fn(() => Promise.resolve())
    Object.assign(navigator, {
      clipboard: { writeText: writeTextMock },
    })

    copySelectedIds()

    expect(writeTextMock).toHaveBeenCalledWith('id-1\nid-2')
  })

  it('should clear all state', () => {
    const { results, error, loading, selectedIds, clear } = useMemorySearch()

    results.value = [{ id: '1', title: 'T', content_preview: '', memory_type: 'note', tags: [], score: 0.9, created_at: '' }]
    error.value = 'Some error'
    loading.value = true
    selectedIds.value.add('1')

    clear()

    expect(results.value).toEqual([])
    expect(error.value).toBeNull()
    expect(loading.value).toBe(false)
    expect(selectedIds.value.size).toBe(0)
  })
})
