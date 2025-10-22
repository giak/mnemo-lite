# Implementation Plan - Option B (POC #1 + POC #3)

**Date**: 2025-10-21
**Duration**: 2-3 hours estimated
**Status**: IN PROGRESS
**Branch**: poc/claude-optimization-validation

---

## 🎯 Objectives

Implement 2 fully validated optimizations:
1. **POC #1**: Progressive Disclosure (mnemolite-gotchas decomposition)
2. **POC #3**: YAML Frontmatter (add metadata to skills)

**Defer**: POC #2 (Hierarchical CLAUDE.md) - requires multi-session validation

---

## 📋 Implementation Steps

### Phase 1: Backup & Setup (15 min)

**Checkpoint 1.1**: Backup current skills
- [x] POC artifacts already exist in `.claude/skills/poc-*`
- [ ] Backup mnemolite-gotchas skill.md → skill.md.BACKUP
- [ ] Backup epic-workflow skill.md → skill.md.BACKUP
- [ ] Git status check

**Checkpoint 1.2**: Analyze current structure
- [ ] Read mnemolite-gotchas skill.md (850 lines)
- [ ] Identify natural domain boundaries
- [ ] Plan split: index + 7 domain files

**Expected domains**:
1. `critical.md` - 7 CRITICAL gotchas (~100 lines)
2. `database.md` - Database gotchas (~100 lines)
3. `testing.md` - Testing gotchas (~100 lines)
4. `architecture.md` - Architecture gotchas (~100 lines)
5. `code-intel.md` - Code Intelligence gotchas (~100 lines)
6. `performance.md` - Performance + Docker gotchas (~100 lines)
7. `workflow.md` - Git & Workflow gotchas (~100 lines)
8. `ui.md` - UI gotchas (~100 lines)

**Index**: skill.md (~150 lines with @references)

---

### Phase 2: POC #1 - Progressive Disclosure Implementation (90 min)

**Checkpoint 2.1**: Create domain files structure
- [ ] Create `.claude/skills/mnemolite-gotchas/domains/` directory
- [ ] Extract and create each domain file:
  - [ ] `critical.md` (7 CRITICAL gotchas)
  - [ ] `database.md` (5 database gotchas)
  - [ ] `testing.md` (3 testing gotchas)
  - [ ] `architecture.md` (3 architecture gotchas)
  - [ ] `code-intel.md` (5 code intel gotchas)
  - [ ] `performance.md` (3 performance gotchas)
  - [ ] `workflow.md` (3 workflow gotchas)
  - [ ] `ui.md` (3 UI gotchas)

**Checkpoint 2.2**: Create new index skill.md
- [ ] Write new skill.md with:
  - Overview section (~20 lines)
  - Domain index with @references (~50 lines)
  - Quick reference table (~30 lines)
  - Usage instructions (~50 lines)
- [ ] Add @critical.md references
- [ ] Add @database.md references
- [ ] Add @testing.md references
- [ ] Add references for all 8 domains

**Checkpoint 2.3**: Test @references
- [ ] Read skill.md (verify it loads)
- [ ] Read critical.md (verify @reference works)
- [ ] Read database.md (verify @reference works)
- [ ] Test with all 8 domain files
- [ ] Measure line counts (verify ~150 for index)

**Checkpoint 2.4**: Validate content completeness
- [ ] Compare original vs decomposed (all 31 gotchas present?)
- [ ] Check all examples preserved
- [ ] Check all code snippets preserved
- [ ] Check troubleshooting table preserved

---

### Phase 3: POC #3 - YAML Frontmatter Implementation (45 min)

**Checkpoint 3.1**: Add YAML to mnemolite-gotchas skill.md
- [ ] Create YAML frontmatter structure
- [ ] Add metadata: name, version, category, auto_invoke, priority, metadata, tags
- [ ] Test YAML syntax (Python yaml.safe_load)
- [ ] Measure token overhead

**YAML structure**:
```yaml
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
  estimated_size: 150 lines (index) + 800 lines (domains)
  token_cost_index: ~3750 tokens
  token_cost_full: ~21250 tokens
  domains: 8
tags:
  - gotchas
  - debugging
  - troubleshooting
  - critical
---
```

**Checkpoint 3.2**: Add YAML to epic-workflow skill.md
- [ ] Create YAML frontmatter structure
- [ ] Add metadata: name, version, category, auto_invoke, priority, metadata, tags
- [ ] Test YAML syntax
- [ ] Measure token overhead

**YAML structure**:
```yaml
---
name: epic-workflow
version: 1.0.0
category: workflow
auto_invoke:
  - EPIC
  - Story
  - completion
  - analysis
  - implementation
  - plan
priority: high
metadata:
  created: 2025-10-21
  purpose: EPIC/Story workflow management
  estimated_size: 750 lines
  token_cost: ~18750 tokens
tags:
  - epic
  - story
  - workflow
  - agile
---
```

**Checkpoint 3.3**: Add YAML to document-lifecycle skill (optional)
- [ ] Create YAML frontmatter structure
- [ ] Add metadata
- [ ] Test YAML syntax

