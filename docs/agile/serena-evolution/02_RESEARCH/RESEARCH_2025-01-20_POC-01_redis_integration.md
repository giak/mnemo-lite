# POC #1: Redis Integration - Deep Analysis

---
type: RESEARCH
status: active
created: 2025-01-20
updated: 2025-01-20
lifecycle: temporary
supersedes: []
superseded_by: null
related:
  - 01_ARCHITECTURE_DECISIONS/ADR-001_cache_strategy.md
  - 03_EPICS/EPIC-10_PERFORMANCE_CACHING.md
contributors: [Human, Claude]
feeds_into: ADR-001_cache_strategy.md
---

**Version**: 1.0
**Date**: 2025-01-20
**Purpose**: Ultra-deep brainstorm on POC #1 to validate Redis integration hypotheses before implementation
**Status**: 🟡 Active Research
**Timeline**: 4 heures (estimation)

---

## 📋 Executive Summary

**Problème**: ADR-001 recommande Redis Standard pour L2 cache, mais **ZERO validation pratique** existe.

**Hypothèses non validées**:
- Redis 7.x compatible avec `redis.asyncio` (Python async client)
- Pub/Sub propagation <100ms pour multi-instance cache invalidation
- Latency <5ms pour get/set operations
- Connection pooling stable sous charge (100 req/s)
- Graceful degradation si Redis down (fallback PostgreSQL)

**Objectif POC**: Valider ces 5 hypothèses avec **code exécutable + métriques mesurées**.

**Risque si skip POC**: Découvrir incompatibilités/limitations en production → rollback coûteux.

---

## 🎯 Objectifs du POC

### Objectif Principal
**Valider que Redis 7.x peut servir de L2 cache avec les caractéristiques promises dans ADR-001**.

### Objectifs Secondaires
1. **Performance**: Mesurer latency réelle (get/set/delete) vs 5ms target
2. **Multi-instance**: Valider Pub/Sub invalidation <100ms
3. **Resilience**: Tester graceful degradation (Redis down → PostgreSQL)
4. **Scalability**: Connection pool stable à 100 req/s
5. **Integration**: Async Python client compatible avec FastAPI lifecycle

### Non-Objectifs (Hors Scope)
- ❌ Redis Cluster (1 node suffit pour 1-3 API instances)
- ❌ Redis Sentinel (overkill pour scale actuelle)
- ❌ Persistence tuning (RDB/AOF defaults OK)
- ❌ Memory eviction policies (LRU default OK)

---

## 🔬 Contexte et Décisions à Informer

### ADR-001: Cache Strategy
**Décision actuelle**: Redis Standard (15 ans, pérenne) > Dragonfly (3 ans, 25× plus rapide)

**Points à valider**:
- ✅ Redis Standard latency acceptable (<5ms) → sinon, reconsidérer Dragonfly
- ✅ Async client stable → sinon, sync client + threadpool
- ✅ Pub/Sub fiable → sinon, polling alternative
- ✅ Graceful degradation → sinon, risk d'outage total

**Impact si POC échoue**:
- Dragonfly devient option #1 (performance > pérennité si Redis trop lent)
- Ou fallback sync client (impact: blocking I/O dans async app)

### EPIC-10: Performance Caching
**Claim actuel**: Triple-layer cache → 65ms/file re-indexing (100× faster)

**Gaps identifiés**:
1. **Baseline manquante**: Aucun benchmark v2.0 documenté → claim "100×" non prouvable
2. **Embedding cache unclear**: EPIC-10 cache `code_chunks` mais pas embeddings → 80% du temps d'indexing non optimisé?
3. **Graph construction non caché**: Seul traversal caché → construction répétée inutilement

**Ce POC doit valider**:
- Redis latency permet bien 100× gain (vs PostgreSQL cold)
- Connection pooling supporte load (sinon, bottleneck)

---

## 🧪 Test Scenarios (Comprehensive)

### Scenario 1: Basic Operations
**Objectif**: Valider Redis 7.x + `redis.asyncio` fonctionnent ensemble.

