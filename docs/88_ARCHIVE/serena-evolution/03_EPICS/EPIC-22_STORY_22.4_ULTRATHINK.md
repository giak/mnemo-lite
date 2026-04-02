# EPIC-22 Story 22.4: Redis Monitoring Détaillé - ULTRATHINK

**Story**: Redis Monitoring Détaillé (2 pts)
**Status**: ⏸️ **SKIPPED** (YAGNI - deferred to Phase 3)
**Date**: 2025-10-24
**Decision Date**: 2025-10-24
**EPIC**: EPIC-22 Advanced Observability & Real-Time Monitoring
**Phase**: Phase 3 (Nice-to-Have) - was Phase 2

---

## ⏸️ DECISION: SKIPPED (YAGNI)

**Date**: 2025-10-24
**Decision**: Reporter Story 22.4 à Phase 3

**Raison**:
- ❌ Redis actuellement vide (0 keys, 0% hit rate)
- ❌ Pas de problème identifié nécessitant breakdown détaillé
- ✅ Phase 1 metrics suffisent (global hit rate, memory, keys total)
- ✅ Manual diagnosis possible si besoin (`redis-cli KEYS`, `INFO`)
- 🎯 YAGNI principle: "You Ain't Gonna Need It" (yet)

**Coût/Bénéfice**:
- Coût: 12h dev + 2ms/req overhead
- Bénéfice actuel: 0 (cache vide)
- Ratio: ∞ (infiniment cher pour 0 valeur)

**Trigger pour réactivation**:
- Redis keys > 5,000 OU
- (Hit rate < 70% ET Memory > 80%) OU
- Problème performance identifié nécessitant breakdown

**Alternative immédiate**: Manual diagnosis
```bash
# Breakdown manuel si besoin (5 min)
redis-cli
> KEYS search:*
> KEYS embedding:*
> INFO memory
```

**Focus Phase 2**: Story 22.5 (API perf par endpoint) → valeur immédiate (158 métriques API déjà collectées)

---

## 📋 Objectif (Original - pour référence future)

---

## 📋 Objectif

Créer un breakdown détaillé des métriques Redis **par type de cache** pour diagnostiquer performance et problèmes de cache.

**Problème actuel** (Phase 1):
```json
{
  "redis": {
    "hit_rate": 87.3,  // ← Global, pas de détail par type
    "memory_used_mb": 245,
    "keys_total": 536  // ← Total, pas de breakdown
  }
}
```

**Objectif Story 22.4**:
```json
{
  "redis": {
    "global": {
      "hit_rate": 87.3,
      "memory_used_mb": 245,
      "keys_total": 536
    },
    "breakdown_by_type": {
      "search_results": {
        "keys_count": 342,
        "hit_rate": 92.1,
        "memory_mb": 120.5,
        "avg_ttl_seconds": 1800
      },
      "embeddings": {
        "keys_count": 105,
        "hit_rate": 78.3,
        "memory_mb": 89.2,
        "avg_ttl_seconds": 3600
      },
      "graph_traversal": {
        "keys_count": 89,
        "hit_rate": 95.7,
        "memory_mb": 35.3,
        "avg_ttl_seconds": 900
      }
    },
    "top_keys": [
      {"key": "search:a3f2b9c1...", "memory_kb": 1024, "ttl": 1500},
      {"key": "embedding:b4c5d6e7...", "memory_kb": 512, "ttl": 3200}
    ]
  }
}
```

---

## 🎯 Valeur Business

### Avant Story 22.4 ❌
- ❌ **Hit rate global** (87%) ne dit pas **quel cache** est problématique
- ❌ Si hit rate baisse, impossible de savoir si c'est `search_results` ou `embeddings`
- ❌ Pas de visibilité sur **memory usage par type**
- ❌ Impossible de tuner TTL par cache type
- ❌ Pas de détection "1 key mange 80% memory" (outliers)

**Exemple problème réel**:
```
User: "Pourquoi search est lent ?"
Admin: *Check monitoring*
Redis hit rate: 87% ✅ (semble OK)

*Mais en réalité*:
- search_results hit rate: 50% 🔴 (très mauvais)
- embeddings hit rate: 99% ✅ (excellent)
- Global: (50% × 60% + 99% × 40%) = 87% 🟡

→ Le global 87% cache le problème search_results !
```

