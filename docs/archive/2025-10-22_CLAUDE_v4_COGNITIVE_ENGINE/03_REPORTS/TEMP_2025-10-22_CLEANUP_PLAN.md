# Plan de Nettoyage - Avant Commit/Merge

**Date**: 2025-10-22
**Branch**: migration/postgresql-18
**Objectif**: Clean avant fusion - Préparer commit propre

---

## 📊 Audit Fichiers Créés/Modifiés

### Fichiers Modifiés (M)
```
M  99_TEMP/POC_TRACKING.md         → KEEP (tracker POCs)
M  CLAUDE.md                        → KEEP (v4.0, 54 lignes)
```

### Nouveaux Fichiers Critiques (KEEP)
```
.claude/skills/claude-md-evolution/SKILL.md     → KEEP (v3.1, 241 lignes)
.claude/settings.local.json                     → KEEP (settings)
```

### Backups CLAUDE.md (ARCHIVE)
```
CLAUDE_v3.0.0_BACKUP.md     → ARCHIVE (79 lignes, backup v3.0)
CLAUDE_v3.2.0_BACKUP.md     → ARCHIVE (225 lignes, backup v3.2)
```

### Fichiers TEMP (20 fichiers, ~15,000 lignes!)

#### Groupe 1: Journey v3.0 → v4.0 (ARCHIVE - Documentation Précieuse)
```
TEMP_2025-10-21_cognitive_architecture_ultrathink.md      (590 lignes)
TEMP_2025-10-21_AUDIT_CLAUDE_SKILLS_ULTRATHINK.md        (590 lignes)
TEMP_2025-10-21_VERIFICATION_AUDIT_RECOMMENDATIONS.md    (590 lignes)
TEMP_2025-10-22_CLAUDE_MD_COGNITIVE_ENGINE_DSL_ULTRATHINK.md
TEMP_2025-10-22_CLAUDE_MD_V4_REDUCTION_REPORT.md
TEMP_2025-10-22_CLAUDE_v3.1_UPGRADE_SUMMARY.md
```

#### Groupe 2: Skill Evolution (ARCHIVE - Meta-learning)
```
TEMP_2025-10-22_SKILL_CLAUDE_MD_EVOLUTION_CREATED.md
TEMP_2025-10-22_SKILL_CLAUDE_MD_EVOLUTION_CRITICAL_AUDIT.md
TEMP_2025-10-22_SKILL_CLAUDE_MD_MAINTENANCE_ULTRATHINK.md
TEMP_2025-10-22_SKILL_CLAUDE_MD_V4_AUDIT.md
TEMP_2025-10-22_SKILL_COMPRESSION_ONTOLOGY_DESIGN.md
TEMP_2025-10-22_SKILL_REDUCTION_PROPOSAL.md
TEMP_2025-10-22_SKILL_V3.1_COMPRESSION_REPORT.md
TEMP_2025-10-22_SKILL_V3_IMPLEMENTATION_SUMMARY.md
TEMP_2025-10-22_OPTION_C_IMPLEMENTATION_SUMMARY.md
```

#### Groupe 3: Tests & Validation (KEEP - Référence Future)
```
TEMP_2025-10-22_TEST_PROMPT_SESSION_VIERGE.md
TEMP_2025-10-22_TEST_PROMPT_SKILLS_ECOSYSTEM.md
TEST_RESULTS_REPORT.md
CLAUDE_SKILLS_LESSONS_LEARNED.md
```

### Fichiers Suspects (DELETE)
```
api/CLAUDE.md                       → DELETE (doublon? erreur?)
99_TEMP/skills_archive_subdirectories/  → REVIEW (ancien?)
```

---

## 🎯 Plan d'Action

### Phase 1: Archivage Structuré

**Créer**: `docs/archive/2025-10-22_CLAUDE_v4_COGNITIVE_ENGINE/`

**Structure proposée**:
```
docs/archive/2025-10-22_CLAUDE_v4_COGNITIVE_ENGINE/
├── 00_SUMMARY.md                           (Résumé journey v3.0→v4.0)
├── 01_ANALYSIS/
│   ├── cognitive_architecture_ultrathink.md
│   ├── audit_claude_skills.md
│   ├── verification_recommendations.md
│   └── claude_md_v4_reduction_analysis.md
├── 02_SKILL_EVOLUTION/
│   ├── skill_creation_ultrathink.md
│   ├── skill_critical_audit.md
│   ├── skill_compression_ontology_design.md
│   ├── skill_v3_implementation.md
│   └── skill_v3.1_compression_report.md
├── 03_REPORTS/
│   ├── claude_v3.1_upgrade_summary.md
│   ├── claude_v4_reduction_report.md
│   ├── option_c_implementation.md
│   └── skill_reduction_proposal.md
├── 04_TESTS/
│   ├── test_prompt_session_vierge.md
│   ├── test_prompt_skills_ecosystem.md
│   └── test_results_report.md
├── 05_BACKUPS/
│   ├── CLAUDE_v3.0.0_BACKUP.md
│   └── CLAUDE_v3.2.0_BACKUP.md
└── 06_LESSONS_LEARNED/
    └── claude_skills_lessons_learned.md
```

**Metrics Archive**:
- CLAUDE.md: v3.2 (225L) → v4.0 (54L) = -76%
- skill:claude-md-evolution: v3.0 (470L) → v3.1 (241L) = -49%
- Système total: -58% lignes, -77% startup tokens
- Documentation: ~15,000 lignes (ultrathinks + reports)

---

### Phase 2: Nettoyage 99_TEMP/

