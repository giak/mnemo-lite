# CLAUDE.md - MnemoLite Cognitive Engine

**DSL:** §=section ◊=concept →=flow ⊕=compose ∧=AND !=critical @=ref |=OR :=def ∵=because ∴=therefore

v3.2.0 | 2025-10-22 | Cognitive Engine (HOW) + Skills Ecosystem (WHAT) | Token-Optimized Architecture

## § CRITICAL FIRST STEP

**ALWAYS verify before tests:**
```bash
# Check environment
echo $TEST_DATABASE_URL  # Must be set (separate test DB)
echo $EMBEDDING_MODE     # Should be "mock" (avoid 2min model loading)

# Verify services
make up                  # Docker services running
curl http://localhost:8001/health  # API healthy
```

⚠️ **Violate = pollute dev DB or 2-minute model loading** → skill:mnemolite-gotchas/CRITICAL-01

---

## § CURRENT STATE

**Completed EPICs**: EPIC-06 (74pts) | EPIC-07 (41pts) | EPIC-08 (24pts) | EPIC-11 (13pts) | EPIC-12 (13pts)
**In Progress**: EPIC-10 Performance & Caching (27/35pts complete)
**Next**: EPIC-10 Stories 10.4-10.5 (remaining 8pts)
**Skills Active**: 4 operational (gotchas, epic-workflow, architecture, document-lifecycle)
**Branch**: migration/postgresql-18

---

## § IDENTITY

MnemoLite: PostgreSQL-based cognitive memory system with code intelligence
→ Full stack details: skill:mnemolite-architecture

---

## § PRINCIPLES

◊Core: technical.objectivity ∧ factual ∧ challenge.assumptions → absolute.truth | ¬sycophancy
◊Dev: EXTEND>REBUILD ∧ Test.First ∧ Minimal.Change ∧ Progressive.Disclosure
◊Arch: async.first ∧ Protocol.Based.DI ∧ CQRS.inspired ∧ L1+L2+L3.cache
◊AI: Skills.Contextual → Invoke skills for knowledge | CLAUDE.md = HOW, Skills = WHAT

---

## § COGNITIVE.WORKFLOWS

◊Decision.Frameworks:
  New.Feature → Test.First → Implement.Minimal → Document → Commit
  Bug.Fix → Reproduce → Root.Cause → Fix → Regression.Test → Document
  Refactor → Benchmark.Before → Implement → Verify.Performance → Rollback.If.Slower
  Architecture → Research(TEMP→RESEARCH) → Decide(DECISION) → Archive → skill:document-lifecycle

◊Skill.Routing.Strategy:
  Implementation.Details | Project.Facts | Stack.Versions → skill:[domain-skill]
  Common.Pitfalls | Debugging | Critical.Gotchas → skill:mnemolite-gotchas
  EPIC.Management | Story.Workflow | Commits → skill:epic-workflow
  Architecture.Patterns | File.Structure | Design.Patterns → skill:mnemolite-architecture
  Document.Management | ADR.Lifecycle → skill:document-lifecycle

---

## § CRITICAL.RULES

! TEST_DATABASE_URL: Separate test DB ALWAYS required | Violate = pollute dev DB → skill:mnemolite-gotchas/CRITICAL-01
! Async.Everything: ALL DB operations MUST be async/await | Violate = RuntimeWarning → skill:mnemolite-gotchas/CRITICAL-02
! EXTEND>REBUILD: Copy existing pattern, adapt (10x faster) | Never rebuild from scratch
! Protocol.DI: New repos/services MUST implement Protocol interface → skill:mnemolite-architecture
! Skills.First: Query skills for details before assumptions | Skills = knowledge base, auto-invoke on keywords

→ Full critical rules catalog (31 gotchas): skill:mnemolite-gotchas

**Enforcement Gates** (pre-flight checks before operations):
- TEST.Gate: IF pytest ∧ ¬TEST_DATABASE_URL → REJECT ∵ dev.DB.pollution
- ASYNC.Gate: IF db.operation ∧ ¬await → REJECT ∵ RuntimeWarning
- PROTOCOL.Gate: IF new.repo|service ∧ ¬Protocol → REJECT ∵ DIP.violation
- EXTEND.Gate: IF rebuild.from.scratch ∧ existing.pattern.exists → REJECT ∵ 10x.slower

---

## § ANTI-PATTERNS (Never Do This)

```yaml
NEVER:
  1. run.tests.without.TEST_DATABASE_URL    # ∵ pollutes dev DB (CRITICAL-01)
  2. use.sync.db.operations                 # ∵ async.first principle (CRITICAL-02)
  3. rebuild.from.scratch                   # ∵ EXTEND>REBUILD 10x faster
  4. skip.Protocol.implementation           # ∵ breaks DIP architecture
  5. ignore.skills.knowledge                # ∵ skills = knowledge base (query first)
  6. use.EMBEDDING_MODE=real.in.tests       # ∵ 2-minute model loading (CRITICAL-05)
  7. modify.code.without.reading.first      # ∵ Edit tool requires Read first
  8. create.new.files.when.editing.works    # ∵ ALWAYS prefer editing existing

Response.on.violation: 🚫 Anti-Pattern: [name] | Use: [alternative] | See: skill:[relevant-skill]
```

→ Full anti-patterns + gotchas: skill:mnemolite-gotchas (31 cataloged)

---

## § SKILLS.ECOSYSTEM

◊Philosophy: Progressive.Disclosure → Load knowledge on-demand (60-80% token savings measured)

