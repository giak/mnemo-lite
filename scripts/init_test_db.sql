-- scripts/init_test_db.sql
-- Combined script to initialize the test database (mnemolite_test)

BEGIN; -- Start transaction

-- 0a. Clean up previous partman config for the table if it exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM partman.part_config WHERE parent_table = 'public.events') THEN
        RAISE NOTICE 'Deleting existing pg_partman config for public.events...';
        DELETE FROM partman.part_config WHERE parent_table = 'public.events';
        RAISE NOTICE 'Deleted existing pg_partman config for public.events.';
    ELSE
        RAISE NOTICE 'No existing pg_partman config found for public.events.';
    END IF;
END;
$$;

-- 0b. Force drop existing events table to ensure schema update
DROP TABLE IF EXISTS public.events CASCADE;

-- 1. Extensions (from 01-extensions.sql and 01-init.sql)
CREATE EXTENSION IF NOT EXISTS pgcrypto; -- Pour gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS partman;
CREATE EXTENSION IF NOT EXISTS pg_partman SCHEMA partman;

-- Grant privileges on the partman schema to the test user (assuming same user as main db)
-- NOTE: This assumes the user already exists. The user is created by docker-entrypoint.
DO $$
DECLARE
    test_db_user TEXT := current_user; -- Get the user connected to mnemolite_test
BEGIN
    EXECUTE format('GRANT USAGE ON SCHEMA partman TO %I;', test_db_user);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON partman.part_config TO %I;', test_db_user);
    RAISE NOTICE 'Granted partman privileges to user %', test_db_user;
END;
$$;

-- 2. Main Table (from 01-init.sql)
CREATE TABLE IF NOT EXISTS public.events (
    id          UUID NOT NULL DEFAULT gen_random_uuid(),
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),         
    content     JSONB NOT NULL,
    embedding   VECTOR(768),
    metadata    JSONB DEFAULT '{}'::jsonb,
    PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

-- Ensure the embedding column has the correct dimension, even if table already existed
ALTER TABLE public.events ALTER COLUMN embedding TYPE vector(768);

-- Create indexes on the parent table (will be inherited)
CREATE INDEX IF NOT EXISTS events_metadata_gin_idx ON public.events USING GIN (metadata jsonb_path_ops);
CREATE INDEX IF NOT EXISTS events_timestamp_idx ON public.events (timestamp);

-- 3. Partman Configuration (from 02-partman-config.sql)
-- Wrap in DO block to handle potential errors if already configured
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM partman.part_config WHERE parent_table = 'public.events') THEN
        RAISE NOTICE 'Configuring pg_partman for public.events...';
        PERFORM partman.create_parent(
            p_parent_table := 'public.events',
            p_control := 'timestamp',
            p_type := 'range',
            p_interval := '1 month',
            p_premake := 4,
            p_start_partition := (now() - interval '1 month')::text
        );
        RAISE NOTICE 'pg_partman configured for public.events.';
    ELSE
        RAISE NOTICE 'pg_partman already configured for public.events.';
    END IF;
EXCEPTION 
    WHEN OTHERS THEN
        RAISE WARNING 'Error during pg_partman configuration (อาจจะถูกกำหนดค่าไว้แล้ว): %', SQLERRM;
END;
$$;

-- Note: Vector indexes on partitions are NOT created here.
-- They should be created MANUALLY in tests if needed for specific performance tests,
-- or the test data generation logic should handle it.
-- For functional tests, they are usually not strictly required.

-- Index IVFFLAT pour la recherche vectorielle (exemple, adapter selon besoin)
-- Le nombre de listes est une suggestion, à ajuster selon la taille des données
CREATE INDEX IF NOT EXISTS idx_events_embedding_ivfflat 
ON public.events 
USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);

-- Note: Pour des performances optimales, envisagez HNSW pour les grands datasets:
-- CREATE INDEX idx_events_embedding_hnsw ON events USING hnsw (embedding vector_l2_ops); 

COMMIT; -- Commit transaction

-- Note: Pour des performances optimales, envisagez HNSW pour les grands datasets:
-- CREATE INDEX idx_events_embedding_hnsw ON events USING hnsw (embedding vector_l2_ops); 