**Garder dans 99_TEMP/** (référence rapide):
```
99_TEMP/
├── POC_TRACKING.md                         (tracker POCs actifs)
├── TEMP_2025-10-22_CLEANUP_PLAN.md         (ce document)
└── README.md                                (créer: index des archives)
```

**Déplacer vers archive**: Tous les TEMP_2025-10-* (20 fichiers)

---

### Phase 3: Skill Backups

**Créer**: `.claude/skills/claude-md-evolution/archive/`

**Structure**:
```
.claude/skills/claude-md-evolution/
├── SKILL.md                                (v3.1, 241 lignes - CURRENT)
└── archive/
    ├── SKILL_v2.0_BACKUP.md                (183 lignes)
    └── SKILL_v3.0_BACKUP.md                (470 lignes)
```

---

### Phase 4: Vérifications Avant Commit

**Checklist**:
- [ ] api/CLAUDE.md supprimé (doublon suspect)
- [ ] 99_TEMP/ nettoyé (seulement POC_TRACKING.md + README.md)
- [ ] Backups archivés (docs/archive/)
- [ ] Skill backups archivés (.claude/skills/*/archive/)
- [ ] git status clean (seulement fichiers pertinents)
- [ ] .gitignore updated (si nécessaire)

**Fichiers à committer** (final):
```
M  CLAUDE.md                                    (v4.0)
M  99_TEMP/POC_TRACKING.md                      (updated)
A  .claude/skills/claude-md-evolution/SKILL.md  (v3.1)
A  docs/archive/2025-10-22_CLAUDE_v4_COGNITIVE_ENGINE/  (documentation journey)
A  99_TEMP/README.md                            (index archives)
```

---

## 🎓 Recommandations

### Option A: Archive Complète (Recommandé)

**Action**:
1. Créer `docs/archive/2025-10-22_CLAUDE_v4_COGNITIVE_ENGINE/`
2. Organiser par thème (Analysis, Skill Evolution, Reports, Tests)
3. Créer 00_SUMMARY.md (résumé journey)
4. Nettoyer 99_TEMP/ complètement

**Avantages**:
- Documentation complète du journey v3.0→v4.0
- Référence future pour décisions architecturales
- Capitalisation expérience (15,000 lignes insights!)
- Branche clean pour merge

**Inconvénients**:
- Effort organisation (~30min)
- +15MB documentation

---

### Option B: Archive Minimale

**Action**:
1. Garder seulement 3-4 documents clés (reports finaux)
2. Supprimer ultrathinks intermédiaires
3. Archiver backups seulement

**Avantages**:
- Rapide (~5min)
- Moins de documentation

**Inconvénients**:
- Perte insights profonds (ultrathinks)
- Difficile reconstruire raisonnement plus tard

---

### Option C: Tout Supprimer (Pas Recommandé)

**Action**:
1. Supprimer tous TEMP files
2. Garder seulement backups CLAUDE.md

**Avantages**:
- Très rapide
- Minimal

**Inconvénients**:
- ❌ Perte totale documentation journey
- ❌ Impossible comprendre décisions plus tard
- ❌ Gaspille 15,000 lignes d'analyse

---

## 📝 Commandes Préparées

### Option A (Archive Complète)

```bash
# 1. Créer structure archive
mkdir -p docs/archive/2025-10-22_CLAUDE_v4_COGNITIVE_ENGINE/{01_ANALYSIS,02_SKILL_EVOLUTION,03_REPORTS,04_TESTS,05_BACKUPS,06_LESSONS_LEARNED}

# 2. Déplacer fichiers vers archive
mv 99_TEMP/TEMP_2025-10-21_cognitive_architecture_ultrathink.md docs/archive/2025-10-22_CLAUDE_v4_COGNITIVE_ENGINE/01_ANALYSIS/
mv 99_TEMP/TEMP_2025-10-21_AUDIT_CLAUDE_SKILLS_ULTRATHINK.md docs/archive/2025-10-22_CLAUDE_v4_COGNITIVE_ENGINE/01_ANALYSIS/
# ... [Tous les autres fichiers selon structure]

# 3. Déplacer backups CLAUDE.md
mv CLAUDE_v3.0.0_BACKUP.md docs/archive/2025-10-22_CLAUDE_v4_COGNITIVE_ENGINE/05_BACKUPS/
mv CLAUDE_v3.2.0_BACKUP.md docs/archive/2025-10-22_CLAUDE_v4_COGNITIVE_ENGINE/05_BACKUPS/

# 4. Archiver skill backups
mkdir -p .claude/skills/claude-md-evolution/archive
mv .claude/skills/claude-md-evolution/SKILL_v2.0_BACKUP.md .claude/skills/claude-md-evolution/archive/
mv .claude/skills/claude-md-evolution/SKILL_v3.0_BACKUP.md .claude/skills/claude-md-evolution/archive/

# 5. Nettoyer suspects
rm -f api/CLAUDE.md  # Doublon

# 6. Créer README archives
# (Script séparé)

# 7. Vérifier git status
git status
```

---

## 🎯 Ma Recommandation

**Option A (Archive Complète)** pour ces raisons:

1. **Documentation précieuse**: 15,000 lignes d'analyse profonde
2. **Journey unique**: v3.0→v3.2 (bloat) → v4.0 (pure DSL) rarement documenté
3. **Meta-learning**: Skill teaching compression → became verbose → compressed itself
4. **Référence future**: Décisions architecturales expliquées
5. **Effort justifié**: 30min pour capitaliser 3 jours de work

**Gain long-terme**: Comprendre décisions > Gain court-terme (clean rapide)

---

**Prochaine étape**: Veux-tu que j'exécute Option A (archive complète)?
