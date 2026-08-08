# EPIC-73 : Sortir du duopole graphique — retirer v-network-graph, garder @antv/g6

> **Status:** DONE
> **Priority:** P1 : deux libs de graphes = deux bundles, deux APIs, deux typages à maintenir. Tranche le duopole avant les EPIC de simplification (74).
> **Date:** 2026-08-08
> **Effort:** 2-3 h
> **Scope:** `frontend/` uniquement

## Problem Statement

Le frontend embarque **deux bibliothèques de graphes** :
- `@antv/g6` (v5) : utilisé par `G6Graph.vue` (961 l), `OrgchartGraph.vue` (824 l), `ForceDirectedGraph.vue` (343 l) — ~2 100 lignes de composants investies ;
- `v-network-graph` (0.9.21) : importé **globalement** dans `main.ts` (`app.use(VNetworkGraph)` + CSS) et utilisé par une branche legacy de `pages/Graph.vue` (computed `nodes`/`edges`/`layouts`/`configs` + bloc `<v-network-graph>` + légende + toggle « View »).

La branche G6 de `Graph.vue` est **le défaut actif** (`useG6 = ref(true)`) ; la branche v-network est un mode alternatif non utilisé en pratique. Coût du duopole : 2 bundles, 2 APIs, 2 systèmes de typage, une maintenance doublée.

**Décision utilisateur (2026-08-08) : garder `@antv/g6`, retirer `v-network-graph`.**

## Correctifs prévus

| # | Fichier | Changement |
|---|---|---|
| 1 | `src/main.ts` | Retirer `import VNetworkGraph`, `import 'v-network-graph/lib/style.css'` et `app.use(VNetworkGraph)` |
| 2 | `package.json` | `pnpm remove v-network-graph` |
| 3 | `src/pages/Graph.vue` | Supprimer la branche legacy : import `Nodes/Edges/Layouts`, `useG6`, `extractNodeName`/`getNodeGroup` (utilisés uniquement par les computeds v-network), computeds `nodes`/`edges`/`layouts`/`configs`, template `<v-network-graph>` + légende + toggle « View ». `Graph.vue` devient un client pur de `G6Graph` |

## Critères d'acceptation

- [x] `grep -rn 'v-network-graph' src/` : seulement le commentaire documentaire de Graph.vue l.5
- [x] `pnpm vue-tsc -b --noEmit` : 0 erreur
- [x] `pnpm vitest run` : 41/41
- [x] `npx eslint .` : 0 erreur (7 warnings de qualité résiduels, identiques à EPIC-71)
- [x] `pnpm build` : OK

## Notes de décision

- L'alternance Network/G6 du toggle « View » de `Graph.vue` disparaît : G6 est l'unique moteur. Si un rendu « réseau » (force layout) est un jour souhaité, `ForceDirectedGraph.vue` (déjà en g6) le fournit sans dépendance nouvelle.
- Le bundler gagnera le poids de `v-network-graph` + son CSS (inutile dans `main.ts`).
- `@antv/g6` reste la seule dépendance de graphe du projet après cette EPIC.
