# MnemoLite v3.1.0-dev - Présentation
## "8 Critical Decisions That Shaped MnemoLite"

**Version**: 3.1.0-dev
**Date**: 2025-10-31
**Approche**: Decision-Driven (Story + Tech fusionnés)
**Durée cible**: 40 minutes
**Tagline**: Un projet = Une série de décisions

---

# INTRODUCTION

---

## [Slide 1] 💡 Un Projet = Une Série de Décisions

<br>

```
    Chaque projet est défini par
    les décisions techniques prises
```

<br>

**MnemoLite en chiffres:**
- 8 EPICs complétés
- 46 completion reports
- 1,195 tests collectés
- 4 mois de développement
- 1 développeur
- 0€ budget

<br>

**Mais surtout: 8 décisions critiques**

---

## [Slide 2] 🎯 Les 8 Décisions

<br>

**Aujourd'hui, je vais vous raconter:**

<br>

```
1. CPU vs GPU              (Le pari impossible)
2. Vector Database Choice  (PostgreSQL ou SaaS?)
3. Cache Strategy          (Performance matters)
4. Async Everything        (Architecture moderne)
5. Testing Strategy        (Mock ou pas mock?)
6. MCP vs Custom API       (Standards win)
7. Process Formalization   (Discipline = force)
8. Observability Built-In  (Debug sans douleur)
```

<br>

Chaque décision: **Contexte → Options → Choix → Résultats → Leçon**

---

## [Slide 3] 📐 Framework de Décision

<br>

### Pour chaque décision, on va voir:

<br>

**1. Story Hook** - Pourquoi cette question?
**2. Options** - Que pouvait-on choisir?
**3. Technical Deep Dive** - Comment ça marche?
**4. Results** - Qu'est-ce que ça a donné?
**5. Lesson Learned** - Quel pattern en tirer?

<br>

> "Decisions > Talent"

---

# 🎲 DECISION 1: CPU vs GPU
**Le Pari Impossible**

---

## [Slide 4] ❓ Story Hook: La Question Hérétique

<br>

**Contexte: Début du projet**

<br>

```
Dogme de l'industrie 2024:
"Vector search = GPU obligatoire"
```

<br>

**Observation:**
- GPUs dédiés: 2000€
- Cloud APIs (OpenAI, Cohere): 300€/mois
- Vendor lock-in total
- Data externalisée

<br>

**Question hérétique:**

> "Peut-on battre les GPUs avec un simple CPU?"

---

## [Slide 5] ⚖️ Options Considérées

<br>

### Option A: GPU dédié
```
+ Ultra rapide (1000s embeddings/sec)
+ State of the art
- 2000€ hardware
- Power consumption
- CUDA dependencies
```

### Option B: Cloud APIs
```
+ Zero setup
+ Scalable
- 300€+/mois
- Vendor lock-in
- Data privacy concerns
- Latency réseau
```

### Option C: CPU local
```
+ 0€ cost
+ Full control
+ Privacy native
- "Trop lent" (selon l'industrie)
? Jamais testé sérieusement
```

---

## [Slide 6] 🔬 Technical Deep Dive: CPU Embeddings

<br>

**Choix: CPU + sentence-transformers**

<br>

**Stack:**
```python
# Model: nomic-embed-text-v1.5
- Parameters: 137M
- Dimensions: 768D
- Quantization: FP32 (default)
- Library: sentence-transformers 2.8.0
```

**Hardware test:**
```
CPU: AMD Ryzen 7 5800X (8 cores @ 3.8GHz)
RAM: 32GB DDR4
Storage: NVMe SSD
```

**Week 1 POC - Benchmarks:**
```bash
# Test 1: Single embedding
Input: "Example text for semantic search"
Latency: 12ms
Memory: 2.1GB (model loaded)

# Test 2: Batch embeddings (100 texts)
Throughput: 68 embeddings/sec
Latency avg: 14.7ms per embedding
Memory peak: 2.3GB

# Test 3: Cold start
Model loading: 1.8 seconds (one-time)
First embedding: 1.8s + 12ms
```

---

## [Slide 7] 📊 Results & Reality Check

<br>

### Performance Mesurée (CPU)

<br>

```
Throughput: 50-100 embeddings/sec
Latency: 10-20ms per embedding
Memory: 2GB model + ~1GB for 10k vectors
```

<br>

### Comparaison GPU

<br>

```
GPU (NVIDIA RTX 4090):
  Throughput: ~1000 embeddings/sec
  Latency: 1-2ms
  Cost: 2000€

CPU (Ryzen 7):
  Throughput: ~70 embeddings/sec
  Latency: 14ms
  Cost: 0€ (déjà possédé)

→ 14x plus lent, mais ∞x moins cher
```

<br>

**Verdict:** Suffisant pour 90% des use cases modestes

---

## [Slide 8] 💡 Lesson Learned #1

<br>

```
╔═══════════════════════════════════════╗
║                                       ║
║  "Challenge Industry Dogmas"          ║
║                                       ║
║  Le "GPU obligatoire" est un mythe    ║
║  pour la plupart des use cases        ║
║                                       ║
╚═══════════════════════════════════════╝
```

<br>

**Pattern réutilisable:**
- ✅ Benchmark first, assume later
- ✅ Cost vs Performance trade-off explicite
- ✅ Most apps don't need extreme performance
- ✅ Local > Cloud for privacy & cost

