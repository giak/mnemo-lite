# Test Prompt - Skills Ecosystem (Session Vierge)

**Objectif**: Valider système cognitif CLAUDE.md v4.0 + Skills ecosystem en conditions réelles

**Ce qui sera testé**:
1. ✅ CLAUDE.md v4.0 (54 lignes DSL) comme moteur cognitif
2. ✅ skill:mnemolite-architecture auto-invoke (stack, structure, patterns)
3. ✅ skill:mnemolite-gotchas auto-invoke (critical rules, 31 gotchas)
4. ✅ skill:epic-workflow auto-invoke (EPIC management)
5. ✅ Progressive disclosure (skills chargés on-demand)
6. ✅ Principes CLAUDE.md (EXTEND>REBUILD, Test.First, Skills.First)
7. ✅ Référencement skills depuis CLAUDE.md

---

## 🎯 Prompt Principal (Copy-Paste)

```
Je vais implémenter une nouvelle feature pour MnemoLite: un système de notifications en temps réel pour alerter quand l'indexation de code est terminée.

**Contexte technique**:
- MnemoLite = PostgreSQL 18 + FastAPI + Redis + Code Intelligence
- On a déjà: PGMQ (message queue), Redis (cache), WebSocket support potentiel
- Architecture: DIP (Protocol-based), async-first, CQRS-inspired

**Ce que je veux faire**:

1. **Créer un nouveau service NotificationService**:
```python
class NotificationService:
    def __init__(self, redis_client, db_engine):
        self.redis = redis_client
        self.db = db_engine

    def notify_indexing_complete(self, repository: str, chunks_indexed: int):
        # Publier notification via Redis pub/sub
        message = {
            "event": "indexing_complete",
            "repository": repository,
            "chunks": chunks_indexed,
            "timestamp": datetime.now()
        }
        self.redis.publish("notifications", json.dumps(message))

    def subscribe_notifications(self):
        pubsub = self.redis.pubsub()
        pubsub.subscribe("notifications")
        for message in pubsub.listen():
            yield message
```

2. **Intégrer dans code_indexing_service.py**:
   - Appeler `notify_indexing_complete()` après indexation
   - Ajouter endpoint WebSocket `/ws/notifications` pour streaming

3. **Ajouter tests**:
   - `tests/test_notification_service.py`
   - Tester pub/sub Redis
   - Tester WebSocket endpoint

**Mes questions**:

1. **Architecture**: Est-ce que NotificationService devrait implémenter un Protocol? Où le placer dans la structure? Comment gérer DI?

2. **Base de données de test**: J'ai besoin de tester avec Redis et PostgreSQL. Comment éviter de polluer la DB de dev?

3. **Async**: Le code doit être async ou sync? Redis pubsub est bloquant, comment gérer ça?

4. **Gotchas**: Quels pièges dois-je éviter? (J'ai lu qu'il y a des gotchas critiques dans ce projet)

5. **Workflow**: C'est quelle taille de feature? Dois-je créer un EPIC, une Story, ou juste coder direct?

Aide-moi à bien architecturer cette feature!
```

---

## 🎯 Résultats Attendus (Validation)

### Test 1: CLAUDE.md v4.0 Principes Appliqués ✅

**Expected**: Claude devrait citer principes de CLAUDE.md v4.0:

1. **◊Arch: async.first**:
   ```
   Redis pub/sub bloquant → Problème avec async.first principle
   Solution: Utiliser aioredis ou redis[asyncio] pour async pub/sub
   Reference: CLAUDE.md § PRINCIPLES
   ```

2. **◊Arch: Protocol.Based.DI**:
   ```
   NotificationService DOIT implémenter Protocol
   Example: NotificationServiceProtocol dans api/interfaces/services.py
   Reference: CLAUDE.md § PRINCIPLES
   ```

3. **◊Dev: EXTEND>REBUILD**:
   ```
   Ne pas recréer de zéro!
   → Copier pattern existant (e.g., EmbeddingService, SearchService)
   → Adapter pour notifications
   Reference: CLAUDE.md § CRITICAL.HEURISTICS
   ```

