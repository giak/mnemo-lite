# EPIC-01: Alignement API-Schéma pour Gestion de Base des Événements

**Objectif :** Rendre l'API MnemoLite capable d'effectuer les opérations CRUD de base (Créer, Lire, Mettre à jour Métadonnées, Supprimer) sur la table `events` conformément au schéma PostgreSQL v1.1.0 (`docs/bdd_schema.md`), en utilisant une couche d'accès aux données (Repository Pattern) pour isoler la logique de persistance.

**Motivation :** Établir une fondation technique solide et cohérente entre l'API et la nouvelle base de données PostgreSQL, permettant l'enregistrement et la récupération fiables des informations de base avant d'implémenter des fonctionnalités plus complexes (recherche vectorielle, graphe). C'est un prérequis pour rendre l'API utilisable et pour nettoyer le code hérité.

**Critères d'Acceptation Généraux (DoD - Definition of Done pour l'Epic) :**

*   Le code API (FastAPI) utilise une classe `EventRepository` pour interagir avec la base de données concernant la table `events`.
*   Les opérations CRUD de base sur les événements via l'API fonctionnent et manipulent les données (`content` JSONB, `metadata` JSONB, `embedding` VECTOR) conformément au schéma v1.1.0.
*   Toutes les références directes à l'ancien schéma (colonnes `memory_type`, `event_type`, `role_id` séparées) ou à la logique ChromaDB pour ces opérations CRUD de base sont supprimées du code concerné.
*   Les tests unitaires/intégration pertinents pour le Repository et les routes API associées sont mis en place et passent.
*   La documentation de l'API (`Specification_API.md`) est mise à jour pour refléter les changements dans les modèles de données et les endpoints concernés. 