# MnemoLite – Schéma SQL Raffiné

> 📅 **Dernière mise à jour**: 2025-10-13
> 📝 **Version**: v1.3.0
> ✅ **Statut**: À jour avec le code

## Contexte
Ce schéma documente la structure de la base de données MnemoLite, alignée avec le PFD v1.2.2, le PRD v1.0.2 et l'ARCH v1.1.1. Il s'appuie sur une architecture 100% PostgreSQL optimisée pour un déploiement local, combinant une table principale `events` partitionnée (temps/vecteur) et des tables `nodes`/`edges` pour le graphe conceptuel.

---

## Extensions Requises

```sql
------------------------------------------------------------------
-- Extensions (gérées par le script db/init/01-extensions.sql)
------------------------------------------------------------------
-- Utilisé pour gen_random_uuid() pour les IDs
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Nécessaire pour le type VECTOR et les index HNSW/IVFFlat
CREATE EXTENSION IF NOT EXISTS vector;

-- Utilisé pour le partitionnement automatique de la table 'events'
CREATE SCHEMA IF NOT EXISTS partman; -- Création du schéma dédié
CREATE EXTENSION IF NOT EXISTS pg_partman SCHEMA partman;

-- Optionnel: Non activé par défaut, mais nécessaire pour la quantisation planifiée
-- CREATE EXTENSION IF NOT EXISTS pg_cron;
```

---

## Schéma SQL (défini dans `db/init/01-init.sql`)

```sql
------------------------------------------------------------------
-- Table Principale: events (partitionnée par mois sur timestamp)
------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events (
    id          UUID NOT NULL DEFAULT gen_random_uuid(),
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    content     JSONB NOT NULL,             -- Contenu flexible: { "type": "prompt", ... } ou { "type": "decision", ... }
    embedding   VECTOR(768),                -- Embedding (nomic-embed-text-v1.5)
    metadata    JSONB DEFAULT '{}'::jsonb,  -- Tags, source, IDs, types, etc.
    -- Clé primaire composite, incluant la clé de partitionnement
    PRIMARY KEY (id, timestamp)
)
PARTITION BY RANGE (timestamp);

COMMENT ON TABLE events IS 'Table principale stockant tous les evenements atomiques (partitionnee par mois sur timestamp).';
COMMENT ON COLUMN events.content IS 'Contenu detaille de l evenement au format JSONB.';
COMMENT ON COLUMN events.embedding IS 'Vecteur semantique du contenu (dimension 768 pour nomic-embed-text-v1.5).';
COMMENT ON COLUMN events.metadata IS 'Metadonnees additionnelles (tags, IDs, types) au format JSONB.';

-- Note: La création des partitions est gérée par pg_partman via le script `db/init/02-partman-config.sql`
-- Ex: SELECT partman.create_parent('public.events', 'timestamp', 'range', '1 month', ...);

-- Index B-tree sur timestamp (clé de partitionnement), hérité par les partitions
CREATE INDEX IF NOT EXISTS events_timestamp_idx ON events (timestamp);

-- Index GIN sur metadata pour recherches flexibles, hérité par les partitions
CREATE INDEX IF NOT EXISTS events_metadata_gin_idx ON events USING GIN (metadata jsonb_path_ops);

-- NOTE IMPORTANTE sur l'index vectoriel (HNSW/IVFFlat):
-- Il DOIT etre cree sur chaque partition individuelle, PAS sur la table mere.
-- Ceci est generalement gere via des hooks pg_partman ou des scripts de maintenance.
-- Exemple pour une partition 'events_pYYYY_MM':
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS events_pYYYY_MM_embedding_hnsw_idx
-- ON events_pYYYY_MM USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

------------------------------------------------------------------
-- Tables Graphe Conceptuel/Événementiel
------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS nodes (
    node_id         UUID PRIMARY KEY, -- Generalement un event.id, mais peut etre autre chose (concept genere)
    node_type       TEXT NOT NULL,    -- Ex: 'event', 'concept', 'entity', 'rule', 'document'
    label           TEXT,             -- Nom lisible pour affichage/requete
    properties      JSONB DEFAULT '{}'::jsonb, -- Attributs additionnels du nœud
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
COMMENT ON TABLE nodes IS 'Noeuds du graphe conceptuel (evenements, concepts, entites).';

CREATE INDEX IF NOT EXISTS nodes_type_idx ON nodes(node_type);
-- Optionnel: Index sur label si recherche frequente par nom
-- CREATE INDEX IF NOT EXISTS nodes_label_idx ON nodes USING gin (label gin_trgm_ops);

CREATE TABLE IF NOT EXISTS edges (
    edge_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_node_id  UUID NOT NULL, -- Reference logique nodes.node_id
    target_node_id  UUID NOT NULL, -- Reference logique nodes.node_id
    relation_type   TEXT NOT NULL, -- Ex: 'causes', 'mentions', 'related_to', 'follows', 'uses_tool', 'part_of'
    properties      JSONB DEFAULT '{}'::jsonb, -- Poids, timestamp de la relation, etc.
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
COMMENT ON TABLE edges IS 'Relations (aretes) entre les noeuds du graphe conceptuel.';
COMMENT ON COLUMN edges.source_node_id IS 'ID du noeud source (pas de FK physique).';
COMMENT ON COLUMN edges.target_node_id IS 'ID du noeud cible (pas de FK physique).';

CREATE INDEX IF NOT EXISTS edges_source_idx ON edges(source_node_id);
CREATE INDEX IF NOT EXISTS edges_target_idx ON edges(target_node_id);
CREATE INDEX IF NOT EXISTS edges_relation_type_idx ON edges(relation_type);
-- Optionnel: Index composite pour requêtes fréquentes
-- CREATE INDEX IF NOT EXISTS edges_source_type_target_idx ON edges(source_node_id, relation_type, target_node_id);

-- Note: Pas de contraintes de clé étrangère (FK) sur edges pour flexibilité.
-- La cohérence est gérée par l'application ou des checks périodiques.
```

