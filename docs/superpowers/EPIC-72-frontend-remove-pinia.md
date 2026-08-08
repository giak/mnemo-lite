# EPIC-72 : Retirer Pinia du frontend (dépendance morte)

> **Status:** DONE
> **Priority:** P1 : élimine une dépendance morte et un `app.use()` sans objet avant les EPIC de refactor fonctionnel (73-74)
> **Date:** 2026-08-08
> **Effort:** 30 min
> **Scope:** `frontend/` uniquement

## Problem Statement

Pinia est installé (`pinia ^3.0.3` dans `dependencies`) et câblé (`createPinia()` + `app.use()` dans `src/main.ts`), mais **aucun store n'existe** : zéro `defineStore`, zéro `usePinia`, aucun dossier `stores/` dans tout `src/` (vérifié le 2026-08-08). Toute la logique applicative vit dans les composables qui font du `fetch` nu. Pinia est donc une dépendance morte qui :

- gonfle le bundle (runtime inutilisé) et les `node_modules` ;
- crée une fausse architecture (un futur agent pourrait croire que l'état applicatif est censé y vivre) ;
- ajoute un `app.use()` sans effet.

## Correctifs prévus

| # | Fichier | Changement |
|---|---|---|
| 1 | `src/main.ts` | Retirer `import { createPinia } from 'pinia'` et `app.use(createPinia())` |
| 2 | `package.json` | `pnpm remove pinia` (dépendance + lockfile) |

## Critères d'acceptation

- [x] `grep -rn 'pinia' src/` : rien (vérifié)
- [x] `pnpm vue-tsc -b --noEmit` : 0 erreur
- [x] `pnpm vitest run` : 41/41
- [x] `npx eslint .` : 0 erreur (7 warnings de qualité résiduels, identiques à EPIC-71)

## Notes de décision

- Décision utilisateur (2026-08-08) : **retirer Pinia** (KISS). Zéro `defineStore` = zéro valeur. Si un besoin d'état cross-pages réel émerge pendant les EPIC suivantes (ex. sélection de recherche persistée entre pages), un simple composable module-level avec `ref` exporté suffira — sans nouvelle dépendance.
- `v-network-graph` reste dans `main.ts` pour l'instant : retiré en EPIC-73 (sortir du duopole g6/v-network-graph).

### Incident connexe découvert (corrigé dans un commit séparé)

Le retrait de Pinia a révélé que le pattern `.gitignore` `src/` (commentaire « Orphaned directories », vestige d'un dossier racine qui n'existe plus) matchait **aussi** `frontend/src/` : tout nouveau fichier frontend/src non tracké était invisible pour git. Conséquences constatées :

- 4 fichiers réels du frontend n'avaient **jamais** été trackés (bloqués par le pattern) :
  - `ConsolidationSuggestions.vue`, `MemoryGraph.vue` : composants actifs (utilisés par `pages/Brain.vue`), portant des corrections typecheck EPIC-71 manquantes au commit `6d1f45d` ;
  - `useConsolidation.ts`, `useMemoryGraph.ts` : code mort (jamais importés, créés 2026-04-04), candidats à la suppression EPIC-74.

Correctif : `.gitignore` `src/` → `/src/` (ancré à la racine) dans le commit `fix(gitignore)` qui suit, avec l'ajout des 4 fichiers.
