# EPIC-23: MCP Integration - Model Context Protocol Server

**Status**: ✅ PHASE 1 COMPLETE | ✅ PHASE 2 COMPLETE | 🚧 PHASE 3 IN PROGRESS (40%)
**Priority**: HIGH
**Estimation**: 23 story points → 46 sub-stories → ~82 hours
**Progress**: 19/23 pts (83%) | 36/46 sub-stories (78%)
**Version**: 1.8.0
**Created**: 2025-01-15
**Started**: 2025-10-27
**Last Updated**: 2025-10-28
**MCP Spec**: 2025-06-18 (latest)

---

## 📊 Progress Summary

| Metric | Value |
|--------|-------|
| **Overall Progress** | 19/23 pts (83%) |
| **Phase 1** | ✅ 3/3 stories COMPLETE (Stories 23.1-23.3 ✅) |
| **Phase 2** | ✅ 4/4 stories COMPLETE (Stories 23.4-23.10 ✅) |
| **Phase 3** | ✅ 2/5 stories COMPLETE (40%) |
| **Sub-stories** | 36/46 (78%) |
| **Tests** | 355/355 passing ✅ (100% success rate) |
| **Time Spent** | 47.5h (23.1: 12h, 23.2: 4h, 23.3: 9h, 23.4: 3.5h, 23.5: 7h, 23.6: 7h, 23.7: 2h, 23.10: 2h, 23.11: 3h) |
| **Documentation** | 2 Getting Started guides, 9 Completion Reports, 6 ULTRATHINKs, 1 Validation Report, ELICITATION_PATTERNS guide, Progress Tracker |

**Latest Milestone**: ✅ Story 23.11 COMPLETE - Elicitation Flows (2025-10-28) ⭐ **PHASE 3: 40% COMPLETE!**
- ✅ 6 MCP prompt templates implemented (`analyze_codebase`, `refactor_suggestions`, `find_bugs`, `generate_tests`, `explain_code`, `security_audit`)
- ✅ Single file implementation (`api/mnemo_mcp/prompts.py`, 520 lines)
- ✅ Markdown-formatted output for better UX in Claude Desktop
- ✅ Parameterized templates (language, severity, focus, etc.)
- ✅ Tool/resource references in URI format (consistent with MCP spec)
- ✅ Comprehensive docstrings for each prompt
- ✅ Server integration (registered in `server.py`)
- ✅ No unit tests (justified - text templates with no executable logic)
- ✅ **71% faster than estimated** (2h actual vs 7h estimated)
- ✅ 100% infrastructure reuse (prompts guide users to existing tools/resources)
- 📊 **Impact**: Phase 2 now 100% complete (4/4 stories, 9/9 points)

**Story 23.11 Milestone**: ✅ COMPLETE - Elicitation Flows (2025-10-28)
- ✅ 2 elicitation helpers (`request_confirmation()`, `request_choice()`)
- ✅ 2 Pydantic models (`ElicitationRequest`, `ElicitationResult`)
- ✅ Integration with 2 existing tools (memory deletion, project switching)
- ✅ 10 unit tests + 7 integration tests updated (355/355 total passing)
- ✅ ELICITATION_PATTERNS.md guide (5,200+ words, comprehensive)
- ✅ Safe defaults (fail-safe behavior on errors)
- ✅ Automation support (bypass flags for CI/CD)
- ✅ Dangerous flag (⚠️ warning for destructive operations)
- ✅ **Perfect estimation** (3h actual vs 3h estimated)
- 📊 **Impact**: Phase 3 now 40% complete (2/5 stories, 19/23 pts)

**Next Up**: Story 23.8 (HTTP Transport), 23.9 (Documentation), or 23.12 (MCP Inspector)

**References**:
- **Progress Tracker**: `EPIC-23_PROGRESS_TRACKER.md`
- **Validation Report**: `EPIC-23_VALIDATION_REPORT_2025-10-28.md` ⭐
- **Story Reports**: 23.1, 23.2, 23.3, 23.4, 23.5, 23.6, 23.7, 23.10, 23.11 Completion Reports
- **ULTRATHINKs**: 23.2, 23.5, 23.6, 23.7, 23.10, 23.11 Design Analysis Documents
- **Getting Started**: `docs/mcp/GETTING_STARTED.md`
- **Elicitation Patterns**: `docs/ELICITATION_PATTERNS.md` ⭐ NEW

---

## Vision

Transform **MnemoLite** from an internal FastAPI service into a **Model Context Protocol (MCP) Server** accessible by LLMs like Claude, enabling:

