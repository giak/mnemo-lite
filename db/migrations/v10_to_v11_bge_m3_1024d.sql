-- Migration v10 → v11 : BGE-M3 1024D
-- EPIC-48 Story 48.2 — Semantic Search Optimization
-- Date: 2026-06-09
--
-- Change vector dimensions from 768D (nomic-v1.5) to 1024D (BGE-M3)
-- DROP+RECREATE columns: 768D vectors can't be ALTER TYPEd to 1024D
-- Existing embeddings are lost — reindexing required (Story 48.3)
-- HNSW indexes optimized: m=24, ef_construction=128

-- Step 1: Drop existing HNSW indexes
DROP INDEX IF EXISTS idx_memories_embedding;
DROP INDEX IF EXISTS idx_memories_embedding_half;

-- Step 2: Drop and recreate embedding columns
-- ALTER TYPE vector(768) → vector(1024) fails with existing data
-- Must drop and recreate
ALTER TABLE memories DROP COLUMN IF EXISTS embedding;
ALTER TABLE memories DROP COLUMN IF EXISTS embedding_half;
ALTER TABLE memories ADD COLUMN embedding vector(1024);
ALTER TABLE memories ADD COLUMN embedding_half halfvec(1024);

-- Step 3: Reset embedding_model
UPDATE memories SET embedding_model = NULL WHERE embedding_model IS NOT NULL;

-- Step 4: Recreate HNSW indexes with optimized parameters
-- m=24 (was 16) for better recall on 37K documents
-- ef_construction=128 for better precision at index time
CREATE INDEX idx_memories_embedding ON memories
  USING hnsw (embedding vector_cosine_ops)
  WITH (m='24', ef_construction='128');

CREATE INDEX idx_memories_embedding_half ON memories
  USING hnsw (embedding_half halfvec_cosine_ops)
  WITH (m='24', ef_construction='128');

-- Note: Trigger trg_sync_memory_halfvec syncs embedding_half from embedding.
-- Recreate it if it was lost during column drop:
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'trg_sync_memory_halfvec'
    ) THEN
        CREATE TRIGGER trg_sync_memory_halfvec
        BEFORE INSERT OR UPDATE OF embedding ON memories
        FOR EACH ROW
        EXECUTE FUNCTION sync_memory_halfvec();
    END IF;
END $$;
