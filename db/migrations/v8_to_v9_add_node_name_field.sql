-- EPIC-27 Story 27.2: Add 'name' field to node properties for call resolution
-- Migration v8 → v9: Backfill node properties with 'name' and 'node_type' fields
-- Author: Claude Code
-- Date: 2025-11-01
-- Context: Fix TypeScript metadata extraction - enable proper call → node matching

-- ============================================================================
-- STEP 1: Backfill 'name' field from label
-- ============================================================================

DO $$
DECLARE
    nodes_updated INTEGER := 0;
BEGIN
    -- Update all nodes: Add 'name' to properties JSONB
    -- Use label as source (it contains the function/class name)
    UPDATE nodes
    SET properties = properties || jsonb_build_object('name', label)
    WHERE properties->>'name' IS NULL;

    GET DIAGNOSTICS nodes_updated = ROW_COUNT;
    RAISE NOTICE 'Backfilled % nodes with name field', nodes_updated;
END $$;

-- ============================================================================
-- STEP 2: Backfill 'node_type' field (if missing)
-- ============================================================================

-- Note: New nodes created after Story 27.1 will have node_type automatically
-- This backfills older nodes that may be missing it

DO $$
DECLARE
    nodes_updated INTEGER := 0;
BEGIN
    -- For nodes without node_type in properties, infer from label or set to 'function' as default
    -- (Most nodes are functions; specific types can be corrected later if needed)
    UPDATE nodes
    SET properties = properties || jsonb_build_object('node_type', 'function')
    WHERE properties->>'node_type' IS NULL;

    GET DIAGNOSTICS nodes_updated = ROW_COUNT;
    RAISE NOTICE 'Backfilled % nodes with node_type field', nodes_updated;
END $$;

-- ============================================================================
-- STEP 3: Create index on name field for fast lookups
-- ============================================================================

-- This index is CRITICAL for GraphConstructionService performance
-- Queries like: WHERE properties->>'name' = 'functionName'
CREATE INDEX IF NOT EXISTS idx_nodes_name
ON nodes ((properties->>'name'));

-- Also index on repository + name for scoped lookups
CREATE INDEX IF NOT EXISTS idx_nodes_repository_name
ON nodes ((properties->>'repository'), (properties->>'name'));

-- ============================================================================
-- STEP 4: Verify migration success
-- ============================================================================

DO $$
DECLARE
    total_nodes INTEGER;
    nodes_with_name INTEGER;
    nodes_with_node_type INTEGER;
    coverage_percent NUMERIC;
BEGIN
    -- Count nodes
    SELECT COUNT(*) INTO total_nodes FROM nodes;
    SELECT COUNT(*) INTO nodes_with_name FROM nodes WHERE properties->>'name' IS NOT NULL;
    SELECT COUNT(*) INTO nodes_with_node_type FROM nodes WHERE properties->>'node_type' IS NOT NULL;

    -- Calculate coverage
    IF total_nodes > 0 THEN
        coverage_percent := (nodes_with_name::NUMERIC / total_nodes::NUMERIC) * 100;
    ELSE
        coverage_percent := 100;
    END IF;

    RAISE NOTICE '=== MIGRATION VERIFICATION ===';
    RAISE NOTICE 'Total nodes: %', total_nodes;
    RAISE NOTICE 'Nodes with name field: % (%.1f%%)', nodes_with_name, coverage_percent;
    RAISE NOTICE 'Nodes with node_type field: %', nodes_with_node_type;

    -- Ensure all nodes have name field
    IF nodes_with_name < total_nodes THEN
        RAISE WARNING 'Not all nodes have name field! % / % nodes', nodes_with_name, total_nodes;
    ELSE
        RAISE NOTICE '✅ All nodes have name field';
    END IF;
END $$;

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON INDEX idx_nodes_name IS 'EPIC-27: Fast lookups for call resolution (properties->>''name'')';
COMMENT ON INDEX idx_nodes_repository_name IS 'EPIC-27: Scoped lookups for call resolution within repository';

-- ============================================================================
-- Example queries enabled by this migration
-- ============================================================================

-- Before migration (BROKEN):
-- SELECT * FROM nodes WHERE properties->>'name' = 'validateEmail';
-- → Returns 0 rows (field doesn't exist)

-- After migration (WORKS):
-- SELECT * FROM nodes WHERE properties->>'name' = 'validateEmail';
-- → Returns matching nodes

-- Scoped lookup (within repository):
-- SELECT * FROM nodes
-- WHERE properties->>'repository' = 'CVGenerator'
-- AND properties->>'name' = 'validateEmail';

-- ============================================================================
-- Rollback (if needed)
-- ============================================================================

-- To rollback this migration:
--
-- DROP INDEX IF EXISTS idx_nodes_name;
-- DROP INDEX IF EXISTS idx_nodes_repository_name;
--
-- UPDATE nodes
-- SET properties = properties - 'name' - 'node_type'
-- WHERE properties ? 'name' OR properties ? 'node_type';

-- ============================================================================
-- Expected Impact
-- ============================================================================

-- Before: 54 edges (9.3% ratio) for CVGenerator
-- After re-index: 150-200 edges (30% ratio)
--
-- Enables proper call → node matching in GraphConstructionService
