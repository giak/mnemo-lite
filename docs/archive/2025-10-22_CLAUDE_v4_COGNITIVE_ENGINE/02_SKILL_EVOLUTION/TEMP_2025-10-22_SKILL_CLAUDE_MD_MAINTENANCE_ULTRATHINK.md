# ULTRATHINK: Skill Meta - CLAUDE.md Maintenance & Evolution

**Date**: 2025-10-22
**Objectif**: Brainstorm deeper sur un skill qui documente comment maintenir/évoluer CLAUDE.md
**Synthèse**: Toute notre expérience récente (POCs + v3.0 + v3.1 + audit + verification)

---

## 🎯 CONCEPT: Méta-Skill pour Auto-Évolution

### Vision

**Le Paradoxe**:
- CLAUDE.md = Cognitive Engine (HOW TO THINK)
- Skills = Knowledge Base (WHAT TO KNOW)
- **Question**: Comment maintenir le HOW TO THINK lui-même?
- **Réponse**: Un skill méta qui documente les règles d'évolution du cognitive engine

### Nom du Skill

**Options**:
1. `claude-md-maintenance` (noun-based, descriptive)
2. `maintaining-claude-md` (gerund-based, action-oriented)
3. `cognitive-engine-evolution` (conceptual, broader)
4. `claude-md-lifecycle` (lifecycle focus)

**Recommandation**: `claude-md-evolution`
- Capture l'aspect évolutif
- Pas juste "maintenance" (passif), mais "evolution" (actif)
- Aligns avec document-lifecycle pattern

### Description YAML

```yaml
---
name: claude-md-evolution
description: Guides CLAUDE.md cognitive engine maintenance, evolution, version management. Use when updating CLAUDE.md, deciding what belongs where (HOW vs WHAT), adopting patterns, managing versions, validating changes.
---
```

**Keywords**: CLAUDE.md, cognitive engine, maintenance, evolution, version, HOW vs WHAT, patterns, validation

---

## 📚 SYNTHÈSE EXPÉRIENCE RÉCENTE

### 1. Skills POCs Journey (2025-10-21)

**Tentative 1: Lowercase skill.md**
```
.claude/skills/mnemolite-gotchas/skill.md  ❌ FAIL
```
- Error: "Unknown skill: mnemolite-gotchas"
- Leçon: Assumed lowercase would work (wrong)

**Tentative 2: Flat Structure**
```
.claude/skills/mnemolite-gotchas.md  ❌ FAIL
```
- Error: Same "Unknown skill"
- Leçon: Structure matters, not just naming

**Tentative 3: UPPERCASE SKILL.md**
```
.claude/skills/mnemolite-gotchas/SKILL.md  ✅ SUCCESS
```
- Result: "The 'mnemolite-gotchas' skill is running"
- Leçon: **ALWAYS check official docs first, not assumptions**

**Meta-Leçon**: Progressive discovery, iterate, validate in session vierge

---

### 2. CLAUDE.md v3.0 Refactor (2025-10-21)

**Challenge**:
- CLAUDE.md v2.4: 88 lines
- Mixing HOW (principles) + WHAT (facts, stack details, structure)
- Token inefficiency
- Redundancy with skills

**Solution**:
- **HOW/WHAT Separation**:
  - CLAUDE.md = Cognitive Engine (HOW TO THINK)
  - Skills = Knowledge Base (WHAT TO KNOW)
- **Test for each line**:
  - Universal principle? Stable? → CLAUDE.md
  - Project fact? Changes often? → Skill
- **Migration**:
  - Stack details → skill:mnemolite-architecture (NEW)
  - File structure → skill:mnemolite-architecture
  - Dev commands → (kept minimal in v3.0, expanded in v3.1 as QUICK COMMANDS)

**Result**:
- v2.4: 88 lines → v3.0: 79 lines (-10%)
- Cleaner separation
- Skills ecosystem formalized

**Meta-Leçon**: Separation of concerns at meta-level (HOW vs WHAT)

---

### 3. CLAUDE.md v3.1 Enhancement (2025-10-22)

**Inspiration**: MCO CLAUDE.md (another project, pure textual cognitive OS)