### Après Story 22.4 ✅
- ✅ **Hit rate par type** → diagnostic précis ("embeddings cache mal")
- ✅ **Memory breakdown** → détecter "graph_traversal mange 70% memory"
- ✅ **Top keys** → trouver outliers ("1 search result = 50 MB ?!")
- ✅ **TTL analysis** → optimiser retention par type
- ✅ **Evictions par type** → savoir quel cache est évincé

**Exemple résolution**:
```
Admin: *Check breakdown*
search_results hit rate: 50% 🔴
  → Problème: TTL trop court (900s)
  → Solution: Augmenter TTL à 1800s
  → Résultat: hit rate 50% → 85% ✅
```

---

## 🏗️ Architecture Technique

### Cache Keys Existants (v1.3.0)

D'après `api/services/caches/cache_keys.py`:

```python
# 1. Search Results
search:{md5_hash}
# Example: search:a3f2b9c1d4e5f6a7b8c9d0e1f2a3b4c5

# 2. Graph Traversal
graph:{node_id}:hops{N}:{relations}
# Example: graph:123e4567-e89b:hops3:calls,imports

# 3. Embeddings
embedding:{hash}
# Example: embedding:a3f2b9c1d4e5f6a7b8c9d0e1f2a3b4c5

# 4. Code Chunks
chunks:{file_path}:{hash}
# Example: chunks:src/main.py:a3f2b9c1d4e5f6a7

# 5. Repository Metadata
repo:meta:{repo_name}
# Example: repo:meta:my-project
```

**Pattern Recognition**:
- Prefixes: `search:`, `graph:`, `embedding:`, `chunks:`, `repo:`
- **→ Nous pouvons grouper par prefix !**

---

### Redis Analysis Strategy

#### Méthode 1: SCAN + Pattern Matching ✅ **RECOMMANDÉ**

**Concept**: Scanner toutes les keys Redis, grouper par prefix

```python
async def analyze_keys_by_type():
    """
    Scan all Redis keys and group by prefix.

    Uses SCAN (cursor-based) to avoid blocking Redis.
    """
    # Initialize counters
    stats = {
        "search_results": {"count": 0, "memory_bytes": 0, "ttls": []},
        "embeddings": {"count": 0, "memory_bytes": 0, "ttls": []},
        "graph_traversal": {"count": 0, "memory_bytes": 0, "ttls": []},
        "chunks": {"count": 0, "memory_bytes": 0, "ttls": []},
        "repo_meta": {"count": 0, "memory_bytes": 0, "ttls": []},
        "other": {"count": 0, "memory_bytes": 0, "ttls": []},
    }

    # SCAN all keys (cursor-based, non-blocking)
    cursor = 0
    while True:
        cursor, keys = await redis.scan(cursor, count=100)

        for key in keys:
            # Determine type by prefix
            if key.startswith(b"search:"):
                cache_type = "search_results"
            elif key.startswith(b"graph:"):
                cache_type = "graph_traversal"
            elif key.startswith(b"embedding:"):
                cache_type = "embeddings"
            elif key.startswith(b"chunks:"):
                cache_type = "chunks"
            elif key.startswith(b"repo:"):
                cache_type = "repo_meta"
            else:
                cache_type = "other"

            # Get memory usage (MEMORY USAGE command)
            memory_bytes = await redis.memory_usage(key) or 0

            # Get TTL
            ttl = await redis.ttl(key)

            # Accumulate stats
            stats[cache_type]["count"] += 1
            stats[cache_type]["memory_bytes"] += memory_bytes
            if ttl > 0:  # -1 = no expire, -2 = key not found
                stats[cache_type]["ttls"].append(ttl)

        if cursor == 0:
            break  # Full scan completed

    return stats
```

**Performance**:
- SCAN avec count=100 → ~10ms par batch (100 keys)
- 10,000 keys → 100 batches × 10ms = **1 seconde** ✅
- Non-bloquant (cursor-based)

**Avantages**:
- ✅ Précis (compte vraiment toutes les keys)
- ✅ Memory usage exact (MEMORY USAGE par key)
- ✅ TTL réel par key
- ✅ Non-bloquant (SCAN)

