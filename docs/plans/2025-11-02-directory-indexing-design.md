# Design: Script d'Indexation de Répertoire

**Date**: 2025-11-02
**Context**: Permettre l'indexation complète d'une codebase TypeScript/JavaScript par répertoire

## Problème

Actuellement, MnemoLite n'a pas de moyen simple d'indexer un projet entier:
- L'API `/v1/code/index` requiert des fichiers individuels
- Pas de CLI pour scanner un dossier
- `code_test` (259 fichiers TS) n'est pas indexé
- Graph UI est vide car aucun repository "code_test"

## Solution

**Script CLI Python**: `scripts/index_directory.py`

### Choix de Design Validés

1. **Scope**: Script CLI autonome (vs endpoint API)
   - Plus rapide à implémenter
   - Idéal pour tests et usage ad-hoc
   - API peut venir plus tard si besoin

2. **Embeddings**: Vrais embeddings activés
   - `jinaai/jina-embeddings-v2-base-code` (768D)
   - Override `EMBEDDING_MODE=mock` → `EMBEDDING_MODE=real`
   - Permet recherche sémantique fonctionnelle

3. **Progression**: Console détaillée avec barres
   - 3 phases visibles: Chunking → Embeddings → Graph
   - Stats par phase + temps
   - Rapport final détaillé

4. **Erreurs**: Mode résilient (continue on error)
   - Continue malgré fichiers corrompus
   - Rapport des échecs à la fin
   - Indexe le maximum de code valide

5. **Filtrage**: Strict TypeScript/JavaScript
   - Include: `.ts`, `.tsx`, `.js`, `.jsx`
   - Exclude: `*.test.ts`, `*.spec.ts`, `__tests__/`, `node_modules/`, `.d.ts`
   - Focus sur code métier uniquement

## Architecture

### Pipeline en 3 Phases

#### Phase 1: Scanning & Chunking (45-60s)
```
Répertoire → Scan récursif → Filtrage → AST Parsing → Chunks
```

**Responsabilités**:
- Scan récursif avec filtres
- Détection langue (TypeScript vs JavaScript)
- AST parsing via tree-sitter
- Génération chunks sémantiques (fonctions, classes, méthodes)
- Classification barrels/configs (EPIC-29)
- Filtrage tests (EPIC-29)

**Services utilisés**:
- `CodeChunkingService` (existant)
- `FileClassificationService` (existant, EPIC-29)

**Output**: Liste de `CodeChunk` objects (non-persistés)

#### Phase 2: Embedding Generation (3-5 min)
```
Chunks → Batch Processing → Model Inference → Vecteurs 768D → PostgreSQL
```

**Responsabilités**:
- Activation embeddings réels (`EMBEDDING_MODE=real`)
- Chargement modèle `jinaai/jina-embeddings-v2-base-code`
- Batch processing (50 chunks/batch pour perf)
- Génération vecteurs CODE (768D)
- Persistance dans `code_chunks` table

**Services utilisés**:
- `DualEmbeddingService` (existant)
- `CodeChunkRepository` (existant)

**Output**: Chunks persistés avec embeddings en DB

#### Phase 3: Graph Construction (10-20s)
```
Chunks DB → Résolution Calls/Imports → Nœuds + Edges → PostgreSQL
```

**Responsabilités**:
- Création nœuds (fonctions, classes)
- Résolution call edges (appels de fonction)
- Résolution import edges
- Filtrage anonymes (EPIC-30): 45-70% réduction
- Transaction atomique (EPIC-12)

**Services utilisés**:
- `GraphConstructionService` (existant, avec EPIC-30)

**Output**: Graph complet dans `nodes` + `edges` tables

### Services Réutilisés

Tous les services existants sont réutilisés:
- ✅ `CodeChunkingService`: AST parsing, chunking sémantique
- ✅ `DualEmbeddingService`: Génération embeddings dual (TEXT + CODE)
- ✅ `GraphConstructionService`: Construction graph avec filtrage EPIC-30
- ✅ `FileClassificationService`: Classification barrels/configs (EPIC-29)
- ✅ `CodeChunkRepository`: Persistance chunks

Le script orchestre simplement ces services existants.

## Interface Utilisateur

### Utilisation
```bash
# Indexation basique
python scripts/index_directory.py /path/to/code_test

# Avec options
python scripts/index_directory.py /path/to/code_test \
  --repository code_test \
  --verbose
```

### Output Console (Phase 1)
```
================================================================================
🚀 MnemoLite Directory Indexer
================================================================================

📁 Repository: code_test
📂 Path: /home/user/code_test
🔍 Scanning for TypeScript/JavaScript files...

   Found files:
   - .ts files: 210
   - .tsx files: 35
   - .js files: 12
   - .jsx files: 2

   Filtered out:
   - Test files: 89
   - Node modules: 1,245
   - Declaration files: 45

   📊 Total to index: 259 files

================================================================================
📖 Phase 1/3: Code Chunking & AST Parsing
================================================================================

[████████████████████████████████] 259/259 files (100%)

✅ Chunking complete in 52.3s
   - Chunks created: 1,247
   - Barrels detected: 8
   - Config files: 12
   - Anonymous filtered: 0 (filtered at graph phase)
```

