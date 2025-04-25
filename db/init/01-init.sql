-- MnemoLite - Initialisation SQL v1.1.0 (Basé sur docs/bdd_schema.md v1.1.0)
-- Ce script crée le schéma de base aligné sur l'architecture 100% PostgreSQL.

------------------------------------------------------------------
-- Extensions Requises
------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS pgcrypto; -- Pour gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS vector; -- Pour VECTOR et index HNSW/IVFFlat
-- pg_partman doit être installé sur le serveur PostgreSQL.
-- Sa création via CREATE EXTENSION est souvent nécessaire si non préchargée.
-- CREATE EXTENSION IF NOT EXISTS pg_partman; -- Commenté: Sera créé manuellement après init

------------------------------------------------------------------
-- Table Principale: events (NON partitionnée pour l'instant)
------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events (
    -- id          UUID NOT NULL DEFAULT gen_random_uuid(),
    -- timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(), -- Clé primaire simple
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),         
    content     JSONB NOT NULL,
    embedding   VECTOR(1536),
    metadata    JSONB DEFAULT '{}'::jsonb
    -- PRIMARY KEY (id, timestamp) -- Clé composite supprimée
); -- PARTITION BY RANGE (timestamp); -- Partitionnement supprimé temporairement

COMMENT ON TABLE events IS 'Table principale stockant tous les evenements atomiques (temporairement NON partitionnee).';
COMMENT ON COLUMN events.content IS 'Contenu detaille de l evenement au format JSONB.';
COMMENT ON COLUMN events.embedding IS 'Vecteur semantique du contenu (dimension 1536 pour text-embedding-3-small).';
COMMENT ON COLUMN events.metadata IS 'Metadonnees additionnelles (tags, IDs, types) au format JSONB.';

-- Index GIN sur metadata pour recherches flexibles sur la table Mere
-- (sera herite par les partitions)
CREATE INDEX IF NOT EXISTS events_metadata_gin_idx ON events USING GIN (metadata jsonb_path_ops);

-- Index B-tree sur timestamp (cle de partitionnement)
CREATE INDEX IF NOT EXISTS events_timestamp_idx ON events (timestamp);

-- NOTE IMPORTANTE sur l'index vectoriel (HNSW/IVFFlat):
-- Il DOIT etre cree sur chaque partition individuelle, PAS sur la table mere.
-- Ceci est generalement gere via des hooks pg_partman ou des scripts de maintenance.
-- Exemple pour une partition 'events_pYYYY_MM':
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS events_pYYYY_MM_embedding_hnsw_idx 
-- ON events_pYYYY_MM USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

------------------------------------------------------------------
-- Tables Graphe Conceptuel/Evenementiel (Optionnel selon usage)
------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS nodes (
    node_id         UUID PRIMARY KEY, -- Generalement un event.id, mais peut etre autre chose (concept genere)
    node_type       TEXT NOT NULL,    -- Ex: 'event', 'concept', 'entity', 'rule', 'document'
    label           TEXT,             -- Nom lisible pour affichage/requete
    properties      JSONB DEFAULT '{}'::jsonb, -- Attributs additionnels du noeud
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

------------------------------------------------------------------
-- Configuration Post-Initialisation (Manuelle ou via Script Séparé)
------------------------------------------------------------------
-- 1. Configuration pg_partman:
--    - Appeler partman.create_parent('public.events', 'timestamp', 'native', 'monthly', ...)
--    - Configurer la rétention via UPDATE partman.part_config ...
--    - Mettre en place la maintenance (run_maintenance_proc via pg_cron ou BGW)

-- 2. Création de l'index vectoriel sur les partitions existantes et futures (voir note plus haut).

-- 3. Création éventuelle de fonctions/procédures stockées (dans setup.sql par exemple).

-- Fin du script d'initialisation de base. 
