-- Migration v2.0 → v3.0: Add content_hash to code_chunks.metadata
-- EPIC-10 Story 10.6: Migration Script for content_hash
--
-- Purpose: Add MD5 content hash to existing code chunks for cache validation
-- Idempotent: Safe to run multiple times (only updates chunks without hash)
-- Estimated time: ~1-2 seconds for 1000 chunks

-- Step 1: Add content_hash to all existing chunks
-- The content_hash is computed as MD5 of source_code and stored in metadata JSONB
UPDATE code_chunks
SET metadata = jsonb_set(
    COALESCE(metadata, '{}'::jsonb),
    '{content_hash}',
    to_jsonb(md5(source_code))
)
WHERE metadata->>'content_hash' IS NULL;

-- Step 2: Validate migration success
-- Raises exception if any chunks are missing content_hash
DO $$
DECLARE
    total_chunks INT;
    chunks_with_hash INT;
    missing_count INT;
BEGIN
    -- Count total chunks
    SELECT COUNT(*) INTO total_chunks FROM code_chunks;

    -- Count chunks with content_hash
    SELECT COUNT(*) INTO chunks_with_hash
    FROM code_chunks
    WHERE metadata->>'content_hash' IS NOT NULL;

    -- Calculate missing
    missing_count := total_chunks - chunks_with_hash;

    -- Raise exception if incomplete
    IF missing_count > 0 THEN
        RAISE EXCEPTION 'Migration failed: % of % chunks missing content_hash',
            missing_count, total_chunks;
    END IF;

    -- Success message
    RAISE NOTICE 'Migration successful: % of % chunks have content_hash (100%%)',
        chunks_with_hash, total_chunks;
END $$;

-- Step 3: Display sample of migrated data
SELECT
    id,
    file_path,
    LEFT(source_code, 50) as source_preview,
    metadata->>'content_hash' as content_hash,
    LENGTH(metadata->>'content_hash') as hash_length
FROM code_chunks
LIMIT 5;