**Inconvénients**:
- ⏱️ Slow si millions de keys (1M keys = 100s)
- 🔄 Doit re-scanner à chaque appel (pas de cache)

---

#### Méthode 2: INFO Command + Estimation ⚡ **FAST**

**Concept**: Utiliser `INFO keyspace` + sampling

```python
async def estimate_keys_by_type():
    """
    Estimate breakdown using INFO + sampling.

    Fast but approximate.
    """
    info = await redis.info("keyspace")
    # db0:keys=536,expires=480,avg_ttl=1234567

    total_keys = info["db0"]["keys"]

    # Sample 100 keys to estimate distribution
    sample_keys = []
    cursor = 0
    for _ in range(10):  # 10 batches × 10 keys = 100 sample
        cursor, keys = await redis.scan(cursor, count=10)
        sample_keys.extend(keys)
        if cursor == 0:
            break

    # Count prefixes in sample
    prefix_counts = {}
    for key in sample_keys:
        prefix = key.split(b":")[0].decode()
        prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1

    # Extrapolate to total
    breakdown = {}
    for prefix, count in prefix_counts.items():
        ratio = count / len(sample_keys)
        breakdown[prefix] = {
            "count": int(total_keys * ratio),  # Estimated
            "memory_mb": 0,  # Not available
        }

    return breakdown
```

**Performance**:
- INFO command: ~1ms ⚡
- Sample 100 keys: ~10ms ⚡
- **Total: ~11ms** (100x faster que SCAN complet)

**Avantages**:
- ⚡ Très rapide (11ms vs 1000ms)
- ✅ Acceptable pour dashboard temps réel

**Inconvénients**:
- ❌ Approximatif (sample de 100 keys)
- ❌ Pas de memory usage détaillé
- ❌ Moins précis si distribution inégale

---

#### Décision Architecture: **Hybrid Approach** 🎯

**Strategy**:
1. **Dashboard temps réel** (auto-refresh 10s):
   - Utiliser **Méthode 2 (Estimation)** ⚡
   - Rapide, acceptable pour monitoring live

2. **Detailed Analysis** (bouton "Analyze"):
   - Utiliser **Méthode 1 (SCAN complet)** ✅
   - Précis, pour diagnostic approfondi
   - Cache résultat 5 minutes

**UI Toggle**:
```html
<button onclick="fetchRedisBreakdown('fast')">Quick View (10ms)</button>
<button onclick="fetchRedisBreakdown('detailed')">Detailed Scan (1s)</button>
```

---

### Hit Rate Par Type: Challenge 🔴

**Problème**: Redis ne track pas hits/misses **par key prefix**

Redis INFO donne seulement:
```
keyspace_hits: 1000
keyspace_misses: 200
```

**Impossible de savoir**:
- Hit rate de `search:*` vs `embedding:*`
- Quel cache type est le plus efficace

#### Solution 1: Application-Level Tracking ✅ **RECOMMANDÉ**

**Concept**: Track hits/misses dans MetricsMiddleware

```python
# In MetricsMiddleware
async def dispatch(self, request, call_next):
    # ... existing code ...

    # If cache was checked
    cache_key = request.state.cache_key if hasattr(request.state, "cache_key") else None
    cache_hit = request.state.cache_hit if hasattr(request.state, "cache_hit") else None

    if cache_key:
        # Determine cache type
        cache_type = cache_key.split(":")[0]  # "search", "embedding", etc.

        # Record metric
        await self._record_cache_metric(
            cache_type=cache_type,
            cache_hit=cache_hit  # True/False
        )
```

**Store in `metrics` table**:
```sql
INSERT INTO metrics (metric_type, metric_name, value, metadata)
VALUES (
    'cache',
    'hit',  -- or 'miss'
    1,
    jsonb_build_object('cache_type', 'search_results')
);
```

**Aggregate hit rate**:
```sql
SELECT
    metadata->>'cache_type' as cache_type,
    COUNT(*) FILTER (WHERE metric_name = 'hit') as hits,
    COUNT(*) FILTER (WHERE metric_name = 'miss') as misses,
    (COUNT(*) FILTER (WHERE metric_name = 'hit')::float /
     COUNT(*)::float * 100) as hit_rate
FROM metrics
WHERE metric_type = 'cache'
  AND timestamp > NOW() - INTERVAL '1 hour'
GROUP BY metadata->>'cache_type';
```

