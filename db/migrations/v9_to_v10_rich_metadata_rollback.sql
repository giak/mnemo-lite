-- Rollback: v10 to v9 - Remove Rich Metadata Tables
-- Date: 2025-11-02
-- Description: Rollback migration v9_to_v10_rich_metadata.sql

BEGIN;

-- Drop indexes on edges table
DROP INDEX IF EXISTS idx_edges_external;
DROP INDEX IF EXISTS idx_edges_weight;

-- Remove columns from edges table
ALTER TABLE edges
    DROP COLUMN IF EXISTS is_external,
    DROP COLUMN IF EXISTS weight;

-- Drop tables (in reverse dependency order)
DROP TABLE IF EXISTS edge_weights CASCADE;
DROP TABLE IF EXISTS computed_metrics CASCADE;
DROP TABLE IF EXISTS detailed_metadata CASCADE;

COMMIT;
