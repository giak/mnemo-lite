# ULTRATHINK: CLAUDE.md = Pure Cognitive Engine DSL

**Date**: 2025-10-22
**Problème**: CLAUDE.md v3.2 = 225 lignes, trop lourd, trop de knowledge
**Objectif**: Retour au principe - Moteur cognitif pur en DSL compressé
**Cible**: ~100-120 lignes max

---

## 🧠 QU'EST-CE QU'UN MOTEUR COGNITIF?

### Définition Profonde

**Moteur Cognitif ≠ Base de Connaissance**

| Aspect | Moteur Cognitif | Base de Connaissance |
|--------|----------------|---------------------|
| **Rôle** | HOW TO THINK | WHAT TO KNOW |
| **Nature** | Heuristiques | Faits |
| **Format** | DSL compressé | Prose détaillée |
| **Stabilité** | Ultra-stable | Évolue fréquemment |
| **Scope** | Universel | Contextuel |
| **Exemples** | Patterns de pensée, workflows, principes | Gotchas, règles détaillées, catalogues |

### Le Test Ultime: Compression Sémantique

**Question**: Peut-on exprimer ce concept en 1 ligne DSL sans perte de sens?

**Exemples**:

**COGNITIF** (compressible):
```
Principe: EXTEND>REBUILD
DSL: EXTEND>REBUILD ∧ copy.existing → adapt → 10x.faster
Compression: ✅ 1 ligne, sens préservé
```

**KNOWLEDGE** (non compressible sans perte):
```
Anti-Pattern: Facts.Bloat
Détail: "Add project facts to CLAUDE.md (use skill reference instead)"
DSL tenté: Facts.Bloat → skill.ref
Compression: ⚠️ Perd le contexte, nécessite explication
→ Devrait être dans skill, pas moteur cognitif
```

### Les 3 Niveaux de Cognition

**Niveau 1: Meta-Cognition** (comment penser)
- Principes universels
- Patterns de décision
- Workflows génériques
→ DOIT être dans CLAUDE.md

**Niveau 2: Domain-Cognition** (comment penser dans ce domaine)
- Patterns spécifiques au projet
- Règles métier
- Heuristiques contextuelles
→ DEVRAIT être dans skills

**Niveau 3: Knowledge** (quoi savoir)
- Faits
- Catalogues
- Exemples
→ DOIT être dans skills

---

## 🔍 AUDIT LIGNE PAR LIGNE: CLAUDE.md v3.2 (225 lignes)

### § CRITICAL FIRST STEP (lignes 7-21) - 15 lignes

**Contenu**:
```markdown
## § CRITICAL FIRST STEP

**ALWAYS verify before tests:**
```bash
echo $TEST_DATABASE_URL
echo $EMBEDDING_MODE
make up
curl http://localhost:8001/health
```

⚠️ **Violate = pollute dev DB or 2-minute model loading** → skill:mnemolite-gotchas/CRITICAL-01
```

**Analyse**:
- Type: **KNOWLEDGE** (commandes spécifiques, setup détaillé)
- Compressible en DSL? ❌ (perd les commandes exactes)
- Universel? ❌ (spécifique à MnemoLite setup)
- Devrait être: skill:mnemolite-gotchas ou skill:mnemolite-testing

**Verdict**: ❌ SUPPRIMER de CLAUDE.md → Migrer vers skill

**Compression DSL possible**:
```
! Pre.Test.Gate: TEST_DATABASE_URL ∧ EMBEDDING_MODE=mock ∧ services.up → skill:mnemolite-gotchas
```
1 ligne vs 15 lignes

---

### § CURRENT STATE (lignes 24-31) - 8 lignes

**Contenu**:
```markdown
## § CURRENT STATE

**Completed EPICs**: EPIC-06 (74pts) | EPIC-07 (41pts) | ...
**In Progress**: EPIC-10 Performance & Caching (27/35pts complete)
**Next**: EPIC-10 Stories 10.4-10.5 (remaining 8pts)
**Skills Active**: 4 operational
**Branch**: migration/postgresql-18
```

