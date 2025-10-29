# User Stories pour EPIC-02: Recherche d'Événements (Filtrage Métadonnées & Recherche Sémantique)

*(Perspective: Développeur / Système Client utilisant l'API MnemoLite)*

## Objectifs de l'Epic:

1.  Permettre le filtrage des événements basé sur leur champ `metadata`.
2.  Permettre la recherche d'événements basé sur la similarité sémantique de leur `embedding`.
3.  (Optionnel) Intégrer la pagination et le tri dans les recherches.

---

## User Stories:

1.  **STORY-02.1: [Repository] Filtrer les événements par métadonnées**
    *   **En tant que** Développeur Système MnemoLite,
    *   **Je veux** implémenter une méthode dans `EventRepository` (par exemple, `filter_by_metadata`) qui accepte un dictionnaire de critères et retourne une liste d'événements dont le champ `metadata` contient ces critères,
    *   **Afin de** fournir une base pour l'API de recherche par métadonnées.
    *   *Critères d'Acceptation:*
        *   Une méthode `filter_by_metadata(self, metadata_criteria: Dict[str, Any]) -> List[EventModel]` existe dans `EventRepository`. **[FAIT]**
        *   La méthode utilise une requête SQL `SELECT` avec une clause `WHERE metadata @> $1::jsonb` (ou un opérateur JSONB similaire approprié). **[FAIT]**
        *   La méthode retourne une liste d'objets `EventModel` correspondants (potentiellement vide). **[FAIT]**
        *   Des tests unitaires valident le fonctionnement de la méthode avec différents critères (cas simple, cas où rien ne correspond). **[FAIT]**
    *   **Statut:** **Terminé**
    *   **Notes / Problèmes Rencontrés & Solutions:**
        *   Implémentation de `filter_by_metadata` avec `conn.fetch` et l'opérateur `@>`.
        *   Ajout de tests unitaires `test_filter_by_metadata_found` et `test_filter_by_metadata_not_found` qui passent.

2.  **STORY-02.2: [API] Rechercher des événements par métadonnées (via `GET /v1/search`)**
    *   **En tant que** Développeur API / Client API,
    *   **Je veux** pouvoir envoyer une requête `GET /v1/search` avec un paramètre `filter_metadata` contenant une chaîne JSON,
    *   **Afin de** récupérer une liste d'événements dont les métadonnées correspondent aux critères JSON fournis.
    *   *Critères d'Acceptation:*
        *   Un endpoint API `GET /v1/search` existe (implémenté via `GET /` dans `search_routes.py` avec préfixe `/v1/search`). **[FAIT]**
        *   Il accepte un paramètre de requête `filter_metadata` (chaîne optionnelle). **[FAIT]**
        *   La chaîne `filter_metadata` est parsée en JSON (dict). Une erreur 422 est levée si invalide. **[FAIT]**
        *   La route utilise la méthode `EventRepository.filter_by_metadata()` si le filtre est fourni et valide. **[FAIT]**
        *   La route retourne une liste d'objets `EventModel` (ou une liste vide). **[FAIT]**
        *   Le format de la réponse est cohérent (utilisation du modèle `SearchResults`). **[FAIT]**
        *   Des tests d'intégration valident la recherche via l'API. **[À FAIRE]**
    *   **Statut:** **Terminé (Code) / Tests API À FAIRE**
    *   **Notes / Problèmes Rencontrés & Solutions:**
        *   Implémentation via `GET /v1/search?filter_metadata=...` pour s'aligner sur `Specification_API.md`.
        *   Refactorisation de `api/routes/search_routes.py` pour ajouter la route `GET /` et commenter le code v0.
        *   Ajout du parsing JSON pour `filter_metadata` avec gestion des erreurs (JSONDecodeError, ValueError).
        *   Utilisation d'un modèle de réponse `SearchResults` simple.
        *   **Débogage API:** Rencontré un problème persistant de `404 Not Found` sur l'endpoint `POST /v1/events/`, malgré une configuration semblant correcte dans `event_routes.py` et `main.py`.
            *   Les étapes de débogage ont inclus : vérification des imports, simplification drastique du routeur d'événements, vérification des logs de démarrage (qui ne montraient pas d'erreur), et isolation des routeurs en commentant les autres inclusions dans `main.py`.
            *   **Cause Racine:** La cause principale identifiée était l'**absence du préfixe `/v1/events`** lors de l'appel à `app.include_router(event_routes.router, ...)` dans `api/main.py`. Les routes étaient enregistrées sous `/` au lieu de `/v1/events/`.
            *   **Facteur Aggravant:** Un problème non lié dans le service *worker* (`ModuleNotFoundError: pgmq`, résolu par `docker compose build --no-cache worker`) et les étapes d'isolation ont temporairement masqué le fait que la simple correction du préfixe suffisait.
            *   **Solution:** Après correction du préfixe dans `main.py` et résolution du problème du worker, la route `POST /v1/events/` est devenue fonctionnelle avec *tous* les routeurs réactivés. Ce problème souligne l'importance de vérifier attentivement les préfixes lors de l'inclusion des routeurs FastAPI.
        *   Tests API reportés en attendant la résolution du problème de mocking.
        *   **Tests d'Intégration (httpx):** Tentative d'implémentation de tests d'intégration avec `httpx` (ciblant une API démarrée) et une base de données de test dédiée.
            *   **Problème Rencontré:** Les tests échouent avec des erreurs `KeyError: 'data'` initialement (problème de format de réponse API qui a été corrigé) puis avec des assertions `assert len(response_data["data"]) == 1` (car la recherche ne retourne rien).
            *   Les logs de debug du repository ne montrent pas d'erreur SQL, mais la recherche via l'API ne retourne pas les données insérées pendant le test.
            *   **Hypothèses:** Problème potentiel avec l'isolation des tests (nettoyage de la DB via `TRUNCATE`), ou interaction complexe entre `httpx`, l'API en cours d'exécution et `asyncpg` lors de la requête `WHERE metadata @> $1::jsonb`.
            *   **Statut:** Investigation mise en pause. Les tests d'intégration pour la recherche par métadonnées restent **À FAIRE**. 