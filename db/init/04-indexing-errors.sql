-- Load indexing_errors table migration
-- This script loads the migration for batch indexing error tracking

-- Note: Migrations are mounted at /docker-entrypoint-initdb.d/migrations in the container
-- (see docker-compose.yml volume mappings)

-- However, during initialization, the db/init folder is mounted at /docker-entrypoint-initdb.d
-- and migrations folder is separately accessible. We need to reference the migration file.

-- For now, inline the migration since the migrations folder may not be mounted
-- during docker-entrypoint-initdb.d execution.

-- Migration: Create indexing_errors table for batch processing error tracking
CREATE TABLE IF NOT EXISTS indexing_errors (
    error_id BIGSERIAL PRIMARY KEY,
    repository VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    error_type VARCHAR(100) NOT NULL,
    error_message TEXT NOT NULL,
    error_traceback TEXT,
    chunk_type VARCHAR(50),
    language VARCHAR(50),
    occurred_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT check_error_type CHECK (
        error_type IN ('parsing_error', 'encoding_error', 'chunking_error', 'embedding_error', 'persistence_error')
    )
);

-- Index for querying errors by repository and timestamp
CREATE INDEX IF NOT EXISTS idx_indexing_errors_repo_time ON indexing_errors(repository, occurred_at DESC);

-- Index for filtering by error type
CREATE INDEX IF NOT EXISTS idx_indexing_errors_type ON indexing_errors(error_type);

-- Index for finding errors by file path
CREATE INDEX IF NOT EXISTS idx_indexing_errors_file ON indexing_errors(file_path);

-- Also create table in test database
\connect mnemolite_test;

CREATE TABLE IF NOT EXISTS indexing_errors (
    error_id BIGSERIAL PRIMARY KEY,
    repository VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    error_type VARCHAR(100) NOT NULL,
    error_message TEXT NOT NULL,
    error_traceback TEXT,
    chunk_type VARCHAR(50),
    language VARCHAR(50),
    occurred_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT check_error_type CHECK (
        error_type IN ('parsing_error', 'encoding_error', 'chunking_error', 'embedding_error', 'persistence_error')
    )
);

CREATE INDEX IF NOT EXISTS idx_indexing_errors_repo_time ON indexing_errors(repository, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_indexing_errors_type ON indexing_errors(error_type);
CREATE INDEX IF NOT EXISTS idx_indexing_errors_file ON indexing_errors(file_path);
