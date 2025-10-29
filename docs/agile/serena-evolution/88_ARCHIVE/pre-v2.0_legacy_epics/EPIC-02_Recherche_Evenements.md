# EPIC-02: Recherche d'Événements (Filtrage Métadonnées & Recherche Sémantique)

> ## ⚠️ DOCUMENT HISTORIQUE (Q1-Q2 2025)
>
> **Ce document fait partie des archives du développement initial**.
> Consultez [`docs/agile/README.md`](README.md) pour le contexte complet.
>
> **Pour la documentation à jour** :
> - Architecture actuelle : [`/docs/Document Architecture.md`](../Document%20Architecture.md)
> - API actuelle : [`/docs/Specification_API.md`](../Specification_API.md)

---

**Objectif :** Permettre aux utilisateurs de l'API MnemoLite de rechercher et filtrer des événements de deux manières complémentaires :
1. **Filtrage par métadonnées** : Recherche basée sur des critères JSON dans le champ `metadata` (ex: `type=log`, `project=Expanse`)
2. **Recherche sémantique** : Recherche par similarité d'embeddings pour trouver des événements sémantiquement proches d'une requête textuelle

**Motivation :** Après avoir établi les opérations CRUD de base (EPIC-01), la prochaine étape logique est de permettre aux clients de **retrouver** efficacement les événements stockés. Cette fonctionnalité est essentielle pour :
- Explorer les données par catégories/tags (métadonnées)
- Rechercher des événements par similarité sémantique (embeddings)
- Préparer l'infrastructure pour les recherches hybrides avancées (EPIC-03)

**Contexte Technique :**
- Utilisation de l'opérateur PostgreSQL `@>` pour le filtrage JSONB sur `metadata`
- Utilisation de pgvector avec l'opérateur de distance pour la recherche par embedding
- Endpoint unifié `GET /v1/search` avec paramètres optionnels `filter_metadata` et `vector_query`

**Critères d'Acceptation Généraux (DoD - Definition of Done pour l'Epic) :**

*   Le `EventRepository` expose une méthode `filter_by_metadata(metadata_criteria: Dict[str, Any]) -> List[EventModel]` fonctionnelle.
*   L'endpoint API `GET /v1/search` accepte le paramètre `filter_metadata` (chaîne JSON) et retourne les événements correspondants.
*   Le parsing JSON du paramètre `filter_metadata` est robuste avec gestion d'erreurs appropriée (422 si invalide).
*   Les recherches par métadonnées utilisent efficacement l'index GIN sur la colonne `metadata`.
*   Des tests unitaires et d'intégration valident le filtrage par métadonnées.
*   La documentation API (`Specification_API.md`) est mise à jour avec les exemples de recherche.
*   (Optionnel pour cet Epic) Une méthode de recherche sémantique de base est implémentée dans le Repository.

**User Stories Associées :**
- Voir [`STORIES_EPIC-02.md`](STORIES_EPIC-02.md) pour les stories détaillées

**Statut :** ✅ **TERMINÉ** (Code fonctionnel, tests d'intégration API reportés)

**Prochaines Étapes :**
- EPIC-03 : Optimisation de la recherche hybride (vecteur + métadonnées + temps) avec partitionnement et indexation HNSW

**Notes Techniques Importantes :**
- **Index GIN** : Créé sur `metadata` avec `jsonb_path_ops` pour performance optimale
- **Format de réponse** : Utilisation du modèle `SearchResults` avec structure `{data: [...], meta: {...}}`
- **Gestion d'erreurs** : Validation stricte des paramètres avec retours HTTP appropriés (422, 404, 500)

**Dépendances :**
- ✅ EPIC-01 (CRUD de base opérationnel)
- PostgreSQL 17 avec extension pgvector installée
- Table `events` avec colonne `metadata` JSONB

**Risques & Mitigations :**
- **Risque** : Performance dégradée sur recherches métadonnées sans filtres temporels
  - **Mitigation** : Documentation encourageant l'utilisation de filtres temporels, implémentation du partitionnement (EPIC-03)
- **Risque** : Format JSON invalide dans `filter_metadata`
  - **Mitigation** : Validation stricte avec messages d'erreur clairs (422)

---

**Date de Création** : Q1 2025
**Dernière Mise à Jour** : 2025-10-13
**Statut Archive** : Document historique
