# PLAN — EPIC-50 : Vectorisation complète BGE-M3 (suppression troncation 2000 chars)

**Statut** : PLAN — prêt pour implémentation
**Date** : 2026-06-11
**Estimation** : 5 points (2h)
**Stories** : 4
**Spec** : `docs/superpowers/specs/2026-06-11_15-30_mnemolite_embedding_full_context_EPIC.md`

---

## Contexte

`write_memory` MCP tronque le texte à **2 000 caractères** avant vectorisation BGE-M3. Le modèle supporte 8 192 tokens (~30 000–47 000 chars en français). Résultat : 78 % des investigations sont tronquées, la recherche sémantique est aveugle au-delà des 2 000 premiers caractères. Test réel sur un document de 32K chars : 1/6 requêtes sémantiques seulement retrouvent le document.

**Root cause** : deux lignes dans `memory_tools.py` et une constante dans `reindex_bge_m3.py`. Copié-collé historique sans remise en question.

---

## Current vs Target

| Composant | Before | After |
|-----------|--------|-------|
| Troncation | `text[:2000]` dans `_trigger_async_embedding` | Supprimé — texte intégral |
| Préfixe | Construit dans `_trigger_async_embedding` | Centralisé dans `LazyEmbeddingService.generate_embedding()` |
| Textes > 8 192 tokens | Non géré (crash ou résultat undefined) | Chunking + mean pooling → 1 vecteur 1024d |
| Ratio chars/tokens | Non mesuré | 3.7–5.8 chars/token (mesuré conteneur MCP) |
| Seuil chunking réel | Inconnu | ~30 000–47 000 chars (5–16 % des investigations) |
| `MAX_CONTENT_LENGTH` | 2 000 (arbitraire) | 100 000 (sécurité RAM) |

---

## Stories

### 50.1 — Supprimer la troncation et centraliser le préfixe

**Phase** : P0 | **Priorité** : Bloquant | **Fichiers** : `memory_tools.py`, `reindex_bge_m3.py`

**Problème** : `_trigger_async_embedding` (lignes 325-329) tronque à 2 000 chars et construit un préfixe qui sera dupliqué par T2 (50.2).

**Solution** :
1. Supprimer les lignes 325-329 dans `_trigger_async_embedding` :
   ```diff
   -                if len(text) > 2000:
   -                    text = text[:2000]
   -                prefix = "Represent this passage for retrieval: "
   -                text_for_embedding = prefix + text
   -                embedding = await emb_svc.generate_embedding(text_for_embedding)
   +                embedding = await emb_svc.generate_embedding(text)
   ```
2. Dans `reindex_bge_m3.py` ligne 43 :
   ```diff
   - MAX_CONTENT_LENGTH = 2000
   + MAX_CONTENT_LENGTH = 100_000  # Hard RAM safety limit
   ```
3. Supprimer toute construction de préfixe dans `reindex_bge_m3.py` si elle existe (le préfixe est désormais centralisé dans `generate_embedding()` — 50.2). Vérifier avec `grep -n 'Represent this passage' scripts/reindex_bge_m3.py`.

**Validation** :
- Le code compile sans erreur de syntaxe
- `grep -n "2000" api/mnemo_mcp/tools/memory_tools.py` ne retourne plus la troncation
- `grep -n "prefix.*Represent this passage" api/mnemo_mcp/tools/memory_tools.py` ne retourne rien

---

### 50.2 — Chunking + mean pooling dans LazyEmbeddingService

**Phase** : P0 | **Priorité** : Bloquant | **Fichier** : `server.py` (classe `LazyEmbeddingService`)

**Problème** : `generate_embedding()` ne gère pas les textes dépassant 8 192 tokens. Le préfixe n'est pas ajouté de façon centralisée.

**Solution** :
1. Dans `_ensure_initialized()`, ajouter l'accès au tokenizer avec fallback :
   ```python
   try:
       self._tokenizer = self._service.tokenizer
   except AttributeError:
       from transformers import AutoTokenizer
       self._tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-m3")
   ```
2. Ajouter les constantes en haut du fichier :
   ```python
   PREFIX = "Represent this passage for retrieval: "
   MAX_TOKENS = 8192  # Limite native BGE-M3 (12 tokens de préfixe inclus)
   CHUNK_SIZE = 8000
   CHUNK_OVERLAP = 256
   ```
3. Réécrire `generate_embedding()` :
   ```python
   async def generate_embedding(self, text: str) -> List[float]:
       if not text or not text.strip():
           return []
       await self._ensure_initialized()
       loop = asyncio.get_event_loop()
       tokenizer = self._tokenizer
       service = self._service
       
       def _encode():
           full_text = PREFIX + text
           tokens = tokenizer.encode(full_text)
           if len(tokens) <= MAX_TOKENS:
               return service.encode(full_text, normalize_embeddings=True)
           chunks = []
           for i in range(0, len(tokens), CHUNK_SIZE):
               chunk_tokens = tokens[i:i + CHUNK_SIZE + CHUNK_OVERLAP]
               chunk_text = tokenizer.decode(chunk_tokens, skip_special_tokens=True)
               chunks.append(chunk_text)
           embeddings = service.encode(chunks, normalize_embeddings=True)
           pooled = np.mean(embeddings, axis=0)
           return pooled / np.linalg.norm(pooled)
       
       return await loop.run_in_executor(None, _encode)
   ```