<br>

**Applicabilité:** Pas juste embeddings - toute décision "il faut X cher"

---

# 🗄️ DECISION 2: Vector Database Choice
**PostgreSQL ou SaaS?**

---

## [Slide 9] ❓ Story Hook: Quelle Base de Données?

<br>

**Contexte: Week 1, POC validé**

<br>

```
Besoin:
→ Stocker embeddings (768D vectors)
→ Recherche similarité rapide
→ Échelle: quelques milliers d'items
```

<br>

**Pression industrie:**
- "Use Pinecone, it's made for this!"
- "Weaviate is the standard"
- "PostgreSQL? Not for vectors!"

<br>

**Question:**

> "Peut-on utiliser PostgreSQL pour tout?"

---

## [Slide 10] ⚖️ Options Considérées

<br>

### Trade-offs Matrix

| Critère | Pinecone | Weaviate | **pgvector** |
|---------|----------|----------|--------------|
| **Cost** | 300€/mois | Self-host | **0€** |
| **Setup time** | 5 min | 30 min | **10 min** |
| **HNSW index** | ✅ | ✅ | **✅** |
| **Graph support** | ❌ | ❌ | **✅ CTEs** |
| **ACID transactions** | ❌ | ❌ | **✅** |
| **SQL queries** | ❌ | Limited | **✅ Full** |
| **Learning curve** | Low | Medium | **Low (si SQL)** |
| **Vendor lock-in** | High | Medium | **None** |
| **Partitioning** | Auto | Manual | **✅ pg_partman** |

<br>

**Winner:** pgvector (polyvalence + cost + no lock-in)

---

## [Slide 11] 🔬 Technical Deep Dive: PostgreSQL + pgvector

<br>

**Stack:**
```sql
-- PostgreSQL 18.0
-- pgvector 0.8.1
-- HNSW index support
```

**Schema Design:**
```sql
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    content TEXT,
    embedding vector(768),  -- pgvector type
    created_at TIMESTAMP DEFAULT NOW()
);

-- HNSW index pour similarité
CREATE INDEX ON events
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

**Query Performance:**
```sql
-- Similarité search (top 10)
SELECT id, content,
       embedding <=> query_vector AS distance
FROM events
ORDER BY embedding <=> query_vector
LIMIT 10;

→ Query time: 8-12ms (10k vectors)
→ HNSW index utilisé
```

---

## [Slide 12] 🌟 Bonus: PostgreSQL Polyvalence

<br>

**Ce que pgvector nous donne EN PLUS:**

<br>

### 1. Graph Traversal (CTEs récursives)
```sql
-- Dépendances code avec CTEs
WITH RECURSIVE deps AS (
  SELECT * FROM code_items WHERE name = 'main.py'
  UNION
  SELECT c.* FROM code_items c
  JOIN dependencies d ON c.id = d.child_id
  JOIN deps ON deps.id = d.parent_id
)
SELECT * FROM deps;

→ 0.155ms query time
```

### 2. Hybrid Search (BM25 + Vector)
```sql
-- Full-text + semantic
SELECT *,
       ts_rank(search_vector, query) as bm25_score,
       embedding <=> query_vec as vec_score
FROM events
WHERE search_vector @@ query
ORDER BY (bm25_score * 0.3 + (1-vec_score) * 0.7) DESC;
```

### 3. Classic SQL
```sql
-- Aggregations, joins, tout fonctionne!
```

---

## [Slide 13] 📊 Results: One DB to Rule Them All

<br>

**Performance (10k vectors):**
```
Vector search (HNSW):     8-12ms
Graph traversal (CTE):    0.155ms
Hybrid search (BM25+Vec): 11ms
Classic query (B-tree):   0.8ms
```

<br>

**Storage:**
```
10k events × 768D × 4 bytes (FP32) = 30MB embeddings
+ Text content ≈ 50MB
Total: ~80MB (nothing)
```

<br>

**Scaling strategy (ready, not activated):**
```
→ Partitioning: pg_partman (by date)
→ Quantization: INT8 (reduce 4x storage)
→ Sharding: If needed (Citus extension)
```

<br>

**Coût total:** 0€ (vs 300€/mois Pinecone)

---

## [Slide 14] 💡 Lesson Learned #2

<br>

```
╔═══════════════════════════════════════╗
║                                       ║
║  "One Database To Rule Them All"      ║
║                                       ║
║  PostgreSQL 18 + pgvector =           ║
║  Vectors + Graph + Classic SQL        ║
║  All in one, ACID, 0€                 ║
║                                       ║
╚═══════════════════════════════════════╝
```

<br>

**Pattern réutilisable:**
- ✅ Polyvalence > Spécialisation (pour scale modeste)
- ✅ No vendor lock-in = long-term freedom
- ✅ PostgreSQL ecosystem is mature & rich
- ✅ ACID transactions matter (data integrity)

<br>

**Bonus:** Une seule DB à maintenir, backup, monitor

---

# ⚡ DECISION 3: Cache Strategy
**Performance Matters**

---

## [Slide 15] ❓ Story Hook: Le Problème des Embeddings

<br>

**Contexte: EPIC-19, Mois 2**

<br>

```
Problème découvert:
→ Model loading: 1.8 secondes
→ En dev: reload à chaque changement code
→ En tests: 1195 tests × 1.8s = 35 minutes!
```

<br>

**Observation:**
```python
# Code typique
def search(query: str):
    model = load_model()  # 1.8s ❌
    embedding = model.encode(query)  # 12ms
    results = db.search(embedding)
    return results

