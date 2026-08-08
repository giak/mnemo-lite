/**
 * Client API unique (EPIC-75 / F-02).
 *
 * Source de vérité unique pour les préfixes API et les appels fetch.
 * En dev, VITE_API_URL est vide et le serveur Vite proxie /api → http://localhost:8001 ;
 * en prod, VITE_API_URL pointe vers le backend réel.
 */

const VITE_API_URL = import.meta.env.VITE_API_URL || ''

/** API base path — relative in dev (uses Vite proxy), absolute in prod */
export const API = VITE_API_URL ? `${VITE_API_URL}/api/v1` : '/api/v1'

/** Full API base with /v1 prefix (legacy endpoints) */
export const API_V1 = VITE_API_URL ? `${VITE_API_URL}/v1` : '/v1'

/** Base URL only (for raw fetch calls) */
export const API_BASE = VITE_API_URL || ''

type FetchInit = Parameters<typeof fetch>[1]

/** fetch() préfixé par /api/v1 (majorité des endpoints) */
export function api(path: string, init?: FetchInit): Promise<Response> {
  return init ? fetch(`${API}${path}`, init) : fetch(`${API}${path}`)
}

/** fetch() préfixé par /v1 (endpoints legacy : code, events, cache, conversations…) */
export function apiV1(path: string, init?: FetchInit): Promise<Response> {
  return init ? fetch(`${API_V1}${path}`, init) : fetch(`${API_V1}${path}`)
}

/** fetch() préfixé par la racine (endpoints hors /api/v1 et /v1, ex. /api/monitoring/advanced) */
export function apiBase(path: string, init?: FetchInit): Promise<Response> {
  // Cas d'usage : les routes montées hors des deux préfixes standard
  // (ex. monitoring_routes_advanced : prefix "/api/monitoring/advanced").
  // Le chemin passé doit donc commencer par le prefix complet.
  return init ? fetch(`${API_BASE}${path}`, init) : fetch(`${API_BASE}${path}`)
}
