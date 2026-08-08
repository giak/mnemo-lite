# 🧭 EPIC-78 : Knowledge Explorer — consulter le socle Truth Engine (faits, enquêtes, articles, relations)

> **Status:** IN_PROGRESS — T0-T5 DONE (2026-08-08) ; reste T6 recherche avancée
> **Priority:** P1 : le besoin central « voir ce qui est lié » est aujourd'hui techniquement impossible
> **Date:** 2026-08-08
> **Effort:** 8-12 h (T0/T1 backend + T2-T6 frontend)
> **Scope:** `api/` (T0/T1) + `frontend/` (T2-T6)

## Diagnostic forensique du socle (mesuré en base, 2026-08-08)

**Volumétrie** (39 702 mémoires) : conversation 33 629 · investigation **4 830** · note 919 · reference 99 · quintessence **94** · article **52** · decision 47 · task 2.

**Socle Truth Engine** = project_id `7b9b2fbf-497f-4f23-a924-8a71c90fdc31` (**3 604 mémoires**), taggé : `kernel` (193), `status:CONFIRME` (169), `fact-check`, `circuit-c*`, `piste*-kernel`, `polarite-*`, `project:truth-engine`, `article:impossible-rassemblement`, sujets (`14-juillet-2026` ×318, `ingerences-russes`, `souverainete`…).

