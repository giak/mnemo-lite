-- db/init/01-extensions.sql
-- Enable necessary extensions

-- Enable pgvector (might already be enabled by base image, but IF NOT EXISTS is safe)
CREATE EXTENSION IF NOT EXISTS vector;

-- Create the schema for pg_partman first
CREATE SCHEMA IF NOT EXISTS partman;

-- Enable pg_partman in its own schema for organization
CREATE EXTENSION IF NOT EXISTS pg_partman SCHEMA partman;

-- Grant privileges on the partman schema and config table to the main user
GRANT USAGE ON SCHEMA partman TO mnemo;
GRANT SELECT, INSERT, UPDATE, DELETE ON partman.part_config TO mnemo;

-- Optional: Enable pg_cron if we want to schedule maintenance internally
-- CREATE EXTENSION IF NOT EXISTS pg_cron; 