-- EPIC-24: Knowledge Graph of Investigations
-- Migration v8 → v9: Add embedding_source field for focused semantic search
-- Author: Claude Code
-- Date: 2025-11-25

-- ============================================================
-- CONTEXT: Why embedding_source?
-- ============================================================
-- Current problem: embeddings computed on full content (10K+ chars)
-- Result: semantic signal diluted (~5% relevant content vs 95% noise)
-- Solution: separate embedding_source field for focused embedding text
--
-- Usage:
--   - If embedding_source IS NOT NULL → compute embedding on embedding_source
--   - If embedding_source IS NULL → compute embedding on title + content (legacy)
--
-- Typical embedding_source: 200-400 word structured summary
-- ============================================================

-- ============================================================
-- STEP 1: Add embedding_source column
-- ============================================================

ALTER TABLE memories ADD COLUMN IF NOT EXISTS embedding_source TEXT;

COMMENT ON COLUMN memories.embedding_source IS
'Optional focused text for embedding computation. If NULL, embedding is computed on title+content. Typical: 200-400 word structured summary with subject, themes, entities, findings.';

-- ============================================================
-- STEP 2: Add new memory_type 'investigation'
-- ============================================================

-- Drop the old constraint first
ALTER TABLE memories DROP CONSTRAINT IF EXISTS chk_memory_type;

-- Add new constraint with 'investigation' type
ALTER TABLE memories ADD CONSTRAINT chk_memory_type
CHECK (memory_type IN ('note', 'decision', 'task', 'reference', 'conversation', 'investigation'));

COMMENT ON COLUMN memories.memory_type IS
'Classification: note, decision, task, reference, conversation, investigation (EPIC-24)';

-- ============================================================
-- STEP 3: Add metadata columns for investigations
-- ============================================================

-- Note: metadata JSONB field already exists, can store:
-- {
--   "subject": "Jordan Bardella",
--   "themes": ["extrême-droite", "élections européennes 2024"],
--   "entities": ["Marine Le Pen", "RN", "Reconquête"],
--   "date_range": "2022-2024",
--   "investigation_type": "APEX",
--   "edi_score": 0.72,
--   "source_count": 18
-- }

-- ============================================================
-- STEP 4: Verify migration
-- ============================================================

-- Show updated columns
SELECT column_name, data_type, column_default, is_nullable
FROM information_schema.columns
WHERE table_name = 'memories'
ORDER BY ordinal_position;

-- Show constraints
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'memories'::regclass
ORDER BY conname;

-- ============================================================
-- ROLLBACK (if needed)
-- ============================================================

-- To rollback this migration:
-- ALTER TABLE memories DROP COLUMN IF EXISTS embedding_source;
-- ALTER TABLE memories DROP CONSTRAINT IF EXISTS chk_memory_type;
-- ALTER TABLE memories ADD CONSTRAINT chk_memory_type
--     CHECK (memory_type IN ('note', 'decision', 'task', 'reference', 'conversation'));

-- ============================================================
-- END OF MIGRATION
-- ============================================================
