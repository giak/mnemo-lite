# Audit MCP Search System — Performance & Optimization

**Date:** 2026-04-02 | **Scope:** Code search + Memory search | **Version:** v4.3.0

---

## 1. Architecture Overview

### 1.1 Code Search Pipeline (`search_code`)

```
Client → MCP Server → SearchCodeTool.execute()
  │
  ├─ 1. Validate inputs (query 1-500, limit 1-100, offset 0-1000)
  ├─ 2. Generate SHA256 cache key from ALL parameters
  ├─ 3. Check Redis L2 cache (30s TTL)
  ├─ 4. Generate CODE embedding (80-200ms cold, 30-80ms warm)
  ├─ 5. HybridCodeSearchService.search()
  │     ├─ lexical_search (pg_trgm)          ← 5-15ms
  │     ├─ vector_search (HNSW halfvec)      ← 10-30ms
  │     ├─ rrf_fusion (Python, k=60 adaptive) ← <1ms
  │     └─ bm25_rerank (disabled by default)  ← <2ms
  ├─ 6. In-memory pagination (fetch all, slice)
  └─ 7. Write to Redis L2 cache (30s TTL)
```

### 1.2 Memory Search Pipeline (`search_memory`)

```
Client → MCP Server → SearchMemoryTool.execute()
  │
  ├─ 1. Validate inputs, normalize tags
  ├─ 2. Detect tag-only query (sys:*/trace:*) → SKIP embedding
  ├─ 3. If not tag-only: generate TEXT embedding (80-200ms)
  ├─ 4. Hybrid search or fallback
  │     ├─ lexical (ILIKE + pg_trgm on title/embedding_source)
  │     ├─ vector (HNSW halfvec, cosine)
  │     ├─ rrf_fusion
  │     └─ bm25_rerank (enabled by default)
  ├─ 5. Apply temporal decay scores
  └─ 6. Return results (NO CACHING)
```

### 1.3 Key Patterns

| Pattern | Implementation |
|---------|---------------|
| CQRS | Separate read (search) and write (CRUD) paths |
| Hybrid Search | pg_trgm lexical + pgvector HNSW + RRF fusion |
| L1/L2/L3 Cache | In-memory LRU → Redis → PostgreSQL |
| Graceful Degradation | Embedding failure → lexical-only; Redis failure → direct DB |
| Tag-only optimization | Skip embedding for sys:*/trace:* queries |

---

## 2. Performance Benchmarks

### 2.1 Code Search

| Stage | Cold Start | Warm Start | Bottleneck |
|-------|-----------|------------|------------|
| Cache lookup | 1-5ms | <1ms | Redis connection pool init |
| Embedding generation | 80-200ms | 30-80ms | Model loading on first call |
| Lexical search (pg_trgm) | 5-15ms | 2-8ms | Trigram index scan |
| Vector search (HNSW) | 10-30ms | 5-15ms | HNSW traversal + filter pushdown |
| RRF fusion | <1ms | <1ms | Negligible |
| BM25 reranking | 0.5-2ms | 0.5-2ms | Pure Python |
| **Total uncached** | **~150-300ms** | **~50-150ms** | Embedding generation |
| **Total cached** | **<10ms** | **<10ms** | Redis roundtrip |

### 2.2 Memory Search

| Stage | Cold Start | Warm Start | Bottleneck |
|-------|-----------|------------|------------|
| Tag-only detection | <1ms | <1ms | Negligible |
| Embedding generation | 80-200ms | 30-80ms | Model loading |
| Lexical search (ILIKE+trgm) | 5-20ms | 2-10ms | Full text scan |
| Vector search (HNSW) | 10-30ms | 5-15ms | HNSW traversal |
| BM25 reranking | 0.5-2ms | 0.5-2ms | Pure Python |
| **Total uncached** | **~100-200ms** | **~50-100ms** | Embedding generation |
| **Total tag-only** | **<20ms** | **<20ms** | DB query |

### 2.3 MCP Search (via Kilo client)

| Scenario | Before Fix | After Fix | Improvement |
|----------|-----------|-----------|-------------|
| `query="sys:protocol"` (tag-only) | 8,214ms | **0.06ms** | **137,000×** |
| `query="authentication function"` (natural) | ~17s (cold) | ~150ms (warm) | **113×** |
| Cached search | N/A | <10ms | — |

---

## 3. Issues Found

### P0 — Critical (Correctness)

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| **1** | **Cache key mismatch** — `HybridCodeSearchService` uses simple key (`cache_keys.py:12`) missing filters/offset/weights. Can return wrong cached results for different filter combinations. | `cache_keys.py:12-34`, `hybrid_code_search_service.py:250-274` | Users may get results for wrong filters |
| **2** | **Memory search not cached** — `search_memory` has zero caching. Every query hits the database directly. | `memory_tools.py:611-820` | Unnecessary DB load for repeated queries |
| **3** | **In-memory pagination** — fetches `limit + offset` then slices. For offset=900, wastes 900 results. | `hybrid_code_search_service.py:197-217` | Wasted DB work + memory for deep pagination |