**Tests**:
1. **Set/Get/Delete**:
   ```python
   await redis.set("key", "value", ex=60)  # TTL 60s
   result = await redis.get("key")
   await redis.delete("key")
   ```
   - **Success**: Operations réussissent sans exception
   - **Metric**: Latency <5ms par opération

2. **TTL expiration**:
   ```python
   await redis.set("key", "value", ex=1)  # 1 second TTL
   await asyncio.sleep(1.5)
   result = await redis.get("key")  # Should be None
   ```
   - **Success**: Key expire automatiquement après TTL
   - **Metric**: Expiration précise (±100ms)

3. **JSON serialization**:
   ```python
   data = {"code_chunk": {"id": "...", "embedding": [0.1, 0.2, ...]}}
   await redis.set("chunk:123", json.dumps(data))
   retrieved = json.loads(await redis.get("chunk:123"))
   ```
   - **Success**: Round-trip serialization sans perte
   - **Metric**: Serialization overhead <1ms

### Scenario 2: Pub/Sub Multi-Instance Invalidation
**Objectif**: Valider cache invalidation propagation entre 3 instances API.

**Setup**:
- 3 async Redis clients (simulent 3 API instances)
- Chaque client subscribe to `cache:invalidate` channel
- Client 1 publie invalidation message → Clients 2 & 3 reçoivent

**Tests**:
1. **Basic Pub/Sub**:
   ```python
   # Instance 1: Publisher
   await redis1.publish("cache:invalidate", json.dumps({"key": "chunk:123"}))

   # Instances 2 & 3: Subscribers
   async for message in pubsub2.listen():
       if message['type'] == 'message':
           # Invalidate local cache
   ```
   - **Success**: Messages reçus par 100% subscribers
   - **Metric**: Propagation time <100ms (P99)

2. **High-frequency invalidation**:
   - Publier 100 invalidations/seconde
   - Vérifier aucun message perdu
   - **Success**: 0% message loss
   - **Metric**: Latency stable même sous charge

3. **Subscriber reconnection**:
   - Kill subscriber connection
   - Reconnect automatiquement
   - **Success**: Reconnection <1s
   - **Metric**: Aucun message perdu pendant reconnection

### Scenario 3: Connection Pooling Under Load
**Objectif**: Valider connection pool stable à 100 req/s.

**Setup**:
- Connection pool: 10 connections (default)
- Simuler 100 req/s pendant 60 secondes
- Mesurer: latency, connection reuse, errors

**Tests**:
1. **Sustained load**:
   ```python
   async def simulate_request():
       await redis.get(f"key:{random.randint(1, 1000)}")

   # 100 req/s for 60s = 6000 requests
   await asyncio.gather(*[simulate_request() for _ in range(6000)])
   ```
   - **Success**: 0 connection errors
   - **Metric**: P50 <5ms, P99 <20ms

2. **Connection exhaustion**:
   - Pool size = 5 connections
   - Simuler 20 concurrent requests (4× pool size)
   - **Success**: Graceful queueing (no crash)
   - **Metric**: Max wait time <50ms

3. **Connection recovery**:
   - Restart Redis mid-test
   - **Success**: Auto-reconnect <2s
   - **Metric**: <1% failed requests

### Scenario 4: Graceful Degradation
**Objectif**: Valider fallback PostgreSQL si Redis down.

**Tests**:
1. **Redis unavailable at startup**:
   ```python
   try:
       redis = await create_redis_pool(...)
   except ConnectionError:
       logger.warning("Redis unavailable, using PostgreSQL only")
       redis = None
   ```
   - **Success**: API démarre quand même
   - **Metric**: Startup time <5s

2. **Redis failure during runtime**:
   - API running with Redis
   - Stop Redis container
   - **Success**: API continue (PostgreSQL fallback)
   - **Metric**: No 500 errors, latency degradation acceptable (<500ms)

3. **Redis recovery during runtime**:
   - Redis redémarre
   - **Success**: API reconnect automatiquement
   - **Metric**: Cache hit rate revient à 80%+ dans 5 minutes

### Scenario 5: Memory and Eviction
**Objectif**: Valider behavior quand Redis atteint maxmemory.

