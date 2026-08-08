/**
 * EPIC-78: Knowledge Explorer Types
 * TypeScript interfaces pour le Knowledge Explorer (page Explorer).
 */

export interface ExplorerStats {
  /** Distribution par memory_type (ex. { investigation: 4808, article: 52 }) */
  by_type: Record<string, number>
  /** Couverture factuelle du socle */
  status: {
    /** Nombre de mémoires taggées status:CONFIRME */
    confirmed: number
    /** Nombre de mémoires taggées fact-check */
    fact_checked: number
    /** Nombre total d'éléments du socle (conversations exclues) */
    total: number
  }
  /** Tags de sujet les plus présents (hors bruit technique) */
  top_subjects: Array<{ tag: string; count: number }>
  /** Investigations/articles/quintessences par mois (YYYY-MM) */
  timeline: Array<{ month: string; count: number }>
}

/** Élément de l'arborescence d'un sujet (endpoint /explorer/tree) */
export interface ExplorerTreeItem {
  id: string
  title: string
  memory_type: string
  tags: string[]
  created_at: string | null
}

/** Arborescence d'un sujet : enquêtes / faits vérifiés / autres */
export interface ExplorerTree {
  subject: string
  total: number
  investigations: ExplorerTreeItem[]
  facts: ExplorerTreeItem[]
  others: ExplorerTreeItem[]
}

/** Mémoire liée par proxy de tags partagés (endpoint /related-by-tags) */
export interface RelatedItem {
  id: string
  title: string
  memory_type: string
  shared_tags: string[]
  score: number
}

export interface RelatedResponse {
  memory_id: string
  related: RelatedItem[]
  total: number
}
