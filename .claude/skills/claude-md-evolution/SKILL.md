---
name: claude-md-evolution
description: CLAUDE.md cognitive engine maintenance frameworks. HOW vs WHAT test, DSL compression, version management, pattern adoption, bloat prevention. Use when updating CLAUDE.md, deciding content placement, bumping versions.
---

# claude-md-evolution

**Ontologie DSL** (LLM comprehension):

**Symbols**: ✅=PASS ❌=FAIL ⚠️=PARTIAL →=MIGRATE ∵=BECAUSE ∴=THEREFORE ≥=THRESHOLD
**Concepts**: HOW=Cognitive WHAT=Knowledge DSL=Compression 1L=1-line BLOAT=Inflation
**Locations**: CM=CLAUDE.md SK=Skill RM=README ST=STATUS GL=git-log
**Criteria**: U=Universal S=Stable C=Cognitive X=Cross-cutting K=Critical D=Compressible
**Versions**: MAJ=MAJOR MIN=MINOR PAT=PATCH

---

## When to Use

- Content placement (CM vs SK): F1 HOW vs WHAT Test
- DSL compression: F4 1L.DSL test
- Version bump: F2 MAJ/MIN/PAT decision
- Pattern adoption: F3 5-criteria filter
- Bloat prevention: 5 anti-patterns check

---

## F1: HOW vs WHAT Test

**Critères** (6): U=Universal, S=Stable, C=Cognitive, X=Cross-cutting, K=Critical, D=Compressible

**Test**: Count ≥4/6 → CM | <4 → SK

| Criterion | CM if... | SK if... |
|-----------|----------|----------|
| U | All projects | Project-specific |
| S | Rare Δ | Frequent Δ |
| C | HOW (principle) | WHAT (fact) |
| X | Multi-domain | Domain-specific |
| K | Top 5 rules | Reference/catalog |
| D | 1L.DSL ✅ | Prose/details |

**Examples**:

| Content | U | S | C | X | K | D | Score | → |
|---------|:-:|:-:|:-:|:-:|:-:|:-:|:-----:|---|
| Test-first | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | 5/6 | CM |
| EXTEND>REBUILD | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | 5/6 | CM |
| PG18 schema | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | 0/6 | SK |
| 31 gotchas | ❌ | ⚠️ | ❌ | ❌ | ❌ | ❌ | 0/6 | SK |
| Top 5 rules | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 6/6 | CM |
| Bash catalog | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | 2/6 | RM |

**Decision**: ≥4/6 → CM | <4 → SK | U ∧ ¬C → RM (universal knowledge)

---

## F2: Version Bump

**SemVer**: vMAJOR.MINOR.PATCH

| Type | When | Example |
|------|------|---------|
| MAJ | Architecture Δ, Breaking Δ, Philosophy shift, -50%+ | v3.2→v4.0 (DSL -76%) |
| MIN | +Sections, Enhancements, Patterns, Non-breaking | v3.0→v3.1 (MCO ❌ bloat) |
| PAT | Typos, Small Δ, Clarifications | v3.1→v3.1.1 (fixes) |
| NONE | Whitespace, Formatting | - |

**Flowchart**:
```
Δ → Architecture|Breaking|Philosophy|Drastic(-50%+)? → MAJ
  → +Sections|Enhancement|Patterns? → MIN
  → Typo|Small|Clarification? → PAT
  → Format only? → NONE
```

---

## F3: Pattern Adoption Filter

**Checklist** (ALL 5 required):
1. ☐ U? (Not project-specific to source)
2. ☐ Solves? (Addresses our need)
3. ☐ Proven? (Evidence works)
4. ☐ Benefit>cost? (Token justified)
5. ☐ Compatible? (Aligns architecture)

**Decision**: 5/5 ✅ → Backup → Adopt → Validate | <5 ❌ → Reject (document TEMP)

**Examples**:

