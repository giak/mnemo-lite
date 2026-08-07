# Spec : Brainstorm, corrections MnemoLite issues de l'usage Truth Engine

**Date** : 2026-08-07
**Contexte** : Utilisation réelle de Mnemolite depuis le projet truth-engine (investigations KERNEL, articles, vérifications forensiques). Constats de terrain + lecture du code serveur.
**Statut** : re-audit KISS/YAGNI + double-vérification du code effectués le 2026-08-07 (corrections de diagnostic intégrées ci-dessous), aucune modification de code effectuée.

---

## 0. Résumé des problèmes constatés (par gravité)

| # | Problème | Gravité | Cause racine (vérifiée dans le code) |
|---|----------|---------|--------------------------------------|
| P1 | **Worker en crash-loop** (auto-save conversations coupé) | 🔴 Critique | `docker/Dockerfile.worker` ne copie pas `api/` ; et `COPY api/` seul est insuffisant : `pydantic-settings` manque aussi dans les requirements worker |
| P2 | **Query libre sans `search_mode` → 0 résultat** | 🟠 Élevé | Défaut `tag` **volontaire** (anti cold-start, commentaire CRITICAL FIX) mais **aucune recherche textuelle n'existe** : le fallback cherche un tag égal à la requête entière (`effective_tags = [query]`) |
| P3 | **Contenus longs introuvables par chaîne exacte** | 🟠 Élevé | **Aucune recherche textuelle** dans le repo (pg_trgm seulement sur le titre, pour la dédup lignes 861-899) ; le vectoriel n'est alimenté que par `embedding_source` (P4) → les faits présents seulement dans le contenu sont invisibles |
| P4 | **Embedding calculé sur `embedding_source` uniquement** si fourni | 🟠 Élevé | `memory_tools.py` `_trigger_async_embedding` : `text = embedding_source or content` → les chaînes présentes seulement dans le contenu sont invisibles du vectoriel |
| P5 | **84,8 % du corpus sans verdict** (33 629 conversations / 39 634) | 🟠 Élevé | `conversations_routes.py:508` pose `memory_type="conversation"` sans tags `project:*`/`status:*` ; corpus figé car le worker est down (P1) ; polluent les résultats hybrides |
| P6 | **Endpoints REST morts ou trompeurs** | 🟡 Moyen | `POST /v1/search/` → "Search failed" ; `POST /v1/search/content`, `similarity` → vide ; seule `GET /api/v1/memories/search` fiable |
| P7 | **861 mémoires sans embedding** (alerte serveur) | 🟡 Moyen | Échec embedding async non retenté (pas de backfill) |
| P8 | **Cache L2 froid** (0 hit / 0 miss) | 🟢 Faible | TTL courts (60 s/300 s), peu de réutilisation inter-sessions |
| P9 | **Divergence de conventions de tags** (`kernel`, `status:CONFIRME` vs `fact:verifie` vs `status:confirme`) | 🟢 Faible | Skill global vs KERNEL vs usage réel divergent |

---

## 1. P1 : Worker en crash-loop, `ModuleNotFoundError: No module named 'api'`

### 1.1 Constat (vérifié en direct)
- `docker ps` : `mnemo-worker Restarting (1)`, **1 506 redémarrages**, ExitCode=1.
- Logs : `conversation_worker.py:13 from api.core.settings import get_settings` → `ModuleNotFoundError`.
- **Cause racine** : `docker/Dockerfile.worker` :
  ```dockerfile
  COPY workers/requirements.txt .
  RUN pip install ...
  COPY workers/ ./workers/
  CMD ["python", "-m", "workers.conversation_worker"]
  ```
  Il ne copie **jamais** `api/`. Or `conversation_worker.py` importe `api.core.settings` (ligne 13) et plus loin des modules du worker seulement. Le conteneur tourne avec `WORKDIR /app` et `/app/api` n'existe pas.
- Conséquence : **l'auto-save des conversations (Redis Streams `conversations:autosave`) est à terre** depuis la dernière reconstruction de l'image. Les 33 629 conversations existantes datent d'avant la panne.

