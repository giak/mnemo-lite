# ADR-017: Story 2 vs Story 2bis Clarification

**Date**: 2025-10-16
**Status**: ✅ ACCEPTED
**Decision Maker**: Technical Analysis (Claude Code AI Assistant)
**Context**: Documentation Audit - Résolution confusion Story 2 vs Story 2bis

---

## Context

Durant l'audit exhaustif de la documentation EPIC-06 (2025-10-16), une confusion majeure a été identifiée concernant l'existence de deux stories avec "2" dans le nom:

1. **Story 2: Dual Embeddings (Text + Code)**
   - Mentionnée dans EPIC-06_Code_Intelligence.md ligne 632
   - Story Points: 5 (RÉDUIT de 8)
   - Status: Marquée "RÉVISÉ" mais pas clairement "COMPLETE" dans Phase 1

2. **Story 2bis: Code Chunks Table & Repository**
   - Mentionnée dans EPIC-06_Code_Intelligence.md ligne 164
   - Story Points: 8 ou 5 (incohérence entre lignes)
   - Status: ✅ COMPLETE (2025-10-16)

**Problème**: Impossible de calculer story points Phase 1 correctement sans savoir si Story 2 est complète, abandonnée, ou fusionnée.

---

## Investigation

### Evidence 1: Fichiers Code Existants

```bash
$ find api/services -name "*embedding*"
api/services/embedding_service.py
api/services/sentence_transformer_embedding_service.py
api/services/dual_embedding_service.py  # ← EXISTE!
```

Le fichier `dual_embedding_service.py` existe et implémente exactement ce que Story 2 demandait.

### Evidence 2: Phase 0 Story 0.2

D'après EPIC-06_Code_Intelligence.md lignes 66-74:

```
#### Story 0.2: Dual Embeddings Service (5 pts) - 2025-10-16 ✅
- ✅ `DualEmbeddingService` créé (EmbeddingDomain: TEXT | CODE | HYBRID)
- ✅ Lazy loading + double-checked locking (thread-safe)
- ✅ RAM safeguard (bloque CODE model si > 900 MB)
- ✅ Backward compatibility 100% (Adapter pattern)
- ✅ 24 unit tests + 19 regression tests passent
- ✅ Audit complet: Score 9.4/10 - Production Ready
```

**Critères d'acceptation Story 0.2** matchent EXACTEMENT **critères Story 2** (lignes 641-648):
- ✅ `EmbeddingService` étendu avec paramètre `domain: 'text'|'code'|'hybrid'`
- ✅ Backward compatibility
- ✅ Dual embeddings support
- ✅ 768D identiques

### Evidence 3: Timeline

- **2025-10-15**: Phase 0 Story 0.1 complete (Alembic)
- **2025-10-16**: Phase 0 Story 0.2 complete (**Dual Embeddings Service**)
- **2025-10-16**: Phase 1 Story 1 complete (Tree-sitter)
- **2025-10-16**: Phase 1 Story 2bis complete (Code Chunks Table)
- **2025-10-16**: Phase 1 Story 3 complete (Metadata Extraction)

**Observation**: Aucune story "Story 2" séparée n'a été implémentée en Phase 1.

---

## Decision

**Story 2 "Dual Embeddings (Text + Code)" a été FUSIONNÉE avec Phase 0 Story 0.2**.

### Rationale

1. **Implémentation identique**: Story 0.2 implémente 100% des critères Story 2
2. **Fichier code existe**: `dual_embedding_service.py` créé en Phase 0
3. **Timeline cohérente**: Story 0.2 complétée AVANT Phase 1, donc Story 2 ne peut pas être re-faite
4. **Story points matchent**: Story 2 = 5 pts (réduit de 8), Story 0.2 = 5 pts
5. **Audit complet**: Story 0.2 auditée (9.4/10), prouve qu'elle est production-ready

### Implications

1. **Phase 1 n'a PAS de Story 2 séparée**
   - Story 1: Tree-sitter Integration & AST Chunking (13 pts) ✅
   - Story 2bis: Code Chunks Table & Repository (5 pts) ✅
   - Story 3: Code Metadata Extraction (8 pts) ✅
   - **Total Phase 1**: 13 + 5 + 8 = **26 pts**

2. **Phase 0 inclut Story 2**
   - Story 0.1: Alembic Async Setup (3 pts) ✅
   - Story 0.2: Dual Embeddings Service = **STORY 2** (5 pts) ✅
   - **Total Phase 0**: 3 + 5 = **8 pts**

3. **Grand Total Completed**: 8 (Phase 0) + 26 (Phase 1) = **34 pts sur 74**

4. **Story 2bis devient "Story 2 Phase 1"** dans documentation future (optionnel)

---

## Consequences

### Documentation Updates Required

1. **EPIC-06_Code_Intelligence.md**:
   - Ajouter note explicative: "Story 2 implémentée en Phase 0 Story 0.2"
   - Clarifier que Story 2bis est la seule "Story 2" de Phase 1
   - Recalculer Phase 1 totaux: 26 pts (pas 18 ou 21)

2. **EPIC-06_ROADMAP.md**:
   - Mettre à jour Phase 1: 26 pts complete
   - Progrès global: 34/74 pts (45.9%)

3. **EPIC-06_README.md**:
   - Même mises à jour que ROADMAP

4. **EPIC-06_DOCUMENTATION_STATUS.md**:
   - Story 2: Marquer comme "Fusionnée avec Story 0.2 Phase 0"
   - Phase 1: 26 pts complete

### Phase 1 Stories Clarifiées

| Story | Story Points | Status | Note |
|-------|--------------|--------|------|
| Story 1: Tree-sitter & AST Chunking | 13 pts | ✅ COMPLETE | - |
| ~~Story 2: Dual Embeddings~~ | ~~5 pts~~ | **MOVED TO PHASE 0** | Fusionnée avec Story 0.2 |
| Story 2bis: Code Chunks Table | **5 pts** | ✅ COMPLETE | Devient "Story 2 Phase 1" |
| Story 3: Code Metadata Extraction | **8 pts** | ✅ COMPLETE | - |
| **TOTAL PHASE 1** | **26 pts** | **✅ 100% COMPLETE** | - |

---

## Alternatives Considered

### Alternative 1: Story 2 Still Pending
**Rejected** - Fichier `dual_embedding_service.py` existe déjà, tous critères remplis

### Alternative 2: Story 2 Abandoned
**Rejected** - Implémentation existe et est production-ready (audit 9.4/10)

### Alternative 3: Story 2 Fusionnée (SELECTED)
**Accepted** - Evidence claire que Story 2 = Story 0.2

---

## Status

- [x] Decision made (2025-10-16)
- [ ] Documentation updated (pending)
- [ ] ADR communicated to stakeholders (pending)
- [ ] Story points recalculated everywhere (pending)

---

**Related**:
- EPIC-06_DOCUMENTATION_AUDIT_EXHAUSTIF.md (Section 3.5)
- EPIC-06_PHASE_0_STORY_0.2_AUDIT_REPORT.md
- docs/agile/EPIC-06_Code_Intelligence.md (lignes 66-74, 632-687)

**Impact**: HAUTE - Affecte calcul story points global et progrès EPIC

**Next Steps**: Mettre à jour tous documents avec valeurs story points correctes (34/74 pts = 45.9%)