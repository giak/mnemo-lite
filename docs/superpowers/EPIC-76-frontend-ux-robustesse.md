# 🟢 EPIC-76 : Robustesse UX (F-06) — états vides/erreurs/chargements des composants

> **Status:** DONE
> **Priority:** P1 : dernière EPIC de la file frontend (F-06, après F-02 traité en EPIC-75)
> **Date:** 2026-08-08
> **Effort:** 2-3 h
> **Commit:** `a7e67fe` (9 fichiers, +177 / −156)
> **Scope:** `frontend/` uniquement

## Problem Statement

La file frontend initiale se terminait par **F-06 (robustesse UX)** : les composants doivent afficher des états vides, d'erreur et de chargement explicites. L'audit forensique a révélé que les 7 pages (Dashboard, Search, Memories, Monitoring, Projects, Graph, Brain) avaient **déjà** le pattern `loading/errors/empty` correct, ainsi que les widgets (AutoSaveStatus, LatencyChart, ConversationsWidget, CodeChunksWidget, MemoriesStatsBar, EmbeddingsWidget) et les 13 composants `brain/*` (états `NO DATA`).

**3 trous réels** subsistaient :

1. **`useBrain` : `error` n'était JAMAIS peuplé** — `safeFetch` avalait toutes les erreurs (retour de fallback) sans jamais écrire `error.value`. Le bandeau d'erreur de `Brain.vue` ne s'affichait donc **jamais**, même backend entièrement down. Silence total.
2. **8 onglets Brain = contenu vide** : `vocabf`, `errors`, `decay`, `lsp`, `autosave`, `weights`, `search` (aucun composant monté dans le template, clic = zone vide) + `events` (composant `EventsTimeline` monté mais `data.events` **toujours `[]`** dans `useBrain` → NO DATA permanent).
3. **`AlertRuleEditor` : erreurs 100 % silencieuses** — fetch/toggle/delete/save passaient tous par `console.error`, zéro retour visuel utilisateur.

## Décisions (validées par l'utilisateur, 2026-08-08)

| # | Question | Décision |
|---|---|---|
| 1 | 7 onglets sans composant | **Retirer de la config** (cohérent avec la directive « poubelle ») + retirer les données mortes et fetches associés |
| 2 | Onglet Events (composant monté mais data.events jamais peuplé) | **Retirer aussi** (même fantôme) — la route `POST /v1/events/filter/metadata` existe mais n'apportait rien à l'UI |
| 3 | AlertRuleEditor | **Bandeau d'erreur + boutons désactivés** pendant les mutations |
| 4 | `useBrain` : comment peupler `error` | **Erreur partielle aussi** : `error` affiché si TOUS les endpoints échouent (backend down) ET si une partie seulement |
| 5 | Onglet Batch (découvert en review : `batchStatus` hardcodé null) | **Brancher la vraie route** `GET /api/v1/indexing/batch/status/{repository}` (vérifiée fonctionnelle) — distinction « fantôme mort » vs « fonctionnalité débranchée » |

## Correctifs appliqués