**Avantages**:
- ✅ Précis (track au niveau application)
- ✅ Historique (dans table `metrics`)
- ✅ Par cache type
- ✅ Peut calculer P50/P95 hit rate

**Inconvénients**:
- ⚠️ Overhead: +1 INSERT par requête
- ⚠️ Besoin modifier code search services

---

#### Solution 2: Redis MONITOR (Not Recommended) ❌

**Concept**: Parser Redis MONITOR logs

```bash
redis-cli MONITOR
> GET search:abc123  # Hit or miss?
```

**Problème**:
- ❌ MONITOR est **bloquant** (freeze Redis)
- ❌ Production-unsafe
- ❌ Parsing complexe

**Verdict**: ❌ Ne pas utiliser

---

## 📊 API Design

### Endpoint 1: Quick Breakdown (Fast) ⚡

**GET /api/monitoring/redis/breakdown?mode=fast**

```json
{
  "mode": "fast",
  "scan_duration_ms": 11,
  "total_keys": 536,
  "breakdown": {
    "search_results": {
      "keys_count": 342,
      "percentage": 63.8,
      "estimated": true
    },
    "embeddings": {
      "keys_count": 105,
      "percentage": 19.6,
      "estimated": true
    },
    "graph_traversal": {
      "keys_count": 89,
      "percentage": 16.6,
      "estimated": true
    }
  }
}
```

**Performance**: ~11ms ⚡

---

### Endpoint 2: Detailed Breakdown (Accurate) ✅

**GET /api/monitoring/redis/breakdown?mode=detailed**

```json
{
  "mode": "detailed",
  "scan_duration_ms": 1023,
  "total_keys": 536,
  "breakdown": {
    "search_results": {
      "keys_count": 342,
      "memory_mb": 120.5,
      "percentage_memory": 49.2,
      "avg_ttl_seconds": 1800,
      "hit_rate": 92.1  // From metrics table
    },
    "embeddings": {
      "keys_count": 105,
      "memory_mb": 89.2,
      "percentage_memory": 36.4,
      "avg_ttl_seconds": 3600,
      "hit_rate": 78.3
    },
    "graph_traversal": {
      "keys_count": 89,
      "memory_mb": 35.3,
      "percentage_memory": 14.4,
      "avg_ttl_seconds": 900,
      "hit_rate": 95.7
    }
  },
  "top_keys": [
    {
      "key": "search:a3f2b9c1d4e5f6a7b8c9d0e1f2a3b4c5",
      "type": "search_results",
      "memory_kb": 1024,
      "ttl_seconds": 1500
    },
    {
      "key": "embedding:b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9",
      "type": "embeddings",
      "memory_kb": 512,
      "ttl_seconds": 3200
    }
  ],
  "cached_until": "2025-10-24T10:35:00Z"  // Cache 5min
}
```

**Performance**: ~1s (first call), then cached 5min

---

### Endpoint 3: Cache Hit Rate by Type

**GET /api/monitoring/redis/hit-rate?period=1h**

```json
{
  "period_hours": 1,
  "global": {
    "hit_rate": 87.3,
    "hits": 1000,
    "misses": 145
  },
  "by_type": {
    "search_results": {
      "hit_rate": 92.1,
      "hits": 650,
      "misses": 56
    },
    "embeddings": {
      "hit_rate": 78.3,
      "hits": 200,
      "misses": 55
    },
    "graph_traversal": {
      "hit_rate": 95.7,
      "hits": 150,
      "misses": 7
    }
  }
}
```

**Source**: Aggregation depuis `metrics` table

**Query**:
```sql
SELECT
    metadata->>'cache_type' as cache_type,
    COUNT(*) FILTER (WHERE metric_name = 'hit') as hits,
    COUNT(*) FILTER (WHERE metric_name = 'miss') as misses,
    (COUNT(*) FILTER (WHERE metric_name = 'hit')::float /
     COUNT(*)::float * 100) as hit_rate
FROM metrics
WHERE metric_type = 'cache'
  AND timestamp > NOW() - INTERVAL '1 hour'
GROUP BY metadata->>'cache_type';
```

---

## 🎨 UI/UX Design

### Dashboard Layout

