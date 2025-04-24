# MnemoLite – Product Requirements Document (PRD)

## 1. Titre du produit
**MnemoLite** — Mémoire cognitive autonome pour assistant conversationnel Expanse

**Version**: 1.0.0  
**Date**: 2025-04-24

## 2. Objectif du produit
Fournir une **mémoire cognitive réutilisable, autonome et interrogeable**, destinée à simuler, tester, visualiser et enrichir les capacités mémorielles d’un agent IA, en reproduisant les grands types de mémoire humaine (épisodique, sémantique, procédurale, prospective, de travail).

MnemoLite doit être intégrable dans Expanse via scripts Python appelés par des règles `.mdc`, mais doit également fonctionner seul, avec une interface Web.

## 3. Public cible
- Architectes & développeurs Expanse
- Chercheurs en cognition augmentée IA
- Formateurs d’agents LLM personnalisés
- Analystes QA / DataOps / A/B testers

## 4. Cas d’usage principaux

### UC1 — Injection de souvenirs simulés
**Acteur** : Testeur, Développeur  
**Précondition** : CLI/API active  
**Description** : L’utilisateur injecte une série d’événements factices (`prompt`, `réponse`, `décision`, `outil`) dans la mémoire.
**Postcondition** : Les entrées sont vectorisées (si applicable), horodatées, indexées (PG + Chroma).

### UC2 — Recherche contextuelle d’un souvenir
**Acteur** : Agent Expanse ou Humain  
**Précondition** : Clé de recherche disponible (texte, vecteur, métadonnée)  
**Description** : Le système restitue les souvenirs les plus proches selon une pondération mixte (`embedding` + tags + temporalité).
**Postcondition** : Les éléments sont renvoyés triés, avec UID source, score de confiance, et contexte relationnel (si graph).

### UC3 — Exploration manuelle (UI HTMX)
**Acteur** : Analyste, Formateur, Développeur  
**Précondition** : UI Web active  
**Description** : L’utilisateur navigue dans une timeline, filtre par type, explore un graphe de dépendances mnésiques, ou demande des résumés.
**Postcondition** : Retour HTML dynamique, exportable, interrogeable via URL.

### UC4 — Requête Ψ réflexive
**Acteur** : LLM ou humain  
**Précondition** : API `/psi/query` accessible  
**Description** : L’utilisateur pose une question réflexive à la mémoire : "Pourquoi as-tu fait ça ?", "Qu’as-tu appris ?", etc.
**Postcondition** : Retour raisonné, enrichi, structuré (preuve, chemin, incertitudes).

## 5. Spécifications fonctionnelles clés