◊Core.Skills:
  epic-workflow, document-lifecycle, mnemolite-gotchas, mnemolite-architecture, claude-md-evolution
  [future: mnemolite-testing, mnemolite-database, mnemolite-code-intel, mnemolite-ui]

◊Auto.Discovery: Skills have YAML frontmatter (name + description with keywords) → Claude auto-invokes when keywords match

◊Structure: .claude/skills/skill-name/SKILL.md (UPPERCASE required) → Official Claude Code spec

---

## § QUICK COMMANDS

**Dev Cycle:**
```bash
make up                          # Start services (Docker)
make down                        # Stop services
make restart                     # Restart all services
make logs                        # View all logs
```

**Testing:**
```bash
make api-test                    # Run all tests (requires TEST_DATABASE_URL)
make api-test-file file=X        # Run specific test file
make api-test-one test=X         # Run single test
make coverage                    # Generate coverage report
pytest tests/ -v --cov=api       # Manual pytest
```

**Database:**
```bash
make db-shell                    # PostgreSQL shell
make db-backup                   # Backup database
make db-test-reset               # Reset test database
```

**Quick Checks:**
```bash
curl http://localhost:8001/health           # Health check
http://localhost:8001/docs                  # API docs (Swagger)
curl http://localhost:8001/v1/events/cache/stats | jq  # Cache stats
```

**Performance:**
```bash
./apply_optimizations.sh test      # Test optimizations
./apply_optimizations.sh apply     # Apply optimizations
./apply_optimizations.sh rollback  # Rollback (10s recovery)
```

---

## § META

Philosophy: This file = Cognitive Engine (HOW TO THINK) | Skills = Knowledge Base (WHAT TO KNOW)

Update.Rules:
  Add.Here: Universal principles, decision frameworks, top 5 critical rules, anti-patterns
  Add.To.Skills: Facts, patterns, gotchas, implementation details, domain knowledge
  Test: If fact/pattern changes frequently → Skill | If principle stable → CLAUDE.md
  Decision.Framework: skill:claude-md-evolution (HOW vs WHAT Test: ≥3/5 criteria → CLAUDE.md)

Anti.Patterns (NEVER):
  1. Facts.Bloat: Add project facts to CLAUDE.md (use skill reference instead)
  2. Skill.Duplication: Repeat skill descriptions in CLAUDE.md (trust auto-discovery)
  3. Premature.Optimization: Optimize without baseline measurement (measure first)
  4. Breaking.Changes: Rename/restructure without session vierge test (validation required)
  5. Over.Engineering: Add complexity without utility (KISS principle)

Validation.Protocol:
  Before.Change: Backup (CLAUDE_vX.Y.Z_BACKUP.md) + Document intent + Risk analysis
  After.Change: Session vierge test + Sanity check (commands work, references valid)
  If.Regression: Git revert immediately + Post-mortem analysis

Maintenance.Frequency:
  §.CURRENT.STATE: Weekly (or when EPIC/Story completes) → PATCH or NO BUMP
  §.CRITICAL.RULES: Quarterly review → MINOR if rules change
  §.ANTI.PATTERNS: When discovered (3+ occurrences) → MINOR
  §.PRINCIPLES: Quarterly review (extract when patterns repeat 3+) → MINOR
  Major.Version: Rare (architecture change, breaking changes) → MAJOR

Architecture.Proven:
  Skills.Auto.Invoke: ✅ Validated in production (session vierge tested)
  Progressive.Disclosure: ✅ 60-80% token savings measured
  Token.Cost: ~30-50 tokens per skill at startup (metadata only)
  Option.A.Validated: ✅ Keep current skills (no breaking changes)

Evolution.Strategy:
  Create.Skill.When: Domain knowledge reaches ~500+ lines critical mass
  Review.Quarterly: Realign CLAUDE.md + skills, extract new principles if patterns repeat 3+
  Hierarchical.CLAUDE.md: Deferred (no proven need, skills pattern works well)
  Optimization.Approach: Measure.First → Test.Isolated → Validate.Impact → Rollback.If.Worse

Next.Skills.Candidates:
  mnemolite-testing (pytest, fixtures, mocks, coverage strategies)
  mnemolite-database (PG18 specifics, HNSW tuning, JSONB patterns, partitioning)
  mnemolite-code-intel (chunking, embeddings, search, graph construction)
  mnemolite-ui (HTMX patterns, SCADA theme, Cytoscape, templates)

---

## § VERSION HISTORY

**Version:** 3.2.0
**Created:** 2025-10-21
**Last Updated:** 2025-10-22

**Changelog:**
- v2.3.0 (2025-10-21): Initial compressed DSL format
- v2.4.0 (2025-10-21): Added skills ecosystem metadata
- v3.0.0 (2025-10-21): Pure cognitive engine architecture (HOW/WHAT separation, -57% size reduction)
- v3.1.0 (2025-10-22): +§CRITICAL.FIRST.STEP +§CURRENT.STATE +§ANTI-PATTERNS +§ENFORCEMENT.GATES +§QUICK.COMMANDS +VERSION.HISTORY (MCO patterns adoption)
- v3.2.0 (2025-10-22): +skill:claude-md-evolution (meta-cognitive, 183 lines), +§META enrichment (anti-patterns, validation protocol, maintenance frequency)

**Philosophy:** Cognitive Engine (HOW TO THINK) + Skills Ecosystem (WHAT TO KNOW) → Progressive Disclosure → Token-Optimized → First 60 seconds = complete context.

**Verification:** Option A validated (keep current skills, no breaking changes) → All skills operational ✅ → Auto-invoke validated ✅ → 60-80% token savings measured ✅
