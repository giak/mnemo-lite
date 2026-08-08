# MnemoLite Frontend

Interface web de gestion et d'exploration de la mémoire MnemoLite : santé système, recherche sémantique (mémoires + code), exploration par graphes, monitoring des alertes et des logs.

## Stack

| Brique | Version | Usage |
|---|---|---|
| **Vue 3** | ^3.5.22 | `<script setup>` SFC |
| **TypeScript** | ~5.9.3 | strict, `noUnusedLocals` |
| **Vite** | ^8.0.3 | dev server + build |
| **Tailwind CSS** | ^4.1.16 | utilitaires + thème custom `src/styles/theme.css` |
| **vue-router** | ^4.6.3 | 13 routes, lazy-loaded |
| **Pinia** | ^3.0.3 | installé (créé dans `main.ts`) — **aucun store n'est défini** (voir État connu) |
| **@antv/g6** | ^5.0.50 | graphes : `G6Graph.vue`, `OrgchartGraph.vue`, `ForceDirectedGraph.vue` |
| **v-network-graph** | ^0.9.21 | graphe : `Graph.vue` + import global `main.ts` (voir État connu) |
| **chart.js** | ^4.5.1 | `LatencyChart.vue` |
| **marked** + **highlight.js** | ^15 / ^11 | rendu Markdown (`useMarkdown.ts`) |
| **Vitest** | ^4.0.6 | tests unitaires (`composables` + `utils`) |

## Démarrage rapide

```bash
pnpm install          # dépendances
pnpm dev              # dev server sur http://localhost:3000 (proxy /api → :8001, /mcp → :8002)
pnpm build            # vue-tsc -b + vite build
pnpm preview          # preview du build
pnpm test             # vitest (watch)
pnpm test:ci          # vitest run
pnpm lint             # eslint . --fix  (⚠️ CASSÉ, voir État connu)
pnpm format           # prettier --write src/
```

### Configuration API

`src/config/api.ts` expose 3 bases :
- `API` = `/api/v1` (voie de référence, prod : `VITE_API_URL`)
- `API_V1` = `/v1` (endpoints legacy)
- `API_BASE` = racine seule

Dev : Vite proxie `/api`, `/v1`, `/health` → `http://localhost:8001` et `/mcp` → `http://localhost:8002` (configurable par `API_TARGET`).

## Structure

```
src/
├── pages/            # 13 pages (routes du router)
├── components/       # composants racine (Navbar, graphes, widgets)
│   ├── brain/        # sous-composants de la page Brain (13)
│   ├── sidebar/      # VIDE (mort)
│   └── explorer/     # VIDE (mort)
├── composables/      # 15 composables (logique de données, fetch nu)
│   └── __tests__/    # tests unitaires composables
├── layouts/          # MainLayout.vue (navbar + router-view)
├── types/            # interfaces par domaine (dashboard, memories, projects, graph)
├── utils/            # helpers (api.ts VIDE, scoring orgchart/zoom)
│   └── __tests__/
├── config/           # api.ts (bases API)
├── styles/           # theme.css (750 lignes de classes SCADA custom)
└── router.ts         # routes
```

## Pages

| Route | Page | Rôle |
|---|---|---|
| `/dashboard` | Dashboard.vue | Santé système, stats embeddings (TEXT/CODE), AutoSave, auto-refresh 30 s |
| `/search` | Search.vue | Recherche hybride : onglet Code + onglet Memories (persistance `?tab=`) |
| `/memories` | Memories.vue | Stats mémoires, récentes (infinite scroll), code chunks, santé embeddings |
| `/projects` | Projects.vue | Projets indexés (contenu, langages, couverture) |
| `/expanse` | Expanse.vue | Vues Expanse (tags, modal) |
| `/expanse-memory` | ExpanseMemory.vue | Mémoire Expanse |
| `/graph` | Graph.vue | Graphe de code (v-network-graph + G6Graph) |
| `/orgchart` | Orgchart.vue | Organigramme : 3 vues (OrgchartGraph, ForceDirected, DependencyMatrix) |
| `/brain` | Brain.vue | Explorateur : groupes, mémoires, code, events, alertes, métriques |
| `/monitoring` | Monitoring.vue | Latence, règles d'alertes |
| `/alerts` | Alerts.vue | Alertes actives (ACK, pagination) |
| `/logs` | Logs.vue | Logs + santé services |
| `/search-analytics` | SearchAnalytics.vue | Analytique de recherche (**absente de la navbar**) |

## Conventions

- Vue 3 `<script setup lang="ts">`, alias `@/` → `src/`.
- Style : Tailwind utilitaires + classes SCADA de `src/styles/theme.css` (`.scada-led`, `.scada-panel`, `.input`, `.section`, `.btn-primary`...).
- Données : composables par domaine (`useMemories`, `useDashboard`...) avec `fetch` direct et auto-refresh (`onMounted`/`onUnmounted`), pattern `data/loading/errors/lastUpdated/refresh`.
- EPICs de référence dans le commit history : EPIC-26 à EPIC-36 (SCADA, monitoring, search analytics, production).

## État connu (vérifié 2026-08-08)

| Point | État | Détail |
|---|---|---|
| **Lint** | ❌ CASSÉ | `eslint.config.js` importe `@eslint/js` mais la dépendance manque dans `package.json` devDependencies |
| **Typecheck** | ❌ 12 erreurs | `useProjects.ts` (2), `ExpanseMemory.vue`, `Graph.vue` (3, typage `Configs` v-network-graph), `Logs.vue` (2 unused), `Monitoring.vue`, `Projects.vue` (2), tests orgchart (2) |
| **Tests** | ⚠️ 40/41 | 1 échec : `semantic-zoom-scoring.test.ts` (garde des ancêtres : attendu 3, reçu 1) |
| **Pinia** | ⚠️ inutilisé | installé + `createPinia()`, zéro `defineStore` |
| **2 libs de graphes** | ⚠️ conflit | `@antv/g6` (3 composants) ET `v-network-graph` (Graph.vue + global) |
| **API_BASE_URL dupliqué** | ⚠️ 5× | `${API}/memories` ×3, `'/api/v1'` en dur (useMonitoring), `${API}/dashboard` |
| **Mort** | 🟡 | `utils/api.ts` vide (0 o), `components/sidebar/`, `components/explorer/` vides |

## Docker (profil dev)

Service `frontend` dans `docker-compose.yml` (profil `dev`, conteneur `mnemo-frontend`), build `docker/Dockerfile.frontend`, servie par nginx (`docker/nginx.conf`) en production (profil prod).
