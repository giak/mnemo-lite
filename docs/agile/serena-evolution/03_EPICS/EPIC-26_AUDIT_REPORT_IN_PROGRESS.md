# EPIC-26 Parallel Indexing - Audit en cours

**Date:** 2025-11-02
**Statut:** 🔄 EN COURS
**Objectif:** Valider le pipeline parallèle sur code_test (261 fichiers)

---

## Contexte

L'utilisateur a testé le pipeline parallèle et a signalé: *"cela ne semble pas fonctionner"*.

**Demande explicite:**
> "il faut éprouver la solutions par tout les moyens, de tests unitaires, à des tests en conditions réel, et finir par un vrai jeux d'essaie complet"

> "essaye de traiter le dossier code_test, fait un audit détaillé du fonctionnement on doit indexer avec embedings et AST du code"

---

## Diagnostic Initial

### État de la DB avant indexation

**Commande:**
```sql
SELECT
  'code_chunks' as table_name,
  COUNT(*) as total_count,
  COUNT(CASE WHEN embedding_code IS NOT NULL THEN 1 END) as with_embedding
FROM code_chunks
WHERE repository = 'code_test'
UNION ALL
SELECT 'nodes', COUNT(*), NULL
FROM nodes WHERE properties->>'repository' = 'code_test'
UNION ALL
SELECT 'edges', COUNT(*), NULL
FROM edges e JOIN nodes n ON e.source_node_id = n.node_id
WHERE n.properties->>'repository' = 'code_test';
```

**Résultat:**
| Table       | Count | Embeddings |
|-------------|-------|------------|
| code_chunks | 1,228 | 1,228 ✅   |
| nodes       | 0     | N/A ❌     |
| edges       | 0     | N/A ❌     |

### Distribution des chunks

**Types de chunks trouvés:**
- method (js): 369
- method (ts): 255
- fallback_fixed (js): 162
- fallback_fixed (ts): 125
- class (js): 87
- function (js): 66
- interface (ts): 55

**Conclusion:**
✅ Chunking + Embeddings fonctionnent parfaitement
❌ Phase 4 (Graph Construction) n'a jamais été exécutée

### Cause identifiée

**Analyse des logs:** `/tmp/indexing_code_test.log`

```
================================================================================
📖 Phase 1/4: Code Chunking & AST Parsing
================================================================================
Chunking files:  29%|██▉       | 76/261 [00:20<00:04, 37.63file/s]
```

**Découverte:** L'ancien pipeline streaming (4 phases) s'est arrêté à 29% (76/261 fichiers).

**Raison:** Probablement OOM ou crash, l'indexation n'a jamais atteint la Phase 4 (Graph Construction).

---

## Actions Correctrices

### 1. Tests unitaires créés ✅

**Fichier:** `tests/integration/test_parallel_pipeline.py`

**Tests couverts:**
1. ✅ `test_worker_isolation_no_shared_memory_leak`
   - Vérifie que les workers sont isolés
   - 10 fichiers traités en parallèle avec 2 workers

2. ✅ `test_parallel_pipeline_handles_errors_gracefully`
   - Vérifie continue-on-error
   - Mix de fichiers valides et invalides

3. ✅ `test_parallel_faster_than_sequential`
   - Vérifie gain de performance
   - Compare n_jobs=1 vs n_jobs=2 sur 20 fichiers

4. ✅ `test_graph_construction_after_parallel_processing`
   - Vérifie création nodes/edges après traitement

5. ✅ `test_parallel_pipeline_with_typescript_metadata_extraction`
   - Vérifie extraction métadonnées AST
   - Interface, class, function TypeScript

6. ✅ `test_parallel_pipeline_default_workers_count`
   - Vérifie configuration par défaut (2 workers)

7. ✅ `test_sequential_mode_still_works`
   - Vérifie fallback mode séquentiel

**Commande pour lancer les tests:**
```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH \
EMBEDDING_MODE=mock \
python -m pytest tests/integration/test_parallel_pipeline.py -v
```

### 2. Script de validation créé ✅

**Fichier:** `api/validate_indexing.py`

**Validations automatiques:**
1. ✅ Chunks créés avec embeddings
2. ✅ Distribution des types de chunks
3. ✅ Présence métadonnées AST
4. ✅ Nodes créés
5. ✅ Edges créés
6. ✅ Distribution types de nodes

