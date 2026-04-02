# EPIC-33: Design Polish & Visual Consistency

**Status**: DRAFT | **Created**: 2026-04-02 | **Effort**: ~12 points | **Stories**: 8

**Source**: Playwright UI audit — screenshots captured for all 11 pages

---

## Context

L'audit visuel via Playwright a révélé des incohérences de design et des problèmes UX
sur plusieurs pages. Le style SCADA est présent mais pas uniformément appliqué.

### État actuel

| Page | Problèmes identifiés |
|------|---------------------|
| **Navbar** | Badge "99+" permanent, liens trop serrés, pas de regroupement visuel |
| **Dashboard** | Footer discret, cartes sans bordures, emoji 🔄 dans boutons |
| **Projects** | Colonnes LANGUAGES vides, barres de couverture invisibles à 0% |
| **Monitoring** | Bouton "?" non SCADA, descriptions d'alertes trop petites |
| **Alerts** | Pas de pagination, boutons ACK trop petits, filtres mal alignés |
| **Expanse Memory** | Trop dense, pas d'espacement, tags sans couleurs par groupe |
| **Logs** | LED status montre DOWN pour DB/Redis (services sains via API) |
| **Brain** | Icônes emoji (🧠, 💻, 📅, 📖) au lieu de LED SCADA |

---

## Stories

### Story 33.1: Navbar — Regroupement visuel et badge dynamique
**Priority**: P1 | **Effort**: 1 pt | **Value**: High

**Problèmes** :
- Badge "99+" affiché en permanence même quand il n'y a pas d'alertes
- Liens trop serrés, pas de séparation visuelle entre les groupes
- Pas de hover states cohérents

**Solution** :
- Grouper les liens avec des séparateurs visuels :
  - `DASHBOARD | SEARCH | MEMORIES` (Data)
  - `PROJECTS | EXPANSE | EXP. MEMORY` (Cognitive)
  - `MONITORING | ALERTS` (Ops)
  - `BRAIN | GRAPH | LOGS` (Tools)
- Badge alertes : afficher uniquement si `activeAlertCount > 0`
- Ajouter des hover states avec transition douce

**Fichiers** :
- `frontend/src/components/Navbar.vue`

---

### Story 33.2: Dashboard — Améliorer les cartes et le footer
**Priority**: P2 | **Effort**: 1 pt | **Value**: Medium

**Problèmes** :
- Footer "AUTO-REFRESH ENABLED" trop discret
- Cartes sans bordures visuelles distinctes
- Emoji 🔄 dans le bouton REFRESH

**Solution** :
- Ajouter des bordures `border border-slate-700` aux DashboardCards
- Footer avec style `scada-panel` cohérent
- Remplacer 🔄 par icône SVG ou texte "REFRESH"

**Fichiers** :
- `frontend/src/pages/Dashboard.vue`
- `frontend/src/components/DashboardCard.vue`

---

### Story 33.3: Projects — Corriger les colonnes vides et barres de couverture
**Priority**: P2 | **Effort**: 1.5 pts | **Value**: Medium

**Problèmes** :
- Colonnes LANGUAGES vides pour certains projets
- Barres de couverture à 0% invisibles
- Boutons d'actions trop serrés

**Solution** :
- Afficher "—" au lieu de vide pour les langues manquantes
- Barre de couverture : minimum 4px visible même à 0%
- Espacement entre boutons d'action

**Fichiers** :
- `frontend/src/pages/Projects.vue`

---

### Story 33.4: Monitoring — Harmoniser le style SCADA
**Priority**: P2 | **Effort**: 1 pt | **Value**: Medium

**Problèmes** :
- Bouton "?" pour l'aide — pas cohérent SCADA
- Descriptions d'alertes trop petites (`text-[10px]`)
- Emoji 🔄 dans le bouton REFRESH

**Solution** :
- Remplacer "?" par bouton "AIDE" style SCADA
- Augmenter taille des descriptions à `text-xs`
- Remplacer 🔄 par texte

**Fichiers** :
- `frontend/src/pages/Monitoring.vue`

---

### Story 33.5: Alerts — Pagination et boutons ACK
**Priority**: P1 | **Effort**: 1.5 pts | **Value**: High

