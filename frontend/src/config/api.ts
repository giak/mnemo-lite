/**
 * Centralized API configuration.
 *
 * Uses Vite env vars:
 *   VITE_API_URL  — Base URL of the MnemoLite API (default: http://localhost:8001)
 *
 * In dev mode, the Vite proxy forwards /api and /v1 to the API server,
 * so relative paths work. In production, set VITE_API_URL to the real URL.
 */

const VITE_API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001'

/** Full API base with /api/v1 prefix */
export const API = `${VITE_API_URL}/api/v1`

/** Full API base with /v1 prefix (legacy endpoints) */
export const API_V1 = `${VITE_API_URL}/v1`

/** Base URL only (for raw fetch calls) */
export const API_BASE = VITE_API_URL