| ID      | Fonctionnalité                                | Priorité |
|---------|-----------------------------------------------|----------|
| F-001   | Ingestion JSON/REST d'événements              | Haute    |
| F-002   | Stockage dans PostgreSQL (métadonnées)        | Haute    |
| F-003   | Vectorisation (OpenAI ou modèle local)        | Haute    |
| F-004   | Indexation dans ChromaDB                      | Haute    |
| F-005   | Interface Web HTMX avec timeline et tags      | Haute    |
| F-006   | Requête vectorielle + sémantique              | Haute    |
| F-007   | Graphe mnésique (pgGraph/pgRouting + tables d'adjacence) | Moyenne  |
| F-008   | Export CSV / JSONL de tout ou partie mémoire  | Moyenne  |
| F-009   | API réflexive (`/psi/`)                       | Moyenne  |
| F-010   | Mécanisme d'oubli actif (TTL / filtre)        | Moyenne  |
| F-011   | Visualisation cause/effet / cluster            | Faible   |
| F-012   | Stratégie d'archivage multi-niveaux            | Moyenne   |
| F-013   | Documentation d'installation et déploiement    | Haute     |
| F-014   | Guides d'intégration (Expanse, standalone)     | Haute     |

## 6. Contraintes techniques
- 100 % open-source / auto-hébergeable
- PostgreSQL 17, ChromaDB, FastAPI 0.110+, HTMX 1.9+, Python 3.12+
- Docker Compose + Makefile + .env
- Aucun SPA ou bundle JS imposé

## 7. KPIs de validation

| Critère                             | Méthode                     | Seuil      |
|------------------------------------|-----------------------------|------------|
| Taux de récupération cohérente     | Test unitaire               | ≥ 99 %     |
| Temps de réponse `/search`         | `bench_httpx`               | < 10 ms P95 |
| Taux de retour pertinent (top 5)   | Test manuel + recall score | > 80 %     |
| Temps de démarrage local complet   | `docker compose up`        | < 3 min    |
| Utilisation mémoire (inference 1M) | `htop + chroma stat`        | < 2.5 GB   |
| Réponse Ψ complète                 | Cas de test Q→A justifiée  | Oui        |
| Démarrage sans Cursor              | Test E2E                    | ≤ 5 min    |
| Intégration `.mdc`                 | Code review                 | ≤ 20 lignes Python |

### KPIs stratégie d'archivage

| Métrique                           | Couche           | Cible                 |
|-----------------------------------|------------------|------------------------|
| Temps d'accès vectoriel           | Hot (0-90j)      | ≤ 5 ms P95             |
|                                   | Warm (90j-1an)   | ≤ 30 ms P95            |
|                                   | Cold (1-2ans)    | ≤ 100 ms P95           |
| Réduction taille stockage         | Warm vs Hot      | ≥ 60%                  |
|                                   | Cold vs Hot      | ≥ 85%                  |
|                                   | Archive vs Hot   | ≥ 95%                  |

## 8. Livrables associés
- Fichier `schema.sql` pour PostgreSQL + pgvector + graph
- Script `populate_fake_data.py`
- API `memory_server.py`
- Interface `templates/index.html` + `search.html`
- Script `vector_indexer.py` (ingestion Chroma)
- Documentation : `README.md`, `api.md`, `psi-guide.md`

## 9. Installation et environnement

### 9.1 Prérequis système
- Linux (Ubuntu 22.04+ ou Debian 11+)
- Docker Engine 24.0+ et Docker Compose 2.20+
- 4GB RAM min (8GB recommandé)
- 20GB SSD min pour les données
- Python 3.12+ pour l'intégration

### 9.2 Guide d'installation rapide
```bash
# Cloner le dépôt
git clone https://github.com/giak/mnemo-lite.git
cd mnemo-lite

# Configuration
cp .env.example .env
# Éditer .env pour les paramètres locaux

# Démarrage
make setup      # Installation dépendances, init DB
make dev        # Mode développement
# OU
make prod       # Mode production
```

### 9.3 Structure des dossiers
```
mnemo-lite/
├── api/               # Code FastAPI
├── db/                # Schémas et migrations
├── workers/           # Workers d'ingestion et maintenance
├── ui/                # Templates HTMX
├── docs/              # Documentation
└── scripts/           # Utilitaires et helpers
```

### 9.4 Configuration et personnalisation
- `.env` : Paramètres connexions, clés API, options
- `config/app.yaml` : Configuration applicative
- `scripts/seed.py` : Données de test

### 9.5 Tests et vérification

La vérification du déploiement peut être effectuée avec:
```bash
make test-install   # Vérifie l'installation
make test-e2e       # Exécute les tests end-to-end
make metrics        # Affiche les métriques de performance
```

## 10. Documentation

### 10.1 Documentation utilisateur
- `README.md` : Vue d'ensemble et démarrage rapide
- `docs/USER.md` : Guide d'utilisation détaillé
- `docs/API.md` : Documentation complète de l'API REST

### 10.2 Documentation technique
- `docs/ARCHITECTURE.md` : Architecture détaillée
- `docs/SCHEMA.md` : Schéma de base de données
- `docs/DEV.md` : Guide développeur
- `docs/INTEGRATION.md` : Guide d'intégration à Expanse

### 10.3 Support et maintenance
- `docs/BACKUP.md` : Procédures de sauvegarde/restauration
- `docs/UPGRADE.md` : Guide de mise à jour
- `docs/TROUBLESHOOTING.md` : Diagnostics et résolution de problèmes

---

### Placeholders restants à remplir : _Néant — document complet._