4. **! Skills.First**:
   ```
   "Query skills for details before assumptions"
   → skill:mnemolite-architecture pour structure
   → skill:mnemolite-gotchas pour pièges critiques
   Reference: CLAUDE.md § CRITICAL.HEURISTICS
   ```

---

### Test 2: skill:mnemolite-architecture Auto-Invoke ✅

**Expected**: Skill devrait s'auto-invoquer car keywords:
- "architecture" ✅
- "structure" ✅
- "DIP" / "Protocol" ✅
- "FastAPI" / "Redis" / "PostgreSQL" ✅

**Info attendue du skill**:

1. **Structure fichiers**:
   ```
   api/
     services/
       notification_service.py  ← Nouveau service ici
     interfaces/
       services.py  ← Protocol ici
     routes/
       notifications.py  ← Nouveau endpoint ici
   tests/
     test_notification_service.py
   ```

2. **DIP Pattern**:
   ```python
   # api/interfaces/services.py
   class NotificationServiceProtocol(Protocol):
       async def notify_indexing_complete(...) -> None: ...

   # api/services/notification_service.py
   class NotificationService:
       # Implémente Protocol

   # api/dependencies.py
   def get_notification_service() -> NotificationServiceProtocol:
       return NotificationService(...)
   ```

3. **Architecture patterns**:
   - CQRS: Notifications = Command (write-side)
   - Async-first: Tout en async/await
   - Protocol-based: Injection via dependencies.py

**Validation**: Claude cite skill:mnemolite-architecture explicitement

---

### Test 3: skill:mnemolite-gotchas Auto-Invoke ✅

**Expected**: Skill devrait s'auto-invoquer car keywords:
- "gotchas" / "pièges" ✅
- "tests" / "DB test" ✅
- "async" ✅

**Gotchas attendus**:

1. **CRITICAL-01: TEST_DATABASE_URL**:
   ```
   ⚠️ CRITIQUE: Toujours utiliser TEST_DATABASE_URL pour tests!

   BAD:
   pytest tests/test_notification_service.py  # Pollue dev DB!

   GOOD:
   export TEST_DATABASE_URL=postgresql://...mnemolite_test
   pytest tests/test_notification_service.py

   Reference: skill:mnemolite-gotchas CRITICAL-01
   ```

2. **CRITICAL-02: Async Everything**:
   ```
   ⚠️ Redis pub/sub bloquant = PROBLÈME!

   BAD:
   self.redis.publish()  # Sync call

   GOOD:
   await self.redis.publish()  # Async avec aioredis

   Reference: skill:mnemolite-gotchas CRITICAL-02
   ```

3. **CRITICAL-05: EMBEDDING_MODE=mock**:
   ```
   Si tests touchent embedding:
   export EMBEDDING_MODE=mock  # Évite 2min model loading

   Reference: skill:mnemolite-gotchas CRITICAL-05
   ```

4. **Edit Tool Requirement**:
   ```
   Avant d'éditer code_indexing_service.py:
   → TOUJOURS lire le fichier d'abord (Read tool)
   → Edit tool requiert Read préalable

   Reference: skill:mnemolite-gotchas
   ```

**Validation**: Claude cite 3-4 gotchas spécifiques avec numéros

---

### Test 4: skill:epic-workflow Auto-Invoke ✅

**Expected**: Skill devrait s'auto-invoquer car keywords:
- "EPIC" / "Story" ✅
- "feature" / "workflow" ✅

**Guidance attendue**:

1. **Sizing**:
   ```
   NotificationService = Feature moyenne

   Estimation:
   - Service + Protocol: 2 pts
   - Routes + WebSocket: 3 pts
   - Tests: 2 pts
   - Integration: 1 pt
   Total: ~8 pts = Story (pas EPIC)

   Reference: skill:epic-workflow
   ```

