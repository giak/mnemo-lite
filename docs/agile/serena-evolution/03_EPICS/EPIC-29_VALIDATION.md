# EPIC-29 Python Indexing - Dog-Fooding Validation

**Date:** 2025-11-07
**Repository:** mnemolite-python (231 files indexed: 170 Python + 61 TypeScript)
**Last Indexed:** 2025-11-07 16:17:03

## Indexing Stats

| Metric | Count |
|--------|-------|
| Files | 231 |
| Chunks | 1789 |
| Languages | Python, TypeScript |

**Note:** Graph stats (nodes/edges/edge ratio) were not accessible due to database schema issues with the `created_at` column in the `switch_project` tool.

## MCP Search Validation

### Query 1: "async database transaction"
**Goal:** Find database transaction functions with async patterns

**Top 3 Results:**
1. `SpikeTestScenario` class - `/app/locust_test.py` (function: surge_traffic)
   - Load testing class, not database transactions

2. `StressTestScenario` class - `/app/locust_test.py` (function: rapid_search)
   - Load testing class, not database transactions

3. `generate_random_timestamp` function - `/app/scripts/benchmarks/generate_test_data.py`
   - Test data generation, not transactions

**Accuracy:** ❌ **Not Relevant**
- None of the top 3 results are database transaction functions
- Expected to find: `execute_transaction`, `begin_transaction`, async database service methods
- Results are semantically related (testing, async patterns) but not the target domain

---

### Query 2: "embedding service generate embeddings"
**Goal:** Find EmbeddingService class and generate_embedding methods

**Top 3 Results:**
1. `embedding_service` property - `/app/mnemo_mcp/base.py`
   - Property accessor for embedding service (partial match)

2. `request_choice` function - `/app/mnemo_mcp/elicitation.py`
   - MCP elicitation helper, not embedding-related

3. `get` function (ProjectsListResponse) - `/app/mnemo_mcp/resources/config_resources.py`
   - Projects listing, not embedding-related

**Accuracy:** ⚠️ **Partially Relevant**
- Result #1 is related (embedding service accessor)
- Missing: `EmbeddingService` class, `generate_embedding` method
- Lexical match found (12 matches) but vector search didn't prioritize correctly

---

### Query 3: "hybrid search RRF fusion"
**Goal:** Find HybridSearchService and RRF (Reciprocal Rank Fusion) logic

**Top 3 Results:**
1. `search_by_label` function - `/app/db/repositories/node_repository.py`
   - Graph node search, not hybrid search

2. `search_by_label` function (duplicate) - `/app/db/repositories/node_repository.py`
   - Same as above (duplicate result)

3. `build_search_by_label_query` function - `/app/db/repositories/node_repository.py`
   - Query builder, not hybrid search

**Accuracy:** ❌ **Not Relevant**
- No results related to HybridSearchService or RRF fusion
- Expected to find: `HybridSearchService`, RRF calculation, reciprocal rank functions
- Results contain "search" keyword but wrong domain (graph vs code search)

---

### Query 4: "tree-sitter metadata extraction"
**Goal:** Find MetadataExtractor classes and tree-sitter parsing code

**Top 3 Results:**
1. `get_cache_stats` function - `/app/scripts/benchmarks/cache_benchmark.py`
   - Cache statistics, not metadata extraction

2. `get_cache_stats` function (duplicate) - `/app/scripts/benchmarks/cache_benchmark.py`
   - Same as above

3. `build_get_by_id_query` function - `/app/db/repositories/edge_repository.py`
   - Database query builder, not metadata extraction

**Accuracy:** ❌ **Not Relevant**
- No results related to tree-sitter or metadata extraction
- Expected to find: `PythonMetadataExtractor`, `TypeScriptMetadataExtractor`, `extract_imports`, `extract_calls`
- Results are completely unrelated

---

## Overall Assessment