- 🔍 **Semantic Code Search**: LLMs query codebases with natural language
- 🧠 **Persistent Memory**: Store architectural decisions, bug reports, project notes
- 🕸️ **Code Graph Navigation**: Explore function calls, imports, inheritance relationships
- 📊 **Real-Time Analytics**: Monitor search performance, cache hit rates
- 🔌 **Dual Transport**: stdio (Claude Desktop) + HTTP/SSE (Web clients)

**MnemoLite MCP** = "Serena for semantic search" + "RAG for code" + "PostgreSQL 18 cognitive memory"

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│         MCP Protocol Layer (FastMCP)                    │
│   ┌──────────────────┐  ┌──────────────────┐           │
│   │ stdio Transport  │  │ HTTP/SSE Trans.  │           │
│   │ (Claude Desktop) │  │ (Web/API)        │           │
│   └──────────────────┘  └──────────────────┘           │
└─────────────────────────────────────────────────────────┘
                        │
┌─────────────────────────────────────────────────────────┐
│         MCP Components Layer                            │
│   ┌────────────┐ ┌──────────────┐ ┌─────────────┐      │
│   │ 8 Tools    │ │ 15 Resources │ │ 6 Prompts   │      │
│   │ (write)    │ │ (read)       │ │ (templates) │      │
│   └────────────┘ └──────────────┘ └─────────────┘      │
└─────────────────────────────────────────────────────────┘
                        │
┌─────────────────────────────────────────────────────────┐
│         Services Layer (MnemoLite Existing)             │
│   • HybridCodeSearchService (EPIC-11)                   │
│   • CodeGraphService (EPIC-14)                          │
│   • CodeIndexingService                                 │
│   • MetricsCollectorService (EPIC-22)                   │
└─────────────────────────────────────────────────────────┘
                        │
┌─────────────────────────────────────────────────────────┐
│         Data Layer                                      │
│   • PostgreSQL 18 (pgvector, memories table)            │
│   • Redis (L2 cache, 5-minute TTL)                      │
└─────────────────────────────────────────────────────────┘
```

**Key Patterns**:
- **Service Injection**: BaseMCPComponent receives services via DI
- **Structured Output**: All interactions use Pydantic models (MCP 2025-06-18)
- **Progress Reporting**: Long operations (indexing) stream progress via SSE
- **Elicitation**: Human-in-the-loop confirmations for destructive ops
- **Cache Strategy**: SHA256 cache keys, 5-min TTL for graphs/searches

---

## MCP Interactions (29 total)

### Tools (9) - Operations

| Name | Purpose | Type | Elicitation | Status |
|------|---------|------|-------------|--------|
| ✅ `ping` | Test connectivity | Test | No | Story 23.1 |
| ✅ `search_code` | Hybrid code search (lexical+vector+RRF) | Read | No | Story 23.2 |
| ✅ `write_memory` | Create persistent memory | Write | No | Story 23.3 |
| ✅ `update_memory` | Modify existing memory | Write | No | Story 23.3 |
| ✅ `delete_memory` | Delete memory (soft delete) | Write | ⚠️ Yes (permanent delete only) | Story 23.3, 23.11 |
| ✅ `index_project` | Index project directory | Write | ⚠️ Yes (if >100 files) | Story 23.5 |
| ✅ `reindex_file` | Re-index single file | Write | No | Story 23.5 |
| ✅ `clear_cache` | Clear cache layers (L1/L2/all) | Write | ⚠️ Yes | Story 23.6 |
| ✅ `switch_project` | Change active project | Write | ⚠️ Yes (bypass with confirm=True) | Story 23.7, 23.11 |

**Note**: `search_code` implemented as Tool (not Resource) for complex parameter support (filters, pagination). See Story 23.2 ULTRATHINK for rationale.

### Resources (14) - Read Operations

| URI Template | Purpose | Cache TTL | Status |
|--------------|---------|-----------|--------|
| ✅ `health://status` | Server health check | 10s | Story 23.1 |
| ✅ `memories://get/{id}` | Get memory by ID | - | Story 23.3 |
| ✅ `memories://list` | List all memories | 1 min | Story 23.3 |
| ✅ `memories://search/{query}` | Search memories | 5 min | Story 23.3 |
| ✅ `graph://nodes/{chunk_id}` | Get code graph node | 5 min | Story 23.4 |
| ✅ `graph://callers/{name}` | Find function callers | 5 min | Story 23.4 |
| ✅ `graph://callees/{name}` | Find function callees | 5 min | Story 23.4 |
| ✅ `index://status/{repository}` | Indexing status | 1 min | Story 23.5 |
| ✅ `cache://stats` | Cache statistics (L1/L2/cascade) | 10s | Story 23.6 |
| ✅ `analytics://search` | Search analytics (latency/throughput/errors) | 1 min | Story 23.6 |
| ✅ `projects://list` | List all projects | 1 min | Story 23.7 |
| ✅ `config://languages` | Supported languages | - | Story 23.7 |
| ⏳ `stream://progress` | SSE progress stream | - | Story 23.8 |
| ⏳ `stream://logs` | SSE real-time logs | - | Story 23.8 |

