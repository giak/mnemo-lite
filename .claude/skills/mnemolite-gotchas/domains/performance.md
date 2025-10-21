# Performance & Optimization Gotchas

**Purpose**: Performance tuning, caching, and optimization gotchas

**When to reference**: Optimizing queries, tuning cache, or debugging performance issues

---

## 🟡 PERF-01: Rollback Safety

**Rule**: `./apply_optimizations.sh rollback` recovers system in ~10s

```bash
# Apply optimizations
./apply_optimizations.sh apply

# Benchmark
./apply_optimizations.sh benchmark

# If slower, rollback
./apply_optimizations.sh rollback  # ~10s recovery
```

**Why**: Backups created automatically, safe to experiment

**Backups location**: `backups/YYYY-MM-DD_HH-MM-SS/`

---

## 🟡 PERF-02: Cache Hit Rate Monitoring

**Rule**: Monitor cache hit rate, adjust TTL if <80%

```bash
# Check cache stats
curl http://localhost:8001/v1/events/cache/stats | jq

# Adjust TTL if hit rate low
# See api/services/caches/redis_cache.py
```

**Target**: 80%+ hit rate

**TTL values**:
- Events: 60s
- Search: 30s
- Graph: 120s

**Tuning**: Increase TTL if hit rate low, decrease if stale data problem

---

## 🟡 PERF-03: Vector Query Limits

**Rule**: ALWAYS use `LIMIT` with vector similarity queries

```sql
-- ✅ CORRECT
SELECT * FROM events
ORDER BY embedding <=> :query_vector
LIMIT 20;  -- CRITICAL!

-- ❌ WRONG - Scans entire table!
SELECT * FROM events
ORDER BY embedding <=> :query_vector;
```

**Why**: Without LIMIT, HNSW index not used efficiently. Scans all vectors.

**Detection**: Slow vector queries (>500ms), high CPU usage

**Typical limits**: 10-50 results (user-facing), 100-200 (internal)

---

**Total Performance Gotchas**: 3
