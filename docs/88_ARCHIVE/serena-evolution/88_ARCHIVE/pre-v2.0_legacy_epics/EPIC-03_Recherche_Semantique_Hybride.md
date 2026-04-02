# EPIC-03: Recherche Sémantique & Hybride Performante

> ## ⚠️ DOCUMENT HISTORIQUE (Q1-Q2 2025)
>
> **Ce document fait partie des archives du développement initial**.
> Consultez [`docs/agile/README.md`](README.md) pour le contexte complet.
>
> **⚠️ ATTENTION** : Ce document contient des références à des **dimensions d'embeddings obsolètes (1536)**.
> La version actuelle utilise **768 dimensions** (nomic-embed-text-v1.5).
>
> **Pour la documentation à jour** :
> - Architecture actuelle : [`/docs/Document Architecture.md`](../Document%20Architecture.md)
> - API actuelle : [`/docs/Specification_API.md`](../Specification_API.md)

---

**Objectif :** Optimiser l'architecture de recherche de MnemoLite pour supporter efficacement la **recherche hybride** à grande échelle, combinant :
1. **Similarité vectorielle** (embeddings + pgvector HNSW)
2. **Filtrage métadonnées** (JSONB + GIN index)
3. **Filtrage temporel** (partitionnement par timestamp via pg_partman)

**Motivation :** Après avoir implémenté les recherches de base (EPIC-02), il est essentiel d'optimiser l'architecture pour :
- **Performance** : Atteindre < 15ms P95 pour les recherches hybrides sur des volumes importants (50k-1M événements)
- **Scalabilité** : Gérer la croissance des données via partitionnement temporel
- **Pertinence** : Combiner efficacement similarité sémantique et filtres métadonnées/temporels

**Approche Architecturale Choisie :**
**"Post-Filtrage HNSW + Partitionnement"**

```
┌─────────────────────────────────────────────┐
│ 1. Recherche KNN (HNSW sur partition)      │
│    → Retourne top-K*overfetch vecteurs     │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│ 2. Post-filtrage (metadata + temps)        │
│    → Applique filtres sur résultats KNN    │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│ 3. Pagination finale                        │
│    → Retourne limit résultats au client    │
└─────────────────────────────────────────────┘
```

**Critères d'Acceptation Généraux (DoD - Definition of Done pour l'Epic) :**

### Infrastructure & Indexation
*   ✅ Table `events` partitionnée par RANGE sur `timestamp` (mensuel) via `pg_partman`
*   ✅ Index HNSW créés sur la colonne `embedding` de chaque partition
*   ✅ Paramètres HNSW documentés (`m=16`, `ef_construction=64`)
*   ✅ Configuration `pg_partman` opérationnelle (création automatique de partitions)

### Repository & Logique
*   ✅ Méthode `EventRepository.search_vector()` implémentée avec stratégie post-filtrage
*   ✅ Support des paramètres : `vector`, `metadata`, `ts_start`, `ts_end`, `limit`, `offset`
*   ✅ Facteur de sur-échantillonnage (overfetch) configurable (défaut: 5x)
*   ✅ Gestion des cas edge : vector seul, metadata seul, hybride, aucun critère

### API
*   ✅ Endpoint `GET /v1/search` étendu pour accepter tous les paramètres de recherche
*   ✅ Validation robuste (dimension vecteur, format dates ISO, JSON metadata)
*   ✅ Format de réponse cohérent avec `SearchResults` (`data`, `meta`)
*   ✅ Documentation OpenAPI mise à jour

### Performance & Validation
*   ✅ PoC réalisé avec ~50k événements (3 mois de données)
*   ✅ Benchmark léger exécuté sur scénarios clés :
    - Vector seul : **~12ms P95** ✅
    - Hybride (vector + metadata) : **~11ms P95** ✅
    - Metadata + temps : **~3ms P95** ✅ (partition pruning validé)
*   ✅ Tests d'intégration fonctionnels pour tous les scénarios de recherche

