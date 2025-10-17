-- MnemoLite Database Index Optimizations
-- For local usage performance improvements
-- Run with: psql -U mnemo -d mnemolite -f optimize_indexes.sql

-- ============================================================================
-- EVENTS TABLE INDEXES
-- ============================================================================

-- Index for metadata source (very frequently used in queries)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_events_metadata_source
ON events((metadata->>'source'))
WHERE metadata IS NOT NULL;

-- Index for metadata tags (if used)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_events_metadata_tags
ON events USING GIN ((metadata->'tags'))
WHERE metadata IS NOT NULL AND metadata ? 'tags';

-- Index for timestamp range queries (already exists but recreate if needed)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_events_timestamp_desc
ON events(timestamp DESC);

-- Partial index for events with embeddings (for vector searches)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_events_with_embedding
ON events(id, timestamp)
WHERE embedding IS NOT NULL;

-- Composite index for metadata + timestamp queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_events_metadata_timestamp
ON events(timestamp DESC)
WHERE metadata IS NOT NULL;

-- ============================================================================
-- CODE_CHUNKS TABLE INDEXES
-- ============================================================================

-- Index for repository queries (very common)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_code_chunks_repository
ON code_chunks(repository)
WHERE repository IS NOT NULL;

-- Index for file_path queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_code_chunks_file_path
ON code_chunks(file_path);

-- Index for language filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_code_chunks_language
ON code_chunks(language)
WHERE language IS NOT NULL;

-- Index for chunk_type filtering (function, class, method)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_code_chunks_chunk_type
ON code_chunks(chunk_type);

-- Composite index for repository + file_path (common query pattern)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_code_chunks_repo_file
ON code_chunks(repository, file_path)
WHERE repository IS NOT NULL;

-- Index for chunks with embeddings
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_code_chunks_with_embeddings
ON code_chunks(id)
WHERE embedding_text IS NOT NULL OR embedding_code IS NOT NULL;

-- Index for metadata complexity queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_code_chunks_complexity
ON code_chunks(((metadata->>'complexity')::jsonb->>'cyclomatic')::int)
WHERE metadata->>'complexity' IS NOT NULL;

-- ============================================================================
-- NODES TABLE INDEXES
-- ============================================================================

-- Index for node_type queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_nodes_node_type
ON nodes(node_type);

-- Index for properties chunk_id (for joins with code_chunks)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_nodes_chunk_id
ON nodes((properties->>'chunk_id'))
WHERE properties ? 'chunk_id';

-- Index for label searches
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_nodes_label
ON nodes(label);

-- ============================================================================
-- EDGES TABLE INDEXES
-- ============================================================================

-- Index for source_node_id (for graph traversal)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_edges_source_node
ON edges(source_node_id);

-- Index for target_node_id (for reverse traversal)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_edges_target_node
ON edges(target_node_id);

-- Index for relation_type filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_edges_relation_type
ON edges(relation_type);

-- Composite index for source + relation (common pattern)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_edges_source_relation
ON edges(source_node_id, relation_type);

-- ============================================================================
-- ANALYZE TABLES FOR QUERY PLANNER
-- ============================================================================

-- Update statistics for better query plans
ANALYZE events;
ANALYZE code_chunks;
ANALYZE nodes;
ANALYZE edges;

-- ============================================================================
-- OPTIONAL: VACUUM FOR SPACE RECLAMATION
-- ============================================================================

-- Only run if you've deleted a lot of data
-- VACUUM ANALYZE events;
-- VACUUM ANALYZE code_chunks;
-- VACUUM ANALYZE nodes;
-- VACUUM ANALYZE edges;

-- ============================================================================
-- VIEW TO CHECK INDEX USAGE
-- ============================================================================

CREATE OR REPLACE VIEW index_usage AS
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;

-- ============================================================================
-- VIEW TO CHECK SLOW QUERIES
-- ============================================================================

CREATE OR REPLACE VIEW slow_queries AS
SELECT
    query,
    calls,
    total_time,
    mean_time,
    stddev_time,
    rows
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat%'
ORDER BY mean_time DESC
LIMIT 20;

-- Note: pg_stat_statements extension must be enabled for slow_queries view
-- If not enabled, run: CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- ============================================================================
-- REPORT
-- ============================================================================

-- Show existing indexes
SELECT
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) as size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;

-- Show table sizes
SELECT
    tablename,
    pg_size_pretty(pg_total_relation_size(tablename::regclass)) as total_size,
    pg_size_pretty(pg_relation_size(tablename::regclass)) as table_size,
    pg_size_pretty(pg_total_relation_size(tablename::regclass) - pg_relation_size(tablename::regclass)) as indexes_size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(tablename::regclass) DESC;