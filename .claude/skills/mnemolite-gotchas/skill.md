---
name: mnemolite-gotchas
version: 2.0.0
category: debugging
auto_invoke:
  - error
  - fail
  - debug
  - gotcha
  - slow
  - crash
  - hang
priority: high
metadata:
  created: 2025-10-21
  updated: 2025-10-21
  purpose: MnemoLite-specific gotchas and pitfalls catalog
  structure: progressive_disclosure
  estimated_size_index: 150 lines
  estimated_size_full: 950 lines
  token_cost_index: ~3750 tokens
  token_cost_full: ~23750 tokens
  domains: 8
tags:
  - gotchas
  - debugging
  - troubleshooting
  - critical
---

# MnemoLite Gotchas & Critical Patterns

**Version**: 2.0.0 (Progressive Disclosure Structure)
**Category**: Gotchas, Debugging, Patterns
**Auto-invoke**: error, fail, debug, gotcha, slow, crash, hang

---

## Purpose

Comprehensive catalog of MnemoLite-specific gotchas, pitfalls, critical patterns, and debugging knowledge. This skill prevents common errors and provides quick troubleshooting guidance.

**Structure**: This skill uses progressive disclosure. The index (this file) provides quick reference and pointers to detailed domain files loaded on-demand.

---

## When to Use This Skill

Use this skill when:
- Encountering unexpected errors or failures
- Debugging code behavior
- Implementing new features (check for known pitfalls)
- Code review (verify patterns followed)
- Onboarding new developers

**Problem solved**: Prevents repeating past mistakes, accelerates debugging

---

## Quick Reference by Symptom

| Symptom | Likely Cause | Domain | Quick Fix |
|---------|--------------|--------|-----------|
| Tests pollute dev DB | CRITICAL-01 | @domains/critical.md | Set TEST_DATABASE_URL, `make db-test-reset` |
| App hangs on DB call | CRITICAL-02 | @domains/critical.md | Convert to async/await |
| Type checker errors | CRITICAL-03 | @domains/critical.md | Implement protocol |
| Slow JSONB queries | CRITICAL-04 | @domains/critical.md | Recreate index with jsonb_path_ops |
| Tests take 30s+ | CRITICAL-05 | @domains/critical.md | Set EMBEDDING_MODE=mock |
| Crash when Redis down | CRITICAL-06 | @domains/critical.md | Add graceful fallback |
| QueuePool limit exceeded | CRITICAL-07 | @domains/critical.md | Use `async with` for connections |
| Column does not exist | DB-04 | @domains/database.md | Check exact column names |
| Migration order issues | DB-05 | @domains/database.md | Apply migrations sequentially |
| Symbol paths backwards | CODE-03 | @domains/code-intel.md | Set reverse=True |
| Graph polluted with builtins | CODE-05 | @domains/code-intel.md | Filter PYTHON_BUILTINS |
| HTMX doesn't update | UI-02 | @domains/ui.md | Match hx-target to element ID |
| Git command hangs | GIT-02 | @domains/workflow.md | Remove -i flag |
| Vector query slow | PERF-03 | @domains/performance.md | Add LIMIT clause |

---

## Gotchas by Domain

### 🔴 Critical Gotchas (7 gotchas - MUST NEVER VIOLATE)

**File**: @domains/critical.md

These gotchas break code if violated. Always check before implementing features.

1. **CRITICAL-01**: Test Database Configuration - Separate TEST_DATABASE_URL required
2. **CRITICAL-02**: Async/Await for All DB Operations - ALL db calls must be awaited
3. **CRITICAL-03**: Protocol Implementation Required - DIP enforcement
4. **CRITICAL-04**: JSONB Operator Choice - Use jsonb_path_ops for @>
5. **CRITICAL-05**: Embedding Mode for Tests - EMBEDDING_MODE=mock required
6. **CRITICAL-06**: Cache Graceful Degradation - L1 → L2 → L3 cascade
7. **CRITICAL-07**: Connection Pool Limits - Respect 20+10 pool limit

**When to load**: Building features, debugging crashes, code review

---

### 🟡 Database Gotchas (5 gotchas)

**File**: @domains/database.md

Database-specific patterns, schema, migrations, and optimization.

1. **DB-01**: Partitioning Currently Disabled - Enable at 500k+ events
2. **DB-02**: Vector Index Tuning - m/ef_construction trade-offs
3. **DB-03**: SQL Complexity Calculation - Cast order for nested JSONB
4. **DB-04**: Column Name Exactness - properties NOT props, relation_type NOT relationship
5. **DB-05**: Migration Sequence - Apply in order: v2→v3→v4→v5

**When to load**: Working with PostgreSQL, migrations, database performance

---

### 🟡 Testing Gotchas (3 gotchas)

**File**: @domains/testing.md

Testing patterns, fixtures, and test configuration.

1. **TEST-01**: AsyncClient Configuration - Use ASGITransport(app)
2. **TEST-02**: Fixture Scope - Database fixtures should be function scope
3. **TEST-03**: Test Execution Order - Tests must pass in ANY order