**Analyse**:
- Type: **KNOWLEDGE** (état factuel du projet)
- Compressible en DSL? ❌ (perd les détails)
- Universel? ❌ (100% spécifique au projet MnemoLite)
- Change: Weekly (très volatile)
- Devrait être: Séparé (STATUS.md? Dashboard? skill:epic-workflow?)

**Verdict**: ❌ SUPPRIMER de CLAUDE.md → Migrer vers STATUS.md ou skill

**Pourquoi**:
- Moteur cognitif = stable, universel
- Current state = volatile, contextuel
- Viole le principe de stabilité

---

### § IDENTITY (lignes 34-37) - 4 lignes

**Contenu**:
```markdown
## § IDENTITY

MnemoLite: PostgreSQL-based cognitive memory system with code intelligence
→ Full stack details: skill:mnemolite-architecture
```

**Analyse**:
- Type: **META-COGNITIVE** (identité du système)
- Compressible en DSL? ✅ (déjà compressé)
- Universel? ⚠️ (identité spécifique mais stable)
- Nécessaire? ⚠️ (orientation, mais pas vraiment "HOW TO THINK")

**Verdict**: ⚠️ OPTIONNEL → Garder si ultra-court, sinon supprimer

**Version ultra-compressée**:
```
§ IDENTITY: MnemoLite → skill:mnemolite-architecture
```
1 ligne vs 4 lignes

---

### § PRINCIPLES (lignes 41-46) - 6 lignes

**Contenu**:
```markdown
## § PRINCIPLES

◊Core: technical.objectivity ∧ factual ∧ challenge.assumptions → absolute.truth | ¬sycophancy
◊Dev: EXTEND>REBUILD ∧ Test.First ∧ Minimal.Change ∧ Progressive.Disclosure
◊Arch: async.first ∧ Protocol.Based.DI ∧ CQRS.inspired ∧ L1+L2+L3.cache
◊AI: Skills.Contextual → Invoke skills for knowledge | CLAUDE.md = HOW, Skills = WHAT
```

**Analyse**:
- Type: **META-COGNITIVE** ✅ (principes universels)
- Compressible en DSL? ✅ (déjà en DSL)
- Universel? ✅ (principes applicables partout)
- Stable? ✅ (change rarement)

**Verdict**: ✅ GARDER → Déjà optimal en DSL

**Note**: Parfait exemple de moteur cognitif compressé

---

### § COGNITIVE.WORKFLOWS (lignes 50-64) - 15 lignes

**Contenu**:
```markdown
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
```

**Analyse**:

**Decision.Frameworks** (lignes 52-56):
- Type: **META-COGNITIVE** ✅ (workflows de décision universels)
- Compressible? ✅ (déjà en DSL)
- Universel? ✅ (workflows applicables à tout projet)

**Verdict**: ✅ GARDER

**Skill.Routing.Strategy** (lignes 58-64):
- Type: **KNOWLEDGE** ❌ (liste des skills, leurs domaines)
- Compressible? ⚠️ (peut être compressé mais...)
- Universel? ❌ (spécifique à nos skills MnemoLite)
- Redondant? ✅ (skills ont déjà descriptions YAML)
- Devrait être: Auto-discovery (pas besoin de lister)

**Verdict**: ❌ SUPPRIMER → Trust auto-discovery

