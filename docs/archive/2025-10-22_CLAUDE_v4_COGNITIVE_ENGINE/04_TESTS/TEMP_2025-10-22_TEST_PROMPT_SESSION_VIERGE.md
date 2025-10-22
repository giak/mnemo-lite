# Test Prompt - Session Vierge (Conditions Réelles)

**Objectif**: Valider système cognitif complet (CLAUDE.md v4.0 + skill v3.1)

**Ce qui sera testé**:
1. ✅ CLAUDE.md v4.0 (54 lignes DSL) chargé au startup
2. ✅ skill:claude-md-evolution v3.1 auto-invoke (keywords match)
3. ✅ Ontologie DSL comprise par LLM
4. ✅ Framework 1 (HOW vs WHAT) actionnable
5. ✅ Framework 4 (DSL Compression) actionnable
6. ✅ Framework 2 (Version Bump) actionnable
7. ✅ Anti-Patterns détection

---

## 🎯 Prompt de Test (Copy-Paste)

```markdown
Je travaille sur MnemoLite et j'ai besoin de ton aide pour décider où ajouter du nouveau contenu dans CLAUDE.md.

**Contexte**: On vient de compléter EPIC-11 (13 points) - Symbol Enhancement avec recherche par qualified name. C'était une grosse feature qui ajoute la recherche hiérarchique de symboles (e.g., "models.user.User.validate").

**Contenu à ajouter**:

Je veux documenter 3 choses:

1. **Liste des 12 commandes Docker courantes qu'on utilise**:
```bash
docker compose up -d
docker compose down
docker compose logs -f api
docker compose exec db psql -U mnemolite
docker compose restart api
docker compose ps
docker stats mnemo-api
docker compose build --no-cache
docker image inspect mnemo-api
docker compose exec api pytest tests/
docker logs mnemo-api --tail 100
docker compose exec api python -m api.main
```

2. **Section § EPIC STATUS actuelle**:
```yaml
§ EPIC STATUS:
  Completed:
    - EPIC-06: Core Events System (74pts) ✅
    - EPIC-07: Code Intelligence MVP (41pts) ✅
    - EPIC-08: Performance & Caching (24pts) ✅
    - EPIC-11: Symbol Enhancement (13pts) ✅
    - EPIC-12: Code Quality & Audit (13pts) ✅

  In Progress:
    - EPIC-10: Advanced Caching (27/35pts complete)
    - Remaining: Stories 10.4-10.5 (8pts)

  Next:
    - EPIC-09: Advanced File Upload (35pts proposed)

  Current Branch: migration/postgresql-18
  Last Updated: 2025-10-22
```

3. **Règle importante sur qualified names**:
"Toujours utiliser qualified names pour la recherche de symboles (e.g., 'models.user.User.validate' au lieu de juste 'validate'). Le name_path utilise containment strict (< et >) pour éviter les faux positifs aux boundaries."

**Mes questions**:

1. Où est-ce que je dois mettre chacun de ces 3 contenus? Dans CLAUDE.md, dans un skill, dans README, ou ailleurs?

2. Si je les ajoute à CLAUDE.md, est-ce que je dois bumper la version? Si oui, MAJOR, MINOR ou PATCH?

3. Y a-t-il des best practices ou anti-patterns que je devrais connaître avant d'ajouter ça?

Aide-moi à prendre la bonne décision!
```

---

## 🎯 Résultats Attendus (Validation)

### Test 1: skill Auto-Invoke ✅

**Expected**: Le skill:claude-md-evolution devrait s'auto-invoquer

**Raison**: Description contient keywords:
- "updating CLAUDE.md" ✅
- "deciding content placement" ✅
- "bumping versions" ✅

**Validation**: Claude devrait mentionner utilisation du skill

---

### Test 2: Framework 1 (HOW vs WHAT) ✅

**Contenu 1 (12 commandes Docker)**:

**Expected Answer**:
```yaml
Test F1 (6 critères):
  U: ✅ (Docker commands universal)
  S: ✅ (rarely change)
  C: ❌ (WHAT not HOW - commands not cognitive)
  X: ❌ (domain-specific Docker)
  K: ❌ (not top 5 critical)
  D: ❌ (cannot compress to 1L.DSL - 12 lines)

Score: 2/6 → <4 → SK or README

Decision: README.md or documentation (universal knowledge, not cognitive)
```

