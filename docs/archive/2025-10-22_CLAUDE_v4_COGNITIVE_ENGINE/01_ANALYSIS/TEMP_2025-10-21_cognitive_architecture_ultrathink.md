# CLAUDE.md Architecture - Deep Think & Vision

**Date**: 2025-10-21
**Context**: Post-Skills Success - Repenser CLAUDE.md comme Cognitive Engine
**Objectif**: Définir architecture optimale CLAUDE.md (HOW TO THINK) + Skills (WHAT TO KNOW)

---

## 🎯 Vision Initiale vs État Actuel

### Vision Initiale (brainstorming)

**CLAUDE.md = Cognitive Engine**:
- HOW TO THINK (principes universels)
- Decision frameworks
- Workflow patterns
- Meta-rules

**Skills = Knowledge Base**:
- WHAT TO KNOW (facts, gotchas, patterns)
- Domain-specific knowledge
- Implementation details
- Auto-invoked contextually

**Hierarchical CLAUDE.md**:
- Root: Universal principles
- api/CLAUDE.md: API-specific rules
- tests/CLAUDE.md: Testing-specific rules
- Domain-contextual loading

### État Actuel (v2.4.0, 88 lines)

**CLAUDE.md contient**:
- ✅ §PRINCIPLES (HOW TO THINK) - Bon
- ⚠️ §IDENTITY (Stack tech) - Facts, devrait être skill?
- ✅ §COGNITIVE.WORKFLOWS - Bon (meta-patterns)
- ⚠️ §SKILLS.AVAILABLE - Redondant avec skills YAML?
- ⚠️ §CRITICAL.RULES - Duplications gotchas?
- ⚠️ §STRUCTURE.SUMMARY - Facts, devrait être skill?

**Skills existants**:
- ✅ mnemolite-gotchas (1208 lines, 31 gotchas, auto-invoke works)
- ✅ epic-workflow (810 lines, EPIC management)
- ✅ document-lifecycle (586 lines, doc patterns)

**Hierarchical CLAUDE.md**:
- ⏳ POC #2 validé comme faisable
- ❌ Pas implémenté (api/CLAUDE.md créé mais pas committé)
- ❓ Valeur réelle incertaine

---

## 🔬 Analyse Profonde - Section par Section

### §IDENTITY (Lines 7-11)

**Contenu actuel**:
```
MnemoLite: PG18.cognitive.memory ⊕ pgvector ⊕ pg_partman ⊕ pgmq ⊕ Redis ⊕ CODE.INTEL
Stack: FastAPI ⊕ SQLAlchemy.async ⊕ asyncpg ⊕ Redis ⊕ sentence-transformers ⊕ tree-sitter ⊕ HTMX ⊕ Cytoscape.js
Arch: PG18.only ∧ CQRS ∧ DIP.protocols ∧ async.first ∧ EXTEND>REBUILD ∧ L1+L2+L3.cache
```

**Type**: FACTS (stack, versions, architecture patterns)

**Question**: Est-ce du "HOW TO THINK" ou du "WHAT TO KNOW"?
- `PG18.cognitive.memory ⊕ pgvector` → FACT (WHAT)
- `EXTEND>REBUILD` → PRINCIPLE (HOW)
- `async.first` → PRINCIPLE (HOW)

**Analyse**:
- Mixed: Facts + Principles
- Facts devraient migrer vers skill (mnemolite-architecture)
- Principles devraient rester ou aller dans §PRINCIPLES

**Proposition**:
- Migrer stack details vers skill:mnemolite-architecture
- Garder identity statement ultra-minimal: "MnemoLite: PostgreSQL cognitive memory system"
- Migrer architectural principles (CQRS, DIP, async.first) vers §PRINCIPLES

---

### §PRINCIPLES (Lines 13-16)

