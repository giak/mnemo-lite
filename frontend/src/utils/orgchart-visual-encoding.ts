import type { ViewMode } from '@/types/orgchart-types'
import type { GraphNode } from '@/composables/useCodeGraph'

export interface NodeVisualStyle {
  fill: string
  size: [number, number]
}

export interface OrgChartNode {
  data: GraphNode
}

// Complexity Mode: Green → Yellow → Orange → Red based on cyclomatic complexity
export function getComplexityColor(complexity: number = 0): string {
  if (complexity <= 10) return '#10b981'  // Green
  if (complexity <= 20) return '#fbbf24'  // Yellow
  if (complexity <= 30) return '#f97316'  // Orange
  return '#ef4444'  // Red
}

// Complexity Mode: Size based on LOC (min 100, max 400)
export function getComplexitySize(loc: number = 0): [number, number] {
  const clampedLoc = Math.max(50, Math.min(loc, 500))
  const width = 100 + (clampedLoc / 500) * 150  // 100-250px
  const height = 30 + (clampedLoc / 500) * 30   // 30-60px
  return [width, height]
}

// Hubs Mode: Blue (many incoming) → Violet (balanced) → Orange (many outgoing)
export function getHubsColor(incomingRatio: number = 0.5): string {
  // incomingRatio = incoming / total (0 to 1)
  // 0.0-0.3: Orange (depends on others)
  // 0.3-0.7: Violet (balanced)
  // 0.7-1.0: Blue (depended upon)

  if (incomingRatio >= 0.7) {
    // Blue gradient
    const intensity = (incomingRatio - 0.7) / 0.3
    return `rgb(${59 - intensity * 30}, ${130 + intensity * 10}, ${246})`
  } else if (incomingRatio >= 0.3) {
    // Violet
    return '#8b5cf6'
  } else {
    // Orange gradient
    const intensity = (0.3 - incomingRatio) / 0.3
    return `rgb(${249}, ${151 - intensity * 50}, ${22 + intensity * 30})`
  }
}

// Hubs Mode: Size based on total connections (min 80, max 300)
export function getHubsSize(totalConnections: number = 0): [number, number] {
  const clampedTotal = Math.max(1, Math.min(totalConnections, 200))
  const width = 80 + (clampedTotal / 200) * 220  // 80-300px
  const height = 30 + (clampedTotal / 200) * 50  // 30-80px
  return [width, height]
}

// Hierarchy Mode: Color gradient based on depth (lighter at top, darker at bottom)
export function getHierarchyColor(depth: number = 0): string {
  if (depth === 0) return '#8b5cf6'  // Root: Purple
  if (depth === 1) return '#06b6d4'  // Level 1 (Modules): Cyan

  // Levels 2+: Blue gradient getting darker
  // Level 2: #3b82f6 (lighter blue)
  // Level 3: #2563eb (medium blue)
  // Level 4+: #1e40af (darker blue)
  const blueLevels = ['#3b82f6', '#2563eb', '#1e40af', '#1e3a8a']
  const index = Math.max(0, Math.min(depth - 2, blueLevels.length - 1))
  return blueLevels[index]!
}

// Hierarchy Mode: Size based on descendants count (min 100, max 250)
export function getHierarchySize(descendantsCount: number = 0): [number, number] {
  const clampedCount = Math.max(0, Math.min(descendantsCount, 100))
  const width = 100 + (clampedCount / 100) * 150  // 100-250px
  const height = 30 + (clampedCount / 100) * 30   // 30-60px
  return [width, height]
}

// Main function: Calculate visual style based on view mode
export function calculateNodeStyle(
  node: OrgChartNode,
  viewMode: ViewMode
): NodeVisualStyle {
  switch (viewMode) {
    case 'complexity':
      return {
        fill: getComplexityColor(node.data.cyclomatic_complexity),
        size: getComplexitySize(node.data.lines_of_code)
      }

    case 'hubs':
      const totalEdges = node.data.total_edges || 1
      const incomingRatio = (node.data.incoming_edges || 0) / totalEdges
      return {
        fill: getHubsColor(incomingRatio),
        size: getHubsSize(totalEdges)
      }

    case 'hierarchy':
      return {
        fill: getHierarchyColor(node.data.depth),
        size: getHierarchySize(node.data.descendants_count)
      }

    default:
      return {
        fill: '#64748b',
        size: [140, 40]
      }
  }
}
