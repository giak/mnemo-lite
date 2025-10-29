-- EPIC-22 Story 22.1: Metrics table for observability
-- Migration v5 → v6: Add metrics table
-- Author: Claude Code
-- Date: 2025-10-24

-- Create metrics table
CREATE TABLE IF NOT EXISTS metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metric_type VARCHAR(50) NOT NULL,  -- 'api', 'redis', 'postgres', 'system', 'cache'
    metric_name VARCHAR(100) NOT NULL, -- 'latency_ms', 'hit_rate', 'connections', etc.
    value DOUBLE PRECISION NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Constraints
    CONSTRAINT valid_metric_type CHECK (metric_type IN ('api', 'redis', 'postgres', 'system', 'cache'))
);

-- Indexes for fast queries
CREATE INDEX idx_metrics_type_time ON metrics (metric_type, timestamp DESC);
CREATE INDEX idx_metrics_time ON metrics (timestamp DESC);
CREATE INDEX idx_metrics_name ON metrics (metric_name);

-- Composite index for aggregation queries
CREATE INDEX idx_metrics_type_name_time ON metrics (metric_type, metric_name, timestamp DESC);

-- JSONB GIN index for metadata queries (optional, if needed later)
-- CREATE INDEX idx_metrics_metadata ON metrics USING gin (metadata jsonb_path_ops);

-- Comments
COMMENT ON TABLE metrics IS 'EPIC-22: Time-series metrics for observability (API latency, cache stats, DB performance)';
COMMENT ON COLUMN metrics.metric_type IS 'Category: api, redis, postgres, system, cache';
COMMENT ON COLUMN metrics.metric_name IS 'Specific metric: latency_ms, hit_rate, connections, cpu_percent, etc.';
COMMENT ON COLUMN metrics.value IS 'Numeric value (float)';
COMMENT ON COLUMN metrics.metadata IS 'Additional context (endpoint, method, status_code, etc.)';

-- Example data for testing (commented out)
-- INSERT INTO metrics (metric_type, metric_name, value, metadata) VALUES
-- ('api', 'latency_ms', 45.3, '{"endpoint": "/v1/code/search/hybrid", "method": "GET", "status_code": 200}'::jsonb),
-- ('redis', 'hit_rate', 0.873, '{"cache_type": "search_results"}'::jsonb),
-- ('postgres', 'active_connections', 8, '{}'::jsonb);

-- Retention policy (optional): Keep 30 days
-- Run daily via cron:
-- DELETE FROM metrics WHERE timestamp < NOW() - INTERVAL '30 days';

-- Verify migration
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE tablename = 'metrics';

-- Show indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'metrics'
ORDER BY indexname;
