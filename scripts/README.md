# Scripts MnemoLite

## claude-with-hooks.sh

**Workaround pour Bug Claude Code #10401**

### Problème

Claude Code v2.0.27+ ne déclenche **AUCUN hook** (Stop, UserPromptSubmit, etc.) sans le flag `--debug hooks`.

**Impact**: Les conversations ne sont PAS sauvegardées automatiquement malgré la configuration correcte dans `.claude/settings.local.json`.

**Issue GitHub**: [#10401](https://github.com/anthropics/claude-code/issues/10401) - OPEN

### Solution

Ce wrapper script force automatiquement le flag `--debug hooks` à chaque lancement de Claude Code.

### Installation Rapide

```bash
# Option 1: Alias global (recommandé)
echo 'alias claude="$HOME/Work/MnemoLite/scripts/claude-with-hooks.sh"' >> ~/.bashrc
source ~/.bashrc

# Option 2: Copie dans ~/bin (si ~/bin est dans PATH)
cp scripts/claude-with-hooks.sh ~/bin/
chmod +x ~/bin/claude-with-hooks.sh
alias claude="$HOME/bin/claude-with-hooks.sh"

# Option 3: Lien symbolique
ln -s ~/Work/MnemoLite/scripts/claude-with-hooks.sh ~/bin/claude-hooks
alias claude='claude-hooks'
```

### Vérification

```bash
# 1. Tester l'alias
claude --version
# → Doit afficher: "🔧 Workaround Bug #10401: Activating hooks with --debug"

# 2. Vérifier que hooks s'exécutent
claude
# Poser une question, puis vérifier:
cat /tmp/mnemo-hook-stop.log
# → Doit contenir des entrées récentes

# 3. Vérifier conversations sauvegardées
docker compose exec -T db psql -U mnemo -d mnemolite -c "
SELECT COUNT(*), MAX(created_at)
FROM memories
WHERE memory_type = 'conversation' AND author = 'AutoSave';"
# → Count devrait augmenter après chaque conversation
```

### Usage

```bash
# Lancer nouvelle session (avec hooks activés)
claude

# Reprendre session précédente (avec hooks activés)
claude --resume

# Continue session spécifique (avec hooks activés)
claude --continue --session-id abc123

# Toutes les commandes Claude fonctionnent normalement
claude --help
```

### Désinstallation

Quand le bug sera corrigé en upstream:

```bash
# Supprimer l'alias
sed -i '/claude-with-hooks/d' ~/.bashrc
source ~/.bashrc

# Vérifier que claude original fonctionne avec hooks
ps aux | grep "claude.*--debug"
# → Si vide et hooks fonctionnent: bug corrigé, wrapper plus nécessaire
```

---

## mcp_server.sh

Script pour lancer le serveur MCP MnemoLite en standalone (pour debug).

**Usage**:
```bash
./scripts/mcp_server.sh
```

**Logs**: stdout/stderr

---

## periodic-conversation-scanner.py (À venir)

Background job pour parser périodiquement les transcripts Claude Code et sauvegarder les conversations manquées.

**Status**: Pas encore implémenté (Layer 3 de l'architecture multi-couches)

**Plan**:
- Parse `~/.claude/projects/` toutes les 5 minutes
- Détecte nouveaux échanges via hash deduplication
- Sauvegarde via `write_memory` MCP tool
- Coverage: +1.5% (rattrapage des hooks manqués)

---

## index_directory.py

Index entire TypeScript/JavaScript codebases into MnemoLite.

### Requirements

- Python 3.12+
- Docker (for running in container)
- tqdm: `pip install tqdm`

### Usage

**In Docker (recommended)**:
```bash
# Copy script to container
docker cp scripts/index_directory.py mnemo-api:/app/scripts/

# Run indexing
docker exec -i mnemo-api python3 /app/scripts/index_directory.py \
  /app/code_test \
  --repository code_test \
  --verbose
```

**On Host**:
```bash
# Ensure DATABASE_URL is set
export DATABASE_URL="postgresql+asyncpg://mnemo:mnemo@localhost:5432/mnemolite"

# Run indexing
python scripts/index_directory.py /path/to/code --repository myproject
```

### Options

- `directory` (required): Path to codebase
- `--repository` (optional): Repository name (default: directory name)
- `--verbose`: Enable detailed logging

### Pipeline Architecture (Streaming Mode)

**Streaming Pipeline** - Constant memory footprint regardless of repository size

**Processing Model:**
- **File-at-a-Time**: Each source file processed completely before next
- **Atomic Transactions**: Each file = 1 DB transaction (auto-rollback on error)
- **Continue-on-Error**: Failed files logged, processing continues
- **Memory Footprint**: Constant ~738MB peak (embedding model + single file)

**Phases:**

1. **Cleanup Phase**: Delete existing repository data (clean slate)
   - Removes all chunks, nodes, edges, metadata for repository
   - Ensures consistent state before indexing

2. **Streaming Process** (per file, one-at-a-time):
   ```
   For each source file:
   a. Chunk (in-memory) → list[CodeChunk]
      - AST parsing with tree-sitter
      - Extracts functions, classes, methods
      - Excludes tests, node_modules, declarations (EPIC-30)

   b. Generate embeddings (in-memory) → add 768D vectors
      - Uses jinaai/jina-embeddings-v2-base-code
      - CODE domain embeddings only

   c. Extract metadata (in-memory) → calls, imports, signatures, complexity
      - Call contexts with line numbers and scope
      - Function signatures with types
      - Cyclomatic complexity metrics

   d. Write atomically to DB (single transaction)
      - All chunks for file written together
      - Transaction rollback on any error

   e. Clear memory (gc.collect())
      - Force garbage collection between files
   ```

3. **Graph Construction Phase** (bulk after all files):
   - **Graph Building**:
     - Creates nodes (functions, classes) in `nodes` table
     - Resolves call/import edges in `edges` table
     - Links to code chunks
   - **Graph Metrics Calculation**:
     - **PageRank**: Identifies most important/central functions
       - Damping factor: 0.85
       - Convergence threshold: 1e-6
     - **Coupling Metrics**:
       - Afferent coupling (incoming dependencies)
       - Efferent coupling (outgoing dependencies)
       - Instability index: Ce / (Ca + Ce)
     - **Edge Weights**: Relationship importance scores
   - **Storage**:
     - Updates `computed_metrics` with coupling/PageRank
     - Stores weights in `edge_weights` table

### Database Schema (Rich Metadata v2.0)

**New Tables:**

1. **detailed_metadata** - Flexible metadata storage
   - `metadata_id` (UUID, PK)
   - `node_id` (UUID, FK → nodes)
   - `chunk_id` (UUID, FK → code_chunks)
   - `metadata` (JSONB) - calls, signatures, contexts
   - `version` (INTEGER) - tracking changes
   - GIN index on `metadata` for fast JSONB queries

2. **computed_metrics** - Performance-optimized metrics
   - `metric_id` (UUID, PK)
   - `node_id` (UUID, FK → nodes)
   - `chunk_id` (UUID, FK → code_chunks)
   - `repository` (VARCHAR)
   - `cyclomatic_complexity` (INTEGER)
   - `cognitive_complexity` (INTEGER)
   - `lines_of_code` (INTEGER)
   - `afferent_coupling` (INTEGER)
   - `efferent_coupling` (INTEGER)
   - `pagerank_score` (DOUBLE PRECISION)
   - `version` (INTEGER)
   - B-tree indexes for query performance

3. **edge_weights** - Relationship importance
   - `weight_id` (UUID, PK)
   - `edge_id` (UUID, FK → edges)
   - `importance_score` (DOUBLE PRECISION)
   - `version` (INTEGER)
   - UNIQUE constraint on (edge_id, version)

**Enhanced Tables:**

- **edges**: Added `is_external` (BOOLEAN), `weight` (DOUBLE PRECISION)

### Performance

**Streaming Mode Results:**

- **Memory**: Constant ~738MB peak (vs 8GB+ OOM in batch mode)
- **Improvement**: 29% → 75% completion before OOM on large repos
- **Test Case**: Successfully processed 196/261 files (code_test), created 1,183 chunks
- **Bottleneck**: Embedding generation (CPU-bound, ~2s per chunk)

**Estimated Pipeline Time:**

- 100 files: ~5-7 minutes
- 200 files: ~10-15 minutes (verified with code_test partial run)
- 500 files: ~25-30 minutes
- 1000 files: ~50-60 minutes

**Phase Breakdown:**
- Cleanup: <5 seconds
- Streaming Process: 90-95% of time
  - Chunking: 10-15%
  - Embeddings: 70-75% ← bottleneck
  - Metadata extraction: 10-15%
  - DB writes: <5%
- Graph Construction: 5-10% of time

**Known Limitations:**
- Large repositories (>200 files) may still encounter OOM
- Workaround: Increase Docker memory limit to 12-16GB
- Future: Implement checkpoint/resume for very large codebases

**Note**: Streaming mode trades ~10% performance overhead for 3x memory efficiency and robust error handling.

### Troubleshooting

**Issue**: Script fails with "out of memory" error
- **Cause**: Very large repositories (>200 files) or individual files (>100MB)
- **Solution**:
  - Increase Docker memory limit in docker-compose.yml to 12-16GB
  - Or split repository into smaller batches for indexing
  - Or exclude large files from indexing

**Issue**: Some files show as "failed" in summary
- **Cause**: Parse errors, invalid syntax, unsupported language constructs
- **Solution**:
  - Check error log for specific file issues
  - Fix source files if syntax errors
  - Add problematic patterns to exclusion filters in `scan_files()`
  - Failed files don't block overall pipeline (continue-on-error)

**Issue**: Graph visualization empty despite chunks indexed
- **Cause**: Phase 3 (graph construction) failed or didn't run
- **Solution**:
  - Check logs for graph construction errors
  - Verify chunks exist: `SELECT COUNT(*) FROM code_chunks WHERE repository = 'your_repo'`
  - Re-run indexing with `--verbose` flag to see detailed Phase 3 output
  - Check for FK constraint violations in edges/nodes tables

**Issue**: Indexing very slow (>1 minute per file)
- **Cause**: Very large functions/classes, complex metadata extraction, CPU bottleneck
- **Solution**:
  - This is expected for large files (embedding generation is CPU-bound)
  - Let it complete, streaming mode ensures it won't OOM
  - Consider excluding very large files if they're auto-generated
  - Monitor with `--verbose` flag to see per-file progress

**Issue**: Missing edges/calls in graph
- **Cause**: Call/import resolution failed (dynamic imports, aliases, external dependencies)
- **Solution**:
  - This is expected - graph shows only statically analyzable relationships
  - Dynamic imports (`import()`) and alias resolution have limitations
  - External dependencies (node_modules) intentionally excluded
  - Check `edges.is_external` flag for cross-repository calls

**Issue**: Transaction rollback errors in logs
- **Cause**: Database constraint violations or connection issues
- **Solution**:
  - Verify DATABASE_URL is correct and accessible
  - Check PostgreSQL logs: `docker compose logs db`
  - Ensure no concurrent indexing of same repository
  - Verify schema is up-to-date: check migrations

### API Endpoints

**Graph Statistics:**
```bash
GET /v1/code/graph/stats/{repository}
# Returns: total_nodes, total_edges, nodes_by_type, edges_by_type
```

**Graph Data (Visualization):**
```bash
GET /v1/code/graph/data/{repository}?limit=500
# Returns: nodes[], edges[] with IDs, labels, types
```

**Repository Metrics:**
```bash
GET /v1/code/graph/metrics/{repository}
# Returns:
# - total_functions
# - avg_complexity, max_complexity, most_complex_function
# - avg_coupling
# - top_pagerank (top 10 most important functions)
```

**Build Graph:**
```bash
POST /v1/code/graph/build
Body: {"repository": "MyRepo", "language": "typescript"}
# Triggers graph construction for existing chunks
```

### Viewing Results

**Graph Visualization UI:**

1. Open http://localhost:3002/
2. Select repository from dropdown
3. View interactive features:
   - **Graph Stats Panel**: Node/edge counts by type
   - **Metrics Dashboard**:
     - Average/Max Cyclomatic Complexity
     - Average Coupling
     - Most Complex Function
     - Top 10 PageRank Functions (bar chart)
   - **Interactive Graph**:
     - Force-directed layout
     - Node colors by type
     - Hover for details
     - Click to navigate

**Database Queries:**

```sql
-- View detailed metadata for a function
SELECT n.properties->>'name' as function_name,
       dm.metadata->'signature' as signature,
       dm.metadata->'complexity' as complexity,
       dm.metadata->'call_contexts' as calls
FROM detailed_metadata dm
JOIN nodes n ON dm.node_id = n.node_id
WHERE n.properties->>'repository' = 'MyRepo';

-- Top 10 most complex functions
SELECT n.properties->>'name' as name,
       cm.cyclomatic_complexity,
       cm.lines_of_code
FROM computed_metrics cm
JOIN nodes n ON cm.node_id = n.node_id
WHERE cm.repository = 'MyRepo'
ORDER BY cm.cyclomatic_complexity DESC
LIMIT 10;

-- Most important functions (PageRank)
SELECT n.properties->>'name' as name,
       cm.pagerank_score,
       cm.afferent_coupling,
       cm.efferent_coupling
FROM computed_metrics cm
JOIN nodes n ON cm.node_id = n.node_id
WHERE cm.repository = 'MyRepo'
  AND cm.pagerank_score IS NOT NULL
ORDER BY cm.pagerank_score DESC
LIMIT 10;

-- High coupling functions (instability > 0.7)
SELECT n.properties->>'name' as name,
       cm.afferent_coupling as ca,
       cm.efferent_coupling as ce,
       ROUND(cm.efferent_coupling::numeric /
             NULLIF(cm.afferent_coupling + cm.efferent_coupling, 0), 2) as instability
FROM computed_metrics cm
JOIN nodes n ON cm.node_id = n.node_id
WHERE cm.repository = 'MyRepo'
  AND (cm.afferent_coupling + cm.efferent_coupling) > 0
HAVING ROUND(cm.efferent_coupling::numeric /
             NULLIF(cm.afferent_coupling + cm.efferent_coupling, 0), 2) > 0.7
ORDER BY instability DESC;
```

---

**Dernière mise à jour**: 2025-11-02
**EPIC**: Rich Metadata Extraction v2.0 (2025-11-02) - Complete code intelligence with graph metrics