---

## Explications Détaillées des Choix de Conception

L'objectif global était de créer une base **robuste**, **performante pour les cas d'usage locaux**, **facile à déployer/maintenir** et **évolutive** dans le contexte d'une machine personnelle ou d'un petit serveur, en s'appuyant **uniquement** sur PostgreSQL 17 et ses extensions.

### 1. Table `events` comme Cœur et Partitionnement Temporel (`pg_partman`)

*   **Pourquoi ?**
    *   **Source de vérité unique :** Tous les faits bruts (interactions, décisions, observations...) arrivent ici. C'est simple et logique.
    *   **Nature temporelle :** Les interactions se déroulent dans le temps. Le partitionnement par `RANGE` sur `timestamp` est le moyen le plus naturel et efficace de gérer ce type de données.
    *   **Gestion du cycle de vie :** Plutôt que des `DELETE` complexes ou des flags `is_deleted`, on peut simplement *détacher* ou *supprimer* des partitions entières (mois) une fois qu'elles deviennent trop vieilles. C'est extrêmement rapide et efficace pour la rétention des données locales.
    *   **Automatisation :** `pg_partman` gère la création/suppression des partitions automatiquement, évitant des scripts manuels complexes et des oublis.
*   **Ce que ça apporte (Performance & Gestion) :**
    *   **Requêtes temporelles rapides :** Les recherches sur une période donnée (ex: "les 7 derniers jours") ne scannent que les partitions pertinentes, ignorant potentiellement une grande partie de la table.
    *   **Maintenance facilitée :** Sauvegarder, archiver, supprimer ou indexer une partition est beaucoup plus rapide que sur une table monolithique géante.
    *   **Index plus petits/efficaces :** Chaque partition a ses propres index (B-Tree, GIN, HNSW), qui sont plus petits et donc plus rapides à parcourir et à maintenir.
    *   **Extensibilité :** Très bonne sur l'axe du temps. Le système peut accumuler des années de données sans que les performances des requêtes sur les données récentes ne se dégradent.

### 2. Clé Primaire Composite `(id, timestamp)` sur `events`

*   **Pourquoi ?**
    *   **Contrainte PostgreSQL :** Pour partitionner une table, la clé de partitionnement (`timestamp` ici) *doit* faire partie de toute clé primaire ou contrainte d'unicité.
    *   **Unicité Logique :** Le couple `(id, timestamp)` garantit l'unicité d'un événement dans l'ensemble de la table logique (mère + partitions).
*   **Ce que ça apporte :**
    *   **Permet le partitionnement :** C'est la condition technique indispensable.
    *   **Garantit l'intégrité :** Assure qu'on n'a pas deux enregistrements pour le même ID au même instant exact.

### 3. Utilisation Intensive de `JSONB` (`content`, `metadata`)

*   **Pourquoi ?**
    *   **Flexibilité maximale :** Le type d'événements et les métadonnées associées peuvent varier énormément. `JSONB` permet de stocker tout ça sans avoir besoin de définir des dizaines de colonnes spécifiques ou de faire des `ALTER TABLE` constants.
    *   **Standardisation de fait :** Le JSON est omniprésent pour l'échange de données structurées/semi-structurées.
