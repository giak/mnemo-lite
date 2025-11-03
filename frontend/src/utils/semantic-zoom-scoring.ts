import type { GraphNode } from '@/composables/useCodeGraph'
import type { ViewMode } from '@/types/orgchart-types'

export interface ScoringWeights {
  complexity: number  // 0-1
  loc: number          // 0-1
  connections: number  // 0-1
}

/**
 * Normalize a metric value to 0-1 range
 */
function normalize(value: number | undefined, max: number): number {
  if (value === undefined || value === null) return 0
  return Math.min(value / max, 1)
}

/**
 * Calculate composite score for a node (0-1 range)
 *
 * Normalization scales:
 * - Complexity: 0-100 (max realistic complexity)
 * - LOC: 0-500 (max realistic lines in one chunk)
 * - Connections: 0-100 (max realistic edge count)
 */
export function calculateNodeScore(
  node: GraphNode,
  viewMode: ViewMode,
  weights: ScoringWeights
): number {
  // Entry points (Modules) are always prioritized - they have no metrics themselves
  // but are essential as roots of the dependency tree
  if (node.type === 'Module') {
    return 1.0
  }

  const normalizedComplexity = normalize(node.cyclomatic_complexity, 100)
  const normalizedLoc = normalize(node.lines_of_code, 500)
  const normalizedConnections = normalize(node.total_edges, 100)

  const score =
    (normalizedComplexity * weights.complexity) +
    (normalizedLoc * weights.loc) +
    (normalizedConnections * weights.connections)

  return score
}

/**
 * Filter nodes to keep only top N% by score
 *
 * @param nodes - All available nodes
 * @param zoomLevel - Percentage (0-100) of nodes to keep
 * @param viewMode - Current view mode (affects default weights if needed)
 * @param weights - Custom scoring weights
 * @returns Filtered nodes sorted by score (highest first)
 */
export function filterNodesByScore(
  nodes: GraphNode[],
  zoomLevel: number,
  viewMode: ViewMode,
  weights: ScoringWeights
): GraphNode[] {
  // Calculate score for each node
  const nodesWithScores = nodes.map(node => ({
    node,
    score: calculateNodeScore(node, viewMode, weights)
  }))

  // Sort by score descending
  nodesWithScores.sort((a, b) => b.score - a.score)

  // Calculate how many nodes to keep
  const percentile = zoomLevel / 100
  const countToKeep = Math.ceil(nodes.length * percentile)

  // Return top N nodes
  return nodesWithScores
    .slice(0, countToKeep)
    .map(item => item.node)
}
