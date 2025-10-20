# 📇 Document Index - Serena Evolution

**Last Updated**: 2025-01-20
**Total Documents**: 16
**Method**: [Screaming Document Architecture](#method)

---

## 📊 Overview by Status

| Status | Count | Location | Purpose |
|--------|-------|----------|---------|
| **Control** | 2 | `00_CONTROL/` | Dashboards, indexes (always current) |
| **Decision** | 3 | `01_ARCHITECTURE_DECISIONS/` | Permanent ADRs (source of truth) |
| **Research** | 1 | `02_RESEARCH/` | Active analysis (work in progress) |
| **Epic** | 4 | `03_EPICS/` | Project tracking (permanent) |
| **Archived** | 6 | `88_ARCHIVE/` | Historical reference (read-only) |
| **Temp** | 0 | `99_TEMP/` | Scratch notes (volatile) |

---

## 🎯 00_CONTROL: Dashboards

| File | Purpose | Status | Last Updated |
|------|---------|--------|--------------|
| `CONTROL_MISSION_CONTROL.md` | Central dashboard (SSOT) | 🟢 Active | 2025-01-19 |
| `CONTROL_DOCUMENT_INDEX.md` | This file | 🟢 Active | 2025-01-20 |

---

## ✅ 01_ARCHITECTURE_DECISIONS: ADRs (Source of Truth)

| File | Topic | Status | Last Updated | Version |
|------|-------|--------|--------------|---------|
| `ADR-001_cache_strategy.md` | Cache Strategy | 🟢 Active | 2025-01-19 | v2.0 |
| `ADR-002_lsp_analysis_only.md` | LSP Analysis | 🟢 Active | 2025-01-18 | v1.0 |
| `ADR-003_breaking_changes_approach.md` | Breaking Changes | 🟢 Active | 2025-01-17 | v1.0 |

**Changes from Deep Challenge (2025-01-19)**:
- ADR-001: Updated with Redis Standard recommendation (pérennité priority)
- ADR-002: Noted basedpyright as primary LSP
- ADR-003: Validated, no changes needed

---

## 🔬 02_RESEARCH: Active Analysis

| File | Topic | Created | Status | Feeds Into |
|------|-------|---------|--------|------------|
| `RESEARCH_2025-01-15_serena_deep_dive.md` | Serena deep dive | 2025-01-15 | 🟡 Reference | Background context |
| `RESEARCH_2025-01-20_POC-01_redis_integration.md` | POC #1 Redis Integration | 2025-01-20 | 🟢 Active | ADR-001_cache_strategy.md |

**Note**: Research files are temporary. When integrated into ADRs → archive to `88_ARCHIVE/`

---

## 📦 03_EPICS: Project Tracking

| File | Topic | Status | Points |
|------|-------|--------|--------|
| `EPIC-10_PERFORMANCE_CACHING.md` | Performance & Caching | 🟢 Defined | TBD |
| `EPIC-11_SYMBOL_ENHANCEMENT.md` | Symbol Enhancement | 🟢 Defined | TBD |
| `EPIC-12_ROBUSTNESS.md` | Robustness | 🟢 Defined | TBD |
| `EPIC-13_LSP_INTEGRATION.md` | LSP Integration | 🟢 Defined | TBD |

---

## 📚 88_ARCHIVE: Historical Reference

### 2025-01-19: Deep Challenge

**Location**: `88_ARCHIVE/2025-01-19_deep_challenge/`
**Files**: 4 (ARCHIVE_2025-01-19_ADR-001/002/003_DEEP_CHALLENGE.md, ARCHIVE_2025-01-19_SYNTHESIS.md)
**Status**: ✅ Integrated into ADRs
**Size**: ~2800 lines

**Summary**: Systematic doubt methodology applied to all ADRs. Explored 40+ alternatives, scored on Performance/Simplicité/Coût/Risque/Pérennité. Result: Redis Standard > Dragonfly (pérennité priority).

**Key Findings**:
- Redis Standard (15 years) recommended over Dragonfly (3 years) - pérennité criterion
- basedpyright recommended for LSP
- Expand-Contract validated, Blue-Green documented for future

**Impact**: ADR-001 updated, score improved from 98/130 (75%) → 110/130 (85%)

### 2025-01-15: APEX Validation

**Location**: `88_ARCHIVE/2025-01-15_apex_validation/`
**Files**: 2 (ARCHIVE_2025-01-15_apex_consolidation_2024.md, ARCHIVE_2025-01-15_adr_validation_report.md)
**Status**: ✅ Base for Deep Challenge
**Purpose**: Preparatory research, superseded by deep challenge

---

## 🗑️ 99_TEMP: Temporary Workspace

**Status**: Currently empty
**Purpose**: Quick scratch notes, brainstorms (can delete anytime)
**Lifecycle**: Delete files >7 days old

---

## 📖 Method: Screaming Document Architecture

### Naming Convention

Format: `{TYPE}_{DATE}_{TOPIC}.md` (ou sans DATE si permanent)

| Prefix | Lifecycle | Example |
|--------|-----------|---------|
| `CONTROL_` | Permanent (always updated) | `CONTROL_MISSION_CONTROL.md` |
| `DECISION_` | Permanent (living doc) | `DECISION_ADR-001_cache_strategy.md` |
| `RESEARCH_` | Temporary (days-weeks) | `RESEARCH_2025-01-20_benchmarks.md` |
| `DRAFT_` | Temporary (hours-days) | `DRAFT_2025-01-20_analysis.md` |
| `TEMP_` | Volatile (delete after) | `TEMP_2025-01-20_notes.md` |
| `ARCHIVE_` | Historical (read-only) | `ARCHIVE_2025-01-19_SYNTHESIS.md` |

### Workflow: From Thinking to Decision

```
TEMP_ → DRAFT_ → RESEARCH_ → Update DECISION_ADR-xxx → Archive RESEARCH_
```

### Rules

1. **Single Source of Truth**: One ADR per topic, all else feeds into it
2. **Time-based cleanup**: TEMP_ (7 days), DRAFT_ (30 days), RESEARCH_ (on decision)
3. **Archive trigger**: When RESEARCH → DECISION: archive immediately
4. **Mandatory updates**: Update CONTROL_MISSION_CONTROL on every ADR change

---

## 📈 Statistics

**Total size**: ~5000+ lines across all documents
**Archived**: 6 files (~3500 lines)
**Active**: 10 files (~1500 lines)
**Reduction**: 70% archived (cleaner workspace)

**Before reorganization** (2025-01-19):
- 7 files in `02_RESEARCH/` (confusing mix)
- No clear lifecycle
- Unclear which documents are current

**After reorganization** (2025-01-20):
- 1 file in `02_RESEARCH/` (active work only)
- Screaming names (type + date)
- Clear archive (6 files in `88_ARCHIVE/`)

---

## 🔄 Maintenance Tasks

### Weekly
- [ ] Review 99_TEMP/ → delete files >7 days
- [ ] Review 02_RESEARCH/DRAFT_ → archive if >30 days
- [ ] Regenerate this index
- [ ] Verify MISSION_CONTROL is current

### On Decision
- [ ] Update ADR in 01_ARCHITECTURE_DECISIONS/
- [ ] Archive related RESEARCH to 88_ARCHIVE/
- [ ] Update CONTROL_MISSION_CONTROL.md
- [ ] Update this index

---

**Index Maintained By**: Human + AI (Claude)
**Regeneration**: On every file creation/archive/major change
