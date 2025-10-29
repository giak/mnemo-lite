# Test MCP MnemoLite - Conditions Réelles

**Objectif**: Tester le système COMPLET via MCP uniquement, sans shortcuts SQL/Python

**Principe**: Si on ne peut pas le tester via MCP, alors il ne fonctionne pas vraiment

---

## 🎯 Stratégie de Test

### Niveau 1: Tests Unitaires MCP
✅ Chaque outil MCP fonctionne isolément

### Niveau 2: Tests d'Intégration
✅ Les outils MCP communiquent entre eux

### Niveau 3: Tests End-to-End
✅ Hook → MCP → DB → MCP → User (flow complet)

### Niveau 4: Tests en Conditions Réelles
✅ Scénarios utilisateur réalistes

### Niveau 5: Stress & Edge Cases
✅ Limites, erreurs, performance

---

## 📊 Outils MCP pour Conversations

### Écriture
- `mcp__mnemolite__write_memory` - Créer mémoire
- `mcp__mnemolite__update_memory` - Modifier mémoire (pas encore testé!)
- `mcp__mnemolite__delete_memory` - Supprimer mémoire (pas encore testé!)

### Lecture
- `ReadMcpResourceTool(server="mnemolite", uri="memories://list")` - Lister mémoires
- `ReadMcpResourceTool(server="mnemolite", uri="memories://search?q=...")` - Chercher
- `ReadMcpResourceTool(server="mnemolite", uri="memories://{id}")` - Get by ID

### Metadata
- `mcp__mnemolite__ping` - Health check

---

## 🧪 Plan de Test Exhaustif

### PHASE 1: Tests Unitaires MCP (10 tests)

#### Test 1.1: write_memory - Conversation Basique
```
Tool: mcp__mnemolite__write_memory
Input:
  - title: "Test Conv 1: Simple message"
  - content: "User: Hello\nClaude: Hi there!"
  - memory_type: "conversation"
  - tags: ["test", "phase1", "simple"]
  - author: "TestSuite"

Expected:
  - Memory created with UUID
  - Embedding generated (768D)
  - Tags stored correctly
  - created_at recent

Verify via: ReadMcpResourceTool(uri="memories://{id}")
```

#### Test 1.2: write_memory - Conversation Complexe
```
Input:
  - title: "Test Conv 2: Multi-line avec code"
  - content: """
    User: Comment implémenter un cache?

    Claude: Voici une solution:
    ```python
    class Cache:
        def __init__(self):
            self.data = {}
    ```
    """
  - memory_type: "conversation"
  - tags: ["test", "phase1", "code", "multiline"]

Expected:
  - Code blocks préservés
  - Markdown intact
  - Embedding capture le code
```

#### Test 1.3: write_memory - Caractères Spéciaux
```
Input:
  - content: "User: Test émojis 🎉 et accents éàç\nClaude: Çà fonctionne!"
Expected:
  - UTF-8 correctement encodé
  - Émojis préservés
  - Accents intacts
```

#### Test 1.4: write_memory - Conversation Longue
```
Input:
  - content: [10 000 caractères de conversation]
Expected:
  - Pas de truncation
  - Performance < 100ms
  - Embedding généré
```

#### Test 1.5: write_memory - Tags Multiples
```
Input:
  - tags: ["test", "bug", "fix", "database", "sqlalchemy", "epic-24"]
Expected:
  - Tous tags stockés
  - Recherche par n'importe quel tag fonctionne
```

#### Test 1.6: list_memories - Sans Filtre
```
Resource: memories://list
Expected:
  - Liste TOUTES les conversations
  - Pagination fonctionne
  - Ordre chronologique
```

#### Test 1.7: list_memories - Filtre par Tag
```
Resource: memories://list?tags=test,phase1
Expected:
  - Uniquement conversations avec ces tags
  - Opérateur AND (les deux tags requis)
```

#### Test 1.8: search_memories - Recherche Texte
```
Resource: memories://search?q=cache+implementation
Expected:
  - Résultats pertinents
  - Full-text search fonctionne
  - Ranking correct
```

#### Test 1.9: get_memory - By ID
```
Resource: memories://{uuid}
Expected:
  - Retourne la mémoire exacte
  - Tous champs présents
  - Embedding NOT NULL
```

#### Test 1.10: ping - Health Check
```
Tool: mcp__mnemolite__ping
Expected:
  - Latency < 10ms
  - All services UP
  - Version spec correcte
```

---

### PHASE 2: Tests d'Intégration (5 tests)

#### Test 2.1: Write → Read Cycle
```
1. write_memory(title="Test Integration 1")
2. Récupérer ID retourné
3. ReadMcpResourceTool(uri=f"memories://{id}")
4. Vérifier: contenu identique
```

