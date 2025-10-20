-- Migration v3.0 → v4.0: Add name_path to code_chunks
-- EPIC-11 Story 11.1: Hierarchical Symbol Paths
--
-- Purpose: Add hierarchical qualified names to code chunks for better search disambiguation
-- Examples: "models.user.User.validate" vs flat "validate"
-- Idempotent: Safe to run multiple times (column and indexes only created if not exists)
-- Estimated time: <1 second for empty table, ~2-3 seconds for 1000 chunks

-- Step 1: Add name_path column (if not exists)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'code_chunks' AND column_name = 'name_path'
    ) THEN
        ALTER TABLE code_chunks ADD COLUMN name_path TEXT;
        RAISE NOTICE 'Column name_path added to code_chunks';
    ELSE
        RAISE NOTICE 'Column name_path already exists in code_chunks, skipping';
    END IF;
END $$;

-- Step 2: Create index for exact name_path lookups (if not exists)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'code_chunks' AND indexname = 'idx_code_chunks_name_path'
    ) THEN
        CREATE INDEX idx_code_chunks_name_path ON code_chunks(name_path);
        RAISE NOTICE 'Index idx_code_chunks_name_path created';
    ELSE
        RAISE NOTICE 'Index idx_code_chunks_name_path already exists, skipping';
    END IF;
END $$;

-- Step 3: Create trigram index for fuzzy name_path search (if not exists)
-- Requires pg_trgm extension
DO $$
BEGIN
    -- Ensure pg_trgm extension is enabled
    CREATE EXTENSION IF NOT EXISTS pg_trgm;

    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'code_chunks' AND indexname = 'idx_code_chunks_name_path_trgm'
    ) THEN
        CREATE INDEX idx_code_chunks_name_path_trgm ON code_chunks USING gin(name_path gin_trgm_ops);
        RAISE NOTICE 'Trigram index idx_code_chunks_name_path_trgm created';
    ELSE
        RAISE NOTICE 'Trigram index idx_code_chunks_name_path_trgm already exists, skipping';
    END IF;
END $$;

-- Step 4: Validate migration success
DO $$
DECLARE
    has_column BOOLEAN;
    has_btree_index BOOLEAN;
    has_trgm_index BOOLEAN;
BEGIN
    -- Check column exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'code_chunks' AND column_name = 'name_path'
    ) INTO has_column;

    -- Check B-tree index exists
    SELECT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'code_chunks' AND indexname = 'idx_code_chunks_name_path'
    ) INTO has_btree_index;

    -- Check trigram index exists
    SELECT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'code_chunks' AND indexname = 'idx_code_chunks_name_path_trgm'
    ) INTO has_trgm_index;

    -- Validate all components
    IF NOT has_column THEN
        RAISE EXCEPTION 'Migration validation failed: name_path column not found';
    END IF;

    IF NOT has_btree_index THEN
        RAISE EXCEPTION 'Migration validation failed: B-tree index not found';
    END IF;

    IF NOT has_trgm_index THEN
        RAISE EXCEPTION 'Migration validation failed: Trigram index not found';
    END IF;

    -- Success message
    RAISE NOTICE '✓ Migration v3.0 → v4.0 successful';
    RAISE NOTICE '  - Column name_path: ADDED';
    RAISE NOTICE '  - B-tree index: CREATED';
    RAISE NOTICE '  - Trigram index: CREATED';
END $$;

-- Step 5: Display schema information
SELECT
    'code_chunks' AS table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'code_chunks' AND column_name = 'name_path';

-- Step 6: Display indexes
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'code_chunks' AND indexname LIKE '%name_path%';

-- Step 7: Display sample data (if any chunks exist)
SELECT
    id,
    name,
    name_path,
    file_path,
    chunk_type
FROM code_chunks
LIMIT 5;