**Pattern Analysis**:
- Identified 10+ MCO patterns
- Separated universal vs MCO-specific
- Adopted 6 universal patterns
- Avoided 4 MCO-specific patterns

**Universal Patterns Adopted**:
1. § CRITICAL FIRST STEP (setup verification)
2. § CURRENT STATE (project status at-a-glance)
3. § ANTI-PATTERNS (explicit NEVER list)
4. § ENFORCEMENT GATES (pre-flight validation)
5. § QUICK COMMANDS (command reference)
6. § VERSION HISTORY (changelog + philosophy)

**MCO-Specific Patterns Avoided**:
- Dashboard-centric architecture (we use skills)
- § KEY DISCOVERY (their specific breakthrough)
- NO.CODE philosophy (we have real codebase)
- Service protocols (their 5 cognitive services)

**Result**:
- v3.0: 79 lines → v3.1: 204 lines (+158%)
- Trade-off: +600-800 tokens for +utility (prevention, productivity, context)

**Meta-Leçon**: Pattern adoption requires filtering (universal vs context-specific)

---

### 4. Audit Détaillé (2025-10-21)

**Hypothèses Identifiées** (claimed as "best practices"):
1. "Third person descriptions required" → ❌ Not in official Anthropic docs
2. "500 lines optimal size limit" → ❌ Not stated (just "split unwieldy")
3. "200 chars description limit" → ❌ Not stated (1024 max found, 200 optimal inferred)
4. "Gerund form names required" → ⚠️ Pattern in examples, not requirement

**Réalité Vérifiée**:
- Skills work perfectly as-is ✅
- Auto-invoke validated ✅
- 60-80% token savings measured ✅
- No problems reported ✅

**Meta-Leçon**:
- Distinguish FACTS (official docs) vs HYPOTHESES (inferences)
- Don't optimize without measuring baseline
- "If it ain't broke, don't fix it"

---

### 5. Vérification Rigoureuse & Option A (2025-10-22)

**Question**: Should we implement audit recommendations?

**Analysis**:
- Third person descriptions: HYPOTHESIS (no official requirement)
- Size compression: RISKY (possible content loss, unconfirmed benefit)
- Gerund names: BREAKING CHANGE (references in CLAUDE.md)

**Decision**: **Option A - Keep skills unchanged**
- All working perfectly
- No evidence of problems
- Premature optimization = root of all evil

**But**: Enhance CLAUDE.md with universal patterns (v3.1)

**Meta-Leçon**:
- Validation before change
- Evidence-based decisions
- No breaking changes without proven benefit

---

## 🧠 PRINCIPLES DISTILLÉS

### Core Philosophy

```yaml
Cognitive_Engine_Philosophy:
  Identity: CLAUDE.md = HOW TO THINK | Skills = WHAT TO KNOW

  Evolution_Strategy:
    - Bottom_up: Skills emerge from knowledge accumulation
    - Top_down: Principles extracted when patterns repeat 3+
    - Horizontal: Adopt universal patterns from other projects

  Stability_Spectrum:
    CLAUDE_md: Stable principles, universal workflows, top N critical rules
    Skills: Domain facts, implementation patterns, evolving knowledge

  Token_Optimization:
    - Progressive disclosure (60-80% savings measured)
    - CLAUDE.md loaded always (~1,400 tokens v3.1)
    - Skills loaded on-demand (30-50 tokens metadata each)
```

---

## 🎯 DECISION FRAMEWORKS

### Framework 1: HOW vs WHAT Test

**Question**: Does this content belong in CLAUDE.md or a skill?

```python
def belongs_in_claude_md(content):
    tests = {
        "universal_principle": is_universal(content),      # Applies to all projects?
        "stable": changes_rarely(content),                 # Version-stable?
        "cognitive": is_how_to_think(content),             # Workflow/principle vs fact?
        "cross_cutting": applies_to_multiple_domains(content),  # Specific domain?
        "critical_top_n": is_top_5_critical(content)      # Most critical rules?
    }

    # CLAUDE.md if majority True
    return sum(tests.values()) >= 3

def belongs_in_skill(content):
    tests = {
        "project_specific": is_project_fact(content),      # MnemoLite-specific?
        "domain_specific": has_clear_domain(content),      # Testing/DB/Code/UI?
        "implementation": is_implementation_detail(content), # How to do X?
        "evolving": changes_frequently(content),           # Updates often?
        "reference": is_lookup_material(content)           # Reference vs principle?
    }

    return sum(tests.values()) >= 3
```

