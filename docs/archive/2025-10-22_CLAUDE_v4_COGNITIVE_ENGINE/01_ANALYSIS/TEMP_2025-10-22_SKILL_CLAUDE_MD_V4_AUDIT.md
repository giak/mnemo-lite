# Audit: skill:claude-md-evolution après CLAUDE.md v4.0

**Date**: 2025-10-22
**Context**: CLAUDE.md v3.2 (225 lignes) → v4.0 (54 lignes, -76%)
**Question**: Le skill est-il aligné avec la philosophie v4.0 "Pure Cognitive DSL"?

---

## 📊 État Actuel: skill v2.0 (183 lignes)

### Structure

```yaml
Frontmatter: name + description (3 lignes)
When to Use: 4 bullet points (6 lignes)
Framework 1: HOW vs WHAT Test (46 lignes)
Framework 2: Version Bump Criteria (42 lignes)
Framework 3: Pattern Adoption Filter (30 lignes)
Quick Reference: 3 flowcharts (26 lignes)
Key Rules Summary: YAML (20 lignes)
Footer: Version info (3 lignes)
```

**Total**: 183 lignes

---

## ✅ Ce qui est BON (à garder)

### Framework 1: HOW vs WHAT Test (lignes 21-45)

```markdown
| Criterion | CLAUDE.md if... | Skill if... |
|-----------|----------------|-------------|
| **Universal** | Applies to all projects | Project-specific fact |
| **Stable** | Rarely changes | Changes frequently |
| **Cognitive** | HOW TO THINK (workflow, principle) | WHAT TO KNOW (implementation, fact) |
| **Scope** | Cross-cutting multiple domains | Domain-specific (DB, Testing, UI) |
| **Critical** | Top 5 most critical rules | Reference material, catalog |

**Decision Rule**: Count criteria → ≥3 TRUE for CLAUDE.md → CLAUDE.md | Else → Skill
```

✅ **Bon**: Clair, actionable, tableau concis
⚠️ **Manque**: Critère "Compressible.1line.DSL" (nouveau dans v4.0!)

### Framework 2: Version Bump Criteria (lignes 48-89)

```yaml
MAJOR (vX.0.0):
  When: Architecture change, Breaking changes, Philosophy shift
  Example: v2.4 → v3.0 (HOW/WHAT separation, -57%)

MINOR (vX.Y.0):
  When: New sections, Enhancements, Pattern adoptions
  Example: v3.0 → v3.1 (+6 MCO patterns, +125 lines)

PATCH (vX.Y.Z):
  When: Typo fixes, Small clarifications, § CURRENT STATE updates
```

✅ **Bon**: Règles claires, flowchart
⚠️ **Problème**: Exemples obsolètes! v3.1 a causé bloat (+125 lignes), pas un succès!
⚠️ **Manque**: Exemple v3.2 → v4.0 (MAJOR: drastic reduction, -76%)

### Framework 3: Pattern Adoption Filter (lignes 93-123)

```markdown
**5-Criteria Checklist** (ALL must pass):
1. ☐ **Universal?** Not project-specific to source
2. ☐ **Solves our problem?** Addresses our actual need
3. ☐ **Proven?** Evidence it works in source project
4. ☐ **Benefit > cost?** Token cost justified by utility gain
5. ☐ **Compatible?** Aligns with skills ecosystem architecture
```

✅ **Bon**: Checklist claire, décision mécanique
❌ **PROBLÈME MAJEUR**: Exemple § CRITICAL FIRST STEP dit "ADOPT ✅" mais on vient de le SUPPRIMER dans v4.0!

**Exemple actuel** (lignes 110-117):
```
§ CRITICAL FIRST STEP:
  ✅ Universal (setup verification applies to all)
  ✅ Solves problem (prevents CRITICAL-01)
  ✅ Proven (MCO uses successfully)
  ✅ Benefit>cost (+15 lines, prevents hours debugging)
  ✅ Compatible (prevention approach)
  → 5/5 ADOPT
```

**Réalité v4.0**: SUPPRIMÉ! 15 lignes bash → 1 ligne heuristique DSL

### Key Rules Summary (lignes 156-177)

✅ **Bon**: YAML concis, capture l'essence
⚠️ **Manque**: Règle "compressible.1line.DSL" pas mentionnée

---

## ❌ Ce qui MANQUE (gaps critiques)

### Gap 1: Framework 4 - DSL Compression Test

