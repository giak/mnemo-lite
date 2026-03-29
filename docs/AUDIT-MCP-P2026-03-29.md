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

## Phase 2 — Fixes Élevés (P1, ~2h)

### P1-1 : `search_memory` hard-fail si embedding down
```
Fichier: tools/memory_tools.py:679
Actuel: raise RuntimeError("Embedding service not available")
Fix:    Fallback vers tag-only search (pas d'embedding, juste filtres tags)
```

### P1-2 : `datetime.utcnow()` déprécié (11 occurrences)
```
Fichiers: test_tool.py, health_resource.py, analytics_resources.py, indexing_tools.py
Fix:      datetime.now(timezone.utc)
```

### P1-3 : database_url.split("@") crash
```
Fichier: server.py:88
Erreur: IndexError si pas de @ dans l'URL
Fix:    host = config.database_url.split("@")[-1] if "@" in config.database_url else config.database_url
```

### P1-4 : Singleton `system_snapshot_tool` dupliqué
```
Fichier: tools/memory_tools.py:1244 + 1323
Fix:    Retirer la première déclaration (ligne 1244)
```

---

## Phase 3 — Performance (P2, ~3h)

### P2-1 : Cache `HybridCodeSearchService` instance
```
Fichier: tools/search_tool.py:203
Actuel: hybrid_service = HybridCodeSearchService(engine=engine) # à chaque appel
Fix:    Initialiser dans lifespan, injecter via DI
```

### P2-2 : Parallel queries sur même connexion
```
Fichier: tools/memory_tools.py:1178-1190 (SystemSnapshot)
Actuel: 7 tasks sur même conn (serialisé)
Fix:    Créer conn séparée par task (engine.connect() dans chaque coroutine)
```

### P2-3 : Retirer pool asyncpg mort
```
Fichier: server.py:90-106
Actuel: asyncpg pool créé mais jamais utilisé
Fix:    Supprimer — simplifie startup, réduit connexions
```

### P2-4 : Unifier caching (2 systèmes indépendants)
```
Fichier: tools/search_tool.py + caches/cascade_cache.py
Actuel: Cache manuel Redis (5min) + cascade cache L1/L2 (30s) = pas coordonnés
Fix:    Invalider le cache recherche après reindex
```

### P2-5 : `search_memory` graceful degradation
```
Fichier: tools/memory_tools.py:679
Actuel: raise RuntimeError si embedding down
Fix:    Fallback tag-only: search avec filtres tags, pas d'embedding
```

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
| P0 (6+1 bugs) | 1h | **Crashs runtime** | 🔴 Immédiat | ✅ FAIT (11/11 tests) |
| P1 (4 fixes) | 2h | **Broken features** | 🟡 Cette semaine | ⬜ |
| P2 (5 perf) | 3h | Performance | 🟢 Ce mois | ⬜ |
| P3 (4 dette) | 1j | Maintenance | 🔵 Quand possible | ⬜ |

---

*Audit MCP Mnemolite — 2026-03-29*
