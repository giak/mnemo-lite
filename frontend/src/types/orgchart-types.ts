export type ViewMode = 'complexity' | 'hubs' | 'hierarchy' | 'force' | 'matrix'

export interface ViewModeConfig {
  name: string
  description: string
  icon: string
}

export const VIEW_MODES: Record<ViewMode, ViewModeConfig> = {
  complexity: {
    name: 'Complexité',
    description: 'Technical debt hotspots',
    icon: '📊'
  },
  hubs: {
    name: 'Hubs',
    description: 'Architectural dependencies',
    icon: '🔗'
  },
  hierarchy: {
    name: 'Hiérarchie',
    description: 'Structure & depth',
    icon: '🌳'
  },
  force: {
    name: 'Architecture',
    description: 'Force-directed clusters',
    icon: '🌐'
  },
  matrix: {
    name: 'Matrice',
    description: 'Dependency heatmap',
    icon: '📋'
  }
}
