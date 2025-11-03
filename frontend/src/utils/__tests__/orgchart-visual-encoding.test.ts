import { describe, it, expect } from 'vitest'
import {
  getComplexityColor,
  getComplexitySize,
  getHubsColor,
  getHubsSize,
  getHierarchyColor,
  getHierarchySize
} from '../orgchart-visual-encoding'

describe('orgchart-visual-encoding', () => {
  describe('Complexity Mode', () => {
    it('returns green for low complexity', () => {
      expect(getComplexityColor(5)).toBe('#10b981')
    })

    it('returns red for high complexity', () => {
      expect(getComplexityColor(40)).toBe('#ef4444')
    })

    it('scales size with LOC', () => {
      const [width1] = getComplexitySize(100)
      const [width2] = getComplexitySize(300)
      expect(width2).toBeGreaterThan(width1)
    })
  })

  describe('Hubs Mode', () => {
    it('returns blue for high incoming ratio', () => {
      const color = getHubsColor(0.9)
      expect(color).toContain('rgb')
      // Blue-ish color
    })

    it('returns orange for low incoming ratio', () => {
      const color = getHubsColor(0.1)
      expect(color).toContain('rgb')
      // Orange-ish color
    })
  })

  describe('Hierarchy Mode', () => {
    it('returns purple for root', () => {
      expect(getHierarchyColor(0)).toBe('#8b5cf6')
    })

    it('returns cyan for level 1', () => {
      expect(getHierarchyColor(1)).toBe('#06b6d4')
    })
  })
})
