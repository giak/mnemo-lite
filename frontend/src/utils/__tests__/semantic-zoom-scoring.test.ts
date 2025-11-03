import { describe, it, expect } from 'vitest'
import { calculateNodeScore, filterNodesByScore } from '../semantic-zoom-scoring'
import type { GraphNode } from '@/composables/useCodeGraph'
import type { ViewMode } from '@/types/orgchart-types'

describe('semantic-zoom-scoring', () => {
  const createNode = (overrides: Partial<GraphNode> = {}): GraphNode => ({
    id: 'test-node',
    label: 'Test',
    type: 'Class',
    cyclomatic_complexity: 10,
    lines_of_code: 100,
    total_edges: 20,
    incoming_edges: 10,
    outgoing_edges: 10,
    depth: 1,
    descendants_count: 5,
    ...overrides
  })

  describe('calculateNodeScore', () => {
    it('calculates composite score with default weights', () => {
      const node = createNode({
        cyclomatic_complexity: 50,
        lines_of_code: 200,
        total_edges: 30
      })

      const score = calculateNodeScore(
        node,
        'complexity',
        { complexity: 0.4, loc: 0.3, connections: 0.3 }
      )

      // Normalized: complexity=50/100=0.5, loc=200/500=0.4, connections=30/100=0.3
      // Score = 0.5*0.4 + 0.4*0.3 + 0.3*0.3 = 0.2 + 0.12 + 0.09 = 0.41
      expect(score).toBeCloseTo(0.41, 2)
    })

    it('handles missing metrics gracefully', () => {
      const node = createNode({
        cyclomatic_complexity: undefined,
        lines_of_code: undefined,
        total_edges: 20
      })

      const score = calculateNodeScore(
        node,
        'complexity',
        { complexity: 0.5, loc: 0.25, connections: 0.25 }
      )

      // Only connections available: 20/100=0.2, weighted by 0.25
      expect(score).toBeGreaterThan(0)
      expect(score).toBeLessThan(1)
    })
  })

  describe('filterNodesByScore', () => {
    it('filters top 30% of nodes by score', () => {
      const nodes: GraphNode[] = [
        createNode({ id: '1', cyclomatic_complexity: 80, lines_of_code: 400 }), // High
        createNode({ id: '2', cyclomatic_complexity: 50, lines_of_code: 200 }), // Medium
        createNode({ id: '3', cyclomatic_complexity: 20, lines_of_code: 100 }), // Low
        createNode({ id: '4', cyclomatic_complexity: 5, lines_of_code: 50 }),   // Very Low
      ]

      const edges = [] // No edges = no ancestors added (flat filtering)

      const filtered = filterNodesByScore(
        nodes,
        edges,
        30,
        'complexity',
        { complexity: 0.5, loc: 0.5, connections: 0 }
      )

      // 30% of 4 nodes = ~1 node (rounded up to 2)
      expect(filtered.length).toBeGreaterThanOrEqual(1)
      expect(filtered.length).toBeLessThanOrEqual(2)
      expect(filtered[0].id).toBe('1') // Highest score
    })

    it('returns all nodes when zoomLevel is 100', () => {
      const nodes: GraphNode[] = [
        createNode({ id: '1' }),
        createNode({ id: '2' }),
        createNode({ id: '3' })
      ]

      const edges = []

      const filtered = filterNodesByScore(
        nodes,
        edges,
        100,
        'complexity',
        { complexity: 1, loc: 0, connections: 0 }
      )

      expect(filtered).toHaveLength(3)
    })

    it('includes ancestors to maintain tree paths', () => {
      // Tree: Module (root) -> Class (parent) -> Function (high score leaf)
      const nodes: GraphNode[] = [
        createNode({ id: 'module', type: 'Module', cyclomatic_complexity: 0, lines_of_code: 0 }),
        createNode({ id: 'class', type: 'Class', cyclomatic_complexity: 20, lines_of_code: 100 }),
        createNode({ id: 'func', type: 'Function', cyclomatic_complexity: 80, lines_of_code: 300 }),
      ]

      const edges = [
        { id: 'e1', source: 'module', target: 'class', type: 'imports' },
        { id: 'e2', source: 'class', target: 'func', type: 'contains' }
      ]

      // 33% zoom = 1 node (the Function with highest score)
      // But should also include Module and Class ancestors
      const filtered = filterNodesByScore(
        nodes,
        edges,
        33,
        'complexity',
        { complexity: 1, loc: 0, connections: 0 }
      )

      expect(filtered.length).toBe(3) // All 3 nodes (func + ancestors)
      expect(filtered.map(n => n.id)).toContain('module') // Ancestor included
      expect(filtered.map(n => n.id)).toContain('class')  // Ancestor included
      expect(filtered.map(n => n.id)).toContain('func')   // Original high-score node
    })
  })
})