#### Test 2.2: Write → Search → Read
```
1. write_memory(content="Unique keyword: XYZTEST123")
2. memories://search?q=XYZTEST123
3. Vérifier: résultat trouvé
4. Get by ID
5. Vérifier: contenu exact
```

#### Test 2.3: Write Multiple → List Filtered
```
1. write_memory() x3 avec tags différents
2. memories://list?tags=specific-tag
3. Vérifier: uniquement les bonnes conversations
```

#### Test 2.4: Write → Update → Verify
```
1. write_memory(title="Original")
2. update_memory(id, title="Modified")
3. Get by ID
4. Vérifier: title = "Modified"
5. Vérifier: updated_at > created_at
```

#### Test 2.5: Write → Delete (Soft) → Verify
```
1. write_memory()
2. delete_memory(id, soft=True)
3. memories://list → Mémoire absente
4. SQL direct (pour vérifier soft): deleted_at NOT NULL
```

---

### PHASE 3: Tests End-to-End (3 scénarios)

#### Scénario 3.1: Session Complète Simulée
```
Simulate:
  1. User ouvre session
  2. User: "Comment debugger un bug SQLAlchemy?"
  3. Hook Stop déclenché
  4. write_memory via MCP
  5. User: "Cherche conversations sur SQL"
  6. Hook UserPromptSubmit
  7. search_memories via MCP
  8. Context injecté dans prompt
  9. Claude répond avec contexte

Verify:
  - Conversation sauvegardée
  - Recherche retourne conversation précédente
  - Context retrieval fonctionne
```

#### Scénario 3.2: Multi-Session Context
```
Session 1:
  - User parle de "cache Redis"
  - Conversation sauvegardée

Session 2 (lendemain):
  - User demande "Comment on avait implémenté le cache?"
  - Search trouve conversation Session 1
  - Context injecté
  - Claude répond avec info Session 1

Verify:
  - Context persiste entre sessions
  - Recherche sémantique trouve bon contexte
```

#### Scénario 3.3: Workflow Bug → Fix → Trace
```
1. User signale bug
   - Conversation sauvegardée: "Bug database connection"

2. Claude analyse
   - Conversation sauvegardée: "Root cause: pool_size=0"

3. User applique fix
   - Conversation sauvegardée: "Fix applied: pool_size=10"

4. User cherche historique bug
   - search_memories("database connection bug")
   - Retourne les 3 conversations dans l'ordre

Verify:
  - Traçabilité complète
  - Chronologie préservée
  - Recherche trouve toutes étapes
```

---

### PHASE 4: Tests Conditions Réelles (5 scénarios)

#### Scénario 4.1: Journée Développement Typique
```
Timeline:
09:00 - "Bon, on fait quoi aujourd'hui?"
09:30 - "Implement feature X"
10:00 - "Bug dans le code Y"
10:30 - "Fix bug Y avec solution Z"
11:00 - "Code review: suggestions"
14:00 - "Recherche: comment on avait fait feature similaire?"
15:00 - "Implement tests"
16:00 - "Documentation"
17:00 - "Recap de la journée"

Actions:
  - 8 conversations sauvegardées
  - Recherche mid-day trouve contexte matin
  - Recap utilise toutes conversations du jour

Verify:
  - Toutes conversations capturées
  - Recherche temporelle fonctionne
  - Tags auto (date:YYYYMMDD) corrects
```

#### Scénario 4.2: Debugging Session Intense
```
Timeline: 10 échanges rapides sur même bug
  1. "Erreur: Connection timeout"
  2. "Vérifie logs"
  3. "Logs montrent pool full"
  4. "Change pool_size"
  5. "Toujours timeout"
  6. "Vérifie max_overflow"
  7. "max_overflow=0!"
  8. "Fix: max_overflow=20"
  9. "Test: fonctionne!"
  10. "Document fix dans code"

Actions:
  - 10 conversations sauvegardées rapidement (< 1 min entre chaque)
  - Performance hook ne dégrade pas Claude
  - Recherche "connection timeout fix" trouve toute séquence

Verify:
  - Performance sous charge
  - Séquence préservée
  - Pas de race conditions
```

#### Scénario 4.3: Recherche Complexe Multi-Critères
```
User: "Trouve conversations sur bugs database des 7 derniers jours"

Search criteria:
  - memory_type: conversation
  - tags: contains "bug" OR "fix"
  - content: contains "database"
  - created_at: > NOW() - 7 days
  - has_embedding: true

Verify:
  - Filtres combinés fonctionnent
  - Performance < 500ms
  - Résultats pertinents
```

#### Scénario 4.4: Large Conversation (Edge Case)
```
Input: Conversation 50 000 caractères
  - Discussion architecture très détaillée
  - Multiples code snippets
  - Diagrammes ASCII

Actions:
  - write_memory
  - Embedding généré
  - Recherche fonctionne

Verify:
  - Pas de truncation
  - Embedding capture essence
  - Performance acceptable
```