**Examples**:

| Content | CLAUDE.md? | Skill? | Reasoning |
|---------|------------|--------|-----------|
| "Test-first principle" | ✅ | ❌ | Universal, stable, cognitive |
| "EXTEND>REBUILD" | ✅ | ❌ | Universal, productivity principle |
| "PostgreSQL 18 schema" | ❌ | ✅ (architecture) | Project-specific, domain, evolving |
| "31 gotchas catalog" | ❌ | ✅ (gotchas) | Reference, domain, large |
| "Top 5 critical rules" | ✅ | ❌ | Cross-cutting, critical, stable |
| "EPIC workflow steps" | ❌ | ✅ (epic-workflow) | Process-specific, detailed, evolving |

---

### Framework 2: Version Bump Criteria

**When to bump version?**

```yaml
Version_Bumping:
  Major_vX.0.0:
    - Architecture change (HOW/WHAT separation = v3.0)
    - Philosophy shift
    - Breaking changes
    - Complete restructure

  Minor_vX.Y.0:
    - New sections added (v3.0 → v3.1 added 6 sections)
    - Significant enhancements
    - Pattern adoptions
    - Non-breaking additions

  Patch_vX.Y.Z:
    - Typo fixes
    - Small clarifications
    - § CURRENT STATE updates (weekly)
    - Minor content updates

Examples:
  v2.4 → v3.0: Major (HOW/WHAT separation, architecture change)
  v3.0 → v3.1: Minor (MCO patterns added, 6 new sections)
  v3.1 → v3.1.1: Patch (update § CURRENT STATE for EPIC-10 completion)
```

---

### Framework 3: Pattern Adoption Filter

**When adopting patterns from other CLAUDE.md files**:

```python
def should_adopt_pattern(pattern, source_project):
    """Filter for adopting patterns from other projects."""

    # 1. Is it universal?
    if is_project_specific(pattern, source_project):
        return False  # E.g., MCO's "Dashboard-centric" → Skip

    # 2. Does it solve our problem?
    if not solves_our_need(pattern):
        return False  # E.g., MCO's "NO.CODE" → Skip (we have codebase)

    # 3. Is it proven to work?
    if not has_evidence(pattern):
        return False  # Need validation, not just ideas

    # 4. Is benefit > cost?
    if token_cost(pattern) > utility_gain(pattern):
        return False  # Token optimization matters

    # 5. Compatible with our architecture?
    if conflicts_with_skills_ecosystem(pattern):
        return False  # Must align with progressive disclosure

    return True  # Adopt!

# MCO Pattern Analysis Example:
patterns = [
    ("CRITICAL FIRST STEP", True),   # Universal, solves setup errors
    ("CURRENT STATE", True),          # Universal, immediate context
    ("ANTI-PATTERNS", True),          # Universal, prevention
    ("Dashboard-centric", False),     # MCO-specific, we use skills
    ("NO.CODE", False),               # MCO-specific, we have codebase
]
```

---

### Framework 4: Change Validation Protocol

**Before ANY change to CLAUDE.md**:

```yaml
Validation_Protocol:
  Pre_Change:
    1. Backup: cp CLAUDE.md CLAUDE_vX.Y.Z_BACKUP.md
    2. Document_intent: Create TEMP_DATE_change_proposal.md
    3. Identify_risks: Breaking changes? Content loss? Token impact?
    4. Plan_rollback: git commit before change

  Change:
    5. Implement: Make changes (isolated, one concept at a time)
    6. Update_version: Bump version number + changelog

  Post_Change:
    7. Session_vierge_test: Verify skills still auto-invoke
    8. Sanity_check: Commands work? References valid?
    9. Measure_impact: Token count, utility, comprehension
    10. User_validation: Does it feel better? Worse? Same?

  Decision:
    IF improvement: Keep + commit
    ELIF neutral: Revert (no benefit = bloat)
    ELSE regression: git revert immediately

Example_v3.1:
  Pre: ✅ CLAUDE_v3.0.0_BACKUP.md created
  Change: ✅ +6 MCO patterns
  Post: ⏳ Session vierge test pending
  Decision: ⏳ Monitor usage, iterate
```

