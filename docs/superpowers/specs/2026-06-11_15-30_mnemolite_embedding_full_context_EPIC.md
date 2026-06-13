# EPIC — Vectorisation complète BGE-M3 : suppression de la troncation à 2000 caractères

**Date** : 2026-06-11
**Statut** : SPEC — en attente validation
**Sévérité** : CRITIQUE — perte de 83 % du contenu sémantique pour les documents longs
**Composant** : Mnemolite MCP — `write_memory` + async embedding

---

## §0 PROBLÈME

### Symptôme

Un document de 32 554 caractères sauvegardé via MCP `write_memory` n'est retrouvable par `search_memory` que sur les thèmes présents dans ses 2 000 premiers caractères. Les concepts des sections centrales et finales (Fanon, Arendt, Tarrow, Graeber, Guattari) sont **invisibles** pour la recherche sémantique.

### Cause racine

Deux lignes dans `memory_tools.py` et une constante dans `reindex_bge_m3.py` :

```python
# memory_tools.py:326-327
if len(text) > 2000:
    text = text[:2000]

# reindex_bge_m3.py:43
MAX_CONTENT_LENGTH = 2000  # Truncate before encoding (tokenizer is O(n) on input length)
```

Le texte est tronqué **avant** vectorisation. BGE-M3 supporte 8 192 tokens (~15 000-30 000 caractères selon la langue). On utilise **6 %** de sa capacité.

### Origine historique

Le script `reindex_bge_m3.py` a été écrit pour indexer des **conversations courtes** (échanges Claude Code). Le commentaire « tokenizer is O(n) on input length » trahit une optimisation paresseuse : plutôt que de compter les tokens, on a posé une limite arbitraire en caractères. Cette limite a été copiée-collée dans `_trigger_async_embedding` sans remise en question.

### Impact mesuré

Test réel sur le document `2026-06-11_theoriciens_absents_fanon_foucault_INTEGRATION.md` (12 000 chars, 6 théoriciens) :

| Requête search_memory | INTEGRATION retrouvé ? | Score |
|------------------------|----------------------|-------|
| Foucault — pouvoir dispositif | ✅ Rang #1 | 0.016 |
| Fanon — violence décoloniale | ❌ Absent | — |
| Arendt — action acéphale | ❌ Absent | — |
| Tarrow — mécanismes mobilisation | ❌ Absent | — |
| Graeber — horizontalité anarchie | ❌ Absent | — |
| Guattari — révolution moléculaire | ❌ Absent | — |

**1/6 seulement.** Les 5 absents sont tous dans les sections après 2 000 caractères. Le document fait 32 554 caractères au total — seuls les ~6 % initiaux sont vectorisés (2 000 / 32 554 chars).

**Données réelles sur la distribution des tailles** (2 726 investigations dans Mnemolite) :
- 78 % > 2 000 chars — la majorité est tronquée aujourd'hui (bug systématique)
- 16 % > 30 000 chars (448 docs) — seuil où le chunking *pourrait* démarrer selon le ratio chars/token
- 3 % > 50 000 chars (83 docs) — chunking certain
- 0.4 % > 100 000 chars (11 docs) — chunking lourd

**Ratio chars/tokens mesuré dans le conteneur MCP** (BGE-M3 tokenizer) :
- Français académique : 5.8 chars/token → seuil chunking ~47 000 chars
- Français dense : 3.7 chars/token → seuil chunking ~30 000 chars
- Préfixe "Represent this passage for retrieval: " : 12 tokens (pas 8)
- Limite effective pour le texte : 8 192 − 12 = 8 180 tokens

Le document INTEGRATION (32 554 chars) fait ~5 600−8 800 tokens selon la densité. À 5.8 chars/token (français académique, probable ici) : ~5 600 tokens → embedding direct. À 3.7 chars/token (français très dense) : ~8 800 tokens → nécessiterait 2 chunks. Seul un `tokenizer.encode()` du document complet tranche. La validation T4 testera les deux cas.