### 1.2 Options de correction
- **Option A (minimale, vérifiée)** : dans `docker/Dockerfile.worker`, ajouter `COPY api/ ./api/` avant le CMD **et** ajouter `pydantic-settings` à `workers/requirements.txt`. Vérifié : `settings.py` importe `pydantic_settings` (absent des requirements worker, qui n'ont que `pydantic`) ; `conversation_worker.py` n'importe **aucun** `workers.utils` (donc pas besoin d'asyncpg/numpy/sentence-transformers) ; `api/__init__.py` fait 27 octets (léger).
- **Option B** : extraire `get_settings()` dans un module partagé. Sur-ingénierie pour un fix d'urgence ; à reconsidérer si d'autres workers doivent utiliser `utils.embeddings`/`utils.db` (deps lourdes absentes des requirements worker).
- **Option C** : monorepo `app/`. Non prioritaire (YAGNI).

**Recommandation** : Option A uniquement (2 lignes, débloque l'auto-save). Ne rien faire d'autre.

### 1.3 Vérification du fix
```bash
docker compose build worker && docker compose up -d worker
docker ps  # mnemo-worker Up (healthy)
docker logs mnemo-worker --tail 20  # plus de ModuleNotFoundError
curl -s http://localhost:8001/v1/conversations/metrics  # compteur qui remonte
```

---

## 2. P2 : query libre sans `search_mode` → 0 résultat (pas de recherche textuelle dans le fallback)

### 2.1 Constat
- `memory_tools.py` `SearchMemoryTool.execute` : `search_mode: str = "tag"`.
- Sans `search_mode="hybrid"`, le code fait :
  ```python
  effective_tags = tags if tags else ([query_stripped] if is_tag_only else [])
  ```
  → il cherche une mémoire dont le **tag est littéralement égal à la requête entière** (« combien de parrainages Asselineau 2022 ? »). Résultat : 0.
- Le skill `mnemolite-mem-first` et le KERNEL ont dû imposer la règle « hybrid obligatoire » comme garde-fou procédural. C'est un symptôme : le fallback par défaut ne fait **aucune recherche textuelle** (voir 2.2).

### 2.2 Constat complémentaire (vérifié dans le code)
- Le défaut `tag` est **délibéré** : commentaire `memory_tools.py` (~ligne 818) : « CRITICAL FIX: Skip embedding generation in search_memory to avoid 10s+ cold start... Use lexical-only search instead ». Changer le défaut en `hybrid` entrerait en conflit avec ce compromis (cold start 10-50 s, timeout client MCP 30 s).
- **Le vrai défaut** : aucune recherche textuelle dans le fallback. `search_by_tags` ne fait que du matching de tags exacts (`:tag = ANY(tags)`) ; le repo n'a pas de méthode ILIKE/full-text sur title+content.

### 2.3 Correction (KISS)
- **Ajouter une méthode `search_by_text(query, filters, limit, offset)`** dans `memory_repository` : `WHERE (title ILIKE :q OR content ILIKE :q)`, paramétrée, mots entiers, ordonnée par pertinence.
- **Fallback modifié** dans `memory_tools.py` : query fournie sans tags → `search_by_text` ; tags seuls → `search_by_tags` (comportement actuel inchangé).
- Résultat : une query libre donne des résultats utiles **sans cold start ni timeout**. Le mode `hybrid`/`semantic` reste disponible explicitement pour la qualité vectorielle.
- Le skill `mnemolite-mem-first` peut ensuite retirer la règle « hybrid obligatoire ».

---

## 3. P3 : Contenus longs introuvables par chaîne exacte

### 3.1 Constat (cas réel truth-engine)
- Mémoire consolidée `58cc0e69` (parrainages 293/49/36, contenu long ~2 000 caractères) :
  - retrouvée par `search_memory` hybride sémantique (« temps de parole ARCOM » → position 1),
  - **pas retrouvée** par `GET /api/v1/memories/search?query=parrainages&limit=3` (REST) ni par requêtes à chaîne exacte, alors qu'elle contient le mot « parrainages ».
- Mémoire courte `6fe3dc7c` (même sujet) : **pas non plus** retrouvée par l'API pour « Asselineau 293 » (POST `/api/v1/memories/search` → 0 résultat), ce qui confirme l'absence de recherche textuelle, pas une dilution.
- **Mécanisme réel (après double-vérification)** : pas de recherche textuelle dans le chemin par défaut (P2), donc 0 résultat quoi qu'il arrive ; et le vectoriel n'est alimenté que par `embedding_source` (P4). Le scénario « pg_trgm dilué » ne se produit pas en pratique : `pg_trgm` n'est utilisé que sur le titre, dans la dédup (lignes 861-899).

### 3.2 Correction (fusionnée avec P2)
- **Le fix P2.3 (`search_by_text`) EST le fix P3** : ILIKE sur titre+contenu matche les mots entiers, indépendamment de la longueur du contenu. Rien d'autre à faire.
- **P3-a (optionnel, à mesurer)** : si le ILIKE brut ramène trop de bruit, pondérer le titre dans le classement. À mesurer après P2.3, pas avant (YAGNI).
- **P3-c (reporté)** : chunking des contenus longs à l'indexation. Sur-ingénierie tant que `search_by_text` n'existe pas.
- **P3-d (reporté)** : exposer `lexical_weight`/`vector_weight` dans `search_memory`. Sans intérêt tant que le composant lexical est trivial (voir P2.3).

---

## 4. P4 : Embedding sur `embedding_source` seulement, invisibilité vectorielle du contenu

### 4.1 Constat
- `_trigger_async_embedding(memory, content, embedding_source)` : `text = embedding_source or content`.
- Si l'appelant fournit `embedding_source` (cas du skill KERNEL : write-back d'investigation complète avec résumé), **le contenu complet n'est jamais vectorisé**.
- Conséquence : une requête sémantique qui ne touche pas le résumé ne trouve pas la mémoire, même si le contenu porte le fait (cas P3 observé : « parrainages » absent du résumé court, présent dans le contenu).

### 4.2 Pistes
- **P4-a** : générer **deux embeddings** (contenu + embedding_source) et les concaténer ou stocker en deux colonnes, avec recherche sur les deux.
- **P4-b** : si `embedding_source` absent, **générer automatiquement un résumé** (LLM local bge-m3 ne fait pas de résumé ; utiliser un petit modèle ou une extraction de phrases-clés, ou simplement title+premier N caractères).
- **P4-c** : au minimum, **toujours inclure le titre dans le texte vectorisé** : `text = f"{title}. {embedding_source or content}"`.

**Recommandation** : P4-c immédiat (1 ligne) + P4-a en design (double embedding), cohérent avec P3-c (chunks).

---

## 5. P5 : 84,8 % du corpus sans verdict, les conversations autosauvées

### 5.1 Constat (vérifié en base le 2026-08-07)
- Requête directe : **39 634 mémoires**, dont **33 629 `conversation` (84,8 %)** ; 4 830 investigation, 881 note, 99 reference, 94 quintessence, 52 article, 47 decision, 2 task.
- Mécanique exacte : le worker délègue à `POST /v1/conversations/save` ; `conversations_routes.py:508` pose `memory_type="conversation"`, **sans tags `project:*` ni `status:*`**.
- **Corpus figé** : le worker étant down (P1), plus aucune conversation n'est écrite depuis la panne.
- Impact : la recherche hybride globale remonte ces conversations à score faible (bruit) ; aucun verdict forensique n'y est attaché.

### 5.2 Pistes
- **P5-a** : **exclure `memory_type=conversation` du RRF par défaut** (sauf si demandé explicitement via filtre). Le serveur ne devrait pas noyer la recherche forensique avec les transcriptions.
- **P5-b** : tagger rétroactivement les conversations par projet (heuristique : chemin du repo, nom de session) en un job one-shot.
- **P5-c** : ne pas écrire les conversations comme `memory_type=conversation` mais les stocker dans une table dédiée (ou avec tag `kind:transcript`), hors du corpus de faits.

**Recommandation** : P5-a (filtre par défaut) + P5-b (campagne de taggage).

---

## 6. P6 : Endpoints REST, fiabiliser la voie sans MCP

### 6.1 Constat
- `POST /v1/search/` → `{"detail": "Search failed"}` (levé dans `server.py`).
- `POST /v1/search/content`, `POST /v1/search/similarity` → `{"data": []}` même sur requête existante.
- `POST /api/v1/memories/search` (body JSON) → vide/erreur dans certains cas.
- **Seule voie fiable** : `GET /api/v1/memories/search?query=...` (utilise `_search_memories`, la même logique que le MCP).

### 6.2 Piste
- **Unifier** : `POST /v1/search/` et `POST /api/v1/memories/search` doivent déléguer à la même fonction hybride que `GET /api/v1/memories/search` et que `search_memory` MCP. Le skill documente déjà « ne pas utiliser POST /v1/search/ », c'est un contournement, pas une solution.

---

## 7. P7 : Backfill des 861 mémoires sans embedding

### 7.1 Constat (vérifié en base le 2026-08-07)
- Requête directe : **861 mémoires sur 39 634 sans `embedding_half` (2,2 %)**.
- Aucun script de backfill d'embeddings n'existe (`scripts/` ne contient que `backfill_memory_relationships.py` et `migrate_v2_to_v3.py`). L'embedding async échoue (timeout, service down au moment du write) et **n'est jamais retenté**.

### 7.2 Piste
- Job de **backfill** : requête SQL `SELECT id, title, content, embedding_source FROM memories WHERE embedding_half IS NULL`, régénération avec retry/backoff, exposé via un outil MCP (`retry_indexing` existe pour le code, pas pour les mémoires) ou une route admin.

---

## 8. P8 : Cache L2 froid

### 8.1 Constat
- `/v1/cache/stats` : L1 0 entrée, L2 `connected=true` mais 0 hit / 0 miss, hit_rate 0 %.
- TTL : 300 s (tag-only) / 60 s (hybride) dans `memory_tools.py`.

### 8.2 Piste
- TTL plus long pour les recherches par tags stables (par ex. 15 min), invalidation à l'écriture (hook existant ?). Mesurer avant/après avec `/v1/cache/stats`.

---

## 9. P9 : Convention de tags, unifier le schéma forensique

### 9.1 Constat (usage réel truth-engine)
- Le skill global et le KERNEL imposent `status:CONFIRME` / `status:PLAUSIBLE`.
- Les mémoires récentes écrites en session (parrainages, ARCOM, loi 76-528) portent `fact:verifie`, `status:confirme` (minuscule), `status:CONFIRME` (majuscule) : **3 variantes coexistent déjà**.
- Le KERNEL ajoute le tag `kernel` non documenté dans le skill.

### 9.2 Piste
- **Registre central des tags** dans `MCP_SETUP.md` (ou `docs/ARCHITECTURE.md`) : casse canonique (`status:CONFIRME`), liste autorisée, validation douce au write (`warning` si tag inconnu). Un `status:` manquant sur une mémoire forensique = `warning` à l'écriture.

---

## 9bis. Tests unitaires : ce qu'il faut couvrir pour chaque fix

Convention existante : 176 fichiers de test, pytest async (pytest-asyncio), fixtures locales par fichier (`mock_ctx`, `mock_memory_repository`, `mock_redis`, `mock_embedding_service`), tests MCP dans `tests/mnemo_mcp/`, tests worker dans `tests/workers/`, tests services dans `tests/services/`. Le test worker actuel (`tests/workers/test_conversation_worker.py`) importe `from workers.conversation_worker import ...`, ce qui le rend **dépendant de la présence de `api/` sur le PYTHONPATH** (même fragilité que le conteneur).

### Tests requis par priorité (nom de fichier cible)

| Fix | Fichier de test | Tests à écrire |
|-----|-----------------|----------------|
| P1 worker | `tests/workers/test_conversation_worker.py` (étendre) | 1) `test_import_succeeds_when_api_present` : import du module passe quand `api` est disponible (simule le conteneur fixé, contrairement à l'état cassé) ; 2) `test_process_message_success` (existe) ; 3) `test_worker_survives_redis_restart` (redis mocké qui lève puis revient, retry tenacity) ; 4) test d'intégration : l'image worker se construit et démarre (`docker compose build worker`) |
| P2 fallback lexical | `tests/mnemo_mcp/test_memory_search_tool.py` + `tests/api/test_memory_repository_search.py` (nouveau) | 1) `test_query_without_search_mode_returns_text_matches` : `execute(query="Asselineau 293")` sans `search_mode` → résultats par `search_by_text`, jamais 0 ni `tag_only` ; 2) `test_tags_without_query_still_tag_only` : `execute(query=None, tags=[...])` → `search_by_tags` inchangé ; 3) `test_search_by_text_parameterized_ilike` : pas d'injection SQL, mots entiers ; 4) `test_search_by_text_orders_by_relevance` |
| P3 (fusionné dans P2) | `tests/mnemo_mcp/test_memory_search_tool.py` (étendre) | `test_long_content_exact_term_found` : contenu long contenant le terme exact → retrouvé par query libre via le fallback lexical |
| P4 titre dans embedding | `tests/mnemo_mcp/test_memory_tools.py` (étendre) | 1) `test_embedding_text_includes_title` : spy sur `generate_embedding`, vérifier que le texte passé commence par le titre ; 2) `test_embedding_uses_embedding_source_if_provided` (existe peut-être, EPIC-24) ; 3) `test_embedding_source_plus_title` : les deux combinés |
| P5 exclusion conversation | `tests/mnemo_mcp/test_memory_search_tool.py` (étendre) | 1) `test_hybrid_search_excludes_conversation_by_default` : des mémoires `conversation` présentes → absentes des résultats par défaut ; 2) `test_conversation_included_when_filtered` : `memory_type=conversation` → présentes ; 3) `test_conversation_filter_parameter` : nouveau paramètre exposé |
| P6 REST unifié | `tests/api/test_memories_routes.py` (étendre ou nouveau) | 1) `test_post_search_returns_same_as_get` : `POST /v1/search/` et `GET /api/v1/memories/search` → mêmes résultats (id et ordre) ; 2) `test_post_search_empty_body_422` ; 3) `test_post_memories_search_json_body` : le body JSON avec tags fonctionne |
| P7 backfill | `tests/mnemo_mcp/test_indexing_tools.py` ou `tests/api/test_memories_routes.py` | 1) `test_backfill_embeddings_missing_only` : seules les mémoires `embedding_half IS NULL` sont traitées ; 2) `test_backfill_retry_on_failure` : échec embedding → retry avec backoff, pas d'abandon ; 3) `test_backfill_idempotent` : relancer ne régénère pas les embeddings existants |
| P8 cache | `tests/mnemo_mcp/test_memory_search_tool.py` (étendre) | 1) `test_cache_ttl_longer_for_tag_search` : TTL attendu selon le mode ; 2) `test_cache_invalidated_on_write` (existant dans le plan de test 2026-06-13, à vérifier) ; 3) `test_cache_hit_returns_cached` (existe) |
| P9 tags | `tests/mnemo_mcp/test_memory_tools.py` (étendre) | 1) `test_write_warns_on_missing_status_tag` : write sans `status:*` → warning dans la réponse (pas bloquant) ; 2) `test_write_warns_on_unknown_tag` ; 3) `test_status_case_normalized` : `status:confirme` → normalisé en `status:CONFIRME` |

