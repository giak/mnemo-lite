# EPIC-03: Recherche Sémantique & Hybride

*(Perspective: Développeur Système MnemoLite, Développeur API, Client API)*

## Objectifs de l'Epic:

1.  Permettre la recherche d'événements par **similarité sémantique** en utilisant leur champ `embedding` (vecteur `pgvector`).
2.  Implémenter une recherche **hybride** efficace combinant similarité vectorielle et filtrage par métadonnées.
3.  Intégrer ces fonctionnalités dans l'endpoint API existant `GET /v1/search` de manière cohérente et performante.
4.  Valider l'approche choisie (Post-filtrage HNSW partitionné) via un PoC et établir une base pour les tests.

---

## User Stories:

*(Note: Basées sur l'Approche 3 recommandée : Post-filtrage HNSW + Partitionnement)*

1.  **STORY-03.1: [DB] Indexation HNSW & Préparation au Partitionnement**
    *   **En tant que** Développeur Système MnemoLite,
    *   **Je veux** créer un index `HNSW` sur la colonne `embedding` de la table `events` (ou de ses futures partitions) et m'assurer que la table est prête pour un partitionnement par range sur `timestamp`,
    *   **Afin de** permettre des recherches vectorielles rapides et de préparer la scalabilité future du système.
    *   *Critères d'Acceptation:*
        *   Un index `HNSW` utilisant la similarité cosinus (`vector_cosine_ops`) est défini pour la colonne `embedding`.
        *   Les paramètres de l'index (`m`, `ef_construction`) sont choisis et documentés (valeurs initiales raisonnables basées sur les recommandations `pgvector`).
        *   La table `events` est définie comme partitionnée par `RANGE` sur `timestamp` (ex: mensuellement), ou la structure le permettant est en place. **FAIT via `pg_partman`.**
        *   La documentation de la structure DB (`docs/bdd_schema.md`) est mise à jour.
    *   **Statut:** **FAIT**
    *   **Notes / Problèmes Rencontrés & Solutions:**
        *   **Fait:** La table `events` est définie avec `PARTITION BY RANGE (timestamp)` comme documenté dans `docs/bdd_schema.md`.
        *   **Fait:** Documentation `docs/bdd_schema.md` mise à jour (index HNSW `m=16, ef_construction=64`).
        *   **Installation `pg_partman`:**
            *   Ajout de `postgresql-17-partman` dans `Dockerfile` pour l'image `db`.
            *   Ajout de `CREATE EXTENSION IF NOT EXISTS pg_partman SCHEMA partman;` dans `db/init/01-init-db.sql`.
        *   **Configuration `pg_partman` (`db/init/02-partman-config.sql`):**
            *   **Étape 1 (Échec):** Tentative d'insertion manuelle dans `partman.part_config`. Échoue car `pg_partman` gère sa propre configuration.
            *   **Étape 2 (Échec):** Tentative d'utilisation de `partman.create_parent` avec `p_type := 'native'` (interprétation erronée) et `p_interval := 'monthly'` (syntaxe incorrecte). Résultat: `ERROR: native is not a valid partitioning type for pg_partman`.
            *   **Étape 3 (Succès):** Utilisation de `partman.create_parent` avec les paramètres corrects : `p_parent_table := 'public.events'`, `p_control := 'timestamp'`, `p_type := 'range'`, `p_interval := '1 month'`, `p_premake := 4`.
            *   **Apprentissage clé:** Dans `pg_partman 5.x`, `p_type` spécifie la *stratégie* (`range` ou `list`), pas le mécanisme (`native`). La version 5+ utilise *toujours* le partitionnement natif de PostgreSQL.
        *   **Vérification:** La commande `\dt public.events_p*` confirme la création des partitions mensuelles (ex: `events_p20241201`, `events_p20250101`, ...).
        *   **À FAIRE (Manuel):** L'index HNSW (`CREATE INDEX ON partition_name USING hnsw (...)`) doit toujours être créé manuellement sur chaque partition (existante et future). Une fonction pour automatiser cela lors de la création de partition par `pg_partman` (via `p_template_table` ou trigger) pourrait être explorée plus tard.
        *   **Maintenance:** La tâche périodique pour créer/détacher les partitions (`partman.run_maintenance_proc()`) doit être configurée (ex: via `pg_cron` dans le conteneur `db`). C'est en dehors du scope de cette story initiale.

2.  **STORY-03.2: [Repository] Implémentation `search_vector` (Logique Post-Filtrage)**
    *   **En tant que** Développeur Système MnemoLite,
    *   **Je veux** implémenter une méthode `search_vector` dans `EventRepository` qui accepte un vecteur de requête, des filtres de métadonnées, un `top_k`, des paramètres de temps et de pagination,
    *   **Afin de** exécuter une recherche hybride en utilisant la stratégie de post-filtrage (requête vectorielle d'abord avec sur-échantillonnage, puis filtrage metadata).
    *   *Critères d'Acceptation:*
        *   Une méthode `search_vector(self, vector: Optional[List[float]], top_k: int, ..., metadata: Optional[Dict], limit: int, offset: int) -> List[EventModel]` existe.
        *   Elle construit et exécute une requête SQL utilisant une CTE pour le `ORDER BY embedding <=> $1 LIMIT N*top_k` (Nearest Neighbor), suivie d'un `WHERE metadata @> $2` sur la CTE.
        *   Elle gère correctement les cas où `vector` et/ou `metadata` sont `None` (retourne une recherche par filtre seul, ou juste paginée, ou échoue si aucun critère ? À définir).
        *   Le `LIMIT` et `OFFSET` finaux sont appliqués correctement.
        *   Un facteur de sur-échantillonnage raisonnable (ex: 5) est utilisé pour la recherche NN initiale.
        *   Des tests unitaires (avec mock `asyncpg` ou connexion de test isolée si possible) valident la logique SQL et la gestion des paramètres.
    *   **Statut:** **FAIT**
    *   **Notes / Problèmes Rencontrés & Solutions:**
        *   **Fait:** Méthode `search_vector` implémentée dans `EventRepository`.
        *   **Fait:** Utilise la stratégie post-filtrage (CTE pour KNN + filtres externes).
        *   **Fait:** Gère les cas `vector=None`, `metadata=None`, et hybrides.
        *   **Fait:** Applique `LIMIT`/`OFFSET` finaux. Facteur overfetch codé à 5 pour l'instant.
        *   **Fait:** Tests unitaires avec `pytest-mock` ajoutés pour les scénarios metadata-only, vector-only, et hybrid. Les tests passent.
        *   Définir le comportement exact si `vector` est `None`. -> Comportement actuel: Recherche par filtres + tri timestamp DESC.
        *   Où/Comment gérer le `total_hits` pour la pagination ? Une requête `COUNT(*)` séparée avec les mêmes filtres ? Coûteux. Peut-être l'omettre ou le rendre approximatif pour l'instant. -> Non implémenté pour l'instant, omis.

3.  **STORY-03.3: [API] Intégration Recherche Vecteur & Hybride dans `/v1/search`**
    *   **En tant que** Développeur API,
    *   **Je veux** modifier l'endpoint `GET /v1/search/` pour accepter les nouveaux paramètres (`vector_query`, `top_k`, `ts_start`, `ts_end`) en plus de `filter_metadata`, `limit`, `offset`,
    *   **Afin de** permettre aux clients d'effectuer des recherches sémantiques et hybrides via l'API REST.
    *   *Critères d'Acceptation:*
        *   L'endpoint `GET /v1/search/` accepte les paramètres optionnels `vector_query` (format à définir : string base64 ? string floats séparés par virgule ?), `top_k` (int), `ts_start`/`ts_end` (datetime string).
        *   La route parse et valide ces paramètres (ex: décoder base64, convertir string en liste de floats, vérifier dimension, parser dates). Erreur 422 si invalide.
        *   La route appelle la méthode `repository.search_vector()` avec les paramètres appropriés.
        *   La réponse utilise le modèle `EventSearchResults` (`{"data": [...], "meta": {...}}`) incluant les résultats et les métadonnées de recherche (limit, offset, total_hits si dispo, query_time).
        *   La spécification OpenAPI (`docs/v2/Specification_API.md`) est mise à jour pour refléter les nouveaux paramètres et la réponse.
    *   **Statut:** **FAIT** *(Implémentation initiale)*
    *   **Notes / Problèmes Rencontrés & Solutions:**
        *   **Fait:** Endpoint `GET /v1/search` modifié pour accepter `vector_query`, `top_k`, `ts_start`, `ts_end`, `filter_metadata`, `limit`, `offset`.
        *   **Fait:** Validation des paramètres ajoutée (Base64 pour `vector_query`, types, etc.). Erreur 422 retournée si invalide.
        *   **Fait:** Appel à `repository.search_vector()` effectué.
        *   **Fait:** Réponse `EventSearchResults` utilisée. Spécification OpenAPI mise à jour.
        *   **Format `vector_query`:** Choix de Base64 encodant une string JSON `"[0.1, 0.2, ...]"` pour compacité et éviter les problèmes d'encodage URL avec les floats.
        *   **Interaction `top_k`/`limit`:** Clarifié que `top_k` est pour la recherche KNN initiale (avec sur-échantillonnage), `limit` est pour le résultat final retourné au client.
        *   **Problèmes de Tests d'Intégration:** Rencontré des erreurs `asyncpg.InterfaceError: connection is closed` et `ConnectionDoesNotExistError` intermittentes lors de l'exécution des tests pour `/v1/search` (`tests/test_search_routes.py`), potentiellement dues à des conflits entre le `TestClient` synchrone, `anyio`, et le pool de connexions `asyncpg`, ou à une fuite d'état entre les tests lors de l'utilisation de fixtures `scope="session"`.
        *   **Solution Tests:** Résolu en revenant à des fixtures `scope="function"` pour le pool de base de données (`test_db_pool`) et le client de test (`client`), et en s'assurant que la base de données est explicitement tronquée (`TRUNCATE TABLE events`) *avant* chaque exécution de test via la fixture `client`. Cela garantit une isolation stricte entre les tests. Les tests sont maintenant stables.

4.  **STORY-03.4: [PoC] Validation Performance & Rappel**
    *   **En tant que** Développeur Système MnemoLite,
    *   **Je veux** réaliser un Proof of Concept en chargeant une quantité significative de données (ex: 500k+ événements avec embeddings) et en mesurant la latence (P95) et le rappel (Recall@k) des requêtes hybrides,
    *   **Afin de** valider l'efficacité de l'approche HNSW + post-filtrage et d'ajuster les paramètres (index, facteur over-fetch) si nécessaire.
    *   *Introduction & Contexte:*
        *   **Besoin:** Valider si notre stratégie de recherche hybride (index HNSW `pgvector` + post-filtrage metadata/temps sur la table `events` partitionnée par mois via `pg_partman`) est performante et pertinente sous une charge de données réaliste (~1 million d'événements).
        *   **Objectif PoC:** Mesurer la latence P95 et le Rappel@k pour divers scénarios de requêtes hybrides. Confirmer l'atteinte des SLOs (ex: P95 < 200ms, Rappel@k ≥ 0.9) ou identifier les points d'amélioration.
    *   *Critères d'Acceptation:*
        *   Un script (`scripts/benchmarks/generate_test_data.py`) génère et charge ~1M+ événements via `asyncpg`.
        *   Les index HNSW sont créés sur les partitions après le chargement.
        *   Un script (`scripts/benchmarks/run_benchmark.py`) exécute un benchmark de requêtes hybrides variées (vector, metadata, hybrid ; `top_k`, filtres, partitions).
        *   Les métriques de latence P95 (client/serveur) et de Rappel@k (vs. exact KNN sur échantillon) sont collectées.
        *   Les résultats sont analysés, comparés aux SLOs (P95 < 200ms, Recall@k ≥ 0.9).
        *   Les paramètres (`ef_search`, over-fetch, `work_mem`) sont ajustés si nécessaire, et les choix finaux sont documentés.
    *   **Statut:** **EN COURS (Benchmark setup initial fait)**
    *   **Plan d'Action / Tâches:**
        *   **Note:** Le script `run_benchmark.py` est fonctionnel mais l'analyse complète et le tuning sont reportés.
        1.  **[À Faire] Génération Données:**
            *   Créer `scripts/benchmarks/generate_test_data.py`.
            *   Implémenter la génération de ~1M événements (timestamps réalistes, metadata variés, embeddings normalisés).
            *   Utiliser `asyncpg.copy_records_to_table` pour l'insertion.
            *   Exécuter pour peupler la base.
        2.  **[À Faire] Création Index:**
            *   Script (ou commandes manuelles) pour `CREATE INDEX CONCURRENTLY ... USING hnsw (...)` sur chaque partition après chargement.
        3.  **[À Faire] Implémentation Benchmark:**
            *   Créer `scripts/benchmarks/run_benchmark.py`.
            *   Définir la matrice de requêtes test.
            *   Implémenter l'appel à `EventRepository.search_vector`.
            *   Ajouter la mesure de latence (client-side `perf_counter_ns`, optionnel `EXPLAIN ANALYZE`).
        4.  **[À Faire] Mesure Rappel:**
            *   Implémenter le calcul de Recall@k (cible ≥ 0.9).
            *   Générer la vérité terrain (exact KNN) sur un échantillon (ex: 1%).
            *   Comparer les résultats HNSW du benchmark.
        5.  **[À Faire] Exécution & Analyse:**
            *   Exécuter le benchmark.
            *   Collecter et analyser les métriques (P95 latence, Recall@k).
            *   Comparer aux SLOs.
        6.  **[À Faire] Tuning (si besoin):**
            *   Ajuster `ef_search`, over-fetch, `work_mem` de manière systématique.
            *   Relancer le benchmark pour valider les améliorations.
        7.  **[À Faire] Documentation:**
            *   Documenter les résultats finaux, paramètres optimaux et conclusions dans cette story.

*(Ajouter STORY-03.5 pour les tests d'intégration spécifiques à la recherche hybride une fois la fonctionnalité de base validée par le PoC)*

--- 