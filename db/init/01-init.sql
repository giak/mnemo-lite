-- MnemoLite - Initialisation SQL v1.1.0 (Basé sur docs/bdd_schema.md v1.1.0)
-- Ce script crée le schéma de base aligné sur l'architecture 100% PostgreSQL.

------------------------------------------------------------------
-- Extensions Requises
------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS pgcrypto; -- Pour gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS vector; -- Pour VECTOR et index HNSW/IVFFlat
-- pg_partman doit être installé sur le serveur PostgreSQL.
-- Sa création via CREATE EXTENSION est souvent nécessaire si non préchargée.
CREATE EXTENSION IF NOT EXISTS pg_partman;

------------------------------------------------------------------
-- Table Principale: events (partitionnée)
------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    content     JSONB NOT NULL,             -- Contenu flexible: { "type": "prompt", "role": "user", "text": "..." } ou { "type": "decision", ... }
    embedding   VECTOR(1536),               -- Embedding de 'content' ou d'une partie pertinente (Dimension OpenAI text-embedding-3-small)
    metadata    JSONB DEFAULT '{}'::jsonb   -- Tags, source, rule_id, session_id, event_type, memory_type, etc.
)
PARTITION BY RANGE (timestamp);

COMMENT ON TABLE events IS 'Table principale stockant tous les événements atomiques, partitionnée par timestamp.';
COMMENT ON COLUMN events.content IS 'Contenu détaillé de l'événement au format JSONB.';
COMMENT ON COLUMN events.embedding IS 'Vecteur sémantique du contenu (dimension 1536 pour text-embedding-3-small).';
COMMENT ON COLUMN events.metadata IS 'Métadonnées additionnelles (tags, IDs, types) au format JSONB.';

-- Index GIN sur metadata pour recherches flexibles sur la table Mère
-- (sera hérité par les partitions)
CREATE INDEX IF NOT EXISTS events_metadata_gin_idx ON events USING GIN (metadata jsonb_path_ops);

-- Index B-tree sur timestamp (clé de partitionnement)
CREATE INDEX IF NOT EXISTS events_timestamp_idx ON events (timestamp);

-- NOTE IMPORTANTE sur l'index vectoriel (HNSW/IVFFlat):
-- Il DOIT être créé sur chaque partition individuelle, PAS sur la table mère.
-- Ceci est généralement géré via des hooks pg_partman ou des scripts de maintenance.
-- Exemple pour une partition 'events_pYYYY_MM':
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS events_pYYYY_MM_embedding_hnsw_idx 
-- ON events_pYYYY_MM USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

------------------------------------------------------------------
-- Tables Graphe Conceptuel/Événementiel (Optionnel selon usage)
------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS nodes (
    node_id         UUID PRIMARY KEY, -- Généralement un event.id, mais peut être autre chose (concept généré)
    node_type       TEXT NOT NULL,    -- Ex: 'event', 'concept', 'entity', 'rule', 'document'
    label           TEXT,             -- Nom lisible pour affichage/requête
    properties      JSONB DEFAULT '{}'::jsonb, -- Attributs additionnels du nœud
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
COMMENT ON TABLE nodes IS 'Nœuds du graphe conceptuel (événements, concepts, entités).';

CREATE INDEX IF NOT EXISTS nodes_type_idx ON nodes(node_type);
-- Optionnel: Index sur label si recherche fréquente par nom
-- CREATE INDEX IF NOT EXISTS nodes_label_idx ON nodes USING gin (label gin_trgm_ops);

CREATE TABLE IF NOT EXISTS edges (
    edge_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_node_id  UUID NOT NULL, -- Référence logique nodes.node_id
    target_node_id  UUID NOT NULL, -- Référence logique nodes.node_id
    relation_type   TEXT NOT NULL, -- Ex: 'causes', 'mentions', 'related_to', 'follows', 'uses_tool', 'part_of'
    properties      JSONB DEFAULT '{}'::jsonb, -- Poids, timestamp de la relation, etc.
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
COMMENT ON TABLE edges IS 'Relations (arêtes) entre les nœuds du graphe conceptuel.';
COMMENT ON COLUMN edges.source_node_id IS 'ID du nœud source (pas de FK physique).';
COMMENT ON COLUMN edges.target_node_id IS 'ID du nœud cible (pas de FK physique).';

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
