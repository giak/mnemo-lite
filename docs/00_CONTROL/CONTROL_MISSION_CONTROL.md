---
type: CONTROL
lifecycle: permanent
created: 2025-11-13
updated: 2025-11-13
status: active
contributors: [Human, Claude]
---

# 🎯 MnemoLite Mission Control

**Last Updated**: 2025-11-13
**Project Status**: Active Development (v3.1.0-dev)
**Documentation Status**: ✅ Reorganized with Lifecycle Structure

---

## 📊 Project Overview

**MnemoLite v3.1.0-dev** is a PostgreSQL-native cognitive memory + code intelligence system designed for AI agents and Claude Desktop integration via MCP.

### Core Capabilities
- 🧠 **Agent Memory**: Conversation persistence, semantic search, time-aware storage
- 💻 **Code Intelligence**: AST-based indexing, dependency graphs, hybrid search
- 🔌 **MCP Integration**: 23 tools + resources for Claude Desktop
- ⚡ **Performance**: <10ms cached queries, 100% test coverage

---

## 🚀 Current Status (2025-11-13)

### ✅ Recently Completed

| Item | Date | Status |
|------|------|--------|
| **EPIC-29**: Barrel/Config Indexing | 2025-11-01 | ✅ Complete |
| **EPIC-27**: TypeScript Metadata Phase 1 | 2025-11-01 | ✅ Complete |
| **EPIC-26**: Parallel Indexing Implementation | 2025-11-01 | ✅ Complete |
| **EPIC-24**: Auto-Save Conversations | 2025-11-12 | ✅ Complete (Hooks-based) |
| **PostgreSQL 18 Migration** | 2025-10-15 | ✅ Complete |
| **Documentation Lifecycle Reorganization** | 2025-11-13 | ✅ Complete |

### 🚧 In Progress

| Item | Status | Next Steps |
|------|--------|------------|
| **Auto-Save Reliability** | 🔧 Monitoring | Daemon disabled, hooks active |
| **MCP Phase 2** | 🚧 Partial | Observability, security (deferred) |
| **UI Modernization (EPIC-21)** | ⏸️ Paused | Resume after core stability |

### 📅 Upcoming

- **Performance Optimization**: Query caching improvements
- **Memory Management**: L1/L2 cache tuning
- **Graph Visualization**: Enhanced dependency views
- **TypeScript LSP Phase 2**: Advanced type inference

---

## 📂 Documentation Structure

### 00_CONTROL (Dashboards)
- `CONTROL_MISSION_CONTROL.md` - **This file** (Project dashboard)
- `CONTROL_DOCUMENT_INDEX.md` - Complete document catalog
- `CONTROL_test_inventory.md` - Test inventory (359 tests passing)

### 01_DECISIONS (Architecture Decision Records)
**8 Active Decisions**

| Decision | Status | Updated |
|----------|--------|---------|
| `DECISION_api_specification.md` | Active | 2025-10-20 |
| `DECISION_database_schema.md` | Active | 2025-10-17 |
| `DECISION_docker_setup.md` | Active | 2025-10-17 |
| `DECISION_architecture_diagrams.md` | Active | 2025-05-06 |
| `DECISION_ui_architecture.md` | Active | 2025-10-13 |
| `DECISION_ui_design_system.md` | Active | 2025-10-14 |
| `DECISION_document_architecture.md` | Active | 2025-10-17 |
| `DECISION_centralized-hooks.md` | Active | 2025-11-12 |

### 02_RESEARCH (Active Research)
**0 Active Research** (All completed research archived)

### 88_ARCHIVE (Historical)
**7 Archive Collections**

| Archive | Date | Content |
|---------|------|---------|
| `2025-10_obsolete_v2_docs/` | 2025-11-13 | Obsolete v2.0.0 documentation |
| `2025-10_docker_analysis/` | 2025-11-13 | Docker optimization research |
| `2025-10_serena_analysis/` | 2025-11-13 | Serena comparison analysis |
| `2025-10_analysis/` | 2025-11-13 | General deep analyses |
| `2025-10_validation/` | 2025-11-13 | Validation reports |
| `2025-10_foundation/` | 2025-11-13 | Project/product foundation docs |
| `backups/` | 2025-11-13 | Cleanup operation backups |