**Absence**: Le skill ne mentionne JAMAIS le test "Peut-on exprimer en 1 ligne DSL?"

**Impact**: C'est le test CRITIQUE qui a permis v4.0! Sans ce test:
- § CRITICAL FIRST STEP (15 lignes bash) semblait "universal" donc OK
- § QUICK COMMANDS (40 lignes) semblait utile donc OK
- § CURRENT STATE (8 lignes) semblait informative donc OK

**Ce test aurait rejeté ces 3 sections immédiatement!**

### Gap 2: Anti-Patterns Bloat

**Absence**: Skill ne documente pas les anti-patterns qui ont causé v3.1→v3.2 bloat

**Anti-patterns manquants**:
1. **Commands.Catalog**: 40 lignes make/curl/pytest → README.md
2. **Volatile.State**: § CURRENT STATE → git status/STATUS.md
3. **Skill.Duplication**: § ANTI-PATTERNS déjà dans skill → suppression
4. **Version.History.Detailed**: 17 lignes changelog → git log
5. **Universal ≠ Cognitive**: Commandes universelles ≠ heuristiques cognitives

### Gap 3: Lessons Learned v3.1→v4.0

**Absence**: Skill ne capture pas l'expérience récente critique

**Lessons manquantes**:
- ❌ **v3.1 (+125 lignes)**: MCO patterns adoption sans filtrage DSL compression → BLOAT
- ❌ **v3.2 (+21 lignes)**: Meta-skill enrichment → duplication § ANTI-PATTERNS → BLOAT
- ✅ **v4.0 (-171 lignes)**: DSL compression test → pure cognitive engine → SUCCESS

**Insight profond manquant**: "Universel" ≠ "Cognitif"
- Commandes bash universelles = KNOWLEDGE
- Heuristiques universelles = COGNITIVE

### Gap 4: Exemples Obsolètes/Trompeurs

**Framework 2 Example** (ligne 66):
```yaml
Example: v3.0 → v3.1 (+6 MCO patterns, +125 lines)
```
❌ **Trompeur**: Présente v3.1 comme exemple MINOR réussi, mais c'est un BLOAT!

**Framework 3 Example** (lignes 111-117):
```
§ CRITICAL FIRST STEP:
  → 5/5 ADOPT
```
❌ **Obsolète**: Cette section a été SUPPRIMÉE dans v4.0!

---

## 🎯 Propositions d'Amélioration

### Proposition 1: Ajouter Framework 4 (DSL Compression Test)

**Nouveau framework** (~30 lignes):

```markdown
## Framework 4: DSL Compression Test

**Question**: Can this content compress to 1-line DSL without loss?

**Test**:
```
Content to evaluate
  ├─ Express in 1 line DSL? → YES → CLAUDE.md (heuristic)
  └─ Requires details/prose? → NO → Skill or README (knowledge)
```

**Examples**:

| Content | 1-line DSL? | Verdict | Compressed Form |
|---------|:-----------:|---------|-----------------|
| EXTEND>REBUILD principle | ✅ | CLAUDE.md | `! EXTEND>REBUILD → copy.existing → adapt → 10x.faster` |
| Test-First workflow | ✅ | CLAUDE.md | `New.Feature → Test.First → Implement → Validate → Commit` |
| Bash commands catalog | ❌ | README.md | `make up/down/test` (40 lines) → README |
| Current EPIC state | ❌ | STATUS.md | `EPIC-10 (27/35pts)` → Volatile, not cognitive |
| Version history | ❌ | git log | Detailed changelog → `git log` |
| § CRITICAL FIRST STEP | ⚠️ | Compress | 15 lines bash → `! Pre.Test.Gate: TEST_DATABASE_URL ∧ EMBEDDING_MODE=mock` |

**Decision**:
- ✅ Compresses → CLAUDE.md (1 line DSL)
- ⚠️ Compresses with loss → Skill (heuristic in CLAUDE.md, details in skill)
- ❌ Cannot compress → README/STATUS/git log
```

**Justification**: Ce test aurait évité bloat v3.1→v3.2, c'est le test CRITIQUE

### Proposition 2: Enrichir Framework 1 avec critère Compression

**Tableau actuel** (5 critères) → **Nouveau** (6 critères):

