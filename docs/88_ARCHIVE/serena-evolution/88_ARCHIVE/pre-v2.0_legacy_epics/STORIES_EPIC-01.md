# User Stories pour EPIC-01: Alignement API-Schéma pour Gestion de Base des Événements

> ## ⚠️ DOCUMENT HISTORIQUE (Q1-Q2 2025)
>
> **Ce document contient des informations obsolètes** issues de la phase initiale de développement.
>
> **Notamment** :
> - ⚠️ Ligne 48 : Mention de **"1536 dimensions"** (ancien modèle OpenAI)
> - ✅ **Version actuelle** : **768 dimensions** avec nomic-embed-text-v1.5 (Sentence-Transformers local)
>
> **Pour la documentation à jour**, consultez :
> - [`/docs/Document Architecture.md`](../Document%20Architecture.md)
> - [`/docs/Specification_API.md`](../Specification_API.md)
> - [`/docs/agile/README.md`](README.md) - Contexte de cette archive

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
        *   Le endpoint API existe et accepte les données conformes au nouveau schéma (`content`, `metadata` JSONB). **[FAIT]**
        *   La route API utilise le `EventRepository.add()` pour insérer l'enregistrement. **[FAIT]**
        *   L'enregistrement est correctement inséré dans la table `events` avec `timestamp`, `content`, `metadata`, `embedding`. **[FAIT - avec simplification du partitionnement]**
        *   Les anciennes colonnes (`memory_type`, etc.) ne sont plus utilisées/requises dans ce flux. **[FAIT - à vérifier en Cleanup]**
        *   Des tests d'intégration valident la création via l'API. **[À FAIRE]**
    *   **Statut:** **Terminé (Fonctionnel)**
    *   **Notes / Problèmes Rencontrés & Solutions:**
        *   Diagnostiqué des erreurs 404 initiales causées par le non-rechargement du code API dans Docker après modification (`make down && docker compose build api && make up`).
        *   Rencontré erreur `relation "events" does not exist`, résolue en changeant l'image Docker de `postgres:17-alpine` à une image incluant `pgvector` (`ankane/pgvector` puis `pgvector/pgvector:pg17`).
        *   Rencontré erreur similaire due à l'extension `pg_partman` manquante. Tentative d'installation via `apt` dans un Dockerfile personnalisé a causé des instabilités (`unhealthy` container, incohérences sur l'existence du schéma `partman`).
        *   Corrigé erreurs de syntaxe SQL dans le script `01-init.sql` (accents dans les commentaires, virgule manquante).
        *   Corrigé erreur de contrainte PostgreSQL sur table partitionnée (clé primaire doit inclure clé de partitionnement).
        *   Solution temporaire adoptée : Commenté `pg_partman` et la clause `PARTITION BY` dans `01-init.sql` pour simplifier l'initialisation et débloquer le CRUD de base. Utilisation de l'image `pgvector/pgvector:pg17` directe.
        *   Rencontré erreur `asyncpg`: `expected str, got list` pour l'embedding `VECTOR`. Corrigé en passant `json.dumps(embedding)` à `fetchrow`.
        *   Rencontré erreur de validation Pydantic (`Input should be a valid dictionary... input_type=str`) pour les champs JSONB. Corrigé en ajoutant `json.loads()` dans `EventModel.from_db_record` pour les champs `content` et `metadata`.
        *   Corrigé erreur `AttributeError: 'asyncpg.Record' object has no attribute 'copy'` en convertissant `record` en `dict` avant d'appeler `from_db_record`.
        *   Rencontré erreur `pgvector`: `expected 1536 dimensions, not 3`. Validé que le schéma impose la bonne dimension. Testé avec un vecteur factice de 1536 zéros.
        *   Création du script `scripts/fake_event_poster.py` (exécuté via `docker compose exec api`) pour faciliter les tests POST futurs.
        *   Endpoint `POST /v1/events/` finalement fonctionnel après toutes ces étapes.

3.  **STORY-01.3: [API - Read] Récupérer un événement par ID**
    *   **En tant que** Développeur API,
    *   **Je veux** pouvoir envoyer une requête GET à un endpoint (ex: `/events/{event_id}`) avec l'ID d'un événement,
    *   **Afin de** récupérer les détails complets de cet événement (`id`, `timestamp`, `content`, `metadata`, `embedding`) via le `EventRepository`.
    *   *Critères d'Acceptation:*
        *   Le endpoint API existe. **[FAIT]**
        *   La route API utilise le `EventRepository.get_by_id()`. **[FAIT]**
        *   Les données retournées sont conformes au schéma actuel de la table `events`. **[FAIT]**
        *   Gestion correcte du cas où l'ID n'existe pas (404). **[FAIT]**
        *   Des tests d'intégration valident la récupération via l'API. **[BLOQUÉ]**
    *   **Statut:** **Terminé (Code) / BLOQUÉ (Tests API)**
    *   **Notes / Problèmes Rencontrés & Solutions:**
        *   Le code de la route et du repository est implémenté.
        *   Les tests unitaires du repository (`test_event_repository.py`) passent.
        *   Les tests d'intégration API (`test_event_routes.py`) sont actuellement bloqués par un problème persistant de mocking/patching (avec `dependency_overrides` ou `unittest.mock.patch`) de la dépendance `EventRepository` lors de l'utilisation de `TestClient`. La méthode mockée n'est jamais appelée. Tests marqués `@pytest.mark.skip` en attendant une solution.

4.  **STORY-01.4: [API - Update Metadata] Mettre à jour les métadonnées d'un événement**
    *   **En tant que** Développeur API,
    *   **Je veux** pouvoir envoyer une requête PATCH ou PUT à un endpoint (ex: `/events/{event_id}`) avec de nouvelles paires clé-valeur à ajouter ou modifier dans le champ `metadata` de l'événement,
    *   **Afin de** pouvoir enrichir ou corriger les métadonnées d'un événement existant via le `EventRepository`.
    *   *Critères d'Acceptation:*
        *   Le endpoint API existe (PATCH `/v1/events/{event_id}`). **[FAIT]**
        *   La route API utilise une méthode `EventRepository.update_metadata()`. **[FAIT]**
        *   Seul le champ `metadata` (JSONB) est modifié en utilisant les opérateurs JSONB de PostgreSQL (`||`). **[FAIT]**
        *   L'événement mis à jour est retourné ou peut être récupéré avec les nouvelles métadonnées. **[FAIT]**
        *   Des tests d'intégration valident la mise à jour des métadonnées. **[À FAIRE (BLOQUÉ PAR MOCKING)]**
    *   **Statut:** **Terminé (Code) / BLOQUÉ (Tests API)**
    *   **Notes / Problèmes Rencontrés & Solutions:**
        *   Implémentation de `EventRepository.update_metadata` utilisant `UPDATE ... SET metadata = metadata || $2::jsonb ... RETURNING *`.
        *   Création du modèle Pydantic `MetadataUpdateRequest` pour la requête PATCH.
        *   Création de la route `PATCH /v1/events/{event_id}`.
        *   Tests API reportés en attendant la résolution du problème de mocking rencontré sur la route GET.

5.  **STORY-01.5: [API - Delete] Supprimer un événement par ID**
    *   **En tant que** Développeur API,
    *   **Je veux** pouvoir envoyer une requête DELETE à un endpoint (ex: `/events/{event_id}`),
    *   **Afin de** supprimer définitivement l'événement correspondant de la table `events` via le `EventRepository`.
    *   *Critères d'Acceptation:*
        *   Le endpoint API existe. **[FAIT]**
        *   La route API utilise le `EventRepository.delete()`. **[FAIT]**
        *   L'enregistrement est effectivement supprimé de la table `events`. **[FAIT]**
        *   Gestion correcte du cas où l'ID n'existe pas (404). **[FAIT]**
        *   Des tests d'intégration valident la suppression via l'API. **[À FAIRE (BLOQUÉ PAR MOCKING)]**
    *   **Statut:** **Terminé (Code) / BLOQUÉ (Tests API)**
    *   **Notes / Problèmes Rencontrés & Solutions:**
        *   Implémentation de `EventRepository.delete` utilisant `DELETE ... WHERE id = $1` et vérifiant le statut retourné par `conn.execute()`.
        *   Création de la route `DELETE /v1/events/{event_id}` retournant 204 si succès, 404 sinon.
        *   Tests API reportés en attendant la résolution du problème de mocking.

6.  **STORY-01.6: [Cleanup] Nettoyer le code API associé au CRUD de base**
    *   **En tant que** Développeur Système MnemoLite,
    *   **Je veux** m'assurer que tout le code Python dans l'API directement lié aux opérations CRUD couvertes par les stories précédentes (modèles Pydantic, routes, repository) n'utilise plus les anciennes colonnes (`memory_type`, `event_type`, `role_id`) ni aucune logique liée à ChromaDB pour ces opérations,
    *   **Afin de** garantir la cohérence avec le nouveau schéma et l'architecture cible.
    *   *Critères d'Acceptation:*
        *   Une revue de code confirme l'absence de références obsolètes dans les fichiers modifiés pour cet Epic (`event_repository.py`, `event_routes.py`). **[FAIT]**
        *   Les modèles Pydantic utilisés par l'API pour `events` (`EventCreate`, `EventModel`, `MetadataUpdateRequest`) reflètent le nouveau schéma. **[FAIT]**
    *   **Statut:** **Terminé**
    *   **Notes / Problèmes Rencontrés & Solutions:**
        *   Revue de code effectuée sur `api/db/repositories/event_repository.py` et `api/routes/event_routes.py`.
        *   Aucune référence aux anciennes colonnes ou à ChromaDB n'a été trouvée.
        *   Les modèles Pydantic sont cohérents avec la structure de la table `events`.

*(Fin de l'EPIC-01)* 