**Note importante — deux problèmes distincts :** Cet EPIC corrige la **troncation** (bug). Mais même avec le texte complet vectorisé, un document couvrant 6 théoriciens aux concepts orthogonaux (Fanon ≠ Guattari ≠ Arendt) restera un « flou sémantique » — un seul vecteur ne peut pas représenter fortement 6 thématiques divergentes. Le vrai gain pour les documents multi-thématiques viendra du **découpage en mémoires séparées** (1 par théoricien), pas seulement du full-context embedding. Ce second problème (dilution thématique) n'est pas traité par cet EPIC.


### Limite connue : la troncation n'explique pas tout

**Fait établi** : l'embedding BGE-M3 complet (4 100 bytes, `BAAI/bge-m3`, halfvec OK) a été généré et stocké en base pour le document INTEGRATION. Malgré cela, les recherches sémantiques post-embedding ont échoué pour 5 requêtes sur 6, avec des scores très bas (0.015) et des résultats parfois hors sujet (dark triad pour une requête Foucault).

**Ce que cet EPIC corrige** : la perte de contenu due à la troncation à 2 000 caractères. Le texte complet sera vectorisé.

**Ce que cet EPIC ne corrige pas** : la qualité intrinsèque du retrieval hybride (`search_memory`). Les scores anormalement bas et les résultats non pertinents suggèrent un problème distinct dans l'algorithme de recherche ou l'index pgvector. Une investigation séparée du `search_memory` est nécessaire — non couverte par cet EPIC.

**Impact sur les attentes** : après T1+T2, le document sera intégralement vectorisé, mais le recall pourrait rester médiocre tant que le problème de retrieval sous-jacent n'est pas diagnostiqué.

---

## §1 DIAGNOSTIC TECHNIQUE

### BGE-M3 : capacité réelle

| Métrique | Valeur |
|----------|--------|
| Modèle | `BAAI/bge-m3` |
| Dimensions | 1 024 |
| Tokens max | **8 192** |
| Équivalent caractères (français) | ~30 000-47 000 (mesuré : 3.7–5.8 chars/token × 8 192) |
| Équivalent caractères (anglais) | Non mesuré — estimé ~40 000-60 000 |
| Capacité utilisée aujourd'hui | **~500 tokens (6 %)** |

### Architecture actuelle du flux d'embedding

```
write_memory (MCP, ~200ms)
    ↓ répond immédiatement
    ↓ asyncio.create_task()
_generate() [background task]
    ↓
LazyEmbeddingService.generate_embedding(text)
    ↓ [TRONCATION 2000 CHARS ICI]
    ↓
SentenceTransformer.encode(text) → vecteur 1024d
    ↓
UPDATE memories SET embedding=..., embedding_half=..., embedding_model='BAAI/bge-m3'
```

### Points de blocage identifiés

1. **Troncation 2000 chars** — `memory_tools.py:326-327`
2. **Pas de comptage de tokens** — on tronque en caractères, pas en tokens. Un texte de 2 000 caractères français fait ~500 tokens, loin des 8 192.
3. **Pas de stratégie pour les textes > 8 192 tokens** — si on supprime la troncation, que faire des documents qui dépassent ?
4. **Pas de re-tokenization dans le service** — `LazyEmbeddingService` ne vérifie pas si l'input dépasse la limite du modèle.
5. **Concurrence séquentielle (GPU-locked)** — si 10 `write_memory` sont appelés en rafale, 10 tâches async d'embedding se lancent simultanément mais `SentenceTransformer.encode()` sérialise les appels en interne (GPU lock). Latence additive, pas de parallélisme.

---

## §2 SOLUTION PROPOSÉE

### Architecture cible : 1 mémoire = 1 vecteur, sans perte

```
write_memory (MCP, ~200ms)
    ↓ répond immédiatement
    ↓ asyncio.create_task()
_generate() [background task, thread run_in_executor]
    ↓
LazyEmbeddingService.generate_embedding(text)
    ├─ tokenize(prefix + text) → n_tokens
    ├─ n_tokens ≤ 8180 → embedding direct (~85-95 % des cas)
    └─ n_tokens > 8184 → chunking (8000 tokens/chunk, overlap 256)
                           → mean pooling → L2 normalize
                           → 1 vecteur 1024d
    ↓
UPDATE memories SET embedding=..., embedding_half=..., embedding_model='BAAI/bge-m3'
```

