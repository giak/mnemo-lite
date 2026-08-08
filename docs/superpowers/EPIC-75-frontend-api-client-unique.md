# EPIC-75 — Frontend F-02 : Client API unique

> **Statut :** ✅ DONE (2026-08-08)
> **Périmètre :** `frontend/` (MnemoLite)
> **Décision :** Option A validée par l'utilisateur — « Frontend seul (recommandé) ». Pas de migration backend `/v1 → /api/v1` (impacterait 6 routeurs + 3 mounts + ≥11 scripts).

## Problème

Le frontend construisait ses URLs API de façon hétérogène :

1. **2 préfixes backend actifs** (vérité forensique vérifiée dans `api/main.py`) :
   - `/api/v1/*` : memories, dashboard, projects, monitoring v1, alertes, decay…
   - `/v1/*` : code_graph, code_search, events, cache, conversations, autosave, lsp.
2. **URLs en dur ignorant `VITE_API_URL`** :
   - `useMonitoring.ts` : `const API_BASE_URL = '/api/v1'` → cassé en config absolue.
   - `AlertRuleEditor.vue` : 4 appels `/api/monitoring/advanced/*` en dur (backend : prefix `/api/monitoring/advanced` vérifié).
3. **Alias locaux redondants** : `const API_BASE_URL = ${API}/…` dans useMemories, useMemorySearch, useDashboard, useProjects.

## Solution

Client unique `src/api/client.ts` (ancien `src/config/api.ts` supprimé) :

```ts
export const API = VITE_API_URL ? `${VITE_API_URL}/api/v1` : '/api/v1'
export const API_V1 = VITE_API_URL ? `${VITE_API_URL}/v1` : '/v1'
export const API_BASE = VITE_API_URL || ''

export function api(path, init?)     // fetch préfixé /api/v1
export function apiV1(path, init?)   // fetch préfixé /v1
export function apiBase(path, init?) // fetch préfixé racine (hors préfixes standard)
```

- `init` n'est passé à `fetch` que s'il est défini (les tests `useCodeGraph.test.ts` assertent un seul argument — non-invasion des tests).
- Type `FetchInit = Parameters<typeof fetch>[1]` (le global DOM `RequestInit` déclenche `no-undef` d'ESLint).

## Fichiers migrés (13)

| Fichier | Avant | Après |
|---|---|---|
| `composables/useMemories.ts` | `API` + alias local | `api()` |
| `composables/useMemorySearch.ts` | `API` + alias local | `api()` |
| `composables/useDashboard.ts` | `API` + alias local | `api()` |
| `composables/useProjects.ts` | `API` + alias local | `api()` |
| `composables/useMonitoring.ts` | **`'/api/v1'` en dur** | `api()` |
| `composables/useCodeGraph.ts` | `API_V1` | `apiV1()` |
| `composables/useCodeSearch.ts` | `API_V1` | `apiV1()` |
| `composables/useBrain.ts` | `API`/`API_V1` + safeFetch(url: string) | `api()`/`apiV1()` + safeFetch(Promise\<Response>) |
| `components/AutoSaveStatus.vue` | `API_V1` | `apiV1()` |
| `components/ConversationDetailModal.vue` | `API` | `api()` |
| `components/brain/ConsolidationSuggestions.vue` | `API` | `api()` |
| `components/brain/MemoryGraph.vue` | `API` | `api()` |
| `components/AlertRuleEditor.vue` | **`/api/monitoring/advanced/*` en dur** | `apiBase()` |
| `pages/Dashboard.vue` | `API_BASE` de `config/api` | `API_BASE` de `api/client` |

## Corrections de bugs réelles

- **`useMonitoring`** : les endpoints `/api/v1/monitoring/latency`, `/api/v1/alerts/*` existent côté backend (`@router_v1` vérifié) → `api()` aligne le comportement sur `VITE_API_URL`.
- **`AlertRuleEditor`** : `apiBase()` respecte désormais `VITE_API_URL` (avant : relatif à l'origin du frontend).
- **`useProjects`** : le diagnostic antérieur « `/projects` sans préfixe » était basé sur un état périmé — le fichier actuel importait déjà `API` (`prefix="/api/v1/projects"` vérifié). Pas de bug à corriger.

## Validation

- `vue-tsc -b --noEmit` : **0 erreur**
- `pnpm vitest run` : **29/29**
- `npx eslint .` : **0 erreur** (4 warnings connus)
- `pnpm build` : **OK**

## Review (code-reviewer-deepseek-flash)

Aucun correctif bloquant. Points traités :
- `safeFetch(Promise<Response>)` sans régression (construction eager identique, typecheck 0 confirme la migration de tous les call sites).
- Commentaire ajouté sur le cas d'usage d'`apiBase`.
- Pattern `init ? fetch(url, init) : fetch(url)` : justifié par les tests existants, KISS.

## Vérifications post-migration (grep)

- `config/api` dans `src/` : **0**
- `API_BASE_URL` dans `src/` : **0**
- `fetch('/…')` en dur : **0**