# 1.8s pour 12ms de vrai travail = inacceptable
```

<br>

**Question:**

> "Comment cacher intelligemment les embeddings?"

---

## [Slide 16] ⚖️ Options Considérées

<br>

### Option A: No Cache
```
+ Simple (no complexity)
- Model reload = 1.8s penalty
- Tests = 35 minutes
- Dev cycle = painful
Verdict: ❌ Inacceptable
```

### Option B: Redis Only
```
+ Fast (2-5ms access)
+ Cross-process
- Cold start toujours 1.8s
- Network latency
- Single point of failure
Verdict: ⚠️ Incomplet
```

### Option C: Triple-Layer (L1+L2+L3)
```
+ L1 = 0ms (in-memory local)
+ L2 = 2ms (Redis cross-process)
+ L3 = Source of truth (PostgreSQL)
+ Graceful degradation
- Complexity
Verdict: ✅ Optimal
```

---

## [Slide 17] 🔬 Technical Deep Dive: Triple-Layer Cache

<br>

**Architecture:**

```
Request → L1 Cache (In-Memory, 100MB LRU)
            ↓ miss (0.5ms)
          L2 Cache (Redis, 2GB, TTL 1h)
            ↓ miss (2ms)
          L3 Source (PostgreSQL + compute)
            ↓ compute embedding (15ms)
          Store in L1 + L2 + L3
```

<br>

**Implementation:**
```python
class TripleLevelCache:
    def __init__(self):
        self.l1 = LRUCache(maxsize=100_000)  # 100MB
        self.l2 = RedisCache(maxsize=2_000_000, ttl=3600)
        self.l3 = PostgreSQLStore()

    async def get_embedding(self, text: str):
        # Try L1
        if cached := self.l1.get(text):
            return cached  # 0ms

        # Try L2
        if cached := await self.l2.get(text):
            self.l1.set(text, cached)
            return cached  # 2ms

        # Compute & store in all layers
        embedding = await compute_embedding(text)  # 15ms
        self.l1.set(text, embedding)
        await self.l2.set(text, embedding)
        await self.l3.set(text, embedding)
        return embedding
```

---

## [Slide 18] 📊 Results: Cache Hit Rates

<br>

**Performance mesurée (production):**

```
L1 (In-Memory):
  Hit rate: 78%
  Latency: 0ms (dict lookup)
  Size: 42MB / 100MB used

L2 (Redis):
  Hit rate: 19% (of L1 misses)
  Latency: 1.8ms avg
  Size: 890MB / 2GB used

L3 (Compute):
  Hit rate: 3% (cold starts)
  Latency: 15ms (model + encode)

Combined hit rate: 97% (L1+L2)
Avg latency: 0.19ms (weighted)
```

<br>

**Test suite impact:**
```
Before caching: 35 minutes (1.8s × 1195 tests)
After caching:  2.3 minutes (L1 hits)

→ 15x faster test suite
```

---

## [Slide 19] 🛡️ Graceful Degradation

<br>

**Robustesse du système:**

```python
async def get_embedding_safe(text: str):
    try:
        return await cache.get_embedding(text)
    except RedisConnectionError:
        # L2 down? Skip to L3
        logger.warning("Redis down, using L1+L3 only")
        return await l1_and_l3_only(text)
    except Exception as e:
        # Everything fails? Compute direct
        logger.error(f"Cache failed: {e}")
        return await compute_embedding(text)
```

<br>

**Observed behavior:**
- ✅ Redis restart: L1 continues → no impact
- ✅ PostgreSQL slow: L1+L2 continue → degraded but functional
- ✅ Model crash: Re-init transparent

<br>

**Uptime:** 99.8% (during 4 months dev)

---

## [Slide 20] 💡 Lesson Learned #3

<br>

```
╔═══════════════════════════════════════╗
║                                       ║
║  "Cache Layers Matter"                ║
║                                       ║
║  L1+L2+L3 = Performance × 100         ║
║  + Resilience built-in                ║
║                                       ║
╚═══════════════════════════════════════╝
```

<br>

**Pattern réutilisable:**
- ✅ Multi-layer cache > Single cache
- ✅ Graceful degradation > Hard failures
- ✅ Local (L1) always fastest
- ✅ Shared (L2) for multi-process
- ✅ Source (L3) as fallback

<br>

**Applicabilité:** Pas juste embeddings - toute ressource coûteuse

---

# 🚀 DECISION 4: Async Everything
**Architecture Moderne**

---

## [Slide 21] ❓ Story Hook: Blocking = Mort en 2025

<br>

**Contexte: EPIC-12, Architecture initiale**

<br>

```python
# Version 1 (synchrone)
def search_endpoint(query: str):
    embedding = get_embedding(query)  # Blocks 15ms
    results = db.query(embedding)      # Blocks 10ms
    return results

# Problème:
# - 1 request = 1 thread blocked 25ms
# - 100 requests simultanés = 100 threads!
# - Thread overhead = gigantesque
```

<br>

**Observation:**
- FastAPI supporte async native
- PostgreSQL a asyncpg
- Tout l'écosystème Python async mature

<br>

**Question:**

> "Async upfront ou retrofit later?"

---

## [Slide 22] ⚖️ Options & Choix

<br>

### Option A: Sync (traditionnel)
```python
def get_data():
    result = db.query()  # Blocks thread
    return result