2. **Workflow**:
   ```
   1. Créer Story (pas EPIC pour 8pts)
   2. Test.First: Écrire tests d'abord
   3. Implement: Service → Routes → Integration
   4. Document: Update CLAUDE.md? Non! → skill:mnemolite-architecture
   5. Commit: "feat(notifications): Add real-time notification system"

   Reference: skill:epic-workflow + CLAUDE.md § COGNITIVE.WORKFLOWS
   ```

**Validation**: Claude recommande Story (pas EPIC) et cite workflow

---

### Test 5: Progressive Disclosure ✅

**Expected**: Skills chargés on-demand, pas tous au startup

**Séquence attendue**:
```
1. User prompt → CLAUDE.md chargé (54 lignes, ~350 tokens)
2. Keywords détectés → skill:mnemolite-architecture invoqué (+~500 tokens)
3. Keywords détectés → skill:mnemolite-gotchas invoqué (+~300 tokens)
4. Keywords détectés → skill:epic-workflow invoqué (+~200 tokens)
5. skill:document-lifecycle NON invoqué (pas de keywords match)

Total: ~1,350 tokens (vs ~2,600 si tous chargés)
Savings: ~48% grâce progressive disclosure
```

**Validation**: Claude mentionne skills invoqués (pas tous les 5)

---

### Test 6: Référencement Skills ✅

**Expected**: CLAUDE.md v4.0 devrait référencer skills correctement

**Dans § IDENTITY**:
```
MnemoLite: PG18.cognitive.memory ⊕ CODE.INTEL → skill:mnemolite-architecture
```

**Dans § CRITICAL.HEURISTICS**:
```
! Skills.First → query.skills → assume.less → progressive.disclosure
→ Full.catalog: skill:mnemolite-gotchas (31) | skill:claude-md-evolution (frameworks)
```

**Validation**: Claude cite "→ skill:mnemolite-architecture" explicitement

---

### Test 7: Réponse Structurée Complète ✅

**Expected Format**:

```markdown
## 🎯 Architecture Recommendation

**Service Structure** (skill:mnemolite-architecture):
[Structure détaillée avec Protocol, DI, async patterns]

**Critical Gotchas** (skill:mnemolite-gotchas):
- ⚠️ CRITICAL-01: TEST_DATABASE_URL required
- ⚠️ CRITICAL-02: Async everything (use aioredis)
- ⚠️ Edit tool: Read file first

**Workflow** (skill:epic-workflow):
[Story sizing: ~8pts, workflow steps]

## 📋 Implementation Checklist

1. [ ] Read existing service (EXTEND>REBUILD principle)
2. [ ] Create NotificationServiceProtocol in interfaces/services.py
3. [ ] Implement NotificationService (async) in services/
4. [ ] Add DI in dependencies.py
5. [ ] Create routes/notifications.py with WebSocket
6. [ ] Write tests with TEST_DATABASE_URL + EMBEDDING_MODE=mock
7. [ ] Integrate into code_indexing_service.py

## 🚨 Critical Rules

- ✅ ASYNC.FIRST: Use aioredis (not sync redis.publish)
- ✅ PROTOCOL.DI: Implement NotificationServiceProtocol
- ✅ TEST_DATABASE_URL: Required for tests
- ✅ EXTEND>REBUILD: Copy existing service pattern

## 📝 References

- Architecture: skill:mnemolite-architecture (DIP patterns)
- Gotchas: skill:mnemolite-gotchas (CRITICAL-01, CRITICAL-02)
- Workflow: skill:epic-workflow (Story sizing)
- Principles: CLAUDE.md § PRINCIPLES (async.first, Protocol.Based.DI)
```

---

## ✅ Checklist Validation Complète

**CLAUDE.md v4.0 (Cognitive Engine)**:
- [ ] Principes cités (async.first, Protocol.Based.DI, EXTEND>REBUILD)
- [ ] Heuristiques critiques mentionnées (Skills.First, Test.First)
- [ ] Workflows cognitifs appliqués (Test → Implement → Document)
- [ ] Références skills correctes (→ skill:name)

