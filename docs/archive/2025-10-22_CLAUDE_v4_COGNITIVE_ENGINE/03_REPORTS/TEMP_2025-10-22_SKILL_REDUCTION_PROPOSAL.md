# Proposition: Skill claude-md-evolution Réduit

**Problème**: 1,081 lignes = encyclopédie, pas skill pratique
**Solution**: Réduire à l'essentiel actionnable (~300-400 lignes max)

---

## Qu'est-ce qu'on GARDE?

**Les outils de décision** (pratiques, rapides):
1. ✅ Framework HOW vs WHAT Test (tableau simple)
2. ✅ Framework Version Bump (règles claires)
3. ✅ Framework Pattern Adoption (checklist 5 items)
4. ✅ Framework Validation Protocol (steps)
5. ✅ Anti-Patterns (liste NEVER courte)
6. ✅ Workflows (steps seulement, pas d'explications)
7. ✅ Quick Reference (flowcharts ultra-compacts)

**Format**: Tableaux, listes, checklists (pas de prose)

---

## Qu'est-ce qu'on SUPPRIME?

**Documentation/explications** (pas actionnable):
1. ❌ Longues explications philosophiques
2. ❌ Exemples détaillés (v2.4→v3.0, v3.0→v3.1)
3. ❌ Lessons Learned Archive (académique)
4. ❌ Contexte historique (POCs journey)
5. ❌ Métriques détaillées
6. ❌ "Why Wrong" paragraphes longs

**Raison**: Trop de blabla, pas assez d'action

---

## Structure Réduite Proposée

```markdown
---
name: claude-md-evolution
description: [same - 1 ligne]
---

# claude-md-evolution

## When to Use
[Liste bullets: 5-6 items, 1 ligne chacun]

## Framework 1: HOW vs WHAT Test
[Tableau 5 critères + exemples → 20 lignes max]

## Framework 2: Version Bump
[Tableau MAJOR/MINOR/PATCH → 15 lignes max]

## Framework 3: Pattern Adoption
[Checklist 5 items → 10 lignes max]

## Framework 4: Validation Protocol
[Steps Pre/Change/Post → 15 lignes max]

## Anti-Patterns (NEVER)
[Liste 5 items, 1 ligne chacun → 10 lignes max]

## Workflows
### Weekly Update
[Steps: 1,2,3 → 5 lignes]
### Quarterly Review
[Steps: 1,2,3,4 → 8 lignes]
### Pattern Adoption
[Steps: 1,2,3,4 → 8 lignes]
### Emergency Rollback
[Steps: 1,2,3 → 5 lignes]

## Quick Reference
[4 flowcharts ultra-compacts → 40 lignes max]

## Validation Checklist
[9 items, checkbox format → 15 lignes max]
```

**Total Estimé**: ~300-350 lignes (70% réduction)

---

## Exemple: Anti-Patterns Avant/Après

**AVANT** (150 lignes):
```markdown
### Anti-Pattern 1: Facts Bloat

**Problem**: Adding project-specific facts to CLAUDE.md instead of skill references

**Example (WRONG)**:
```markdown
## § DATABASE SCHEMA

events: {id:UUID.PK, timestamp:TIMESTAMPTZ...}
code_chunks: {id:UUID.PK, file_path:TEXT...}
```

**Why Wrong**:
- Project-specific facts (not universal principles)
- Changes frequently (schema evolution)
- Bloats CLAUDE.md (token cost)
...
```

**APRÈS** (10 lignes):
```markdown
## Anti-Patterns (NEVER)

1. Facts.Bloat: Add project facts to CLAUDE.md instead of skill reference
2. Skill.Duplication: Repeat skill descriptions (trust auto-discovery)
3. Premature.Optimization: Optimize without baseline measurement
4. Breaking.Changes: Rename/restructure without session vierge test
5. Over.Engineering: Add complexity without utility (KISS)
```

**Réduction**: 150 → 10 lignes (93% réduction)

---

## Exemple: Framework Avant/Après

**AVANT** (80 lignes avec pseudo-code Python):
```python
def belongs_in_claude_md(content):
    """Returns True if content belongs in CLAUDE.md."""
    tests = {
        "universal_principle": is_universal(content),
        ...
    }
    return sum(tests.values()) >= 3
```

**APRÈS** (20 lignes tableau):
```markdown
## HOW vs WHAT Test

| Criterion | CLAUDE.md if... | Skill if... |
|-----------|----------------|-------------|
| Universal | Applies to all projects | Project-specific |
| Stable | Rarely changes | Changes frequently |
| Cognitive | HOW TO THINK | WHAT TO KNOW |
| Scope | Cross-cutting | Domain-specific |
| Critical | Top 5 rules | Reference material |

Decision: ≥3 criteria → CLAUDE.md | Else → Skill
```

**Réduction**: 80 → 20 lignes (75% réduction)

---

## Veux-tu que je:

**Option 1**: Créer version réduite (~300-350 lignes) maintenant?

**Option 2**: On brainstorm ensemble ce qu'il faut garder exactement?

**Option 3**: On supprime ce skill et on garde juste les 4 autres?

Dis-moi ce que tu préfères!