**Contenu actuel**:
```
◊Core: technical.objectivity ∧ factual ∧ challenge.assumptions → absolute.truth | ¬sycophancy
◊Meta: EXTEND>REBUILD ∧ Test.First ∧ Minimal.Change ∧ Protocol.Based.DI
```

**Type**: PURE COGNITIVE (HOW TO THINK)

**Analyse**:
- ✅ Parfait pour cognitive engine
- ✅ Universal principles applicable partout
- ✅ Guide decision-making

**Proposition**: **KEEP AS IS** (peut-être expand légèrement)

---

### §COGNITIVE.WORKFLOWS (Lines 18-43)

**Contenu actuel**:
```
◊Task.Classification: EPIC|Story → skill:epic-workflow + context.skill
◊Decision.Framework: New.Feature → Test.First → Implement → Document → Commit
◊Skill.Auto.Invocation: Mention{"EPIC","Story"} → epic-workflow
```

**Type**: META-PATTERNS (HOW TO ROUTE THINKING)

**Analyse**:

**◊Task.Classification** (lines 20-27):
- ✅ Bon: Mapping mental tasks → skills
- ✅ Aide Claude savoir quel skill invoquer
- ⚠️ Mais: Skills ont déjà descriptions avec keywords
- ❓ Redondant?

**◊Decision.Framework** (lines 29-33):
- ✅ Excellent: Workflows génériques
- ✅ Pure cognitive (HOW TO APPROACH tasks)
- ✅ Universal patterns

**◊Skill.Auto.Invocation** (lines 35-43):
- ❌ Problème: Duplique info déjà dans skills YAML descriptions
- ❌ Maintenance burden: Changer 2 endroits (skill YAML + CLAUDE.md)
- ❓ Valeur ajoutée vs redondance?

**Proposition**:
- **KEEP**: ◊Decision.Framework (pure cognitive patterns)
- **REMOVE**: ◊Skill.Auto.Invocation (redondant avec skills YAML)
- **REFINE**: ◊Task.Classification → Plus générique, pas liste exhaustive skills

---

### §DEV.OPS (Lines 45-48)

**Contenu actuel**:
```
◊Essential: make.{up, down, restart, test} + TEST_DATABASE_URL.ALWAYS + EMBEDDING_MODE=mock
◊Details → skill:mnemolite-gotchas
```

**Type**: FACTS + REDIRECT

**Analyse**:
- ⚠️ `make.{up, down}` → Commands (FACTS)
- ✅ `TEST_DATABASE_URL.ALWAYS` → Critical rule (HOW)
- ✅ Redirect to skill → Good pattern

**Proposition**:
- Migrer commands vers skill:mnemolite-gotchas or mnemolite-devops
- Garder critical rule (`TEST_DATABASE_URL.ALWAYS`) si vraiment critique
- Ou simplifier: "◊DevOps → skill:mnemolite-gotchas + skill:mnemolite-devops"

---

### §STRUCTURE.SUMMARY (Lines 50-53)

**Contenu actuel**:
```
api/{routes, services, repositories, models, utils, config} → PG18
! Full structure → skill:mnemolite-architecture (future)
```

**Type**: FACTS (file structure)

**Analyse**:
- ❌ Pure facts (WHAT TO KNOW)
- ❌ Devrait être dans skill:mnemolite-architecture
- ✅ Redirect to skill is good

**Proposition**: **REMOVE** - Migrer vers skill:mnemolite-architecture

---

### §CRITICAL.RULES (Lines 55-61)

**Contenu actuel**:
```
! TEST_DATABASE_URL.ALWAYS: Separate test DB required (skill:mnemolite-gotchas/CRITICAL-01)
! Async.All.DB: ALL database operations MUST be async/await (skill:mnemolite-gotchas/CRITICAL-02)
! Protocol.Required: New repos/services MUST implement Protocol (skill:mnemolite-gotchas/CRITICAL-03)
! EXTEND>REBUILD: Copy existing → adapt (10x faster) | Never rebuild from scratch
! Skills.Contextual: Invoke skills for detailed knowledge | CLAUDE.md = HOW TO THINK, Skills = WHAT TO KNOW
```