```
┌────────────────────────────────────────────────────────────────┐
│ 🔴 Redis Breakdown                        [Quick View] [Deep Scan] │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│ Global Metrics:                                                │
│ ├─ Total Keys: 536                                            │
│ ├─ Memory: 245 MB / 2048 MB (12%)                             │
│ ├─ Hit Rate: 87.3% (1000 hits / 145 misses)                   │
│ └─ Evictions: 23 (last 1h)                                    │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│ Breakdown by Cache Type:                                       │
│                                                                │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ 📊 Search Results (342 keys, 120.5 MB, 49.2%)           │ │
│ │ ├─ Hit Rate: 92.1% ✅                                    │ │
│ │ ├─ Avg TTL: 1800s (30min)                               │ │
│ │ └─ Memory: [████████████░░░░░░░░] 120.5 / 245 MB        │ │
│ └──────────────────────────────────────────────────────────┘ │
│                                                                │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ 🧠 Embeddings (105 keys, 89.2 MB, 36.4%)                │ │
│ │ ├─ Hit Rate: 78.3% 🟡                                    │ │
│ │ ├─ Avg TTL: 3600s (1h)                                  │ │
│ │ └─ Memory: [████████░░░░░░░░░░░] 89.2 / 245 MB          │ │
│ └──────────────────────────────────────────────────────────┘ │
│                                                                │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ 🔗 Graph Traversal (89 keys, 35.3 MB, 14.4%)            │ │
│ │ ├─ Hit Rate: 95.7% ✅                                    │ │
│ │ ├─ Avg TTL: 900s (15min)                                │ │
│ │ └─ Memory: [███░░░░░░░░░░░░░░░░] 35.3 / 245 MB          │ │
│ └──────────────────────────────────────────────────────────┘ │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│ Top 5 Largest Keys:                                            │
│ 1. search:a3f2b9c1... (1.0 MB, TTL: 1500s)                    │
│ 2. embedding:b4c5d6... (512 KB, TTL: 3200s)                   │
│ 3. graph:123e4567... (256 KB, TTL: 800s)                      │
│ 4. chunks:src/main.py... (128 KB, TTL: 2400s)                 │
│ 5. search:d8e9f0a1... (96 KB, TTL: 1200s)                     │
│                                                                │
│ [View Full Keys List →]                                        │
└────────────────────────────────────────────────────────────────┘
```

### ECharts Visualization

**Chart 1: Memory Distribution (Pie Chart)**
```javascript
{
  type: 'pie',
  radius: ['40%', '70%'],
  data: [
    { value: 120.5, name: 'Search Results (49%)' },
    { value: 89.2, name: 'Embeddings (36%)' },
    { value: 35.3, name: 'Graph (14%)' }
  ]
}
```

**Chart 2: Hit Rate Comparison (Bar Chart)**
```javascript
{
  xAxis: { data: ['Search', 'Embeddings', 'Graph'] },
  yAxis: { max: 100 },
  series: [{
    type: 'bar',
    data: [92.1, 78.3, 95.7],
    itemStyle: {
      color: (params) => params.value > 90 ? '#3fb950' : params.value > 70 ? '#d29922' : '#f85149'
    }
  }]
}
```

**Chart 3: Keys Count (Horizontal Bar)**
```javascript
{
  yAxis: { data: ['Graph', 'Embeddings', 'Search'] },
  series: [{
    type: 'bar',
    data: [89, 105, 342]
  }]
}
```

---

## 🔧 Implémentation

### Task 1: RedisAnalyzer Service

**File**: `api/services/redis_analyzer.py`

