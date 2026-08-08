# MnemoLite Frontend

Interface web de gestion et d'exploration de la mémoire MnemoLite : santé système, recherche sémantique (mémoires + code), exploration par graphes, monitoring des alertes.

## Stack

| Brique | Version | Usage |
|---|---|---|
| **Vue 3** | ^3.5.22 | `<script setup>` SFC |
| **TypeScript** | ~5.9.3 | strict, `noUncheckedIndexedAccess` |
| **Vite** | ^8.0.3 | dev server + build |
| **Tailwind CSS** | ^4.1.16 | utilitaires + thème custom `src/styles/theme.css` |
| **vue-router** | ^4.6.3 | 7 routes lazy-loaded ; la navbar est générée depuis le router (`meta.navLabel`/`navGroup`) |
| **@antv/g6** | ^5.0.50 | graphe : `G6Graph.vue` (seule lib de graphe) |
| **chart.js** | ^4.5.1 | `LatencyChart.vue` |
| **marked** + **marked-highlight** | ^15 | rendu Markdown (`useMarkdown.ts`) |
| **Vitest** | ^4.0.6 | tests unitaires (`composables/__tests__`) |

## Démarrage rapide

```bash
pnpm install          # dépendances
pnpm dev              # dev server sur http://localhost:3000 (proxy /api → :8001, /mcp → :8002)
pnpm build            # vue-tsc -b + vite build
pnpm preview          # preview du build
pnpm test             # vitest (watch)
pnpm test:ci          # vitest run
pnpm lint             # eslint . --fix (⚠️ désactive les règles de formatage template, voir config)
pnpm format           # prettier --write src/
```

### Configuration API

`src/api/client.ts` est le **client API unique** (EPIC-75) : 3 constantes + 3 helpers fetch.
- `API` = `/api/v1` (voie de référence, prod : `VITE_API_URL`)
- `API_V1` = `/v1` (endpoints legacy : code, events, cache, conversations…)
- `API_BASE` = racine seule (endpoints hors préfixes standard, ex. `/api/monitoring/advanced`)
- `api(path, init?)` / `apiV1(path, init?)` / `apiBase(path, init?)` : `fetch` préfixé (ne passe `init` que s'il est défini)

Dev : Vite proxie `/api`, `/v1`, `/health` → `http://localhost:8001` et `/mcp` → `http://localhost:8002` (configurable par `API_TARGET`).

## Structure

```
src/
├── pages/            # 7 pages (routes du router, meta.navLabel pour la nav)
├── components/       # composants racine (Navbar, G6Graph, widgets)
│   └── brain/        # 12 sous-composants de la page Brain
├── composables/      # 10 composables (logique de données, fetch nu)
│   └── __tests__/    # tests unitaires composables
├── layouts/          # MainLayout.vue (navbar + router-view)
├── api/              # client.ts (client API unique : constantes + helpers fetch)
├── types/            # interfaces par domaine (dashboard, memories, memory-graph, projects)
├── styles/           # theme.css (750 lignes de classes SCADA custom)
└── router.ts         # routes + meta nav
```

## Pages

| Route | Page | Rôle |
|---|---|---|
| `/dashboard` | Dashboard.vue | Santé système, stats embeddings, AutoSave, auto-refresh 30 s |
| `/search` | Search.vue | Recherche hybride : onglet Code + onglet Memories (persistance `?tab=`) |
| `/memories` | Memories.vue | Stats mémoires, récentes (infinite scroll), code chunks, santé embeddings |
| `/brain` | Brain.vue | Explorateur : groupes (memory/system/intelligence), 10 onglets (mémoires, code, alertes, métriques, cache, batch, graphe, métriques calculées, graphe mémoire, consolidation). Onglets fantômes retirés en EPIC-76 |
| `/monitoring` | Monitoring.vue | Latence, règles d'alertes |
| `/projects` | Projects.vue | Projets indexés (contenu, langages, couverture) |
| `/graph` | Graph.vue | Graphe de code (G6Graph) |

Routes supprimées en EPIC-74 (récupérables via git) : `/search-analytics`, `/orgchart`, `/alerts`, `/expanse`, `/expanse-memory`, `/logs`. Toute URL inconnue redirige vers `/dashboard` (catch-all).

## Conventions

- Vue 3 `<script setup lang="ts">`, alias `@/` → `src/`.
- Style : Tailwind utilitaires + classes SCADA de `src/styles/theme.css` (`.scada-led`, `.scada-panel`, `.input`, `.section`, `.btn-primary`...).
- Données : composables par domaine (`useMemories`, `useDashboard`...) avec `fetch` direct et auto-refresh (`onMounted`/`onUnmounted`), pattern `data/loading/errors/lastUpdated/refresh`.
- Navigation : ajouter une route avec `meta: { navLabel, navGroup }` la fait apparaître automatiquement dans la navbar (ordre = ordre de déclaration des routes).

## Reliquats connus (vérifié 2026-08-08)

| Point | État | Détail |
|---|---|---|
| **Client API unique** | ✅ | EPIC-75 : `src/api/client.ts` (3 constantes + helpers `api`/`apiV1`/`apiBase`), `config/api.ts` supprimé, tous les fetch migrés |
| **Warnings lint** | ⚠️ 4 | `vue/require-default-prop` (props sans défaut) + `vue/no-v-html` (BrainSidebar) — de la vraie qualité, volontairement actifs |
| **Chunk size** | ⚠️ | bundle g6 > 500 kB (warning Vite au build, non bloquant) |
| **Robustesse UX (F-06)** | ✅ | EPIC-76 : bandeau d'erreur Brain réel (échec partiel/total), onglets fantômes retirés, Batch branché sur la vraie route, AlertRuleEditor avec erreurs + actions bloquées |

État du pipeline (EPIC-71-74) : lint **0 erreur**, vue-tsc **0 erreur**, vitest **29/29**, build **OK**.

## Docker (profil dev)

Service `frontend` dans `docker-compose.yml` (profil `dev`, conteneur `mnemo-frontend`), build `docker/Dockerfile.frontend`, servie par nginx (`docker/nginx.conf`) en production (profil prod).
