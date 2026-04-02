# MnemoLite – Schéma SQL Raffiné

> 📅 **Dernière mise à jour**: 2025-10-17
> 📝 **Version**: v5.0.0-dev
> ✅ **Statut**: À jour avec le code (PostgreSQL 18, Dual-Purpose: Agent Memory + Code Intelligence)

## Contexte
Ce schéma documente la structure de la base de données MnemoLite v5.0.0-dev, un **système dual-purpose** combinant:
1. **Agent Memory** - Table `events` partitionnée (temps/vecteur) pour mémoire cognitive d'agents IA
2. **Code Intelligence** - Table `code_chunks` avec dual embeddings (TEXT + CODE) pour indexation sémantique de code

Architecture 100% **PostgreSQL 18** optimisée pour un déploiement local, avec tables `nodes`/`edges` pour graphes causaux (Agent Memory) ET graphes de dépendances (Code Intelligence).

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

-- Nécessaire pour la recherche lexicale (trigram similarity) sur le code
CREATE EXTENSION IF NOT EXISTS pg_trgm;

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
-- Table Code Intelligence: code_chunks (dual embeddings)
------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS code_chunks (
    chunk_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository          TEXT NOT NULL,      -- Nom du repository/projet indexé
    file_path           TEXT NOT NULL,      -- Chemin relatif du fichier source
    chunk_type          TEXT NOT NULL CHECK (chunk_type IN ('function', 'class', 'method', 'file')),
    language            TEXT NOT NULL,      -- Langage détecté (python, javascript, etc.)
    code_text           TEXT NOT NULL,      -- Texte du chunk de code
    start_line          INTEGER,            -- Ligne de début dans le fichier
    end_line            INTEGER,            -- Ligne de fin dans le fichier
    metadata            JSONB DEFAULT '{}'::jsonb,  -- Métadonnées structurées (voir ci-dessous)
    embedding_text      VECTOR(768),        -- Embedding TEXT (nomic-embed-text-v1.5)
    embedding_code      VECTOR(768),        -- Embedding CODE (nomic-embed-text-v1.5)
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE code_chunks IS 'Chunks de code indexes avec dual embeddings (TEXT + CODE) pour recherche semantique hybride.';
COMMENT ON COLUMN code_chunks.embedding_text IS 'Embedding semantique pour recherche par description (TEXT mode).';
COMMENT ON COLUMN code_chunks.embedding_code IS 'Embedding semantique pour recherche par similarite de code (CODE mode).';
COMMENT ON COLUMN code_chunks.metadata IS 'Metadonnees structurees: {name, signature, docstring, complexity, imports, calls, class_name, parameters, return_type, decorators}.';

-- Index HNSW pour recherche vectorielle sur embedding TEXT (recherche par description)
CREATE INDEX IF NOT EXISTS code_chunks_embedding_text_hnsw_idx
    ON code_chunks USING hnsw (embedding_text vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Index HNSW pour recherche vectorielle sur embedding CODE (recherche par similarité de code)
CREATE INDEX IF NOT EXISTS code_chunks_embedding_code_hnsw_idx
    ON code_chunks USING hnsw (embedding_code vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Index GIN trigram pour recherche lexicale full-text sur code_text
CREATE INDEX IF NOT EXISTS code_chunks_code_text_trgm_idx
    ON code_chunks USING gin (code_text gin_trgm_ops);

-- Index GIN trigram pour recherche lexicale sur metadata (notamment 'name' et 'signature')
CREATE INDEX IF NOT EXISTS code_chunks_metadata_trgm_idx
    ON code_chunks USING gin (metadata jsonb_path_ops);

-- Index B-tree pour filtrage par repository
CREATE INDEX IF NOT EXISTS code_chunks_repository_idx
    ON code_chunks (repository);

-- Index B-tree pour filtrage par file_path
CREATE INDEX IF NOT EXISTS code_chunks_file_path_idx
    ON code_chunks (file_path);

-- Index B-tree pour filtrage par language
CREATE INDEX IF NOT EXISTS code_chunks_language_idx
    ON code_chunks (language);

-- Index B-tree pour filtrage par chunk_type
CREATE INDEX IF NOT EXISTS code_chunks_chunk_type_idx
    ON code_chunks (chunk_type);

-- Index composite pour requêtes fréquentes (repository + file_path)
CREATE INDEX IF NOT EXISTS code_chunks_repo_file_idx
    ON code_chunks (repository, file_path);

------------------------------------------------------------------
-- Tables Graphe Conceptuel/Événementiel (Dual-Purpose)
------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS nodes (
    node_id         UUID PRIMARY KEY, -- Generalement un event.id (Agent Memory) ou code_chunk.chunk_id (Code Intelligence)
    node_type       TEXT NOT NULL,    -- Ex: 'event', 'concept', 'entity', 'rule', 'document', 'function', 'class', 'module'
    label           TEXT,             -- Nom lisible pour affichage/requete
    properties      JSONB DEFAULT '{}'::jsonb, -- Attributs additionnels du nœud
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
COMMENT ON TABLE nodes IS 'Noeuds du graphe (dual-purpose): graphe causal Agent Memory + graphe de dependances Code Intelligence.';

CREATE INDEX IF NOT EXISTS nodes_type_idx ON nodes(node_type);
-- Optionnel: Index sur label si recherche frequente par nom
-- CREATE INDEX IF NOT EXISTS nodes_label_idx ON nodes USING gin (label gin_trgm_ops);

CREATE TABLE IF NOT EXISTS edges (
    edge_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_node_id  UUID NOT NULL, -- Reference logique nodes.node_id
    target_node_id  UUID NOT NULL, -- Reference logique nodes.node_id
    relation_type   TEXT NOT NULL, -- Ex: 'causes', 'mentions', 'related_to' (Agent) | 'imports', 'calls', 'inherits', 'defines' (Code)
    properties      JSONB DEFAULT '{}'::jsonb, -- Poids, timestamp de la relation, etc.
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
COMMENT ON TABLE edges IS 'Relations (aretes) entre noeuds (dual-purpose): liens causaux Agent Memory + dependances Code Intelligence.';
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

L'objectif global était de créer une base **robuste**, **performante pour les cas d'usage locaux**, **facile à déployer/maintenir** et **évolutive** dans le contexte d'une machine personnelle ou d'un petit serveur, en s'appuyant **uniquement** sur PostgreSQL 18 et ses extensions.

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

### 7. Table `code_chunks` et Dual Embeddings (TEXT + CODE)

*   **Pourquoi ?**
    *   **Code Intelligence locale :** Indexer et rechercher sémantiquement du code sans dépendre d'APIs externes (GitHub Copilot, etc.).
    *   **Dual embeddings :** Deux embeddings distincts pour chaque chunk de code permettent deux types de recherche complémentaires :
        *   **TEXT embedding** : Recherche par description ("find authentication logic") - optimisé pour le langage naturel.
        *   **CODE embedding** : Recherche par similarité de code ("find similar functions") - optimisé pour la structure/syntaxe du code.
    *   **Recherche hybride :** Combinaison de recherche lexicale (pg_trgm) + vectorielle (HNSW) + fusion RRF (Reciprocal Rank Fusion).
    *   **Métadonnées riches :** JSONB stocke complexité cyclomatique, imports, appels de fonctions, paramètres, etc.
*   **Ce que ça apporte (Performance & Flexibilité) :**
    *   **Recherche sémantique performante :** HNSW sur 2 embeddings (768D chacun) avec ~12ms de latence pour K-NN.
    *   **Recherche lexicale rapide :** Index GIN trigram (pg_trgm) pour recherche full-text sur code (~3ms).
    *   **Filtrage efficace :** Index B-tree sur repository, file_path, language, chunk_type pour filtrages rapides.
    *   **Graphe de dépendances :** Tables nodes/edges réutilisées pour modéliser imports/calls/inherits entre chunks de code.
    *   **Pipeline d'indexation complet :** 7 étapes automatisées (détection langage → AST parsing tree-sitter → chunking → metadata → dual embedding → graph → storage).
*   **Trade-offs :**
    *   **Espace disque :** Dual embeddings = 2 × 768 × 4 bytes = ~6KB par chunk (acceptable pour des dizaines de milliers de chunks).
    *   **Temps d'indexation :** ~2-3s par fichier (AST parsing + dual embedding generation) - batch processing recommandé.
    *   **Maintenance :** Index HNSW à reconstruire lors de reindexation massive (REINDEX CONCURRENTLY).

### 8. Architecture Dual-Purpose (Agent Memory + Code Intelligence)

*   **Pourquoi ?**
    *   **Réutilisation maximale :** Les tables `nodes`/`edges` servent à la fois pour :
        *   **Agent Memory** : Graphe causal entre événements (causes, mentions, related_to).
        *   **Code Intelligence** : Graphe de dépendances entre chunks de code (imports, calls, inherits, defines).
    *   **Simplification stack :** Une seule base PostgreSQL 18 pour deux cas d'usage distincts.
    *   **Extensions partagées :** pgvector (HNSW), pg_trgm (trigrams), pg_partman (partitionnement) profitent aux deux.
*   **Ce que ça apporte :**
    *   **Opérations simplifiées :** Une seule base à sauvegarder, monitorer, optimiser.
    *   **Requêtes cross-domain :** Possibilité de lier events (agent) et code_chunks (code) dans le graphe.
    *   **Évolutivité :** Ajout de nouveaux types de nœuds/relations sans modification de schéma.

### Conclusion de la Rationale

Ce schéma est un **concentré de pragmatisme** pour un déploiement local : il maximise la flexibilité et la puissance de recherche en exploitant les fonctionnalités natives de PostgreSQL 18 et ses extensions clés, tout en gardant une structure simple à comprendre, à déployer et à maintenir.

Le système **dual-purpose** (Agent Memory + Code Intelligence) réutilise intelligemment les mêmes tables (`nodes`/`edges`) et extensions (pgvector, pg_trgm, pg_partman) pour deux cas d'usage distincts, maximisant la simplicité opérationnelle tout en offrant des capacités avancées de recherche sémantique et de graphe.

Les compromis (absence de FK sur `edges`, performance limitée des CTE pour graphes complexes, temps d'indexation pour dual embeddings) sont conscients et jugés acceptables au vu de l'objectif de simplicité et des cas d'usage principaux ciblés.

---

**Version :** v5.0.0-dev
**Date :** 2025-10-17
**Auteur :** Giak

**Changements majeurs v5.0.0-dev** :
- Migration PostgreSQL 17 → 18 (EPIC-06)
- Ajout table `code_chunks` avec dual embeddings (TEXT + CODE, 768D chacun)
- Extension pg_trgm pour recherche lexicale sur code
- 9 index sur code_chunks (2 HNSW, 2 GIN, 5 B-tree)
- Tables nodes/edges étendues pour usage dual-purpose (Agent Memory + Code Intelligence)
- Ajout sections rationale 7-8 (code_chunks, dual-purpose architecture)
- Documentation complète métadonnées code (complexity, imports, calls, parameters)