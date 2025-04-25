# User Stories pour EPIC-01: Alignement API-Schéma pour Gestion de Base des Événements

*(Perspective: Développeur utilisant l'API MnemoLite)*

1.  **STORY-01.1: [Repository] Mettre en place la couche `EventRepository`**
    *   **En tant que** Développeur Système MnemoLite,
    *   **Je veux** créer une classe `EventRepository` qui gère les connexions à PostgreSQL (via un pool `asyncpg`) et encapsule la logique SQL de base,
    *   **Afin de** centraliser et d'isoler l'accès à la table `events`.
    *   *Critères d'Acceptation:*
        *   Une classe `EventRepository` existe (`api/db/repositories/event_repository.py`). **[FAIT]**
        *   Elle reçoit un pool de connexion `asyncpg` (injecté). **[FAIT - Structure Init]**
        *   Les méthodes CRUD de base sont définies (même vides au début). **[FAIT - Placeholders]**
        *   Des tests unitaires basiques existent pour mocker le repository. **[FAIT - Structure Init & Test Placeholders]**
    *   **Statut:** **Terminé**
    *   **Notes / Problèmes Rencontrés & Solutions:**
        *   La structure de base de la classe `EventRepository` est créée.
        *   Décision prise d'exécuter les tests DANS Docker pour l'isolation (plutôt qu'un venv local) suite à l'erreur `externally-managed-environment`.
        *   Mise en place de `requirements-dev.txt` pour `pytest`, `pytest-asyncio`, `pytest-mock`.
        *   Modification des `Dockerfile` pour installer les dépendances de dev.
        *   Correction du contexte de build Docker et des chemins `COPY` pour accéder à `requirements-dev.txt`.
        *   Correction de la commande `make api-test` pour utiliser `python -m pytest tests/`.
        *   Ajout du montage du volume `./tests:/app/tests` dans `docker-compose.yml`.
        *   Résolution de l'erreur `fixture 'mocker' not found` via rebuild `--no-cache` après ajout de `pytest-mock`.
        *   Résolution de l'erreur `AttributeError` avec `mocker.spy` en ciblant `builtins.print`.
        *   Les tests initiaux (`test_event_repository_instantiation`, `test_add_event_placeholder`) passent via `make api-test`.

2.  **STORY-01.2: [API - Create] Créer un nouvel événement**
    *   **En tant que** Développeur API,
    *   **Je veux** pouvoir envoyer une requête POST à un endpoint (ex: `/events/`) avec le `content` (JSONB) et les `metadata` (JSONB) d'un événement (et optionnellement un `embedding`),
    *   **Afin que** l'événement soit enregistré dans la table `events` via le `EventRepository`.
    *   *Critères d'Acceptation:*
        *   Le endpoint API existe et accepte les données conformes au nouveau schéma (`content`, `metadata` JSONB).
        *   La route API utilise le `EventRepository.add()` pour insérer l'enregistrement.
        *   L'enregistrement est correctement inséré dans la table `events` avec `timestamp`, `content`, `metadata`, `embedding`.
        *   Les anciennes colonnes (`memory_type`, etc.) ne sont plus utilisées/requises dans ce flux.
        *   Des tests d'intégration valident la création via l'API.

3.  **STORY-01.3: [API - Read] Récupérer un événement par ID**
    *   **En tant que** Développeur API,
    *   **Je veux** pouvoir envoyer une requête GET à un endpoint (ex: `/events/{event_id}`) avec l'ID d'un événement,
    *   **Afin de** récupérer les détails complets de cet événement (`id`, `timestamp`, `content`, `metadata`, `embedding`) via le `EventRepository`.
    *   *Critères d'Acceptation:*
        *   Le endpoint API existe.
        *   La route API utilise le `EventRepository.get_by_id()`.
        *   Les données retournées sont conformes au schéma actuel de la table `events`.
        *   Gestion correcte du cas où l'ID n'existe pas (404).
        *   Des tests d'intégration valident la récupération via l'API.

4.  **STORY-01.4: [API - Update Metadata] Mettre à jour les métadonnées d'un événement**
    *   **En tant que** Développeur API,
    *   **Je veux** pouvoir envoyer une requête PATCH ou PUT à un endpoint (ex: `/events/{event_id}`) avec de nouvelles paires clé-valeur à ajouter ou modifier dans le champ `metadata` de l'événement,
    *   **Afin de** pouvoir enrichir ou corriger les métadonnées d'un événement existant via le `EventRepository`.
    *   *Critères d'Acceptation:*
        *   Le endpoint API existe.
        *   La route API utilise une méthode `EventRepository.update_metadata()` (ou similaire).
        *   Seul le champ `metadata` (JSONB) est modifié en utilisant les opérateurs JSONB de PostgreSQL (`||`, `jsonb_set`).
        *   L'événement mis à jour est retourné ou peut être récupéré avec les nouvelles métadonnées.
        *   Des tests d'intégration valident la mise à jour des métadonnées.

5.  **STORY-01.5: [API - Delete] Supprimer un événement par ID**
    *   **En tant que** Développeur API,
    *   **Je veux** pouvoir envoyer une requête DELETE à un endpoint (ex: `/events/{event_id}`),
    *   **Afin de** supprimer définitivement l'événement correspondant de la table `events` via le `EventRepository`.
    *   *Critères d'Acceptation:*
        *   Le endpoint API existe.
        *   La route API utilise le `EventRepository.delete()`.
        *   L'enregistrement est effectivement supprimé de la table `events`.
        *   Gestion correcte du cas où l'ID n'existe pas (éventuellement 404 ou 204).
        *   Des tests d'intégration valident la suppression via l'API.

6.  **STORY-01.6: [Cleanup] Nettoyer le code API associé au CRUD de base**
    *   **En tant que** Développeur Système MnemoLite,
    *   **Je veux** m'assurer que tout le code Python dans l'API directement lié aux opérations CRUD couvertes par les stories précédentes (modèles Pydantic, routes, repository) n'utilise plus les anciennes colonnes (`memory_type`, `event_type`, `role_id`) ni aucune logique liée à ChromaDB pour ces opérations,
    *   **Afin de** garantir la cohérence avec le nouveau schéma et l'architecture cible.
    *   *Critères d'Acceptation:*
        *   Une revue de code confirme l'absence de références obsolètes dans les fichiers modifiés pour cet Epic.
        *   Les modèles Pydantic utilisés par l'API pour `events` reflètent le nouveau schéma. 