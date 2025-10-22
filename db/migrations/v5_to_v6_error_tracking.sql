-- Migration v5 to v6: Error Tracking System
-- Story: EPIC-12 Story 12.4 - Error Tracking & Alerting
-- Purpose: Add error_logs table for centralized error tracking and alerting
-- Date: 2025-10-22
-- Author: Claude Code

-- ========================================
-- Error Tracking Table
-- ========================================

CREATE TABLE IF NOT EXISTS error_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    severity TEXT NOT NULL CHECK (severity IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')),
    category TEXT NOT NULL,  -- 'database', 'embedding', 'api', 'circuit_breaker', 'cache', 'graph', 'timeout', etc.
    service TEXT NOT NULL,   -- Service name where error occurred
    error_type TEXT NOT NULL, -- Exception class name (e.g., 'ValueError', 'TimeoutError')
    message TEXT NOT NULL,
    stack_trace TEXT,        -- Full stack trace (optional)
    context JSONB,           -- Additional context: request_id, user, metadata, etc.
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Comment the table
COMMENT ON TABLE error_logs IS
'Story 12.4: Centralized error tracking for all application errors.
Stores structured error data with severity, category, service context.
Used for error analytics, alerting, and debugging.
Created: 2025-10-22';

-- ========================================
-- Indexes for Error Querying
-- ========================================

-- Index for time-based queries (most common: errors in last N hours)
CREATE INDEX IF NOT EXISTS idx_error_logs_timestamp ON error_logs(timestamp DESC);

-- Index for severity filtering (critical errors, error counts)
CREATE INDEX IF NOT EXISTS idx_error_logs_severity ON error_logs(severity);

-- Index for category grouping (errors by category)
CREATE INDEX IF NOT EXISTS idx_error_logs_category ON error_logs(category);

-- Index for service filtering (errors by service)
CREATE INDEX IF NOT EXISTS idx_error_logs_service ON error_logs(service);

-- Index for error type grouping
CREATE INDEX IF NOT EXISTS idx_error_logs_error_type ON error_logs(error_type);

-- Composite index for common queries (severity + timestamp)
CREATE INDEX IF NOT EXISTS idx_error_logs_severity_timestamp
ON error_logs(severity, timestamp DESC);

-- GIN index on JSONB context for flexible querying
CREATE INDEX IF NOT EXISTS idx_error_logs_context ON error_logs USING GIN(context);

-- ========================================
-- Views for Error Analytics
-- ========================================

-- Error summary view (last 24 hours)
CREATE OR REPLACE VIEW error_summary_24h AS
SELECT
    category,
    service,
    error_type,
    severity,
    COUNT(*) as total_count,
    MAX(timestamp) as last_occurrence,
    MIN(timestamp) as first_occurrence
FROM error_logs
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY category, service, error_type, severity
ORDER BY total_count DESC;

COMMENT ON VIEW error_summary_24h IS
'Story 12.4: Aggregated error summary for the last 24 hours.
Groups errors by category, service, type, and severity.
Used for error dashboard and trend analysis.';

-- Critical errors view (last hour)
CREATE OR REPLACE VIEW critical_errors_recent AS
SELECT *
FROM error_logs
WHERE severity = 'CRITICAL'
  AND timestamp > NOW() - INTERVAL '1 hour'
ORDER BY timestamp DESC;

COMMENT ON VIEW critical_errors_recent IS
'Story 12.4: Recent critical errors requiring immediate attention.
Shows all CRITICAL severity errors from the last hour.
Used for alert monitoring and incident response.';

-- Error rate by hour (last 24 hours)
CREATE OR REPLACE VIEW error_rate_hourly AS
SELECT
    date_trunc('hour', timestamp) as hour,
    severity,
    COUNT(*) as error_count
FROM error_logs
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY hour, severity
ORDER BY hour DESC, severity;

COMMENT ON VIEW error_rate_hourly IS
'Story 12.4: Hourly error rate trends for the last 24 hours.
Shows error distribution over time by severity.
Used for trend analysis and spike detection.';

-- ========================================
-- Verification Queries
-- ========================================

-- Verify table and indexes created
-- SELECT tablename, indexname FROM pg_indexes WHERE tablename = 'error_logs';

-- Sample error insert
-- INSERT INTO error_logs (severity, category, service, error_type, message, context)
-- VALUES ('ERROR', 'database', 'EventRepository', 'TimeoutError', 'Query timeout after 5s', '{"query": "SELECT * FROM events", "timeout": 5}');

-- Query error summary
-- SELECT * FROM error_summary_24h;

-- Query critical errors
-- SELECT * FROM critical_errors_recent;

-- ========================================
-- Rollback (if needed)
-- ========================================

-- To rollback this migration:
-- DROP VIEW IF EXISTS error_rate_hourly;
-- DROP VIEW IF EXISTS critical_errors_recent;
-- DROP VIEW IF EXISTS error_summary_24h;
-- DROP TABLE IF EXISTS error_logs CASCADE;