**Pourquoi supprimer Skill.Routing**:
- Skills auto-invoke basé sur YAML descriptions
- Lister ici = duplication
- Si on ajoute nouveau skill, faut update 2 endroits
- Viole DRY (Don't Repeat Yourself)

---

### § CRITICAL.RULES (lignes 67-82) - 16 lignes

**Contenu**:
```markdown
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
```

**Analyse**:

**Top 5 Critical Rules** (lignes 69-73):
- Type: **MIXED** ⚠️
  - EXTEND>REBUILD: META-COGNITIVE ✅ (principe universel)
  - Skills.First: META-COGNITIVE ✅ (méta-principe)
  - TEST_DATABASE_URL, Async.Everything, Protocol.DI: **KNOWLEDGE** ❌ (règles projet-spécifiques)
- Compressible? ⚠️ (partiellement)
- Universel? ⚠️ (2/5 universels, 3/5 projet-spécifiques)

**Enforcement Gates** (lignes 77-82):
- Type: **KNOWLEDGE** ❌ (règles de validation détaillées)
- Compressible? ❌ (perd les détails)
- Universel? ❌ (spécifique MnemoLite)
- Devrait être: skill:mnemolite-gotchas ou skill:claude-md-evolution

**Verdict**:
- ✅ GARDER principes universels (EXTEND>REBUILD, Skills.First)
- ❌ SUPPRIMER règles projet-spécifiques → Migrer vers skill:mnemolite-gotchas
- ❌ SUPPRIMER Enforcement Gates → Migrer vers skill:claude-md-evolution

**Compression possible**:
```
! EXTEND>REBUILD ∧ Test.First ∧ Skills.First → skill:[domain] ∀ details
```
1 ligne vs 16 lignes

---

### § ANTI-PATTERNS (lignes 85-102) - 18 lignes

**Contenu**:
```yaml
## § ANTI-PATTERNS (Never Do This)

```yaml
NEVER:
  1. run.tests.without.TEST_DATABASE_URL
  2. use.sync.db.operations
  3. rebuild.from.scratch
  4. skip.Protocol.implementation
  5. ignore.skills.knowledge
  6. use.EMBEDDING_MODE=real.in.tests
  7. modify.code.without.reading.first
  8. create.new.files.when.editing.works

Response.on.violation: 🚫 Anti-Pattern: [name] | Use: [alternative] | See: skill:[relevant-skill]
```

→ Full anti-patterns + gotchas: skill:mnemolite-gotchas (31 cataloged)
```

**Analyse**:
- Type: **KNOWLEDGE** ❌ (liste détaillée de règles)
- Compressible? ❌ (perd les détails spécifiques)
- Universel? ⚠️ (mix: #3,#7,#8 universels | #1,#2,#4,#5,#6 MnemoLite-spécifiques)
- Devrait être: skill:mnemolite-gotchas (déjà référencé ligne 101!)
- Redondant: ✅ (ligne 101 dit "Full anti-patterns: skill:mnemolite-gotchas")

**Verdict**: ❌ SUPPRIMER → Tout est déjà dans skill:mnemolite-gotchas

**Pourquoi c'est redondant**:
- Ligne 101: "Full anti-patterns + gotchas: skill:mnemolite-gotchas (31 cataloged)"
- Donc on liste 8 items ici + 31 dans skill = duplication
- Viole DRY principle

**Compression possible**:
```
! Anti.Patterns → skill:mnemolite-gotchas (31 cataloged) | skill:claude-md-evolution (frameworks)
```
1 ligne vs 18 lignes

---

### § SKILLS.ECOSYSTEM (lignes 105-116) - 12 lignes

**Contenu**:
```markdown
## § SKILLS.ECOSYSTEM

◊Philosophy: Progressive.Disclosure → Load knowledge on-demand (60-80% token savings measured)

◊Core.Skills:
  epic-workflow, document-lifecycle, mnemolite-gotchas, mnemolite-architecture, claude-md-evolution
  [future: mnemolite-testing, mnemolite-database, mnemolite-code-intel, mnemolite-ui]

◊Auto.Discovery: Skills have YAML frontmatter (name + description with keywords) → Claude auto-invokes when keywords match

◊Structure: .claude/skills/skill-name/SKILL.md (UPPERCASE required) → Official Claude Code spec
```

**Analyse**:

**Philosophy** (ligne 107):
- Type: **META-COGNITIVE** ✅ (principe architectural)
- Compressible? ✅ (déjà compressé)

**Core.Skills list** (lignes 109-111):
- Type: **KNOWLEDGE** ❌ (liste factuelle)
- Nécessaire? ❌ (auto-discovery works, why list?)
- Volatile? ✅ (change chaque fois qu'on ajoute skill)

**Auto.Discovery** (ligne 113):
- Type: **KNOWLEDGE** ❌ (comment marchent les skills)
- Universel? ⚠️ (Claude Code spec, pas MnemoLite-specific)
- Devrait être: skill:claude-md-evolution

**Structure** (ligne 115):
- Type: **KNOWLEDGE** ❌ (spécification technique)
- Universel? ⚠️ (Claude Code spec)
- Devrait être: skill:claude-md-evolution

**Verdict**:
- ✅ GARDER Philosophy (1 ligne)
- ❌ SUPPRIMER Core.Skills list → Redondant avec auto-discovery
- ❌ SUPPRIMER Auto.Discovery, Structure → Migrer vers skill:claude-md-evolution

**Compression possible**:
```
§ SKILLS: Progressive.Disclosure → 60-80% token.savings | Details → skill:claude-md-evolution
```
1 ligne vs 12 lignes

---

### § QUICK COMMANDS (lignes 119-158) - 40 lignes

**Contenu**: Dev Cycle, Testing, Database, Quick Checks, Performance commands

**Analyse**:
- Type: **KNOWLEDGE** ❌ (commandes spécifiques MnemoLite)
- Compressible? ❌ (perd les commandes exactes)
- Universel? ❌ (100% projet-spécifique)
- Devrait être: skill:mnemolite-gotchas ou COMMANDS.md ou README

**Verdict**: ❌ SUPPRIMER → Migrer vers README.md ou skill

**Pourquoi**:
- Moteur cognitif ≠ manuel utilisateur
- Commands changent (Makefile updates, scripts ajoutés)
- Volatile, contextuel, factuel
- 40 lignes = 18% de CLAUDE.md!

---

### § META (lignes 161-206) - 46 lignes

**Contenu**:
- Philosophy
- Update.Rules
- Decision.Framework
- Anti.Patterns (NEVER)
- Validation.Protocol
- Maintenance.Frequency
- Architecture.Proven
- Evolution.Strategy
- Next.Skills.Candidates

**Analyse détaillée**:

**Philosophy** (ligne 163):
- Type: **META-COGNITIVE** ✅
- Verdict: ✅ GARDER (1 ligne)

**Update.Rules** (lignes 165-169):
- Type: **META-COGNITIVE** ✅ (quand ajouter ici vs skill)
- Verdict: ✅ GARDER mais compresser

**Decision.Framework** (ligne 169):
- Type: **META-COGNITIVE** ✅ (référence au framework)
- Verdict: ✅ GARDER (1 ligne)

**Anti.Patterns (NEVER)** (lignes 171-176):
- Type: **KNOWLEDGE** ❌ (déjà dans § ANTI-PATTERNS lignes 85-102!)
- Verdict: ❌ SUPPRIMER (duplication)

**Validation.Protocol** (lignes 178-181):
- Type: **KNOWLEDGE** ❌ (procédure détaillée)
- Devrait être: skill:claude-md-evolution
- Verdict: ❌ SUPPRIMER

**Maintenance.Frequency** (lignes 183-188):
- Type: **KNOWLEDGE** ❌ (règles opérationnelles)
- Devrait être: skill:claude-md-evolution
- Verdict: ❌ SUPPRIMER

**Architecture.Proven** (lignes 190-194):
- Type: **KNOWLEDGE** ❌ (métriques, validation data)
- Verdict: ❌ SUPPRIMER

**Evolution.Strategy** (lignes 196-200):
- Type: **META-COGNITIVE** ⚠️ (principes d'évolution)
- Compressible? ✅
- Verdict: ✅ GARDER mais ultra-compresser

**Next.Skills.Candidates** (lignes 202-206):
- Type: **KNOWLEDGE** ❌ (roadmap, liste volatile)
- Verdict: ❌ SUPPRIMER

**Compression § META**:
```
§ META

◊Philosophy: CLAUDE.md = HOW (cognitive) | Skills = WHAT (knowledge)
◊Update.Rule: Universal ∧ stable ∧ cognitive → CLAUDE.md | Else → skill
◊Evolution: Bottom.up (skills@500+) ∧ Top.down (principles@3x) ∧ Horizontal (patterns.filtered)
◊Validation: skill:claude-md-evolution (frameworks + protocols)
```

4 lignes vs 46 lignes (-91% réduction!)

---

### § VERSION HISTORY (lignes 208-225) - 18 lignes

**Contenu**: Version, Created, Last Updated, Changelog, Philosophy, Verification

**Analyse**:
- Type: **KNOWLEDGE** ❌ (historique factuel)
- Nécessaire? ⚠️ (traçabilité, mais est-ce un moteur cognitif?)
- Compressible? ⚠️ (peut être dans git commits)

**Verdict**: ⚠️ OPTIONNEL

**Options**:
1. Supprimer totalement (use git log)
2. Garder ultra-minimal (version + date seulement)
3. Migrer vers CHANGELOG.md

**Compression possible**:
```
v3.3.0 | 2025-10-22 | Cognitive.Engine.DSL | Changelog → git.log
```
1 ligne vs 18 lignes

---

## 📊 RÉCAPITULATIF AUDIT

### Répartition Actuelle (225 lignes)

| Section | Lignes | Type | Verdict |
|---------|--------|------|---------|
| DSL Header | 3 | Meta | ✅ GARDER |
| § CRITICAL FIRST STEP | 15 | KNOWLEDGE | ❌ SUPPRIMER → skill |
| § CURRENT STATE | 8 | KNOWLEDGE | ❌ SUPPRIMER → STATUS.md |
| § IDENTITY | 4 | Meta | ⚠️ COMPRESSER (1 ligne) |
| § PRINCIPLES | 6 | META-COGNITIVE | ✅ GARDER |
| § COGNITIVE.WORKFLOWS | 15 | MIXED | ✅ GARDER workflows, ❌ SUPPRIMER routing |
| § CRITICAL.RULES | 16 | MIXED | ⚠️ GARDER 2/5, ❌ SUPPRIMER rest |
| § ANTI-PATTERNS | 18 | KNOWLEDGE | ❌ SUPPRIMER → skill |
| § SKILLS.ECOSYSTEM | 12 | MIXED | ✅ GARDER 1 ligne, ❌ SUPPRIMER rest |
| § QUICK COMMANDS | 40 | KNOWLEDGE | ❌ SUPPRIMER → README |
| § META | 46 | MIXED | ✅ GARDER 4 lignes, ❌ SUPPRIMER rest |
| § VERSION HISTORY | 18 | KNOWLEDGE | ⚠️ COMPRESSER (1 ligne) |
| **TOTAL** | **225** | | **Cible: ~100-120** |

### Résumé

**À GARDER** (META-COGNITIVE, ~35-40 lignes):
- DSL Header (3 lignes)
- § PRINCIPLES (6 lignes)
- § COGNITIVE.WORKFLOWS/Decision.Frameworks (5 lignes)
- § META Philosophy + Update.Rule + Evolution (4 lignes)
- Principes universels compressés

**À SUPPRIMER** (~185 lignes):
- § CRITICAL FIRST STEP (15) → skill:mnemolite-gotchas
- § CURRENT STATE (8) → STATUS.md
- § ANTI-PATTERNS détaillé (18) → skill:mnemolite-gotchas
- § QUICK COMMANDS (40) → README.md
- § META détails (42) → skill:claude-md-evolution
- Skill.Routing.Strategy (7) → Auto-discovery
- Enforcement Gates (6) → skill:claude-md-evolution
- Core.Skills list (3) → Auto-discovery
- Next.Skills.Candidates (5) → Roadmap

**À COMPRESSER** (~80 lignes actuels → ~30 lignes DSL):
- § IDENTITY (4→1)
- § CRITICAL.RULES (16→2)
- § SKILLS.ECOSYSTEM (12→1)
- § META (46→4)
- § VERSION HISTORY (18→1)

**Réduction attendue**: 225 lignes → ~100-120 lignes (-47% à -56%)

---

## 🎯 PROPOSITION: CLAUDE.md v4.0 (Moteur Cognitif Pur DSL)

### Structure Cible (~100-120 lignes)

```markdown
# CLAUDE.md - MnemoLite Cognitive Engine

**DSL:** §=section ◊=concept →=flow ⊕=compose ∧=AND !=critical @=ref |=OR :=def ∵=because ∴=therefore

v4.0.0 | 2025-10-22 | Pure Cognitive Engine DSL

---

## § IDENTITY

MnemoLite → skill:mnemolite-architecture

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

◊Skill.Discovery: Auto.invoke → keywords.match → progressive.load → 60-80%.token.savings

---

## § CRITICAL.HEURISTICS

! EXTEND>REBUILD → copy.existing → adapt → 10x.faster | ¬rebuild.from.scratch
! Skills.First → query.skills → assume.less → progressive.disclosure
! Test.First → write.test → implement → validate → commit
! Measure.Before.Optimize → baseline → change → measure → decide(keep|revert)
! Validate.Before.Commit → backup → test → session.vierge → sanity.check → commit|revert

→ Detailed rules: skill:mnemolite-gotchas (31 gotchas) | skill:claude-md-evolution (frameworks)

---

## § META

◊Philosophy: CLAUDE.md = HOW (cognitive.engine.DSL) | Skills = WHAT (knowledge.base)

◊Update.Rule:
  CLAUDE.md ← Universal ∧ stable ∧ cognitive ∧ cross-cutting
  Skills ← Project-specific | domain-specific | evolving | detailed

◊Evolution:
  Bottom.up: Skills emerge@500+ lines
  Top.down: Principles extracted@3x.repeat
  Horizontal: Patterns adopted.filtered (skill:claude-md-evolution@5.criteria)

◊Maintenance → skill:claude-md-evolution (HOW vs WHAT Test, Version Bump, Pattern Adoption, Validation)

---

v4.0.0 | 2025-10-22 | Pure.Cognitive.Engine.DSL | Skills.Ecosystem@5.active | Changelog→git.log
```

**Ligne count**: ~55-60 lignes (vs 225 actuel, -73%)

---

## 💡 COMPRESSION DSL: Principes Appliqués

### Principe 1: Une Pensée = Une Ligne

**Avant (prose)**:
```markdown
! TEST_DATABASE_URL: Separate test DB ALWAYS required | Violate = pollute dev DB → skill:mnemolite-gotchas/CRITICAL-01
```

**Après (DSL heuristique)**:
```
! Skills.First → query.skills → assume.less
```

**Gain**: 10 mots → 4 concepts DSL

---

### Principe 2: Symboles > Mots

**Avant**:
```markdown
Add.Here: Universal principles, decision frameworks, top 5 critical rules, anti-patterns
Add.To.Skills: Facts, patterns, gotchas, implementation details, domain knowledge
```

**Après**:
```
CLAUDE.md ← Universal ∧ stable ∧ cognitive ∧ cross-cutting
Skills ← Project-specific | domain-specific | evolving | detailed
```

**Gain**: 20 mots → 8 concepts DSL avec symboles logiques

---

### Principe 3: Référence > Duplication

**Avant** (duplication):
```markdown
## § ANTI-PATTERNS

1. Facts.Bloat: Add project facts to CLAUDE.md
2. Skill.Duplication: Repeat skill descriptions
3. Premature.Optimization: Optimize without baseline
...8 items total

→ Full anti-patterns: skill:mnemolite-gotchas (31 cataloged)
```

**Après** (référence pure):
```
→ Rules: skill:mnemolite-gotchas (31) | skill:claude-md-evolution (frameworks)
```

**Gain**: 18 lignes → 1 ligne référence

---

### Principe 4: Heuristiques > Règles Détaillées

**Avant** (règle détaillée):
```yaml
Validation.Protocol:
  Before.Change: Backup (CLAUDE_vX.Y.Z_BACKUP.md) + Document intent + Risk analysis
  After.Change: Session vierge test + Sanity check (commands work, references valid)
  If.Regression: Git revert immediately + Post-mortem analysis
```

**Après** (heuristique compressée):
```
! Validate.Before.Commit → backup → test → session.vierge → commit|revert
```

**Gain**: 4 lignes détaillées → 1 ligne heuristique + référence skill pour détails

---

### Principe 5: Éliminer le Volatil

**Volatil** (change fréquemment):
- § CURRENT STATE (EPIC progress) → Weekly updates
- § QUICK COMMANDS (make targets) → Scripts change
- Next.Skills.Candidates (roadmap) → Planning changes
- Core.Skills list → Grows with new skills

**Solution**: Supprimer totalement → Migrer vers:
- STATUS.md (current state)
- README.md (commands)
- ROADMAP.md (next skills)
- Auto-discovery (skills list)

**Principe**: Moteur cognitif = stable | Knowledge = volatile

---

## 🎯 RECOMMANDATION FINALE

### CLAUDE.md v4.0: ~55-60 lignes (Pure Cognitive DSL)

**Sections**:
1. Header (DSL + version) - 3 lignes
2. § IDENTITY - 1 ligne
3. § PRINCIPLES - 6 lignes
4. § COGNITIVE.WORKFLOWS - 8 lignes
5. § CRITICAL.HEURISTICS - 8 lignes
6. § META - 12 lignes
7. Footer (version) - 1 ligne

**Total**: ~55-60 lignes

**Réduction**: 225 → 60 lignes (-73%)

---

### Migration Plan

**Créer nouveaux documents**:
- STATUS.md (§ CURRENT STATE content)
- README.md enrichi (§ QUICK COMMANDS)
- CHANGELOG.md (§ VERSION HISTORY détaillé)

**Migrer vers skills**:
- skill:mnemolite-gotchas:
  - § CRITICAL FIRST STEP details
  - § ANTI-PATTERNS détaillé (8 items)
  - § CRITICAL.RULES project-specific (3/5)
  - Enforcement Gates

- skill:claude-md-evolution:
  - § META Validation.Protocol détaillé
  - § META Maintenance.Frequency détaillé
  - § SKILLS.ECOSYSTEM Auto.Discovery, Structure specs

**Supprimer**:
- § CURRENT STATE (→ STATUS.md)
- § QUICK COMMANDS (→ README.md)
- Skill.Routing.Strategy (→ auto-discovery)
- Core.Skills list (→ auto-discovery)
- Next.Skills.Candidates (→ ROADMAP.md)
- Architecture.Proven (→ git history)

---

## 🧠 PHILOSOPHIE: Retour aux Sources

**Ce qu'est un moteur cognitif**:
- Heuristiques universelles (pas règles projet-spécifiques)
- Compression sémantique maximale (DSL, pas prose)
- Stabilité (change rarement, peut durer des mois)
- Meta-cognition (comment penser, pas quoi savoir)

**Ce qu'est une knowledge base** (skills):
- Faits détaillés (PostgreSQL schema, 31 gotchas)
- Prose explicative (pourquoi, comment, exemples)
- Volatilité (évolue avec projet)
- Domain-cognition (comment penser dans CE domaine)

**La règle d'or**:
> Si ça prend >1 ligne DSL pour exprimer → C'est du knowledge → Skills

**Le test ultime**:
> Est-ce que je peux appliquer cette heuristique dans un AUTRE projet sans modification?
> - OUI → CLAUDE.md
> - NON → Skill

---

**Document**: Ultrathink Complete
**Recommandation**: v4.0 = 55-60 lignes pure DSL (-73%)
**Next**: User decision sur migration