| # | Fichier | Changement |
|---|---|---|
| 1 | `src/composables/useBrain.ts` | Compteur `fetchStats` (total/failed/failedEndpoints) incrémenté dans `safeFetch` → `error` peuplé à la fin du cycle : **null** si 0 échec, **« Backend inaccessible : N endpoints en échec »** si tous, **« X/Y endpoints en échec : liste (label + HTTP status) »** si partiel. `BrainData` réduit de 30 à 17 champs (12 champs morts retirés : events, eventsCount, vocabfWords, indexingErrors, edgeWeights, edgeWeightsCount, searchResults, decayConfig, autosaveStats, memoryStats, graphStats, alertSummary). 5 fetches morts retirés (`/events/cache/stats`, `/memories/decay/config`, `/autosave/stats`, `/alerts/summary`, `/memories/stats`). 6 fetch principaux + 3 fetch graph/batch (conditionnés à `repos.length > 0`), chacun avec label pour les messages d'erreur |
| 2 | `src/pages/Brain.vue` | Retrait de `EventsTimeline` (import + rendu), 3 configs d'onglets réduites (memory : 4 → 2, system : 8 → 4, intelligence : 6 → 4), `eventsCount` retiré du count du groupe memory, `:data` retiré de `BrainSidebar` |
| 3 | `src/components/brain/GroupTabs.vue` | `tabLabels` + `getTabCount` réduits aux 10 onglets restants, labels `memory-graph` et `consolidation` ajoutés |
| 4 | `src/components/brain/BatchStatus.vue` | Réécrit : mappe la réponse réelle (`status`, `processed_files`, `total_files`, `failed_files`, `current_batch`, `total_batches`, `progress_percent`) + mapping statuts backend (`pending`/`processing`/`completed`/`failed`/`not_found`) vers affichage SCADA |
| 5 | `src/components/brain/BrainSidebar.vue` | Prop `data` retiré (inutilisé) + bloc « event detail » retiré (type jamais émis après suppression d'EventsTimeline) |
| 6 | `src/components/brain/EventsTimeline.vue` | **Supprimé** (récupérable via git) |
| 7 | `src/components/AlertRuleEditor.vue` | Ref `error` + bandeau `alert-error` + `actionLoading` (id de la règle en cours de mutation) qui désactive NEW/EDIT/DEL/SAVE, « SAVING... » sur le bouton SAVE |

## Critères d'acceptation

- [x] `pnpm vue-tsc -b --noEmit` : 0 erreur
- [x] `pnpm vitest run` : 29/29
- [x] `npx eslint .` : 0 erreur (4 warnings de qualité connus)
- [x] `pnpm build` : OK (warning chunk size g6 non bloquant, préexistant)
- [x] Aucune référence résiduelle aux champs morts (grep vérifié : vide)
- [x] Le bandeau d'erreur de Brain s'affiche si backend down ou échec partiel
- [x] L'onglet Batch affiche les vraies données (statut d'indexation du premier repo)

## État final (2026-08-08, mesuré)

- `pnpm vue-tsc -b --noEmit` : **0 erreur**
- `pnpm vitest run` : **29/29**
- `npx eslint .` : **0 erreur** (4 warnings : `vue/require-default-prop` + `vue/no-v-html`, qualité volontaire)
- `pnpm build` : **OK**
- `git show --stat a7e67fe` : 9 fichiers, 177 insertions, 156 suppressions, dont 1 suppression (EventsTimeline.vue)

### Onglets Brain après EPIC-76 (10)

- **memory** : memories, code
- **system** : alerts, metrics, cache, batch
- **intelligence** : graph, computed, memory-graph, consolidation

## Review (code-reviewer-deepseek-flash)

**1 point critique trouvé en review, corrigé dans le même cycle** : l'onglet `batch` était le nouveau fantôme silencieux — `useBrain` hardcodait `batchStatus: null` sans fetch. Contrairement à Events (route de liste non branchée, onglet retiré), la route de statut batch existe et fonctionne : décision de **brancher** (`GET /api/v1/indexing/batch/status/{repo}`), `BatchStatus.vue` réécrit avec mapping backend.

**Verdict reviewer sur le reste** : compteur `fetchStats` fiable (calcul final exécuté après le bloc graph conditionnel, pas de fausse erreur si `repos` vide) ; retrait des champs morts sans risque (typecheck 0 + greps confirment) ; retraits Brain.vue/GroupTabs/BrainSidebar propres.

## Notes de décision

- **Cohérence Events vs Batch** : Events retiré (route de liste jamais branchée, zéro valeur UI) ; Batch branché (route GET existante, vraie valeur de monitoring). La distinction : « fantôme mort » vs « fonctionnalité débranchée ».
- Le retrait des 8 onglets ne supprime aucune page : Brain reste le hub, les onglets retirés sont récupérables via git.
- La décision « erreur partielle aussi » rend le bandeau d'erreur de Brain **verbeux** : un endpoint legacy qui échoue en permanence (ex. `HTTP 404`) affichera le bandeau à chaque cycle de 30 s. C'est le choix assumé de l'utilisateur (plus de transparence que le silence).
- Les 4 warnings lint restants (`vue/require-default-prop` + `vue/no-v-html`) sont de la qualité volontaire, documentés dans le README frontend.
