# Serena Evolution - Documentation Hub

**Version**: 3.0
**Last Updated**: 2025-10-28
**Status**: Production Readiness Phase (v3.1) - EPIC-22 (53%) + EPIC-23 (100%) + EPIC-24 (100%)
**Method**: [Screaming Document Architecture](#-screaming-architecture-method)

---

## 🎯 Quick Navigation

| I want to... | Go to... |
|--------------|----------|
| **See current status & decisions** | [`00_CONTROL/CONTROL_MISSION_CONTROL.md`](00_CONTROL/CONTROL_MISSION_CONTROL.md) |
| **Find all documents** | [`00_CONTROL/CONTROL_DOCUMENT_INDEX.md`](00_CONTROL/CONTROL_DOCUMENT_INDEX.md) |
| **Read architecture decisions** | [`01_ARCHITECTURE_DECISIONS/`](01_ARCHITECTURE_DECISIONS/) |
| **See active research** | [`02_RESEARCH/`](02_RESEARCH/) |
| **Track EPICs** | [`03_EPICS/`](03_EPICS/) |
| **View historical research** | [`88_ARCHIVE/`](88_ARCHIVE/) |
| **Quick scratch notes** | [`99_TEMP/`](99_TEMP/) |

---

## 📂 Directory Structure

```
serena-evolution/
├── 00_CONTROL/              # 🎛️ Dashboards & Indexes
│   ├── CONTROL_MISSION_CONTROL.md    (Central dashboard - SSOT)
│   └── CONTROL_DOCUMENT_INDEX.md     (All documents indexed)
│
├── 01_ARCHITECTURE_DECISIONS/  # ✅ ADRs (Permanent)
│   ├── ADR-001_cache_strategy.md
│   ├── ADR-002_lsp_analysis_only.md
│   └── ADR-003_breaking_changes_approach.md
│
├── 02_RESEARCH/             # 🔬 Active Research (Temporary)
│   └── RESEARCH_2025-01-15_serena_deep_dive.md
│
├── 03_EPICS/                # 📦 Project Tracking (Permanent)
│   ├── EPIC-10_PERFORMANCE_CACHING.md (✅ Complete - 36 pts)
│   ├── EPIC-11_SYMBOL_ENHANCEMENT.md (✅ Complete - 13 pts)
│   ├── EPIC-12_ROBUSTNESS.md (✅ Complete - 23 pts)
│   ├── EPIC-13_LSP_INTEGRATION.md (✅ Complete - 21 pts)
│   ├── EPIC-14_LSP_UI_ENHANCEMENTS.md (✅ Complete - 25 pts)
│   ├── EPIC-18_TYPESCRIPT_LSP_STABILITY.md (✅ Complete - 8 pts)
│   ├── EPIC-19_* (✅ Complete - Embeddings)
│   ├── EPIC-22_README.md (🟡 In Progress - 10/19 pts)
│   ├── EPIC-23_README.md (✅ Complete - 23/23 pts - MCP Integration)
│   └── EPIC-24_README.md (✅ Complete - Auto-Save Conversations)
│
├── 88_ARCHIVE/              # 📚 Historical (Read-only)
│   ├── 2025-01-19_deep_challenge/  (Deep challenge research)
│   └── 2025-01-15_apex_validation/ (APEX consolidation)
│
├── 99_TEMP/                 # 🗑️ Scratch (Volatile)
│   └── (Empty - for quick notes)
│
└── 99_THINKING_WORKSPACE/   # 💭 Brainstorms
    └── BRAINSTORM_document_lifecycle_method.md
```

---

## 📖 Understanding the Structure

### 00_CONTROL: Your Starting Point

**Always start here!**
- `CONTROL_MISSION_CONTROL.md` = **Single Source of Truth** (current status, decisions, next steps)
- `CONTROL_DOCUMENT_INDEX.md` = Complete catalog of all documents

### 01_ARCHITECTURE_DECISIONS: The Truth

**Permanent ADRs** - These are the official architectural decisions.
- Always up-to-date
- Living documents (updated as decisions evolve)
- **Source of truth** for all architectural questions

### 02_RESEARCH: Work in Progress

**Temporary research files** - Active explorations and deep dives.
- Named with date: `RESEARCH_YYYY-MM-DD_topic.md`
- **Lifecycle**: When research → decision, file moves to `88_ARCHIVE/`
- Don't trust old RESEARCH files - check CONTROL_MISSION_CONTROL for status

### 03_EPICS: Project Management

**Epic tracking** - Long-term features and initiatives.
- Permanent (but can be archived when complete)
- Linked to ADRs when architectural decisions are needed

### 88_ARCHIVE: Historical Record

**Read-only historical reference** - Completed research, superseded documents.
- Organized by date: `YYYY-MM-DD_topic/`
- Each archive has a README explaining context & findings
- **Don't modify** - historical record only

**Current archives**:
- `2025-01-19_deep_challenge/` - Deep challenge des ADRs (2800 lines, integrated)
- `2025-01-15_apex_validation/` - APEX consolidation 2024 (prep work)

### 99_TEMP: Disposable Workspace

**Volatile scratch space** - Quick notes, brainstorms, temporary thinking.
- Files can be deleted anytime (cleanup: 7 days)
- No structure required
- Don't put important content here!

---

## 🏗️ Screaming Architecture Method

### Principle: **Filenames Scream Their Purpose**

Every file uses a **type prefix** that tells you its lifecycle:

| Prefix | Meaning | Lifecycle | Example |
|--------|---------|-----------|---------|
| `CONTROL_` | Dashboard/index | Permanent (always updated) | `CONTROL_MISSION_CONTROL.md` |
| `DECISION_` | ADR | Permanent (living doc) | `DECISION_ADR-001_cache.md` |
| `RESEARCH_` | Deep analysis | Temporary (archive on decision) | `RESEARCH_2025-01-20_benchmarks.md` |
| `DRAFT_` | Work in progress | Temporary (promote or archive) | `DRAFT_2025-01-20_analysis.md` |
| `TEMP_` | Scratch notes | Volatile (delete after session) | `TEMP_2025-01-20_brainstorm.md` |
| `ARCHIVE_` | Historical | Read-only (historical record) | `ARCHIVE_2025-01-19_SYNTHESIS.md` |

### Workflow: From Idea to Decision

```
💭 TEMP_notes.md
    ↓ (worth pursuing?)
📝 DRAFT_analysis.md
    ↓ (structure thinking)
🔬 RESEARCH_deep_dive.md
    ↓ (decision ready?)
✅ Update ADR-xxx.md
    ↓ (archive research)
📚 ARCHIVE_research/ (done!)
```

### Rules to Follow

1. **Single Source of Truth**: One ADR per topic
2. **Date all temporary files**: `YYYY-MM-DD` format
3. **Archive on decision**: RESEARCH → DECISION = archive immediately
4. **Update control**: Always update CONTROL_MISSION_CONTROL on ADR changes
5. **No orphans**: Every doc has clear relationships (frontmatter)

---

## 🚀 Common Workflows

### Starting New Research

```bash
# 1. Quick notes first
touch 99_TEMP/TEMP_$(date +%Y-%m-%d)_my_topic.md

# 2. Worth it? Promote to research
mv 99_TEMP/TEMP_*_my_topic.md \
   02_RESEARCH/RESEARCH_$(date +%Y-%m-%d)_my_topic.md

# 3. Add YAML frontmatter (type, status, created, etc.)
```

### Making an Architectural Decision

```bash
# 1. Complete your RESEARCH_* analysis
# 2. Update the relevant ADR in 01_ARCHITECTURE_DECISIONS/
# 3. Archive the research:
mkdir -p 88_ARCHIVE/$(date +%Y-%m-%d)_topic_name
mv 02_RESEARCH/RESEARCH_*_topic* 88_ARCHIVE/$(date +%Y-%m-%d)_topic_name/
# Add ARCHIVE_ prefix to filenames

# 4. Create archive README
# 5. Update 00_CONTROL/CONTROL_MISSION_CONTROL.md
# 6. Update 00_CONTROL/CONTROL_DOCUMENT_INDEX.md
```

### Finding Information

1. **Start with MISSION_CONTROL** (`00_CONTROL/CONTROL_MISSION_CONTROL.md`)
2. **Check DOCUMENT_INDEX** for full catalog
3. **Read relevant ADR** for architectural decisions
4. **Check ARCHIVE** for historical context

---

## 📊 Current Status (2025-10-27)

**Documents**:
- Control: 2 (dashboards)
- Decisions: 3 ADRs (source of truth)
- Research: 1 active (serena deep dive)
- EPICs: 9 (4 complete Serena v3.0 + 2 in progress v3.1)
- Archived: 6+ files (~2800+ lines)

**Recent Activity**:
- ✅ Serena Evolution v3.0 COMPLETE (2025-10-23) - EPIC-10/11/12/13/14/18 (126 pts)
- 🟡 EPIC-22 Phase 2 (2025-10-24) - Observability 53% complete (10/19 pts)
- 🚧 EPIC-23 Story 23.1 (2025-10-27) - MCP Server Foundation complete (3/23 pts)
- 🟢 All ADRs current and validated

**Key Milestones** (October 2025):
1. **Performance** (EPIC-10): 100× faster re-indexing with L1/L2/L3 cache ✅
2. **LSP Integration** (EPIC-13/14): Type information complete, UI enhanced ✅
3. **Observability** (EPIC-22): Unified monitoring dashboard, real-time logs 🟡
4. **MCP Integration** (EPIC-23): FastMCP server operational, Phase 1 started 🚧

---

## 💡 Pro Tips

1. **Always check MISSION_CONTROL first** - it's always current
2. **Don't trust old RESEARCH files** - check their status in INDEX
3. **ARCHIVE is read-only** - historical reference, don't modify
4. **Use TEMP for quick thinking** - don't worry about structure
5. **Date all temporary files** - makes lifecycle management easy

---

## 🆘 Need Help?

- **Lost?** → Start at `00_CONTROL/CONTROL_MISSION_CONTROL.md`
- **Can't find a document?** → Check `00_CONTROL/CONTROL_DOCUMENT_INDEX.md`
- **Unsure about file lifecycle?** → See [Screaming Architecture Method](#-screaming-architecture-method)
- **Want to understand the deep challenge?** → Read `88_ARCHIVE/2025-01-19_deep_challenge/README.md`

---

## 📚 Further Reading

- **Methodology**: `99_THINKING_WORKSPACE/BRAINSTORM_document_lifecycle_method.md` (full methodology explanation)
- **Deep Challenge Results**: `88_ARCHIVE/2025-01-19_deep_challenge/README.md`
- **Document Index**: `00_CONTROL/CONTROL_DOCUMENT_INDEX.md` (all files cataloged)

---

**Maintained By**: Human + AI (Claude)
**Method**: Screaming Document Architecture
**Version**: 2.0 (2025-01-20 reorganization)
