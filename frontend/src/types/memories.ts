/**
 * EPIC-26: Memories Monitor Types
 * TypeScript interfaces for memories monitor page
 */

export interface MemoriesStats {
  total: number
  today: number
  embedding_rate: number
  last_activity: string | null
}

export interface Memory {
  id: string
  title: string
  created_at: string
  memory_type: string
  tags: string[]
  has_embedding: boolean
  author: string | null
}

export interface MemoryDetail extends Memory {
  content: string
  updated_at: string | null
  project_id: string | null
}

export interface CodeChunk {
  id: string
  file_path: string
  chunk_type: string
  repository: string
  language: string
  indexed_at: string
  content_preview: string
}

export interface IndexingStats {
  chunks_today: number
  files_today: number
}

export interface CodeChunksResponse {
  indexing_stats: IndexingStats
  recent_chunks: CodeChunk[]
}

export interface EmbeddingsHealth {
  text_embeddings: {
    total: number
    with_embeddings: number
    success_rate: number
    model: string
  }
  code_embeddings: {
    total: number
    model: string
  }
  alerts: Array<{
    type: 'warning' | 'error' | 'info'
    message: string
  }>
  status: 'healthy' | 'degraded' | 'critical'
}

export interface MemoriesData {
  stats: MemoriesStats | null
  recentMemories: Memory[]
  codeChunks: CodeChunksResponse | null
  embeddingsHealth: EmbeddingsHealth | null
}

export interface MemoriesError {
  endpoint: string
  message: string
  timestamp: string
}
