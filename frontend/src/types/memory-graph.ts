export interface MemoryNode {
  id: string
  title: string
  memory_type: string
  size: number
  tags: string[]
  entities?: string[]
  concepts?: string[]
}

export interface MemoryEdge {
  source: string
  target: string
  score: number
  types: string[]
  shared_entities?: string[]
  shared_concepts?: string[]
}

export interface MemoryGraphData {
  nodes: MemoryNode[]
  edges: MemoryEdge[]
  total_nodes: number
  total_edges: number
}

export interface ConsolidationGroup {
  source_ids: string[]
  titles: string[]
  content_previews: string[]
  shared_entities: string[]
  shared_concepts: string[]
  avg_similarity: number
  suggested_title: string
  suggested_tags: string[]
  suggested_summary_hint: string
}

export interface ConsolidationSuggestionsResponse {
  groups: ConsolidationGroup[]
  total_groups_found: number
}

export interface ConsolidateRequest {
  title: string
  summary: string
  source_ids: string[]
  tags?: string[]
  memory_type?: string
  author?: string
}

export interface ConsolidateResponse {
  consolidated_memory: {
    id: string
    title: string
    memory_type: string
    tags: string[]
    created_at: string
  }
  deleted_count: number
  total_source_ids: number
  source_ids: string[]
}