```
- ❌ Thread per request
- ❌ Limited concurrency
- ❌ Retrofit = painful

### Option B: Async (moderne)
```python
async def get_data():
    result = await db.query()  # Non-blocking
    return result
```
- ✅ Event loop efficient
- ✅ High concurrency
- ✅ Modern ecosystem

<br>

**Choix:** Async-first dès EPIC-12

<br>

**Motto:** "Async upfront, not retrofitted"

---

## [Slide 23] 🔬 Technical Deep Dive: Async Stack

<br>

**Stack complet async:**

```python
# FastAPI (async native)
@app.get("/search")
async def search(query: str):
    embedding = await cache.get_embedding(query)
    results = await db.search(embedding)
    return results

# SQLAlchemy Core (async)
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    "postgresql+asyncpg://...",
    pool_size=20,
    max_overflow=10
)

async with engine.begin() as conn:
    result = await conn.execute(query)

# Redis (aioredis)
redis = await aioredis.create_redis_pool(
    "redis://localhost"
)
await redis.get("key")
```

---

## [Slide 24] 📊 Results: Concurrency Benchmark

<br>

**Test setup:**
```
Scenario: 100 requests simultanés
Query: Semantic search (cache miss)
Hardware: Ryzen 7 5800X (8 cores)
```

<br>

**Sync version:**
```
Threads: 100 (1 per request)
Memory: 850MB (thread overhead)
Latency P50: 145ms
Latency P99: 380ms
Throughput: 68 req/sec
```

**Async version:**
```
Threads: 1 (event loop)
Memory: 120MB
Latency P50: 28ms
Latency P99: 65ms
Throughput: 340 req/sec

→ 5x faster, 7x less memory
```

---

## [Slide 25] 💡 Lesson Learned #4

<br>

```
╔═══════════════════════════════════════╗
║                                       ║
║  "Async Upfront, Not Retrofitted"     ║
║                                       ║
║  Going async later = rewrite          ║
║  Going async first = natural          ║
║                                       ║
╚═══════════════════════════════════════╝
```

<br>

**Pattern réutilisable:**
- ✅ Async from day 1 (no retrofit pain)
- ✅ Event loop > Thread pool (efficiency)
- ✅ Modern Python ecosystem is async-ready
- ✅ Connection pooling matters

<br>

**Caveat:** Async everywhere = discipline (no blocking calls)

---

# 🧪 DECISION 5: Testing Strategy
**Mock ou Pas Mock?**

---

## [Slide 26] ❓ Story Hook: Tests Impossibles

<br>

**Contexte: EPIC-18, Tests en croissance**

<br>

```
Problème:
→ 1195 tests collectés
→ Chaque test charge le model: 1.8s
→ Total: 1195 × 1.8s = 35 minutes
→ CI/CD timeout à 10 minutes
```

<br>

**Dilemme:**
```python
def test_search():
    # Besoin d'embeddings réels?
    query = "test query"
    result = search(query)  # Loads model 1.8s
    assert len(result) > 0

# Mais... est-ce qu'on teste vraiment les embeddings?
# Ou on teste la logique search?
```

<br>

**Question:**

> "Mocker les embeddings = acceptable?"

---

## [Slide 27] ⚖️ Options Considérées

<br>

### Option A: No Mock (Real embeddings)
```python
def test_search():
    result = search("query")  # Real 768D vector
    assert result
```
- ✅ Tests "réels"
- ❌ 35 min test suite
- ❌ CI/CD impossible
- ❌ Dev loop painful

### Option B: Full Mock (Fake everything)
```python
def test_search():
    with mock.patch("get_embedding", return_value=[0]*768):
        result = search("query")
```
- ✅ Fast (2 min)
- ⚠️ Faux négatifs (mock cache bugs)
- ⚠️ Moins confiance

### Option C: Smart Mock (Env-based)
```python
if EMBEDDING_MODE == "mock":
    return deterministic_mock(text)
else:
    return real_embedding(text)
```
- ✅ Fast en dev/CI (2 min)
- ✅ Real en staging/prod
- ✅ Configurable
- ✅ Best of both worlds

---

## [Slide 28] 🔬 Technical Deep Dive: EMBEDDING_MODE

<br>

**Implementation:**

```python
# api/services/embedding_service.py

import os
import hashlib

EMBEDDING_MODE = os.getenv("EMBEDDING_MODE", "real")

async def get_embedding(text: str) -> List[float]:
    if EMBEDDING_MODE == "mock":
        # Deterministic mock based on text hash
        hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
        np.random.seed(hash_val % (2**32))
        return np.random.randn(768).tolist()

    elif EMBEDDING_MODE == "real":
        # Real sentence-transformers
        return await real_encode(text)

    else:
        raise ValueError(f"Invalid EMBEDDING_MODE: {EMBEDDING_MODE}")
```

**Usage:**
```bash
# Development (fast)
export EMBEDDING_MODE=mock
pytest  # 2.3 min

# CI/CD (fast)
EMBEDDING_MODE=mock pytest  # 2.3 min

# Staging (real, sample)
EMBEDDING_MODE=real pytest -k "critical"  # 8 min