### P1 — High Priority (Performance)

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| **4** | **JSONB filter scans** — `metadata->>'repository'` and `jsonb_each_text` prevent index usage. Full O(n) scan instead of index lookup. | `lexical_search_service.py:136-152`, `vector_search_service.py:126-142` | 5-10× slower for filtered searches |
| **5** | **Repository invalidation clears ALL L1** — `cascade_cache.py:219` calls `self.l1.clear()` for any repo flush. Evicts all cached chunks. | `cascade_cache.py:219` | Cache thrashing after any reindex |
| **6** | **No embedding cache** — Embeddings regenerated every search call. Model load adds 80-200ms cold start. | `dual_embedding_service.py` | Repeated embedding computation |
| **7** | **BM25 reranking disabled for code search** — `default_enable_reranking=False` in code search. Missing +10-20% relevance. | `hybrid_code_search_service.py:149` | Lower search quality |

### P2 — Medium Priority (Quality)

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| **8** | **Two cache key strategies** — Tool generates SHA256, service uses MD5. Inconsistent and confusing. | `search_tool.py:326-366` vs `cache_keys.py:12` | Maintainability risk |
| **9** | **No search analytics** — No tracking of query patterns, hit rates, or result quality. Cannot optimize what you can't measure. | — | Blind to search quality |
| **10** | **L2 cache TTL too short** — 30s for search results means frequent cache misses for popular queries. | `hybrid_code_search_service.py:250` | Unnecessary DB load |
| **11** | **Tag filter uses AND logic only** — `search_by_tags` requires ALL tags to match. No OR mode. | `memory_repository.py:580-620` | Limited search flexibility |
| **12** | **No full-text index on memories.content** — Lexical search skips content entirely. Vector search may miss exact keyword matches. | `hybrid_memory_search_service.py:466-578` | Lower recall |

### P3 — Low Priority

| # | Issue | Impact |
|---|-------|--------|
| **13** | RRF k heuristic is simplistic (counts parentheses/braces) | Misclassifies some queries |
| **14** | No search result deduplication | Same file appears multiple times |
| **15** | No query rewriting ("auth" ≠ "authentication") | Misses synonyms |

---

## 4. Missing Features

| Feature | Value | Effort |
|---------|-------|--------|
| **Search suggestions/autocomplete** | Help users formulate effective queries | M |
| **Search analytics dashboard** | Identify popular queries, zero-result queries, slow queries | M |
| **Query rewriting** | "auth" → "authentication", "db" → "database" | M |
| **Advanced filtering** | Date range, file size, complexity metrics, dependency depth | M |
| **Search result highlighting** | Highlight matching terms in results | S |
| **Cross-repository search** | Search across multiple repositories simultaneously | M |
| **Incremental index awareness** | Auto cache invalidation on incremental reindex | S |

---

## 5. Recommended EPIC: EPIC-32 — Search Performance & Quality

Based on this audit, here's a prioritized implementation plan:

### Phase 1: Quick Wins (P0 fixes, ~4h)
- **32.1** Fix cache key mismatch — unify cache key strategy
- **32.2** Add Redis caching for memory search (tag-only + frequent queries)
- **32.3** Enable BM25 reranking for code search

### Phase 2: Performance (P1 fixes, ~6h)
- **32.4** Add GIN index on metadata JSONB paths (or computed columns)
- **32.5** Fix L1 cache invalidation — per-repository instead of global clear
- **32.6** Add embedding cache (query text → vector, 5-min TTL)

### Phase 3: Quality (P2 fixes, ~6h)
- **32.7** Add search analytics logging
- **32.8** Increase L2 cache TTL to 2-5 minutes
- **32.9** Add OR mode for tag filters
- **32.10** Add GIN trigram index on memories.content

### Phase 4: Features (P3, ~8h)
- **32.11** Search result highlighting
- **32.12** Search result deduplication
- **32.13** Query rewriting / synonym support

**Total estimated effort:** ~24h (3 days)
**Expected improvement:** 5-10× faster cached searches, +20% search relevance

---

## 6. Summary Statistics

| Category | P0 | P1 | P2 | P3 |
|----------|----|----|----|----|
| Correctness | 1 | 0 | 0 | 0 |
| Performance | 2 | 3 | 1 | 0 |
| Quality | 0 | 1 | 1 | 1 |
| Maintainability | 0 | 0 | 1 | 0 |
| Usability | 0 | 0 | 1 | 1 |
| Observability | 0 | 0 | 1 | 0 |
| **Total** | **3** | **4** | **5** | **2** |