**User Stories Associées :**
- Voir [`STORIES_EPIC-03.md`](STORIES_EPIC-03.md) pour les 6 stories détaillées

**Statut :** ✅ **TERMINÉ** (Architecture validée, performances excellentes à 50k événements)

**Résultats Clés du PoC :**

| Type de Recherche | P50 | P95 | Observations |
|-------------------|-----|-----|--------------|
| **Vector Seul** | 11.30ms | 12.21ms | HNSW très performant |
| **Hybride (type=log)** | 11.03ms | 11.33ms | Post-filtrage efficace |
| **Metadata Seul** | 280ms | 306ms | Scan de partitions (sans filtre temps) |
| **Metadata + Temps (1 mois)** | 2.97ms | 3.43ms | **Partition pruning 100x plus rapide** ✅ |

**Décisions Architecturales Importantes :**

1. **Partitionnement Mensuel** : Choix de l'intervalle mensuel pour équilibre entre granularité et nombre de partitions
2. **Index HNSW par Partition** : Nécessité de créer les index manuellement sur chaque partition (limitation pg_partman)
3. **Facteur Overfetch=5** : Valeur empirique pour équilibrer recall et performance
4. **Post-Filtrage** : Plus performant que pré-filtrage pour notre cas d'usage (métadonnées peu sélectives)

**Alternatives Considérées (Rejetées) :**

| Alternative | Raison du Rejet |
|-------------|-----------------|
| **Pré-filtrage (Filtered KNN)** | Recall instable, performances imprévisibles |
| **Table Distincte pour Index** | Complexité de synchronisation, maintenance accrue |
| **IVFFlat au lieu de HNSW** | HNSW > IVFFlat pour nos cas d'usage (< 10M vecteurs) |

**Leçons Apprises :**

1. **Partition Pruning = Game Changer** : Filtres temporels essentiels pour performance (300ms → 3ms)
2. **HNSW Parameters Matter** : `m=16` / `ef_construction=64` offre bon compromis build/query
3. **Overfetch Nécessaire** : Sans over-sampling, recall dégradé sur recherches hybrides
4. **Test Data Important** : Génération de données réalistes critique pour validation

**Recommandations pour Production :**

1. **Documentation Utilisateur** : Encourager fortement l'utilisation de filtres temporels
2. **Monitoring** : Surveiller latence des requêtes sans filtres temporels
3. **Maintenance** : Configurer `pg_cron` pour exécution périodique de `partman.run_maintenance_proc()`
4. **Index Management** : Automatiser création HNSW sur nouvelles partitions (script ou trigger)
5. **Archivage** : Stratégie de détachement des partitions anciennes (> 12 mois)

**Prochaines Étapes (Post-EPIC-03) :**

- ⏳ EPIC-04 : Refactoring avec bonnes pratiques (DIP, Repository pattern strict)
- ⏳ Optimisation Hot/Warm : Quantization INT8 des vecteurs après 12 mois (pg_cron) [TODO]
- ⏳ Scaling Test : Validation performance à 1M+ événements

**Dépendances :**

- ✅ EPIC-02 (Recherche de base opérationnelle)
- ✅ PostgreSQL 17 + pgvector + pg_partman installés
- ✅ Script de génération de données de test
- ✅ Infrastructure de benchmarking

**Risques & Mitigations :**

| Risque | Impact | Mitigation | Statut |
|--------|--------|-----------|--------|
| Performance dégradée à 1M+ events | Moyen | Validation nécessaire, tuning HNSW | ⏳ À valider |
| Maintenance index HNSW manuelle | Faible | Script automatisation, documentation | ✅ Documenté |
| Recall dégradé sur post-filtrage | Moyen | Overfetch=5, monitoring recall | ✅ Validé PoC |
| Partition pruning non effectif | Élevé | Tests validation, EXPLAIN ANALYZE | ✅ Validé (100x) |

---

**Date de Création** : Q1-Q2 2025
**Dernière Mise à Jour** : 2025-10-13
**Statut Archive** : Document historique
**Version Architecture** : v1.1.0 (Pré-migration embeddings locaux)