#### Scénario 4.5: Caractères Problématiques
```
Input: Conversation avec:
  - SQL injection attempts: '; DROP TABLE--
  - Quotes: "test" 'test' `test`
  - Backslashes: C:\\Users\\test
  - Unicode: 你好 مرحبا שלום
  - Emoji combos: 👨‍👩‍👧‍👦 🏳️‍🌈

Verify:
  - Aucune injection
  - Tous caractères préservés
  - Pas d'erreur encoding
```

---

### PHASE 5: Stress & Performance (5 tests)

#### Test 5.1: Stress Write - 100 Conversations Rapides
```
Action: Boucle write_memory x100 en 1 minute
Verify:
  - Toutes sauvegardées
  - Pas de duplicates
  - Pas d'erreurs pool
  - Performance stable
```

#### Test 5.2: Stress Search - 50 Requêtes Concurrentes
```
Action: 50 search_memories en parallèle
Verify:
  - Toutes retournent résultats
  - Pas de timeout
  - Performance moyenne < 200ms
```

#### Test 5.3: Large Dataset - 1000 Conversations
```
Setup: Créer 1000 conversations
Action: Search dans ce dataset
Verify:
  - Recherche reste rapide
  - Pertinence maintenue
  - Pagination fonctionne
```

#### Test 5.4: Concurrent Write/Read
```
Action:
  - Thread 1: write_memory loop
  - Thread 2: search_memories loop
  - Thread 3: list_memories loop

Verify:
  - Pas de deadlocks
  - Pas de race conditions
  - Read voir writes récents
```

#### Test 5.5: Memory Leak Check
```
Action: 1000 operations write/search sur 10 minutes
Monitor:
  - Memory usage API container
  - DB connections actives
  - Cache size Redis

Verify:
  - Pas de leak mémoire
  - Connections pool stable
  - Cache bounded
```

---

## 🚨 Edge Cases Critiques

### Edge Case 1: Empty Content
```
write_memory(content="")
Expected: Erreur validation, pas crash
```

### Edge Case 2: Null Fields
```
write_memory(title=None, author=None)
Expected: Defaults appliqués
```

### Edge Case 3: Duplicate Detection
```
write_memory(même content 2x)
Expected: 2 mémoires (timestamps différents)
```

### Edge Case 4: Invalid UUID
```
ReadMcpResourceTool(uri="memories://invalid-uuid")
Expected: 404 graceful, pas crash
```

### Edge Case 5: Tag Injection
```
tags: ["valid", "'; DROP TABLE memories--"]
Expected: Tag escaped, pas injection
```

---

## 📏 Métriques de Succès

### Performance
- write_memory: < 50ms (p95)
- search_memories: < 200ms (p95)
- list_memories: < 100ms (p95)

### Fiabilité
- Success rate: > 99.9%
- No data loss: 100%
- Encoding errors: 0

### Qualité Recherche
- Precision@5: > 80%
- Recall: > 70%
- Search relevance: user satisfaction

---

## 🛠️ Outils de Test

### Test Runner
```python
# test_mcp_exhaustif.py
import asyncio
from typing import List, Dict

class MCPTestRunner:
    def __init__(self):
        self.results = []

    async def run_phase(self, phase: int):
        tests = self.get_phase_tests(phase)
        for test in tests:
            result = await self.run_test(test)
            self.results.append(result)

    async def run_test(self, test: Dict):
        # Use ONLY MCP tools
        # No SQL, no direct Python
        pass
```

### Assertion Framework
```python
class MCPAssertions:
    @staticmethod
    async def assert_memory_exists(memory_id: str):
        # Via MCP only
        resource = await read_mcp_resource(f"memories://{memory_id}")
        assert resource is not None

    @staticmethod
    async def assert_search_finds(query: str, expected_id: str):
        # Via MCP only
        results = await search_memories(query)
        ids = [r['id'] for r in results]
        assert expected_id in ids
```

---

## 📝 TODO: Implémentation

1. [ ] Créer test_mcp_exhaustif.py (framework)
2. [ ] Implémenter Phase 1 tests (unitaires)
3. [ ] Implémenter Phase 2 tests (intégration)
4. [ ] Implémenter Phase 3 tests (E2E)
5. [ ] Implémenter Phase 4 tests (conditions réelles)
6. [ ] Implémenter Phase 5 tests (stress)
7. [ ] Run all tests
8. [ ] Document findings
9. [ ] Fix issues found
10. [ ] Re-run tests jusqu'à 100% pass

---

**Status**: PLAN CREATED - READY FOR IMPLEMENTATION
**Next**: Implement test framework using MCP tools ONLY
