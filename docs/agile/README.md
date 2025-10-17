# 📚 Documents Agile - Historique & Documentation Actuelle

## 📋 Structure de la Documentation

Ce dossier contient **deux catégories** de documents :

### 🟢 **Développements Récents (ACTUELS - 2025-10)**
- **EPIC-06**: Code Intelligence (Backend) - ✅ **100% COMPLET** (74 pts, Oct 2025)
- **EPIC-07**: Code Intelligence UI (Frontend) - ✅ **100% COMPLET** (41 pts, Oct 2025)

### 🟡 **Archive Historique (Q1-Q2 2025)**
- EPIC-01 à EPIC-05 : Phase initiale du développement

> **⚠️ AVERTISSEMENT ARCHIVE HISTORIQUE**: Les documents EPIC-01 à EPIC-05 capturent l'historique du développement de MnemoLite (Q1-Q2 2025).
> Ils peuvent contenir des informations obsolètes qui ne reflètent plus l'implémentation actuelle.

## 🕰️ Contexte Historique (EPIC 01-05)

Ces documents ont été créés pendant la phase initiale de développement du projet (Q1-Q2 2025) et documentent :
- Les décisions d'architecture prises pendant la migration de OpenAI vers les embeddings locaux
- Les user stories et epics de la phase de développement agile initial
- Les défis techniques rencontrés et leurs résolutions

## ⚠️ Informations Potentiellement Obsolètes (EPIC 01-05 uniquement)

Les documents **d'archive historique** (EPIC-01 à EPIC-05) peuvent contenir des références obsolètes à :
- **Dimensions d'embeddings : 1536** → Maintenant **768** (nomic-embed-text-v1.5)
- **Modèle OpenAI** (text-embedding-3-small) → Maintenant **Sentence-Transformers local**
- **Architecture ancienne** → Voir `docs/Document Architecture.md` pour l'architecture actuelle
- **PostgreSQL 17** → Maintenant **PostgreSQL 18** (migré en Oct 2025)

## 📖 Pour la Documentation À Jour

**Consultez plutôt** :
- [`/README.md`](../../README.md) - Vue d'ensemble du projet
- [`/GUIDE_DEMARRAGE.md`](../../GUIDE_DEMARRAGE.md) - Guide utilisateur complet
- [`/docs/Document Architecture.md`](../Document%20Architecture.md) - Architecture technique H-VG-T
- [`/docs/Specification_API.md`](../Specification_API.md) - Spécification API OpenAPI 3.1
- [`/CLAUDE.md`](../../CLAUDE.md) - Guide développeur

## 📂 Contenu de cette Documentation

### 🟢 Développements Récents (ACTUELS - Oct 2025)

#### EPIC-06: Code Intelligence (Backend) - ✅ 100% COMPLET
- `EPIC-06_README.md` - Point d'entrée principal (1.6.0, 2025-10-16)
- `EPIC-06_Code_Intelligence.md` - Vue d'ensemble de l'Epic (33 KB)
- `EPIC-06_ROADMAP.md` - Timeline visuelle & métriques (17 KB)
- `EPIC-06_IMPLEMENTATION_PLAN.md` - Plan détaillé étape par étape (31 KB)
- `EPIC-06_DECISIONS_LOG.md` - ADRs (Architecture Decision Records, 17 KB)
- `STORIES_EPIC-06.md` - User stories détaillées (6 stories, ~100 KB)
- `EPIC-06_PHASE_4_STORY_6_COMPLETION_REPORT.md` - Rapport final (47 KB)
- Rapports de complétion : Phase 0 (Stories 0.1-0.2), Phase 2 (Story 4), Phase 3 (Story 5)
- **Résumé** : 74/74 pts, 8 stories, 10 jours (vs 77 estimés)

#### EPIC-07: Code Intelligence UI (Frontend) - ✅ 100% COMPLET
- `EPIC-07_README.md` - Point d'entrée principal (2.0.0, 2025-10-17)
- `EPIC-07_CODE_UI_ULTRADEEP_BRAINSTORM.md` - Brainstorm complet (21 KB)
- `EPIC-07_MVP_COMPLETION_REPORT.md` - Rapport MVP complet (810 lignes)
- **Résumé** : 41/41 pts, 6 stories, 2 jours (vs 16-19 estimés)
- **Livrables** : 5 pages UI (Dashboard, Repos, Search, Graph, Upload)

### 🟡 Archive Historique (Q1-Q2 2025)

#### Epics Historiques
- `EPIC-01_Alignement_API_Schema_Base.md` - Alignement initial API/DB
- `EPIC-02_Recherche_Evenements.md` - Système de recherche événements
- `EPIC-03_Recherche_Semantique_Hybride.md` - Recherche hybride (lexical + vector)
- `EPIC-04_Refactoring_Bonnes_Pratiques.md` - Refactoring DIP/Repository pattern
- `EPIC-05_UI_Exploration_MnemoLite.md` - Interface utilisateur HTMX (première version)

#### User Stories Historiques
- `STORIES_EPIC-01.md` - Stories d'alignement API/Schema
- `STORIES_EPIC-02.md` - Stories de partitionnement et indexation
- `STORIES_EPIC-03.md` - Stories de benchmarking et tests
- `STORIES_EPIC-04.md` - Stories de refactoring
- `STORIES_EPIC-05.md` - Stories d'interface utilisateur

#### Rapports Historiques
- `US-04-2_DIP_rapport.md` - Rapport sur l'application du principe DIP
- `EPIC-05_COMPLETION_REPORT.md` - Rapport de complétion EPIC-05

## 🎯 Utilisation de cette Documentation

### Pour les Développements Récents (EPIC-06 & EPIC-07)
- ✅ **Point d'entrée** : Lire `EPIC-06_README.md` et `EPIC-07_README.md`
- ✅ **Code Intelligence** : Comprendre l'architecture dual embeddings + graph + hybrid search
- ✅ **UI Patterns** : Voir la stratégie "EXTEND DON'T REBUILD" (EPIC-07)
- ✅ **Performance** : Analyser les optimisations (CTE 129× faster, Search 28× faster)
- ✅ **Documentation à jour** : Tous les rapports reflètent l'implémentation actuelle

### Pour l'Archive Historique (EPIC 01-05)
Ces documents restent utiles pour :
- ✅ Comprendre l'**historique des décisions** d'architecture
- ✅ Analyser les **défis techniques** rencontrés et résolus (migration OpenAI → local embeddings)
- ✅ Étudier le **processus de développement** agile appliqué
- ✅ Apprendre des **erreurs et solutions** documentées

## 📅 Timeline du Projet

| Période | Phase | EPICs |
|---------|-------|-------|
| **Mars-Mai 2025** | Phase Initiale | EPIC-01 à EPIC-05 (Archives) |
| **Octobre 2025** | Code Intelligence | EPIC-06 (Backend, 10 jours) + EPIC-07 (UI, 2 jours) |

**Version actuelle du projet** : v2.0.0 (Octobre 2025)

**Progrès Total** :
- ✅ EPIC-01 à EPIC-05 : Complétés (Q1-Q2 2025)
- ✅ EPIC-06 : 74/74 pts (Oct 2025)
- ✅ EPIC-07 : 41/41 pts (Oct 2025)

---

_Dernière mise à jour de cette documentation : 2025-10-17_