**Skills Ecosystem (Knowledge Base)**:
- [ ] skill:mnemolite-architecture invoqué (structure, DIP, patterns)
- [ ] skill:mnemolite-gotchas invoqué (CRITICAL-01, CRITICAL-02, etc.)
- [ ] skill:epic-workflow invoqué (sizing, workflow)
- [ ] skill:document-lifecycle NON invoqué (pas de keywords)

**Progressive Disclosure**:
- [ ] Pas tous les skills chargés (seulement ceux nécessaires)
- [ ] Réponse structurée avec références explicites
- [ ] Token efficiency (≤1,500 tokens vs 2,600 si tous chargés)

**Qualité Réponse**:
- [ ] Architecture claire (Protocol, DI, structure fichiers)
- [ ] Gotchas critiques identifiés (3-4 minimum)
- [ ] Workflow guidé (Story vs EPIC, steps)
- [ ] Implementation checklist actionnable
- [ ] Références skills/CLAUDE.md explicites

**Si TOUTES les cases cochées**: ✅ Système validé en conditions réelles!

---

## 🎯 Tests Bonus (Si Validation OK)

### Bonus 1: Test EXTEND>REBUILD

**Prompt**:
```
Je vais créer le NotificationService. Par où commencer? Dois-je tout écrire from scratch?
```

**Expected**:
```
❌ NON! EXTEND>REBUILD principle (CLAUDE.md § CRITICAL.HEURISTICS)

1. Lis service existant similaire:
   - EmbeddingService (api/services/embedding_service.py)
   - SearchService (api/services/search_service.py)

2. Copie structure:
   - Protocol definition
   - __init__ avec dependencies
   - Async methods
   - Error handling

3. Adapte pour notifications:
   - Replace embedding logic → notification logic
   - Keep structure, DI pattern, async

→ 10x plus rapide que from scratch!
```

---

### Bonus 2: Test Gotchas Spécifiques

**Prompt**:
```
J'ai écrit mes tests dans tests/test_notification_service.py. Je lance:
pytest tests/test_notification_service.py

Ça prend 2 minutes et j'ai des warnings "Using dev database". C'est normal?
```

**Expected**:
```
🚨 NON! Deux gotchas critiques:

1. CRITICAL-01 violé:
   - Utilise dev DB → POLLUTION!
   - Fix: export TEST_DATABASE_URL=postgresql://...mnemolite_test

2. CRITICAL-05 (si embedding):
   - 2min = model loading
   - Fix: export EMBEDDING_MODE=mock

Reference: skill:mnemolite-gotchas
```

---

### Bonus 3: Test Version Bump (Meta)

**Prompt**:
```
Feature implémentée! Dois-je mettre à jour CLAUDE.md avec les infos sur NotificationService? Si oui, où et quelle version?
```

**Expected**:
```
Test skill:claude-md-evolution (meta):

F1 HOW vs WHAT Test:
  "NotificationService details" = WHAT (implementation fact)
  Score: 0/6 → Skill

F4 DSL Compression Test:
  Cannot compress to 1L.DSL (details)

Decision: skill:mnemolite-architecture (update)
Version CLAUDE.md: NO BUMP (pas de changement CM)
Version skill: MINOR (skill:mnemolite-architecture v2.1.0)

Reference: skill:claude-md-evolution
```

---

## 📊 Metrics à Collecter

**Token Usage**:
- CLAUDE.md startup: ~350 tokens
- Skills invoqués: ~1,000-1,200 tokens
- Total: ~1,350-1,550 tokens
- vs Full load (5 skills): ~2,600 tokens
- **Savings**: ~40-45%

**Skills Invoked**:
- Expected: 3 (architecture, gotchas, epic-workflow)
- Not invoked: 2 (document-lifecycle, claude-md-evolution)
- **Precision**: 60% (3/5 relevant invoqués)

**Response Quality**:
- Principes CLAUDE.md cités: Count
- Gotchas spécifiques: Count (target ≥3)
- Skills référencés: Count
- Implementation checklist: Present?

---

**Recommendation**: Utilise Prompt Principal, valide checklist complète, puis tests bonus

**Doc complète**: Ce fichier contient tous les résultats attendus détaillés