**Tests**:
1. **LRU eviction**:
   - Set maxmemory = 100MB
   - Fill avec 150MB de data
   - **Success**: Least Recently Used keys évincées
   - **Metric**: No OOM errors

2. **Eviction policy verification**:
   ```python
   info = await redis.info("memory")
   assert info['maxmemory_policy'] == 'allkeys-lru'
   ```
   - **Success**: Policy = allkeys-lru (pas noeviction)

---

## ✅ Success Criteria (Measurable)

### Performance Criteria
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| **Get latency (P50)** | <5ms | `time.perf_counter()` over 1000 ops |
| **Get latency (P99)** | <20ms | 99th percentile of latencies |
| **Set latency (P50)** | <5ms | Same as get |
| **Pub/Sub propagation (P99)** | <100ms | Timestamp diff publisher → subscriber |
| **Throughput** | 100 req/s sustained | 60s load test, 0 errors |
| **Connection pool stability** | 0 errors @ 100 req/s | Error count during load test |

### Functional Criteria
| Feature | Success Definition |
|---------|-------------------|
| **TTL expiration** | Keys expire within ±100ms of TTL |
| **JSON serialization** | Round-trip without data loss |
| **Pub/Sub delivery** | 100% message delivery to all subscribers |
| **Graceful degradation** | API functional when Redis down |
| **Auto-reconnect** | Reconnect <2s after Redis restart |

### Integration Criteria
| Aspect | Success Definition |
|--------|-------------------|
| **FastAPI lifecycle** | Redis pool created in `lifespan`, closed on shutdown |
| **Async compatibility** | No blocking I/O in async context |
| **Error handling** | No uncaught exceptions, graceful fallback |

---

## 🛠️ Implementation Approach

### Phase 1: Environment Setup (30 min)

**Docker Compose**:
```yaml
version: '3.8'
services:
  redis:
    image: redis:7.2-alpine
    ports:
      - "6379:6379"
    command: redis-server --maxmemory 100mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
```

**Python Dependencies**:
```bash
pip install redis[hiredis]==5.0.1  # Async client + faster parser
pip install pytest-asyncio pytest-benchmark
```

### Phase 2: Test Harness (1h)

**Structure**:
```
poc_redis/
├── docker-compose.yml
├── test_redis_integration.py  # All scenarios
├── metrics.py                  # Latency/throughput measurement
├── README.md                   # Results documentation
└── requirements.txt
```

**Core Test Utilities**:
```python
# metrics.py
import time
import statistics
from typing import List

class LatencyMetrics:
    def __init__(self):
        self.latencies: List[float] = []

    async def measure(self, coro):
        start = time.perf_counter()
        result = await coro
        elapsed = (time.perf_counter() - start) * 1000  # ms
        self.latencies.append(elapsed)
        return result

    def report(self):
        return {
            "p50": statistics.median(self.latencies),
            "p99": statistics.quantiles(self.latencies, n=100)[98],
            "mean": statistics.mean(self.latencies),
            "count": len(self.latencies)
        }
```

### Phase 3: Execute Scenarios (2h)

**Test Execution Order**:
1. ✅ Scenario 1: Basic Operations (validate setup works)
2. ✅ Scenario 3: Connection Pooling (validate scalability)
3. ✅ Scenario 2: Pub/Sub (validate multi-instance)
4. ✅ Scenario 4: Graceful Degradation (validate resilience)
5. ✅ Scenario 5: Memory/Eviction (validate resource limits)

**Metrics Collection**:
- JSON file: `results.json` with all latencies
- Markdown report: `RESULTS.md` (human-readable)
- Grafana dashboard (optional, si temps permet)

### Phase 4: Analysis & Decision (30 min)

**Decision Tree**:
```
All criteria met?
├─ YES → ✅ Proceed with Redis Standard implementation
├─ NO → Performance issues?
    ├─ YES → 🔄 Consider Dragonfly (tradeoff pérennité)
    ├─ NO → Stability issues?
        ├─ YES → 🔄 Consider sync client + threadpool
        └─ NO → 🔄 Consider alternative (Valkey, KeyDB)
```

---

## 🚨 Risks and Mitigations