```markdown
| Criterion | CLAUDE.md if... | Skill if... |
|-----------|----------------|-------------|
| **Universal** | Applies to all projects | Project-specific fact |
| **Stable** | Rarely changes | Changes frequently |
| **Cognitive** | HOW TO THINK (workflow, principle) | WHAT TO KNOW (implementation, fact) |
| **Scope** | Cross-cutting multiple domains | Domain-specific (DB, Testing, UI) |
| **Critical** | Top 5 most critical rules | Reference material, catalog |
| **Compressible** | 1-line DSL without loss | Requires details/prose |

**Decision Rule**: Count criteria → ≥4/6 TRUE for CLAUDE.md → CLAUDE.md | Else → Skill
```

**Ajustement décision**: ≥3/5 → ≥4/6 (même seuil ~60%)

### Proposition 3: Corriger Exemples Framework 2

**Avant** (trompeur):
```yaml
MINOR (vX.Y.0):
  Example: v3.0 → v3.1 (+6 MCO patterns, +125 lines)
```

**Après** (honnête):
```yaml
MINOR (vX.Y.0):
  When: New sections, Enhancements, Pattern adoptions
  Example_Success: v3.1 → v3.1.1 (typo fixes)
  Example_BLOAT: v3.0 → v3.1 (+125 lines MCO) → Caused bloat, reverted in v4.0

MAJOR (vX.0.0):
  When: Architecture change, Breaking changes, Philosophy shift
  Example: v3.2 → v4.0 (Pure DSL compression, -76%, -171 lines)
```

### Proposition 4: Ajouter Section "Anti-Patterns Bloat"

**Nouvelle section** (~25 lignes):

```markdown
## Anti-Patterns (NEVER Add to CLAUDE.md)

**1. Commands.Catalog** (40+ lines bash commands):
```bash
make up/down/restart/test/db-shell/coverage
curl http://localhost:8001/health
./apply_optimizations.sh test/apply/rollback
```
❌ **Why**: Knowledge (WHAT), not cognitive (HOW) → README.md or `make help`

**2. Volatile.State** (project status updates):
```yaml
Completed: EPIC-06 (74pts) | EPIC-07 (41pts)
In Progress: EPIC-10 (27/35pts)
Branch: migration/postgresql-18
```
❌ **Why**: Changes weekly, not stable cognitive pattern → STATUS.md or `git status`

**3. Skill.Duplication** (repeating skill content):
```yaml
Anti-patterns catalog already in skill:claude-md-evolution
→ Adding § ANTI-PATTERNS in CLAUDE.md = duplication
```
❌ **Why**: Trust auto-discovery, avoid duplication → skill only

**4. Version.History.Detailed** (17+ lines changelog):
```markdown
- v2.3.0 (2025-10-21): Initial compressed DSL
- v2.4.0 (2025-10-21): Added skills ecosystem
- v3.0.0 (2025-10-21): Pure cognitive engine (-57%)
...
```
❌ **Why**: Git log is source of truth → `git log` or CHANGELOG.md

**5. Universal ≠ Cognitive Confusion**:
```bash
echo $TEST_DATABASE_URL  # Universal command
make up                  # Universal command
```
❌ **Why**: Universal commands ≠ cognitive heuristics → Compress to heuristic or remove

**Test**: If content is universal BUT requires details/prose/volatile → NOT CLAUDE.md!
```

### Proposition 5: Ajouter Section "Lessons Learned"

**Nouvelle section** (~20 lignes):

```markdown
## Lessons Learned (v3.0 → v4.0 Journey)

**v3.0 (79 lines)**: Pure HOW/WHAT separation ✅
- Success: -57% reduction from v2.4
- Principle: CLAUDE.md = HOW, Skills = WHAT

**v3.1 (204 lines)**: MCO patterns adoption ❌ BLOAT
- Problem: Adopted 6 "universal" patterns without DSL compression test
- Result: +125 lines (+158% bloat)
- Mistake: Universal ≠ Cognitive (bash commands universal but not cognitive)

**v3.2 (225 lines)**: Meta-skill enrichment ❌ MORE BLOAT
- Problem: Added § META details, § ANTI-PATTERNS (duplicate skill content)
- Result: +21 lines (+10% more bloat)
- Mistake: Knowledge in CLAUDE.md instead of skill

**v4.0 (54 lines)**: Pure Cognitive DSL ✅ SUCCESS
- Solution: DSL Compression Test ("1 line DSL without loss?")
- Result: -171 lines (-76% reduction from v3.2)
- Principle: If cannot compress to 1 line DSL → NOT CLAUDE.md

**Key Insight**: "Universal" ≠ "Cognitive"
- Universal bash commands = KNOWLEDGE (README)
- Universal heuristics = COGNITIVE (CLAUDE.md DSL)
```