**3 blocages backend constatés** :
1. **Memory Graph cassé** : `GET /api/v1/memories/graph` renvoyait « Failed to retrieve memory ». **Cause racine réelle** : `memories_routes` (`GET /{memory_id}`) est monté **avant** les routeurs graph dans `main.py` → le segment unique `graph` était capté comme un `memory_id` (les 2 `GET /graph` déclarés par `memory_relationship_routes` l.106 et `memory_graph_routes` l.30 étaient tous deux masqués). **Corrigé en T0.**
2. **Relations jamais peuplées** : table `memory_relationships` = **0 ligne** (le `compute-relationships` existe mais le worker d'extraction d'entités n'a jamais tourné). → contourné par le proxy tags (T1), le pipeline reste un chantier séparé.
3. **Consolidation** : `/consolidation/suggestions` = 0 groupes.

**Déjà disponible** : `GET /api/v1/memories/search` (filtres `tags` logique ET + `memory_type`), `GET /memories/recent`, `GET /memories/stats`, `G6Graph.vue` réutilisable, nav générée depuis le router (`meta.navLabel`/`navGroup`), client API unique `src/api/client.ts`.

## Décisions (validées par l'utilisateur, 2026-08-08)

1. **Relations par proxy tags/entités** (pas de pipeline compute à réparer) : relations calculées à la volée par partage de tags/entités communes — fonctionne immédiatement sur les 3 604 mémoires TE déjà taggées.
2. **Nouvelle page Explorer** dédiée (groupe Data de la nav), lieu unique de consultation du corpus.
3. **Backend + frontend ensemble** dans la même EPIC (stories).

## Vision produit

### ✅ T0 — Réparer le Memory Graph (backend, DONE)
**Cause racine** : `GET /api/v1/memories/graph` (1 segment) était capté par `GET /{memory_id}` de `memories_routes`, monté avant les routeurs graph dans `main.py`. **Fix** : (1) retrait du `GET /graph` dupliqué/obsolète de `memory_relationship_routes` (la version riche de `memory_graph_routes` est la bonne) ; (2) montage de `memory_relationship_routes` + `memory_graph_routes` **avant** `memories_routes`. **Validé live** : `/graph` renvoie `{nodes:[],edges:[],total_nodes:0,total_edges:0}` (structure valide ; table `memory_relationships` toujours vide, à peupler par le pipeline ou le proxy). Zéro régression (26/26 tests adjacents).

### ✅ T1 — Endpoint relations + agrégats socle (backend, DONE)
Nouveau routeur `api/routes/explorer_routes.py` (SQL direct, pattern `memory_graph_routes`, zéro service dédié) :
- **`GET /api/v1/memories/{id}/related-by-tags`** (proxy) : candidats partageant ≥1 tag (insensible à la casse, `lower()` — la base a des tags mixtes `status:CONFIRME`/`status:confirme`), score = somme des tags partagés pondérés (sujet = 2, technique = 1), `min_shared` + `limit`. Limite assumée : candidats = 200 plus récents (biais de récence documenté). **Validé live** : sur la mémoire parrainages → ARCOM, SREN, divergence 2022, score 6.
- **`GET /api/v1/memories/explorer/stats`** (agrégats socle) : `by_type`, `status.confirmed/fact_checked/total`, `top_subjects` (filtre anti-bruit PRÉCIS : exclusions `session:/date:/source-/verifie-/status:/project:/memory:/trace:`, versions `t[0-9]+|v[0-9]+` via `!~*`, bruit corpus livre) , `timeline` par mois. Filtres : `project_id` optionnel (défaut = tout le socle, conversations exclues — les 153 `status:CONFIRME` récents sont hors project_id). **Validé live** : 5 957 éléments (4 808 investigations, 94 quintessences, 52 articles), 153 CONFIRME, sujets réels (14-juillet-2026, france, macron, iran, iceberg-max…).
- **`GET /api/v1/memories/explorer/tree?subject=X`** (arborescence) : sujet → `investigations` / `facts` (quintessences + fact-check) / `others`. **Validé live** : `14-juillet-2026` = 318 éléments (256 investigations).

### ✅ T2 — Page Socle (frontend, DONE)
Nouvelle page `src/pages/Explorer.vue` (route `/explorer`, groupe Data, nav auto depuis le router) avec 3 onglets : **Socle** (implémenté) / **Explorer** (T3) / **Relations** (T4). Onglet Socle :
- **4 cartes de stats** : total socle, enquêtes, fiches internes (quintessences), articles publiés.
- **Distribution par type** : barres proportionnelles + compteurs par `memory_type` (icônes + couleurs par type).
- **Couverture factuelle** : barres de progression `status:CONFIRME` et `fact-check` sur le total du socle, avec pourcentages.
- **Top sujets** : liste cliquable (barres + compteurs) → clic = sélection du sujet + bascule sur l'onglet Explorer (prêt pour T3).
- **Timeline des investigations** : barres mensuelles (compteur au survol, libellés YY-MM).
- Fichiers : `src/types/explorer.ts` (types), `src/api/explorer.ts` (`getExplorerStats`), test `src/api/explorer.test.ts` (2 tests).
- **Validé** : vue-tsc 0 erreur · vitest 31/31 · eslint 0 erreur · build OK · rendu navigateur vérifié (zéro erreur console).

### ✅ T3 — Explorer arborescence (frontend, DONE)
Onglet **Explorer** de `Explorer.vue` :
- **Sélecteur de sujet** : champ de saisie libre (tag) + chips des 12 top sujets (depuis les stats Socle) ; l'input libre est le cas d'usage principal (ex. `ingerences-russes` hors top 25).
- **Arborescence 3 sections** : `Enquêtes` (investigations) / `Faits vérifiés` (quintessences + fact-check) / `Autres`, avec compteurs par section, barre de synthèse (total éléments), badges tags (3 max), date, état vide explicite si le tag ne matche rien.
- **Détail de l'élément** (préfiguration T5) : panneau avec type, date, tous les tags, bouton copier l'ID (toast).
- **Backend** : `tree` rendu **insensible à la casse** (`lower(t) = lower(:subject)`, aligné sur `related-by-tags`) pour éviter les faux négatifs du sélecteur ; validé live (318 éléments avec casse exacte et différente), pytest 8/8.
- Composant `src/components/TreeItemRow.vue` (DRY, 3 sections). Tests `getExplorerTree` : parsing, URL-encoding, erreur HTTP.
- **Validé** : vue-tsc 0 erreur · vitest 34/34 · eslint 0 erreur · build OK · rendu Socle navigateur vérifié.

### ✅ T4 — Graphe de relations (frontend, DONE)
Onglet **Relations** de `Explorer.vue`, branché sur `/api/v1/memories/{id}/related-by-tags` :
- **Sélecteur de mémoire source** : recherche sémantique par titre (POST `/memories/search`, 8 résultats cliquables) + chips rapides depuis le tree du sujet courant.
- **Graphe G6 réutilisé** (`G6Graph`) : nœud central = source, satellites = relations (labels = titres, couleurs = type), arêtes source→relation (`type: related`). Les types mémoires ne matchent pas Class/Function/Method → la garde EPIC-71 garde tous les nœuds.
- **Filtres** : `min_shared` (1-3) et `limit` (10/20/50), rechargement auto via watch ; **liste des relations** (score coloré ≥ 4, tags partagés max 4) cliquable → la relation devient la nouvelle source (exploration en saut de puce).
- **Robustesse** : garde anti-course (`relatedSeq`) pour les changements rapides de source ; états loading/error/empty explicites (aucune relation au seuil choisi).
- **Tests** : `getRelatedByTags` (URL + parsing) et `searchSourceMemories` (POST + mapping) — 4 nouveaux tests.
- **Limitations assumées** (review) : G6Graph affiche du chrome code-oriented (légende Classes/Functions, stats Complexity) — garde EPIC-71 assure l'affichage, un `memoryMode` restera propre plus tard ; le clic nœud ne re-propage pas à la page (re-centrage via la liste) ; `created_at` absent du hop (date vide dans la barre source).
- **Validé** : vue-tsc 0 erreur · vitest 38/38 · eslint 0 erreur · build OK.

### ✅ T5 — Fiche mémoire enrichie (frontend, DONE)
Nouveau composant `src/components/MemoryDetailPanel.vue`, branché dans l'onglet Explorer (clic sur un élément du tree) :
- **Contenu markdown** via `useMarkdown` (classe `scada-markdown`, highlight.js), chargé par `GET /memories/{id}` ; le titre du nœud sert de placeholder pendant le chargement.
- **Tags colorés par rôle** (insensible à la casse) : `status:CONFIRME` vert · `status:` ambre · `project:` cyan · `article:` bleu · `circuit:` orange · `piste:` violet · `fact-check` vert · `date:/session:/source-` gris.
- **Entités / concepts** : sections conditionnelles (non affichées si vides). **Backend étendu** : `GET /memories/{id}` expose désormais les colonnes `entities`/`concepts` (text[] en base, jamais exposées auparavant).
- **Bloc « Liées »** : relations par proxy de tags partagés (`/related-by-tags`, limit 8), score coloré, clic = re-centrage de la fiche (emit `select-memory`).
- Meta : type, date, auteur, badge embedding, bouton copier l'ID (feedback inline).
- **Robustesse** : séquence anti-course (détail puis relations, garde `seq`) ; états loading/error. **Tests** : `getMemoryDetail` (parsing + 404).
- **Review** : prop `title` réutilisée en placeholder de chargement, `tagRole` normalisé `toLowerCase()`, CSS `fade` mort retiré, `circuit:` → orange.
- **Validé** : vue-tsc 0 erreur · vitest 40/40 · eslint 0 erreur · build OK.

### T6 — Recherche avancée (frontend, ~2 h)
Extension de Search : filtres combinés (type + tags + statut + période) en s'appuyant sur le search existant (`tags` ET + `memory_type`), résultats groupés par type.

## Critères d'acceptation

- [x] `GET /api/v1/memories/graph` renvoie une structure valide sans erreur (T0 ; nodes/edges vides tant que la table n'est pas peuplée)
- [x] `related-by-tags` renvoie les top-N liées pour une fiche TE quelconque (validé : ARCOM/SREN/divergence 2022 sur la mémoire parrainages)
- [x] Page Explorer : onglets Socle (T2), Explorer (T3), Relations (T4) + fiche enrichie (T5) livrés ; recherche avancée T6 à venir
- [x] `pnpm vue-tsc -b --noEmit` : 0 erreur · vitest 40/40 · eslint 0 erreur · build OK (frontend, T2-T5)
- [x] Tests backend (pytest) pour les 3 nouveaux endpoints : `tests/routes/test_explorer_routes.py` **8/8** + zéro régression adjacente (26/26)

## Notes de décision

- **Proxy vs pipeline compute** : le proxy par tags est choisi car le pipeline d'extraction d'entités n'a jamais produit de données (0 ligne). Le proxy donne une valeur immédiate et correcte pour le cas TE (les tags sont le vocabulaire de vérité du KERNEL). Le pipeline compute reste un chantier séparé (EPIC-70 est déjà parké pour le volet code).
- **Conversation = bruit** : les 33 629 conversations sont exclues du socle par défaut (types + project_id TE) ; bascule « tout voir » disponible.
- **Réutilisation maximale** : G6Graph, useMarkdown, client API unique, patterns loading/errors/empty, nav auto depuis le router. Aucun nouveau pattern.
