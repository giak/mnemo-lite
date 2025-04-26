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
        *   (Optionnel pour PoC, mais recommandé) La table `events` est définie comme partitionnée par `RANGE` sur `timestamp` (ex: mensuellement), ou la structure le permettant est en place.
        *   La documentation de la structure DB (`docs/bdd_schema.md`) est mise à jour.
    *   **Statut:** **PARTIELLEMENT FAIT**
    *   **Notes / Problèmes Rencontrés & Solutions:**
        *   **Fait:** La table `events` est définie avec `PARTITION BY RANGE (timestamp)` comme documenté dans `docs/bdd_schema.md`. La structure de base est prête.
        *   **Fait:** La documentation `docs/bdd_schema.md` est à jour concernant la structure de la table et la définition de l'index HNSW (cosine, params `m=16, ef_construction=64`).
        *   **À FAIRE (Manuel):** L'index HNSW (`CREATE INDEX ON partition_name USING hnsw (...)`) doit être créé manuellement sur chaque partition existante et future. L'automatisation via `pg_partman` ou similaire est différée pour le moment.
        *   Quel partitionnement choisir (mensuel, hebdomadaire) ? Impact sur la maintenance vs performance. -> Décision différée avec l'automatisation.
        *   Comment gérer la création de nouvelles partitions (manuel, `pg_partman`, trigger) ? -> Gestion manuelle pour l'instant.

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
    *   **Statut:** **À FAIRE**
    *   **Notes / Problèmes Rencontrés & Solutions:**
        *   Choisir le format de `vector_query`. Base64 est plus compact mais moins lisible. Floats séparés par virgule est plus simple mais peut poser problème avec les limites d'URL si la dimension est grande (1536 ici, c'est beaucoup). JSON dans le corps serait idéal mais c'est un `GET`. Peut-être accepter les deux ou privilégier Base64 ?
        *   Comment `top_k` interagit avec `limit` ? `top_k` est pour la recherche NN initiale, `limit` est pour le résultat final.

4.  **STORY-03.4: [PoC] Validation Performance & Rappel**
    *   **En tant que** Développeur Système MnemoLite,
    *   **Je veux** réaliser un Proof of Concept en chargeant une quantité significative de données (ex: 500k+ événements avec embeddings) et en mesurant la latence (P95) et le rappel (Recall@k) des requêtes hybrides,
    *   **Afin de** valider l'efficacité de l'approche HNSW + post-filtrage et d'ajuster les paramètres (index, facteur over-fetch) si nécessaire.
    *   *Critères d'Acceptation:*
        *   Un script ou notebook existe pour générer/importer des données de test à grande échelle.
        *   Un script ou notebook existe pour exécuter un benchmark de requêtes hybrides variées (différents `top_k`, sélectivité des filtres).
        *   Les métriques de latence P95 et de rappel (comparé à une recherche exhaustive sur petit dataset) sont collectées.
        *   Les résultats sont analysés pour confirmer l'atteinte des SLO (<100ms) ou identifier les goulets d'étranglement.
        *   Les paramètres d'index HNSW (`ef_search`) et le facteur d'over-fetch sont potentiellement ajustés.
    *   **Statut:** **À FAIRE**
    *   **Notes / Problèmes Rencontrés & Solutions:**
        *   Génération des embeddings factices mais réalistes.
        *   Définition d'un benchmark représentatif.
        *   Comment mesurer le rappel efficacement ?

*(Ajouter STORY-03.5 pour les tests d'intégration spécifiques à la recherche hybride une fois la fonctionnalité de base validée par le PoC)*

--- 