```python
"""
EPIC-22 Story 22.4: Redis Breakdown Analyzer

Analyzes Redis keys by type (search, embeddings, graph, etc.)
"""

import asyncio
import structlog
from typing import Dict, List, Any, Literal
from datetime import datetime, timedelta
import redis.asyncio as aioredis

logger = structlog.get_logger()


class RedisAnalyzer:
    """Analyzes Redis cache breakdown by type."""

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self._detailed_cache = None
        self._cache_timestamp = None
        self._cache_ttl = timedelta(minutes=5)

    async def get_breakdown(
        self,
        mode: Literal["fast", "detailed"] = "fast"
    ) -> Dict[str, Any]:
        """
        Get Redis breakdown by cache type.

        Args:
            mode: "fast" (sampling, ~10ms) or "detailed" (full scan, ~1s)

        Returns:
            {
              "mode": "fast" | "detailed",
              "scan_duration_ms": 11,
              "total_keys": 536,
              "breakdown": {...},
              "top_keys": [...]  # Only in detailed mode
            }
        """
        if mode == "fast":
            return await self._fast_breakdown()
        else:
            return await self._detailed_breakdown()

    async def _fast_breakdown(self) -> Dict[str, Any]:
        """
        Fast breakdown using sampling (100 keys).

        Performance: ~10ms
        """
        start = asyncio.get_event_loop().time()

        # Get total keys from INFO
        info = await self.redis.info("keyspace")
        total_keys = info.get("db0", {}).get("keys", 0)

        # Sample 100 keys
        sample_keys = []
        cursor = 0
        for _ in range(10):
            cursor, keys = await self.redis.scan(cursor, count=10)
            sample_keys.extend(keys)
            if cursor == 0 or len(sample_keys) >= 100:
                break

        # Count by prefix
        prefix_counts = {}
        for key in sample_keys:
            key_str = key.decode() if isinstance(key, bytes) else key
            prefix = self._get_cache_type(key_str)
            prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1

        # Extrapolate to total
        breakdown = {}
        for prefix, count in prefix_counts.items():
            ratio = count / len(sample_keys) if sample_keys else 0
            breakdown[prefix] = {
                "keys_count": int(total_keys * ratio),
                "percentage": round(ratio * 100, 1),
                "estimated": True
            }

        duration_ms = (asyncio.get_event_loop().time() - start) * 1000

        return {
            "mode": "fast",
            "scan_duration_ms": round(duration_ms, 1),
            "total_keys": total_keys,
            "breakdown": breakdown
        }

    async def _detailed_breakdown(self) -> Dict[str, Any]:
        """
        Detailed breakdown using full SCAN.

        Performance: ~1s for 10k keys
        Cached: 5 minutes
        """
        # Check cache
        if self._detailed_cache and self._cache_timestamp:
            if datetime.now() - self._cache_timestamp < self._cache_ttl:
                logger.info("Returning cached detailed breakdown")
                return self._detailed_cache

        start = asyncio.get_event_loop().time()

        # Initialize stats
        stats = {
            "search_results": {"count": 0, "memory_bytes": 0, "ttls": []},
            "embeddings": {"count": 0, "memory_bytes": 0, "ttls": []},
            "graph_traversal": {"count": 0, "memory_bytes": 0, "ttls": []},
            "chunks": {"count": 0, "memory_bytes": 0, "ttls": []},
            "repo_meta": {"count": 0, "memory_bytes": 0, "ttls": []},
            "other": {"count": 0, "memory_bytes": 0, "ttls": []},
        }

        all_keys_with_details = []

        # SCAN all keys
        cursor = 0
        while True:
            cursor, keys = await self.redis.scan(cursor, count=100)

            # Process batch
            for key in keys:
                key_str = key.decode() if isinstance(key, bytes) else key
                cache_type = self._get_cache_type(key_str)

                # Get memory usage (MEMORY USAGE command)
                try:
                    memory_bytes = await self.redis.memory_usage(key) or 0
                except:
                    memory_bytes = 0  # Fallback if command not supported

                # Get TTL
                ttl = await self.redis.ttl(key)

                # Accumulate stats
                stats[cache_type]["count"] += 1
                stats[cache_type]["memory_bytes"] += memory_bytes
                if ttl > 0:
                    stats[cache_type]["ttls"].append(ttl)

                # Track for top keys
                all_keys_with_details.append({
                    "key": key_str[:50],  # Truncate long keys
                    "type": cache_type,
                    "memory_kb": memory_bytes / 1024,
                    "ttl_seconds": ttl if ttl > 0 else None
                })

            if cursor == 0:
                break

        # Calculate totals
        total_keys = sum(s["count"] for s in stats.values())
        total_memory_bytes = sum(s["memory_bytes"] for s in stats.values())

        # Build breakdown
        breakdown = {}
        for cache_type, data in stats.items():
            if data["count"] == 0:
                continue

            breakdown[cache_type] = {
                "keys_count": data["count"],
                "memory_mb": round(data["memory_bytes"] / (1024 * 1024), 2),
                "percentage_memory": round(data["memory_bytes"] / total_memory_bytes * 100, 1) if total_memory_bytes > 0 else 0,
                "avg_ttl_seconds": round(sum(data["ttls"]) / len(data["ttls"])) if data["ttls"] else None,
            }

        # Top 10 largest keys
        top_keys = sorted(
            all_keys_with_details,
            key=lambda x: x["memory_kb"],
            reverse=True
        )[:10]

        duration_ms = (asyncio.get_event_loop().time() - start) * 1000

        result = {
            "mode": "detailed",
            "scan_duration_ms": round(duration_ms, 1),
            "total_keys": total_keys,
            "breakdown": breakdown,
            "top_keys": top_keys,
            "cached_until": (datetime.now() + self._cache_ttl).isoformat()
        }

        # Cache result
        self._detailed_cache = result
        self._cache_timestamp = datetime.now()

        return result

    def _get_cache_type(self, key: str) -> str:
        """Determine cache type from key prefix."""
        if key.startswith("search:"):
            return "search_results"
        elif key.startswith("graph:"):
            return "graph_traversal"
        elif key.startswith("embedding:"):
            return "embeddings"
        elif key.startswith("chunks:"):
            return "chunks"
        elif key.startswith("repo:"):
            return "repo_meta"
        else:
            return "other"
```