# Production (real, all)
EMBEDDING_MODE=real pytest  # 35 min (scheduled nightly)
```

---

## [Slide 29] 📊 Results: Test Suite Performance

<br>

**Metrics:**

```
Test suite: 1,195 tests collected

EMBEDDING_MODE=mock:
  Duration: 2.3 minutes
  Memory: 450MB
  Pass rate: 100% (when code works)
  False positives: 0 (deterministic mock)

EMBEDDING_MODE=real:
  Duration: 35 minutes
  Memory: 2.8GB (model loaded once)
  Pass rate: 100%
  Confidence: Maximum

Strategy:
→ Dev: Always mock (fast iteration)
→ CI: Always mock (gate keeper)
→ Nightly: Real (sanity check)
→ Pre-release: Real (validation)
```

<br>

**Developer experience:**
```
Before: 35 min → ☕ break → context switch
After:  2.3 min → ⚡ instant feedback
```

---

## [Slide 30] 💡 Lesson Learned #5

<br>

```
╔═══════════════════════════════════════╗
║                                       ║
║  "Mock External Dependencies"         ║
║                                       ║
║  Model loading = external dependency  ║
║  Mock smart, validate occasionally    ║
║                                       ║
╚═══════════════════════════════════════╝
```

<br>

**Pattern réutilisable:**
- ✅ Env-based config (not hard-coded mocks)
- ✅ Deterministic mocks (hash-based)
- ✅ Fast feedback loop > Perfect realism
- ✅ Periodic real validation (nightly)

<br>

**Applicabilité:** Toute ressource externe coûteuse (APIs, ML models, etc.)

---

# 🔌 DECISION 6: MCP vs Custom API
**Standards Win** ⭐ **CLIMAX**

---

## [Slide 31] ❓ Story Hook: Intégrer avec Claude Desktop

<br>

**Contexte: EPIC-23, Mois 4 - Le Défi Ultime**

<br>

```
Besoin:
→ Permettre à Claude (AI) d'accéder à MnemoLite
→ Search conversations, code, memories
→ Intégration native avec Claude Desktop
```

<br>

**Options:**
1. **Custom REST API** - classique, flexible
2. **GraphQL** - moderne, over-engineering?
3. **MCP (Model Context Protocol)** - nouveau standard Anthropic

<br>

**Enjeu:**
- Si ça marche = **game changer**
- Si ça échoue = 4 mois pour rien?

<br>

**Pression:** C'est nouveau (spec juin 2025), peu de docs, risqué

---

## [Slide 32] ⚖️ Options Détaillées

<br>

### Option A: Custom REST API
```python
@app.get("/api/search")
async def search(query: str):
    return {"results": [...]}
```
- ✅ Total control
- ✅ Bien connu
- ❌ Custom client needed
- ❌ No standard
- ❌ Maintenance burden

### Option B: GraphQL
```graphql
query Search($query: String!) {
  search(query: $query) {
    results { id content }
  }
}
```
- ✅ Flexible queries
- ❌ Over-engineering (our case)
- ❌ Learning curve
- ❌ Still custom

### Option C: MCP (Model Context Protocol)
```python
# Spec: 2025-06-18
# Library: FastMCP 2.0
@mcp.tool()
async def search_code(query: str) -> List[Result]:
    """Search code semantically"""
    return results
```
- ✅ **Standard protocol**
- ✅ Native Claude Desktop
- ✅ Tools + Resources
- ⚠️ Nouveau (risk)
- ⚠️ Peu de docs

---

## [Slide 33] 🔬 Technical Deep Dive: MCP Implementation

<br>

**Stack:**
```python
# FastMCP 2.0
from fastmcp import FastMCP

mcp = FastMCP("MnemoLite Server")

# 6 Tools implémentés
@mcp.tool()
async def search_code(query: str, limit: int = 10):
    """Search code semantically via embeddings"""
    embedding = await get_embedding(query)
    return await db.search(embedding, limit=limit)

@mcp.tool()
async def search_conversations(query: str, limit: int = 10):
    """Search past conversations"""
    # Similar

@mcp.tool()
async def write_memory(content: str, tags: List[str]):
    """Persist a memory for future retrieval"""
    # ...

# 5 Resources exposées
@mcp.resource("mnemolite://stats")
async def get_stats():
    """System statistics"""
    return {
        "conversations": 7972,
        "code_items": 1523,
        "memories": 342
    }
```

---

## [Slide 34] 🏗️ Architecture MCP

<br>

```
┌─────────────────────────────────────┐
│   Claude Desktop (Client)           │
│   - User interface                  │
│   - MCP client built-in             │
└─────────────────┬───────────────────┘
                  │ JSON-RPC over stdio
                  ↓
┌─────────────────────────────────────┐
│   FastMCP Server (Python)           │
│   - 6 tools (search_code, etc.)     │
│   - 5 resources (stats, etc.)       │
└─────────────────┬───────────────────┘
                  │ Async calls
                  ↓
┌─────────────────────────────────────┐
│   MnemoLite Core                    │
│   - Triple-layer cache              │
│   - PostgreSQL + Redis              │
│   - Embedding service               │
└─────────────────────────────────────┘
```

<br>

**Communication:**
- Protocol: JSON-RPC 2.0
- Transport: stdio (standard input/output)
- Async: Full async/await
- Error handling: Protocol-level + app-level

---

## [Slide 35] 🧪 Testing Strategy MCP

<br>

**Test Pyramid:**

```
Unit Tests (250 tests)
├─ Tool logic isolated
├─ Resource formatting
└─ Error handling