**Checkpoint 3.4**: Validate all YAML
- [ ] Python script to validate all skill YAML frontmatter
- [ ] Check no syntax errors
- [ ] Verify all skills still load

---

### Phase 4: Testing & Validation (30 min)

**Checkpoint 4.1**: Functional testing
- [ ] Read mnemolite-gotchas skill.md (index should load)
- [ ] Test @critical.md reference works
- [ ] Test @database.md reference works
- [ ] Test all 8 domain references work
- [ ] Verify YAML frontmatter visible and readable

**Checkpoint 4.2**: Token cost measurement
- [ ] Count lines: skill.md index
- [ ] Count lines: each domain file
- [ ] Calculate total lines (should be ~950, was 850)
- [ ] Calculate token cost: index only (~3750 tokens, was ~21250)
- [ ] Calculate savings: (21250 - 3750) / 21250 = ~82% when index-only

**Checkpoint 4.3**: Content validation
- [ ] Check all 31 gotchas present
- [ ] Check all examples preserved
- [ ] Check troubleshooting table preserved
- [ ] Verify no content loss

---

### Phase 5: Documentation & Commit (20 min)

**Checkpoint 5.1**: Update POC_TRACKING.md
- [ ] Add "Implementation Results" section
- [ ] Document actual vs estimated metrics
- [ ] Document any issues encountered
- [ ] Update status to COMPLETE

**Checkpoint 5.2**: Create implementation completion report
- [ ] Create TEMP_2025-10-21_option_b_completion_report.md
- [ ] Document what was implemented
- [ ] Document metrics (lines, tokens, savings)
- [ ] Document lessons learned

**Checkpoint 5.3**: Git commit
- [ ] Review all changes: git status
- [ ] Review diff: git diff
- [ ] Stage changes: git add
- [ ] Commit with message:
```
feat(claude-optimization): Implement POC #1 (Progressive Disclosure) + POC #3 (YAML)

POC #1 - Progressive Disclosure:
- Decomposed mnemolite-gotchas (850 lines → 150 line index + 8 domain files)
- Added @filename.md references for on-demand loading
- Token savings: 82% when loading index only (3750 vs 21250 tokens)
- Domains: critical, database, testing, architecture, code-intel, performance, workflow, ui

POC #3 - YAML Frontmatter:
- Added YAML frontmatter to mnemolite-gotchas, epic-workflow
- Metadata: name, version, category, auto_invoke, priority, tags
- Enables skill discovery, versioning, token cost tracking
- Token overhead: +38% acceptable for metadata benefits

Validation:
- All 31 gotchas preserved
- All @references work correctly
- YAML parsing validated (Python yaml.safe_load)
- No content loss

Branch: poc/claude-optimization-validation
Status: COMPLETE
Duration: ~2-3 hours

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>
```

---

## 📊 Success Criteria

**Must achieve**:
- [x] POC #1: mnemolite-gotchas decomposed into index + domains
- [ ] POC #1: All @references work correctly
- [ ] POC #1: Token savings ≥ 70% when loading index only
- [ ] POC #3: YAML frontmatter added to 2+ skills
- [ ] POC #3: YAML parsing validated (no syntax errors)
- [ ] All content preserved (31 gotchas intact)
- [ ] Git commit with clear message

**Nice to have**:
- [ ] YAML added to document-lifecycle skill
- [ ] Skill catalog generation script (Python)
- [ ] Token cost estimation script

---

## 🚨 Rollback Plan

**If issues discovered**:
1. Restore from backup: `cp skill.md.BACKUP skill.md`
2. Git rollback: `git checkout -- .claude/skills/`
3. POC artifacts remain in `.claude/skills/poc-*` for reference

---

## 📈 Expected Metrics

**Before (baseline)**:
- mnemolite-gotchas: 850 lines (~21250 tokens)
- epic-workflow: 750 lines (~18750 tokens)
- Total: 1600 lines (~40000 tokens)

**After (Option B)**:
- mnemolite-gotchas index: ~150 lines (~3750 tokens) [82% savings]
- mnemolite-gotchas domains: 8 × ~100 lines = ~800 lines (~20000 tokens)
- mnemolite-gotchas total: ~950 lines (~23750 tokens) [when all loaded]
- epic-workflow with YAML: ~768 lines (~19200 tokens) [+2.4% overhead]
- Total index-only: ~918 lines (~22950 tokens)
- **Savings when index-only**: (40000 - 22950) / 40000 = **42.6% token reduction**

**When loading index + 1 domain**:
- mnemolite-gotchas: 150 + 100 = 250 lines (~6250 tokens) [71% savings vs original]
- epic-workflow: 768 lines (~19200 tokens)
- Total: ~1018 lines (~25450 tokens)
- **Savings**: (40000 - 25450) / 40000 = **36.4% token reduction**

---

**Last Updated**: 2025-10-21 (Phase 1 start)
**Status**: IN PROGRESS
**Current Phase**: Phase 1 - Backup & Setup
