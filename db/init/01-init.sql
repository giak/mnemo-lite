-- Extensions nécessaires
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_cron;
CREATE EXTENSION IF NOT EXISTS pg_partman;
CREATE EXTENSION IF NOT EXISTS pgmq;
CREATE EXTENSION IF NOT EXISTS pgrouting;

-- Création des schémas
CREATE SCHEMA IF NOT EXISTS partman;
CREATE SCHEMA IF NOT EXISTS cron;

-- Tables principales

-- Table events
CREATE TABLE events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  timestamp TIMESTAMPTZ NOT NULL,
  expiration TIMESTAMPTZ, -- pour TTL automatique
  memory_type TEXT REFERENCES memory_types(code),
  event_type TEXT REFERENCES event_types(code),
  role_id INTEGER REFERENCES roles(id),
  content JSONB NOT NULL,
  embedding VECTOR(1536),
  metadata JSONB DEFAULT '{}'
);
CREATE INDEX ON events(timestamp);
CREATE INDEX ON events USING hnsw(embedding) WITH (ef_construction=128, m=16);

-- Table roles
CREATE TABLE roles (
  id SERIAL PRIMARY KEY,
  role_name TEXT UNIQUE NOT NULL
);

-- Table memory_types
CREATE TABLE memory_types (
  code TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  description TEXT
);

-- Table event_types
CREATE TABLE event_types (
  code TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  description TEXT
);

-- Table relations
CREATE TABLE relations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID REFERENCES events(id),
  target_id UUID REFERENCES events(id),
  relation_type TEXT CHECK (relation_type IN ('causes', 'depends_on', 'relates_to')),
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON relations(source_id);
CREATE INDEX ON relations(target_id);

