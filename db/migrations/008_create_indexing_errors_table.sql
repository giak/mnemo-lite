-- Migration: Create indexing_errors table for batch processing error tracking
-- EPIC: Error tracking for batch indexing failures

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

    -- Indexes for common queries
    CONSTRAINT check_error_type CHECK (
        error_type IN ('parsing_error', 'encoding_error', 'chunking_error', 'embedding_error', 'persistence_error')
    )
);

-- Index for querying errors by repository and timestamp
CREATE INDEX idx_indexing_errors_repo_time ON indexing_errors(repository, occurred_at DESC);

-- Index for filtering by error type
CREATE INDEX idx_indexing_errors_type ON indexing_errors(error_type);

-- Index for finding errors by file path
CREATE INDEX idx_indexing_errors_file ON indexing_errors(file_path);