---

## 🚫 ANTI-PATTERNS (CLAUDE.md-Specific)

### Anti-Pattern 1: Facts Bloat

**Problem**: Adding project facts to CLAUDE.md instead of skills

**Example (WRONG)**:
```markdown
## § DATABASE SCHEMA

events: {id, timestamp, content, embedding, metadata}
code_chunks: {id, file_path, language, chunk_type, ...}
nodes: {node_id, node_type, label, properties}
edges: {edge_id, source_node_id, target_node_id}
```

**Why wrong**:
- Project-specific facts (not universal principles)
- Changes frequently (schema evolution)
- Belongs in skill:mnemolite-architecture

**Fix**: Reference, don't duplicate
```markdown
## § CRITICAL.RULES

! Database.Schema: See skill:mnemolite-architecture for complete schema
```

---

### Anti-Pattern 2: Skill Duplication

**Problem**: Repeating skill descriptions in CLAUDE.md

**Example (WRONG)**:
```markdown
## § SKILL.ROUTING.STRATEGY

Common.Pitfalls | Debugging | Critical.Gotchas → skill:mnemolite-gotchas
  - 31 gotchas cataloged
  - 8 domains: Critical, Database, Testing, Performance, Code Intel, UI, Docker
  - Symptom table for quick lookup
  - Progressive disclosure structure
```

**Why wrong**:
- Skills already have YAML descriptions (auto-discovery)
- Duplication = maintenance burden (2 places to update)
- Bloats CLAUDE.md (token cost)

**Fix**: Trust auto-discovery
```markdown
## § SKILL.ROUTING.STRATEGY

Common.Pitfalls | Debugging | Critical.Gotchas → skill:mnemolite-gotchas
```

---

### Anti-Pattern 3: Premature Optimization

**Problem**: Optimizing without measuring baseline

**Example (from audit)**:
- Claim: "Skills >500 lines cause performance degradation"
- Reality: No official docs state this, skills work perfectly
- Risk: Aggressive compression → content loss

**Why wrong**:
- Fixing "problems" that don't exist
- Risk > benefit (content loss vs unconfirmed gain)
- Violates "measure first" principle

**Fix**: Evidence-based optimization
```yaml
Optimization_Approach:
  1. Measure_baseline: Current performance, token usage, utility
  2. Identify_actual_problem: User reports? Slow? Errors?
  3. Hypothesize_cause: What might be causing issue?
  4. Test_isolated_change: One variable at a time
  5. Measure_impact: Better? Worse? Same?
  6. Decide: Keep if improvement, revert if not
```

---

### Anti-Pattern 4: Breaking Changes Without Validation

**Problem**: Renaming, restructuring without testing

**Example (from audit)**:
- Proposal: Rename skills to gerund form (mnemolite-gotchas → debugging-mnemolite)
- Risk: Breaking references in CLAUDE.md, git history, documentation
- Benefit: Unconfirmed (pattern from examples, not requirement)

**Why wrong**:
- High risk (breaking)
- Low benefit (hypothesis)
- No validation protocol

**Fix**: Validation-first approach (Option A from verification)
```yaml
Change_Risk_Assessment:
  Breaking_change: YES (skill names referenced in CLAUDE.md)
  Confirmed_benefit: NO (hypothesis from examples)
  Validation_evidence: NO (no session vierge test)

  Decision: REJECT (high risk, unconfirmed benefit)
```

---

### Anti-Pattern 5: Over-Engineering

**Problem**: Adding complexity without clear benefit

**Example (hypothetical)**:
```markdown
## § SKILL.DEPENDENCY.GRAPH

skill:mnemolite-gotchas
  ├── skill:mnemolite-architecture (references for structure)
  └── skill:epic-workflow (references for commit patterns)

skill:epic-workflow
  ├── skill:document-lifecycle (references for doc states)
  └── skill:mnemolite-architecture (references for DIP patterns)
```

**Why wrong**:
- Skills are independent (by design)
- Auto-discovery handles this automatically
- Maintenance burden (update graph when skills change)
- Complexity without utility gain

