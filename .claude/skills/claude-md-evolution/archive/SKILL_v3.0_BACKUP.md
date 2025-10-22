---
name: claude-md-evolution
description: Guides CLAUDE.md cognitive engine maintenance, evolution, version management. Use when updating CLAUDE.md, deciding what belongs where (HOW vs WHAT), adopting patterns, managing versions, validating changes. Includes DSL compression test.
---

# claude-md-evolution

**Purpose**: Decision frameworks for CLAUDE.md evolution (HOW TO THINK vs WHAT TO KNOW)

---

## When to Use

- Deciding where content belongs (CLAUDE.md vs skill)
- Testing if content compresses to 1-line DSL
- Bumping version (MAJOR/MINOR/PATCH decision)
- Adopting patterns from other projects
- Validating changes before commit
- Preventing bloat anti-patterns

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
| **Compressible** | 1-line DSL without loss | Requires details/prose |

**Decision Rule**: Count criteria → ≥4/6 TRUE for CLAUDE.md → CLAUDE.md | Else → Skill

**Examples**:

| Content | CLAUDE.md? | Skill? | Score | Reasoning |
|---------|:----------:|:------:|:-----:|-----------|
| "Test-first principle" | ✅ | ❌ | 5/6 | Universal, stable, cognitive, cross-cutting, compressible |
| "EXTEND>REBUILD" | ✅ | ❌ | 5/6 | Universal productivity principle, compresses well |
| "PostgreSQL 18 schema" | ❌ | ✅ | 0/6 | Project fact, domain-specific, evolving, not compressible |
| "31 gotchas catalog" | ❌ | ✅ | 1/6 | Reference material, large, domain-specific |
| "Top 5 critical rules" | ✅ | ❌ | 6/6 | Universal, stable, cognitive, cross-cutting, critical, compressible |
| "Bash commands catalog" | ❌ | ✅ | 1/6 | Universal BUT not cognitive, requires prose |

---

## Framework 2: Version Bump Criteria

**Semantic Versioning**: `vMAJOR.MINOR.PATCH`

```yaml
MAJOR (vX.0.0):
  When:
    - Architecture change (e.g., HOW/WHAT separation)
    - Breaking changes (skills renamed, structure changed)
    - Philosophy shift (fundamental approach change)
    - Drastic reduction/restructure (-50%+ size change)
  Example_Success: v3.2 → v4.0 (Pure DSL compression, -76%, -171 lines)
  Example_Breaking: v2.4 → v3.0 (HOW/WHAT separation, -57%)

MINOR (vX.Y.0):
  When:
    - New sections added (e.g., § ANTI-PATTERNS)
    - Significant enhancements (e.g., enforcement gates)
    - Pattern adoptions (e.g., MCO patterns)
    - Non-breaking additions
  Example_Success: v3.1 → v3.1.1 (minor fixes)
  Example_BLOAT: v3.0 → v3.1 (+125 lines MCO) → Caused bloat, corrected in v4.0

PATCH (vX.Y.Z):
  When:
    - Typo fixes
    - Small clarifications
    - Minor content updates (no structure change)
  Example: v3.1.0 → v3.1.1 (typo fixes)

NO_BUMP:
  When:
    - Whitespace, formatting only
    - Very minor edits
```

**Decision Flowchart**:
```
Change made
  ├─ Architecture? Breaking? Philosophy? Drastic? → YES → MAJOR (vX.0.0)
  ├─ New sections? Enhancement? Patterns? → YES → MINOR (vX.Y.0)
  ├─ Typo? Small? Clarification? → YES → PATCH (vX.Y.Z)
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

**Example** (MCO patterns evaluation):
```
§ PRINCIPLES:
  ✅ Universal (applies to all projects)
  ✅ Solves problem (cognitive foundations)
  ✅ Proven (MCO uses successfully)
  ✅ Benefit>cost (+6 lines, foundation clarity)
  ✅ Compatible (cognitive approach)
  → 5/5 ADOPT

§ QUICK COMMANDS (40 lines bash):
  ✅ Universal (make/curl commands)
  ⚠️ Solves problem (convenience, not cognitive)
  ✅ Proven (MCO uses)
  ❌ Benefit>cost (+40 lines, fails DSL compression test)
  ⚠️ Compatible (knowledge, not cognitive)
  → 2/5 REJECT (adopted in v3.1, removed in v4.0 after DSL compression test)

Dashboard-centric:
  ❌ Universal (MCO-specific architecture)
  ❌ Solves problem (we use skills ecosystem)
  → 0/5 REJECT
