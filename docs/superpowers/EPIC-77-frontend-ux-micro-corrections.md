# EPIC-77 : Micro-corrections UX (revue de parcours des 7 pages)

> **Status:** DONE
> **Priority:** P2 : polish de la revue de parcours utilisateur post-EPIC-76
> **Date:** 2026-08-08
> **Effort:** ~1 h
> **Scope:** `frontend/` uniquement

## Contexte

Revue du parcours utilisateur sur les 7 pages restantes (Dashboard, Search, Memories, Monitoring, Projects, Graph, Brain). Le socle (états vides/erreurs/chargements) était sain après EPIC-76. **6 micro-frictions** identifiées, toutes validées pour correction par l'utilisateur (« Toutes (EPIC-77) »).

## Frictions corrigées

| # | Friction | Fichier(s) | Correctif |
|---|---|---|---|
| 1 | **Boutons REFRESH à double label** : « LOADING LOADING... » / « REFRESH REFRESH » (un `<span>` + une interpolation rendaient le texte deux fois) | `Memories.vue`, `Monitoring.vue` | Suppression des spans redondants ; seule l'interpolation `{{ loading ? 'LOADING...' : 'REFRESH' }}` reste (pattern déjà utilisé par Dashboard/Brain) |
| 2 | **`healthStatus` : « NOMINAL » en jaune** avec des warnings non acquittés (trompeur) | `Monitoring.vue` | `if (critCount > 0 || warnCount > 0)` → WARNING ; sinon HEALTHY. NOMINAL supprimé |
| 3 | **`alert()` / `confirm()` natifs** (la seule page à utiliser les dialogs navigateur, dont un `alert()` de succès après delete) | `Projects.vue` | Bandeau feedback inline (succès vert / erreur rouge, auto-disparition 4 s) + modal custom de confirmation reindex (pattern du modal delete existant) |
| 4 | **`ackAlert` sans état de chargement** : double-clic = double POST, zéro feedback | `useMonitoring.ts`, `Monitoring.vue` | Ref `ackingId` exposé, anti double-clic (`early return` + `finally`), bouton ACK `:disabled="ackingId !== null"`, label `ACK...` |
| 5 | **Brain : compteurs à « 0 » pendant le premier chargement** | `Brain.vue` | `totalRows` et counts de groupes affichent `—` tant que `lastUpdated === null` |
| 6 | **Graph : aucun feedback de succès après BUILD** | `Graph.vue` | Toast transitoire « BUILD OK — {repo} » (4 s, transition fade) affiché si `buildError` reste null après `buildGraph` |

## Critères d'acceptation

- [x] `pnpm vue-tsc -b --noEmit` : 0 erreur
- [x] `pnpm vitest run` : 29/29
- [x] `npx eslint .` : 0 erreur (4 warnings de qualité connus)
- [x] `pnpm build` : OK (warning chunk size g6 non bloquant)
- [x] Aucun `alert(` / `confirm(` natif restant dans `src/pages/` (grep vérifié)

## Notes de décision

- **Zéro nouveau pattern** : tout réutilise ce qui existait (bandeau `alert-error` du thème, pattern `actionLoading` d'EPIC-76, toast `copyFeedback` de Search, modal custom de delete).
- La friction 2 a révélé une vraie incohérence sémantique : « NOMINAL » (vert par définition) affiché avec une LED jaune. Corrigé en WARNING, aligné sur la sémantique des LED.
- La friction 3 élimine le dernier usage de dialogs navigateur natifs : l'ensemble du frontend est désormais cohérent (UI custom partout).
