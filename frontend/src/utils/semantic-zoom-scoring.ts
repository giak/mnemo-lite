import type { GraphNode, GraphEdge } from '@/composables/useCodeGraph'
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
 * Filter nodes to keep only top N% by score, PLUS all ancestors to maintain tree paths
 *
 * @param nodes - All available nodes
 * @param edges - All edges (needed to determine parent-child relationships)
 * @param zoomLevel - Percentage (0-100) of nodes to keep
 * @param viewMode - Current view mode (affects default weights if needed)
 * @param weights - Custom scoring weights
 * @returns Filtered nodes with complete tree paths preserved
 */
export function filterNodesByScore(
  nodes: GraphNode[],
  edges: GraphEdge[],
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

  // DEBUG: Log top 10 and bottom 10 scores
  console.log('[SemanticZoom] Top 10 scores:', nodesWithScores.slice(0, 10).map(n => ({
    type: n.node.type,
    label: n.node.label,
    score: n.score.toFixed(3)
  })))

  // Calculate how many nodes to keep based on score
  const percentile = zoomLevel / 100
  const countToKeep = Math.ceil(nodes.length * percentile)

  // Get top N nodes by score
  const topNodes = nodesWithScores
    .slice(0, countToKeep)
    .map(item => item.node)

  console.log(`[SemanticZoom] Top ${countToKeep} nodes selected (${zoomLevel}%)`)

  // Build parent map from edges (child -> parent relationship)
  const parentMap = new Map<string, string>()
  edges.forEach(edge => {
    // edge.source is parent, edge.target is child (for imports/calls/contains edges)
    parentMap.set(edge.target, edge.source)
  })

  // For each selected node, add all its ancestors to maintain tree paths
  const nodesToInclude = new Set<string>()

  topNodes.forEach(node => {
    // Add the node itself
    nodesToInclude.add(node.id)

    // Walk up the tree to add all ancestors
    let currentId = node.id
    let depth = 0
    const maxDepth = 50 // Prevent infinite loops

    while (parentMap.has(currentId) && depth < maxDepth) {
      const parentId = parentMap.get(currentId)!
      nodesToInclude.add(parentId)
      currentId = parentId
      depth++
    }
  })

  // Filter nodes to only those included (maintaining order from original array)
  const filtered = nodes.filter(node => nodesToInclude.has(node.id))

  console.log('[SemanticZoom] After ancestor inclusion:', {
    topNodesCount: topNodes.length,
    withAncestorsCount: filtered.length,
    ancestorsAdded: filtered.length - topNodes.length
  })

  console.log('[SemanticZoom] Filtered node types:', filtered.map(n => n.type).reduce((acc, type) => {
    acc[type] = (acc[type] || 0) + 1
    return acc
  }, {} as Record<string, number>))

  return filtered
}