**Type**: Mixed (PRINCIPLES + REDIRECTS)

**Analyse**:
- ❓ Duplication: Lines 1-3 référencent gotchas déjà dans skill
- ✅ Line 4: EXTEND>REBUILD → Pure principle (should be in §PRINCIPLES)
- ✅ Line 5: Meta-instruction on architecture (good)

**Question Critique**: Si skill:mnemolite-gotchas contient déjà CRITICAL-01, pourquoi répéter ici?

**Hypothèses**:
1. **Top-of-mind critical rules**: Garder les plus critiques dans CLAUDE.md pour quick access
2. **Redundancy for safety**: Critical rules méritent duplication
3. **Discovery mechanism**: CLAUDE.md lu au startup, skills on-demand

**Proposition**:
- **Option A** (Minimal): Supprimer duplication, garder seulement "→ skill:mnemolite-gotchas for critical rules"
- **Option B** (Top 3)**: Garder top 3 critical rules + redirect
- **Option C** (Current)**: Keep as is (redondant mais safe)

**Recommandation**: **Option B** - Top 3-5 critical rules + redirect

---

### §SKILLS.AVAILABLE (Lines 63-75)

**Contenu actuel**:
```
**Core Workflow**:
- **epic-workflow**: EPIC/Story management (analysis, implementation, completion reports, commit patterns)
- **document-lifecycle**: Doc management (TEMP→DRAFT→RESEARCH→DECISION→ARCHIVE lifecycle)

**Domain Knowledge**:
- **mnemolite-gotchas**: ✅ Common pitfalls, debugging, troubleshooting (31 gotchas cataloged)
- **mnemolite-testing**: [Future] pytest patterns, fixtures, mocks, coverage
- ...
```

**Type**: CATALOG (Skills inventory)

**Analyse**:

**Redondance Question**: Claude Code scans `.claude/skills/*/SKILL.md` au startup. Chaque skill a déjà:
```yaml
---
name: mnemolite-gotchas
description: MnemoLite debugging gotchas & critical patterns. Use for errors, failures...
---
```

**Donc**: Info déjà disponible via skills YAML descriptions.

**Valeur de §SKILLS.AVAILABLE**:
- ✅ Donne vue d'ensemble (catalog)
- ✅ Aide Claude comprendre skill ecosystem
- ❌ Redondant avec skills metadata
- ❌ Maintenance burden (update 2 places)

**Test à faire**: Supprimer §SKILLS.AVAILABLE, voir si Claude trouve skills aussi facilement?

**Proposition**:
- **Option A** (Remove): Supprimer, rely on skills auto-discovery
- **Option B** (Minimal)**: Garder liste noms seulement: "Skills: epic-workflow, mnemolite-gotchas, document-lifecycle, [future]..."
- **Option C** (Keep)**: Garder pour overview

**Recommandation**: **Option A** - Remove (let skills speak for themselves via YAML)

---

### §QUICK.REF (Lines 77-82)

**Contenu actuel**:
```
◊API: http://localhost:8001 | /docs | /health
◊EPICs: docs/agile/serena-evolution/03_EPICS/ → skill:epic-workflow
◊Gotchas: 31 cataloged → skill:mnemolite-gotchas
◊Tests: make api-test + TEST_DATABASE_URL + EMBEDDING_MODE=mock
```

**Type**: QUICK REFERENCES (Facts + redirects)

**Analyse**:
- ⚠️ Facts (URLs, paths, counts)
- ✅ Redirects to skills (good)

**Proposition**:
- Migrer facts vers skills
- Garder seulement redirects pattern: "◊Quick.Refs → skill:[appropriate-skill]"

---

### §META (Lines 84-88)