-- Outbox pour synchronisation avec ChromaDB
CREATE TABLE chroma_outbox (
  id UUID PRIMARY KEY,
  embedding VECTOR(1536),
  op_type TEXT CHECK (op_type IN ('upsert','delete')),
  retry_count INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tables temporelles

-- Table sequences
CREATE TABLE sequences (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table sequence_events
CREATE TABLE sequence_events (
  sequence_id UUID REFERENCES sequences(id),
  event_id UUID REFERENCES events(id),
  position INTEGER NOT NULL,
  PRIMARY KEY (sequence_id, event_id)
);

-- Table events_archive
CREATE TABLE events_archive (
  LIKE events INCLUDING ALL,
  archived_at TIMESTAMPTZ DEFAULT NOW()
);

-- Vue matérialisée
CREATE MATERIALIZED VIEW active_memories AS
SELECT * FROM events WHERE expiration IS NULL OR expiration > NOW();

-- Index complémentaires
CREATE INDEX ON events ((metadata->>'rule_id'));
CREATE INDEX ON events ((metadata->>'session_id'));
CREATE INDEX ON events ((metadata->>'source_file'));

-- Trigger pour alimenter la outbox
CREATE OR REPLACE FUNCTION trg_events_to_outbox() RETURNS TRIGGER AS $$
BEGIN
  IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
    INSERT INTO chroma_outbox(id, embedding, op_type)
    VALUES (NEW.id, NEW.embedding, 'upsert')
    ON CONFLICT (id) DO UPDATE SET embedding = EXCLUDED.embedding, op_type = 'upsert';
  ELSIF TG_OP = 'DELETE' THEN
    INSERT INTO chroma_outbox(id, op_type) VALUES (OLD.id, 'delete');
  END IF;
  PERFORM pg_notify('outbox_new','');
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trig_events_outbox
AFTER INSERT OR UPDATE OR DELETE ON events
FOR EACH ROW EXECUTE PROCEDURE trg_events_to_outbox();

-- Données de base

-- Rôles de base
INSERT INTO roles (role_name) VALUES 
  ('system'),
  ('user'),
  ('assistant') 
ON CONFLICT (role_name) DO NOTHING;

-- Types de mémoire
INSERT INTO memory_types (code, label, description) VALUES
  ('episodic', 'Épisodique', 'Mémoire liée à un événement précis dans le temps'),
  ('semantic', 'Sémantique', 'Mémoire des concepts, connaissances générales'),
  ('procedural', 'Procédurale', 'Mémoire des séquences d''actions'),
  ('working', 'De travail', 'Mémoire temporaire à court terme'),
  ('prospective', 'Prospective', 'Mémoire des intentions futures')
ON CONFLICT (code) DO NOTHING;

-- Types d'événements
INSERT INTO event_types (code, label, description) VALUES
  ('prompt', 'Prompt', 'Entrée utilisateur'),
  ('response', 'Réponse', 'Réponse du système'),
  ('decision', 'Décision', 'Choix ou décision prise'),
  ('feedback', 'Feedback', 'Retour correctif ou évaluatif'),
  ('tool_use', 'Utilisation d''outil', 'Appel d''un outil externe')
ON CONFLICT (code) DO NOTHING;

-- Configuration pg_partman
SELECT partman.create_parent('public.events', 'timestamp', 'native', 'monthly');
UPDATE partman.part_config SET retention = '12 months', retention_schema = NULL WHERE parent_table = 'public.events';
-- Fin du script d'initialisation principal
-- Suppression de la section conflictuelle ci-dessous

-- MnemoLite Database Initialization Script
-- This script creates the necessary tables and triggers for the MnemoLite system

-- Enable pgmq extension
CREATE EXTENSION IF NOT EXISTS pgmq;

-- Add uuidv7 extension for time-ordered UUIDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Event Types Enum
CREATE TYPE event_type AS ENUM (
    'message',
    'document',
    'image',
    'action',
    'system'
);

-- Memory Types Enum
CREATE TYPE memory_type AS ENUM (
    'conversation',
    'fact',
    'document',
    'experience'
);

-- Create Roles Table
CREATE TABLE IF NOT EXISTS roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create Events Table
CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type event_type NOT NULL,
    memory_type memory_type NOT NULL,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    metadata JSONB,
    embedding JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index on role_id
CREATE INDEX IF NOT EXISTS idx_events_role_id ON events(role_id);

-- Create index on event_type
CREATE INDEX IF NOT EXISTS idx_events_event_type ON events(event_type);

-- Create index on memory_type
CREATE INDEX IF NOT EXISTS idx_events_memory_type ON events(memory_type);

-- Create index on created_at (for time-based queries)
CREATE INDEX IF NOT EXISTS idx_events_created_at ON events(created_at);

-- Create Outbox Table for ChromaDB Sync
CREATE TABLE IF NOT EXISTS chroma_outbox (
    id UUID PRIMARY KEY,
    content TEXT NOT NULL,
    op_type VARCHAR(10) NOT NULL,
    metadata JSONB,
    embedding JSONB,
    retry_count INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index on created_at for outbox
CREATE INDEX IF NOT EXISTS idx_chroma_outbox_created_at ON chroma_outbox(created_at);

-- Create a function to add events to the outbox
CREATE OR REPLACE FUNCTION add_event_to_outbox()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
        INSERT INTO chroma_outbox (id, content, op_type, metadata, embedding)
        VALUES (
            NEW.id,
            NEW.content,
            'upsert',
            jsonb_build_object(
                'event_type', NEW.event_type,
                'memory_type', NEW.memory_type,
                'role_id', NEW.role_id,
                'metadata', NEW.metadata
            ),
            NEW.embedding
        )
        ON CONFLICT (id) DO UPDATE SET
            content = EXCLUDED.content,
            op_type = EXCLUDED.op_type,
            metadata = EXCLUDED.metadata,
            embedding = EXCLUDED.embedding,
            retry_count = 0;
        
        -- Notify the worker
        PERFORM pg_notify('outbox_new', NEW.id::text);
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO chroma_outbox (id, content, op_type)
        VALUES (OLD.id, '', 'delete')
        ON CONFLICT (id) DO UPDATE SET
            op_type = EXCLUDED.op_type,
            retry_count = 0;
        
        -- Notify the worker
        PERFORM pg_notify('outbox_new', OLD.id::text);
    END IF;
    
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Create a trigger for outbox
CREATE TRIGGER events_outbox_trigger
AFTER INSERT OR UPDATE OR DELETE ON events
FOR EACH ROW EXECUTE FUNCTION add_event_to_outbox();

-- Create a function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for updated_at
CREATE TRIGGER update_events_updated_at
BEFORE UPDATE ON events
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_roles_updated_at
BEFORE UPDATE ON roles
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create message queue
SELECT pgmq.create('memory_tasks');

-- Create a default role
INSERT INTO roles (name, description)
VALUES ('default', 'Default system role')
ON CONFLICT DO NOTHING;

-- Create a system user for indexing
INSERT INTO roles (name, description)
VALUES ('system', 'System role for automated actions')
ON CONFLICT DO NOTHING; 