### Pourquoi mean pooling et pas multi-vecteurs ?

| Approche | Avantage | Inconvénient |
|----------|---------|--------------|
| **Mean pooling (choisi)** | 0 migration DB, `search_memory` inchangé, simple | Dilution sémantique sur très longs docs (>30K chars) |
| Multi-vecteurs (N embedding rows) | Précision maximale | Migration DB lourde (table de jonction), `search_memory` complexe (agrégation de scores) |

**Décision** : Mean pooling pour le V1. ~5-16 % des investigations dépassent le seuil de chunking (30 000−47 000 chars selon la densité du français). Si la dilution sémantique devient problématique, un EPIC V2 passera au multi-vecteur.

### Chargement du tokenizer

Le `SentenceTransformer` expose son tokenizer interne. On peut y accéder via :

```python
# Dans LazyEmbeddingService._ensure_initialized()
try:
    self._tokenizer = self._service.tokenizer
except AttributeError:
    from transformers import AutoTokenizer
    self._tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-m3")

# Dans generate_embedding()
n_tokens = len(self._tokenizer.encode(text))
```

**Fallback** : si `.tokenizer` n'est pas exposé (cas rare), on charge `AutoTokenizer` séparément. Coût mémoire négligeable (le vocab est déjà en RAM via le modèle).

---

## §3 PLAN DE MISE EN ŒUVRE

### T1 — Supprimer la troncation et déplacer le préfixe (2 fichiers)

**Fichier** : `api/mnemo_mcp/tools/memory_tools.py`

```diff
-                if len(text) > 2000:
-                    text = text[:2000]
-                prefix = "Represent this passage for retrieval: "
-                text_for_embedding = prefix + text
-                embedding = await emb_svc.generate_embedding(text_for_embedding)
+                embedding = await emb_svc.generate_embedding(text)
```

**Pourquoi supprimer aussi le préfixe** : T2 ajoute le préfixe dans `generate_embedding()` (point central unique). Si on le laisse dans `_trigger_async_embedding`, le préfixe sera appliqué **deux fois** : `"Represent this passage for retrieval: Represent this passage for retrieval: <texte>"`.

**Fichier** : `scripts/reindex_bge_m3.py`

```diff
- MAX_CONTENT_LENGTH = 2000  # Truncate before encoding (tokenizer is O(n) on input length)
+ MAX_CONTENT_LENGTH = 100_000  # Hard RAM safety limit — not a semantic boundary
```

Vérifier aussi que `reindex_bge_m3.py` ne construit pas son propre préfixe — si oui, le supprimer (même raison : le préfixe est désormais dans `generate_embedding`).

**Impact** : Les textes de ≤8 184 tokens (hors préfixe) passent intacts. Les textes plus longs seront gérés par T2.

### T2 — Chunking + mean pooling dans LazyEmbeddingService

**Fichier** : `api/mnemo_mcp/server.py` (classe `LazyEmbeddingService`)

**Modifications** :

1. **Ajouter l'accès au tokenizer** dans `_ensure_initialized()` :
```python
try:
    self._tokenizer = self._service.tokenizer
except AttributeError:
    from transformers import AutoTokenizer
    self._tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-m3")
```

2. **Modifier `generate_embedding()`** :
```python
import numpy as np
import asyncio

PREFIX = "Represent this passage for retrieval: "
MAX_TOKENS = 8192  # Limite native BGE-M3 (préfixe de 12 tokens inclus)
CHUNK_SIZE = 8000
CHUNK_OVERLAP = 256

async def generate_embedding(self, text: str) -> List[float]:
    if not text or not text.strip():
        return []  # Garde-fou : texte vide
    await self._ensure_initialized()
    loop = asyncio.get_event_loop()
    tokenizer = self._tokenizer
    service = self._service

    def _encode():
        # Le préfixe est ajouté AVANT tokenization (consomme ~8 tokens)
        full_text = PREFIX + text
        tokens = tokenizer.encode(full_text)
        if len(tokens) <= MAX_TOKENS:
            # Chaque embedding est normalisé individuellement par SentenceTransformer
            return service.encode(full_text, normalize_embeddings=True)
        # Chunking : découpage avec overlap, batch encoding, mean pooling
        chunks = []
        for i in range(0, len(tokens), CHUNK_SIZE):
            chunk_tokens = tokens[i:i + CHUNK_SIZE + CHUNK_OVERLAP]
            chunk_text = tokenizer.decode(chunk_tokens, skip_special_tokens=True)
            chunks.append(chunk_text)
        embeddings = service.encode(chunks, normalize_embeddings=True)
        # Mean pooling + L2 re-normalize (les embeddings individuels sont déjà L2)
        pooled = np.mean(embeddings, axis=0)
        return pooled / np.linalg.norm(pooled)

    return await loop.run_in_executor(None, _encode)
```