**Contenu actuel**:
```
Philosophy: Cognitive.Engine (this file) + Skill.Ecosystem (contextual KB)
Update.Rule: This file = HOW TO THINK (meta-rules, workflows) | Skills = WHAT TO KNOW (facts, patterns, gotchas)
Next.Skills: mnemolite-testing, mnemolite-database, mnemolite-architecture (create as needed)
```

**Type**: META-INSTRUCTIONS

**Analyse**:
- ✅ Excellent: Self-documenting architecture
- ✅ Helps Claude understand separation of concerns
- ✅ Pure meta-cognitive

**Proposition**: **KEEP AND EXPAND** - Critical for understanding architecture

---

## 🧠 Deep Think: HOW TO THINK vs WHAT TO KNOW

### Principe de Séparation

**HOW TO THINK (Cognitive Engine)**:
- Universal principles applicables partout
- Decision frameworks (comment aborder problèmes)
- Meta-patterns (comment router thinking)
- Architecture philosophy
- Ne change pas souvent (stable over time)

**WHAT TO KNOW (Knowledge Base)**:
- Facts (stack, versions, structure)
- Patterns spécifiques (code patterns, gotchas)
- Implementation details
- Domain-specific knowledge
- Change fréquemment (évolution projet)

### Test de Classification

Pour chaque ligne dans CLAUDE.md, demander:

**Question 1**: Est-ce un principe universel ou un fait spécifique?
- Principe → HOW TO THINK → CLAUDE.md
- Fact → WHAT TO KNOW → Skill

**Question 2**: S'applique à tous domaines ou domaine spécifique?
- Universel → CLAUDE.md
- Domaine-specific → Skill

**Question 3**: Change rarement ou fréquemment?
- Stable → CLAUDE.md
- Fréquent → Skill

**Examples**:

`EXTEND>REBUILD` principle:
- Q1: Principe ✅
- Q2: Universel ✅
- Q3: Stable ✅
- **→ CLAUDE.md**

`FastAPI 0.111+` version:
- Q1: Fact ✅
- Q2: Domain-specific (stack) ✅
- Q3: Change avec upgrades ✅
- **→ Skill (mnemolite-architecture)**

`TEST_DATABASE_URL must be set`:
- Q1: Principe ✅ (critical rule)
- Q2: Universal testing principle ✅
- Q3: Stable ✅
- **→ CLAUDE.md (critical rules) + Skill (gotchas for details)**

---

## 🏗️ Hierarchical CLAUDE.md - Deep Analysis

### POC #2 Findings (from POC_TRACKING.md)

**What was tested**:
- Created `api/CLAUDE.md` (35 lines, API-specific rules)
- Pattern: Root CLAUDE.md + domain CLAUDE.md
- Technical feasibility: ✅ Files coexist without conflicts

**Limitation**:
- Cannot test automatic contextual loading in single session
- Need multi-session testing from different CWDs

### Value Proposition

**Potential Benefits**:
1. **Contextual rules**: Different rules for api/ vs tests/ vs db/
2. **Reduced cognitive load**: Load only relevant domain rules when working in that directory
3. **Modularity**: Domain teams can maintain their own CLAUDE.md

**Potential Drawbacks**:
1. **Complexity**: Multiple CLAUDE.md files to maintain
2. **Fragmentation**: Hard to see full picture
3. **Uncertainty**: Not clear if Claude Code loads contextually or always from root

### Critical Question

**Does Claude Code load CLAUDE.md contextually based on CWD?**

**Hypothesis A**: Loads only root CLAUDE.md (CWD at session start)
- If true: Hierarchical pattern has NO VALUE
- Domain CLAUDE.md never loaded

**Hypothesis B**: Loads root + all CLAUDE.md in working paths
- If true: Hierarchical pattern has SOME VALUE
- But: How to control which loaded? Token overhead?

**Hypothesis C**: Loads contextually based on file being edited
- If true: Hierarchical pattern has HIGH VALUE
- Example: Editing api/services/foo.py → loads root + api/CLAUDE.md
- Token efficient