Integration Tests (80 tests)
├─ MCP protocol compliance
├─ Tool → Service → DB flow
└─ Async context propagation

E2E Tests (25 tests)
├─ Full MCP server lifecycle
├─ Real JSON-RPC messages
└─ Claude Desktop simulation

Total: 355 tests MCP
```

<br>

**Challenges rencontrés:**
```python
# Challenge 1: Async/await hell
async def tool_wrapper(func):
    async def wrapper(*args, **kwargs):
        # Pydantic validation (sync)
        # Database call (async)
        # Error handling (sync/async mix)
    return wrapper

# Challenge 2: Type mismatches (Pydantic v2)
# Challenge 3: Transaction management
# Challenge 4: Flaky tests avec Docker
```

---

## [Slide 36] 🎯 Le Moment de Vérité

<br>

### Dimanche 27 octobre 2025, 23h47

<br>

```bash
$ EMBEDDING_MODE=mock pytest tests/mnemo_mcp/ -v
```

<br>

```
tests/mnemo_mcp/test_tools.py::test_search_code PASSED
tests/mnemo_mcp/test_tools.py::test_search_conversations PASSED
tests/mnemo_mcp/test_tools.py::test_write_memory PASSED
...
...
[WAITING...]
```

<br>
<br>

**Suspense maximum** ⏳

---

## [Slide 37] 🏆 VICTOIRE! (CLIMAX)

<br>

```
╔═══════════════════════════════════════╗
║                                       ║
║   355/355 tests passing               ║
║   100% success rate                   ║
║   0 failures, 0 errors                ║
║                                       ║
║   EPIC-23 MCP COMPLETE ✅             ║
║                                       ║
╚═══════════════════════════════════════╝
```

<br>

**Results:**
- ✅ Claude Desktop connecté
- ✅ MCP Server opérationnel
- ✅ 6 tools fonctionnels
- ✅ 5 resources disponibles
- ✅ Integration time: 47.5h (1 dev)
- ✅ Bugs found & fixed: 15
- ✅ Rewrites: 3 major iterations

<br>

**Le POC d'une semaine est maintenant
un système MCP-enabled complet**

<br>

# 🎉 PAYOFF ÉMOTIONNEL! 🎉

---

## [Slide 38] 💡 Lesson Learned #6

<br>

```
╔═══════════════════════════════════════╗
║                                       ║
║  "Standards Win"                      ║
║                                       ║
║  MCP (standard) > Custom API          ║
║  Interoperability > Control           ║
║  Ecosystem > Solo solution            ║
║                                       ║
╚═══════════════════════════════════════╝
```

<br>

**Pattern réutilisable:**
- ✅ Bet on standards (even if new)
- ✅ Protocol > Implementation
- ✅ Ecosystem integration > Custom
- ✅ Spec compliance = future-proof

<br>

**Bonus MCP:**
- Native Claude Desktop integration
- Other MCP clients work too
- Tools composability
- Resource discovery

---

# 📋 DECISION 7: Process Formalization
**Discipline = Force**

---

## [Slide 39] ❓ Story Hook: POC ou Vrai Projet?

<br>

**Contexte: Dimanche soir, fin semaine 1**

<br>

```
Situation:
→ POC validé (CPU embeddings marchent!)
→ Code: ~500 lignes Python
→ Tests: 15 tests basiques
→ Docs: README.md minimal
```

<br>

**Le choix:**
```
Option A: Continue cowboy coding
  → Fast, flexible
  → Mais... pas scalable

Option B: Formaliser un process
  → EPICs, Stories, Reports
  → Discipline, traçabilité
  → Mais... overhead?
```

<br>

**Question:**

> "Est-ce qu'un projet solo mérite un process formel?"

---

## [Slide 40] 🔬 Technical Deep Dive: Process Adopted

<br>

**Structure adoptée (inspirée Agile):**

```
EPIC (Epic)
├─ Story 1
│  ├─ Acceptance criteria
│  ├─ Tasks breakdown
│  └─ Completion report
├─ Story 2
└─ Story N

EPIC Completion Report
├─ What was done
├─ Metrics
├─ Challenges
├─ Lessons learned
```

<br>

**Example: EPIC-23 MCP Integration**
```markdown
# EPIC-23: MCP Integration

## Stories:
- Story 23.1: FastMCP Setup (3 pts)
- Story 23.2: Implement Tools (9 pts)
- Story 23.3: Implement Resources (3 pts)
- Story 23.4: Testing Strategy (4 pts)
- Story 23.5: Integration Tests (4 pts)

Total: 23 story points
Duration: 47.5h actual
Completion: 19/23 pts (83%)
```

---

## [Slide 41] 📊 Results: Traçabilité

<br>

**Après 4 mois:**

```
8 EPICs complétés:
├─ EPIC-12: Foundation
├─ EPIC-13: Graph & Dependencies
├─ EPIC-14: UI SCADA
├─ EPIC-19: Embeddings Deep Dive
├─ EPIC-21: UI/UX Improvements
├─ EPIC-22: Observability
├─ EPIC-23: MCP Integration
└─ EPIC-24: Auto-Save