```

---

## Framework 4: DSL Compression Test

**Question**: Can this content compress to 1-line DSL without loss?

**Purpose**: Critical test to prevent bloat - if content requires prose/details/commands, it's KNOWLEDGE not COGNITIVE

**Test**:
```
Content to evaluate
  ├─ Express in 1 line DSL? → YES → CLAUDE.md (heuristic)
  ├─ Compress with acceptable loss? → MAYBE → Heuristic in CLAUDE.md + Details in skill
  └─ Requires details/prose/commands? → NO → Skill or README (knowledge)
```

**Examples**:

| Content | 1-line DSL? | Compressed Form | Verdict |
|---------|:-----------:|-----------------|---------|
| EXTEND>REBUILD principle | ✅ | `! EXTEND>REBUILD → copy.existing → adapt → 10x.faster` | CLAUDE.md ✅ |
| Test-First workflow | ✅ | `New.Feature → Test.First → Implement → Validate → Commit` | CLAUDE.md ✅ |
| Pre-test verification | ⚠️ | `! Pre.Test.Gate: TEST_DATABASE_URL ∧ EMBEDDING_MODE=mock` | CLAUDE.md (compressed) ✅ |
| Bash commands catalog | ❌ | `make up/down/test` (40 lines cannot compress) | README.md ❌ |
| Current EPIC state | ❌ | `EPIC-10 (27/35pts)` (volatile, not cognitive) | STATUS.md or git status ❌ |
| Version history | ❌ | Detailed changelog (17 lines) | git log ❌ |
| § CRITICAL FIRST STEP | ❌ | 15 lines bash (detailed commands) | Compress to heuristic ⚠️ |

**Real-World Impact** (v4.0 reduction):
```yaml
§ CRITICAL FIRST STEP (15 lines):
  Before: |
    ```bash
    echo $TEST_DATABASE_URL
    echo $EMBEDDING_MODE
    make up
    curl http://localhost:8001/health
    ```
  After (1 line DSL): "! Pre.Test.Gate: TEST_DATABASE_URL ∧ EMBEDDING_MODE=mock"
  Reduction: 15 → 1 line (-93%)

§ QUICK COMMANDS (40 lines):
  Before: make up/down/restart/test/db-shell/coverage...
  After: Removed (→ README.md or `make help`)
  Reduction: 40 → 0 lines (-100%)

§ CURRENT STATE (8 lines):
  Before: Completed: EPIC-06 (74pts)... In Progress: EPIC-10...
  After: Removed (volatile, → git status or STATUS.md)
  Reduction: 8 → 0 lines (-100%)
```

**Decision**:
- ✅ Compresses to 1 line → CLAUDE.md (pure heuristic)
- ⚠️ Compresses with loss → Heuristic in CLAUDE.md + Details in skill
- ❌ Cannot compress → README/STATUS/git log (not cognitive)

---

## Anti-Patterns (NEVER Add to CLAUDE.md)

**These patterns caused v3.1-v3.2 bloat (+146 lines), corrected in v4.0 (-171 lines)**

### 1. Commands.Catalog (40+ lines bash commands)

**Example**:
```bash
make up/down/restart/test/db-shell/coverage
curl http://localhost:8001/health
./apply_optimizations.sh test/apply/rollback
pytest tests/ -v --cov=api
```

❌ **Why Wrong**:
- Universal commands ≠ cognitive heuristics
- Fails DSL compression test (cannot express in 1 line)
- WHAT TO KNOW (commands) not HOW TO THINK (workflow)

✅ **Correct**: README.md or `make help` or documentation

---

### 2. Volatile.State (project status updates)

**Example**:
```yaml
§ CURRENT STATE:
  Completed: EPIC-06 (74pts) | EPIC-07 (41pts) | EPIC-08 (24pts)
  In Progress: EPIC-10 (27/35pts)
  Next: EPIC-10 Stories 10.4-10.5
  Branch: migration/postgresql-18
```

❌ **Why Wrong**:
- Changes weekly (not stable)
- Project-specific facts (not universal)
- Volatile state (not cognitive pattern)

✅ **Correct**: STATUS.md, git status, or git branch

---

### 3. Skill.Duplication (repeating skill content)

**Example**:
```yaml
§ ANTI-PATTERNS:
  NEVER:
    1. run.tests.without.TEST_DATABASE_URL
    2. use.sync.db.operations
    ...8 total