**Problèmes** :
- Pas de pagination quand il y a 100+ résultats
- Boutons ACK trop petits (`text-[10px]`)
- Filtres mal alignés

**Solution** :
- Ajouter pagination avec `currentPage`, `pageSize=20`
- Boutons ACK : `text-xs` avec padding confortable
- Aligner les filtres avec `flex-wrap gap-2`

**Fichiers** :
- `frontend/src/pages/Alerts.vue`

---

### Story 33.6: Expanse Memory — Espacement et couleurs par groupe
**Priority**: P2 | **Effort**: 2 pts | **Value**: Medium

**Problèmes** :
- Trop dense, besoin de plus d'espacement entre les sections
- Tags sans couleurs distinctes par groupe (PERMANENT, LONG TERME, etc.)
- Modal détail : contenu trop grand, pas de wrap

**Solution** :
- Ajouter `gap-4` entre les sections de taxonomie
- Couleurs par groupe :
  - PERMANENT : `border-green-600 bg-green-900/30`
  - LONG TERME : `border-cyan-600 bg-cyan-900/30`
  - MOYEN TERME : `border-yellow-600 bg-yellow-900/30`
  - COURT TERME : `border-red-600 bg-red-900/30`
- Modal : `max-h-[60vh]` avec scroll pour le contenu

**Fichiers** :
- `frontend/src/pages/ExpanseMemory.vue`

---

### Story 33.7: Logs — Corriger le status des services
**Priority**: P2 | **Effort**: 1 pt | **Value**: Medium

**Problèmes** :
- La page Logs montre DB: DOWN, Redis: DOWN alors que les services sont sains
- Les liens OpenObserve pointent vers des URLs qui n'existent pas

**Solution** :
- Utiliser le même endpoint health que le Dashboard
- Masquer les liens OpenObserve si le service n'est pas accessible
- Ajouter un message "OpenObserve non configuré" au lieu de liens cassés

**Fichiers** :
- `frontend/src/pages/Logs.vue`
- `frontend/src/composables/useLogs.ts` (nouveau)

---

### Story 33.8: Brain — Remplacer les emojis par des LED SCADA
**Priority**: P3 | **Effort**: 2 pts | **Value**: Low

**Problèmes** :
- Icônes emoji (🧠, 💻, 📅, 📖) au lieu de LED SCADA
- Compteurs affichent "0" partout (API non implémentée)
- Layout déséquilibré

**Solution** :
- Remplacer les emojis par des `scada-led` avec des couleurs
- Ajouter un état "API non disponible" au lieu de "0"
- Réorganiser le layout en grille 3 colonnes équilibrée

**Fichiers** :
- `frontend/src/pages/Brain.vue`

---

## Ordre d'exécution

```
Phase 1 (Quick Wins, ~3h)
  33.1 → Navbar regroupement + badge
  33.5 → Alerts pagination + boutons
  33.3 → Projects colonnes + barres

Phase 2 (Harmonisation, ~4h)
  33.2 → Dashboard cartes + footer
  33.4 → Monitoring style SCADA
  33.6 → Expanse Memory espacement + couleurs
  33.7 → Logs status services

Phase 3 (Polish, ~2h)
  33.8 → Brain emojis → LED
```

---

## Critères de complétion

- [ ] Navbar avec regroupement visuel et badge dynamique
- [ ] Dashboard avec cartes bordurées et footer cohérent
- [ ] Projects avec colonnes complètes et barres visibles
- [ ] Monitoring avec bouton aide SCADA
- [ ] Alerts avec pagination et boutons ACK confortables
- [ ] Expanse Memory avec espacement et couleurs par groupe
- [ ] Logs avec status services corrects
- [ ] Brain sans emojis, avec LED SCADA
- [ ] 0 emoji restants dans l'UI (sauf contenu utilisateur)
- [ ] Tous les boutons utilisent `scada-btn` variants
- [ ] Playwright audit : 11/11 pages OK, 0 erreurs visuelles

---

## Métriques de succès

| Métrique | Avant | Après |
|----------|-------|-------|
| Pages OK (Playwright) | 8/11 | 11/11 |
| Emojis dans l'UI | 12+ | 0 |
| Boutons non-SCADA | 8+ | 0 |
| Colonnes vides | 3 | 0 |
| Badges incorrects | 1 (99+) | 0 |
