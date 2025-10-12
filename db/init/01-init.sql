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
-- Create Test Database (if it doesn't exist)
------------------------------------------------------------------
SELECT 'CREATE DATABASE mnemolite_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'mnemolite_test')\gexec

-- Optional: Grant privileges if needed, though usually the user owns it
-- GRANT ALL PRIVILEGES ON DATABASE mnemolite_test TO "${POSTGRES_USER}";

-- Reconnect or ensure subsequent scripts handle the test DB context if needed
-- \connect mnemolite_test -- This might be needed if schemas are applied to test DB

------------------------------------------------------------------
-- Apply Schema to MAIN Database (mnemolite)
------------------------------------------------------------------
-- (Connects implicitly to POSTGRES_DB initially)

CREATE TABLE IF NOT EXISTS events (
    id          UUID NOT NULL DEFAULT gen_random_uuid(),
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),         
    content     JSONB NOT NULL,             -- Contenu flexible: { "type": "prompt", ... } ou { "type": "decision", ... }
    embedding   VECTOR(768),                -- Embedding (nomic-embed-text-v1.5)
    metadata    JSONB DEFAULT '{}'::jsonb,  -- Tags, source, IDs, types, etc.
    -- Clé primaire composite, incluant la clé de partitionnement
    -- Commented out partitioning for test setup simplicity
    PRIMARY KEY (id)
);
-- PARTITION BY RANGE (timestamp);

COMMENT ON TABLE events IS 'Table principale stockant tous les evenements atomiques (NON partitionnee pour test setup).';
COMMENT ON COLUMN events.content IS 'Contenu detaille de l evenement au format JSONB.';
COMMENT ON COLUMN events.embedding IS 'Vecteur semantique du contenu (dimension 768 pour nomic-embed-text-v1.5).';
COMMENT ON COLUMN events.metadata IS 'Metadonnees additionnelles (tags, IDs, types) au format JSONB.';

CREATE INDEX IF NOT EXISTS events_timestamp_idx ON events (timestamp);
CREATE INDEX IF NOT EXISTS events_metadata_gin_idx ON events USING GIN (metadata jsonb_path_ops);

CREATE TABLE IF NOT EXISTS nodes (
    node_id         UUID PRIMARY KEY, -- Generalement un event.id, mais peut etre autre chose (concept genere)
    node_type       TEXT NOT NULL,    -- Ex: 'event', 'concept', 'entity', 'rule', 'document'
    label           TEXT,             -- Nom lisible pour affichage/requete
    properties      JSONB DEFAULT '{}'::jsonb, -- Attributs additionnels du nœud
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
COMMENT ON TABLE nodes IS 'Noeuds du graphe conceptuel (evenements, concepts, entites).';
CREATE INDEX IF NOT EXISTS nodes_type_idx ON nodes(node_type);

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

------------------------------------------------------------------
-- Apply Schema to TEST Database (mnemolite_test)
------------------------------------------------------------------
-- Important: Requires running this script with a tool that handles \connect (like psql)
-- or splitting into separate scripts executed against respective DBs.
-- For simplicity here, we duplicate the DDL assuming manual application or adjustment.
-- If docker-entrypoint runs scripts sequentially, it might apply to the default DB only.
-- A more robust approach involves separate scripts or conditional logic.

\connect mnemolite_test;

-- Re-create tables in the test database
CREATE TABLE IF NOT EXISTS events (
    id          UUID PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    content     JSONB NOT NULL,
    embedding   VECTOR(768),
    metadata    JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS events_timestamp_idx ON events (timestamp);
CREATE INDEX IF NOT EXISTS events_metadata_gin_idx ON events USING GIN (metadata jsonb_path_ops);

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

-- Optionally connect back
-- \connect mnemolite;

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