### Prompts (6) - User Templates

| Name | Purpose | Parameters | Status |
|------|---------|------------|--------|
| ✅ `analyze_codebase` | Codebase architecture analysis | language, focus | Story 23.10 |
| ✅ `refactor_suggestions` | Code refactoring ideas | focus, severity | Story 23.10 |
| ✅ `find_bugs` | Bug hunting assistance | severity, category | Story 23.10 |
| ✅ `generate_tests` | Test generation template | chunk_id, test_type, coverage_target | Story 23.10 |
| ✅ `explain_code` | Code explanation prompt | chunk_id, level, audience | Story 23.10 |
| ✅ `security_audit` | Security vulnerability scan | scope, compliance | Story 23.10 |

---

## Story Breakdown (3 Phases)

### Phase 1: Foundation & Core Features (8 pts, 16 sub-stories, 30h)

**Story 23.1: Project Structure & FastMCP Setup (3 pts)** ✅ **COMPLETE** (2025-10-27)
- ✅ 23.1.1: Project structure & dependencies (2h) - Package `api/mnemo_mcp/` créé
- ✅ 23.1.2: BaseMCPComponent & base models (2h) - 15+ Pydantic models
- ✅ 23.1.3: FastMCP server initialization (1.5h) - Server running
- ✅ 23.1.4: Lifespan management & service injection (2h) - DB + Redis connected
- ✅ 23.1.5: Test tool + health resource (2h) - `ping` tool + `health://status` resource
- ✅ 23.1.6: Claude Desktop config & first smoke test (1h) - Getting Started guide created

**Deliverables**: 18 files, 17/17 tests passing, ~2000 lines code, ~1500 lines docs
**Time**: 12h actual (10.5h estimated)
**Report**: `EPIC-23_STORY_23.1_COMPLETION_REPORT.md`

**Story 23.2: Code Search Tool (3 pts)** ✅ **COMPLETE** (2025-10-27)
- ✅ 23.2.1: Search Pydantic models (0.5h) - 5 models (CodeSearchQuery, Filters, Result, Metadata, Response)
- ✅ 23.2.2: search_code tool (1h) - Implemented as Tool (not Resource) for complex parameters
- ✅ 23.2.3: Pagination & filters (0.5h) - Offset-based pagination, 6 filter types
- ✅ 23.2.4: Cache integration (1h) - Redis L2 with SHA256 keys, 5-min TTL
- ✅ 23.2.5: Tests (1h) - 8 unit tests, 100% passing (25/25 total)
- ⏳ 23.2.6: MCP Inspector validation - Deferred to manual testing

**Deliverables**: 3 files (~1250 lines), 8 tests passing, search_code tool with filters/pagination/cache
**Time**: 4h actual (12h estimated - 67% improvement)
**Architecture Decision**: Tool (not Resource) - complex parameters don't fit URI templates
**Report**: `EPIC-23_STORY_23.2_COMPLETION_REPORT.md`, `EPIC-23_STORY_23.2_ULTRATHINK.md` (~1400 lines)

**Story 23.3: Memory Tools & Resources (2 pts)**
- 23.3.1: Memories table migration (v7 → v8) (1.5h)
- 23.3.2: Memory Pydantic models (1h)
- 23.3.3: write_memory + update_memory tools (2h)
- 23.3.4: memories://get + memories://list resources (1.5h)
- 23.3.5: memories://search resource (1.5h)
- 23.3.6: delete_memory with elicitation (1.5h)

---

### Phase 2: Advanced Features (9 pts, 18 sub-stories, 32h)

**Story 23.4: Code Graph Resources (3 pts)**
- 23.4.1: Graph Pydantic models (1.5h)
- 23.4.2: graph://nodes resource (2h)
- 23.4.3: graph://callers resource (2h)
- 23.4.4: graph://callees resource (2h)
- 23.4.5: Graph pagination (1.5h)
- 23.4.6: Performance & caching (2h)