### Risk 1: Redis 7.x incompatible avec redis.asyncio
**Probabilité**: Faible (redis-py 5.0+ stable)
**Impact**: Élevé (blocker pour async implementation)
**Mitigation**: Test basic operations first (Scenario 1), fallback sync client si nécessaire

### Risk 2: Pub/Sub latency >100ms
**Probabilité**: Moyenne (network latency variable)
**Impact**: Moyen (cache coherency delayed)
**Mitigation**:
- Augmenter timeout à 500ms (acceptable pour cache invalidation)
- Ou polling alternative (check Redis key version)

### Risk 3: Connection pool instable sous charge
**Probabilité**: Faible (redis-py mature)
**Impact**: Élevé (bottleneck performance)
**Mitigation**:
- Tune pool size (default 10 → 20 si nécessaire)
- Monitor connection reuse rate

### Risk 4: Graceful degradation échoue
**Probabilité**: Moyenne (error handling non trivial)
**Impact**: Critique (outage total si Redis down)
**Mitigation**:
- Implement circuit breaker pattern
- Fallback PostgreSQL doit être TOUJOURS testé

### Risk 5: Memory eviction trop agressive
**Probabilité**: Faible (100MB sufficient pour cache)
**Impact**: Moyen (cache hit rate diminue)
**Mitigation**:
- Monitor eviction rate
- Augmenter maxmemory si >10% eviction rate

---

## 📊 Expected Outcomes

### Scenario: Success (80% probability)
**Résultats attendus**:
- ✅ Get/Set latency: 2-4ms (P50), 8-15ms (P99)
- ✅ Pub/Sub propagation: 20-50ms (P99)
- ✅ Throughput: 100 req/s stable
- ✅ Graceful degradation: 0 errors when Redis down
- ✅ Auto-reconnect: <1s

**Décision**:
- ✅ **Proceed avec Redis Standard** (ADR-001 validé)
- ✅ Update ADR-001 avec métriques mesurées
- ✅ Move to POC #2 (LSP Pyright Query)

### Scenario: Partial Success (15% probability)
**Résultats possibles**:
- ⚠️ Latency: 8-12ms (P50) → Acceptable mais pas optimal
- ⚠️ Pub/Sub: 150-200ms (P99) → Lent mais fonctionnel