### Règle de validation

- Chaque fix P0-P1 doit arriver avec ses tests verts (`pytest tests/... -v --tb=short`) dans le même commit.
- Les tests du pipeline critique (write→search e2e, race async embedding, dedup) listés dans `plans/2026-06-13_mnemolite-mcp-test-protocol.md` doivent être relancés après chaque modification du moteur de recherche (régression).
- Le test worker doit passer **avec** `api/` présent (comme dans le conteneur fixé par l'Option A). La régression du Dockerfile (api oublié au COPY) doit être attrapée par le test d'intégration `docker compose build worker` en CI, pas par un test unitaire.

---

## 9ter. Re-audit KISS / DRY / YAGNI (2026-08-07, après double-vérification du code)

Verdict : **4 fixes apportent ~90 % du gain. Le reste est coupé ou reporté.**

### Conservé (à implémenter)
1. **P1 worker** : `COPY api/ ./api/` + `pydantic-settings` dans les requirements worker. Deux lignes. Chaîne d'import vérifiée légère (le worker n'utilise que `api.core.settings` ; `api/__init__.py` fait 27 octets).
2. **P2/P3 fallback lexical** : `search_by_text` (ILIKE paramétré titre+contenu) branchée dans le fallback. Le fix le plus rentable : élimine la classe d'erreur n°1 (query libre → 0) et règle le cas des contenus longs, sans cold start ni timeout.
3. **P4-c** : titre inclus dans le texte vectorisé (`text = f"{title}. {embedding_source or content}"`). Une ligne.
4. **P5-a** (décision produit à valider) : exclure `memory_type=conversation` de la recherche par défaut, sauf demande explicite.