**Notes** :
- L'encodage reste dans `run_in_executor` (thread) pour ne pas bloquer l'event loop
- Le préfixe est inclus dans le comptage de tokens (12 tokens mesurés, déduits du total de 8 192)
- `encode(normalize_embeddings=True)` normalise chaque chunk individuellement, puis L2 est réappliquée après mean pooling. Cette double normalisation est intentionnelle et correcte
- `SentenceTransformer.encode()` est thread-safe mais sérialise les appels en interne (GPU lock). Les appels concurrents sont mis en file d'attente automatiquement
- **Validation préalable obligatoire** : vérifier que `SentenceTransformer('BAAI/bge-m3').tokenizer` est accessible dans le conteneur Docker MCP avant d'implémenter T2. Si non, utiliser `AutoTokenizer.from_pretrained("BAAI/bge-m3")` comme fallback.

### T3 — Re-indexation des mémoires existantes

Lancer `reindex_bge_m3.py` après déploiement pour regénérer tous les embeddings avec le texte complet. Les 36 940 mémoires tronquées à 2 000 chars récupéreront leur contexte intégral.

**Coût estimé** :
- Modèle chaud : ~20-30 minutes pour 37K mémoires (débit réel ~20-30 embeddings/seconde avec batch processing)
- Cold start : ajouter ~3 minutes pour le chargement initial du modèle BGE-M3
- Le script met à jour à la fois `embedding` (1024d vector) et `embedding_half` (halfvec)

### T4 — Validation

| Test | Critère de succès |
|------|-------------------|
| `write_memory` doc 32K chars (taille réelle INTEGRATION) | Embedding direct (≤8 180 tokens), `embedding_model='BAAI/bge-m3'` |
| `search_memory` "Guattari révolution moléculaire" | INTEGRATION trouvé dans le top 5 |
| `search_memory` "Fanon violence décoloniale" | INTEGRATION trouvé dans le top 5 |
| `search_memory` "Foucault pouvoir dispositif" | INTEGRATION toujours trouvé (non-régression : le score ne doit pas baisser) |
| `write_memory` doc 12K chars (test court) | Embedding direct, `embedding_model='BAAI/bge-m3'` |
| `write_memory` doc 60K chars (test chunking) | Mean pooling activé, pas de crash, embedding 1024d stocké |
| `write_memory` texte vide `"   "` | Pas de crash, `generate_embedding` retourne `[]` |
| 5 × `write_memory` concurrents | Aucune erreur, tous les embeddings stockés |
| `write_memory` doc 60K chars (test chunking) | Mean pooling activé, pas de crash, embedding 1024d stocké |
| `search_memory` "Fanon violence décoloniale" post-T1 | INTEGRATION trouvé dans le top 10 (test de non-régression vs §0) |
| `search_memory` "Guattari révolution moléculaire" post-T1 | INTEGRATION trouvé dans le top 10 |
| `search_memory` "Foucault pouvoir dispositif" post-T1 | Score ≥ 0.016 (non-régression vs baseline) |
| MCP reste responsive pendant embedding | `ping` répond en <200ms |

**Note sur les tests retrieval** : si les 3 requêtes sémantiques échouent malgré l'embedding complet, le problème est dans `search_memory` et non dans la troncation → investigation séparée requise.

---

## §4 RISQUES ET TRADE-OFFS

### Risque 1 : Mean pooling dilue la précision sur les documents chunkés