### 99_TEMP (Volatile Scratch)
**1 Active Status** - `TEMP_2025-11-05_status.md`

### agile/serena-evolution/
**Active EPIC Tracking** - Follows full lifecycle structure
- 00_CONTROL: Mission control, document index
- 01_ARCHITECTURE_DECISIONS: 3 ADRs (cache, LSP, breaking changes)
- 02_RESEARCH: 3 active research documents
- 03_EPICS: 212 EPIC files (stories, analyses, completion reports)
- 88_ARCHIVE: 5 archive collections (pre-v2.0 legacy, EPIC-20, EPIC-21, EPIC-24, apex validation)
- 99_DRAFTS: WIP drafts, POC tracking

### plans/
**29 Implementation Plans** (2025-11-01 to 2025-11-13)
- Latest: `2025-11-13-cleanup-dual-autosave-design.md`
- Format: `YYYY-MM-DD-description.md` (all dated)

---

## 🏗️ Architecture Highlights

### Technology Stack
- **Database**: PostgreSQL 18 + pgvector 0.8.1 + pg_trgm + pg_partman
- **API**: FastAPI + AsyncPG (Python 3.12+)
- **Cache**: Redis 7-alpine (L2 cache, Redis Streams for queue)
- **Worker**: Async Python worker for conversation processing
- **Observability**: OpenObserve (logs, metrics, traces)
- **UI**: HTMX 2.0 + SCADA industrial design

### Key Architectural Decisions

**ADR-001: Cache Strategy (Redis Standard)**
- Decision: Use Redis Standard over Dragonfly/Valkey/KeyDB
- Rationale: Pérennité > Performance (proven stability, wide adoption)
- Impact: Simplified ops, predictable performance
- Status: Active, validated

**ADR-002: LSP Analysis-Only**
- Decision: LSP metadata extraction without execution analysis
- Rationale: Security (no code execution), simplicity, performance
- Impact: Fast, safe, sufficient metadata for most use cases
- Status: Active

**ADR-003: Breaking Changes Approach**
- Decision: Pragmatic breaking changes with clear migration paths
- Rationale: Move fast, document migrations, keep backward compat where cheap
- Impact: Faster development, clear upgrade guides
- Status: Active

**Auto-Save Architecture (2025-11-12)**
- Decision: Hooks-based system (primary), daemon disabled by default
- Rationale: Single active pathway, no duplications, cleaner logs
- Impact: Simplified architecture, improved reliability
- Status: Active, validated

---

## 📈 Metrics & Health

### System Performance
- **API Response Time**: <10ms (cached), <100ms (uncached)
- **Indexing Speed**: <100ms per file (7-step pipeline)
- **Graph Traversal**: 0.155ms for 3-hop recursive CTE (129× faster than target)
- **Test Coverage**: 100% (359/359 tests passing)
- **Cache Hit Rate**: 80%+ (L1 + L2)

### Database
- **PostgreSQL**: 18.0 (Debian 18.0-1.pgdg12+3)
- **pgvector**: 0.8.1 (HNSW index)
- **Embeddings**: 768D (nomic-embed-text-v1.5, jina-embeddings-v2-base-code)
- **Indexes**: 23 optimized indexes (HNSW, GIN, B-tree)

### MCP Integration
- **Tools**: 23 tools (search, memory, graph, projects, indexing)
- **Resources**: 14 resources (memories, graph, projects)
- **Performance**: <10ms cached, graceful degradation
- **Stability**: 149/149 tests passing (100%)

---

## 🔗 Quick Links