**When to load**: Writing tests, debugging test failures, configuring test environment

---

### 🟡 Architecture Gotchas (3 gotchas)

**File**: @domains/architecture.md

Architectural patterns, DIP principles, and code organization.

1. **ARCH-01**: EXTEND > REBUILD Principle - Copy existing patterns (~10× faster)
2. **ARCH-02**: Service Method Naming - Match protocol method names exactly
3. **ARCH-03**: Repository Layer Boundaries - Use SQLAlchemy Core (NOT ORM)

**When to load**: Building new features, refactoring, ensuring pattern consistency

---

### 🟡 Code Intelligence Gotchas (5 gotchas)

**File**: @domains/code-intel.md

Code indexing, embeddings, symbol paths, and graph construction.

1. **CODE-01**: Embedding Storage Pattern - Store in dict BEFORE CodeChunkCreate
2. **CODE-02**: Dual Embedding Domain - Use EmbeddingDomain.HYBRID for code
3. **CODE-03**: Symbol Path Parent Context - reverse=True CRITICAL
4. **CODE-04**: Strict Containment Bounds - Use < and > (not ≤ and ≥)
5. **CODE-05**: Graph Builtin Filtering - Filter Python builtins

**When to load**: Working with code chunking, embeddings, dependency graphs

---

### 🟡 Git & Workflow Gotchas (3 gotchas)

**File**: @domains/workflow.md

Git patterns, commit conventions, and workflow.

1. **GIT-01**: Commit Message Pattern for EPICs - <type>(EPIC-XX): description
2. **GIT-02**: Interactive Commands Not Supported - Never use -i flag
3. **GIT-03**: Empty Commits - Don't create empty commits

**When to load**: Creating commits, managing branches, following EPIC workflow

---

### 🟡 Performance Gotchas (3 gotchas)

**File**: @domains/performance.md

Performance tuning, caching, and optimization.

1. **PERF-01**: Rollback Safety - ./apply_optimizations.sh rollback recovers in ~10s
2. **PERF-02**: Cache Hit Rate Monitoring - Target 80%+ hit rate
3. **PERF-03**: Vector Query Limits - ALWAYS use LIMIT with vector queries

**When to load**: Optimizing queries, tuning cache, debugging performance

---

### 🟡 UI Gotchas (3 gotchas)

**File**: @domains/ui.md

UI patterns, HTMX, templates, and frontend.

1. **UI-01**: Template Inheritance Pattern - base.html → page.html → partials/
2. **UI-02**: HTMX Partial Targets - Match hx-target to element ID
3. **UI-03**: Cytoscape.js Initialization - Wait for DOMContentLoaded

**When to load**: Building UI features, debugging HTMX, working with templates

---

### 🟡 Docker & Environment Gotchas (3 gotchas)

**File**: @domains/docker.md

Docker configuration, environment variables, and deployment.

1. **DOCKER-01**: Volume Mounting for Live Reload - Mount api/ AND tests/
2. **DOCKER-02**: Redis Memory Limit - 2GB max with LRU eviction
3. **DOCKER-03**: API Port Mapping - 8001:8000 (host:container)

**When to load**: Configuring Docker, debugging containers, managing environments

---

## How to Use Progressive Disclosure

**Level 1** (This index): Quick reference, symptom table, domain overview (~150 lines, ~3750 tokens)

**Level 2** (Domain files): Load specific domain when needed:
- Critical issues → @domains/critical.md
- Database work → @domains/database.md
- Testing → @domains/testing.md
- Architecture → @domains/architecture.md
- Code intelligence → @domains/code-intel.md
- Git/workflow → @domains/workflow.md
- Performance → @domains/performance.md
- UI work → @domains/ui.md
- Docker/env → @domains/docker.md

**Token savings**:
- Index only: ~3750 tokens (vs ~23750 for full monolithic)
- Index + 1 domain: ~6250 tokens (vs ~23750)
- **Savings**: 71-84% when not loading all domains

---

## Related Skills

- **epic-workflow**: EPIC implementation patterns, completion reports
- **document-lifecycle**: Document lifecycle (TEMP→DECISION→ARCHIVE)
- **mnemolite-testing**: Test patterns (references TEST-01 to TEST-03)
- **mnemolite-database**: Database patterns (references DB-01 to DB-05)
- **mnemolite-architecture**: Architecture principles (references ARCH-01 to ARCH-03)
- **mnemolite-code-intel**: Code intelligence patterns (references CODE-01 to CODE-05)
- **mnemolite-ui**: UI patterns (references UI-01 to UI-03)

---

## Version History

- **v2.0.0** (2025-10-21): Progressive disclosure structure, 8 domain files
- **v1.0** (2025-10-21): Initial skill creation, monolithic (920 lines, 31 gotchas)

---

**Total Gotchas**: 31 (7 Critical + 24 domain-specific)
**Structure**: Progressive disclosure (index + 8 domain files)
**Auto-invoke keywords**: error, fail, debug, gotcha, slow, crash, hang
**Maintained by**: Human + AI collaboration
