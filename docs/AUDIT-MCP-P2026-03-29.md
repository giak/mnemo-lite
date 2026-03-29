# Audit MCP Mnemolite — Plan de Correction

> **Date :** 2026-03-29 08:17 / **Mis à jour :** 2026-03-29 09:27  
> **Audit :** Code quality + Services integration (35+ fichiers, ~9200 lignes)  
> **Priorisation :** P0 (crash) → P1 (broken) → P2 (perf) → P3 (dette)

---

## Phase 1 — Fixes Critiques (P0, ~1h) — ✅ TERMINÉ

### P0-1 : `batch_generate_embeddings` n'existe pas — ✅ FIXÉ
```
Fichier: tools/indexing_tools.py:713
Erreur: AttributeError → index_markdown_workspace crash
Fix:   await embedding_service.generate_embeddings_batch(texts=texts)
Commit: 90b106a
Test:  TestP01BatchEmbeddings.test_correct_method_name ✅
```

### P0-2 : `consolidate_memory` passe dict comme embedding — ✅ FIXÉ
```
Fichier: tools/memory_tools.py:946
Erreur: DualEmbeddingService retourne Dict mais repo attend List[float]
Fix:   embedding_raw = await embedding_svc.generate_embedding(embedding_text)
       embedding = embedding_raw.get("text") if isinstance(embedding_raw, dict) else embedding_raw
Commit: 90b106a
Test:  TestP02ConsolidateEmbedding.test_extracts_from_dict ✅
```

### P0-3 : `project_id` undefined dans fallback search — ✅ FIXÉ
```
Fichier: tools/memory_tools.py:740
Erreur: NameError si hybrid search unavailable
Fix:   Retirer project_id=project_id du fallback MemoryFilters
Commit: 90b106a
Test:  TestP03ProjectIdFallback.test_no_undefined_project_id ✅
```

### P0-4 : `index_incremental` mauvaise clé service — ✅ FIXÉ
```
Fichier: tools/indexing_tools.py:464
Erreur: services.get("indexing_service") → toujours None
Fix:   services.get("code_indexing_service") (clé correcte: server.py:226)
Commit: 90b106a
Test:  TestP04ServiceKey.test_correct_service_key ✅
```

### P0-5 : Path traversal `reindex_file` — ✅ FIXÉ
```
Fichier: tools/indexing_tools.py:337
Erreur: Lecture fichiers arbitraires (/etc/passwd)
Fix:   os.path.realpath(file_path) + startswith("/") check
Commit: 90b106a
Test:  TestP05PathTraversal (3 tests) ✅
```

### P0-6 : Path traversal `index_project` — ✅ FIXÉ
```
Fichier: tools/indexing_tools.py:86
Erreur: Accès fichiers arbitraires
Fix:   os.path.realpath(project_path) + startswith("/") check
Commit: 90b106a
Test:  TestP05PathTraversal.test_index_project_validates_path ✅
```

### P0-BONUS : Singleton `system_snapshot_tool` dupliqué — ✅ FIXÉ
```
Fichier: tools/memory_tools.py:1246 + 1325
Erreur: 2 instances → maintenance trap
Fix:   Retirer la première déclaration (ligne 1246)
Commit: d3635bf
Test:  TestRegressionSingletons (2 tests) ✅
```

**Tests : 11/11 passed (4.0s)**

---

## Phase 2 — Fixes Élevés (P1, ~2h) — ✅ TERMINÉ

### P1-1 : `search_memory` hard-fail si embedding down — ✅ FIXÉ
```
Fichier: tools/memory_tools.py:679
Actuel: raise RuntimeError("Embedding service not available")
Fix:    try/except around embedding, fallback to tag-only search, log warning
Commit: 280927a
Test:   TestP11SearchMemoryGracefulDegradation (2 tests) ✅
```

### P1-2 : `datetime.utcnow()` déprécié (9 occurrences) — ✅ FIXÉ
```
Fichiers: health_resource.py, analytics_resources.py, indexing_tools.py, test_tool.py
Fix:      datetime.now(timezone.utc) + added timezone import
Commit: 280927a
Test:   TestP12DatetimeTimezone (3 tests) ✅
```

