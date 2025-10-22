# Skill claude-md-evolution Created

**Date**: 2025-10-22
**Location**: `.claude/skills/claude-md-evolution/SKILL.md`
**Size**: 1,081 lines
**Type**: Meta-cognitive skill (how to maintain CLAUDE.md itself)

---

## Skill Overview

**Name**: `claude-md-evolution`
**Version**: 1.0.0
**Purpose**: Meta-cognition for cognitive engine evolution

**YAML Frontmatter**:
```yaml
---
name: claude-md-evolution
description: Guides CLAUDE.md cognitive engine maintenance, evolution, version management. Use when updating CLAUDE.md, deciding what belongs where (HOW vs WHAT), adopting patterns, managing versions, validating changes.
---
```

**Auto-invoke keywords**: CLAUDE.md, cognitive engine, maintenance, evolution, version, HOW vs WHAT, pattern adoption, validation

---

## Content Structure (9 Major Sections)

### 1. Purpose & Philosophy
- Meta-cognitive skill concept
- HOW TO THINK vs WHAT TO KNOW separation
- Evolution strategy (bottom-up, top-down, horizontal)
- Token optimization principles
- Validation-first approach

### 2. When to Use This Skill
- 8 use cases documented
- Questions this skill answers
- Auto-invoke triggers

### 3. Decision Frameworks (4 Frameworks)

**Framework 1: HOW vs WHAT Test**
- Criteria: Universal? Stable? Cognitive? Cross-cutting? Critical?
- Examples table (6 content types with reasoning)
- Decision rule: ≥3 TRUE → CLAUDE.md, else → Skill

**Framework 2: Version Bump Criteria**
- MAJOR: Architecture changes, breaking changes, philosophy shifts
- MINOR: New sections, enhancements, pattern adoptions
- PATCH: Small updates, typos, § CURRENT STATE weekly
- Examples: v2.4→v3.0 (MAJOR), v3.0→v3.1 (MINOR)

**Framework 3: Pattern Adoption Filter**
- 5 criteria filter: Universal? Solves problem? Proven? Benefit>cost? Compatible?
- MCO pattern analysis example (6 adopted, 4 rejected)
- Decision logic in Python pseudocode

**Framework 4: Change Validation Protocol**
- Pre-change: Backup, document intent, identify risks, plan rollback
- Change: Implement, update version, update changelog
- Post-change: Session vierge test, sanity check, measure impact
- Decision: Keep if improvement, revert if regression

### 4. Maintenance Workflows (4 Workflows)

**Workflow 1: Weekly Update (§ CURRENT STATE)**
- Trigger: EPIC completed, Story completed, milestone
- Steps: Update completed EPICs, in-progress, next, skills, branch
- Version: PATCH or NO BUMP

**Workflow 2: Quarterly Review**
- Review: Principles, critical rules, anti-patterns, skills, workflows
- Extract patterns that repeated 3+ times
- Version: MINOR if significant enhancements

**Workflow 3: Pattern Adoption (external projects)**
- Document pattern → Apply filter → Test → Decide
- Example: MCO patterns (v3.1 adoption)

**Workflow 4: Emergency Rollback**
- Immediate rollback (git revert or restore backup)
- Verify restoration (session vierge, commands, comprehension)
- Post-mortem analysis
- Update validation protocol

### 5. Anti-Patterns (5 CLAUDE.md-Specific)

**Anti-Pattern 1: Facts Bloat**
- Problem: Adding project facts instead of skill references
- Example: Database schema in CLAUDE.md (WRONG)
- Fix: Reference skill:mnemolite-architecture

**Anti-Pattern 2: Skill Duplication**
- Problem: Repeating skill descriptions in CLAUDE.md
- Fix: Trust auto-discovery, single source of truth

**Anti-Pattern 3: Premature Optimization**
- Problem: Optimizing without measuring baseline
- Example: Aggressive compression without evidence
- Fix: Evidence-based optimization (measure first)

**Anti-Pattern 4: Breaking Changes Without Validation**
- Problem: Renaming, restructuring without testing
- Example: Rename skills to gerund form (high risk, low benefit)
- Fix: Validation protocol, require session vierge test

**Anti-Pattern 5: Over-Engineering**
- Problem: Complexity without utility
- Example: Skill dependency graph (redundant)
- Fix: KISS principle, trust auto-discovery

### 6. Version Management
- Semantic versioning discipline
- Changelog discipline (every bump updates § VERSION HISTORY)
- Backup strategy (before every change)
- Retention policy (last 3 major, current minor)

### 7. Lessons Learned Archive (5 Lessons)

**Lesson 1: UPPERCASE SKILL.md Required**
- Discovery: 3 attempts to find correct structure
- Takeaway: ALWAYS check official docs first

**Lesson 2: HOW/WHAT Separation Works**
- Discovery: 60-80% token savings measured
- Takeaway: Maintain strict separation

**Lesson 3: Pattern Adoption Requires Filtering**
- Discovery: 6/10 MCO patterns adopted (60% adoption rate)
- Takeaway: Use filter framework, universal vs context-specific

**Lesson 4: Evidence > Hypotheses**
- Discovery: Many "best practices" are hypotheses, not official
- Takeaway: Distinguish facts from inferences

**Lesson 5: Validation Protocol Essential**
- Discovery: Changes without validation risk breaking architecture
- Takeaway: Validation mandatory before ANY change

### 8. Examples (3 Detailed Examples)

**Example 1: v2.4 → v3.0 (HOW/WHAT Separation)**
- Trigger, problem, framework applied, changes, result, validation
- Version bump: MAJOR