---

## 📊 Taille Estimée Skill v3.0

| Section | Actuel v2.0 | Proposé v3.0 | Delta |
|---------|-------------|--------------|-------|
| Framework 1 (HOW vs WHAT) | 46 lignes | 52 lignes | +6 (critère Compressible) |
| Framework 2 (Version Bump) | 42 lignes | 50 lignes | +8 (exemples corrigés) |
| Framework 3 (Pattern Adoption) | 30 lignes | 28 lignes | -2 (exemple corrigé) |
| **Framework 4 (DSL Compression)** | **0 lignes** | **30 lignes** | **+30 (nouveau)** |
| **Anti-Patterns Bloat** | **0 lignes** | **25 lignes** | **+25 (nouveau)** |
| **Lessons Learned** | **0 lignes** | **20 lignes** | **+20 (nouveau)** |
| Quick Reference | 26 lignes | 30 lignes | +4 (flowchart F4) |
| Key Rules Summary | 20 lignes | 25 lignes | +5 (enrichi) |
| **Total** | **183 lignes** | **~280 lignes** | **+97 (+53%)** |

**Verdict**: +97 lignes MAIS justifiés par:
1. Framework 4 = CRITIQUE (aurait évité bloat v3.1-v3.2)
2. Anti-Patterns = Prévention proactive
3. Lessons Learned = Expérience capitalisée (v3.0→v4.0 journey)

---

## 🎯 Recommandation Finale

### Option A: Enrichissement Complet (v3.0, ~280 lignes)

**Ajouter**:
1. ✅ Framework 4: DSL Compression Test (30 lignes)
2. ✅ Anti-Patterns Bloat section (25 lignes)
3. ✅ Lessons Learned v3.0→v4.0 (20 lignes)
4. ✅ Enrichir Framework 1 avec critère Compressible (6 lignes)
5. ✅ Corriger exemples Framework 2 (8 lignes)
6. ✅ Corriger exemple Framework 3 (0 lignes, juste update)

**Total**: 183 → ~280 lignes (+97, +53%)

**Justification**:
- Framework 4 = CRITIQUE (test qui manquait, aurait évité bloat)
- Anti-Patterns = Prévention (empêche répétition erreurs v3.1-v3.2)
- Lessons Learned = Capitalisation expérience (3 mois POCs → v4.0)

**Risk**: Skill devient lourd (~280 lignes)
**Mitigation**: Content = frameworks actionables, pas prose documentation

### Option B: Enrichissement Minimal (v2.1, ~220 lignes)

**Ajouter**:
1. ✅ Framework 4: DSL Compression Test (30 lignes) - CRITIQUE
2. ✅ Anti-Patterns Bloat section (15 lignes) - Réduit
3. ❌ Lessons Learned - Supprimé (TEMP docs suffisent)
4. ✅ Enrichir Framework 1 critère Compressible (6 lignes)
5. ❌ Corriger exemples - Minimal

**Total**: 183 → ~220 lignes (+37, +20%)

**Justification**: Framework 4 + Anti-Patterns = essentiel, reste optionnel

### Option C: Correction Minimale (v2.0.1, ~185 lignes)

**Ajouter**:
1. ✅ Framework 4 ultra-compact (15 lignes)
2. ✅ Corriger exemple § CRITICAL FIRST STEP (0 lignes, update)
3. ✅ Note critère Compressible dans Framework 1 (2 lignes)

**Total**: 183 → ~185 lignes (+2, +1%)

**Justification**: Skill déjà pratique, juste updates critiques

---

## ❓ Question pour Utilisateur

Quel niveau d'enrichissement veux-tu?

**Option A** (~280 lignes): Capture complète expérience v3.0→v4.0 (frameworks + anti-patterns + lessons)
**Option B** (~220 lignes): Frameworks essentiels + anti-patterns (sans lessons learned)
**Option C** (~185 lignes): Corrections minimales (Framework 4 compact + fixes exemples)

**Ma recommandation**: **Option A**
**Raison**: Framework 4 DSL Compression = CRITIQUE, aurait évité 3 mois de bloat iterations!
