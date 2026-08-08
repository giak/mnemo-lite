# 🟢 EPIC-71 : Fondations vertes frontend (lint + typecheck + tests + mort cérébrale)

> **Status:** DONE
> **Priority:** P0 : sans lint/typecheck/tests au vert, aucune dette ne peut être contractée en toute sécurité pendant les EPIC frontend suivantes (72-75)
> **Date:** 2026-08-08
> **Effort:** 1 h 30
> **Scope:** `frontend/` uniquement

## Problem Statement

Le frontend MnemoLite (Vue 3 + TS + Vite) est fonctionnel mais porte 3 fragilités de fondation + un mort cérébral, mesurés le 2026-08-08 :

1. **Lint CASSÉ** : `pnpm lint` crashe `ERR_MODULE_NOT_FOUND: Cannot find package '@eslint/js'`. `eslint.config.js` importe `@eslint/js` mais la dépendance est absente des devDependencies. (`vue-eslint-parser` est aussi importé sans être déclaré.)
2. **12 erreurs de type** (`pnpm vue-tsc -b --noEmit`) : 3 dans `pages/Graph.vue` (typage `Configs` v-network-graph + `start_line`/`end_line` absents de `GraphNode`), 2 dans `composables/useProjects.ts`, 1 dans `pages/ExpanseMemory.vue`, 5 imports/variables inutilisées (`Logs.vue`, `Monitoring.vue`, `Projects.vue`), 2 dans les tests `orgchart-visual-encoding.test.ts`.
3. **1 test rouge** : `semantic-zoom-scoring.test.ts > filterNodesByScore > includes ancestors to maintain tree paths` (attendu 3 nœuds, reçu 1 : les ancêtres ne sont pas conservés).
4. **Mort cérébrale** : `src/utils/api.ts` vide (0 octet), dossiers `src/components/sidebar/` et `src/components/explorer/` vides.

## Correctifs prévus

| # | Fichier | Changement |
|---|---|---|
| 1 | `package.json` | Ajouter `@eslint/js` et `vue-eslint-parser` aux devDependencies (alignés sur `eslint.config.js`) |
| 2 | `src/pages/Graph.vue` | Corriger les types : étendre `GraphNode` avec `start_line`/`end_line` optionnels (aligné sur le type réellement produit par l'API), résoudre l'appel `Configs` non typé |
| 3 | `src/composables/useProjects.ts` | Corriger `ReindexProjectResponse` non assignable à `void` + garde `undefined` (l.168) |
| 4 | `src/pages/ExpanseMemory.vue` | Garde `undefined` (l.73) |
| 5 | `src/pages/Logs.vue`, `Monitoring.vue`, `Projects.vue` | Supprimer imports/variables inutilisées |
| 6 | `src/utils/__tests__/orgchart-visual-encoding.test.ts` | Supprimer imports inutilisés (`getHubsSize`, `getHierarchySize`) |
| 7 | `src/utils/__tests__/semantic-zoom-scoring.test.ts` | Corriger le **test** (pas l'algo) : à 33 % le top-1 était le Module (priorité 1.0, priorité documentée) et non la Function — le test calibré à 33 % testait un contrat impossible. Recalé à 50 % (top-2 = Module + Function) : le chemin ancêtre Class est bien ajouté → 3 nœuds. |
| 8 | `src/utils/api.ts`, `src/components/sidebar/`, `src/components/explorer/` | Supprimer le mort |

## Critères d'acceptation

- [x] `npx eslint .` : **0 erreur** (7 warnings de qualité résiduels, documentés ci-dessous)
- [x] `pnpm vue-tsc -b --noEmit` : **0 erreur**
- [x] `pnpm vitest run` : **41/41**
- [x] Aucun dossier vide ni fichier 0-octet ne subsiste dans `src/` (`utils/api.ts` supprimé, `sidebar/` et `explorer/` supprimés)

## Notes de décision

- Le duopole graphique (g6 vs v-network-graph) est **hors périmètre** de cette EPIC : tranché en EPIC-73 (garder `@antv/g6`, retirer `v-network-graph`). Ici, on corrige juste les types de Graph.vue sans changer la lib.
- Pinia : retiré en EPIC-72.
- Simplification des pages (suppressions) : EPIC-74.

## État final (2026-08-08, mesuré)

- `npx eslint .` : **0 erreur** (7 warnings résiduels : `vue/require-default-prop` ×5 sur `OrgchartGraph`, `vue/no-v-html` ×2 sur `BrainSidebar` — de la vraie qualité, laissés actifs)
- `pnpm vue-tsc -b --noEmit` : **0 erreur**
- `pnpm vitest run` : **41/41**
- `pnpm build` (`vue-tsc -b && vite build`) : **OK**
- Dépendances ajoutées : `@eslint/js`, `vue-eslint-parser`, `globals` (dev) ; `marked-highlight` (runtime, marked v15 a déplacé l'option `highlight` vers un plugin)

### Périmètre réel (vs prévu)

- Le typecheck réel était **77 erreurs** (et non 12 : les 12 visibles étaient le sommet de l'arbre incrémental masquant le reste), réparties sur 16 fichiers — toutes corrigées (composants graphiques G6, composables, tests, useMarkdown).
- Le lint réel était **1 655 erreurs** : la flat config ESLint n'ignorait pas `dist/` (bundle minifié, ~1 600 erreurs) ni ne déclarait les globals navigateur. Corrigé par `ignores` + `globals` dans `eslint.config.js`.

### Config eslint : règles de formatage désactivées

`pnpm lint` = `eslint . --fix` reformatait massivement les templates (`vue/attributes-order`, `vue/html-self-closing` → 2 410 lignes de diff cosmétique sur 57 fichiers). Décision : désactiver les règles de formatage template (le code n'a jamais été formaté selon elles, zéro valeur de correction) et garder les règles de qualité. Le reformatage accidentel a été reversé (`git checkout` des 22 fichiers non édités).

### Caveat runtime connu (hors périmètre, préexistant)

Le « Memory Graph » (`MemoryGraph.vue`, embarqué dans `pages/Brain.vue`) **ne se rend pas** : `G6Graph` filtre les nœuds sur `filterByType = ['Class','Function','Method']`, or les nœuds mémoire ont `type: decision/note/investigation` → tout est exclu → graph vide. **Préexistant** (avant, `type` était même absent des nœuds), non introduit par cette EPIC. Options : (a) `G6Graph` ne filtre que si des types connus existent, (b) page dédiée hors G6Graph. Page susceptible d'être supprimée en EPIC-74 (simplification) → laissé tel quel (YAGNI).