### Output Console (Phase 2)
```
================================================================================
🧠 Phase 2/3: Embedding Generation
================================================================================

🔧 Loading embedding model: jinaai/jina-embeddings-v2-base-code
   Model loaded in 2.1s (768 dimensions)

[████████████████████████████████] 1247/1247 chunks (100%)
   Batch 1/25: 50 chunks embedded in 8.2s
   Batch 2/25: 50 chunks embedded in 8.1s
   ...
   Batch 25/25: 47 chunks embedded in 7.8s

✅ Embeddings generated in 3m 45s
   - Code embeddings: 1,247
   - Average time/chunk: 0.18s
   - Stored in database: ✅
```

### Output Console (Phase 3)
```
================================================================================
🔗 Phase 3/3: Graph Construction
================================================================================

Building graph for repository: code_test
   Creating nodes... [████████████] 850 nodes created

   EPIC-30 Anonymous Filtering:
   - Total chunks: 1,247
   - Anonymous functions: 397 (31.8%)
   - Filtered out: 397 ❌
   - Nodes created: 850 ✅

   Creating edges... [████████████] 324 edges created
   - Call edges: 278
   - Import edges: 46
   - Re-export edges: 0

✅ Graph constructed in 11.7s
   - Nodes: 850
   - Edges: 324
   - Edge ratio: 38.1%

================================================================================
✅ INDEXING COMPLETE!
================================================================================

📊 Final Summary:
   Repository: code_test

   Files:
   - Scanned: 259
   - Succeeded: 256
   - Failed: 3

   Chunks:
   - Created: 1,247
   - With embeddings: 1,247

   Graph:
   - Nodes: 850 (397 anonymes filtrés)
   - Edges: 324
   - Edge ratio: 38.1%

   Performance:
   - Phase 1 (Chunking): 52.3s
   - Phase 2 (Embeddings): 3m 45s
   - Phase 3 (Graph): 11.7s
   - Total: 4m 49s

⚠️  Failed Files (3):
   1. packages/ui/src/broken.ts
      Error: Invalid UTF-8 encoding at line 42

   2. packages/core/src/legacy.ts
      Error: Parse error - unexpected token

   3. packages/shared/src/timeout.ts
      Error: Chunking timeout after 60s

🎨 View graph at: http://localhost:3002/
   Select repository: code_test

================================================================================
```

## Gestion des Erreurs

### Erreurs Niveau Fichier
- **Continue on error**: Fichier échoué → logged, continuez
- **Causes**: UTF-8 invalide, parse error, timeout
- **Rapport**: Liste à la fin avec détails

### Erreurs Niveau Service
- **Embedding service failure**: Retry 3x, puis skip chunk
- **Database error**: Rollback transaction, rapport erreur
- **Graph construction error**: Skip, log warning

### Transaction Safety (EPIC-12)
- Phase 2 (embeddings): Transaction par batch (50 chunks)
- Phase 3 (graph): Transaction atomique pour tout le graph
- Rollback si erreur critique

## Performance Attendue

**Pour code_test (259 fichiers, ~50k LOC)**:
- Phase 1: ~50s (chunking)
- Phase 2: ~4min (embeddings, model loading inclus)
- Phase 3: ~10s (graph)
- **Total**: ~5 minutes

**Scalabilité**:
- 1,000 fichiers: ~15-20 min
- 10,000 fichiers: ~2-3 heures
- Bottleneck: Embedding generation (CPU-bound)

## Améliorations Futures

1. **Parallélisation embeddings**: ThreadPoolExecutor pour batches parallèles
2. **Endpoint API**: `/v1/code/index/directory` pour usage REST
3. **Progress callback**: WebSocket pour real-time progress dans UI
4. **Filtres configurables**: Arguments CLI pour personnaliser filtrage
5. **Cache AST**: Réutiliser parsed trees si fichier inchangé
6. **Incremental indexing**: Re-indexer seulement fichiers modifiés

## Tests

### Test 1: Indexation code_test
```bash
python scripts/index_directory.py /app/code_test --repository code_test
```
**Attendu**: 850+ nodes, 300+ edges, 0-3 erreurs

### Test 2: Vérification graph UI
1. Ouvrir http://localhost:3002/
2. Sélectionner "code_test"
3. Vérifier graph visible et navigable

### Test 3: Recherche sémantique
```bash
curl -X POST http://localhost:8001/v1/search \
  -d '{"query": "validate resume", "repository": "code_test"}'
```
**Attendu**: Résultats pertinents avec embeddings CODE

## Décisions Techniques

| Aspect | Choix | Alternatives | Raison |
|--------|-------|--------------|--------|
| Interface | CLI Script | API Endpoint | Plus rapide à implémenter |
| Embeddings | Real (Jina) | Mock | Recherche sémantique fonctionnelle |
| Progression | Console détaillée | Silent + log file | Feedback utilisateur |
| Erreurs | Continue on error | Fail-fast | Robustesse |
| Filtrage | Strict TS/JS | Tout inclure | Graph propre |
| Transaction | Atomic graph | No transaction | EPIC-12 safety |

## Références

- EPIC-29: Barrel/Config classification
- EPIC-30: Anonymous function filtering
- EPIC-12: Transaction safety
- Service: `CodeIndexingService` (référence pour pipeline)