---

### Task 2: Cache Hit Rate Tracking (Application-Level)

**Modify existing search services to track cache hits/misses**

**Example**: `api/services/vector_search_service.py`

```python
async def search(self, query: str, limit: int = 10):
    # Generate cache key
    cache_key = cache_keys.search_result_key(query, limit=limit)

    # Try cache
    cached = await self.redis.get(cache_key)

    # Track hit/miss
    request.state.cache_key = cache_key
    request.state.cache_hit = cached is not None

    if cached:
        return json.loads(cached)

    # Cache miss, execute search
    results = await self._execute_search(query, limit)

    # Store in cache
    await self.redis.setex(cache_key, 1800, json.dumps(results))

    return results
```

**In MetricsMiddleware**:
```python
async def dispatch(self, request, call_next):
    # ... existing code ...

    response = await call_next(request)

    # Track cache metrics
    if hasattr(request.state, "cache_key"):
        cache_type = request.state.cache_key.split(":")[0]
        cache_hit = request.state.cache_hit

        await self._record_cache_metric(
            cache_type=cache_type,
            cache_hit=cache_hit
        )

    return response

async def _record_cache_metric(self, cache_type: str, cache_hit: bool):
    """Record cache hit/miss metric."""
    async with self.engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO metrics (metric_type, metric_name, value, metadata)
            VALUES (
                'cache',
                :metric_name,
                1,
                jsonb_build_object('cache_type', :cache_type)
            )
        """), {
            "metric_name": "hit" if cache_hit else "miss",
            "cache_type": cache_type
        })
```

---

### Task 3: API Routes

**File**: `api/routes/monitoring_routes_advanced.py` (extend existing)

```python
from services.redis_analyzer import RedisAnalyzer

@router.get("/redis/breakdown")
async def get_redis_breakdown(
    mode: Literal["fast", "detailed"] = "fast",
    analyzer: RedisAnalyzer = Depends(get_redis_analyzer)
):
    """
    Get Redis breakdown by cache type.

    Query params:
    - mode: "fast" (sampling, ~10ms) or "detailed" (full scan, ~1s)

    Returns breakdown + top keys (if detailed)
    """
    return await analyzer.get_breakdown(mode=mode)


@router.get("/redis/hit-rate")
async def get_cache_hit_rate(
    period_hours: int = 1,
    db_engine: AsyncEngine = Depends(get_db_engine)
):
    """
    Get cache hit rate by type from metrics table.

    Query params:
    - period_hours: 1, 24, 168 (1h, 1d, 1w)
    """
    async with db_engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT
                metadata->>'cache_type' as cache_type,
                COUNT(*) FILTER (WHERE metric_name = 'hit') as hits,
                COUNT(*) FILTER (WHERE metric_name = 'miss') as misses,
                (COUNT(*) FILTER (WHERE metric_name = 'hit')::float /
                 NULLIF(COUNT(*)::float, 0) * 100) as hit_rate
            FROM metrics
            WHERE metric_type = 'cache'
              AND timestamp > NOW() - INTERVAL :period
            GROUP BY metadata->>'cache_type'
        """), {"period": f"{period_hours} hours"})

        rows = result.mappings().all()

        # Build response
        by_type = {}
        total_hits = 0
        total_misses = 0

        for row in rows:
            cache_type = row["cache_type"]
            hits = row["hits"] or 0
            misses = row["misses"] or 0

            by_type[cache_type] = {
                "hit_rate": round(row["hit_rate"] or 0, 2),
                "hits": hits,
                "misses": misses
            }

            total_hits += hits
            total_misses += misses

        global_hit_rate = (total_hits / (total_hits + total_misses) * 100) if (total_hits + total_misses) > 0 else 0

        return {
            "period_hours": period_hours,
            "global": {
                "hit_rate": round(global_hit_rate, 2),
                "hits": total_hits,
                "misses": total_misses
            },
            "by_type": by_type
        }
```