### Getting Started
- `README.md` - Full project documentation (v3.1.0-dev)
- `QUICKSTART.md` - 5-minute setup guide
- `SETUP.md` - Project setup for new projects
- `CLAUDE_CODE_INTEGRATION.md` - Claude Code + MCP integration guide
- `CONTRIBUTING.md` - Contribution guidelines

### Key Configuration
- `.env` - Environment variables (EMBEDDING_MODE, ENABLE_AUTO_IMPORT)
- `docker-compose.yml` - Docker orchestration (5 services)
- `CLAUDE.md` - AI agent instructions (DSL v4.2.0)

### Development
- `docs/plans/` - Implementation plans (dated)
- `docs/debugging/` - Debugging reports
- `docs/agile/serena-evolution/03_EPICS/` - EPIC tracking

---

## 🛠️ Maintenance Tasks

### Weekly
- [ ] Review `99_TEMP/` files (delete >7 days old)
- [ ] Check `02_RESEARCH/DRAFT_*` (archive or promote >30 days)
- [ ] Update this dashboard with recent completions
- [ ] Review performance metrics (health endpoints)

### Monthly
- [ ] Archive completed `02_RESEARCH/RESEARCH_*` files
- [ ] Regenerate `CONTROL_DOCUMENT_INDEX.md`
- [ ] Review ADRs for obsolescence
- [ ] Clean up old backups (>3 months)

### Ad-Hoc
- [ ] Update ADRs when architectural decisions change
- [ ] Create archive READMEs when moving research to 88_ARCHIVE
- [ ] Update version in README.md when releasing

---

## 📝 Recent Changes

### 2025-11-13: Documentation Lifecycle Reorganization
- ✅ Implemented document-lifecycle skill structure
- ✅ Created 00_CONTROL, 01_DECISIONS, 02_RESEARCH, 88_ARCHIVE, 99_TEMP directories
- ✅ Moved 23 root docs/ files to appropriate categories with prefixes
- ✅ Archived obsolete v2.0.0 documentation
- ✅ Removed api/code_test/ (freed 80MB disk space)
- ✅ Integrated docs/agile/, docs/architecture/ into lifecycle structure
- ✅ Created archive READMEs for 7 collections

### 2025-11-12: Auto-Save Reliability Fixes + Dual System Cleanup
- ✅ Fixed SQL INTERVAL syntax in monitoring_alert_service
- ✅ Fixed project name detection for Docker container environment
- ✅ Migrated 997 conversations to correct projects (109 unique after dedup)
- ✅ Disabled daemon by default (ENABLE_AUTO_IMPORT=false)
- ✅ Simplified healthcheck (removed daemon-specific check)

### 2025-11-01: Multiple EPIC Completions
- ✅ EPIC-29: Barrel and config indexing validation
- ✅ EPIC-27 Phase 1: TypeScript metadata extraction improvements
- ✅ EPIC-26: Parallel indexing implementation

---

## 🎯 Strategic Priorities

### Short-Term (Next 2 weeks)
1. **Stability**: Monitor auto-save hooks, ensure zero data loss
2. **Performance**: Tune L1/L2 cache hit rates
3. **Documentation**: Keep Mission Control updated

### Medium-Term (Next month)
1. **UI Modernization**: Resume EPIC-21 (Vue 3 + Composition API)
2. **Memory Optimization**: Implement memory tiering (hot/warm)
3. **Graph Enhancements**: Improve dependency visualization

### Long-Term (Next quarter)
1. **Multi-Repository Support**: Index multiple projects simultaneously
2. **Advanced Search**: Implement filters (complexity, language, date ranges)
3. **API v2**: Breaking changes with migration guide (if needed)

---

## 📞 Contact & Resources

- **Repository**: [MnemoLite GitHub](https://github.com/giak/MnemoLite)
- **License**: MIT
- **Python Version**: 3.12+
- **PostgreSQL Version**: 18+

---

**Next Review**: 2025-11-20
**Maintained By**: Human + Claude
**Document Status**: Living document (update weekly)
