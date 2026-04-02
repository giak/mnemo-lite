# EPIC-23 Story 23.3: Memory Tools & Resources - ULTRATHINK

**Author**: Claude Code
**Date**: 2025-10-27
**Status**: 🚧 ANALYSIS COMPLETE - BLOCKERS IDENTIFIED
**Story Points**: 2 pts
**Estimated Time**: 9h

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [BLOCKER Identification](#blocker-identification)
4. [Memory Architecture Design](#memory-architecture-design)
5. [MCP Tools & Resources Design](#mcp-tools--resources-design)
6. [Database Migration Strategy](#database-migration-strategy)
7. [Implementation Plan](#implementation-plan)
8. [Testing Strategy](#testing-strategy)
9. [Risk Analysis](#risk-analysis)
10. [References](#references)

---

## Executive Summary

### Mission

Implement MCP memory tools and resources to provide persistent, project-scoped memory storage for LLM interactions. Enable create, read, update, delete (CRUD) operations via MCP Tools, and semantic search via MCP Resources.

### Critical Findings

**🚨 BLOCKER #1: Migration Spec Incorrect**
- **Issue**: EPIC-23_README.md says "ALTER TABLE memories (8 cols → 15 cols)" but `memories` table does NOT exist
- **Reality**: Need to CREATE TABLE, not ALTER
- **Impact**: Must rewrite migration v7→v8 completely
- **Status**: Identified, resolution in progress

**✅ Positive Findings**:
- Memory models already exist (`api/models/memory_models.py`)
- MemorySearchService exists with events table integration
- Conversion layer EventModel → Memory already working
- Clear separation of concerns (models, services, repositories)

### Architecture Decision

**Use Dedicated `memories` Table** (vs continue with events table):

| Criteria | Events Table | Dedicated Memories Table | Winner |
|----------|--------------|--------------------------|--------|
| **Data Integrity** | ⚠️ Mixed concerns (events + memories) | ✅ Clear semantic separation | Memories |
| **Schema Fit** | ⚠️ Need metadata conversion hacks | ✅ Native columns (title, tags, author) | Memories |
| **Performance** | ⚠️ Pollutes event queries with memories | ✅ Isolated queries, dedicated indexes | Memories |
| **MCP Semantics** | ⚠️ events vs memories confusion | ✅ Clear resource URIs (`memories://`) | Memories |
| **Migration Cost** | ✅ Zero (no migration) | ⚠️ CREATE TABLE + data migration | Events |
| **Future-Proof** | ❌ Technical debt grows | ✅ Scales cleanly with features | Memories |

**DECISION**: Create dedicated `memories` table despite migration cost. Semantic clarity and future scalability justify the upfront investment.

---

## Current State Analysis

### Existing Memory Infrastructure

#### 1. Memory Models (`api/models/memory_models.py`)

**Already Implemented** ✅:

```python
class MemoryBase(BaseModel):
    memory_type: str           # Type de mémoire (episodic, semantic, etc)
    event_type: str            # Type d'événement (prompt, response, etc)
    role_id: int               # ID du rôle
    content: Dict[str, Any]    # Contenu de la mémoire
    metadata: Dict[str, Any]   # Métadonnées
    embedding: Optional[Union[List[float], str]]  # Vecteur d'embedding

class MemoryCreate(MemoryBase):
    expiration: Optional[datetime]
    timestamp: Optional[datetime]

class Memory(MemoryBase):
    id: uuid.UUID
    timestamp: datetime
    expiration: Optional[datetime]
    similarity_score: Optional[float]

class MemoryUpdate(BaseModel):
    # All fields optional for partial updates
    memory_type: Optional[str]
    event_type: Optional[str]
    ...
```

**Analysis**:
- ✅ Well-structured Pydantic models
- ✅ Embedding validation with `@field_validator`
- ⚠️ Schema mismatch with events table (needs dedicated memories table)
- ⚠️ Missing MCP-specific fields: `title`, `tags`, `author`, `project_id`

#### 2. MemorySearchService (`api/services/memory_search_service.py`)

**Key Methods**:
```python
class MemorySearchService:
    async def search_by_content(query: str, limit: int) -> List[Memory]
    async def search_by_metadata(metadata_filter: Dict, ...) -> List[Memory]
    async def search_by_similarity(query: str, ...) -> List[Memory]
    async def search_by_vector(vector: List[float], ...) -> Tuple[List[Memory], int]
    async def search_hybrid(query: str, ...) -> Tuple[List[EventModel], int]

    def _event_to_memory(event: EventModel) -> Memory  # Conversion layer
```

**Analysis**:
- ✅ Complete search interface implemented
- ✅ Conversion layer EventModel → Memory works
- ⚠️ Uses `event_repository.search_vector()` (needs memory_repository)
- ⚠️ search_hybrid returns EventModel (not Memory) - inconsistent
- ✅ Supports pagination (limit, offset), time filtering (ts_start, ts_end)

#### 3. Events Table (Current Storage)

**Schema**:
```sql
CREATE TABLE events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    content     JSONB NOT NULL,
    embedding   VECTOR(768),
    metadata    JSONB DEFAULT '{}'::jsonb
);

-- Indexes
events_pkey PRIMARY KEY (id)
events_embedding_hnsw_idx HNSW (embedding vector_l2_ops)
events_metadata_gin_idx GIN (metadata jsonb_path_ops)
events_timestamp_idx BTREE (timestamp)
```

**Analysis**:
- ✅ Vector index (HNSW) for fast similarity search
- ✅ JSONB indexes (GIN) for metadata queries
- ⚠️ No memory-specific columns (title, tags, author, project_id)
- ⚠️ Mixed concerns (events + memories in same table)

---

## BLOCKER Identification

### BLOCKER #1: Migration Spec Incorrect ⚠️

**Issue**: EPIC-23_README.md migration spec assumes `memories` table exists:

```sql
-- INCORRECT (from EPIC-23_README.md)
ALTER TABLE memories
  ADD COLUMN memory_type VARCHAR(50) NOT NULL DEFAULT 'note',
  ADD COLUMN author VARCHAR(100),
  ...
```

**Reality**: Database has NO memories table:

```bash
$ docker compose exec db psql -U mnemo -d mnemolite -c "\dt"
 Schema |      Name       | Type  | Owner
--------+-----------------+-------+-------
 public | events          | table | mnemo
 public | code_chunks     | table | mnemo
 public | nodes           | table | mnemo
 public | edges           | table | mnemo
 public | metrics         | table | mnemo
 public | alerts          | table | mnemo
(6 rows)  # NO memories table!
```

**Impact**:
- ❌ Cannot run ALTER TABLE migration as-is
- ⚠️ Need to design complete table schema from scratch
- ⚠️ Must decide on initial vs extended schema
- ⚠️ Data migration from events table required? (decision needed)

**Resolution Strategy**:

**Option A: CREATE TABLE with Full Schema (RECOMMENDED)**
- Create memories table with all 15 columns from day 1
- No future ALTER needed (future-proof)
- Simpler migration path
- **PRO**: One-time migration, complete schema
- **CON**: Larger initial migration

**Option B: CREATE TABLE with Basic Schema → ALTER Later**
- Create with 8 basic columns (matches old spec assumption)
- Run ALTER to add 7 more columns (matches spec)
- **PRO**: Follows original spec intent
- **CON**: Two migrations instead of one, unnecessary complexity

**DECISION**: Option A - CREATE TABLE with full 15-column schema. Simpler, cleaner, follows "do it right the first time" principle.

---

## Memory Architecture Design

### Schema Design: `memories` Table v8

**Complete Schema** (15 columns):

```sql
CREATE TABLE IF NOT EXISTS memories (
    -- Core Identity (5 cols)
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Semantic Classification (3 cols)
    memory_type     VARCHAR(50) NOT NULL DEFAULT 'note',  -- 'note', 'decision', 'task', 'reference'
    tags            TEXT[] DEFAULT ARRAY[]::TEXT[],       -- User-defined tags
    author          VARCHAR(100),                         -- Optional author attribution

    -- Project Context (1 col)
    project_id      UUID,  -- NULL = global, UUID = project-scoped

    -- Vector Embeddings (2 cols)
    embedding       VECTOR(768),                          -- Semantic embedding
    embedding_model VARCHAR(100),                         -- Model used (e.g., 'nomic-embed-text-v1.5')

    -- Code Graph Links (1 col)
    related_chunks  UUID[] DEFAULT ARRAY[]::UUID[],       -- Link to code_chunks.id

    -- MCP 2025-06-18 Features (1 col)
    resource_links  JSONB DEFAULT '[]'::jsonb,            -- MCP resource links

    -- Soft Delete (1 col)
    deleted_at      TIMESTAMPTZ,                          -- NULL = active, TIMESTAMPTZ = deleted

    -- Legacy Compatibility (1 col - optional, for migration only)
    metadata        JSONB DEFAULT '{}'::jsonb             -- Catch-all for migration
);

-- Indexes (7 total)
CREATE INDEX idx_memories_created_at ON memories (created_at DESC);
CREATE INDEX idx_memories_project_id ON memories (project_id) WHERE project_id IS NOT NULL;
CREATE INDEX idx_memories_type ON memories (memory_type);
CREATE INDEX idx_memories_tags ON memories USING GIN (tags);  -- Array GIN index
CREATE INDEX idx_memories_deleted_at ON memories (deleted_at) WHERE deleted_at IS NULL;  -- Partial index (active only)
CREATE INDEX idx_memories_embedding ON memories USING HNSW (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);
CREATE INDEX idx_memories_related_chunks ON memories USING GIN (related_chunks);  -- Array GIN index

-- Constraints
ALTER TABLE memories
    ADD CONSTRAINT chk_memory_type CHECK (memory_type IN ('note', 'decision', 'task', 'reference', 'conversation')),
    ADD CONSTRAINT chk_content_not_empty CHECK (char_length(content) > 0),
    ADD CONSTRAINT unique_title_per_project UNIQUE (title, project_id);  -- Allow duplicate titles across projects

-- Comments
COMMENT ON TABLE memories IS 'EPIC-23 Story 23.3: Persistent memory storage for MCP with project scoping and semantic search';
COMMENT ON COLUMN memories.memory_type IS 'Classification: note (general), decision (ADR-like), task (TODO), reference (docs), conversation (dialogue)';
COMMENT ON COLUMN memories.project_id IS 'NULL = global memory, UUID = project-scoped memory';
COMMENT ON COLUMN memories.related_chunks IS 'Array of code_chunks.id for linking memories to code';
COMMENT ON COLUMN memories.resource_links IS 'MCP 2025-06-18 resource links: [{"uri": "code://chunk/...", "type": "related"}]';
COMMENT ON COLUMN memories.deleted_at IS 'Soft delete: NULL = active, TIMESTAMPTZ = deleted (for elicitation rollback)';
```

**Design Rationale**:

| Feature | Rationale |
|---------|-----------|
| **title + content separation** | MCP best practice: title for listings, content for details |
| **memory_type enum** | Semantic classification for filtering, better than metadata hacks |
| **tags TEXT[]** | Native PostgreSQL array, faster than JSONB for tag queries |
| **project_id with partial index** | Multi-project support, partial index excludes NULLs (global memories) |
| **embedding VECTOR(768)** | Semantic search with cosine similarity via HNSW index |
| **related_chunks UUID[]** | Code graph integration (EPIC-14), links memories to code |
| **resource_links JSONB** | MCP 2025-06-18 spec compliance, extensible for future link types |
| **deleted_at (soft delete)** | Enables rollback after elicitation (delete_memory tool) |
| **HNSW index (not IVFFlat)** | Better for <100K memories, faster queries, simpler tuning |

### Memory Types Taxonomy

```python
class MemoryType(str, Enum):
    NOTE = "note"            # General observations, thoughts
    DECISION = "decision"    # ADR-like decisions (why X was chosen)
    TASK = "task"            # TODO items, action items
    REFERENCE = "reference"  # Documentation links, external resources
    CONVERSATION = "conversation"  # Dialogue context for multi-turn chats
```

**Usage Examples**:
- `note`: "User prefers TailwindCSS for styling"
- `decision`: "Chose Redis over Memcached for L2 cache (see ADR-001)"
- `task`: "TODO: Implement pagination for code search"
- `reference`: "Official FastMCP docs: https://..."
- `conversation`: "User mentioned working on EPIC-23 MCP integration"

---

## MCP Tools & Resources Design

### Tools (3 + 1 with Elicitation)

#### Tool 1: `write_memory`

**Signature**:
```python
@mcp.tool()
async def write_memory(
    ctx: Context,
    title: str,
    content: str,
    memory_type: MemoryType = MemoryType.NOTE,
    tags: List[str] = [],
    author: Optional[str] = None,
    project_id: Optional[str] = None,
    related_chunks: List[str] = [],
    resource_links: List[Dict[str, str]] = []
) -> Dict[str, Any]:
    """
    Create a new persistent memory.

    Args:
        title: Short title (max 200 chars)
        content: Full memory content
        memory_type: Classification (note, decision, task, reference, conversation)
        tags: User-defined tags for filtering
        author: Optional author attribution
        project_id: UUID for project scoping (null = global)
        related_chunks: Array of code chunk UUIDs
        resource_links: MCP resource links [{"uri": "...", "type": "..."}]

    Returns:
        {
            "id": "uuid",
            "title": "Memory title",
            "memory_type": "note",
            "created_at": "2025-10-27T20:00:00Z",
            "embedding_generated": true
        }
    """
```

**Implementation Notes**:
- Generate embedding for `title + content` using EmbeddingService
- Validate `memory_type` against enum
- Validate `project_id` is valid UUID (if provided)
- Set `updated_at = created_at` initially
- Return minimal response (not full Memory object - keep it lightweight)

**Error Handling**:
- Duplicate title+project_id → HTTP 409 Conflict with suggestion
- Invalid memory_type → HTTP 400 with valid options
- Embedding generation failure → graceful degradation (write without embedding, log warning)

#### Tool 2: `update_memory`

**Signature**:
```python
@mcp.tool()
async def update_memory(
    ctx: Context,
    id: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    memory_type: Optional[MemoryType] = None,
    tags: Optional[List[str]] = None,
    author: Optional[str] = None,
    related_chunks: Optional[List[str]] = None,
    resource_links: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """
    Update an existing memory (partial update).

    All fields except id are optional. Only provided fields are updated.

    Args:
        id: Memory UUID to update
        (other fields same as write_memory)

    Returns:
        {
            "id": "uuid",
            "updated_at": "2025-10-27T20:30:00Z",
            "embedding_regenerated": false  # true if title/content changed
        }
    """
```

**Implementation Notes**:
- Fetch existing memory first (verify exists and not deleted)
- Build partial update dict (only non-None fields)
- Regenerate embedding if `title` or `content` changed
- Update `updated_at` timestamp
- Atomic transaction (fetch + update)

**Error Handling**:
- Memory not found → HTTP 404
- Memory already deleted → HTTP 410 Gone with suggestion to restore
- Duplicate title after update → HTTP 409 Conflict

#### Tool 3: `delete_memory` (WITH ELICITATION ⚠️)

**Signature**:
```python
@mcp.tool()
async def delete_memory(
    ctx: Context,
    id: str,
    permanent: bool = False  # Elicitation trigger
) -> Dict[str, Any]:
    """
    Delete a memory (soft delete by default).

    Args:
        id: Memory UUID to delete
        permanent: If True, triggers elicitation for hard delete confirmation

    Returns:
        {
            "id": "uuid",
            "deleted_at": "2025-10-27T20:35:00Z",
            "permanent": false,
            "can_restore": true
        }
    """
```

**Elicitation Flow**:

```python
# Step 1: User calls delete_memory(id="abc-123")
# → Soft delete (set deleted_at = NOW())

# Step 2: User calls delete_memory(id="abc-123", permanent=True)
# → Trigger elicitation
elicitation = Elicitation(
    type="confirmation",
    message=f"⚠️ Permanently delete memory '{memory.title}'?",
    options=[
        {"value": "confirm", "label": "Yes, delete permanently"},
        {"value": "cancel", "label": "No, keep soft deleted"}
    ]
)
raise ElicitationRequired(elicitation)

# Step 3: User confirms → Hard delete (DELETE FROM memories)
if user_choice == "confirm":
    await memory_repository.delete_permanently(id)
```

**Implementation Notes**:
- Default behavior: soft delete (set `deleted_at = NOW()`)
- `permanent=True` → check if already soft deleted → trigger elicitation
- Hard delete removes row from DB (no rollback possible)
- Log all deletions (audit trail)

**Error Handling**:
- Memory not found → HTTP 404
- Already permanently deleted → HTTP 410 Gone

### Resources (3)

#### Resource 1: `memories://get/{id}`

**URI Template**: `memories://get/{id}`

**Implementation**:
```python
@mcp.resource(uri="memories://get/{id}")
async def get_memory(uri: str) -> str:
    """
    Get a single memory by UUID.

    Args:
        uri: Resource URI (id extracted from path)

    Returns:
        JSON string with complete Memory object
    """
    memory_id = extract_id_from_uri(uri)  # Parse "memories://get/abc-123"
    memory = await memory_repository.get_by_id(memory_id)

    if memory is None or memory.deleted_at is not None:
        raise ResourceNotFound(f"Memory {memory_id} not found or deleted")

    return json.dumps(memory.model_dump())
```

**Response Format**:
```json
{
    "id": "abc-123-...",
    "title": "User prefers async/await",
    "content": "User mentioned preferring async/await over callbacks...",
    "memory_type": "note",
    "tags": ["preferences", "coding-style"],
    "author": "Claude",
    "project_id": null,
    "created_at": "2025-10-27T20:00:00Z",
    "updated_at": "2025-10-27T20:00:00Z",
    "embedding": [0.123, -0.456, ...],  // 768 dims
    "embedding_model": "nomic-embed-text-v1.5",
    "related_chunks": ["chunk-uuid-1", "chunk-uuid-2"],
    "resource_links": [{"uri": "code://chunk/xyz", "type": "related"}],
    "deleted_at": null
}
```

**Caching**: No cache (always fresh data for single-memory lookups)

#### Resource 2: `memories://list`

**URI Template**: `memories://list?project_id={project_id}&memory_type={memory_type}&limit={limit}&offset={offset}`

**Implementation**:
```python
@mcp.resource(uri="memories://list")
async def list_memories(uri: str) -> str:
    """
    List memories with optional filters.

    Query params:
        - project_id: UUID (optional, filter by project)
        - memory_type: note|decision|task|reference|conversation (optional)
        - tags: comma-separated (optional, e.g., "python,async")
        - limit: 1-100 (default 10)
        - offset: pagination offset (default 0)
        - include_deleted: true|false (default false)

    Returns:
        JSON string with list of memories + pagination metadata
    """
    params = parse_query_params(uri)

    # Build filters
    filters = {
        "project_id": params.get("project_id"),
        "memory_type": params.get("memory_type"),
        "tags": params.get("tags", "").split(",") if params.get("tags") else [],
        "include_deleted": params.get("include_deleted", "false") == "true"
    }

    limit = min(int(params.get("limit", 10)), 100)
    offset = int(params.get("offset", 0))

    memories, total_count = await memory_repository.list_memories(
        filters=filters,
        limit=limit,
        offset=offset
    )

    response = {
        "memories": [m.model_dump(exclude={"embedding"}) for m in memories],  # Exclude embeddings (large)
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": total_count,
            "has_more": offset + len(memories) < total_count
        }
    }

    return json.dumps(response)
```

**Response Format**:
```json
{
    "memories": [
        {
            "id": "abc-123",
            "title": "User prefers async/await",
            "memory_type": "note",
            "tags": ["preferences"],
            "created_at": "2025-10-27T20:00:00Z",
            "updated_at": "2025-10-27T20:00:00Z"
            // No embedding (excluded for bandwidth)
        },
        // ... more memories
    ],
    "pagination": {
        "limit": 10,
        "offset": 0,
        "total": 42,
        "has_more": true
    }
}
```

**Caching**: 1-minute TTL (Redis L2 cache with query params in cache key)

#### Resource 3: `memories://search/{query}`

**URI Template**: `memories://search/{query}?limit={limit}&offset={offset}&project_id={project_id}`

**Implementation**:
```python
@mcp.resource(uri="memories://search/{query}")
async def search_memories(uri: str) -> str:
    """
    Semantic search for memories using embeddings.

    Path param:
        - query: Search text (URL-encoded)

    Query params:
        - limit: 1-50 (default 5, smaller than code search)
        - offset: pagination offset (default 0)
        - project_id: UUID (optional, filter by project)
        - memory_type: filter by type (optional)
        - tags: comma-separated tags (optional)
        - threshold: similarity threshold 0.0-1.0 (default 0.7)

    Returns:
        JSON string with ranked memories + similarity scores
    """
    query_text = extract_query_from_uri(uri)  # Parse "memories://search/async%20patterns"
    params = parse_query_params(uri)

    # Generate query embedding
    query_embedding = await embedding_service.generate_embedding(query_text)

    # Build filters
    filters = {
        "project_id": params.get("project_id"),
        "memory_type": params.get("memory_type"),
        "tags": params.get("tags", "").split(",") if params.get("tags") else []
    }

    limit = min(int(params.get("limit", 5)), 50)
    offset = int(params.get("offset", 0))
    threshold = float(params.get("threshold", 0.7))

    # Vector search with filters
    memories, total_count = await memory_search_service.search_by_vector(
        vector=query_embedding,
        filters=filters,
        limit=limit,
        offset=offset,
        distance_threshold=threshold
    )

    response = {
        "query": query_text,
        "memories": [
            {
                "id": m.id,
                "title": m.title,
                "content": m.content[:200] + "..." if len(m.content) > 200 else m.content,  # Truncate
                "memory_type": m.memory_type,
                "tags": m.tags,
                "similarity_score": m.similarity_score,
                "created_at": m.created_at
            }
            for m in memories
        ],
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": total_count,
            "has_more": offset + len(memories) < total_count
        },
        "metadata": {
            "threshold": threshold,
            "embedding_model": "nomic-embed-text-v1.5"
        }
    }

    return json.dumps(response)
```

**Response Format**:
```json
{
    "query": "async patterns",
    "memories": [
        {
            "id": "abc-123",
            "title": "Async/await best practices",
            "content": "When using async/await in Python, always...",
            "memory_type": "note",
            "tags": ["python", "async"],
            "similarity_score": 0.89,
            "created_at": "2025-10-27T20:00:00Z"
        }
        // ... more results
    ],
    "pagination": {
        "limit": 5,
        "offset": 0,
        "total": 12,
        "has_more": true
    },
    "metadata": {
        "threshold": 0.7,
        "embedding_model": "nomic-embed-text-v1.5"
    }
}
```

**Caching**: 5-minute TTL (same as code search - Redis L2 with SHA256 cache keys)

---

## Database Migration Strategy

### Migration File: `db/migrations/v7_to_v8_create_memories_table.sql`

**Corrected Migration** (CREATE instead of ALTER):

```sql
-- EPIC-23 Story 23.3: Create memories table for MCP persistent storage
-- Migration v7 → v8: CREATE memories table (not ALTER - table doesn't exist yet!)
-- Author: Claude Code
-- Date: 2025-10-27

-- ============================================================
-- STEP 1: Create memories table
-- ============================================================

CREATE TABLE IF NOT EXISTS memories (
    -- Core Identity
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Semantic Classification
    memory_type     VARCHAR(50) NOT NULL DEFAULT 'note',
    tags            TEXT[] DEFAULT ARRAY[]::TEXT[],
    author          VARCHAR(100),

    -- Project Context
    project_id      UUID,

    -- Vector Embeddings
    embedding       VECTOR(768),
    embedding_model VARCHAR(100) DEFAULT 'nomic-embed-text-v1.5',

    -- Code Graph Links
    related_chunks  UUID[] DEFAULT ARRAY[]::UUID[],

    -- MCP 2025-06-18 Features
    resource_links  JSONB DEFAULT '[]'::jsonb,

    -- Soft Delete
    deleted_at      TIMESTAMPTZ,

    -- Legacy Compatibility (optional, for future migration from events table)
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

-- INSERT INTO memories (title, content, memory_type, tags, author, project_id) VALUES
-- ('User prefers async/await', 'User mentioned preferring async/await over callbacks for Python async code', 'note', ARRAY['preferences', 'python'], 'Claude', NULL),
-- ('Chose Redis for L2 cache', 'Decision: Redis Standard over Dragonfly for pérennité (15 years vs 3 years). See ADR-001.', 'decision', ARRAY['architecture', 'cache'], 'System', 'mnemolite-project-uuid'),
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
-- STEP 7: Update schema version (optional, if using migrations table)
-- ============================================================

-- If using alembic or custom migrations table:
-- UPDATE schema_version SET version = 8, applied_at = NOW() WHERE id = 1;

-- ============================================================
-- END OF MIGRATION
-- ============================================================
```

### Migration Validation Plan

**Pre-migration checks**:
```bash
# 1. Verify PostgreSQL 18 with pgvector
docker compose exec db psql -U mnemo -d mnemolite -c "SELECT version();"
docker compose exec db psql -U mnemo -d mnemolite -c "SELECT * FROM pg_extension WHERE extname = 'vector';"

# 2. Check no memories table exists
docker compose exec db psql -U mnemo -d mnemolite -c "\dt memories"
# Expected: "Did not find any relation named "memories""

# 3. Backup database (safety)
docker compose exec db pg_dump -U mnemo mnemolite > backup_before_v8_$(date +%Y%m%d_%H%M%S).sql
```

**Run migration**:
```bash
docker compose exec db psql -U mnemo -d mnemolite -f /app/scripts/v7_to_v8_create_memories_table.sql
```

**Post-migration validation**:
```bash
# 1. Verify table created
docker compose exec db psql -U mnemo -d mnemolite -c "\d memories"

# 2. Check indexes (should be 7)
docker compose exec db psql -U mnemo -d mnemolite -c "\di memories*"

# 3. Check constraints (should be 4)
docker compose exec db psql -U mnemo -d mnemolite -c "SELECT conname FROM pg_constraint WHERE conrelid = 'memories'::regclass;"

# 4. Test insert (should succeed)
docker compose exec db psql -U mnemo -d mnemolite -c "
INSERT INTO memories (title, content, memory_type, tags)
VALUES ('Test memory', 'Test content', 'note', ARRAY['test']);
SELECT * FROM memories;
"

# 5. Test vector index (should use HNSW)
docker compose exec db psql -U mnemo -d mnemolite -c "
EXPLAIN ANALYZE
SELECT * FROM memories
ORDER BY embedding <-> '[0.1, 0.2, ...]'::vector
LIMIT 5;
"
# Expected: "Index Scan using idx_memories_embedding on memories"
```

### Rollback Plan

**If migration fails**:
```sql
-- Rollback v8 → v7: Drop memories table
DROP TABLE IF EXISTS memories CASCADE;

-- Restore from backup
psql -U mnemo -d mnemolite < backup_before_v8_YYYYMMDD_HHMMSS.sql
```

**Impact**: Zero data loss (no memories exist yet, table is new)

---

## Implementation Plan

### Sub-Story Breakdown (6 sub-stories, 9h total)

#### Sub-Story 23.3.1: Database Migration (1.5h)

**Tasks**:
1. Create migration file `v7_to_v8_create_memories_table.sql` (20 min)
2. Test migration locally (docker-compose restart) (15 min)
3. Validate indexes (EXPLAIN ANALYZE) (10 min)
4. Update README with migration instructions (15 min)
5. Create rollback procedure (10 min)
6. Commit migration file (10 min)

**Deliverables**:
- `db/migrations/v7_to_v8_create_memories_table.sql`
- Migration validation checklist
- Rollback procedure documented

**Tests**:
- ✅ Table created with 15 columns
- ✅ 7 indexes present (HNSW, GIN, BTREE)
- ✅ 4 constraints working (CHECK, UNIQUE)
- ✅ INSERT/SELECT works
- ✅ Vector similarity query uses HNSW index

#### Sub-Story 23.3.2: Memory Pydantic Models (1h)

**Tasks**:
1. Create `api/mnemo_mcp/models/memory_models.py` (NEW file for MCP) (20 min)
2. Define MemoryBase, MemoryCreate, MemoryUpdate, Memory models (15 min)
3. Define MemoryResponse, MemoryListResponse, MemorySearchResponse (15 min)
4. Add field validators (title length, content not empty, UUID validation) (10 min)

**Deliverables**:
- `api/mnemo_mcp/models/memory_models.py` (~300 lines)

**Models**:
```python
# api/mnemo_mcp/models/memory_models.py

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
from enum import Enum

class MemoryType(str, Enum):
    NOTE = "note"
    DECISION = "decision"
    TASK = "task"
    REFERENCE = "reference"
    CONVERSATION = "conversation"

class MemoryBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Memory title")
    content: str = Field(..., min_length=1, description="Memory content")
    memory_type: MemoryType = Field(MemoryType.NOTE, description="Memory classification")
    tags: List[str] = Field(default_factory=list, description="User-defined tags")
    author: Optional[str] = Field(None, max_length=100, description="Author attribution")
    project_id: Optional[uuid.UUID] = Field(None, description="Project UUID (null = global)")
    related_chunks: List[uuid.UUID] = Field(default_factory=list, description="Related code chunks")
    resource_links: List[Dict[str, str]] = Field(default_factory=list, description="MCP resource links")

class MemoryCreate(MemoryBase):
    pass

class MemoryUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    memory_type: Optional[MemoryType] = None
    tags: Optional[List[str]] = None
    author: Optional[str] = Field(None, max_length=100)
    related_chunks: Optional[List[uuid.UUID]] = None
    resource_links: Optional[List[Dict[str, str]]] = None

class Memory(MemoryBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    embedding: Optional[List[float]] = None
    embedding_model: Optional[str] = None
    deleted_at: Optional[datetime] = None

class MemoryResponse(BaseModel):
    """Response for write_memory and update_memory tools"""
    id: uuid.UUID
    title: str
    memory_type: MemoryType
    created_at: datetime
    updated_at: datetime
    embedding_generated: bool

class MemoryListResponse(BaseModel):
    """Response for memories://list resource"""
    memories: List[Memory]
    pagination: Dict[str, Any]

class MemorySearchResponse(BaseModel):
    """Response for memories://search resource"""
    query: str
    memories: List[Memory]
    pagination: Dict[str, Any]
    metadata: Dict[str, Any]
```

**Tests**:
- ✅ Model validation (valid data passes)
- ✅ Field validation (min_length, max_length, UUID format)
- ✅ Enum validation (MemoryType)
- ✅ Optional fields work (None values)

#### Sub-Story 23.3.3: write_memory + update_memory Tools (2h)

**Tasks**:
1. Create `api/mnemo_mcp/tools/memory_tools.py` (30 min)
2. Implement `write_memory` tool (30 min)
3. Implement `update_memory` tool (30 min)
4. Integrate EmbeddingService for embeddings (15 min)
5. Error handling (duplicate title, invalid UUID) (15 min)

**Deliverables**:
- `api/mnemo_mcp/tools/memory_tools.py` (~400 lines)
- Unit tests in `tests/mnemo_mcp/test_memory_tools.py` (~300 lines)

**Implementation**:
```python
# api/mnemo_mcp/tools/memory_tools.py

from mnemo_mcp.core.base import BaseMCPComponent
from mnemo_mcp.models.memory_models import MemoryCreate, MemoryUpdate, MemoryResponse
from mcp import Context
from typing import Dict, Any, Optional, List
import uuid

class MemoryTools(BaseMCPComponent):
    async def write_memory(
        self,
        ctx: Context,
        title: str,
        content: str,
        memory_type: str = "note",
        tags: List[str] = [],
        author: Optional[str] = None,
        project_id: Optional[str] = None,
        related_chunks: List[str] = [],
        resource_links: List[Dict[str, str]] = []
    ) -> Dict[str, Any]:
        # Validate and create MemoryCreate object
        memory_create = MemoryCreate(
            title=title,
            content=content,
            memory_type=memory_type,
            tags=tags,
            author=author,
            project_id=uuid.UUID(project_id) if project_id else None,
            related_chunks=[uuid.UUID(c) for c in related_chunks],
            resource_links=resource_links
        )

        # Generate embedding
        embedding_text = f"{title}\n\n{content}"
        embedding = await self.embedding_service.generate_embedding(embedding_text)

        # Save to database
        memory = await self.memory_repository.create(memory_create, embedding)

        return MemoryResponse(
            id=memory.id,
            title=memory.title,
            memory_type=memory.memory_type,
            created_at=memory.created_at,
            updated_at=memory.updated_at,
            embedding_generated=embedding is not None
        ).model_dump()
```

**Tests**:
- ✅ write_memory creates memory in DB
- ✅ Embedding generated and stored
- ✅ Duplicate title raises error
- ✅ Invalid project_id raises error
- ✅ update_memory modifies existing memory
- ✅ Partial update (only title) works
- ✅ update_memory regenerates embedding if content changes

#### Sub-Story 23.3.4: memories://get + memories://list Resources (1.5h)

**Tasks**:
1. Create `api/mnemo_mcp/resources/memory_resources.py` (30 min)
2. Implement `memories://get/{id}` resource (20 min)
3. Implement `memories://list` resource with filters (30 min)
4. Add pagination logic (10 min)

**Deliverables**:
- `api/mnemo_mcp/resources/memory_resources.py` (~350 lines)
- Unit tests in `tests/mnemo_mcp/test_memory_resources.py` (~400 lines)

**Implementation**:
```python
# api/mnemo_mcp/resources/memory_resources.py

from mnemo_mcp.core.base import BaseMCPComponent
import json
from typing import Optional

class MemoryResources(BaseMCPComponent):
    async def get_memory(self, uri: str) -> str:
        # Extract ID from URI: "memories://get/abc-123"
        memory_id = uri.split("/")[-1]

        memory = await self.memory_repository.get_by_id(memory_id)
        if memory is None or memory.deleted_at is not None:
            raise ResourceNotFound(f"Memory {memory_id} not found")

        return json.dumps(memory.model_dump())

    async def list_memories(self, uri: str) -> str:
        # Parse query params
        params = parse_query_params(uri)
        filters = {
            "project_id": params.get("project_id"),
            "memory_type": params.get("memory_type"),
            "tags": params.get("tags", "").split(",") if params.get("tags") else []
        }
        limit = min(int(params.get("limit", 10)), 100)
        offset = int(params.get("offset", 0))

        memories, total = await self.memory_repository.list_memories(filters, limit, offset)

        response = {
            "memories": [m.model_dump(exclude={"embedding"}) for m in memories],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": total,
                "has_more": offset + len(memories) < total
            }
        }
        return json.dumps(response)
```

**Tests**:
- ✅ get_memory returns full memory object
- ✅ get_memory raises error for deleted memory
- ✅ list_memories returns paginated list
- ✅ Filters work (project_id, memory_type, tags)
- ✅ Pagination works (limit, offset)

#### Sub-Story 23.3.5: memories://search Resource (1.5h)

**Tasks**:
1. Implement `memories://search/{query}` resource (40 min)
2. Integrate MemorySearchService (20 min)
3. Add Redis L2 caching (20 min)
4. Add similarity threshold filtering (10 min)

**Deliverables**:
- Updated `api/mnemo_mcp/resources/memory_resources.py` (+150 lines)
- Unit tests in `tests/mnemo_mcp/test_memory_resources.py` (+200 lines)

**Implementation**:
```python
async def search_memories(self, uri: str) -> str:
    # Extract query: "memories://search/async%20patterns"
    query_text = unquote(uri.split("/")[-1])
    params = parse_query_params(uri)

    # Check cache
    cache_key = f"memory_search:{sha256(uri.encode()).hexdigest()}"
    cached = await self.redis_client.get(cache_key)
    if cached:
        return cached

    # Generate embedding
    embedding = await self.embedding_service.generate_embedding(query_text)

    # Search with filters
    filters = {
        "project_id": params.get("project_id"),
        "memory_type": params.get("memory_type")
    }
    limit = min(int(params.get("limit", 5)), 50)
    threshold = float(params.get("threshold", 0.7))

    memories, total = await self.memory_search_service.search_by_vector(
        vector=embedding,
        filters=filters,
        limit=limit,
        distance_threshold=threshold
    )

    response = {
        "query": query_text,
        "memories": [m.model_dump() for m in memories],
        "pagination": {"limit": limit, "total": total},
        "metadata": {"threshold": threshold}
    }

    result = json.dumps(response)
    await self.redis_client.set(cache_key, result, ex=300)  # 5 min TTL
    return result
```

**Tests**:
- ✅ search_memories returns ranked results
- ✅ Similarity scores present
- ✅ Cache hit returns cached result
- ✅ Cache miss generates embedding and queries DB
- ✅ Threshold filtering works

#### Sub-Story 23.3.6: delete_memory with Elicitation (1.5h)

**Tasks**:
1. Implement soft delete (set deleted_at) (20 min)
2. Implement elicitation flow for permanent delete (30 min)
3. Add hard delete logic (DELETE FROM) (20 min)
4. Add audit logging (10 min)
5. Error handling (not found, already deleted) (10 min)

**Deliverables**:
- Updated `api/mnemo_mcp/tools/memory_tools.py` (+100 lines)
- Unit tests (+150 lines)

**Implementation**:
```python
async def delete_memory(
    self,
    ctx: Context,
    id: str,
    permanent: bool = False
) -> Dict[str, Any]:
    memory = await self.memory_repository.get_by_id(id)
    if not memory:
        raise MemoryNotFound(id)

    # Soft delete (default)
    if not permanent:
        await self.memory_repository.soft_delete(id)
        return {
            "id": id,
            "deleted_at": datetime.now().isoformat(),
            "permanent": False,
            "can_restore": True
        }

    # Hard delete (requires elicitation)
    if memory.deleted_at is None:
        raise ValueError("Must soft delete before permanent delete")

    # Trigger elicitation
    elicitation = Elicitation(
        type="confirmation",
        message=f"⚠️ Permanently delete memory '{memory.title}'? This cannot be undone.",
        options=[
            {"value": "confirm", "label": "Yes, delete permanently"},
            {"value": "cancel", "label": "No, keep soft deleted"}
        ]
    )
    raise ElicitationRequired(elicitation)

    # After user confirms (handled by FastMCP)
    await self.memory_repository.delete_permanently(id)
    self.logger.info(f"Memory {id} permanently deleted", extra={"memory_id": id})

    return {
        "id": id,
        "permanent": True,
        "can_restore": False
    }
```

**Tests**:
- ✅ Soft delete sets deleted_at
- ✅ Soft deleted memories excluded from list/search
- ✅ permanent=True triggers elicitation
- ✅ Hard delete removes row from DB
- ✅ Audit log entry created

---

## Testing Strategy

### Unit Tests (100% Coverage Target)

**Test Files**:
1. `tests/mnemo_mcp/test_memory_models.py` (~150 lines)
2. `tests/mnemo_mcp/test_memory_tools.py` (~400 lines)
3. `tests/mnemo_mcp/test_memory_resources.py` (~600 lines)

**Test Categories**:

#### 1. Model Validation Tests
```python
def test_memory_create_valid():
    memory = MemoryCreate(title="Test", content="Content", memory_type="note")
    assert memory.title == "Test"

def test_memory_title_too_long():
    with pytest.raises(ValidationError):
        MemoryCreate(title="a" * 201, content="Content")

def test_memory_type_invalid():
    with pytest.raises(ValidationError):
        MemoryCreate(title="Test", content="Content", memory_type="invalid")
```

#### 2. write_memory Tool Tests
```python
@pytest.mark.asyncio
async def test_write_memory_success(memory_tools, mock_embedding_service, mock_db):
    response = await memory_tools.write_memory(
        ctx=Context(),
        title="Test Memory",
        content="Test content",
        memory_type="note",
        tags=["test"]
    )
    assert response["id"] is not None
    assert response["embedding_generated"] is True
    assert mock_db.create.called

@pytest.mark.asyncio
async def test_write_memory_duplicate_title(memory_tools):
    # First write
    await memory_tools.write_memory(ctx=Context(), title="Duplicate", content="Content")

    # Second write (should fail)
    with pytest.raises(DuplicateMemoryError):
        await memory_tools.write_memory(ctx=Context(), title="Duplicate", content="Content")
```

#### 3. update_memory Tool Tests
```python
@pytest.mark.asyncio
async def test_update_memory_partial(memory_tools):
    # Create memory
    response = await memory_tools.write_memory(ctx=Context(), title="Original", content="Original content")
    memory_id = response["id"]

    # Update only title
    update_response = await memory_tools.update_memory(ctx=Context(), id=memory_id, title="Updated")

    assert update_response["id"] == memory_id
    assert update_response["embedding_regenerated"] is False  # Content unchanged
```

#### 4. Resource Tests
```python
@pytest.mark.asyncio
async def test_get_memory_success(memory_resources, mock_db):
    memory = Memory(id=uuid.uuid4(), title="Test", content="Content", ...)
    mock_db.get_by_id.return_value = memory

    result = await memory_resources.get_memory("memories://get/abc-123")
    data = json.loads(result)
    assert data["id"] == str(memory.id)

@pytest.mark.asyncio
async def test_list_memories_pagination(memory_resources):
    result = await memory_resources.list_memories("memories://list?limit=10&offset=0")
    data = json.loads(result)
    assert "pagination" in data
    assert data["pagination"]["limit"] == 10
```

#### 5. Search Tests
```python
@pytest.mark.asyncio
async def test_search_memories_cache_hit(memory_resources, mock_redis):
    cached_result = '{"query": "test", "memories": []}'
    mock_redis.get.return_value = cached_result

    result = await memory_resources.search_memories("memories://search/test")
    assert result == cached_result
    assert not mock_redis.set.called  # No new cache write

@pytest.mark.asyncio
async def test_search_memories_similarity_threshold(memory_resources):
    result = await memory_resources.search_memories("memories://search/test?threshold=0.9")
    # Verify only high-similarity results returned
```

#### 6. delete_memory Tests
```python
@pytest.mark.asyncio
async def test_delete_memory_soft(memory_tools):
    response = await memory_tools.delete_memory(ctx=Context(), id="abc-123")
    assert response["permanent"] is False
    assert response["can_restore"] is True

@pytest.mark.asyncio
async def test_delete_memory_elicitation(memory_tools):
    # Soft delete first
    await memory_tools.delete_memory(ctx=Context(), id="abc-123")

    # Attempt permanent delete (should trigger elicitation)
    with pytest.raises(ElicitationRequired) as exc:
        await memory_tools.delete_memory(ctx=Context(), id="abc-123", permanent=True)

    assert "Permanently delete" in exc.value.elicitation.message
```

### Integration Tests

**Test Scenarios**:
1. End-to-end memory CRUD flow
2. Search with filters + pagination
3. Cache invalidation on update
4. Elicitation flow simulation

### Performance Tests

**Benchmarks**:
- write_memory: <100ms (with embedding generation)
- update_memory: <50ms (no embedding regen)
- search_memories (cached): <10ms
- search_memories (uncached): <200ms
- Vector similarity search: <100ms (1000 memories)

---

## Risk Analysis

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **BLOCKER: Migration spec wrong** | ✅ Confirmed | 🔴 High | Fixed in ULTRATHINK (CREATE vs ALTER) |
| Vector index slow (<100K rows) | Low | Medium | HNSW tuned (m=16, ef_construction=64) |
| Embedding generation timeout | Medium | Medium | Graceful degradation (skip embedding) |
| Duplicate title conflicts | Low | Low | Clear error messages + suggestions |
| Elicitation UX confusion | Low | Medium | Clear messaging + docs |
| Cache invalidation bugs | Low | Medium | Conservative TTL (5 min), clear invalidation |

### Operational Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Memory table grows unbounded | Medium | High | Retention policy (90 days soft deleted) |
| Embedding storage cost | Medium | Medium | Vector dimension 768 (not 1536) |
| Search query abuse | Low | Medium | Rate limiting (future) |

### Mitigation Strategies

**1. Memory Growth**:
```sql
-- Cron job: Delete old soft-deleted memories (run weekly)
DELETE FROM memories
WHERE deleted_at < NOW() - INTERVAL '90 days';
```

**2. Vector Index Performance**:
```sql
-- Monitor index usage
SELECT
    schemaname, tablename, indexname,
    idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
WHERE tablename = 'memories' AND indexname = 'idx_memories_embedding';

-- If slow, rebuild index with higher ef_construction
DROP INDEX idx_memories_embedding;
CREATE INDEX idx_memories_embedding ON memories
    USING HNSW (embedding vector_cosine_ops)
    WITH (m=32, ef_construction=128);  -- More accurate, slower build
```

**3. Embedding Failures**:
```python
# Graceful degradation in write_memory
try:
    embedding = await embedding_service.generate_embedding(text)
except EmbeddingError as e:
    logger.warning(f"Embedding generation failed: {e}")
    embedding = None  # Store without embedding, still searchable by metadata
```

---

## References

### Internal Documentation

- `EPIC-23_README.md` - Main EPIC specification
- `EPIC-23_STORY_23.1_COMPLETION_REPORT.md` - FastMCP setup patterns
- `EPIC-23_STORY_23.2_ULTRATHINK.md` - Tool vs Resource decision rationale
- `EPIC-23_STORY_23.2_COMPLETION_REPORT.md` - Pydantic model patterns
- `ADR-001_cache_strategy.md` - Redis L2 cache patterns

### External References

- **MCP Spec 2025-06-18**: https://spec.modelcontextprotocol.io/2025-06-18/
  - Elicitation: https://spec.modelcontextprotocol.io/2025-06-18/basic/prompts/#elicitation
  - Resource Links: https://spec.modelcontextprotocol.io/2025-06-18/basic/resources/#resource-links
- **FastMCP SDK**: https://github.com/modelcontextprotocol/python-sdk
- **pgvector HNSW**: https://github.com/pgvector/pgvector#hnsw
- **PostgreSQL Array Types**: https://www.postgresql.org/docs/current/arrays.html

### Similar Implementations

- **Serena MCP** (reference): No equivalent found (no serena-main/ directory)
- **Story 23.2 (search_code)**: Tool implementation pattern reused
- **MemorySearchService**: Existing search patterns adapted

---

## Next Steps

### Immediate Actions (Ready to Implement)

1. **Review ULTRATHINK with user** ✅ (this document)
2. **Get user approval** for:
   - BLOCKER resolution (CREATE TABLE vs ALTER)
   - Schema design (15 columns, HNSW index)
   - Tool/Resource design (3 tools + 3 resources)
3. **Start implementation** (Sub-story 23.3.1: Migration)

### Implementation Order

```
23.3.1: Migration (1.5h)
   ↓
23.3.2: Pydantic models (1h)
   ↓
23.3.3: write_memory + update_memory (2h)
   ↓
23.3.4: memories://get + memories://list (1.5h)
   ↓
23.3.5: memories://search (1.5h)
   ↓
23.3.6: delete_memory + elicitation (1.5h)
   ↓
Testing + Validation (integrate with 9h estimate)
   ↓
COMPLETION REPORT
```

### Success Criteria

- ✅ memories table created with 15 columns
- ✅ 7 indexes present (including HNSW for embeddings)
- ✅ 3 tools implemented (write, update, delete with elicitation)
- ✅ 3 resources implemented (get, list, search)
- ✅ 100% test coverage (unit tests)
- ✅ Redis L2 caching working (5-min TTL)
- ✅ Graceful degradation (embedding failures)
- ✅ MCP Inspector validation passing

---

**Status**: 🚧 READY FOR IMPLEMENTATION
**Blockers**: 0 (BLOCKER #1 resolved)
**Approval Needed**: User confirmation to proceed

**Total Analysis Time**: ~3h
**Document Size**: ~1800 lines (comprehensive)

**Recommendation**: Proceed with Sub-story 23.3.1 (Database Migration) after user approval.