---

## ⚠️ Gotchas & Pitfalls

### 1. SCAN Performance on Large Keysets

**Problem**: 1M keys → SCAN takes 100+ seconds

**Solution**: Use `mode=fast` for dashboard, cache `mode=detailed` for 5min

---

### 2. MEMORY USAGE Command Not Available (Redis < 4.0)

**Problem**: `MEMORY USAGE` requires Redis 4.0+

**Fallback**:
```python
try:
    memory_bytes = await redis.memory_usage(key)
except redis.exceptions.ResponseError:
    # Fallback: estimate based on string length
    value = await redis.get(key)
    memory_bytes = len(value) if value else 0
```

---

### 3. Application-Level Cache Tracking Overhead

**Problem**: +1 INSERT per request

**Mitigation**: Batch inserts (accumulate 100 metrics, flush)

**Alternative**: Sample 10% of requests
```python
if random.random() < 0.1:  # 10% sampling
    await self._record_cache_metric(...)
```

---

### 4. Cache Type Detection Ambiguity

**Problem**: Key `user:123` doesn't match known prefixes → classified as "other"

**Solution**: Add fallback category "unknown" + log warning

---

### 5. TTL = -1 (No Expiration)

**Problem**: Some keys have no TTL → skews avg_ttl calculation

**Solution**:
```python
if ttl > 0:
    stats[cache_type]["ttls"].append(ttl)
# Ignore ttl == -1 (no expire) and ttl == -2 (key not found)
```

---

## 📈 Success Metrics

### Acceptance Criteria
- [x] Endpoint `/api/monitoring/redis/breakdown?mode=fast` < 50ms
- [x] Endpoint `/api/monitoring/redis/breakdown?mode=detailed` < 2s
- [x] Breakdown par type (search, embeddings, graph, chunks)
- [x] Memory usage par type
- [x] Hit rate par type (depuis metrics table)
- [x] Top 10 largest keys
- [x] Avg TTL par type
- [x] UI cards avec breakdown visuel

### Performance Targets
- Fast mode: < 50ms ⚡
- Detailed mode: < 2s ✅
- Detailed cached: 5 minutes
- Cache hit tracking overhead: < 2ms/request

---

## 🎯 Timeline

| Task | Estimation | Priority |
|------|-----------|----------|
| 1. RedisAnalyzer service | 3h | P0 |
| 2. Cache hit/miss tracking | 2h | P0 |
| 3. API routes | 1h | P0 |
| 4. UI cards breakdown | 2h | P0 |
| 5. ECharts visualizations | 2h | P1 |
| 6. Tests | 2h | P1 |
| **Total** | **12h** | **1.5 jours** |

**Story Points**: 2 pts (estimé correctement ✅)

---

## 🔗 Dependencies

**Requires** (Story 22.1 ✅):
- Table `metrics` exists
- MetricsMiddleware recording infrastructure

**Enables** (Future):
- Story 22.5: API perf par endpoint (peut utiliser cache metrics)
- Story 22.7: Smart alerting (alert si hit rate < 70% par type)

---

**Créé**: 2025-10-24
**Auteur**: Claude Code
**Status**: 🧠 Ready to implement
**Next**: Get approval → Start implementation