*   **Ce que ça apporte (Extensibilité & Performance) :**
    *   **Extensibilité sans friction :** On peut ajouter de nouveaux types d'événements ou de nouvelles métadonnées sans modifier le schéma SQL. L'application écrit juste une structure JSON différente.
    *   **Recherche puissante :** L'index GIN (`jsonb_path_ops`) permet de rechercher très efficacement *à l'intérieur* des JSONB, que ce soit sur des clés spécifiques (`metadata->>'rule_id' = 'X'`) ou sur l'existence de clés.
*   **Trade-offs :** Léger surcoût en stockage ; requêtes JSON parfois moins intuitives pour des accès très simples (largement compensé par la flexibilité ici).

### 4. Stockage Direct des `VECTOR` (`embedding`) et Index HNSW (`pgvector`)

*   **Pourquoi ?**
    *   **Colocalisation donnée/vecteur :** Garder le vecteur sémantique avec les données qu'il représente simplifie les requêtes.
    *   **Écosystème PG :** `pgvector` est une extension mature et performante. HNSW est l'algorithme d'indexation de choix pour un bon compromis vitesse/précision (Approximate Nearest Neighbor).
    *   **Simplification stack :** Évite d'avoir à gérer une base de données vectorielle séparée localement.
*   **Ce que ça apporte (Performance & Simplicité) :**
    *   **Recherche de similarité rapide :** L'index HNSW permet des recherches K-NN (K-Nearest Neighbors) très rapides, essentielles pour retrouver des souvenirs pertinents.
    *   **Requêtes hybrides faciles :** On peut combiner facilement dans une même requête SQL une recherche vectorielle (similarité sémantique) ET des filtres sur les métadonnées JSONB ou le timestamp.
    *   **Opérations simplifiées :** Une seule base à sauvegarder, monitorer, maintenir.
*   **Points d'attention :** L'index HNSW doit être créé et maintenu *par partition* (via `pg_partman` hooks) ; sa construction peut être gourmande en ressources.

### 5. Graphe Conceptuel (`nodes`/`edges`) et Absence de Clés Étrangères (FK)

*   **Pourquoi ?**
    *   **Représentation des relations :** Pour modéliser des liens (cause/effet, mention...). Essentiel pour les requêtes réflexives ("Pourquoi ?").
    *   **Découplage :** Les concepts/entités (`nodes`) peuvent exister indépendamment des `events` bruts.
    *   **Absence de FK sur `edges` :** Choix *délibéré* pour la flexibilité. Permet de créer une relation même si l'un des nœuds référencés n'est pas *encore* dans la table `nodes` ou si on veut lier des `events` sans forcément créer un `node` dédié. Simplifie les insertions.
    *   **Requêtes via CTE SQL :** Moyen standard et intégré à PostgreSQL pour parcourir le graphe pour des relations simples (cible ≤ 3 sauts).
*   **Ce que ça apporte (Flexibilité & Intégration) :**
    *   **Modélisation sémantique :** Permet de répondre à des questions plus complexes sur les liens entre les souvenirs.
    *   **Flexibilité d'ingestion :** Moins de contraintes rigides lors de l'écriture des relations.
    *   **Pas de base de données graphe dédiée :** Simplifie la stack locale.
*   **Trade-offs / Points d'attention :** La **cohérence référentielle est gérée par l'application** ; les performances des CTE récursives sont bonnes pour des faibles profondeurs mais limitées par rapport à une base graphe dédiée pour des traversées complexes (compromis assumé).

### 6. Stratégie d'Indexation Globale

*   **Pourquoi ?** Optimiser les types de requêtes les plus fréquents :
    *   Partitionnement + B-tree `timestamp` => Requêtes temporelles.
    *   GIN `metadata` => Recherches flexibles sur les attributs JSONB.
    *   HNSW `embedding` (par partition) => Recherche de similarité sémantique.
    *   B-tree sur `nodes`/`edges` IDs/types => Recherche et parcours simples du graphe.
*   **Ce que ça apporte :** Bonnes performances générales pour les cas d'usage visés (recherche contextuelle, exploration temporelle, requêtes causales simples).
*   **Points d'attention :** Les index consomment de l'espace disque et ralentissent (un peu) les écritures ; nécessitent une maintenance (VACUUM, REINDEX).

### Conclusion de la Rationale

Ce schéma est un **concentré de pragmatisme** pour un déploiement local : il maximise la flexibilité et la puissance de recherche en exploitant les fonctionnalités natives de PostgreSQL 17 et ses extensions clés, tout en gardant une structure simple à comprendre, à déployer et à maintenir. Les compromis (absence de FK sur `edges`, performance limitée des CTE pour graphes complexes) sont conscients et jugés acceptables au vu de l'objectif de simplicité et des cas d'usage principaux ciblés.

---

**Version :** v1.3.0
**Date :** 2025-10-13
**Auteur :** Giak