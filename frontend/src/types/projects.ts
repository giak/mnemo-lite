/**
 * EPIC-27: Projects Management Types
 * TypeScript interfaces for projects management page
 */

export type ProjectStatus = 'healthy' | 'needs_reindex' | 'poor_coverage' | 'error'

export interface Project {
  repository: string
  files_count: number
  chunks_count: number
  languages: string[]
  last_indexed: string | null
  status: ProjectStatus
  total_loc: number
  graph_coverage: number
}

export interface ProjectsResponse {
  projects: Project[]
}

export interface ActiveProjectResponse {
  repository: string
}

export interface SetActiveProjectRequest {
  repository: string
}

export interface SetActiveProjectResponse {
  repository: string
  message: string
}

export interface ReindexProjectResponse {
  repository: string
  status: string
  message: string
  project_root: string
}

export interface DeleteProjectResponse {
  repository: string
  deleted_chunks: number
  deleted_nodes: number
  message: string
}
