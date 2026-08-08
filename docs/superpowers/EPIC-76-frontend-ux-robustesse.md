# EPIC-76 : Robustesse UX (F-06) — états vides/erreurs/chargements des composants

> **Status:** DONE
> **Priority:** P1 : dernière EPIC de la file frontend (F-06)
> **Date:** 2026-08-08
> **Effort:** 2-3 h
> **Scope:** `frontend/` uniquement

## Audit initial (vérité forensique)

Les 7 pages (Dashboard, Search, Memories, Monitoring, Projects, Graph, Brain) avaient déjà le pattern `loading/errors/empty` correct. Les widgets (AutoSaveStatus, LatencyChart, ConversationsWidget, CodeChunksWidget, MemoriesStatsBar, EmbeddingsWidget) avaient leurs états. **3 trous réels** identifiés :

1. **`useBrain` : `error` n'était JAMAIS peuplé** — `safeFetch` avalait toutes les erreurs silencieusement. Le bandeau d'erreur de Brain.vue ne s'affichait jamais, même backend down.
2. **7 onglets Brain = pages blanches** : `vocabf`, `errors`, `decay`, `lsp`, `autosave`, `weights`, `search` — aucun composant monté dans le template. Plus `Events` : composant monté mais `data.events` toujours `[]` → NO DATA permanent.
3. **AlertRuleEditor : erreurs 100 % silencieuses** (console.error uniquement).

## Décisions (validées par l'utilisateur, 2026-08-08)

1. **Retirer les onglets fantômes** : `vocabf`, `errors`, `decay`, `lsp`, `autosave`, `weights`, `search` (aucun composant) **+ `Events`** (data.events jamais peuplé) → 10 onglets conservés : memories, code, alerts, metrics, cache, batch, graph, computed, memory-graph, consolidation.
2. **Retirer les données mortes de `useBrain`** : events, eventsCount, vocabfWords, indexingErrors, edgeWeights, edgeWeightsCount, searchResults, decayConfig, autosaveStats, memoryStats, graphStats, alertSummary + les fetches associés (`/events/cache/stats`, `/memories/decay/config`, `/autosave/stats`, `/alerts/summary`, `/memories/stats`).
3. **AlertRuleEditor : bandeau d'erreur + boutons désactivés** pendant les mutations.
4. **`useBrain` : erreur partielle aussi** — `error` peuplé si TOUS les endpoints échouent (backend down) OU si une partie seulement.
5. **Onglet Batch : brancher la vraie route** (`GET /api/v1/indexing/batch/status/{repository}`, vérifiée fonctionnelle) — décision review : `batchStatus` hardcodé null était le nouveau fantôme silencieux, mais contrairement à Events la route existe et fonctionne.

## Correctifs appliqués

| # | Fichier | Changement |
|---|---|---|
| 1 | `src/composables/useBrain.ts` | Compteur `fetchStats` (total/failed/failedEndpoints) dans `safeFetch` → peuple `error` (null si 0 échec, « Backend inaccessible » si tous, « X/Y endpoints en échec : liste » si partiel). BrainData réduit de 30 à 17 champs. 6 fetch principaux + 3 fetch graph/batch (conditionnés à `repos.length > 0`), tous avec label pour les messages d'erreur |
| 2 | `src/pages/Brain.vue` | Retrait de EventsTimeline (import + rendu), 3 configs d'onglets réduites, `eventsCount` retiré du count memory, `:data` retiré de BrainSidebar |
| 3 | `src/components/brain/GroupTabs.vue` | tabLabels + getTabCount réduits aux 10 onglets restants (labels `memory-graph`/`consolidation` ajoutés) |
| 4 | `src/components/brain/BatchStatus.vue` | Réécrit : mappe la réponse réelle (`status`, `processed_files`, `total_files`, `failed_files`, `current_batch`, `total_batches`, `progress_percent`) + mapping statuts backend→affichage SCADA |
| 5 | `src/components/brain/BrainSidebar.vue` | Prop `data` retiré (inutilisé) + bloc « event detail » retiré (type jamais émis après suppression d'EventsTimeline) |
| 6 | `src/components/brain/EventsTimeline.vue` | **Supprimé** |
| 7 | `src/components/AlertRuleEditor.vue` | Ref `error` + bandeau `alert-error` + `actionLoading` (id de la règle en cours) qui désactive NEW/EDIT/DEL/SAVE pendant les mutations, « SAVING... » sur le bouton SAVE |

## Critères d'acceptation

- [x] `pnpm vue-tsc -b --noEmit` : 0 erreur
- [x] `pnpm vitest run` : 29/29
- [x] `npx eslint .` : 0 erreur (4 warnings de qualité connus)
- [x] `pnpm build` : OK
- [x] Aucune référence résiduelle aux champs morts (grep vérifié : vide)
- [x] Le bandeau d'erreur de Brain s'affiche si backend down ou échec partiel
- [x] L'onglet Batch affiche les vraies données (statut d'indexation du premier repo)

## Notes de décision

- **Cohérence Events vs Batch** : Events a été retiré (la route de liste `POST /v1/events/filter/metadata` existe mais `data.events` n'était jamais branché et l'onglet n'apportait rien) ; Batch a été **branché** car la route GET existe et fournit une vraie valeur de monitoring. C'est la distinction « fantôme mort » vs « fonctionnalité débranchée ».
- Le retrait des 8 onglets ne supprime aucune page : Brain reste le hub, les onglets retirés sont récupérables via git.
- Les 4 warnings lint restants (vue/require-default-prop + vue/no-v-html) sont de la qualité volontaire, documentés dans le README.
