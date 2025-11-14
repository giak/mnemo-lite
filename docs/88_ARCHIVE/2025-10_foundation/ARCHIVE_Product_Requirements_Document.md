# MnemoLite – Product Requirements Document (PRD)

> 📅 **Dernière mise à jour**: 2025-10-13
> 📝 **Version**: v1.3.0
> ✅ **Statut**: À jour avec le code

## 1. Titre du produit
**MnemoLite** — Mémoire cognitive autonome pour assistant conversationnel Expanse

## 2. Objectif du produit
Fournir une **mémoire cognitive réutilisable, autonome et interrogeable**, optimisée pour un déploiement local, destinée à simuler, tester, visualiser et enrichir les capacités mémorielles d'un agent IA, en reproduisant les grands types de mémoire humaine (épisodique, sémantique, procédurale, prospective, de travail).

MnemoLite doit être intégrable dans Expanse via scripts Python appelés par des règles `.mdc`, mais doit également fonctionner seul, avec une interface Web.

## 3. Public cible
- Architectes & développeurs Expanse
- Chercheurs en cognition augmentée IA
- Formateurs d'agents LLM personnalisés
- Analystes QA / DataOps / A/B testers

## 4. Cas d'usage principaux

### UC1 — Injection de souvenirs simulés
**Acteur** : Testeur, Développeur  
**Précondition** : CLI/API active  
**Description** : L'utilisateur injecte une série d'événements factices (`prompt`, `réponse`, `décision`, `outil`) dans la mémoire.
**Postcondition** : Les entrées sont vectorisées (si applicable), horodatées, indexées (PostgreSQL + pgvector).

### UC2 — Recherche contextuelle d'un souvenir
**Acteur** : Agent Expanse ou Humain  
**Précondition** : Clé de recherche disponible (texte, vecteur, métadonnée)  
**Description** : Le système restitue les souvenirs les plus proches selon une pondération mixte (`embedding` + tags + temporalité).
**Postcondition** : Les éléments sont renvoyés triés, avec UID source, score de confiance, et contexte relationnel (si graph).

### UC3 — Exploration manuelle (UI HTMX)
**Acteur** : Analyste, Formateur, Développeur  
**Précondition** : UI Web active  
**Description** : L'utilisateur navigue dans une timeline, filtre par type, explore un graphe de dépendances mnésiques, ou demande des résumés.
**Postcondition** : Retour HTML dynamique, exportable, interrogeable via URL.

### UC4 — Requête Ψ réflexive
**Acteur** : LLM ou humain  
**Précondition** : API `/psi/query` accessible  
**Description** : L'utilisateur pose une question réflexive à la mémoire : "Pourquoi as-tu fait ça ?", "Qu'as-tu appris ?", etc.
**Postcondition** : Retour raisonné, enrichi, structuré (preuve, chemin, incertitudes).

## 5. Spécifications fonctionnelles clés

| ID      | Fonctionnalité                                | Priorité | Notes                                        |
|---------|-----------------------------------------------|----------|----------------------------------------------|
| F-001   | Ingestion JSON/REST d'événements              | Haute    |                                              |
| F-002   | Stockage dans PostgreSQL (métadonnées)        | Haute    | Tables principales (events, nodes, edges)    |
| F-003   | Vectorisation (modèle local Sentence-Transformers) | Haute    | Worker ou application logic (nomic-embed-text-v1.5) |
| F-004   | Indexation vectorielle via pgvector (HNSW)    | Haute    | Remplacement de ChromaDB                     |
| F-005   | Interface Web HTMX avec timeline et tags      | Haute    | Pour exploration locale                      |
| F-006   | Requête vectorielle + sémantique              | Haute    | API `/search`                                |
| F-007   | Graphe mnésique (Tables nodes/edges + CTE SQL)| Moyenne  | Limité à ≤ 3 sauts pour performance locale   |
| F-008   | Export CSV / JSONL de tout ou partie mémoire  | Moyenne  | Utile pour analyse / backup manuel         |
| F-009   | API réflexive (`/psi/`)                       | Moyenne  | **⚠️ TODO (Non implémenté)** - Requiert logique LLM externe |
| F-010   | Mécanisme d'oubli actif (TTL / filtre)        | Moyenne  | Via partitionnement `pg_partman`             |
| F-011   | Visualisation cause/effet / cluster            | Faible   | **⚠️ TODO (Non implémenté)** - Potentiellement via UI ou export + outil ext |
| F-012   | Cycle de vie Hot/Warm (Quantisation INT8)     | Haute    | **⚠️ TODO (Non implémenté)** - Géré par `pg_cron` (nécessite installation/config) ; Cold/Archive différé |
| F-013   | Documentation d'installation et déploiement    | Haute    | Focus sur Docker local                       |
| F-014   | Guides d'intégration (Expanse, standalone)     | Haute    | Script Python simple pour `.mdc`             |

## 6. Contraintes techniques
- 100 % open-source / auto-hébergeable
- PostgreSQL 17 (+ pgvector, pg_partman, pg_cron), FastAPI 0.110+, HTMX 1.9+, Python 3.12+
- Docker Compose + Makefile + .env
- Aucun SPA ou bundle JS imposé