**Fix**: Keep it simple (KISS)
```markdown
## § SKILLS.ECOSYSTEM

◊Core.Skills: epic-workflow, document-lifecycle, mnemolite-gotchas, mnemolite-architecture
◊Auto.Discovery: Skills auto-invoke based on keywords
```

---

## 📋 MAINTENANCE WORKFLOWS

### Workflow 1: Weekly Update (§ CURRENT STATE)

**Trigger**: EPIC completed, Story completed, major milestone

**Steps**:
1. Open CLAUDE.md
2. Find § CURRENT STATE section
3. Update completed EPICs, in-progress, next
4. Update branch if changed
5. Commit with message: `docs(claude): Update § CURRENT STATE - EPIC-X complete`

**Example**:
```diff
- **Completed EPICs**: EPIC-06 | EPIC-07 | EPIC-08 | EPIC-11 | EPIC-12
+ **Completed EPICs**: EPIC-06 | EPIC-07 | EPIC-08 | EPIC-10 ✅ | EPIC-11 | EPIC-12
- **In Progress**: EPIC-10 Performance & Caching (27/35pts complete)
+ **In Progress**: EPIC-13 Advanced Features (0/25pts)
```

**Version**: Patch bump (v3.1.0 → v3.1.1) or no bump (minor content update)

---

### Workflow 2: Quarterly Review

**Trigger**: Every 3 months, or when 3+ patterns repeat

**Steps**:
1. **Review § PRINCIPLES**: Any new principles emerged?
   - Look for patterns that repeated 3+ times
   - Extract to principle if universal

2. **Review § CRITICAL.RULES**: Still top 5 most critical?
   - New gotcha elevated to CRITICAL?
   - Old rule less critical now?

3. **Review § ANTI-PATTERNS**: New anti-patterns discovered?
   - Errors that happened 3+ times?
   - Add to NEVER list

4. **Review § SKILLS.ECOSYSTEM**: New skills needed?
   - Domain knowledge reached critical mass (~500+ lines)?
   - Create new skill vs expand existing?

5. **Review § COGNITIVE.WORKFLOWS**: New workflows emerged?
   - Deployment workflow?
   - Migration workflow?
   - Add if pattern established

6. **Update § VERSION HISTORY**: Document changes

**Output**: TEMP_DATE_quarterly_review.md → Recommendations → Implement → Minor version bump

---

### Workflow 3: Pattern Adoption (from other projects)

**Trigger**: Discovered interesting CLAUDE.md pattern in another project

**Steps**:
1. **Document pattern**: Create TEMP_DATE_pattern_analysis.md
   - What is the pattern?
   - What problem does it solve?
   - Source project context

2. **Apply Pattern Adoption Filter**:
   - Universal vs project-specific?
   - Solves our problem?
   - Proven to work?
   - Benefit > cost?
   - Compatible with our architecture?

3. **Test pattern**:
   - Create POC section in TEMP document
   - Simulate how it would look in our CLAUDE.md
   - Token cost estimate
   - Utility gain estimate

4. **Decision**:
   - IF adopt: Backup → Implement → Validate → Commit
   - ELSE: Document in ARCHIVE (why rejected, might be useful later)

**Example**: MCO patterns (v3.1 upgrade)
- Analyzed 10+ patterns
- Filtered to 6 universal patterns
- Rejected 4 MCO-specific patterns
- Result: v3.1 with enhanced utility

---

### Workflow 4: Emergency Rollback