**Contenu 2 (§ EPIC STATUS)**:

**Expected Answer**:
```yaml
Test F1 (6 critères):
  U: ❌ (project-specific)
  S: ❌ (changes weekly/bi-weekly)
  C: ❌ (WHAT not HOW - state not workflow)
  X: ❌ (project management specific)
  K: ❌ (not critical rule)
  D: ❌ (cannot compress - 20+ lines volatile)

Score: 0/6 → SK or STATUS.md or git status

Decision: STATUS.md or git status (volatile state)
```

**Contenu 3 (Qualified names rule)**:

**Expected Answer**:
```yaml
Test F1 (6 critères):
  U: ⚠️ (symbol search practice - somewhat universal)
  S: ✅ (rarely changes)
  C: ✅ (HOW - best practice, not fact)
  X: ⚠️ (code search domain)
  K: ⚠️ (important but not top 5)
  D: ⚠️ (compressible: "Use qualified.names → name_path strict containment")

Score: 3-4/6 → Borderline

Decision: skill:mnemolite-gotchas or skill:mnemolite-code-intel (domain-specific best practice)
```

---

### Test 3: Framework 4 (DSL Compression) ✅

**Expected**: Claude devrait appliquer test "1L.DSL?"

**Contenu 1 (Docker commands)**:
```
Test F4: 12 lines bash → 1L.DSL?
Answer: ❌ Cannot compress (commands catalog)
Decision: README.md (fails 1L.DSL test)
```

**Contenu 2 (EPIC STATUS)**:
```
Test F4: 20+ lines volatile state → 1L.DSL?
Answer: ❌ Cannot compress (volatile, changes weekly)
Decision: STATUS.md or git status (not cognitive)
```

**Contenu 3 (Qualified names)**:
```
Test F4: Rule → 1L.DSL?
Answer: ⚠️ Compressible with acceptable loss
Compressed: "! Use qualified.names (name_path) → strict containment (< >) ∵ avoid boundary FP"
Decision: Could go CM (compressed) or SK (detailed)
```

---

### Test 4: Anti-Patterns Detection ✅

**Expected**: Claude devrait détecter anti-patterns:

1. **Commands.Catalog** (Contenu 1):
   ```
   Pattern: Commands.Catalog (12 Docker commands)
   Why Wrong: U ✅ C ❌ (universal but not cognitive)
   Test Fail: 1L.DSL ❌
   Correct: README.md
   Reference: Anti-Pattern #1 in skill
   ```

2. **Volatile.State** (Contenu 2):
   ```
   Pattern: Volatile.State (EPIC STATUS weekly updates)
   Why Wrong: S ❌ (changes weekly)
   Test Fail: S ❌ (Stable criteria)
   Correct: STATUS.md or git status
   Reference: Anti-Pattern #2 in skill
   ```

3. **Potential Skill.Duplication** (Contenu 3):
   ```
   Warning: If qualified names rules already in skill:mnemolite-code-intel
   → Don't duplicate in CLAUDE.md
   → Reference skill only
   Reference: Anti-Pattern #3 in skill
   ```

---

### Test 5: Framework 2 (Version Bump) ✅

**Expected**: Si utilisateur veut quand même ajouter à CLAUDE.md

**Question**: "Si j'ajoute quand même, quel version bump?"

**Expected Answer**:
```yaml
Current: v4.0.0

Scenario 1: Add all 3 → BAD IDEA (violates anti-patterns)
  But if forced:
    - +§ DOCKER COMMANDS (12L) + § EPIC STATUS (20L) + qualified rule
    - Non-breaking but violates philosophy
    - Version: MINOR (v4.1.0) - significant addition
    - But: ❌ NOT RECOMMENDED (bloat, violates v4.0 pure DSL)

Scenario 2: Add only qualified names rule (compressed)
  - Compress: "! Use qualified.names → strict containment"
  - 1 line addition to § CRITICAL.HEURISTICS
  - Version: PATCH (v4.0.1) - small addition
  - Acceptable: ✅ (maintains DSL purity)

Recommendation:
  - Docker commands → README.md (NO version bump CLAUDE.md)
  - EPIC STATUS → STATUS.md or git status (NO version bump CLAUDE.md)
  - Qualified names → skill:mnemolite-code-intel or PATCH if compressed
```