**Example 2: v3.0 → v3.1 (MCO Patterns Adoption)**
- Pattern analysis, filter application, 6 adopted/4 rejected
- Version bump: MINOR

**Example 3: Weekly § CURRENT STATE Update**
- Trigger: EPIC-10 completion
- Version bump: PATCH or NO BUMP

### 9. Quick Reference
- 4 decision flowcharts (content placement, version bump, pattern adoption, change validation)

### 10. Metrics & Validation
- Token cost metrics (v3.0, v3.1, targets)
- Validation checklist (9 items REQUIRED post-change)
- Maintenance frequency targets

---

## Size Analysis

**Total Lines**: 1,081 lines

**Size Breakdown** (estimated):
- YAML frontmatter: 5 lines
- Purpose & Philosophy: 40 lines
- When to Use: 20 lines
- Decision Frameworks: 250 lines (4 frameworks, detailed)
- Maintenance Workflows: 200 lines (4 workflows, detailed)
- Anti-Patterns: 150 lines (5 anti-patterns with examples)
- Version Management: 50 lines
- Lessons Learned: 150 lines (5 lessons, detailed)
- Examples: 150 lines (3 examples, detailed)
- Quick Reference: 40 lines
- Metrics & Validation: 40 lines

**Note**: Exceeds 500 line "hypothesis" from audit, but:
1. 500 lines was hypothesis, not official requirement
2. This is meta-skill (documents entire skill + CLAUDE.md system)
3. Knowledge-dense (every line valuable)
4. Progressive disclosure structure (index + detailed sections)
5. Real experience synthesized (POCs + v3.0 + v3.1 + audit + verification)

---

## Knowledge Sources Synthesized

**1. Skills POCs Journey** (2025-10-21):
- 3 attempts (lowercase → flat → UPPERCASE)
- Lesson: Official docs first, not assumptions

**2. CLAUDE.md v3.0 Refactor** (2025-10-21):
- HOW/WHAT separation
- 88 → 79 lines (-10%)
- 60-80% token savings measured

**3. CLAUDE.md v3.1 Enhancement** (2025-10-22):
- MCO patterns analyzed (10+ patterns)
- 6 universal adopted, 4 MCO-specific rejected
- 79 → 204 lines (+158%)

**4. Detailed Audit** (2025-10-21):
- Hypotheses vs facts distinction
- Skills work perfectly as-is
- Evidence-based approach

**5. Verification & Option A** (2025-10-22):
- Validation protocol designed
- Option A decision (keep skills unchanged)
- No breaking changes without proven benefit

---

## Value Proposition

**Prevents Errors**:
- 5 anti-patterns documented (don't repeat mistakes)
- Validation protocol enforces testing before changes
- Emergency rollback workflow for recovery

**Guides Evolution**:
- 4 decision frameworks (clear criteria for common decisions)
- 4 maintenance workflows (weekly, quarterly, adoption, rollback)
- Decision flowcharts for quick reference

**Preserves Knowledge**:
- 5 key lessons archived (POCs, HOW/WHAT, patterns, evidence, validation)
- 3 detailed examples (v2.4→v3.0, v3.0→v3.1, weekly update)
- Real experience, not theory

**Maintains Quality**:
- Version discipline (semantic versioning, changelog required)
- Metrics tracked (token costs, utility, frequency)
- Validation checklist (9 items REQUIRED post-change)

---

## Auto-Invoke Scenarios

This skill will auto-invoke when:
1. "Should this go in CLAUDE.md or a skill?"
2. "How do I update CLAUDE.md?"
3. "When to bump version?"
4. "How to adopt patterns from another project?"
5. Mention of: CLAUDE.md, cognitive engine, HOW vs WHAT, validation

---

## Next Steps

**Testing** (Next Session Recommended):
1. Session vierge test
   - Launch new session
   - Ask: "Should I add this stack detail to CLAUDE.md or a skill?"
   - Verify: "The 'claude-md-evolution' skill is running"

2. Practical test
   - Try using Framework 1 (HOW vs WHAT Test) for real content
   - Verify decision makes sense

3. Utility validation
   - Is skill helpful? Or too long/complex?
   - Iterate based on usage

**CLAUDE.md Update** (Optional):
- Update § SKILLS.ECOSYSTEM:
  - Add `claude-md-evolution` to core skills list
- Update § VERSION HISTORY:
  - Note: v3.1.0 → v3.1.1 (added meta-skill: claude-md-evolution)
  - Or defer to next MINOR version bump

**Documentation**:
- Skill is self-documenting (meta-cognitive)
- No additional docs needed

---

## Metrics

**Creation**:
- Ultrathink: 590 lines (TEMP_2025-10-22_SKILL_CLAUDE_MD_MAINTENANCE_ULTRATHINK.md)
- Skill: 1,081 lines (comprehensive synthesis)
- Time: Single session (brainstorm → design → create)

**Token Cost** (estimated):
- Metadata: ~40-50 tokens (YAML frontmatter in startup)
- Body: ~6,000-7,000 tokens (if loaded on-demand)
- Impact: Progressive disclosure (only loads when needed)

**Knowledge Density**:
- 4 decision frameworks (actionable criteria)
- 4 maintenance workflows (step-by-step procedures)
- 5 anti-patterns (what NOT to do)
- 5 lessons learned (real experience)
- 3 detailed examples (concrete applications)

---

**Status**: ✅ Skill created successfully
**Location**: `.claude/skills/claude-md-evolution/SKILL.md`
**Version**: 1.0.0
**Type**: Meta-cognitive (maintains the cognitive engine itself)
**Ready**: For session vierge testing