### Coupé ou reporté (YAGNI)
- **P3-c chunking des contenus longs** : sur-ingénierie tant que `search_by_text` n'existe pas. Réévaluer après P2.3 + P4-c.
- **P4-a double embedding** : deux colonnes et deux recherches pour un gain marginal vs P4-c. Reporté.
- **P8 cache** : 0 hit, TTL courts assumés, personne ne s'en plaint. Mesurer avant d'optimiser.
- **P6 unification REST** : `GET` fonctionne ; corriger seulement le POST mort en déléguant à la même fonction (quelques lignes).
- **P9 registre des tags** : documentation d'abord (MCP_SETUP.md), validation douce ensuite. Pas de code avant usage.
- **P7 backfill** : 2,2 % du corpus. Endpoint admin simple, pas un worker dédié.

### DRY
- `COPY api/` réutilise la source unique des settings (pas de copie locale dans le worker).
- `search_by_text` s'appuie sur `search_by_tags` (mêmes filtres) : on n'ajoute qu'une clause de texte, pas un nouveau moteur.

---

## 10. Priorisation proposée

| Priorité | Action | Effort | Impact |
|----------|--------|--------|--------|
| P0 | Fix worker (Option A : `COPY api/` + `pydantic-settings`) | 15 min | Débloque l'auto-save conversations |
| P0 | Fallback lexical `search_by_text` (ILIKE titre+contenu) | 1 h | Élimine la classe d'erreur n°1 (query libre → 0) et règle P3 |
| P1 | Inclure le titre dans le texte vectorisé (P4-c) | 10 min | Améliore la retrouvabilité immédiatement |
| P1 | Exclure `memory_type=conversation` du RRF par défaut | 30 min | Nettoie la recherche |
| P1 | Backfill 861 embeddings | 1 h | Couverture 100 % |
| P1 | Unifier `POST /v1/search/` sur la même logique hybride | 1-2 h | Voie REST fiable sans MCP |
| P1 | Exclure `memory_type=conversation` par défaut (P5-a, décision produit) | 15 min | Nettoie la recherche |
| P1 | Backfill 861 embeddings (endpoint admin simple) | 1 h | Couverture 100 % (2,2 % du corpus) |
| P1 | Corriger `POST /v1/search/` (déléguer à la même fonction) | 30 min | Voie REST fiable |
| Reporté (YAGNI) | Pondération titre (P3-a), chunking (P3-c), double embedding (P4-a) | - | À mesurer après P2.3 + P4-c, pas avant |
| Reporté (YAGNI) | TTL cache (P8), registre des tags + validation (P9) | - | Documentation d'abord, mesurer ensuite |

