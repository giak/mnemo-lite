-- EPIC-22 Story 22.7: Alerts table for smart alerting
-- Migration v6 → v7: Add alerts table
-- Author: Claude Code
-- Date: 2025-10-24

-- Create alerts table
CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    alert_type VARCHAR(50) NOT NULL,  -- 'cache_hit_rate_low', 'memory_high', 'slow_queries', 'error_rate_high', 'evictions_high'
    severity VARCHAR(20) NOT NULL,    -- 'info', 'warning', 'critical'
    message TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL,  -- Current value that triggered alert
    threshold DOUBLE PRECISION NOT NULL, -- Threshold that was crossed
    metadata JSONB DEFAULT '{}'::jsonb,  -- Additional context (endpoint, query, etc.)
    acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by VARCHAR(100),  -- User/system that acknowledged (optional for MVP)

    -- Constraints
    CONSTRAINT valid_severity CHECK (severity IN ('info', 'warning', 'critical')),
    CONSTRAINT valid_alert_type CHECK (alert_type IN (
        'cache_hit_rate_low',
        'memory_high',
        'slow_queries',
        'error_rate_high',
        'evictions_high',
        'cpu_high',
        'disk_high',
        'connections_high'
    ))
);

-- Indexes for fast queries
CREATE INDEX idx_alerts_severity_ack ON alerts (severity, acknowledged, created_at DESC);
CREATE INDEX idx_alerts_time ON alerts (created_at DESC);
CREATE INDEX idx_alerts_type ON alerts (alert_type);
CREATE INDEX idx_alerts_unacknowledged ON alerts (acknowledged) WHERE acknowledged = FALSE;

-- JSONB GIN index for metadata queries
CREATE INDEX idx_alerts_metadata ON alerts USING gin (metadata jsonb_path_ops);

-- Comments
COMMENT ON TABLE alerts IS 'EPIC-22 Story 22.7: Smart alerting for automatic threshold-based notifications';
COMMENT ON COLUMN alerts.alert_type IS 'Type of alert (cache_hit_rate_low, memory_high, slow_queries, error_rate_high, evictions_high, cpu_high, disk_high, connections_high)';
COMMENT ON COLUMN alerts.severity IS 'Severity level: info, warning, critical';
COMMENT ON COLUMN alerts.message IS 'Human-readable alert message';
COMMENT ON COLUMN alerts.value IS 'Current value that triggered the alert';
COMMENT ON COLUMN alerts.threshold IS 'Threshold value that was crossed';
COMMENT ON COLUMN alerts.metadata IS 'Additional context (endpoint, query, time window, etc.)';
COMMENT ON COLUMN alerts.acknowledged IS 'Whether alert has been acknowledged by user';
COMMENT ON COLUMN alerts.acknowledged_at IS 'Timestamp when alert was acknowledged';
COMMENT ON COLUMN alerts.acknowledged_by IS 'User or system that acknowledged the alert';

-- Example data for testing (commented out)
-- INSERT INTO alerts (alert_type, severity, message, value, threshold, metadata) VALUES
-- ('cache_hit_rate_low', 'warning', 'Redis cache hit rate below 70%', 65.3, 70.0, '{"cache_type": "search_results"}'::jsonb),
-- ('memory_high', 'critical', 'System memory usage above 80%', 85.7, 80.0, '{"hostname": "api-server-1"}'::jsonb),
-- ('slow_queries', 'warning', 'Slow queries detected (>1s)', 1.45, 1.0, '{"query_count": 15}'::jsonb);

-- Retention policy: Keep 90 days (alerts are important audit trail)
-- Run daily via cron or background task:
-- DELETE FROM alerts WHERE created_at < NOW() - INTERVAL '90 days' AND acknowledged = TRUE;

-- Verify migration
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE tablename = 'alerts';

-- Show indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'alerts'
ORDER BY indexname;

-- Count current alerts
SELECT
    severity,
    acknowledged,
    COUNT(*) as count
FROM alerts
GROUP BY severity, acknowledged
ORDER BY severity, acknowledged;