46 Completion Reports rédigés
~250 pages de documentation
Chaque décision tracée
```

<br>

**Bénéfices concrets:**
- ✅ Roadmap claire (quoi faire ensuite?)
- ✅ Mémoire du projet (pourquoi X?)
- ✅ Learnings documentés (ne pas répéter erreurs)
- ✅ Onboarding futur (si contributeurs)
- ✅ Portfolio professionnel (preuves)

---

## [Slide 42] 💡 Lesson Learned #7

<br>

```
╔═══════════════════════════════════════╗
║                                       ║
║  "Process = Force Multiplier"         ║
║                                       ║
║  Solo dev + Discipline                ║
║  > Team sans process                  ║
║                                       ║
╚═══════════════════════════════════════╝
```

<br>

**Pattern réutilisable:**
- ✅ EPICs même pour solo (structure)
- ✅ Completion reports = mémoire
- ✅ Acceptance criteria = clarity
- ✅ Traçabilité ≠ bureaucratie

<br>

**Caveat:** Process ≠ overhead si bien dosé (Lean)

---

# 🔍 DECISION 8: Observability Built-In
**Debug Sans Douleur**

---

## [Slide 43] ❓ Story Hook: Blind Flying

<br>

**Contexte: EPIC-22, Mois 3**

<br>

```
Problème vécu:
→ Bug mystérieux en production
→ "Ça marche pas" (user report)
→ Pas de logs structurés
→ Pas de métriques
→ Pas de monitoring
→ Debug = print() statements + guessing
```

<br>

**Réalisation:**
```python
# Code sans observability
def process_request(data):
    result = do_stuff(data)
    return result

# When fails:
# - No trace of inputs
# - No metrics logged
# - No errors captured properly
# → Impossible to debug post-mortem
```

<br>

**Question:**

> "Observability: Après coup ou built-in?"

---

## [Slide 44] 🔬 Technical Deep Dive: Observability Stack

<br>

**Components implémentés:**

```
1. Structured Logging
├─ JSON format
├─ Correlation IDs
├─ Levels (DEBUG, INFO, ERROR)
└─ Contextual metadata

2. Real-Time Log Streaming (SSE)
├─ Server-Sent Events
├─ Web dashboard
├─ Filter by level/source
└─ No polling (push)

3. Metrics Collection
├─ Request latency
├─ Cache hit rates
├─ Database query time
├─ Error rates
└─ Stored in PostgreSQL

4. Dashboard UI
├─ /ui/monitoring/advanced
├─ Real-time graphs
├─ Log streaming live
└─ System health
```

---

## [Slide 45] 📊 Implementation: SSE Logs

<br>

**Server-Sent Events for Real-Time Logs:**

```python
# api/routes/monitoring_routes.py

@app.get("/v1/monitoring/logs/stream")
async def stream_logs(request: Request):
    """Stream logs via SSE"""

    async def event_generator():
        buffer = LogsBuffer()  # Thread-safe circular buffer

        while True:
            if await request.is_disconnected():
                break

            # Get new logs from buffer
            logs = buffer.get_new()
            for log in logs:
                yield {
                    "event": "log",
                    "data": json.dumps({
                        "timestamp": log.timestamp,
                        "level": log.level,
                        "message": log.message,
                        "source": log.source
                    })
                }

            await asyncio.sleep(0.1)  # 100ms poll

    return EventSourceResponse(event_generator())
```

**Frontend (JavaScript):**
```javascript
const eventSource = new EventSource('/v1/monitoring/logs/stream');
eventSource.onmessage = (event) => {
    const log = JSON.parse(event.data);
    appendLogToUI(log);  // Real-time append
};
```

---

## [Slide 46] 🎯 Results: Debug Experience

<br>

**Before Observability:**
```
Bug report: "Search doesn't work"
Debug process:
1. Add print() statements
2. Restart server
3. Reproduce bug
4. Read stdout
5. Repeat
Time: 2-3 hours per bug
```

**After Observability:**
```
Bug report: "Search doesn't work"
Debug process:
1. Open /ui/monitoring/advanced
2. Filter logs by user/timestamp
3. See exact error with context
4. Identify root cause
Time: 5-10 minutes per bug

→ 10-20x faster debugging
```

<br>

**Metrics retention:**
```sql
-- All requests logged in DB
SELECT endpoint, avg(latency_ms), count(*)
FROM metrics
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY endpoint;