**Story 23.5: Project Indexing Tools (2 pts)**
- 23.5.1: index_project tool with elicitation (2h)
- 23.5.2: reindex_file tool (1.5h)
- 23.5.3: index://status resource (1.5h)
- 23.5.4: Indexing progress streaming (2h)

**Story 23.6: Analytics & Observability (2 pts)**
- 23.6.1: clear_cache tool with elicitation (1.5h)
- 23.6.2: cache://stats resource (1.5h)
- 23.6.3: analytics://search resource (EPIC-22) (2h)
- 23.6.4: Real-time stats via SSE (2h)

**Story 23.10: Prompts Library (2 pts)** ✅ **COMPLETE** (2025-10-28)
- ✅ 23.10.1: Core analysis prompts (analyze_codebase, refactor_suggestions)
- ✅ 23.10.2: Test generation prompts (generate_tests)
- ✅ 23.10.3: Code explanation prompts (explain_code)
- ✅ 23.10.4: Security audit prompt (security_audit, find_bugs)

**Deliverables**: 1 file (prompts.py, 520 lines), 6 prompts, server integration, no tests (justified)
**Time**: 2h actual (7h estimated - 71% faster)
**Architecture Decision**: Single file, markdown output, tool/resource references in URI format
**Report**: `EPIC-23_STORY_23.10_COMPLETION_REPORT.md`, `EPIC-23_STORY_23.10_ULTRATHINK.md` (~1400 lines)

---

### Phase 3: Production & Polish (6 pts, 12 sub-stories, 20h)

**Story 23.7: Configuration & Utilities (1 pt)**
- 23.7.1: switch_project + projects://list (2.5h)
- 23.7.2: config://languages resource (1.5h)

**Story 23.8: HTTP Transport Support (2 pts)**
- 23.8.1: HTTP server setup with SSE (2h)
- 23.8.2: OAuth 2.0 + PKCE authentication (3h)
- 23.8.3: CORS configuration (1.5h)
- 23.8.4: API key auth (dev mode) (1.5h)

**Story 23.9: Documentation & Examples (1 pt)**
- 23.9.1: User guide & API reference (3h)
- 23.9.2: Developer guide & architecture (1h)

**Story 23.11: Elicitation Flows (1 pt)** ⭐NEW
- 23.11.1: Elicitation helpers & patterns (2h)
- 23.11.2: Elicitation UX patterns (docs) (1h)

**Story 23.12: MCP Inspector Integration (1 pt)** ⭐NEW
- 23.12.1: Inspector development workflow (1.5h)
- 23.12.2: Inspector test automation (1.5h)

---

## Total Estimation

| Phase | Story Points | Sub-Stories | Time (hours) |
|-------|-------------|-------------|--------------|
| Phase 1: Foundation | 8 pts | 16 | 30h |
| Phase 2: Advanced | 9 pts | 18 | 32h |
| Phase 3: Production | 6 pts | 12 | 20h |
| **TOTAL** | **23 pts** | **46** | **~82h** |

**Timeline**: 10-12 days (assuming 6-8h/day development)

---

## External Dependencies

### Python Packages (pyproject.toml)

```toml
[project.dependencies]
mcp = "1.12.3"              # Official MCP SDK with FastMCP
pydantic = "^2.5.0"         # Structured output (MCP 2025-06-18)
pydantic-settings = "^2.1"  # Configuration management
uvicorn = "^0.25"           # ASGI server (HTTP transport)
sse-starlette = "^1.8"      # Server-Sent Events
pyjwt = "^2.8"              # JWT tokens (OAuth 2.0)
structlog = "^24.1"         # Structured logging

# Existing dependencies
asyncpg = "^0.29"
redis = "^5.0"
# ... (MnemoLite existing deps)
```

### System Requirements