**Testing needed**:
1. Create api/CLAUDE.md with unique rule
2. Start session with CWD=project root
3. Edit file in api/
4. See if unique rule is followed
5. Repeat from different CWD

**Current state**: Hypothesis UNKNOWN (POC #2 not fully tested)

### Recommendation on Hierarchical CLAUDE.md

**Verdict**: ⏸️ **DEFER** until we can test properly

**Reasoning**:
1. Skills pattern is working well (60-80% token savings)
2. Hierarchical CLAUDE.md value is UNCERTAIN
3. Risk of over-complicating architecture
4. Focus on optimizing current CLAUDE.md first

**Future consideration**: If domain-specific rules accumulate, revisit

---

## 🎯 Optimal CLAUDE.md Architecture (Proposal)

### Design Principles

1. **Pure Cognitive Engine**: Only HOW TO THINK content
2. **Minimal Surface Area**: Reduce from 88 to ~40-50 lines
3. **Redirect to Skills**: For all WHAT TO KNOW content
4. **Self-Documenting**: §META explains architecture
5. **Stable Over Time**: Rarely needs updates (principles stable)

### Proposed Structure (v3.0)

```markdown
# CLAUDE.md - MnemoLite Cognitive Engine

**DSL:** [compressed DSL symbols]
**Version**: v3.0.0 | Date | EPICs status

## §IDENTITY

MnemoLite: PostgreSQL-based cognitive memory system with code intelligence

## §PRINCIPLES

◊Core: technical.objectivity ∧ factual ∧ challenge.assumptions → absolute.truth | ¬sycophancy
◊Dev: EXTEND>REBUILD ∧ Test.First ∧ Minimal.Change ∧ Progressive.Disclosure
◊Arch: async.first ∧ Protocol.Based.DI ∧ CQRS.inspired ∧ L1+L2+L3.cache
◊AI: Skills.Contextual → Invoke skills for knowledge | CLAUDE.md = HOW, Skills = WHAT

## §COGNITIVE.WORKFLOWS

◊Task.Approach:
  Feature → skill:epic-workflow (Test.First → Implement → Document → Commit)
  Bug → skill:mnemolite-gotchas (Reproduce → Root.Cause → Fix → Regression.Test)
  Refactor → Benchmark → Implement → Verify → Rollback.If.Slower
  Architecture → skill:document-lifecycle (TEMP→DRAFT→RESEARCH→DECISION)

◊Skill.Routing:
  Implementation.Details → skill:[domain-skill]
  Project.Facts → skill:[domain-skill]
  Critical.Gotchas → skill:mnemolite-gotchas
  Workflow.Patterns → skill:epic-workflow

## §CRITICAL.RULES

! TEST_DATABASE_URL: Separate test DB ALWAYS required → skill:mnemolite-gotchas/CRITICAL-01
! Async.Everything: ALL DB ops MUST be async/await → skill:mnemolite-gotchas/CRITICAL-02
! EXTEND>REBUILD: Copy existing pattern, adapt (~10x faster) | Never rebuild from scratch
! Skills.First: Query skills for details before assumptions

## §SKILLS

◊Available: epic-workflow, document-lifecycle, mnemolite-gotchas, [future: testing, database, architecture, code-intel, ui]
◊Discovery: Skills auto-invoke via description keywords
◊Details: Each skill has YAML frontmatter (name + description)

## §META

Philosophy: This file = Cognitive Engine (HOW TO THINK) | Skills = Knowledge Base (WHAT TO KNOW)
Update.Rule: Add here ONLY universal principles, decision frameworks, critical rules | Everything else → Skills
Architecture: Progressive disclosure via skills (60-80% token savings measured)
Next.Evolution: Create domain skills as knowledge accumulates (testing, database, architecture, code-intel, ui)
```

**Size**: ~40-45 lines (vs 88 currently)
**Reduction**: ~50% smaller
**Content**: Pure cognitive + redirects

---

## 📊 Migration Analysis

### What Moves to Skills

**From §IDENTITY**:
- Stack details (FastAPI, SQLAlchemy versions) → skill:mnemolite-architecture
- Technology list (pgvector, Redis, etc.) → skill:mnemolite-architecture

**From §COGNITIVE.WORKFLOWS**:
- ◊Skill.Auto.Invocation list → DELETE (redondant with skills YAML)

**From §DEV.OPS**:
- Commands (make.up, make.down) → skill:mnemolite-gotchas or new skill:mnemolite-devops

**From §STRUCTURE.SUMMARY**:
- Full file structure → skill:mnemolite-architecture

**From §CRITICAL.RULES**:
- Keep top 3-5, rest → skill:mnemolite-gotchas

**From §SKILLS.AVAILABLE**:
- Detailed descriptions → DELETE (in skills YAML already)
- Keep minimal list

**From §QUICK.REF**:
- URLs, paths, counts → Skills
- Keep redirects only

### Skills to Create

**skill:mnemolite-architecture** (NEW):
- Stack details (versions, dependencies)
- File structure
- Layering (routes → services → repos)
- DIP patterns, CQRS, protocols
- Cache architecture (L1+L2+L3)

**skill:mnemolite-devops** (NEW or merge into gotchas):
- Make commands
- Docker setup
- Environment variables
- Development workflow

**skill:mnemolite-database** (FUTURE):
- PG18 specifics
- HNSW index tuning
- JSONB patterns
- Partitioning (when enabled)
- Migration patterns

**skill:mnemolite-testing** (FUTURE):
- pytest patterns
- Fixtures
- Mocks (EMBEDDING_MODE=mock)
- Coverage strategies

**skill:mnemolite-code-intel** (FUTURE):
- Chunking strategies
- Dual embeddings
- Symbol path patterns
- Graph construction

**skill:mnemolite-ui** (FUTURE):
- HTMX patterns
- SCADA theme
- Cytoscape.js
- Template patterns

---

## 🔮 Vision & Roadmap

### Phase 1: CLAUDE.md Optimization (Now)

**Goal**: Reduce CLAUDE.md to pure cognitive engine (~40-50 lines)

**Actions**:
1. Create skill:mnemolite-architecture (migrate §IDENTITY, §STRUCTURE details)
2. Simplify §COGNITIVE.WORKFLOWS (remove redundant skill list)
3. Reduce §CRITICAL.RULES (top 3-5 + redirect)
4. Remove §SKILLS.AVAILABLE (rely on auto-discovery)
5. Simplify §QUICK.REF (redirects only)
6. Expand §META (document architecture philosophy)

**Deliverable**: CLAUDE.md v3.0 (~45 lines, 50% reduction)

**Timeline**: 1-2 hours

**Risk**: Low (skills already working, just refactoring CLAUDE.md)

### Phase 2: Complete Skill Ecosystem (Near Future)

**Goal**: Create comprehensive skill coverage

**Skills to create**:
1. **mnemolite-architecture** (Priority: HIGH) - Stack, structure, patterns
2. **mnemolite-devops** (Priority: MEDIUM) - Commands, Docker, env vars
3. **mnemolite-database** (Priority: MEDIUM) - PG18, HNSW, JSONB
4. **mnemolite-testing** (Priority: LOW) - pytest, fixtures, mocks

**Timeline**: Create as knowledge accumulates (not all at once)

**Strategy**: Create skill when domain reaches critical mass of knowledge (~500+ lines)

### Phase 3: Hierarchical CLAUDE.md (Far Future, Maybe)

**Goal**: Domain-specific cognitive rules IF needed

**Trigger**: Evidence that domain-specific HOW TO THINK rules accumulate
- Example: api/ has different decision patterns than tests/
- Example: db/ migrations require different workflow than code changes

**Prerequisites**:
1. Test and validate contextual loading behavior
2. Measure token overhead
3. Prove value > complexity cost

**Decision**: ⏸️ DEFER until clear need emerges

### Phase 4: Continuous Optimization (Ongoing)

**Practices**:
1. **Quarterly review**: CLAUDE.md + Skills alignment
2. **Knowledge capture**: New gotchas → skills, not CLAUDE.md
3. **Principle extraction**: If pattern repeats 3+ times → consider principle
4. **Token monitoring**: Measure actual savings in production

---

## 💡 Key Insights from Ultra-Think

### 1. Skills Success Validates Architecture

**Evidence**:
- Auto-invoke working ✅
- 60-80% token savings measured ✅
- Progressive disclosure validated ✅

**Implication**: Double down on skills, reduce CLAUDE.md

### 2. Redondance is Main Problem

**Identified**:
- §SKILLS.AVAILABLE duplicates skills YAML
- §COGNITIVE.WORKFLOWS/◊Skill.Auto.Invocation duplicates skills descriptions
- §CRITICAL.RULES partially duplicates gotchas

**Fix**: Eliminate redundancy, rely on single source of truth (skills)

### 3. CLAUDE.md Should Be Extremely Stable

**Observation**: If done right, CLAUDE.md should change RARELY
- Principles don't change
- Decision frameworks are universal
- Facts change → but facts are in skills now

**Test**: If we update CLAUDE.md weekly → something wrong (facts creeping in)

### 4. Hierarchical CLAUDE.md Value is Uncertain

**Problem**: Cannot validate without multi-session testing
**Risk**: Over-complicating architecture prematurely
**Decision**: Defer until proven need

### 5. "HOW vs WHAT" Test is Critical

**Use for every line**:
- HOW TO THINK? → CLAUDE.md
- WHAT TO KNOW? → Skill

**Grey area**: Critical rules (WHAT) that guide thinking (HOW)
- Solution: Minimal critical rules in CLAUDE.md + full details in skill

---

## ✅ Recommendations

### Immediate Actions (Next Session)

1. **Create skill:mnemolite-architecture**
   - Migrate §IDENTITY stack details
   - Migrate §STRUCTURE.SUMMARY
   - Add architecture patterns (DIP, CQRS, layers, cache)
   - Size: ~400-600 lines

2. **Refactor CLAUDE.md to v3.0**
   - Remove redundancies
   - Keep pure cognitive content
   - Add strong §META
   - Target: ~45 lines

3. **Test and validate**
   - Fresh session test
   - Measure token usage
   - Verify auto-invoke still works
   - Compare v2.4 vs v3.0

### Medium-Term (As Needed)

4. **Create skill:mnemolite-database** (when DB knowledge accumulates)
5. **Create skill:mnemolite-testing** (when testing patterns accumulate)
6. **Create skill:mnemolite-devops** (or merge into gotchas)

### Long-Term (Evaluate)

7. **Hierarchical CLAUDE.md**: Test properly, decide based on evidence
8. **Quarterly review**: CLAUDE.md + skills alignment
9. **Token monitoring**: Production measurements

---

## 🎯 Success Criteria

**CLAUDE.md v3.0 Success**:
- [ ] Size: ~40-50 lines (50% reduction from 88)
- [ ] Content: 100% HOW TO THINK (no facts)
- [ ] Auto-invoke: Still works (not broken by refactor)
- [ ] Token savings: Maintained or improved (60-80%+)
- [ ] Clarity: Easier to understand than v2.4
- [ ] Stability: Doesn't need updates for months

**Skills Ecosystem Success**:
- [ ] Coverage: All major domains have skills
- [ ] Discoverability: Auto-invoke works reliably
- [ ] Progressive disclosure: Measurable token savings
- [ ] Maintenance: Easy to add new gotchas/patterns

---

**Document**: Deep Think Complete
**Next**: Decision from user - proceed with Phase 1?