## 7. KPIs de validation

| Critère                             | Méthode                     | Seuil (Local)             |
|------------------------------------|-----------------------------|---------------------------|
| Taux de récupération cohérente     | Test unitaire               | ≥ 99 %                    |
| Temps de réponse `/search` (k=10)  | `bench_httpx`               | < 10 ms P95 (@ 10M local) |
| Recall Warm INT8                   | Bench spécifique            | ≥ 92 %                    |
| Taux de retour pertinent (top 5)   | Test manuel + recall score | > 80 %                    |
| Temps de démarrage local complet   | `docker compose up`        | < 3 min                   |
| Utilisation mémoire (10M vecteurs) | `htop` pendant bench        | < 4 GB (estimé sur 64GB RAM) |
| Disk / 10M events                  | `df -h` sur volume PG       | < 100 GB (estimé)         |
| Réponse Ψ complète                 | Cas de test Q→A justifiée  | Oui                       |
| Démarrage sans Cursor              | Test E2E                    | ≤ 5 min                   |
| Intégration `.mdc`                 | Code review                 | ≤ 20 lignes Python        |

## 8. Livrables associés
- Scripts d'initialisation DB (`db/init/*.sql`)
- Script de données de test (`scripts/testing/generate_test_data.py` et `scripts/testing/fake_event_poster.py`)
- API FastAPI (`api/main.py`)
- Templates HTMX (`api/templates/*.html`)
- Workers Python (`workers/*.py` pour ingestion/tâches asynchrones via PGMQ)
- Configuration `pg_cron` (SQL ou via outil d'admin) pour maintenance (quantization, etc.)
- Documentation : `README.md` + fichiers dans `docs/` (`docs/Specification_API.md`, `docs/ARCHITECTURE.md`, `docs/bdd_schema.md`, `docs/docker_setup.md` etc.)

## 9. Installation et environnement

### 9.1 Prérequis système
- Linux (Ubuntu 22.04+ ou Debian 11+, Mint 22)
- Docker Engine 24.0+ et Docker Compose 2.20+
- 8GB RAM min (16GB+ recommandé, 64GB cible)
- 20GB SSD min pour les données (plus selon volume mémoire)
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
├── api/               # Code FastAPI (inclut /templates pour HTMX)
├── db/                # Schémas et initialisation (dans /init)
├── workers/           # Workers d'ingestion et maintenance (Python)
├── docs/              # Documentation
└── scripts/           # Utilitaires et helpers (ex: seed.py)
```

### 9.4 Configuration et personnalisation
- `.env` : Fichier principal pour les paramètres de connexions, clés API optionnelles, et variables d'environnement (ex: `ENVIRONMENT`).
- `scripts/testing/generate_test_data.py` et `scripts/testing/fake_event_poster.py` : Pour la génération ou l'injection de données de test.
- `scripts/testing/test_application.sh` : Suite de tests rapides (quick/full/load modes).

### 9.5 Tests et vérification

La vérification du déploiement peut être effectuée avec:
```bash
make test-install   # Vérifie l'installation
make test-e2e       # Exécute les tests end-to-end (si définis, ex: via test_memory_api.sh)
make metrics        # Affiche les métriques de performance (basé sur les stats PG)
```

## 10. Documentation

### 10.1 Documentation utilisateur ✅
- `README.md` : Vue d'ensemble et démarrage rapide
- `GUIDE_DEMARRAGE.md` : Guide utilisateur détaillé avec exemples pratiques
- `docs/Specification_API.md` : Documentation complète de l'API REST (OpenAPI 3.1)

### 10.2 Documentation technique ✅
- `docs/Document Architecture.md` : Architecture détaillée (H-VG-T, pgvector, partitioning)
- `docs/bdd_schema.md` : Schéma de base de données (tables, indexes, partitions)
- `docs/docker_setup.md` : Configuration et explication de l'environnement Docker
- `CLAUDE.md` : Guide développeur pour Claude Code (contexte projet, commands)
- `docs/test_inventory.md` : Inventaire et couverture des tests
- `docs/architecture_diagrams.md` : Diagrammes d'architecture (Mermaid)
- `docs/ui_architecture.md` : Architecture de l'interface HTMX

### 10.3 Documents Fondateurs ✅
- `docs/Product Requirements Document.md` : PRD - Spécifications fonctionnelles
- `docs/Project Foundation Document.md` : PFD - Fondations et décisions d'architecture

### 10.4 Support et maintenance ⚠️ TODO
> **⚠️ Documentation manquante - À créer selon besoin**:
> - `docs/INTEGRATION.md` - Guide d'intégration à Expanse (.mdc)
> - `docs/BACKUP.md` - Procédures de sauvegarde/restauration
> - `docs/UPGRADE.md` - Guide de mise à jour
> - `docs/TROUBLESHOOTING.md` - Diagnostics et résolution de problèmes
>
> **En attendant**, consulter :
> - README.md section "Dépannage"
> - GUIDE_DEMARRAGE.md section "🐛 Dépannage"
> - Issues GitHub pour le support communautaire

---

### Placeholders restants à remplir : _Néant — document complet._