| Pattern | U | Solves | Proven | B>C | Compat | Score | F4? | → |
|---------|:-:|:------:|:------:|:---:|:------:|:-----:|:---:|---|
| § PRINCIPLES | ✅ | ✅ | ✅ | ✅ | ✅ | 5/5 | ✅ | ADOPT |
| § QUICK COMMANDS | ✅ | ⚠️ | ✅ | ❌ | ⚠️ | 2/5 | ❌ | REJECT (v3.1→v4.0) |
| Dashboard-centric | ❌ | ❌ | ✅ | ❌ | ❌ | 1/5 | - | REJECT |

**Lesson**: F3 (5/5) ∧ F4 (1L.DSL) BOTH required | § QUICK passed F3 ✅ failed F4 ❌ → Removed v4.0

---

## F4: DSL Compression Test

**Test**: Content → 1L.DSL? → ✅ CM | ⚠️ CM.heuristic+SK.details | ❌ SK/RM/ST

| Content | 1L? | Compressed | → |
|---------|:---:|------------|---|
| EXTEND>REBUILD | ✅ | `! EXTEND>REBUILD → copy → adapt` | CM |
| Test-First | ✅ | `New.Feature → Test → Implement → Commit` | CM |
| Pre-test gate | ⚠️ | `! Pre.Test.Gate: TEST_DB ∧ EMBED=mock` | CM |
| Bash catalog (40L) | ❌ | Cannot compress | RM |
| EPIC state | ❌ | Volatile | ST/git |
| Version history (17L) | ❌ | Historical facts | GL |

**Impact v4.0**: § CRITICAL FIRST STEP (15→1L), § QUICK COMMANDS (40→0L), § CURRENT STATE (8→0L)

**Decision**: ✅ 1L → CM | ⚠️ Compress → CM+SK | ❌ Prose/details → SK/RM/ST/GL

---

## Anti-Patterns (NEVER → CM)

**v3.1-v3.2 bloat**: +146L → v4.0 correction: -171L

| Pattern | Example | ❌ Why | ✅ Correct | Test Fail |
|---------|---------|--------|-----------|-----------|
| Commands.Catalog | `make up/test` (40L bash) | U ✅ C ❌ | RM | 1L.DSL ❌ |
| Volatile.State | `EPIC-10 (27/35pts)` | S ❌ weekly | ST/git | S ❌ |
| Skill.Duplication | § ANTI-PATTERNS (18L) | Already in SK | Reference SK | DRY ❌ |
| Version.History | Changelog (17L) | GL = truth | GL/CHANGELOG | 1L.DSL ❌ |
| Universal≠Cognitive | `echo $TEST_DB` | U ✅ C ❌ | Compress: `! Pre.Test.Gate` | C ❌ |

**Key**: U=Universal, S=Stable, C=Cognitive, CM=CLAUDE.md, SK=Skill, RM=README, ST=STATUS, GL=git log

**Insight**: U ∧ C = CM (BOTH required!) | U ∧ ¬C = RM (universal knowledge)

---

## Lessons: v3.0 → v4.0 Journey (2025-10-21→22)

| Ver | Lines | Δ | Strategy | Result | Mistake/Success |
|-----|-------|---|----------|--------|-----------------|
| v3.0 | 79 | -10% | HOW/WHAT split → SK:arch | ✅ SUCCESS | Principle: CM=HOW, SK=WHAT |
| v3.1 | 204 | +158% | MCO patterns (6) | ❌ BLOAT +125L | U ✅ C ❌ confusion, no F4 test |
| v3.2 | 225 | +10% | SK:claude-md + § META | ❌ BLOAT +21L | Duplicate SK content → CM |
| v4.0 | 54 | -76% | F4 DSL compression | ✅ SUCCESS -171L | F4 test applied, pure DSL |