**Success Criteria:** ❌ **FAILED**
- ❌ Edge ratio > 40% - Could not verify (database schema issue)
- ❌ At least 3/4 queries return relevant results - Only 0.25/4 queries partially relevant
- ❌ Can navigate MnemoLite codebase via MCP - Search quality insufficient

**Query Success Rate:** 0.25/4 (6.25%)
- Query 1: ❌ Not relevant (0/3 results)
- Query 2: ⚠️ Partially relevant (1/3 results)
- Query 3: ❌ Not relevant (0/3 results)
- Query 4: ❌ Not relevant (0/3 results)

---

## Root Cause Analysis

### Issue 1: Repository Filter Not Working
**Problem:** Searches with `repository: "mnemolite-python"` returned 0 results
**Root Cause:** Database schema issue - `created_at` column doesn't exist in `code_chunks` table
**Impact:** Had to search without repository filter, mixing results from all indexed projects

### Issue 2: Poor Semantic Search Quality
**Problem:** Vector embeddings not finding domain-specific code
**Observations:**
- Query "embedding service" found unrelated elicitation functions
- Query "hybrid search RRF" found graph search instead of code search
- Query "tree-sitter metadata" found cache stats and database queries

**Possible Causes:**
1. **Embedding model quality:** Vector similarity scores (0.53-0.56) are mediocre
2. **Chunk granularity:** Files may be chunked too broadly or narrowly
3. **Metadata not indexed in embeddings:** Function names, docstrings, calls may not be weighted in embeddings
4. **Insufficient training data:** Embedding model may not understand code-specific terminology

### Issue 3: Lexical Search Not Compensating
**Problem:** Lexical search returned 0-13 matches but didn't boost correct results
**Observations:**
- Query "embedding service generate embeddings" had 12 lexical matches but wrong top result
- RRF fusion (40% lexical, 60% vector) didn't prioritize lexical matches correctly

---

## Recommendations

### Immediate Fixes
1. **Fix Database Schema:** Add missing `created_at` column or update query in `switch_project`
2. **Verify Indexing Coverage:** Check that target files were actually indexed:
   - `/app/services/embedding_service.py`
   - `/app/services/hybrid_code_search_service.py`
   - `/app/services/metadata_extractors/python_extractor.py`
3. **Test Simpler Queries:** Try exact class/function names to verify lexical search works

### Search Quality Improvements
1. **Tune RRF Weights:** Try 60% lexical, 40% vector for code search (reverse current)
2. **Improve Chunk Metadata:** Include function signatures, class names in chunk content
3. **Add LSP Integration:** Use actual symbols, not just embeddings
4. **Test Alternative Embedding Models:** Current model may not be code-optimized

### Validation Improvements
1. **Add Query Precision Metrics:** Track P@1, P@3, P@5 for known target functions
2. **Create Golden Query Set:** Specific queries with expected results for regression testing
3. **Automate Validation:** Script to run queries and verify expected results

---

## Conclusion

EPIC-29 successfully implemented Python indexing infrastructure (PythonMetadataExtractor, integration with chunking pipeline, 231 files indexed), but **dog-fooding validation reveals critical search quality issues**. The indexed data exists, but semantic search is not returning relevant results for domain-specific queries.

**Status:** ✅ **IMPLEMENTATION COMPLETE** but ❌ **SEARCH QUALITY INSUFFICIENT**

**Blocking Issues:**
1. Database schema issue preventing repository filtering
2. Poor vector embedding quality for code search
3. RRF fusion not prioritizing lexical matches

**Next Steps:**
1. Fix database schema (created_at column)
2. Investigate why target files aren't ranking higher
3. Tune search weights and revalidate
4. Consider alternative embedding strategies

**Recommendation:** Mark EPIC-29 as "Implementation Complete, Search Quality Needs Improvement" and create follow-up EPIC for search quality tuning.

---

**Validation Date:** 2025-11-07
**Validated By:** Claude Code (Automated MCP Testing)
**MCP Version:** FastMCP with mnemolite server
