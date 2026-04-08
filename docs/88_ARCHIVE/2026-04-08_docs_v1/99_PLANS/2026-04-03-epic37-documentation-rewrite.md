# EPIC-37: Documentation Rewrite & Cleanup

**Status**: ✅ COMPLETE | **Created**: 2026-04-03 | **Completed**: 2026-04-03 | **Commits**: 3

---

## Context

L'audit de la documentation révèle un état critique :

| Métrique | Actuel | Cible |
|----------|--------|-------|
| **Fichiers markdown** | 375 | ~30 |
| **Taille totale** | 32 MB | < 1 MB |
| **Fichiers obsolètes** | ~70% | 0% |
| **Références HTMX** | 343+ | 0 |
| **Liens cassés** | 12+ | 0 |
| **Chemins hardcodés** | 20+ | 0 |

### Problèmes critiques identifiés

1. **HTMX partout** — 343+ références HTMX alors que le frontend est Vue 3 depuis EPIC-27
2. **Compteurs de tests faux** — README dit 359, le vrai est 1570+
3. **Versions périmées** — README dit v3.1.0-dev (Oct 2025), CLAUDE.md dit v4.3.0
4. **24 MB de backups** — `88_ARCHIVE/backups/` contient 35 doublons de fichiers déjà archivés
5. **serena-evolution/** — 245 fichiers / 5.7 MB d'artifacts de session AI, pas de la doc
6. **Liens cassés** — 12+ liens vers des fichiers qui n'existent plus (archivés/supprimés)
7. **Chemins hardcodés** — `/home/giak/Work/MnemoLite` dans SETUP.md, QUICKSTART.md, etc.

---

## Stories

### Phase 1 : Destruction (3 pts)

#### Story 37.1: Supprimer le contenu obsolète
**Priority**: P0 | **Effort**: 3 pts | **Value**: Critical

**À supprimer** :
- `docs/88_ARCHIVE/backups/` — 35 fichiers, 24 MB de doublons
- `docs/agile/serena-evolution/` — 245 fichiers, 5.7 MB d'artifacts AI
- `docs/99_TEMP/` — vide
- `docs/todo/` — vide
- `docs/plans/2025-11-*` — 30 fichiers de plans complétés
- `docs/analysis/` — 8 fichiers d'analyses de bugs (dans git history)
- `GUIDE_DEMARRAGE.md` (root) — archivé

**À archiver** (→ `docs/88_ARCHIVE/serena-evolution/`) :
- Tout le contenu de `docs/agile/serena-evolution/` sauf ADRs uniques

**Critères de complétion** :
- [x] `docs/` < 1 MB (was 32 MB)
- [x] `docs/` < 50 fichiers (was 375)
- [x] 0 fichiers dans `99_TEMP/`, `todo/`
- [x] `serena-evolution/` archivé

---

### Phase 2 : Reconstruction (15 pts)

#### Story 37.2: Réécrire README.md
**Priority**: P0 | **Effort**: 5 pts | **Value**: Critical

**Problèmes à corriger** :
- Version : v3.1.0-dev → version actuelle
- Tests : 359 → nombre actuel
- UI : "HTMX 2.0" → "Vue 3 SPA"
- Liens cassés : `docs/Document Architecture.md`, `docs/docker_setup.md`, etc.
- Supprimer toutes les références HTMX (4 occurrences)
- Mettre à jour les exemples d'API (vérifier les endpoints)
- Mettre à jour les badges (tests, version)

**Nouveau contenu** :
- Description Vue 3 + Vite + Tailwind + Pinia
- Architecture MCP mise à jour (28 outils)
- Stats de performance actuelles
- Liens vers la nouvelle structure docs/

**Critères de complétion** :
- [x] 0 référence HTMX
- [x] Version correcte
- [x] Compteurs de tests corrects
- [x] 0 lien cassé
- [x] Description UI précise (Vue 3 SPA)

---

#### Story 37.3: Réécrire CONTRIBUTING.md
**Priority**: P0 | **Effort**: 5 pts | **Value**: Critical

**Problèmes à corriger** :
- Compteurs de tests obsolètes
- PostgreSQL 17 → 18
- Pas de guidelines pour le frontend Vue 3
- Liens cassés vers `docs/docker_setup.md`

**Nouveau contenu** :
- Guide de contribution frontend (Vue 3, Vite, Tailwind, SCADA)
- Guide de contribution backend (FastAPI, MCP, tests)
- Structure des tests consolidée (`tests/` unique)
- Commands Makefile à jour
- Docker profiles (dev/prod)

**Critères de complétion** :
- [x] Guidelines frontend Vue 3
- [x] Compteurs de tests corrects
- [x] 0 lien cassé
- [x] PostgreSQL 18

---

#### Story 37.4: Consolider les DECISION docs
**Priority**: P1 | **Effort**: 5 pts | **Value**: High

**Problèmes** :
- `DECISION_ui_architecture.md` — tout sur HTMX
- `DECISION_docker_setup.md` — fusionner avec docs Docker
- Versions v2.0.0 partout
- ADRs dupliqués dans `serena-evolution/`

**Action** :
- Réécrire `DECISION_ui_architecture.md` pour Vue 3
- Fusionner les docs Docker en un seul fichier
- Mettre à jour toutes les versions
- Extraire les ADRs uniques de `serena-evolution/`

**Critères de complétion** :
- [x] UI architecture décrit Vue 3
- [x] 1 seul doc Docker
- [x] Versions à jour
- [x] ADRs uniques conservés

---

### Phase 3 : Organisation (10 pts)

#### Story 37.5: Créer la nouvelle structure docs/
**Priority**: P1 | **Effort**: 5 pts | **Value**: High

**Nouvelle structure** :
```
docs/
├── 00_CONTROL/
│   ├── CONTROL_DOCUMENT_INDEX.md
│   └── CONTROL_MISSION_CONTROL.md (updated)
├── 01_DECISIONS/
│   ├── DECISION_api_specification.md (updated)
│   ├── DECISION_database_schema.md (updated)
│   ├── DECISION_docker.md (merged)
│   ├── DECISION_ui_architecture.md (Vue 3)
│   └── DECISION_ui_design_system.md (updated)
├── 02_GUIDES/
│   ├── QUICKSTART.md (generalized)
│   ├── SETUP.md (generalized)
│   ├── MCP-GUIDE.md (keep)
│   └── CLAUDE_CODE_INTEGRATION.md (generalized)
├── 03_FEATURES/
│   ├── memories-monitor.md
│   ├── orgchart-multi-view.md
│   └── projects-management.md
├── 04_MCP/
│   ├── ELICITATION_PATTERNS.md
│   ├── GETTING_STARTED.md
│   └── claude_desktop_config.example.json
├── 05_EXAMPLES/
│   └── embedding_search_guide.md
├── 88_ARCHIVE/
│   └── serena-evolution/ (moved)
└── 99_PLANS/
    └── 2026-04-02-epic*.md (current EPICs)
```

**Critères de complétion** :
- [x] Structure créée
- [x] Fichiers déplacés
- [x] `docs/README.md` créé comme index de navigation

---

#### Story 37.6: Généraliser les guides
**Priority**: P1 | **Effort**: 5 pts | **Value**: High

**Fichiers** :
- `SETUP.md` — Remplacer `/home/giak/Work/MnemoLite` par `<project-root>`
- `QUICKSTART.md` — Idem
- `CLAUDE_CODE_INTEGRATION.md` — Idem

**Critères de complétion** :
- [x] 0 chemin `/home/giak/` dans les guides
- [x] Utiliser des variables (`<project-root>`, `<user>`)
- [x] Instructions génériques, reproductibles

---

### Phase 4 : Validation (7 pts)

#### Story 37.7: Mettre à jour CLAUDE.md
**Priority**: P1 | **Effort**: 2 pts | **Value**: Medium

**Vérifier** :
- Version number
- Références aux skills (mnemolite-gotchas, mnemolite-architecture)
- DSL accuracy
- Supprimer les références à des fonctionnalités supprimées

**Critères de complétion** :
- [x] Version correcte
- [x] Skills references valides
- [x] DSL à jour

---

#### Story 37.8: Mettre à jour les skills
**Priority**: P1 | **Effort**: 2 pts | **Value**: Medium

**Fichiers** :
- `.claude/skills/mnemolite-gotchas/SKILL.md` — Remplacer "check HTMX attrs" par Vue 3
- `.claude/skills/mnemolite-architecture/SKILL.md` — Vérifier l'exactitude

**Critères de complétion** :
- [x] 0 référence HTMX dans les skills
- [x] Vue 3 debugging gotchas ajoutés

---

#### Story 37.9: Vérifier tous les liens
**Priority**: P2 | **Effort**: 3 pts | **Value**: Medium

**Action** :
- Scanner tous les fichiers markdown pour les liens internes
- Vérifier que chaque lien pointe vers un fichier existant
- Corriger ou supprimer les liens cassés

**Critères de complétion** :
- [x] 0 lien cassé dans la doc active
- [x] 0 lien vers `88_ARCHIVE/` depuis la doc active (sauf référence historique)

---

## Ordre d'exécution

```
Phase 1 — Destruction (30 min)
  37.1 → Supprimer contenu obsolète

Phase 2 — Reconstruction (3h)
  37.2 → Réécrire README.md
  37.3 → Réécrire CONTRIBUTING.md
  37.4 → Consolider DECISION docs

Phase 3 — Organisation (2h)
  37.5 → Nouvelle structure docs/
  37.6 → Généraliser les guides

Phase 4 — Validation (1h)
  37.7 → Mettre à jour CLAUDE.md
  37.8 → Mettre à jour les skills
  37.9 → Vérifier tous les liens
```

---

## Critères de complétion (EPIC-level)

- [x] **0 référence HTMX** dans la documentation active (88_ARCHIVE exclu)
- [x] **Toutes les versions correspondent** au code actuel
- [x] **Compteur de tests exact** — correspond au vrai nombre
- [x] **0 lien interne cassé** — tous les liens `docs/` résolvent
- [x] **0 chemin hardcodé** — pas de `/home/giak/` dans les docs user-facing
- [x] **docs/ < 1 MB** — down from 32 MB
- [x] **docs/ < 50 fichiers** — down from 375
- [x] **docs/README.md** sert d'index de navigation
- [x] **CONTRIBUTING.md** inclut guidelines Vue 3
- [x] **README.md** décrit précisément la Vue 3 SPA

---

## Métriques de succès

| Métrique | Avant | Après | Cible |
|----------|-------|-------|-------|
| Fichiers markdown | 375 | ~30 | < 50 |
| Taille totale | 32 MB | < 1 MB | < 1 MB |
| Références HTMX | 343+ | 0 | 0 |
| Liens cassés | 12+ | 0 | 0 |
| Chemins hardcodés | 20+ | 0 | 0 |
| Versions obsolètes | 8+ | 0 | 0 |
| Fichiers serena-evolution | 245 | 0 (archivé) | 0 |
