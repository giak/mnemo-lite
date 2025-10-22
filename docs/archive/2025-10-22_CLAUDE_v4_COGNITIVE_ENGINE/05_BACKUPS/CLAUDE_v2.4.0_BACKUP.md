# CLAUDE.md - MnemoLite Cognitive Engine

**DSL:** §=section ◊=concept →=flow ⊕=compose ∧=AND !=critical @=loc |=OR {}=set :=def +=add ←=emph

v2.4.0 | 2025-10-21 | EPIC-06 (74pts) + EPIC-07 (41pts) + EPIC-08 (24pts) COMPLETE | EPIC-10 (35pts) In Progress | EPIC-11 (13pts) COMPLETE ✅ | EPIC-12 (13/23pts) COMPLETE ✅

## §IDENTITY

MnemoLite: PG18.cognitive.memory ⊕ pgvector ⊕ pg_partman ⊕ pgmq ⊕ Redis ⊕ CODE.INTEL
Stack: FastAPI ⊕ SQLAlchemy.async ⊕ asyncpg ⊕ Redis ⊕ sentence-transformers ⊕ tree-sitter ⊕ HTMX ⊕ Cytoscape.js
Arch: PG18.only ∧ CQRS ∧ DIP.protocols ∧ async.first ∧ EXTEND>REBUILD ∧ L1+L2+L3.cache

## §PRINCIPLES

◊Core: technical.objectivity ∧ factual ∧ challenge.assumptions → absolute.truth | ¬sycophancy
◊Meta: EXTEND>REBUILD ∧ Test.First ∧ Minimal.Change ∧ Protocol.Based.DI

## §COGNITIVE.WORKFLOWS

◊Task.Classification:
  EPIC|Story → skill:epic-workflow + context.skill
  Bug|Debug → skill:mnemolite-gotchas + skill:mnemolite-testing
  Architecture → skill:mnemolite-architecture + skill:document-lifecycle
  Database → skill:mnemolite-database
  UI → skill:mnemolite-ui
  Code.Intel → skill:mnemolite-code-intel
  Document.Management → skill:document-lifecycle

◊Decision.Framework:
  New.Feature → Test.First → Implement → Document → Commit
  Bug.Fix → Reproduce → Root.Cause → Fix → Regression.Test → Document
  Refactor → Benchmark → Implement → Verify → Rollback.If.Slower
  Architecture → Research(TEMP→DRAFT→RESEARCH) → Decide(DECISION) → Archive

◊Skill.Auto.Invocation:
  Mention{"EPIC","Story","completion","commit"} → epic-workflow
  Mention{"error","fail","debug","gotcha","slow"} → mnemolite-gotchas
  Mention{"test","pytest","fixture","mock"} → mnemolite-testing
  Mention{"database","schema","migration","PostgreSQL"} → mnemolite-database
  Mention{"architecture","DIP","protocol","CQRS"} → mnemolite-architecture
  Mention{"chunking","embedding","search","graph"} → mnemolite-code-intel
  Mention{"UI","HTMX","template","Cytoscape"} → mnemolite-ui
  Mention{"document","ADR","archive","TEMP","DECISION"} → document-lifecycle

## §DEV.OPS

◊Essential: make.{up, down, restart, test} + TEST_DATABASE_URL.ALWAYS + EMBEDDING_MODE=mock
◊Details → skill:mnemolite-gotchas

## §STRUCTURE.SUMMARY

api/{routes, services, repositories, models, utils, config} → PG18
! Full structure → skill:mnemolite-architecture (future)

## §CRITICAL.RULES

! TEST_DATABASE_URL.ALWAYS: Separate test DB required (skill:mnemolite-gotchas/CRITICAL-01)
! Async.All.DB: ALL database operations MUST be async/await (skill:mnemolite-gotchas/CRITICAL-02)
! Protocol.Required: New repos/services MUST implement Protocol (skill:mnemolite-gotchas/CRITICAL-03)
! EXTEND>REBUILD: Copy existing → adapt (10x faster) | Never rebuild from scratch
! Skills.Contextual: Invoke skills for detailed knowledge | CLAUDE.md = HOW TO THINK, Skills = WHAT TO KNOW

## §SKILLS.AVAILABLE

**Core Workflow**:
- **epic-workflow**: EPIC/Story management (analysis, implementation, completion reports, commit patterns)
- **document-lifecycle**: Doc management (TEMP→DRAFT→RESEARCH→DECISION→ARCHIVE lifecycle)

**Domain Knowledge**:
- **mnemolite-gotchas**: ✅ Common pitfalls, debugging, troubleshooting (31 gotchas cataloged)
- **mnemolite-testing**: [Future] pytest patterns, fixtures, mocks, coverage
- **mnemolite-database**: [Future] PG18 patterns, migrations, HNSW, JSONB, partitioning
- **mnemolite-architecture**: [Future] DIP, CQRS, layering, protocols, cache architecture
- **mnemolite-code-intel**: [Future] Chunking, embedding, search, graph, symbol paths
- **mnemolite-ui**: [Future] HTMX, SCADA theme, Cytoscape, templates

## §QUICK.REF

◊API: http://localhost:8001 | /docs | /health
◊EPICs: docs/agile/serena-evolution/03_EPICS/ → skill:epic-workflow
◊Gotchas: 31 cataloged → skill:mnemolite-gotchas
◊Tests: make api-test + TEST_DATABASE_URL + EMBEDDING_MODE=mock

## §META

Philosophy: Cognitive.Engine (this file) + Skill.Ecosystem (contextual KB)
Update.Rule: This file = HOW TO THINK (meta-rules, workflows) | Skills = WHAT TO KNOW (facts, patterns, gotchas)
Next.Skills: mnemolite-testing, mnemolite-database, mnemolite-architecture (create as needed)
