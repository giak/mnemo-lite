-- Migration: v8 → v9 - Create Projects Table
-- Date: 2025-11-12
-- Purpose: Add proper project management with soft delete and referential integrity

BEGIN;

-- ============================================================================
-- 1. CREATE PROJECTS TABLE
-- ============================================================================

CREATE TABLE projects (
  -- Primary Key
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Core Fields
  name TEXT UNIQUE NOT NULL,                    -- Technical name: "mnemolite" (lowercase)
  display_name TEXT NOT NULL,                   -- Display name: "MnemoLite" (with capitals)
  description TEXT,                             -- Project description for UI

  -- Metadata
  repository_path TEXT,                         -- "/home/giak/Work/MnemoLite"
  project_type TEXT DEFAULT 'application',      -- 'application', 'library', 'tool', etc.

  -- Soft Delete
  status TEXT DEFAULT 'active' CHECK (status IN ('active', 'archived')),

  -- Timestamps
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- 2. CREATE INDEXES
-- ============================================================================

CREATE INDEX idx_projects_name ON projects(name);
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_name_status ON projects(name, status);  -- Composite for lookups

-- ============================================================================
-- 3. ADD FOREIGN KEY TO MEMORIES
-- ============================================================================

-- Add FK constraint (memories.project_id already exists as UUID)
-- No ON DELETE because we use soft delete (status='archived')
ALTER TABLE memories
  ADD CONSTRAINT fk_memories_project
  FOREIGN KEY (project_id) REFERENCES projects(id);

-- Add index for FK lookups (if not exists - may already exist from previous migrations)
CREATE INDEX IF NOT EXISTS idx_memories_project_id ON memories(project_id);

-- ============================================================================
-- 4. INSERT INITIAL PROJECTS
-- ============================================================================

-- Insert MnemoLite project (primary project)
INSERT INTO projects (name, display_name, description, repository_path, project_type, status)
VALUES (
  'mnemolite',
  'MnemoLite',
  'PostgreSQL 18 Cognitive Memory + Code Intelligence System',
  '/home/giak/Work/MnemoLite',
  'application',
  'active'
)
ON CONFLICT (name) DO NOTHING;

-- Add other known projects here as needed
-- Example:
-- INSERT INTO projects (name, display_name, repository_path, project_type)
-- VALUES ('serena', 'Serena', '/home/giak/Work/Serena', 'application');

-- ============================================================================
-- 5. UPDATE SCHEMA VERSION
-- ============================================================================

-- Update schema version tracking (if you have a versions table)
-- INSERT INTO schema_versions (version, applied_at) VALUES (9, NOW());

COMMIT;

-- ============================================================================
-- ROLLBACK (if needed)
-- ============================================================================

-- To rollback this migration:
-- BEGIN;
-- ALTER TABLE memories DROP CONSTRAINT IF EXISTS fk_memories_project;
-- DROP INDEX IF EXISTS idx_memories_project_id;
-- DROP INDEX IF EXISTS idx_projects_name_status;
-- DROP INDEX IF EXISTS idx_projects_status;
-- DROP INDEX IF EXISTS idx_projects_name;
-- DROP TABLE IF EXISTS projects CASCADE;
-- COMMIT;
