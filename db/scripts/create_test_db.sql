-- MnemoLite - Script d'initialisation de la base de données de test
-- Créée: 27 avril 2025
-- Description: Ce script crée et initialise la base de données de test

-- Supprimer la base de test si elle existe déjà
DROP DATABASE IF EXISTS mnemolite_test;

-- Créer la base de test
CREATE DATABASE mnemolite_test WITH OWNER = mnemo;

-- Basculer vers la base de test
\c mnemolite_test

-- Extensions requises
CREATE EXTENSION IF NOT EXISTS pgcrypto; -- Pour gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS vector;   -- Pour le type VECTOR

-- Table principale: events (sans partitionnement pour simplifier les tests)
CREATE TABLE IF NOT EXISTS events (
    id          UUID NOT NULL DEFAULT gen_random_uuid(),
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),         
    content     JSONB NOT NULL,
    embedding   VECTOR(768),
    metadata    JSONB DEFAULT '{}'::jsonb,
    PRIMARY KEY (id)
);

COMMENT ON TABLE events IS 'Table principale stockant tous les événements atomiques (sans partitionnement pour les tests).';
COMMENT ON COLUMN events.content IS 'Contenu détaillé de l''événement au format JSONB.';
COMMENT ON COLUMN events.embedding IS 'Vecteur sémantique du contenu (dimension 768 pour nomic-embed-text-v1.5).';
COMMENT ON COLUMN events.metadata IS 'Métadonnées additionnelles (tags, IDs, types) au format JSONB.';

-- Index GIN sur metadata
CREATE INDEX IF NOT EXISTS events_metadata_gin_idx ON events USING GIN (metadata jsonb_path_ops);

-- Index B-tree sur timestamp 
CREATE INDEX IF NOT EXISTS events_timestamp_idx ON events (timestamp);

-- Index HNSW pour recherche vectorielle (pour tests plus complets)
CREATE INDEX IF NOT EXISTS events_embedding_hnsw_idx 
ON events USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- Tables Graphe Conceptuel/Événementiel (si nécessaire pour les tests)
CREATE TABLE IF NOT EXISTS nodes (
    node_id         UUID PRIMARY KEY,
    node_type       TEXT NOT NULL,
    label           TEXT,
    properties      JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS nodes_type_idx ON nodes(node_type);

CREATE TABLE IF NOT EXISTS edges (
    edge_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_node_id  UUID NOT NULL,
    target_node_id  UUID NOT NULL,
    relation_type   TEXT NOT NULL,
    properties      JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS edges_source_idx ON edges(source_node_id);
CREATE INDEX IF NOT EXISTS edges_target_idx ON edges(target_node_id);
CREATE INDEX IF NOT EXISTS edges_relation_type_idx ON edges(relation_type);

-- Ajouter les utilisateurs nécessaires pour le test
GRANT ALL PRIVILEGES ON DATABASE mnemolite_test TO mnemo;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO mnemo;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO mnemo;

-- Confirmer la création
SELECT 'Base de données de test créée avec succès!' as resultat; 