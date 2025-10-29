-- EPIC-23 Story 23.3: Create memories table for MCP persistent storage
-- Migration v7 → v8: CREATE memories table (not ALTER - table doesn't exist yet!)
-- Author: Claude Code
-- Date: 2025-10-27

-- ============================================================
-- STEP 1: Create memories table
-- ============================================================

CREATE TABLE IF NOT EXISTS memories (
    -- Core Identity (5 cols)
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Semantic Classification (3 cols)
    memory_type     VARCHAR(50) NOT NULL DEFAULT 'note',
    tags            TEXT[] DEFAULT ARRAY[]::TEXT[],
    author          VARCHAR(100),

    -- Project Context (1 col)
    project_id      UUID,

    -- Vector Embeddings (2 cols)
    embedding       VECTOR(768),
    embedding_model VARCHAR(100) DEFAULT 'nomic-embed-text-v1.5',

    -- Code Graph Links (1 col)
    related_chunks  UUID[] DEFAULT ARRAY[]::UUID[],

    -- MCP 2025-06-18 Features (1 col)
    resource_links  JSONB DEFAULT '[]'::jsonb,

    -- Soft Delete (1 col)
    deleted_at      TIMESTAMPTZ,

    -- Legacy Compatibility (1 col - for future migration from events table)
    metadata        JSONB DEFAULT '{}'::jsonb
);

-- ============================================================
-- STEP 2: Add constraints
-- ============================================================

ALTER TABLE memories
    ADD CONSTRAINT chk_memory_type CHECK (memory_type IN ('note', 'decision', 'task', 'reference', 'conversation')),
    ADD CONSTRAINT chk_content_not_empty CHECK (char_length(content) > 0),
    ADD CONSTRAINT chk_title_not_empty CHECK (char_length(title) > 0),
    ADD CONSTRAINT unique_title_per_project UNIQUE (title, project_id);

-- ============================================================
-- STEP 3: Create indexes
-- ============================================================

-- Timestamp index (most queries filter by time)
CREATE INDEX idx_memories_created_at ON memories (created_at DESC);

-- Project scoping (exclude NULLs = global memories)
CREATE INDEX idx_memories_project_id ON memories (project_id) WHERE project_id IS NOT NULL;

-- Memory type filtering
CREATE INDEX idx_memories_type ON memories (memory_type);

-- Tag array search (GIN for array containment queries)
CREATE INDEX idx_memories_tags ON memories USING GIN (tags);

-- Soft delete filter (partial index for active memories only)
CREATE INDEX idx_memories_deleted_at ON memories (deleted_at) WHERE deleted_at IS NULL;

-- Vector similarity search (HNSW for <100K rows, faster than IVFFlat)
CREATE INDEX idx_memories_embedding ON memories
    USING HNSW (embedding vector_cosine_ops)
    WITH (m=16, ef_construction=64);

-- Related chunks (GIN for array containment)
CREATE INDEX idx_memories_related_chunks ON memories USING GIN (related_chunks);

-- ============================================================
-- STEP 4: Add comments (documentation)
-- ============================================================

COMMENT ON TABLE memories IS 'EPIC-23 Story 23.3: Persistent memory storage for MCP with project scoping and semantic search';
COMMENT ON COLUMN memories.id IS 'Unique memory identifier (UUID v4)';
COMMENT ON COLUMN memories.title IS 'Short memory title (max 200 chars recommended)';
COMMENT ON COLUMN memories.content IS 'Full memory content (plain text or markdown)';
COMMENT ON COLUMN memories.memory_type IS 'Classification: note, decision, task, reference, conversation';
COMMENT ON COLUMN memories.tags IS 'User-defined tags for filtering (PostgreSQL array)';
COMMENT ON COLUMN memories.author IS 'Optional author attribution (e.g., "Claude", "User", "System")';
COMMENT ON COLUMN memories.project_id IS 'NULL = global memory, UUID = project-scoped memory';
COMMENT ON COLUMN memories.embedding IS 'Semantic embedding vector (768D, nomic-embed-text-v1.5)';
COMMENT ON COLUMN memories.embedding_model IS 'Model name used for embedding generation';
COMMENT ON COLUMN memories.related_chunks IS 'Array of code_chunks.id for linking memories to code';
COMMENT ON COLUMN memories.resource_links IS 'MCP 2025-06-18 resource links: [{"uri": "code://chunk/...", "type": "related"}]';
COMMENT ON COLUMN memories.deleted_at IS 'Soft delete: NULL = active, TIMESTAMPTZ = deleted';
COMMENT ON COLUMN memories.metadata IS 'Legacy compatibility field (for future events→memories migration)';

-- ============================================================
-- STEP 5: Insert sample data (for testing - commented out)
-- ============================================================

-- Uncomment to insert test data:
-- INSERT INTO memories (title, content, memory_type, tags, author, project_id) VALUES
-- ('User prefers async/await', 'User mentioned preferring async/await over callbacks for Python async code', 'note', ARRAY['preferences', 'python'], 'Claude', NULL),
-- ('Chose Redis for L2 cache', 'Decision: Redis Standard over Dragonfly for pérennité (15 years vs 3 years). See ADR-001.', 'decision', ARRAY['architecture', 'cache'], 'System', NULL),
-- ('TODO: Implement pagination', 'Need to add cursor-based pagination for large result sets in memory search', 'task', ARRAY['todo', 'performance'], 'Claude', NULL);

-- ============================================================
-- STEP 6: Verify migration
-- ============================================================

-- Show table size
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE tablename = 'memories';

-- Show indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'memories'
ORDER BY indexname;

-- Show constraints
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'memories'::regclass
ORDER BY conname;

-- Count initial memories (should be 0)
SELECT COUNT(*) as memory_count FROM memories;

-- ============================================================
-- STEP 7: Performance validation
-- ============================================================

-- Test vector index exists (should return idx_memories_embedding)
SELECT indexname
FROM pg_indexes
WHERE tablename = 'memories' AND indexname LIKE '%embedding%';

-- Test GIN indexes exist (should return 3: tags, related_chunks, and partial deleted_at won't show here)
SELECT indexname
FROM pg_indexes
WHERE tablename = 'memories' AND indexdef LIKE '%USING gin%';

-- ============================================================
-- ROLLBACK (if needed)
-- ============================================================

-- To rollback this migration, run:
-- DROP TABLE IF EXISTS memories CASCADE;

-- ============================================================
-- END OF MIGRATION
-- ============================================================
