# 🔧 EPIC-79 : Artefact `embedding_generated: false` de write_memory — rendre le flag honnête

> **Status:** DONE — implémenté, validé et commité (2026-08-09)
> **Priority:** P2 : fausse alerte récurrente pour les agents (vérifications/backfills inutiles)
> **Date:** 2026-08-08
> **Effort:** 2-3 h
> **Scope:** `api/mnemo_mcp/tools/memory_tools.py` + `tests/mnemo_mcp/test_memory_tools.py` (optionnel : docs)

## Diagnostic forensique (vérifié en code et en base, 2026-08-08)

**Symptôme** : `write_memory` retourne `embedding_generated: false` alors que l'embedding **est bien écrit** en base quelques secondes plus tard. Les agents (constaté en session le 2026-08-08 sur la mémoire `886badd1`) interprètent `false` comme un échec permanent et lancent des vérifications manuelles (`SELECT embedding_half IS NOT NULL`), voire des backfills inutiles.

**Mécanisme exact (lu dans `api/mnemo_mcp/tools/memory_tools.py`)** :

1. `WriteMemoryTool.execute` (l.236-239) : `embedding = None; embedding_generated = False` — **codé en dur**, avec le commentaire « CRITICAL FIX: Skip embedding generation in write_memory to avoid 10s+ cold start ».
2. La réponse (l.268) retourne `embedding_generated=embedding_generated` = **toujours `False`**, même quand la génération async va réussir.
3. `_trigger_async_embedding` (l.320) lance `asyncio.create_task(_generate())` **fire-and-forget** : l'UPDATE SQL `embedding/embedding_half/embedding_model` part en background et réussit dans les secondes suivantes (modèle BGE-M3 déjà chargé après EPIC-68).
4. `read_memory` (l.1136) est **correct** : `embedding_generated=memory.embedding is not None` — calculé à la lecture, à l'état réel.

**Preuve de santé du système** : 0 mémoire sans `embedding_half` sur 39 569 (vérifié en base) ; la mémoire EPIC-78 `886badd1` a `has_emb = t` et remonte en 1ʳᵉ position en recherche vectorielle (score 0.0328). **Le flag du write est donc un mensonge structurel, pas un vrai échec.**

## Décisions (validées avec l'utilisateur, 2026-08-08)

1. **On ne revient PAS à la génération synchrone bloquante** (elle a été retirée pour cause de cold start 10-50 s qui timeout le client MCP 30 s et le middleware 120 s). YAGNI de casser cette décision.
2. **Correctif : await la tâche async avec timeout court** — si le modèle est chaud (cas nominal après le premier write), l'embedding est écrit en <1 s et le flag devient **vrai honnête**. Si cold start (premier write après boot), on dépasse le timeout : flag `false` **+ champ `embedding_pending: true`** pour lever l'ambiguïté (l'embedding partira en background, comme aujourd'hui).
3. **Pattern anti-annulation** : utiliser `asyncio.wait({task}, timeout=...)` (et non `asyncio.wait_for`, qui **annule** la tâche au timeout). Si la tâche est encore pending au timeout, on la laisse tourner en background (fire-and-forget préservé).
4. **Le flag `embedding_generated` signifie désormais** « embedding écrit en base au moment de la réponse ». `embedding_pending: true` signifie « génération lancée en background, non terminée à la réponse ». Un `false` sans `pending` = échec réel (service absent, erreur).

## Implémentation

### 1. `api/mnemo_mcp/tools/memory_tools.py` — `_trigger_async_embedding`

- Retourner la tâche `asyncio.create_task(_generate())` au lieu de `None` (ou créer la tâche dans `execute`).
- La coroutine `_generate` doit retourner `True` en cas d'UPDATE réussi (actuellement `None`) pour que l'appelant connaisse l'issue.

### 2. `api/mnemo_mcp/tools/memory_tools.py` — `WriteMemoryTool.execute`

Remplacer le fire-and-forget actuel (l.248 + l.239/268) :

```python
# état réel au moment de la réponse
embedding_generated = False
embedding_pending = False

task = self._trigger_async_embedding(memory, content, embedding_source)
if task is not None:
    try:
        done, _pending = await asyncio.wait({task}, timeout=EMBEDDING_WRITE_TIMEOUT_S)
        if task in done:
            embedding_generated = bool(task.result())  # True si UPDATE réussi
        else:
            embedding_pending = True  # en background, non terminé
    except Exception:
        embedding_pending = True  # dégradation : background fera foi
```

