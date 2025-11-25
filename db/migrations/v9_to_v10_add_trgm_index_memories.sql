-- EPIC-24 P0: Hybrid Search for Memories
-- Migration v9 → v10: Add pg_trgm indexes for lexical search on memories
-- Author: Claude Code
-- Date: 2025-11-25

-- ============================================================
-- CONTEXT: Why pg_trgm for memories?
-- ============================================================
-- Current: Vector search only (diluted signal, misses exact matches)
-- Problem: "Bardella" query returns low similarity (0.10) even when present
-- Solution: Hybrid search (BM25-like lexical + vector + RRF fusion)
--
-- pg_trgm provides:
-- - Trigram similarity for fuzzy matching
-- - Fast ILIKE queries with GIN index
-- - Robust to typos and variations
--
-- Combined with vector search via RRF fusion:
-- - Lexical catches exact terms (proper nouns, acronyms)
-- - Vector catches semantic similarity (synonyms, paraphrases)
-- - RRF fusion combines both without score normalization
-- ============================================================

-- ============================================================
-- STEP 1: Ensure pg_trgm extension is enabled
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================
-- STEP 2: Add GIN trigram index on title
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_memories_title_trgm
ON memories USING GIN (title gin_trgm_ops);

COMMENT ON INDEX idx_memories_title_trgm IS
'EPIC-24: Trigram index for lexical search on title (hybrid search)';

-- ============================================================
-- STEP 3: Add GIN trigram index on content
-- ============================================================

-- For content, we use a partial index on first 10000 chars to limit size
-- Full content can be very large (conversations)
CREATE INDEX IF NOT EXISTS idx_memories_content_trgm
ON memories USING GIN (LEFT(content, 10000) gin_trgm_ops);

COMMENT ON INDEX idx_memories_content_trgm IS
'EPIC-24: Trigram index for lexical search on content (first 10K chars, hybrid search)';

-- ============================================================
-- STEP 4: Add GIN trigram index on embedding_source
-- ============================================================

-- embedding_source is typically 200-400 words, ideal for trigram search
CREATE INDEX IF NOT EXISTS idx_memories_embedding_source_trgm
ON memories USING GIN (embedding_source gin_trgm_ops)
WHERE embedding_source IS NOT NULL;

COMMENT ON INDEX idx_memories_embedding_source_trgm IS
'EPIC-24: Trigram index for lexical search on embedding_source (hybrid search)';

-- ============================================================
-- STEP 5: Add combined text search column (optional optimization)
-- ============================================================

-- For even faster search, we could add a generated column combining fields
-- But this increases storage, so we skip for now

-- ============================================================
-- STEP 6: Verify migration
-- ============================================================

-- Show new indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'memories' AND indexname LIKE '%trgm%'
ORDER BY indexname;

-- Test trigram similarity (should work after extension is enabled)
SELECT show_trgm('Bardella');

-- ============================================================
-- ROLLBACK (if needed)
-- ============================================================

-- To rollback this migration:
-- DROP INDEX IF EXISTS idx_memories_title_trgm;
-- DROP INDEX IF EXISTS idx_memories_content_trgm;
-- DROP INDEX IF EXISTS idx_memories_embedding_source_trgm;

-- ============================================================
-- END OF MIGRATION
-- ============================================================