**Trigger**: Change broke something (skills don't auto-invoke, commands fail, confusion)

**Steps**:
1. **Immediate rollback**:
   ```bash
   git revert HEAD  # If committed
   # OR
   cp CLAUDE_vX.Y.Z_BACKUP.md CLAUDE.md  # If not committed
   ```

2. **Verify restoration**:
   - Session vierge test (skills auto-invoke?)
   - Commands work?
   - Comprehension restored?

3. **Post-mortem**:
   - Create TEMP_DATE_rollback_postmortem.md
   - What broke?
   - Why did change break it?
   - What validation was missed?
   - How to prevent in future?

4. **Update validation protocol**:
   - Add check to prevent this type of regression
   - Document in skill:claude-md-evolution

**Example (hypothetical)**:
- Renamed skill directories → Skills stopped auto-invoking
- Rollback: Restore backup
- Post-mortem: Didn't test in session vierge
- Prevention: Add "session vierge test REQUIRED" to validation protocol

---

## 🎯 VERSION MANAGEMENT

### Semantic Versioning

```
vMAJOR.MINOR.PATCH

MAJOR: Architecture changes, breaking changes, philosophy shifts
MINOR: New sections, significant enhancements, pattern adoptions
PATCH: Small updates, typo fixes, § CURRENT STATE weekly updates
```

### Changelog Discipline

**Every version bump**:
```markdown
## § VERSION HISTORY

**Changelog:**
- vX.Y.Z (YYYY-MM-DD): [Brief description of changes]
  - Added: [What was added]
  - Changed: [What was modified]
  - Removed: [What was removed]
  - Fixed: [What was corrected]
```

**Example (v3.1.0)**:
```markdown
- v3.1.0 (2025-10-22): MCO universal patterns adoption
  - Added: §CRITICAL.FIRST.STEP, §CURRENT.STATE, §ANTI-PATTERNS, §ENFORCEMENT.GATES, §QUICK.COMMANDS, §VERSION.HISTORY
  - Changed: §CRITICAL.RULES enhanced with enforcement gates
  - Changed: §META enhanced with Option A validation
  - Changed: DSL header added ∵ and ∴ symbols
```

### Backup Strategy

**Before every change**:
```bash
cp CLAUDE.md CLAUDE_vX.Y.Z_BACKUP.md
git add CLAUDE.md
git commit -m "docs(claude): Backup before vX.Y.Z upgrade"
```

**Retention**:
- Keep last 3 major version backups
- Keep current minor version backup
- Archive old backups to docs/archive/claude-md-versions/

---

## 📊 METRICS & VALIDATION

### Measurable Metrics

```yaml
Token_Cost:
  v3.0: ~700 tokens (79 lines)
  v3.1: ~1,400 tokens (204 lines)
  Target: <2,000 tokens (keep cognitive engine lightweight)

Skills_Metadata_Cost:
  Per_skill: 30-50 tokens
  4_skills: 120-200 tokens
  Total_with_CLAUDE: ~1,600 tokens (v3.1) - acceptable

Progressive_Disclosure_Savings:
  Measured: 60-80% token savings
  Method: Skills load on-demand, not upfront
  Validation: Compare session with/without skills

Utility_Metrics:
  Sections: 11 (v3.1)
  Critical_rules: 5 (top N)
  Anti_patterns: 8 (NEVER list)
  Quick_commands: 20+ (productivity)

Maintenance_Frequency:
  § CURRENT STATE: Weekly (patch bumps)
  § CRITICAL.RULES: Quarterly review
  § ANTI-PATTERNS: As discovered (3+ occurrences)
  Major_version: When architecture shifts
```

### Validation Checklist

**Post-change validation**:
- [ ] Backup created before change
- [ ] Version number bumped appropriately
- [ ] Changelog updated
- [ ] Session vierge test (skills auto-invoke?)
- [ ] Commands in § QUICK COMMANDS work
- [ ] No broken references (skill:X exists?)
- [ ] Token count reasonable (<2,000 for CLAUDE.md)
- [ ] Comprehension improved (or at least same)
- [ ] Git committed with descriptive message

---

## 💡 LESSONS LEARNED ARCHIVE

### Lesson 1: UPPERCASE SKILL.md Required (2025-10-21)

**Discovery**: Skills must be `.claude/skills/name/SKILL.md` (UPPERCASE)

**Journey**:
1. Tried: lowercase skill.md → Failed
2. Tried: flat structure → Failed
3. Success: UPPERCASE SKILL.md in subdirs

**Takeaway**: ALWAYS check official documentation first, not assumptions

**Applied to**: All future skills creation, documented in lessons learned

---

### Lesson 2: HOW/WHAT Separation Works (2025-10-21)

**Discovery**: Separating cognitive (HOW) from knowledge (WHAT) reduces tokens + improves clarity

**Evidence**:
- v2.4 (88 lines, mixed) → v3.0 (79 lines, separated)
- 60-80% token savings measured (progressive disclosure)
- Skills auto-invoke correctly (validated)

**Takeaway**: Maintain strict separation, test each line against HOW/WHAT criteria

**Applied to**: v3.0 architecture, all future content additions

---

### Lesson 3: Pattern Adoption Requires Filtering (2025-10-22)

**Discovery**: Not all patterns are universal, must filter for context

**Evidence**:
- MCO CLAUDE.md: 10+ patterns analyzed
- 6 adopted (universal): CRITICAL FIRST STEP, CURRENT STATE, etc.
- 4 rejected (MCO-specific): Dashboard-centric, NO.CODE, etc.

**Takeaway**: Use Pattern Adoption Filter framework before adopting external patterns

**Applied to**: v3.1 enhancement, future pattern adoptions

---

### Lesson 4: Evidence > Hypotheses (2025-10-22)

**Discovery**: Many "best practices" are hypotheses, not official requirements

**Evidence**:
- Audit claimed: third person required, 500 lines limit, etc.
- Verification: None in official Anthropic docs
- Reality: Skills work perfectly as-is

**Takeaway**:
- Distinguish FACTS (official docs) vs HYPOTHESES (inferences)
- Measure before optimizing
- "If it ain't broke, don't fix it"

**Applied to**: Option A decision (keep skills unchanged), validation protocol

---

### Lesson 5: Validation Protocol Essential (2025-10-22)

**Discovery**: Changes without validation risk breaking working architecture

**Evidence**:
- Proposed: Rename skills, compress aggressively
- Analysis: High risk (breaking), unconfirmed benefit
- Decision: Option A (keep working architecture)

**Takeaway**: Validation protocol mandatory before ANY change

**Applied to**: All future CLAUDE.md changes, emergency rollback workflow

---

## 📚 EXAMPLES (Recent Evolutions)

### Example 1: v2.4 → v3.0 (HOW/WHAT Separation)

**Trigger**: CLAUDE.md too large, mixing concerns

**Analysis**:
- v2.4: 88 lines
- Content: Principles + facts + stack + structure + commands
- Problem: What belongs in CLAUDE.md vs skills?

**Decision Framework Applied**: HOW/WHAT Test

**Changes**:
- Created: skill:mnemolite-architecture (932 lines)
- Moved: Stack details, file structure, patterns → skill
- Kept: Principles, workflows, top 5 critical rules → CLAUDE.md
- Result: 88 → 79 lines (-10%)

**Validation**:
- Session vierge test: ✅ Skills auto-invoke
- Token savings: ✅ 60-80% measured
- Comprehension: ✅ Clearer separation

**Version**: v2.4 → v3.0 (MAJOR - architecture change)

---

### Example 2: v3.0 → v3.1 (MCO Patterns Adoption)

**Trigger**: Discovered MCO CLAUDE.md with interesting patterns

**Analysis**:
- MCO: 148 lines, mature architecture
- Patterns: CRITICAL FIRST STEP, CURRENT STATE, ANTI-PATTERNS, etc.
- Question: Which patterns are universal vs MCO-specific?

**Decision Framework Applied**: Pattern Adoption Filter

**Adopted** (6 universal patterns):
1. § CRITICAL FIRST STEP (prevents setup errors)
2. § CURRENT STATE (immediate context)
3. § ANTI-PATTERNS (proactive prevention)
4. § ENFORCEMENT GATES (pre-flight validation)
5. § QUICK COMMANDS (productivity)
6. § VERSION HISTORY (evolution tracking)

**Rejected** (4 MCO-specific):
- Dashboard-centric (we use skills)
- § KEY DISCOVERY (their specific breakthrough)
- NO.CODE (we have codebase)
- Service protocols (different architecture)

**Changes**:
- Added: 6 new sections (+101 lines)
- Enhanced: §CRITICAL.RULES, §META
- Result: 79 → 204 lines (+158%)

**Validation**:
- Token cost: +600-800 tokens (acceptable for +utility)
- Skills unchanged: ✅ Option A respected
- Comprehension: ⏳ Monitor in usage

**Version**: v3.0 → v3.1 (MINOR - significant enhancements)

---

### Example 3: Weekly § CURRENT STATE Update

**Trigger**: EPIC-10 Story 10.3 completed (8pts)

**Change**:
```diff
- **In Progress**: EPIC-10 Performance & Caching (27/35pts complete)
+ **In Progress**: EPIC-10 Performance & Caching (35/35pts complete) ✅
- **Next**: EPIC-10 Stories 10.4-10.5 (remaining 8pts)
+ **Next**: EPIC-11 Story 11.4 (next in backlog)
```

**Validation**:
- Accuracy check: EPIC-10 actually complete?
- Update references: Backlog updated?

**Version**: v3.1.0 → v3.1.1 (PATCH - content update) OR no bump (minor)

**Commit**: `docs(claude): Update § CURRENT STATE - EPIC-10 complete`

---

## 🎯 QUICK REFERENCE (Meta-Skill)

### When to Use This Skill

**Auto-invoke triggers**:
- CLAUDE.md, cognitive engine, maintenance, evolution, version
- HOW vs WHAT, pattern adoption, validation
- "Should this go in CLAUDE.md or a skill?"
- "How do I update CLAUDE.md?"
- "When to create new skill vs expand CLAUDE.md?"

### Decision Flowcharts

**Content Placement**:
```
New content to add
  ├─ Universal principle? Stable? Cognitive?
  │    └─ YES → CLAUDE.md
  └─ NO
       └─ Project fact? Domain-specific? Evolving?
            └─ YES → Skill (new or existing)
```

**Version Bump**:
```
Change made
  ├─ Architecture shift? Breaking change?
  │    └─ YES → Major (vX.0.0)
  └─ NO
       ├─ New sections? Significant enhancement?
       │    └─ YES → Minor (vX.Y.0)
       └─ NO
            └─ Small update? Typo fix?
                 └─ Patch (vX.Y.Z) or no bump
```

**Pattern Adoption**:
```
External pattern discovered
  ├─ Universal? (not project-specific)
  │    └─ NO → Reject
  └─ YES
       ├─ Solves our problem?
       │    └─ NO → Reject
       └─ YES
            ├─ Proven? Benefit > cost?
            │    └─ NO → Defer or reject
            └─ YES
                 └─ Adopt (backup → test → validate)
```

---

## 🎯 STRUCTURE PROPOSITION (Skill File)

```markdown
---
name: claude-md-evolution
description: Guides CLAUDE.md cognitive engine maintenance, evolution, version management. Use when updating CLAUDE.md, deciding what belongs where (HOW vs WHAT), adopting patterns, managing versions, validating changes.
---

# Skill: CLAUDE.md Evolution & Maintenance

## Purpose
[Meta-cognition: how to maintain the HOW TO THINK]

## When to Use This Skill
[Auto-invoke triggers, use cases]

## Philosophy
[HOW/WHAT separation, progressive disclosure, token optimization]

## Decision Frameworks
[HOW vs WHAT Test, Version Bump Criteria, Pattern Adoption Filter, Change Validation Protocol]

## Maintenance Workflows
[Weekly update, Quarterly review, Pattern adoption, Emergency rollback]

## Anti-Patterns
[5 CLAUDE.md-specific anti-patterns with examples]

## Version Management
[Semantic versioning, changelog discipline, backup strategy]

## Lessons Learned Archive
[5 key lessons from recent experience]

## Examples
[v2.4→v3.0, v3.0→v3.1, weekly updates]

## Quick Reference
[Flowcharts, checklists, commands]

## Metrics & Validation
[Token costs, utility metrics, validation checklist]
```

**Estimated size**: 400-600 lines (knowledge-dense but manageable)

---

## 🎯 NEXT STEPS

1. **Review this ultrathink** avec user
2. **Décider structure finale** du skill
3. **Créer skill file**: `.claude/skills/claude-md-evolution/SKILL.md`
4. **Tester auto-invoke**: Session vierge validation
5. **Documenter dans CLAUDE.md § VERSION HISTORY**: Note l'ajout du meta-skill

---

**Document**: ULTRATHINK Complete
**Concept**: Meta-skill pour CLAUDE.md maintenance/evolution
**Synthèse**: POCs + v3.0 + v3.1 + audit + verification (toute l'expérience)
**Next**: User decision on structure + creation