**v3.1 Mistakes**:
- § QUICK COMMANDS (40L bash): U ✅ C ❌ → F4 ❌ 1L.DSL → RM
- § CURRENT STATE (8L): S ❌ volatile → ST/git
- § CRITICAL FIRST STEP (15L bash): Details ❌ 1L.DSL → Compress: `! Pre.Test.Gate: TEST_DB ∧ EMBED=mock`

**v3.2 Mistakes**:
- § ANTI-PATTERNS (18L): Duplicate SK content → Meta-irony!
- § META details (47→12L in v4.0): Knowledge not cognitive

**Key Insights**:
1. **U ≠ C**: U ∧ C BOTH required | `make up` = U ✅ C ❌ → RM
2. **F4 = Litmus**: 1L.DSL test prevents bloat | Commands/state/history fail → RM/ST/GL
3. **F3 insufficient**: Pattern adoption needs F3 ∧ F4 | § CRITICAL passed F3 (5/5) failed F4 (15L bash)
4. **Meta-irony**: SK teaching compression caused bloat (duplicate § ANTI-PATTERNS)

**Timeline**: 3 iterations 1 day → F4 discovered ∴ -76% v4.0

---

## Quick Reference

### Content Placement
```
New content
  ├─ F4 (1L.DSL?) → ❌ → SK/RM/ST
  ├─ F4 → ✅ → F1 (6 criteria)
  │  └─ ≥4/6 → CM | <4 → SK
  └─ U ∧ ¬C → RM (universal knowledge)
```

### Version Bump
```
Δ → Architecture|Breaking|Philosophy|Drastic(-50%+)? → MAJ
  → +Sections|Enhancement|Patterns? → MIN
  → Typo|Small|Clarification? → PAT
  → Format only? → NONE
```

### Pattern Adoption
```
External pattern
  ├─ F4 (1L.DSL?) → ❌ → REJECT or compress
  ├─ F3 (5 criteria) → 5/5 → ADOPT (backup → validate)
  └─ <5 → REJECT (document TEMP)
```

### Bloat Prevention
```
Before adding → CM
  ├─ Check Anti-Patterns (5 NEVER)
  ├─ F4 (1L.DSL test)
  ├─ F1 (6 criteria ≥4)
  └─ All pass? → SAFE
```

---

## Key Rules (Summary)

```yaml
Core_Principle:
  CM: HOW (principles, workflows, heuristics → 1L.DSL)
  SK: WHAT (facts, patterns, domain knowledge, details)

Decision_Criteria:
  Content_Placement: ≥4/6 criteria → CM | <4 → SK | U ∧ ¬C → RM
  DSL_Compression: 1L.DSL ✅ → CM | ❌ → SK/RM/ST/GL
  Version_Bump: Architecture→MAJ | Sections→MIN | Small→PAT
  Pattern_Adoption: F3 (5/5) ∧ F4 (1L.DSL) → ADOPT | Else → REJECT

Evolution_Strategy:
  Bottom_up: SK emerge @500+L knowledge
  Top_down: Principles extracted @3x.repeat
  Horizontal: Adopt universal patterns (F3 ∧ F4 filter)

Validation:
  Before: Backup (CLAUDE_vX.Y.Z_BACKUP.md) + Document + F4 test
  After: Session vierge + Sanity check + No broken refs
  Fail: git revert immediately

Anti_Patterns (NEVER):
  Commands.Catalog: 40+L bash → RM
  Volatile.State: Weekly Δ → ST/git
  Skill.Duplication: Repeat SK → Reference only
  Version.History.Detailed: 17+L → GL/CHANGELOG
  Universal≠Cognitive: U ✅ C ❌ → RM or compress
```

---

**Version**: 3.1.0 (compressed with DSL ontology)
**Size**: 272 lines (vs 470 v3.0, -198 lines, -42%)
**Philosophy**: Ontology-driven compression → LLM comprehension → Massive reduction without utility loss
**Critical**: F4 (DSL Compression Test) prevents bloat, ensures cognitive purity