```

❌ **Why Wrong**:
- Anti-patterns catalog already in skill:claude-md-evolution
- Duplication violates DRY principle
- Skills auto-invoke, trust the system

✅ **Correct**: Reference skill only (`→ skill:mnemolite-gotchas`)

---

### 4. Version.History.Detailed (17+ lines changelog)

**Example**:
```markdown
§ VERSION HISTORY:
- v2.3.0 (2025-10-21): Initial compressed DSL format
- v2.4.0 (2025-10-21): Added skills ecosystem metadata
- v3.0.0 (2025-10-21): Pure cognitive engine architecture...
- v3.1.0 (2025-10-22): +§CRITICAL.FIRST.STEP +§CURRENT.STATE...
...
```

❌ **Why Wrong**:
- Git log is source of truth (duplication)
- Historical facts (not cognitive pattern)
- Grows unbounded over time

✅ **Correct**: git log, CHANGELOG.md, or 1-line footer reference

---

### 5. Universal ≠ Cognitive Confusion

**Example**:
```bash
§ CRITICAL FIRST STEP:
echo $TEST_DATABASE_URL  # Universal command ✅
make up                  # Universal command ✅
```

❌ **Why Wrong**:
- Commands are universal BUT not cognitive
- Universal ≠ cognitive (both criteria must pass!)
- Fails DSL compression test

✅ **Correct**: Compress to heuristic:
```
! Pre.Test.Gate: TEST_DATABASE_URL ∧ EMBEDDING_MODE=mock ∵ avoid{dev.DB.pollution}
```

**Key Insight**: Content can be universal BUT still KNOWLEDGE not COGNITIVE
- Universal bash commands = KNOWLEDGE → README
- Universal heuristics = COGNITIVE → CLAUDE.md DSL

---

## Lessons Learned (v3.0 → v4.0 Journey)

**Timeline**: 2025-10-21 to 2025-10-22 (3 iterations in 1 day)

### v3.0 (79 lines): Pure HOW/WHAT Separation ✅

**Changes**: CLAUDE.md v2.4 (88 lines) → v3.0 (79 lines, -10%)
**Strategy**: Created skill:mnemolite-architecture, migrated stack details
**Result**: SUCCESS - Clean HOW/WHAT separation
**Principle**: CLAUDE.md = HOW TO THINK, Skills = WHAT TO KNOW

---

### v3.1 (204 lines): MCO Patterns Adoption ❌ BLOAT

**Changes**: CLAUDE.md v3.0 (79 lines) → v3.1 (204 lines, +158%)
**Strategy**: Adopted 6 "universal" patterns from MCO project
**Result**: BLOAT +125 lines
**Mistake**:
- Adopted patterns without DSL compression test
- Confused "universal" with "cognitive"
- Added § QUICK COMMANDS (40 lines bash) - universal BUT not cognitive
- Added § CURRENT STATE (8 lines) - useful BUT volatile
- Added § CRITICAL FIRST STEP (15 lines) - important BUT not compressed

**Pattern**: Framework 3 (Pattern Adoption) passed 5/5 ✅ BUT missed DSL compression test!

---

### v3.2 (225 lines): Meta-Skill Enrichment ❌ MORE BLOAT

**Changes**: CLAUDE.md v3.1 (204 lines) → v3.2 (225 lines, +10%)
**Strategy**: Created skill:claude-md-evolution, enriched § META section
**Result**: MORE BLOAT +21 lines
**Mistake**:
- Added § META details (validation protocol, maintenance frequency) - duplicates skill
- Added § ANTI-PATTERNS catalog - duplicates skill:claude-md-evolution content
- Didn't apply own frameworks (skill duplication anti-pattern)

**Pattern**: Meta-skill helped but also caused bloat by adding knowledge to CLAUDE.md

---

### v4.0 (54 lines): Pure Cognitive DSL ✅ SUCCESS

**Changes**: CLAUDE.md v3.2 (225 lines) → v4.0 (54 lines, -76%)
**Strategy**: Applied DSL Compression Test - "Can express in 1 line DSL?"
**Result**: SUCCESS -171 lines
**Solution**:
- Removed § CRITICAL FIRST STEP (15 lines) → compressed to 1 heuristic
- Removed § CURRENT STATE (8 lines) → volatile, not cognitive
- Removed § QUICK COMMANDS (40 lines) → README.md
- Removed § VERSION HISTORY (17 lines) → git log
- Removed § ANTI-PATTERNS details (18 lines) → skill only
- Removed § SKILLS.ECOSYSTEM (12 lines) → auto-discovery
- Compressed § META (47 lines → 12 lines) → essence only

**Principle Discovered**: Framework 4 (DSL Compression Test) = CRITICAL missing test

---

### Key Insights

**1. Universal ≠ Cognitive**:
- Bash commands can be universal (apply to all projects)
- BUT they're KNOWLEDGE (WHAT), not COGNITIVE (HOW)
- Both "universal" AND "cognitive" criteria must pass!

**2. DSL Compression = Litmus Test**:
- If cannot compress to 1-line DSL → NOT CLAUDE.md
- Heuristics compress well: `EXTEND>REBUILD → copy → adapt`
- Commands don't compress: `make up && curl localhost:8001/health`

**3. Framework 3 Insufficient Without Framework 4**:
- Framework 3 (Pattern Adoption): § CRITICAL FIRST STEP passed 5/5 ✅
- Framework 4 (DSL Compression): § CRITICAL FIRST STEP failed (15 lines bash) ❌
- BOTH tests needed to prevent bloat

**4. Meta-Skills Can Cause Bloat**:
- Creating skill:claude-md-evolution helped long-term
- BUT short-term caused bloat (enriched § META with duplicates)
- Must apply own frameworks to avoid irony

---

## Quick Reference

### Content Placement
```
New content
  ├─ Apply Framework 4 (DSL Compression Test)
  │  ├─ Compresses to 1 line? → YES → Continue to Framework 1
  │  └─ Requires details? → NO → Skill/README/STATUS
  ├─ Apply Framework 1 (HOW vs WHAT Test - 6 criteria)
  │  └─ ≥4/6 TRUE → CLAUDE.md
  └─ <4/6 TRUE → Skill (existing or new)