---

### Test 6: Ontologie DSL Comprise ✅

**Expected**: Claude devrait utiliser ontologie dans sa réponse:

**Symboles attendus**:
- ✅ ❌ ⚠️ (PASS/FAIL/PARTIAL)
- → (MIGRATE to)
- CM, SK, RM, ST (CLAUDE.md, Skill, README, STATUS)
- U, S, C, X, K, D (criteria)
- 1L.DSL (1-line DSL test)
- F1, F2, F3, F4 (frameworks)

**Example réponse attendue**:
```
Contenu 1 (Docker commands):
  F1 Test: U ✅ S ✅ C ❌ X ❌ K ❌ D ❌ → Score 2/6 → RM
  F4 Test: 12L bash → 1L.DSL? ❌
  Anti-Pattern: Commands.Catalog detected
  Decision: RM (README.md)
  Version: NO BUMP (not in CM)
```

---

### Test 7: Réponse Structurée ✅

**Expected**: Claude devrait structurer réponse avec:

1. **Analyse par contenu** (3 contenus)
2. **Application frameworks** (F1, F4)
3. **Détection anti-patterns**
4. **Recommendations finales** (tableau summary)
5. **Version bump decision** (si applicable)

**Format attendu**:
```markdown
## Analyse Contenu (F1 + F4)

### Contenu 1: Docker Commands (12 lignes)
[Test F1: score, Test F4: result, Anti-pattern: detected, Decision: RM]

### Contenu 2: EPIC STATUS (20 lignes)
[Test F1: score, Test F4: result, Anti-pattern: detected, Decision: ST]

### Contenu 3: Qualified Names Rule
[Test F1: score, Test F4: result, Decision: SK or CM compressed]

## Recommendations

| Content | F1 Score | F4 Test | Anti-Pattern | → Decision |
|---------|----------|---------|--------------|------------|
| Docker commands | 2/6 | ❌ | Commands.Catalog | RM |
| EPIC STATUS | 0/6 | ❌ | Volatile.State | ST/git |
| Qualified names | 3-4/6 | ⚠️ | - | SK or CM (compressed) |

## Version Bump

[Analysis based on F2 criteria]
```

---

## ✅ Checklist Validation

**Si Claude répond avec**:

- [ ] skill:claude-md-evolution auto-invoqué
- [ ] Ontologie DSL utilisée (✅ ❌ CM SK RM etc.)
- [ ] Framework 1 (HOW vs WHAT) appliqué aux 3 contenus
- [ ] Framework 4 (1L.DSL test) appliqué
- [ ] Anti-Patterns détectés (Commands.Catalog, Volatile.State)
- [ ] Framework 2 (Version Bump) expliqué
- [ ] Recommendations claires (tableau summary)
- [ ] Réponse structurée et actionnable

**Alors**: ✅ Système validé en conditions réelles!

---

## 🎯 Scénarios Bonus (Tests Additionnels)

### Scénario 2: Adoption Pattern Externe

**Prompt**:
```
Je viens de voir un CLAUDE.md d'un autre projet qui a une section § TROUBLESHOOTING avec 8 problèmes courants et leurs solutions. Devrais-je adopter ce pattern pour MnemoLite?
```

**Expected**:
- F3 (Pattern Adoption) appliqué (5 critères)
- F4 (DSL compression) testé
- Decision basée sur F3 ∧ F4

---

### Scénario 3: Version Bump Ambigu

**Prompt**:
```
Je viens de refactoriser § PRINCIPLES pour séparer ◊Core et ◊Dev en deux sections distinctes. Pas de nouveau contenu, juste réorganisation. MAJOR, MINOR ou PATCH?
```

**Expected**:
- F2 (Version Bump) appliqué
- Discussion: Restructure = breaking? Philosophy change?
- Decision: Probablement MINOR (restructure non-breaking)

---

**Recommendation**: Commence avec Prompt principal, puis tests bonus si validation OK