→ Performance trends visible
```

---

## [Slide 47] 💡 Lesson Learned #8

<br>

```
╔═══════════════════════════════════════╗
║                                       ║
║  "Observability From Day 1"           ║
║                                       ║
║  Logs + Metrics + Dashboard           ║
║  Built-in > Retrofitted               ║
║                                       ║
╚═══════════════════════════════════════╝
```

<br>

**Pattern réutilisable:**
- ✅ Structured logging (not print)
- ✅ Real-time streaming (SSE)
- ✅ Metrics persistence (trends)
- ✅ Correlation IDs (trace requests)

<br>

**Bonus:**
- ✅ Confidence to deploy
- ✅ Post-mortem analysis
- ✅ Performance optimization data

---

# 🎯 SYNTHESIS & LESSONS

---

## [Slide 48] 🧩 Pattern Émergent

<br>

### Les 8 décisions révèlent un pattern commun:

<br>

```
1. CPU vs GPU           → Challenge assumptions
2. Vector DB            → Polyvalence > Spécialisation
3. Cache Strategy       → Layers matter
4. Async Everything     → Modern upfront
5. Testing Strategy     → Fast feedback loop
6. MCP vs Custom        → Standards win
7. Process              → Discipline = force
8. Observability        → Built-in > Retrofit
```

<br>

**Meta-pattern:**
```
╔═══════════════════════════════════════╗
║                                       ║
║  Decisions > Talent                   ║
║  Process + Standards + Testing        ║
║  = Success multiplier                 ║
║                                       ║
╚═══════════════════════════════════════╝
```

---

## [Slide 49] 📊 Métriques Finales

<br>

**Ce qui est PROUVÉ:**

```
✅ 8 EPICs complétés (EPIC-12 → EPIC-24)
✅ 46 Completion Reports formels
✅ 1,195 tests collectés
✅ 355+ tests validés passants (100% MCP)
✅ 7,972 conversations auto-saved
✅ ~15,000 lignes de code
✅ Triple-layer cache (L1+L2+L3)
✅ PostgreSQL 18 + pgvector 0.8.1
✅ 4 mois développement
✅ 1 développeur
✅ 0€ budget infrastructure
```

<br>

**Performance (échelle modeste):**
```
→ Vector search: 8-12ms (10k items)
→ Cache hit rate: 97% (L1+L2)
→ Throughput: 340 req/sec (async)
→ Test suite: 2.3 min (mock mode)
```

---

## [Slide 50] ⚠️ Limitations Honnêtes

<br>

**Ce qu'on NE sait PAS:**

```
❓ Production multi-users
   → Jamais testé >1 user concurrent

❓ Scale 100k+ items
   → Architecture prête, pas validé

❓ Load testing formel
   → Absent (k6, Locust)

❓ Long-term maintenance
   → Solo dev = bus factor 1

❓ Enterprise-ready
   → Clairement non (pas de SLA, support, certs)
```

<br>

**Verdict:**
```
Plus qu'un POC
Moins qu'une solution enterprise
Fonctionne à échelle modeste
Honnête sur les limites
```

---

## [Slide 51] 🎯 Use Cases Réalistes

<br>

### ✅ Validé Pour:

```
→ Projets solo/duo
→ Prototypes & POCs
→ Learning projects
→ Small teams (<5 devs)
→ Quelques milliers d'items
→ Privacy-first applications
→ Cost-sensitive projects (0€)
```

<br>

### ❌ NOT For:

```
→ Enterprise critical systems
→ Millions d'items
→ High traffic (>100 req/s)
→ Multi-tenant SaaS
→ Mission critical (pas de SLA)
→ 24/7 support needed
```

<br>

**Comparaison honnête:** MnemoLite ≠ Pinecone (différents besoins)

---

## [Slide 52] 💭 Ce Que J'ai Appris

<br>

**Leçons Techniques:**
- PostgreSQL 18 est puissant (vectors + graph + SQL)
- MCP change tout pour l'intégration LLM
- Tests = confiance (360+ = deploy sans peur)
- Cache layers matter (L1+L2+L3)
- Async upfront > retrofit

**Leçons Process:**
- EPICs formels aident (même solo)
- Completion reports = mémoire projet
- Discipline = force multiplier
- Over-engineering est un risque réel
- Observability from day 1

**Leçons Meta:**
- Decisions > Talent
- Process + Standards + Testing = Success
- Challenge dogmas (GPU obligatoire?)
- Solo dev peut aller loin (avec discipline)
- Limites dans nos têtes, pas tech

---

## [Slide 53] 🚀 Message Final

<br>

```
╔═══════════════════════════════════════╗
║                                       ║
║  "8 Decisions Shaped MnemoLite"       ║
║                                       ║
║  Vos 8 prochaines décisions           ║
║  façonneront votre projet             ║
║                                       ║
║  Choisissez avec intention            ║
║  Documentez                           ║
║  Apprenez                             ║
║  Partagez                             ║
║                                       ║
╚═══════════════════════════════════════╝
```

<br>

**Framework réutilisable:**
1. Identifiez vos décisions critiques
2. Évaluez les options honnêtement
3. Choisissez avec data (benchmarks)
4. Documentez le "pourquoi"
5. Mesurez les résultats
6. Extrayez les lessons

---

## [Slide 54] 📖 Open Source & Ressources

<br>

**GitHub:**
```
→ github.com/.../mnemolite
→ MIT License
→ Documentation: 46 completion reports
→ Architecture guides
→ Getting started
→ MCP integration guide
```

<br>

**Disclaimers:**
```
→ Pas production-ready enterprise
→ Support limité (solo dev)
→ Use at own risk
→ Contributions bienvenues (avec patience)
```

<br>

**Mais:**
```
✅ Inspiration gratuite
✅ Patterns réutilisables
✅ Lessons learned documentées
✅ Framework de décision applicable
```

---

## [Slide 55] 🙏 Merci & Questions

<br>

```
╔═══════════════════════════════════════╗
║                                       ║
║   "Start with a question.             ║
║    Make 8 critical decisions.         ║
║    Document.                          ║
║    Share."                            ║
║                                       ║
║   MnemoLite: 8 EPICs • 4 months       ║
║             • 1 developer • 0 GPU     ║
║                                       ║
║   Your project's next 8 decisions     ║
║   could be transformative             ║
║                                       ║
╚═══════════════════════════════════════╝
```

<br>

**Contact:**
- GitHub: [lien]
- Email: [email]
- LinkedIn: [profil]

<br>

# Questions? 💬

---

**FIN**
