-- Migration v11 → v12 : events 768D → 1024D
-- EPIC-62 - Events Migration 1024
-- Date: 2026-08-07
--
-- La migration v10→v11 (EPIC-48) a migre `memories` vers BGE-M3 1024D
-- mais JAMAIS la table `events` (768D nomic-embed-text-v1.5, index HNSW
-- vector_l2_ops). Consequences :
--   - POST /v1/events/ : l'embedding auto-genere (bge-m3 1024D) etait
--     insere dans une colonne vector(768) -> DataError, event perdu
--   - GET /v1/search/ (voie events, MemorySearchService.search_by_similarity) :
--     ValueError "Vector dimension mismatch. Expected 768, got 1024" -> 500
--   - 4 tests famille events en echec (preuve stash EPIC-62)
--
-- Pattern identique a v10→v11 : DROP+RECREATE (un vecteur 768D ne peut
-- pas etre ALTER TYPEd vers 1024D avec des donnees existantes).
-- Les 2 894 embeddings 768D existants sont perdus -> backfill requis
-- (scripts/backfill_event_embeddings.py, EPIC-62).

-- Step 1: Drop existing HNSW index
DROP INDEX IF EXISTS events_embedding_hnsw_idx;

-- Step 2: Drop and recreate embedding column
ALTER TABLE events DROP COLUMN IF EXISTS embedding;
ALTER TABLE events ADD COLUMN embedding vector(1024);

-- Step 3: Recreate HNSW index (meme operateur L2 que le query builder <->)
CREATE INDEX events_embedding_hnsw_idx ON events
  USING hnsw (embedding vector_l2_ops)
  WITH (m='24', ef_construction='128');