---

## 10bis. État d'avancement (2026-08-07, après implémentation)

Fixes implémentés et validés :
1. **P1 worker** : `COPY api/` dans `docker/Dockerfile.worker` + `pydantic>=2.7.1` + `pydantic-settings>=2.5.2` dans `workers/requirements.txt`. Image reconstruite, conteneur `Up`, RestartCount 0 (contre 1 506), log `worker_started` sur `conversations:autosave`.
2. **P2/P3 fallback lexical** : `search_by_tags(query_text=...)` (ILIKE paramétré, un mot = une clause, title OU content, wildcards `%`/`_` échappés via `ESCAPE '\'`) + branche dans `SearchMemoryTool.execute` (query libre → mode `text` ; requête au pattern de tag `^[a-z][a-z0-9_-]*:[a-z0-9_.-]+$` → `tag_only`, comportement historique préservé ; le texte libre avec deux-points « loi 76-528 : parrainages » reste en `text`, correctif de revue). Validé sur données réelles : « parrainages » → 28 résultats, mémoire consolidée `58cc0e69` en position 1, 0 conversation ; « loi 76-528 : parrainages » → 1 ; « 100% parrainage » → 3 (littéral).
3. **P4-c** : titre inclus dans le texte vectorisé (`title + embedding_source or content`).
4. **P5-a** : `MemoryFilters.exclude_conversations` appliqué par défaut (memory_type non précisé) dans le fallback repo, les 4 sous-recherches du service hybride, le MCP et le REST.