- Constante module `EMBEDDING_WRITE_TIMEOUT_S = 10` (10 s < timeout middleware 120 s et client 30 s ; le cas nominal BGE-M3 chaud est < 1 s).
- Ajouter `embedding_pending` dans le dict retourné (après le `model_dump`, comme `duplicate_warning`).
- **Ne PAS** modifier `MemoryResponse` (champ non requis par le modèle) — champ ajouté au dict de retour uniquement, comme les autres champs conditionnels.
- Mettre à jour le docstring (`Returns:`).

### 3. `tests/mnemo_mcp/test_memory_tools.py`

3 asserts actuels `embedding_generated is False` à réconcilier (l.120, l.287, l.333) :
- `test_execute_success` (l.117) : fournir un `engine` mocké sur le repository + `embedding_service` qui retourne un vecteur → la tâche réussit → assert `embedding_generated is True`.
- `test_execute_embedding_failure_graceful_degradation` (l.284) : le service lève → la tâche échoue (catchée) → `task.result()` lève ? Non : `_generate` catch déjà l'exception interne et logge `async_embedding_failed` sans la re-propager → la tâche « réussit » avec `None` retour → `bool(None)` = False. Assert `embedding_generated is False` **sans** `embedding_pending` (échec réel) — à affiner selon l'implémentation exacte.
- `test_execute_no_embedding_service` (l.330) : `_trigger_async_embedding` skippe (pas de service) → pas de tâche → `embedding_generated is False`. Inchangé.
- Nouveau test : cold start simulé (embedding_service lent, > timeout) → `embedding_generated is False` + `embedding_pending is True`, et la tâche continue en background.

## Critères d'acceptation

- [x] `write_memory` (modèle chaud) retourne `embedding_generated: true` et l'embedding est vérifiable en base immédiatement (`embedding_half IS NOT NULL`) — couvert par `test_execute_success` (engine mock + UPDATE réussi → True)
- [x] Premier write après boot (cold start) retourne `embedding_generated: false` + `embedding_pending: true` (pas de timeout client) — couvert par `test_execute_cold_start_embedding_pending` (service lent > timeout patché)
- [x] `embedding_pending` documenté dans le docstring du tool MCP `write_memory` (`server.py`) — Returns mis à jour
- [x] `pytest tests/mnemo_mcp/test_memory_tools.py` : vert (28 passed), 3 asserts réconciliés + 1 nouveau test pending
- [x] Zéro régression sur `tests/mnemo_mcp/` : 437 passed / 1 failed **préexistant** (`test_write_then_search_finds_memory`, mock `mock_hybrid_search` insuffisant — échec identique constaté avec `git stash` sur le code EPIC-79 retiré ; hors périmètre) ; `test_mcp_http_integration.py` exclu du run (nécessite le serveur MCP 8002 non lancé, blocage préexistant)
- [ ] Vérification live MCP : `write_memory` réel → flag vrai + recherche vectorielle le retrouve (à faire au prochain boot MCP)
- [x] Doc EPIC-79 DONE + commit conventionnel

## Notes d'implémentation (2026-08-09)

- `_trigger_async_embedding` retourne désormais la `asyncio.Task` (ou `None` si pas de service) ; `_generate` retourne `True`/`False` selon l'issue de l'UPDATE.
- `WriteMemoryTool.execute` : `await asyncio.wait({task}, timeout=10)` (pas `wait_for` : anti-annulation). Tâche done → `bool(task.result())` ; timeout → `embedding_pending: true`. Exception sur `task.result()` → `embedding_generated: false` sans pending (échec réel, review point 1).
- `embedding_pending` ajouté au dict de retour uniquement si `True` (comme `duplicate_warning`), `MemoryResponse` inchangé.
- Review : 1 point corrigé (sémantique du `except` : échec ≠ pending).

## Notes de décision

- **Pourquoi ne pas renommer en `embedding_status`** : KISS — l'ajout d'un champ booléen `embedding_pending` suffit à lever l'ambiguïté sans casser les consommateurs existants de `embedding_generated`.
- **Pourquoi attendre 10 s** : le cas nominal (modèle chaud, EPIC-68) est < 1 s. 10 s couvre les lenteurs machine sans jamais approcher les timeouts client/middleware. Si la tâche n'a pas fini à 10 s, c'est un cold start : on retombe exactement sur le comportement actuel (background), sans régression de latence.
- **Pourquoi `asyncio.wait` et pas `wait_for`** : `wait_for` annule la tâche au timeout — l'embedding ne serait plus jamais écrit. `wait` laisse la tâche courir : le write-back actuel (qui fonctionne, 0 mémoire sans embedding) est préservé.
