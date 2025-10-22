---
name: claude-md-evolution
description: Guides CLAUDE.md cognitive engine maintenance, evolution, version management. Use when updating CLAUDE.md, deciding what belongs where (HOW vs WHAT), adopting patterns, managing versions, validating changes.
---

# claude-md-evolution

**Purpose**: Decision frameworks for CLAUDE.md evolution (HOW TO THINK vs WHAT TO KNOW)

---

## When to Use

- Deciding where content belongs (CLAUDE.md vs skill)
- Bumping version (MAJOR/MINOR/PATCH decision)
- Adopting patterns from other projects
- Validating changes before commit

---

## Framework 1: HOW vs WHAT Test

**Question**: Does this content belong in CLAUDE.md or a skill?

| Criterion | CLAUDE.md if... | Skill if... |
|-----------|----------------|-------------|
| **Universal** | Applies to all projects | Project-specific fact |
| **Stable** | Rarely changes | Changes frequently |
| **Cognitive** | HOW TO THINK (workflow, principle) | WHAT TO KNOW (implementation, fact) |
| **Scope** | Cross-cutting multiple domains | Domain-specific (DB, Testing, UI) |
| **Critical** | Top 5 most critical rules | Reference material, catalog |

**Decision Rule**: Count criteria → ≥3 TRUE for CLAUDE.md → CLAUDE.md | Else → Skill

**Examples**:

| Content | CLAUDE.md? | Skill? | Score | Reasoning |
|---------|:----------:|:------:|:-----:|-----------|
| "Test-first principle" | ✅ | ❌ | 4/5 | Universal, stable, cognitive, cross-cutting |
| "EXTEND>REBUILD" | ✅ | ❌ | 4/5 | Universal productivity principle |
| "PostgreSQL 18 schema" | ❌ | ✅ | 0/5 | Project fact, domain-specific, evolving |
| "31 gotchas catalog" | ❌ | ✅ | 1/5 | Reference material, large, domain-specific |
| "Top 5 critical rules" | ✅ | ❌ | 5/5 | Universal, stable, cognitive, cross-cutting, critical |
| "EPIC workflow steps" | ❌ | ✅ | 1/5 | Process-specific, detailed, evolving |

---

## Framework 2: Version Bump Criteria

**Semantic Versioning**: `vMAJOR.MINOR.PATCH`

```yaml
MAJOR (vX.0.0):
  When:
    - Architecture change (e.g., HOW/WHAT separation)
    - Breaking changes (skills renamed, structure changed)
    - Philosophy shift (fundamental approach change)
  Example: v2.4 → v3.0 (HOW/WHAT separation, -57%)

MINOR (vX.Y.0):
  When:
    - New sections added (e.g., § ANTI-PATTERNS)
    - Significant enhancements (e.g., enforcement gates)
    - Pattern adoptions (e.g., MCO patterns)
    - Non-breaking additions
  Example: v3.0 → v3.1 (+6 MCO patterns, +125 lines)

PATCH (vX.Y.Z):
  When:
    - Typo fixes
    - Small clarifications
    - § CURRENT STATE weekly updates
    - Minor content updates (no structure change)
  Example: v3.1.0 → v3.1.1 (update § CURRENT STATE)

NO_BUMP:
  When:
    - Whitespace, formatting only
    - Very minor edits
```

**Decision Flowchart**:
```
Change made
  ├─ Architecture? Breaking? Philosophy? → YES → MAJOR (vX.0.0)
  ├─ New sections? Enhancement? Patterns? → YES → MINOR (vX.Y.0)
  ├─ Typo? Small? § CURRENT STATE? → YES → PATCH (vX.Y.Z)
  └─ Formatting only? → NO BUMP
```

---

## Framework 3: Pattern Adoption Filter

**Question**: Should we adopt this pattern from another CLAUDE.md?

**5-Criteria Checklist** (ALL must pass):

1. ☐ **Universal?** Not project-specific to source
2. ☐ **Solves our problem?** Addresses our actual need
3. ☐ **Proven?** Evidence it works in source project
4. ☐ **Benefit > cost?** Token cost justified by utility gain
5. ☐ **Compatible?** Aligns with skills ecosystem architecture

**Decision**:
- 5/5 ✅ → ADOPT (backup → implement → validate)
- <5 ❌ → REJECT (document why in TEMP)

**Example** (MCO v3.1 adoption):
```
§ CRITICAL FIRST STEP:
  ✅ Universal (setup verification applies to all)
  ✅ Solves problem (prevents CRITICAL-01)
  ✅ Proven (MCO uses successfully)
  ✅ Benefit>cost (+15 lines, prevents hours debugging)
  ✅ Compatible (prevention approach)
  → 5/5 ADOPT

Dashboard-centric:
  ❌ Universal (MCO-specific architecture)
  ❌ Solves problem (we use skills ecosystem)
  → 1/5 REJECT
```

---

## Quick Reference

### Content Placement
```
New content
  ├─ Apply HOW vs WHAT Test (5 criteria)
  │  └─ ≥3 TRUE → CLAUDE.md
  └─ <3 TRUE → Skill (existing or new)
```

### Version Bump
```
Change
  ├─ Architecture/Breaking/Philosophy? → MAJOR
  ├─ Sections/Enhancement/Patterns? → MINOR
  ├─ Typo/Small/Weekly? → PATCH
  └─ Formatting? → NO BUMP
```

### Pattern Adoption
```
External pattern
  ├─ Apply 5 criteria
  │  └─ 5/5 → ADOPT (backup → validate)
  └─ <5 → REJECT (document why)
```

---

## Key Rules (Summary)

```yaml
Core_Principle:
  CLAUDE.md: HOW TO THINK (principles, workflows, top N critical)
  Skills: WHAT TO KNOW (facts, patterns, domain knowledge)

Decision_Criteria:
  Content_Placement: ≥3/5 criteria → CLAUDE.md | Else → Skill
  Version_Bump: Architecture→MAJOR | Sections→MINOR | Small→PATCH
  Pattern_Adoption: All 5 criteria pass → ADOPT | Else → REJECT

Evolution_Strategy:
  Bottom_up: Skills emerge from knowledge accumulation (~500+ lines)
  Top_down: Principles extracted when patterns repeat 3+ times
  Horizontal: Adopt universal patterns (filtered with 5 criteria)

Validation:
  Before: Backup (CLAUDE_vX.Y.Z_BACKUP.md) + Document intent
  After: Session vierge test + Sanity check + No broken references
  Fail: Git revert immediately
```

---

**Version**: 2.0.0 (minimal, actionable frameworks only)
**Size**: 129 lines (vs 323 before, -60%)
**Philosophy**: Frameworks for decisions, rules in CLAUDE.md § META