Tests : 43 passés (dont 6 nouveaux : fallback text, tags-only inchangé, exclusion conversation ×2, titre dans l'embedding, texte avec deux-points), 2 échecs PRÉEXISTANTS (hard delete, élicitation mockée, confirmé par git stash sur le code d'origine).

Revue de code (code-reviewer-deepseek-flash) : 2 points bloquants identifiés et corrigés (heuristique `:` trop large → pattern de tag ; wildcards ILIKE non échappés → échappement). Points documentés non bloquants : portée de P4-c limitée aux futurs writes (l'existant nécessitera un backfill, reporté), duplication du bloc d'exclusion 6× (cohérent avec le pattern préexistant), classement created_at DESC (choix KISS documenté).

Incident infra : diagnostic révisé après investigation complète (2026-08-07).
- **Le « blocage » du lifespan n'était pas l'init OpenTelemetry** : c'était un démarrage lent (~13 min) dû au préchargement des modèles d'embedding au boot (`EMBEDDING_MODE=real` → téléchargement Hugging Face de bge-m3 torch + jina code, puis chargement CPU). L'api a fini par être healthy et fonctionnelle : `GET /api/v1/memories/search` répond 200 en ~5 s (cold start du modèle au premier appel).
- **Bug 1 (corrigé) : endpoints OTLP doublés** dans `docker-compose.yml`. `OTLP_ENDPOINT` contenait déjà `/api/default/v1/traces` alors que `configure_otel` ajoute `/v1/traces` (et le log processor `/logs/_json`) → 401/404 en continu sur traces, métriques et logs. Corrigé : les 3 services (api, worker, mcp) pointent vers la base `http://openobserve:5080/api/default`. Validé : credentials openobserve corrects (200 avec auth sur `_bulk` et `/logs/_json`), **0 erreur d'ingestion** sur mcp et api après recréation des conteneurs.
- **Bug 2 (préexistant, non corrigé) : le préchargement du modèle CODE échoue à chaque boot** : « CODE model dimension mismatch: expected 1024, got 768 » (jina-embeddings-v2-base-code / jina-bert-v2-qk-post-norm, version HF flottante). L'api continue en dev (service créé à la demande, embedding texte OK) ; les recherches de code seraient affectées. Correctifs possibles à valider : épingler la révision HF du modèle code, ou `USE_ONNX=true` (bge-m3 local monté, pas de téléchargement), ou lazy-loading au premier appel.

---

## 11. Livrables du brainstorm

1. Ce spec (référence du plan de correction).
2. Un ticket par priorité P0-P1 (corrections de code dans MnemoLite).
3. La mise à jour du skill `mnemolite-mem-first` (suppression de la règle « hybrid obligatoire » une fois P2 serveur fait ; ajout du tag `kernel` et des conventions unifiées).