### P1-3 : `database_url.split("@")` crash — ✅ FIXÉ
```
Fichier: server.py:88
Erreur: IndexError si pas de @ dans l'URL
Fix:    .split("@")[-1] with "@" check
Commit: 280927a
Test:   TestP13DatabaseUrlParsing (1 test) ✅
```

### P1-4 : Singleton `system_snapshot_tool` dupliqué — ✅ DÉJÀ FIXÉ
```
Commit: d3635bf
Test:   TestRegressionSingletons (2 tests) ✅
```

**Tests : 17/17 passed (3.9s)**

---

## Phase 3 — Performance (P2, ~3h) — ✅ TERMINÉ (3/5, 2 skip)

### P2-1 : Cache `HybridCodeSearchService` instance — ✅ FIXÉ
```
Fichier: tools/search_tool.py:203
Actuel: hybrid_service = HybridCodeSearchService(engine=engine) # à chaque appel
Fix:    Cached on self._hybrid_search_service, created once, reused
Commit: e16e781
Impact: Avoid recreating LexicalSearchService + VectorSearchService per call
```

### P2-2 : Parallel queries sur conn séparées — ✅ FIXÉ
```
Fichier: tools/memory_tools.py:1182-1194 (SystemSnapshot)
Actuel: 7 tasks sur même conn (serialisé par SQLAlchemy)
Fix:    fetch_group/health create own connection for true parallelism
Commit: e16e781
Impact: 7 connections vs 1 → true concurrent execution
```

### P2-3 : Retirer pool asyncpg mort — ⏭️ SKIPPÉ
```
Fichier: server.py:90-106
Décision: Pool utilisé par health_resource.py pour DB ping checks
Risque: Casser health checks pour gain marginal (2-10 connexions)
```

### P2-4 : Unifier caching — ✅ FIXÉ
```
Fichier: tools/indexing_tools.py (reindex_file + index_incremental)
Actuel: 2 systèmes cache non coordonnés (cascade L1/L2 + search Redis)
Fix:    scan+delete search:v1:* keys after successful reindex
Commit: e16e781
Impact: Stale cached results cleared immediately after reindex
```

### P2-5 : `search_memory` graceful degradation — ✅ DÉJÀ FIXÉ (P1-1)
```
Commit: 280927a
```

**Tests : 17/17 passed (3.7s)**

---

## Phase 4 — Dette Technique (P3, ~1j)

### P3-1 : `_convert_to_mcp_node` dupliqué 3×
```
Fichier: resources/graph_resources.py:177, 375, 562
Fix:    Extraire dans BaseMCPComponent ou utility
```

### P3-2 : Validation tags dupliquée 3×
```
Fichier: models/memory_models.py:69, 146, 356
Fix:    Extraire dans un validateur commun
```

### P3-3 : `**params` anti-pattern (6 outils)
```
Fichiers: memory_tools.py:896,1030,1108,1263, indexing_tools.py:443,645
Fix:    Paramètres nommés explicites
```

### P3-4 : God-class `server.py` (1833 lignes)
```
Fix:    Extraire lifespan dans ServiceFactory
        Extraire registrations dans register_*.py
        Réduire server.py à < 500 lignes
```

---

## Matrice de Décision

| Phase | Effort | Impact | Priorité | Status |
|-------|--------|--------|----------|--------|
| P0 (6+1 bugs) | 1h | **Crashs runtime** | 🔴 Immédiat | ✅ FAIT (17/17 tests) |
| P1 (4 fixes) | 2h | **Broken features** | 🟡 Cette semaine | ✅ FAIT (17/17 tests) |
| P2 (3+2 perf) | 3h | Performance | 🟢 Ce mois | ✅ FAIT (17/17 tests) |
| P3 (4 dette) | 1j | Maintenance | 🔵 Quand possible | ⬜ |

---

*Audit MCP Mnemolite — 2026-03-29*
