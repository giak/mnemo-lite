/**
 * EPIC-25 Story 25.3: Dashboard TypeScript Types
 * Type definitions for dashboard API responses
 */

export interface HealthStatus {
  status: 'healthy' | 'degraded'
  timestamp: string
  services: {
    api: boolean
    database: boolean
    redis: boolean
  }
}

export interface EmbeddingStats {
  model: string
  count: number
  dimension: number
  lastIndexed: string | null
}

export interface DashboardData {
  health: HealthStatus | null
  textEmbeddings: EmbeddingStats | null
  codeEmbeddings: EmbeddingStats | null
}

export interface DashboardError {
  endpoint: string
  message: string
  timestamp: string
}