**Décision**:
- 🔄 **Benchmark Dragonfly** (POC #1b)
- 🔄 Si Dragonfly <2ms latency → Reconsider pérennité vs performance tradeoff
- 🔄 Document tradeoffs dans ADR-001

### Scenario: Failure (5% probability)
**Résultats possibles**:
- ❌ Connection errors sous charge
- ❌ Pub/Sub message loss >1%
- ❌ Graceful degradation échoue (500 errors)

**Décision**:
- 🔄 **Fallback sync client** + threadpool executor
- 🔄 Ou **Skip L2 cache** → Dual-layer (L1 memory + L3 PostgreSQL)
- 🔄 Update ADR-001 avec nouvelle recommandation

---

## 🔗 Decision Points

### Decision Point 1: Redis Standard vs Dragonfly
**Critère**: Latency <5ms (P50) avec Redis Standard?
- **YES** → Proceed avec Redis Standard (pérennité wins)
- **NO** → Benchmark Dragonfly (performance wins if <2ms)

### Decision Point 2: Async vs Sync Client
**Critère**: redis.asyncio stable à 100 req/s?
- **YES** → Use async client (native FastAPI integration)
- **NO** → Sync client + `asyncio.to_thread()` (perf hit acceptable)

### Decision Point 3: Pub/Sub vs Polling
**Critère**: Pub/Sub propagation <100ms (P99)?
- **YES** → Use Pub/Sub (optimal)
- **NO** → Polling alternative (check key version every 5s)

### Decision Point 4: Triple-Layer vs Dual-Layer
**Critère**: Graceful degradation works flawlessly?
- **YES** → Triple-layer (L1 + L2 + L3)
- **NO** → Dual-layer (L1 + L3, skip Redis)

---

## 📝 Documentation des Résultats

### Template: RESULTS.md
```markdown
# POC #1: Redis Integration - Results

**Date**: YYYY-MM-DD
**Duration**: Xh
**Redis Version**: 7.2
**Python Client**: redis==5.0.1

## Test Environment
- OS: Ubuntu 22.04 / Docker
- CPU: [spec]
- Memory: [spec]
- Network: localhost (loopback)

## Scenario 1: Basic Operations
| Operation | P50 | P99 | Mean | Count | Target | Status |
|-----------|-----|-----|------|-------|--------|--------|
| GET       | Xms | Xms | Xms  | 1000  | <5ms   | ✅/❌  |
| SET       | Xms | Xms | Xms  | 1000  | <5ms   | ✅/❌  |
| DELETE    | Xms | Xms | Xms  | 1000  | <5ms   | ✅/❌  |

## Scenario 2: Pub/Sub
| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Propagation (P99) | Xms | <100ms | ✅/❌ |
| Message Loss | X% | 0% | ✅/❌ |
| Reconnect Time | Xs | <1s | ✅/❌ |

## Scenario 3: Connection Pooling
| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Throughput | X req/s | 100 req/s | ✅/❌ |
| Errors | X | 0 | ✅/❌ |
| Latency (P99) | Xms | <20ms | ✅/❌ |

## Scenario 4: Graceful Degradation
| Test | Result | Status |
|------|--------|--------|
| Redis down @ startup | [description] | ✅/❌ |
| Redis down @ runtime | [description] | ✅/❌ |
| Redis recovery | [description] | ✅/❌ |

## Scenario 5: Memory/Eviction
| Test | Result | Status |
|------|--------|--------|
| LRU eviction | [description] | ✅/❌ |
| Eviction rate | X% | <10% | ✅/❌ |

## Decision
- [ ] ✅ Proceed avec Redis Standard
- [ ] 🔄 Benchmark Dragonfly
- [ ] 🔄 Fallback sync client
- [ ] ❌ Skip L2 cache

## Next Steps
1. [action]
2. [action]
```

---

## 🎯 Liens avec Autres POCs

### POC #2: LSP Pyright Query
**Dépendance**: Aucune (peut être parallèle)
**Insight attendu**: Si LSP workspace mode 2-5× faster → Réduit besoin cache?

### POC #3: Triple-Cache Benchmark
**Dépendance**: **BLOQUÉ par POC #1** (need Redis validated)
**Insight attendu**: Mesure gain réel L1+L2+L3 vs L1+L3 (validate 100× claim)

### POC #4: Embedding Cache Strategy
**Dépendance**: Partielle (Redis validated help, but not required)
**Insight attendu**: Si embeddings = 80% indexing time → L2 cache MUST include embeddings, pas juste chunks

---

## 📚 References

### Documentation
- Redis Python Client: https://redis-py.readthedocs.io/en/stable/
- Redis Pub/Sub: https://redis.io/docs/manual/pubsub/
- FastAPI Lifespan: https://fastapi.tiangolo.com/advanced/events/

### Code Examples
- ADR-001 (cache strategy): `01_ARCHITECTURE_DECISIONS/ADR-001_cache_strategy.md`
- EPIC-10 (implementation specs): `03_EPICS/EPIC-10_PERFORMANCE_CACHING.md`

### Related Issues
- Gap: Baseline benchmarks missing → POC #3 must establish
- Gap: Embedding cache unclear → POC #4 must clarify
- Gap: Dates obsolètes in MISSION_CONTROL → Update après POC #1

---

## 🚀 Action Plan

### Immediate Next Steps (Next 4 hours)
1. **Setup environment** (30 min)
   - `docker-compose up -d`
   - Create `poc_redis/` directory structure
   - Install dependencies

2. **Implement test harness** (1h)
   - `metrics.py` (latency measurement)
   - `test_redis_integration.py` (5 scenarios)
   - `conftest.py` (pytest fixtures)

3. **Execute scenarios** (2h)
   - Run all 5 scenarios sequentially
   - Collect metrics in `results.json`
   - Document observations

4. **Analysis & decision** (30 min)
   - Generate `RESULTS.md` report
   - Make go/no-go decision
   - Update ADR-001 if validated

### Deliverables
- [ ] `poc_redis/` directory with all code
- [ ] `RESULTS.md` with measured metrics
- [ ] Decision: Proceed / Benchmark alternatives / Fallback
- [ ] Updated ADR-001 (if proceed)

---

## 💡 Ultra-Thinking: Edge Cases & Deep Questions

### Edge Case 1: Clock Skew Between API Instances
**Scenario**: 3 API instances with clocks ±2s apart
**Impact**: TTL expiration inconsistent → cache coherency issues
**Test**: Set key with TTL=5s, verify expiration within ±500ms across instances
**Mitigation**: Use Redis server time for TTL, not client time

### Edge Case 2: Network Partition During Pub/Sub
**Scenario**: Subscriber loses connection for 10s, then reconnects
**Impact**: Missed invalidation messages → stale cache
**Test**: Disconnect subscriber, publish 10 invalidations, reconnect
**Mitigation**: Version-based cache validation (compare version on get)

### Edge Case 3: Thundering Herd on Cache Miss
**Scenario**: 100 concurrent requests miss cache → 100 PostgreSQL queries
**Impact**: Database overload
**Test**: Flush Redis, send 100 concurrent identical requests
**Mitigation**: Request coalescing (first request fetches, others wait)

### Edge Case 4: Embedding Size Exceeds Redis String Limit
**Scenario**: Embedding = 768 floats × 4 bytes = 3KB per chunk × 1000 chunks = 3MB per cache entry
**Impact**: Redis string limit = 512MB (OK), but network latency increases
**Test**: Store 100 chunks with embeddings, measure get latency
**Mitigation**: Compress embeddings (zlib) if latency >10ms

### Deep Question 1: Cache Warming Strategy
**Question**: Should we pre-warm Redis on API startup?
**Tradeoffs**:
- PRO: Immediate cache hit on first request
- CON: Startup time +10s, complexity
**POC Test**: Measure startup time with/without warming (100 chunks)
**Decision Criteria**: If startup <5s with warming → implement

### Deep Question 2: Cache Key Versioning
**Question**: Should cache keys include version (e.g., `v1:chunk:123`)?
**Tradeoffs**:
- PRO: Schema changes don't corrupt cache
- CON: Manual invalidation on version bump
**POC Test**: Not critical for POC, document for future
**Decision Criteria**: Implement if schema changes expected

### Deep Question 3: Redis Persistence (RDB vs AOF)
**Question**: Do we need persistence for cache?
**Tradeoffs**:
- NO persistence: Faster, cache is ephemeral (PostgreSQL = SSOT)
- RDB: Slower writes, cache survives restarts
- AOF: Slowest, maximum durability
**POC Test**: Measure write latency with RDB disabled vs enabled
**Decision Criteria**: If latency delta <1ms → enable RDB (convenience)

---

## 🧠 Meta-Reflection: What This POC Teaches Us

### About Our Process
1. **Documentation ≠ Validation**: ADR-001 était excellent sur papier, mais **ZERO validation pratique** → dangerous assumption
2. **Systematic Doubt works**: Ce POC existe parce que j'ai challengé l'ADR-001 → découvert gaps
3. **POCs prevent costly rollbacks**: 4h POC now >> 40h rollback later

### About Redis Integration
1. **Async client maturity**: redis-py 5.0+ devrait être stable, mais **must verify** (breaking changes historiques)
2. **Pub/Sub subtleties**: Message delivery guarantees non évidentes → edge cases critiques
3. **Graceful degradation complexity**: Fallback PostgreSQL simple en théorie, **edge cases nombreux**

### About Performance Claims
1. **"100× faster" claim dangereux**: Sans baseline v2.0 + benchmark L1+L2+L3, claim non prouvable
2. **Embedding cache gap**: Si embeddings pas cachés → 80% du gain potentiel perdu
3. **Redis latency ≠ end-to-end latency**: Redis 2ms doesn't mean API response 2ms (serialization, network, etc.)

---

**STATUS**: 🟢 Ready to Execute
**BLOQUÉ PAR**: Rien (can start immediately)
**BLOQUE**: POC #3 (Triple-Cache Benchmark)

**NEXT ACTION**: Create `poc_redis/` directory structure and begin implementation.
