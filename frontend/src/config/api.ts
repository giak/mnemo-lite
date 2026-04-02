/**
 * Centralized API configuration.
 *
 * In dev mode, the Vite dev server proxies /api → http://localhost:8001,
 * so we use relative paths. In production, set VITE_API_URL to the real URL.
 */

const VITE_API_URL = import.meta.env.VITE_API_URL || ''

/** API base path — relative in dev (uses Vite proxy), absolute in prod */
export const API = VITE_API_URL ? `${VITE_API_URL}/api/v1` : '/api/v1'

/** Full API base with /v1 prefix (legacy endpoints) */
export const API_V1 = VITE_API_URL ? `${VITE_API_URL}/v1` : '/v1'

/** Base URL only (for raw fetch calls) */
export const API_BASE = VITE_API_URL || ''
