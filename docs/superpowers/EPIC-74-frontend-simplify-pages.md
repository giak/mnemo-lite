# EPIC-74 : Simplifier les pages — suppression radicale + nav générée depuis le router

> **Status:** DONE
> **Priority:** P0 : le plus gros gain utilisateur. Consigne utilisateur : « tout ce qui n'est pas utile, poubelle. On pourra plus tard recréer des pages et des fonctionnalités. »
> **Date:** 2026-08-08
> **Effort:** 2-3 h
> **Scope:** `frontend/` uniquement

## Décision (validée par l'utilisateur, 2026-08-08)

**Supprimer 6 pages** : `SearchAnalytics` (route orpheline, jamais liée), `Orgchart` (redondant avec le Code Graph), `Alerts` (redondant : `Monitoring`/`AlertRuleEditor` + `Brain`/`AlertsDashboard`), `Expanse`, `ExpanseMemory`, `Logs`.

**Conserver 7 pages** : `Dashboard`, `Search`, `Memories`, `Projects`, `Monitoring`, `Brain`, `Graph`.

## Correctifs prévus

| # | Fichier | Changement |
|---|---|---|
| 1 | `src/router.ts` | Retirer les 6 routes supprimées ; ajouter `meta: { navLabel, navGroup }` aux 7 routes conservées ; ajouter une route catch-all `/:pathMatch(.*)*` → `/dashboard` |
| 2 | `src/components/Navbar.vue` | **Nav générée depuis le router** (filtre sur `meta.navLabel`, groupée par `meta.navGroup`) — plus de liens codés en dur, plus de sous-menu, plus de badge ALERTS (page supprimée) ni de `fetch /alerts/summary` |
| 3 | Pages supprimées | `SearchAnalytics.vue`, `Orgchart.vue`, `Alerts.vue`, `Expanse.vue`, `ExpanseMemory.vue`, `Logs.vue` |
| 4 | Composants orphelins | `OrgchartGraph.vue`, `ForceDirectedGraph.vue`, `DependencyMatrix.vue` (uniquement utilisés par Orgchart), `ExpanseTagModal.vue` (uniquement utilisé par Expanse) |
| 5 | Composables orphelins | `useExpanse.ts`, `useExpanseMemory.ts`, `useConsolidation.ts` (mort, identifié EPIC-72), `useMemoryGraph.ts` (mort, identifié EPIC-72) |
| 6 | Utils/types orphelins | `utils/orgchart-visual-encoding.ts`, `utils/semantic-zoom-scoring.ts`, `types/orgchart-types.ts` (chaîne de dépendances d'Orgchart uniquement) |
| 7 | Tests orphelins | `utils/__tests__/orgchart-visual-encoding.test.ts`, `utils/__tests__/semantic-zoom-scoring.test.ts` |

## Critères d'acceptation

- [x] `pnpm vue-tsc -b --noEmit` : 0 erreur
- [x] `pnpm vitest run` : 29/29 (les 12 tests des utilitaires supprimés sont retirés avec eux)
- [x] `npx eslint .` : 0 erreur (4 warnings de qualité)
- [x] `pnpm build` : OK
- [x] La nav ne référence que les 7 routes restantes (générée depuis le router, aucun lien mort)

## Notes de décision

- Le badge « alertes actives » de la nav est retiré avec la page `Alerts` : les alertes restent consultables via `Brain` (onglet Alerts) et configurables via `Monitoring` (AlertRuleEditor).
- Les composants `brain/*` (MemoryGraph, ConsolidationSuggestions, AlertsDashboard, ...) et `G6Graph` restent : utilisés par `Brain.vue` et `Graph.vue`.
- La nav est désormais la **source de vérité dérivée du router** : toute future route avec `meta.navLabel` apparaît automatiquement (fini le décalage navbar/route, comme pour l'orpheline SearchAnalytics).
- Les pages supprimées restent récupérables via l'historique git (retrait réversible).