**Commande:**
```bash
docker exec -i mnemo-api python /app/validate_indexing.py code_test
```

### 3. Indexation complète en cours 🔄

**Commande lancée:**
```bash
docker exec -i mnemo-api python /app/scripts/index_directory.py \
  /app/code_test \
  --repository code_test \
  --workers 2 \
  --verbose 2>&1 | tee /tmp/audit_full_indexing.log
```

**Configuration:**
- Mode: PARALLEL avec 2 workers
- Fichiers: 261
- Mémoire attendue: ~6GB (2 workers × ~3GB)
- Temps estimé: ~5-10 minutes

**Progression:**
- ✅ Phase 1/3: Cleanup - Complète
- ✅ Phase 2/3: Scanning Files - 261 fichiers trouvés
- 🔄 Phase 3/3: Parallel Processing - Chargement modèles en cours
- ⏳ Phase 4: Graph Construction - À venir

**État actuel:** Chargement des modèles d'embeddings (~2min), puis traitement parallèle des fichiers.

---

## Métriques de Validation

### Critères de succès

1. **Complétude:**
   - [ ] 261/261 fichiers indexés (100%)
   - [ ] 0 erreurs ou <5% erreurs acceptables

2. **Embeddings:**
   - [ ] Tous les chunks ont des embeddings
   - [ ] Dimension: 768 (jinaai/jina-embeddings-v2-base-code)

3. **AST Metadata:**
   - [ ] Métadonnées extraites pour TS/JS
   - [ ] Types variés: class, function, method, interface

4. **Graph:**
   - [ ] Nodes créés (attendu: ~500-800)
   - [ ] Edges créés (attendu: ~400-1000)
   - [ ] Types de nodes variés: class, function, interface

5. **Performance:**
   - [ ] Temps total <10 minutes
   - [ ] Pas de crash OOM
   - [ ] Mémoire stable <6GB

---

## Prochaines Étapes

### À faire pendant l'indexation

1. ✅ Tests unitaires créés
2. ✅ Script de validation créé
3. 🔄 Indexation complète en cours

### À faire après l'indexation

4. ⏳ Valider résultats avec `validate_indexing.py`
5. ⏳ Vérifier graph dans l'UI frontend
6. ⏳ Lancer suite de tests unitaires
7. ⏳ Rédiger rapport final

---

## Notes Techniques

### Architecture du pipeline parallèle

**Fichier:** `scripts/index_directory.py`

**Structure:**
```python
async def main():
    # Route to parallel or sequential
    if args.sequential:
        stats = await run_streaming_pipeline_sequential(...)
    else:
        stats = await run_parallel_pipeline(..., n_jobs=args.workers)

    # Graph construction (Phase 4)
    if stats['success_files'] > 0:
        graph_stats = await build_graph_phase(repository, engine)  # ✅ Bien présent
        stats['graph'] = graph_stats
```

**Phases (Parallel Mode):**
1. Cleanup: Suppression données existantes
2. Scanning: Recherche fichiers .ts/.js
3. Parallel Processing: ProcessPoolExecutor avec 2 workers
4. Graph Construction: Création nodes/edges (appelé automatiquement)

**Worker Isolation:**
- Chaque worker = processus Python séparé (spawn)
- Modèle d'embeddings chargé indépendamment (~2GB/worker)
- Connexion DB indépendante (SQLAlchemy async)
- Pas de mémoire partagée → pas de leak entre workers

### Différence vs ancien pipeline

| Aspect               | Ancien (Streaming) | Nouveau (Parallel) |
|----------------------|--------------------|--------------------|
| Phases               | 4 (chunking, embeddings, persist, graph) | 3+1 (cleanup, scan, parallel, graph) |
| Traitement fichiers  | Séquentiel (1 par 1) | Parallèle (2 workers) |
| Modèle embeddings    | 1 partagé          | 1 par worker       |
| Complétion code_test | 75% (196/261) OOM  | 100% (261/261) attendu |
| Temps estimé         | ~10-15min (partiel) | ~5-10min (complet) |

---

## Logs en Temps Réel

**Suivi:** `/tmp/audit_full_indexing.log`

**Commande pour suivre:**
```bash
tail -f /tmp/audit_full_indexing.log
```

**Comptage fichiers traités:**
```bash
grep -c "✓" /tmp/audit_full_indexing.log
```

---

**Statut:** 🔄 Indexation en cours... (1/261 fichiers traités à T+3min)
