# CLAUDE.md - MnemoLite Cognitive Engine

**DSL:** §=section ◊=concept →=flow ⊕=compose ∧=AND !=critical @=ref |=OR :=def

v3.0.0 | 2025-10-21 | Cognitive Engine (HOW) + Skills Ecosystem (WHAT) | Token-Optimized Architecture

## §IDENTITY

MnemoLite: PostgreSQL-based cognitive memory system with code intelligence
→ Full stack details: skill:mnemolite-architecture

## §PRINCIPLES

◊Core: technical.objectivity ∧ factual ∧ challenge.assumptions → absolute.truth | ¬sycophancy
◊Dev: EXTEND>REBUILD ∧ Test.First ∧ Minimal.Change ∧ Progressive.Disclosure
◊Arch: async.first ∧ Protocol.Based.DI ∧ CQRS.inspired ∧ L1+L2+L3.cache
◊AI: Skills.Contextual → Invoke skills for knowledge | CLAUDE.md = HOW, Skills = WHAT

## §COGNITIVE.WORKFLOWS

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

## §CRITICAL.RULES

! TEST_DATABASE_URL: Separate test DB ALWAYS required | Violate = pollute dev DB → skill:mnemolite-gotchas/CRITICAL-01
! Async.Everything: ALL DB operations MUST be async/await | Violate = RuntimeWarning → skill:mnemolite-gotchas/CRITICAL-02
! EXTEND>REBUILD: Copy existing pattern, adapt (10x faster) | Never rebuild from scratch
! Protocol.DI: New repos/services MUST implement Protocol interface → skill:mnemolite-architecture
! Skills.First: Query skills for details before assumptions | Skills = knowledge base, auto-invoke on keywords

→ Full critical rules catalog (31 gotchas): skill:mnemolite-gotchas

## §SKILLS.ECOSYSTEM

◊Philosophy: Progressive.Disclosure → Load knowledge on-demand (60-80% token savings measured)

◊Core.Skills:
  epic-workflow, document-lifecycle, mnemolite-gotchas, mnemolite-architecture
  [future: mnemolite-testing, mnemolite-database, mnemolite-code-intel, mnemolite-ui]

◊Auto.Discovery: Skills have YAML frontmatter (name + description with keywords) → Claude auto-invokes when keywords match

◊Structure: .claude/skills/skill-name/SKILL.md (UPPERCASE required) → Official Claude Code spec

## §META

Philosophy: This file = Cognitive Engine (HOW TO THINK) | Skills = Knowledge Base (WHAT TO KNOW)

Update.Rules:
  Add.Here: Universal principles, decision frameworks, top 3-5 critical rules only
  Add.To.Skills: Facts, patterns, gotchas, implementation details, domain knowledge
  Test: If fact/pattern changes frequently → Skill | If principle stable → CLAUDE.md

Architecture.Proven:
  Skills.Auto.Invoke: ✅ Validated in production (session vierge tested)
  Progressive.Disclosure: ✅ 60-80% token savings measured
  Token.Cost: ~30-50 tokens per skill at startup (metadata only)

Evolution.Strategy:
  Create.Skill.When: Domain knowledge reaches ~500+ lines critical mass
  Review.Quarterly: Realign CLAUDE.md + skills, extract new principles if patterns repeat 3+
  Hierarchical.CLAUDE.md: Deferred (no proven need, skills pattern works well)

Next.Skills.Candidates:
  mnemolite-testing (pytest, fixtures, mocks, coverage strategies)
  mnemolite-database (PG18 specifics, HNSW tuning, JSONB patterns, partitioning)
  mnemolite-code-intel (chunking, embeddings, search, graph construction)
  mnemolite-ui (HTMX patterns, SCADA theme, Cytoscape, templates)