4. Vérifier que `import numpy as np` et `import asyncio` sont présents en haut du fichier. Les ajouter si absents (attention : `asyncio` est probablement déjà importé).

**Prérequis** (à vérifier AVANT de coder) :
```bash
docker compose exec mcp python3 -c "
from sentence_transformers import SentenceTransformer
m = SentenceTransformer('BAAI/bge-m3')
print('tokenizer:', type(m.tokenizer).__name__)
print('OK' if hasattr(m, 'tokenizer') else 'FALLBACK NEEDED')
"
```
Si `hasattr` retourne False → utiliser `AutoTokenizer.from_pretrained("BAAI/bge-m3")` comme fallback (déjà prévu dans le code).

**Validation** :
- `docker compose exec mcp python3 -c "from mnemo_mcp.server import mcp_server_instance; ..."` — le service s'initialise sans erreur
- Test unitaire : `generate_embedding("Test")` retourne une liste de 1 024 floats
- Test chunking : `generate_embedding("x " * 50_000)` ne crashe pas

---

### 50.3 — Rebuild, déploiement et smoke test

**Phase** : P0 | **Priorité** : Bloquant

**Solution** :
1. Lancer les tests existants : `pytest tests/ -x -q` — doit retourner 0 fail
2. `docker compose build mcp && docker compose up -d mcp`
3. Vérifier que le conteneur est healthy : `docker compose ps mcp`
4. `write_memory` MCP d'un document de 32K chars (l'INTEGRATION)
4. Vérifier en DB : `embedding_model = 'BAAI/bge-m3'`, embedding présent
5. Attendre 3 minutes si cold start (lazy loading BGE-M3 ~135s), ou 10 secondes si le modèle est déjà chargé. Vérifier avec `docker stats mnemo-mcp --no-stream` : si RAM > 2 GB, le modèle est chargé.
6. Vérifier que le MCP reste responsive pendant le chargement (`ping` < 200ms)

**Validation** :
- `write_memory` répond en < 500ms
- L'embedding apparaît en DB dans les 3 minutes (cold start) ou 5 secondes (modèle chaud)
- `write_memory` doc 60K chars → pas de crash, embedding 1024d stocké (test chunking)
- `search_memory` "Fanon violence décoloniale" → INTEGRATION dans le top 10
- `search_memory` "Foucault pouvoir dispositif" → score ≥ baseline (0.016)

**Gate conditionnelle** (après validation) :
- ✅ Embedding en DB + pas de crash → **50.3 SUCCESS**. Continuer vers 50.4.
- ⚠️ `search_memory` échoue malgré embedding OK → **non bloquant pour cet EPIC**. Le problème est dans `search_memory` (cf. EPIC §0.1). Ouvrir un ticket séparé. Continuer vers 50.4.
- ❌ Crash ou embedding absent → **HALTE**. Corriger avant de continuer.

---

### 50.4 — Re-indexation des mémoires existantes

**Phase** : P1 | **Priorité** : Important | **Fichier** : `scripts/reindex_bge_m3.py`

**Problème** : Les 36 940 mémoires existantes ont des embeddings tronqués à 2 000 chars. Après T1+T2, elles doivent être regénérées avec le texte complet.

**Solution** :
1. Vérifier que `reindex_bge_m3.py` utilise `generate_embedding()` du `LazyEmbeddingService`. Si le script a son propre encodage ou préfixe, le migrer pour appeler `LazyEmbeddingService.generate_embedding()` — comme le fait `_trigger_async_embedding` après 50.1.
2. Lancer le script : `docker compose exec mcp python3 scripts/reindex_bge_m3.py`
3. Vérifier : `SELECT COUNT(*) FROM memories WHERE embedding_model = 'BAAI/bge-m3'`

**Validation** :
- 100 % des mémoires ont `embedding_model = 'BAAI/bge-m3'` après ré-indexation
- Aucune mémoire avec `embedding IS NULL AND content IS NOT NULL AND content != ''`

---

## Risques et Rollback

| Risque | Probabilité | Impact | Mitigation |
|--------|:----------:|:------:|-----------|
| Tokenizer non accessible dans DualEmbeddingService | Faible | Bloquant | Fallback `AutoTokenizer` déjà prévu dans 50.2 |
| Cold start BGE-M3 bloque l'event loop | Nul | — | Déjà géré par `run_in_executor` (thread séparé) |
| Mean pooling dilue la précision sur longs docs | Faible (3–16 % des investigations) | Modéré | Monitorer scores post-déploiement. EPIC V2 multi-vecteur si nécessaire |
| Concurrence : N `write_memory` simultanés | Modérée | Faible | GPU lock sérialise les appels automatiquement |
| `reindex_bge_m3.py` utilise son propre préfixe → double préfixe | Faible | Bloquant | Vérifié dans 50.1 |

**Rollback** : `git revert` du commit. Les embeddings regénérés sont compatibles avec l'ancien code (même format 1024d).

---

## Ordre d'exécution

```
50.1 (truncation + préfixe)
  ↓
50.2 (chunking + mean pooling)
  ↓
50.3 (rebuild + smoke test)
  ↓
50.4 (re-indexation)
```

50.1 et 50.2 modifient des fichiers différents (`memory_tools.py` vs `server.py`) et peuvent être codés en parallèle. Attention : 50.2 part du principe que le préfixe N'EST PLUS dans `_trigger_async_embedding` (supprimé par 50.1). Les deux développeurs doivent se coordonner sur ce point. 50.3 nécessite les deux. 50.4 nécessite 50.3 validé.