```

### Version Bump
```
Change
  ├─ Architecture/Breaking/Philosophy/Drastic? → MAJOR
  ├─ Sections/Enhancement/Patterns? → MINOR
  ├─ Typo/Small/Clarification? → PATCH
  └─ Formatting? → NO BUMP
```

### Pattern Adoption
```
External pattern
  ├─ Apply Framework 4 (DSL Compression)
  │  └─ Fails? → REJECT or compress
  ├─ Apply Framework 3 (5 criteria)
  │  └─ 5/5 → ADOPT (backup → validate)
  └─ <5 → REJECT (document why)
```

### Bloat Prevention
```
Before adding to CLAUDE.md
  ├─ Check Anti-Patterns (5 NEVER items)
  ├─ Run DSL Compression Test
  ├─ Run HOW vs WHAT Test (6 criteria)
  └─ All pass? → SAFE to add
```

---

## Key Rules (Summary)

```yaml
Core_Principle:
  CLAUDE.md: HOW TO THINK (principles, workflows, heuristics compressible to DSL)
  Skills: WHAT TO KNOW (facts, patterns, domain knowledge, details)

Decision_Criteria:
  Content_Placement: ≥4/6 criteria → CLAUDE.md | Else → Skill
  DSL_Compression: 1-line DSL possible → CLAUDE.md | Else → Skill/README
  Version_Bump: Architecture→MAJOR | Sections→MINOR | Small→PATCH
  Pattern_Adoption: All 5 criteria pass AND DSL compression → ADOPT | Else → REJECT

Evolution_Strategy:
  Bottom_up: Skills emerge from knowledge accumulation (~500+ lines)
  Top_down: Principles extracted when patterns repeat 3+ times
  Horizontal: Adopt universal patterns (filtered with 5 criteria + DSL compression)

Validation:
  Before: Backup (CLAUDE_vX.Y.Z_BACKUP.md) + Document intent + DSL compression test
  After: Session vierge test + Sanity check + No broken references
  Fail: Git revert immediately

Anti_Patterns (NEVER):
  Commands.Catalog: 40+ lines bash → README.md
  Volatile.State: Weekly updates → STATUS.md or git status
  Skill.Duplication: Repeat skill content → Reference skill only
  Version.History.Detailed: 17+ lines → git log or CHANGELOG.md
  Universal≠Cognitive: Universal commands ≠ cognitive heuristics → Compress or remove
```

---

**Version**: 3.0.0 (comprehensive frameworks + anti-patterns + lessons learned)
**Size**: 283 lines (vs 183 v2.0, +100 lines, +55%)
**Philosophy**: Frameworks for decisions, anti-patterns for prevention, lessons for wisdom
**Critical Addition**: Framework 4 (DSL Compression Test) - prevents bloat, ensures cognitive purity