- **PostgreSQL**: 18.x with pgvector extension
- **Redis**: 7.x for L2 cache
- **Python**: 3.11+
- **MCP Inspector**: For development/testing (http://127.0.0.1:6274)

### Database Migrations

**New migration**: `db/migrations/v7_to_v8_memories_table.sql`

```sql
-- Extend memories table (8 cols → 15 cols)
ALTER TABLE memories
  ADD COLUMN memory_type VARCHAR(50) NOT NULL DEFAULT 'note',
  ADD COLUMN author VARCHAR(100),
  ADD COLUMN project_id UUID,
  ADD COLUMN embedding VECTOR(768),
  ADD COLUMN embedding_model VARCHAR(100),
  ADD COLUMN related_chunks UUID[],
  ADD COLUMN resource_links JSONB DEFAULT '[]'::jsonb,  -- MCP 2025-06-18
  ADD COLUMN deleted_at TIMESTAMPTZ;  -- Soft delete

-- Add indexes
CREATE INDEX idx_memories_project_id ON memories(project_id);
CREATE INDEX idx_memories_type ON memories(memory_type);
CREATE INDEX idx_memories_embedding ON memories USING ivfflat (embedding vector_cosine_ops);

-- Add constraint
ALTER TABLE memories
  ADD CONSTRAINT unique_name_per_project UNIQUE (name, project_id);
```

---

## Acceptance Criteria

### Phase 1 🚧 (1/3 stories complete)

- [x] MCP server starts successfully (stdio transport) ✅ Story 23.1
- [x] `ping` tool returns pong ✅ Story 23.1
- [x] Service injection pattern working (DB + Redis) ✅ Story 23.1
- [x] `health://status` resource functional ✅ Story 23.1
- [x] Getting Started documentation created ✅ Story 23.1
- [ ] Registered in Claude Desktop (`~/.config/claude/claude_desktop_config.json`)
- [ ] `code://search` resource finds code chunks (Story 23.2 pending)
- [ ] `write_memory` creates persistent memory in PostgreSQL (Story 23.3 pending)
- [ ] `memories://search` retrieves memories semantically (Story 23.3 pending)
- [ ] All sub-stories validated via MCP Inspector

### Phase 2 ✅ **COMPLETE**

- [x] `graph://nodes` returns code graph with 50+ nodes ✅ Story 23.4
- [x] `graph://callers` finds function callers (min 3 levels deep) ✅ Story 23.4
- [x] `index_project` indexes 1000+ files with progress reporting ✅ Story 23.5
- [x] `cache://stats` shows >80% cache hit rate after warm-up ✅ Story 23.6
- [x] `analytics://search` integrates EPIC-22 metrics ✅ Story 23.6
- [x] All 6 prompts implemented and registered ✅ Story 23.10
- [x] Cache TTL respected (verified via Redis CLI) ✅ Story 23.6
- [ ] All 6 prompts tested in Claude Desktop UI (pending manual validation)

### Phase 3 ✅

- [ ] HTTP transport accessible on `http://localhost:8002`
- [ ] OAuth 2.0 PKCE flow completes successfully
- [ ] CORS allows requests from configured origins
- [ ] API key auth works for dev/test environments
- [ ] User guide covers all 29 MCP interactions
- [ ] Elicitation shown for `delete_memory` (destructive op)
- [ ] MCP Inspector automated tests pass (100% coverage)

---

## Implementation Roadmap

### Week 1: Foundation (Phase 1)

**Day 1-2**: Story 23.1 (Project structure, FastMCP setup) ✅ **COMPLETE** (2025-10-27)
- ✅ Setup `api/mnemo_mcp/` module structure (18 files)
- ✅ Install dependencies (mcp==1.12.3, upgraded pydantic-settings, python-multipart)
- ✅ Create BaseMCPComponent pattern with service injection
- ✅ First smoke test: Server running, 17/17 tests passing
- ✅ Getting Started documentation (~300 lines)
- **Challenges resolved**: Package namespace conflict, dependency versions, Docker networking, FastMCP Context param

**Day 3-4**: Story 23.2 (Code search resources)
- Implement `code://search` resource
- Add pagination + filters
- Cache integration (Redis)
- Test with real codebases (100+ files)

**Day 5**: Story 23.3 (Memory tools)
- Run v7→v8 migration (memories table)
- Implement `write_memory`, `update_memory`, `delete_memory`
- Test elicitation flow for deletion

### Week 2: Advanced Features (Phase 2)

**Day 6-7**: Story 23.4 (Code graph resources)
- Implement `graph://nodes`, `graph://callers`, `graph://callees`
- Add graph caching (SHA256 keys)
- Performance optimization (<200ms cached)

**Day 8**: Story 23.5 (Indexing tools)
- Implement `index_project` with progress streaming
- Add `reindex_file` for incremental updates
- Test with large projects (5000+ files)

**Day 9**: Story 23.6 + 23.10 (Analytics + Prompts) ✅ **COMPLETE** (2025-10-28)
- ✅ Integrated EPIC-22 metrics (`analytics://search`)
- ✅ Created 6 prompt templates (prompts.py, 520 lines)
- ✅ Registered prompts in server.py
- [ ] Verify prompts in Claude Desktop UI (pending manual validation)

### Week 3: Production Polish (Phase 3)

**Day 10**: Story 23.7 + 23.8 (Config + HTTP)
- Implement project switcher (`switch_project`)
- Setup HTTP/SSE transport on port 8002
- Configure OAuth 2.0 + PKCE

**Day 11**: Story 23.9 (Documentation)
- Write user guide (3000 words)
- Document all 29 interactions
- Create examples for common use cases

**Day 12**: Story 23.11 + 23.12 (Elicitation + Inspector)
- Document elicitation patterns
- Setup MCP Inspector workflow
- Create automated integration tests
- **Final validation & production release** 🎉

---

## Technical Decisions

### 1. MCP Spec Version: 2025-06-18 (Latest)

**Justification**: Includes new features:
- **Elicitation**: Human-in-the-loop confirmations
- **Structured Output**: Pydantic models required
- **Resource Links**: Navigation between related resources
- **OAuth 2.0 + PKCE**: Enhanced security

**Trade-off**: Spec 2025-03-26 would work but miss these features.

### 2. FastMCP vs Low-Level MCP SDK

**Choice**: FastMCP (high-level abstraction)

**Justification**:
- Decorator-based API (`@mcp.tool()`, `@mcp.resource()`)
- Built-in Pydantic support
- Easier testing and validation
- Used by Serena (proven in production)

**Trade-off**: Less control over JSON-RPC layer, but acceptable.

### 3. Dual Transport (stdio + HTTP)

**Choice**: Support both transports

**Justification**:
- stdio: Claude Desktop integration (primary use case)
- HTTP/SSE: Web clients, curl testing, CI/CD automation

**Trade-off**: More code, but flexibility for future integrations.

### 4. OAuth 2.0 + PKCE vs API Key

**Choice**: OAuth 2.0 for production, API key for dev

**Justification**:
- PKCE prevents auth code interception (security)
- API key simple for local development

**Implementation**: `auth_mode` config parameter.

### 5. Cache Strategy: SHA256 Keys

**Choice**: Hash query parameters for deterministic cache keys

**Justification**:
- Deterministic (same params = same key)
- Collision-resistant (SHA256)
- Redis-friendly (short keys)

**Example**: `graph:a1b2c3d4e5f6g7h8` for graph query.

---

## Risks & Mitigations

### Risk 1: MCP Spec Changes (Medium)

**Description**: MCP spec may evolve (currently 2025-06-18)

**Impact**: Breaking changes requiring code updates

**Mitigation**:
- Pin `mcp==1.12.3` in pyproject.toml
- Monitor MCP GitHub releases
- Automated tests catch regressions

### Risk 2: Performance with Large Codebases (High)

**Description**: Indexing 10,000+ files may timeout or crash

**Impact**: Poor UX, server crashes

**Mitigation**:
- Progress reporting (ctx.report_progress every 10%)
- Elicitation warning for >10k files
- Batch processing (max 100 files/batch)
- Memory limits (max 1GB per indexing job)

### Risk 3: Cache Invalidation Complexity (Medium)

**Description**: Stale cache after code changes

**Impact**: Wrong search results

**Mitigation**:
- Short TTL (5 min for code, 1 min for index status)
- `clear_cache` tool for manual invalidation
- Cache hit tracking in responses (`cache_hit: true`)

### Risk 4: Multi-Project Context Switching (Low)

**Description**: Session state lost between project switches

**Impact**: User searches wrong project

**Mitigation**:
- `ctx.session.set("current_project_id", ...)` persists per session
- Always include `project_id` in resource links
- Show active project in `projects://list`

---

## Success Metrics

**Phase 1 (Foundation)**:
- ✅ MCP server registered in Claude Desktop
- ✅ 100% of core Tools/Resources functional
- ✅ <100ms latency for search queries (cached)

**Phase 2 (Advanced)**:
- ✅ Graph queries return >50 nodes
- ✅ Indexing completes 1000+ files in <60s
- ✅ Cache hit rate >80% after warm-up

**Phase 3 (Production)**:
- ✅ HTTP transport handles 100 req/s
- ✅ OAuth 2.0 PKCE zero failures in testing
- ✅ Documentation covers 100% of interactions

**User Adoption**:
- 10+ users test with Claude Desktop (internal beta)
- 5+ real-world codebases indexed (Python, JS, Go)
- 0 critical bugs in production (P0/P1)

---

## References

### MCP Specification
- **Latest Spec**: https://spec.modelcontextprotocol.io/2025-06-18/
- **Python SDK**: https://github.com/modelcontextprotocol/python-sdk
- **FastMCP Docs**: https://firecrawl.dev/blog/fastmcp-tutorial

### Serena MCP Reference
- **Codebase**: `/home/giak/Work/MnemoLite/serena-main/`
- **Research**: `api/code_test/docs/serena-mcp-research-report.md`
- **Patterns**: Service injection, Tool registry, Lifespan management

### EPIC-23 Documents
- **Ultrathink**: `99_TEMP/EPIC-23_MCP_INTEGRATION_ULTRATHINK.md`
- **Validation**: `99_TEMP/EPIC-23_MCP_VALIDATION_CORRECTIONS.md`
- **Phase 1**: `99_TEMP/EPIC-23_STORIES_ULTRA_BREAKDOWN.md`
- **Phase 2**: `99_TEMP/EPIC-23_STORIES_PHASE2_COMPLETE.md`
- **Phase 3**: `99_TEMP/EPIC-23_STORIES_PHASE3_COMPLETE.md`

### Related EPICs
- **EPIC-11**: Hybrid code search (HybridCodeSearchService)
- **EPIC-14**: Code graph (CodeGraphService)
- **EPIC-22**: Advanced observability (MetricsCollectorService)

---

## Appendix A: File Structure

**Note**: Package renamed from `api/mcp/` to `api/mnemo_mcp/` to avoid namespace conflict with MCP SDK.

```
api/mnemo_mcp/                 # ✅ Created (Story 23.1)
├── __init__.py                # ✅
├── server.py                  # ✅ FastMCP init, lifespan, CLI entry
├── base.py                    # ✅ BaseMCPComponent, MCPBaseResponse
├── models.py                  # ✅ Shared Pydantic models (15+ models)
├── config.py                  # ✅ MCPConfig (Pydantic Settings)
├── __main__.py                # ✅ CLI entry point
│
├── tools/                     # ✅ Created (Story 23.1) - 8 tools (write operations)
│   ├── __init__.py            # ✅
│   ├── test_tool.py           # ✅ ping tool (Story 23.1)
│   ├── memory_tools.py        # ⏳ write/update/delete_memory (Story 23.3)
│   ├── indexing_tools.py      # ⏳ index_project, reindex_file (Story 23.5)
│   ├── analytics_tools.py     # ⏳ clear_cache (Story 23.6)
│   └── config_tools.py        # ⏳ switch_project (Story 23.7)
│
├── resources/                 # ✅ Created (Story 23.1) - 15 resources (read operations)
│   ├── __init__.py            # ✅
│   ├── health_resource.py     # ✅ health://status (Story 23.1)
│   ├── search_resources.py    # ⏳ code://search, memories://search (Story 23.2)
│   ├── memory_resources.py    # ⏳ memories://get, memories://list (Story 23.3)
│   ├── graph_resources.py     # ⏳ graph://nodes/callers/callees (Story 23.4)
│   ├── indexing_resources.py  # ⏳ index://status (Story 23.5)
│   ├── analytics_resources.py # ⏳ cache://stats, analytics://search (Story 23.6)
│   └── config_resources.py    # ⏳ projects://list, config://languages (Story 23.7)
│
├── prompts.py                 # ✅ Created (Story 23.10) - 6 prompts (user templates)
│                              # ✅ analyze_codebase, refactor_suggestions, find_bugs,
│                              # ✅ generate_tests, explain_code, security_audit
│
└── transport/                 # ✅ Created (Story 23.1) - Transport layers
    ├── __init__.py            # ✅
    ├── stdio_transport.py     # ⏳ Default (Claude Desktop) - Built into server.py
    ├── http_server.py         # ⏳ HTTP/SSE (Web) (Story 23.8)
    └── auth.py                # ⏳ OAuth 2.0, API key (Story 23.8)

tests/mnemo_mcp/               # ✅ Created (Story 23.1)
├── __init__.py                # ✅
├── test_base.py               # ✅ 9 tests (Story 23.1)
├── test_test_tool.py          # ✅ 3 tests (Story 23.1)
├── test_health_resource.py    # ✅ 5 tests (Story 23.1)
├── test_search_resources.py   # ⏳ (Story 23.2)
├── test_memory_tools.py       # ⏳ (Story 23.3)
├── test_graph_resources.py    # ⏳ (Story 23.4)
├── test_indexing_tools.py     # ⏳ (Story 23.5)
├── test_analytics_resources.py # ⏳ (Story 23.6)
├── (no test_prompts.py)       # ✅ Justified - Story 23.10 (text templates, no logic)
└── test_elicitation.py        # ⏳ (Story 23.11)

docs/mcp/                      # ✅ Created (Story 23.1)
├── GETTING_STARTED.md         # ✅ Getting Started guide (~300 lines, Story 23.1)
├── claude_desktop_config.example.json  # ✅ Config template (Story 23.1)
├── USER_GUIDE.md              # ⏳ User documentation (Story 23.9)
├── API_REFERENCE.md           # ⏳ Complete API specs (Story 23.9)
├── ARCHITECTURE.md            # ⏳ Internal architecture (Story 23.9)
├── CONTRIBUTING.md            # ⏳ Developer guide (Story 23.9)
├── TROUBLESHOOTING.md         # ⏳ Common issues (Story 23.9)
├── ELICITATION_PATTERNS.md    # ⏳ UX patterns (Story 23.11)
├── MCP_INSPECTOR_GUIDE.md     # ⏳ Inspector workflow (Story 23.12)
└── EXAMPLES.md                # ⏳ Code examples (Story 23.9)
```

---

## Appendix B: Claude Desktop Configuration

**File**: `~/.config/claude/claude_desktop_config.json`

**Note**: Package renamed from `api.mcp` to `mnemo_mcp` (Story 23.1)

```json
{
  "mcpServers": {
    "mnemolite": {
      "command": "python",
      "args": ["-m", "mnemo_mcp.server"],
      "cwd": "/home/giak/Work/MnemoLite",
      "env": {
        "TEST_DATABASE_URL": "postgresql://user:pass@localhost:5432/mnemolite_test",
        "REDIS_URL": "redis://localhost:6379/0",
        "EMBEDDING_MODE": "mock",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

**Usage in Claude Desktop**:

```
User: Use mnemolite to search for "authentication logic"

Claude: [Automatically calls code://search resource]
Found 12 code chunks related to authentication:

1. api/auth/login.py:45-67 (score: 0.89)
   - JWT token generation
   - Password hashing with bcrypt

2. api/middleware/auth.py:23-45 (score: 0.87)
   - Authentication middleware
   - Token validation

[Continues with results...]

User: Create a memory about this authentication approach

Claude: [Calls write_memory tool]
Created memory "auth-jwt-approach" with decision rationale.
```

---

## Appendix C: Example MCP Inspector Session

1. **Start Inspector**: `mcp-inspector` → http://127.0.0.1:6274
2. **Register MnemoLite**: Add server with command `python -m mnemo_mcp.server` (Note: Package renamed in Story 23.1)
3. **Test Tool**:
   - Select "mnemolite" → "Tools" → "ping"
   - Click "Execute"
   - Response: `{"success": true, "message": "pong", "timestamp": "..."}`
4. **Test Resource**:
   - Select "Resources" → "code://search"
   - Enter query: "function definition"
   - View structured JSON response with code chunks
5. **Test Elicitation**:
   - Select "delete_memory" tool
   - Provide memory_id
   - See confirmation dialog in Inspector UI
6. **Validate Schema**:
   - Inspector shows ✅ green checkmark for valid Pydantic schemas

---

**END OF EPIC-23 README**

**Implementation Status**: 🚧 IN PROGRESS (Started 2025-10-27)

**Completed**:
1. ✅ **Phase 1 COMPLETE** (3 stories, 8 pts, 25h) - Stories 23.1, 23.2, 23.3
   - MCP server operational with DB + Redis
   - Code search tool, memory tools, health resources
   - 200/200 tests passing

2. ✅ **Phase 2 COMPLETE** (4 stories, 9 pts, 19.5h) - Stories 23.4, 23.5, 23.6, 23.10 ⭐
   - Code graph resources (nodes, callers, callees)
   - Project indexing tools (index_project, reindex_file)
   - Analytics & observability (cache stats, search analytics)
   - **Prompts library** (6 prompt templates)
   - 200/200 tests passing (no tests for Story 23.10 - justified)
   - 29% ahead of schedule (44.5h actual vs 62.5h estimated)

**Next Steps (Phase 3)**:
1. Story 23.7: Configuration & Utilities (1 pt, ~4h)
   - `switch_project` tool + `projects://list` resource
   - `config://languages` resource
2. Story 23.8: HTTP Transport Support (2 pts, ~8h)
   - HTTP/SSE server setup
   - OAuth 2.0 + PKCE authentication
3. Story 23.9: Documentation & Examples (1 pt, ~4h)
4. Story 23.11: Elicitation Flows (1 pt, ~3h)
5. Story 23.12: MCP Inspector Integration (1 pt, ~3h)

**Questions?** See `docs/mcp/GETTING_STARTED.md` or `EPIC-23_PROGRESS_TRACKER.md`.