**Probabilité** : Faible à modérée — 3-16 % des investigations dépassent le seuil de chunking (30 000−47 000 chars). Le document déclencheur de cet EPIC (32K chars) tient dans un seul embedding.
**Impact** : Modéré sur les 3 % de documents >50K chars — la recherche les retrouve mais avec un score plus faible (dilution proportionnelle au nombre de chunks).
**Mitigation** : Monitorer les scores de retrieval post-déploiement. EPIC V2 avec stockage multi-vecteur si la dilution est problématique.

### Risque 2 : Le tokenizer n'est pas accessible dans DualEmbeddingService

**Probabilité** : Faible — `SentenceTransformer` expose `.tokenizer` par défaut
**Contingence** : Charger `AutoTokenizer.from_pretrained("BAAI/bge-m3")` séparément (coût mémoire négligeable, le vocab est déjà en RAM)

### Risque 3 : Temps de chargement du modèle au cold start

**Probabilité** : Certain — le lazy-loading prend ~135s au premier appel
**Impact** : Acceptable — déjà géré par `run_in_executor`, l'event loop reste libre. Le MCP répond aux autres requêtes pendant le chargement.

### Risque 4 : Batch encoding sur chunks très nombreux

**Probabilité** : Très faible — nécessite un document de >100K chars
**Impact** : Mineur — le batch encoding de SentenceTransformer est optimisé

### Risque 5 : Concurrence — appels simultanés à `write_memory`

**Probabilité** : Modérée — usage normal (1-5 appels simultanés), usage batch (10+)
**Impact** : Faible — `SentenceTransformer.encode()` est thread-safe et sérialise les appels en interne. Latence additive mais pas de corruption.
**Mitigation** : Aucune nécessaire pour le V1. Si le débit devient un problème, implémenter un worker queue dédié.

### Risque 6 : Tokenizer non accessible

**Probabilité** : Faible — `SentenceTransformer` expose `.tokenizer` par défaut
**Contingence** : Fallback `AutoTokenizer.from_pretrained()` déjà prévu dans T2. Coût mémoire négligeable.

---

## §5 IMPACT PROJET

### Fichiers modifiés

| Fichier | Modification | Complexité |
|---------|-------------|:----------:|
| `api/mnemo_mcp/tools/memory_tools.py` | Supprimer troncation + déplacer préfixe (~5 lignes) | Triviale |
| `scripts/reindex_bge_m3.py` | Modifier 1 constante | Triviale |
| `api/mnemo_mcp/server.py` (`LazyEmbeddingService`) | Ajouter chunking + mean pooling (~30 lignes) | Moyenne |

### Fichiers non modifiés

- `search_memory` — inchangé (1 vecteur par mémoire, schéma identique)
- Schéma DB — inchangé (colonnes `embedding`, `embedding_half`, `embedding_model`)
- `write_memory` — inchangé (seul le contenu de la tâche async change)

### Régression impossible

- Les embeddings sont regénérés (pas de compatibilité à maintenir avec les anciens vecteurs tronqués)
- Le format de stockage est identique (vecteur 1024d, halfvec)
- La recherche fonctionne à l'identique (KNN pgvector sur 1 vecteur)

---

## §6 GLOSSAIRE

| Terme | Définition |
|-------|------------|
| **BGE-M3** | Modèle d'embedding de BAAI : multilingue, 1024 dimensions, 8192 tokens max |
| **Mean pooling** | Moyenne arithmétique de N vecteurs → 1 vecteur de même dimension |
| **Chunking** | Découpage d'un texte long en segments de taille ≤ limite du modèle |
| **L2 normalization** | Normalisation d'un vecteur à une norme euclidienne de 1 |
| **Halfvec** | Vecteur en précision float16 (2 octets/dimension) — utilisé pour l'index pgvector |
| **run_in_executor** | Exécution d'une fonction synchrone dans un thread séparé sans bloquer l'event loop asyncio |
| **Tokenizer** | Composant BGE-M3 qui convertit le texte en tokens. Accessible via `model.tokenizer` ou `AutoTokenizer.from_pretrained()` |
| **LazyEmbeddingService** | Wrapper qui charge BGE-M3 à la demande (lazy) et expose `generate_embedding()`. Utilise `run_in_executor` pour ne pas bloquer l'event loop |
