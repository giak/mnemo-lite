# 📚 Documents Agile - Archive Historique

> **⚠️ AVERTISSEMENT**: Ces documents capturent l'historique du développement de MnemoLite.
> Ils peuvent contenir des informations obsolètes qui ne reflètent plus l'implémentation actuelle.

## 🕰️ Contexte Historique

Ces documents ont été créés pendant la phase initiale de développement du projet (Q1-Q2 2025) et documentent :
- Les décisions d'architecture prises pendant la migration de OpenAI vers les embeddings locaux
- Les user stories et epics de la phase de développement agile
- Les défis techniques rencontrés et leurs résolutions

## ⚠️ Informations Potentiellement Obsolètes

Les documents de ce dossier peuvent contenir des références à :
- **Dimensions d'embeddings : 1536** → Maintenant **768** (nomic-embed-text-v1.5)
- **Modèle OpenAI** (text-embedding-3-small) → Maintenant **Sentence-Transformers local**
- **Architecture ancienne** → Voir `docs/Document Architecture.md` pour l'architecture actuelle

## 📖 Pour la Documentation À Jour

**Consultez plutôt** :
- [`/README.md`](../../README.md) - Vue d'ensemble du projet
- [`/GUIDE_DEMARRAGE.md`](../../GUIDE_DEMARRAGE.md) - Guide utilisateur complet
- [`/docs/Document Architecture.md`](../Document%20Architecture.md) - Architecture technique H-VG-T
- [`/docs/Specification_API.md`](../Specification_API.md) - Spécification API OpenAPI 3.1
- [`/CLAUDE.md`](../../CLAUDE.md) - Guide développeur

## 📂 Contenu de cette Archive

### Epics
- `EPIC-01_Alignement_API_Schema_Base.md` - Alignement initial API/DB
- `EPIC-04_Refactoring_Bonnes_Pratiques.md` - Refactoring DIP/Repository pattern
- `EPIC-05_UI_Exploration_MnemoLite.md` - Interface utilisateur HTMX

### User Stories
- `STORIES_EPIC-01.md` - Stories d'alignement API/Schema
- `STORIES_EPIC-02.md` - Stories de partitionnement et indexation
- `STORIES_EPIC-03.md` - Stories de benchmarking et tests
- `STORIES_EPIC-04.md` - Stories de refactoring
- `STORIES_EPIC-05.md` - Stories d'interface utilisateur

### Rapports
- `US-04-2_DIP_rapport.md` - Rapport sur l'application du principe DIP

## 🎯 Utilisation de cette Archive

Ces documents restent utiles pour :
- ✅ Comprendre l'**historique des décisions** d'architecture
- ✅ Analyser les **défis techniques** rencontrés et résolus
- ✅ Étudier le **processus de développement** agile appliqué
- ✅ Apprendre des **erreurs et solutions** documentées

## 📅 Date de Création

Ces documents couvrent la période de développement : **Mars 2025 - Mai 2025**

**Version actuelle du projet** : v1.3.0 (Octobre 2025)

---

_Dernière mise à jour de cette archive : 2025-10-13_
