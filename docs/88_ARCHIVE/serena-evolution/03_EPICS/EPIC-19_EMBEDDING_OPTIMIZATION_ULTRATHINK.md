# EPIC-19: Embedding Optimization - ULTRATHINK Deep Dive

**Date**: 2025-10-23
**Auteur**: Claude Code
**Contexte**: Suite aux tests réels d'embeddings sémantiques
**Objectif**: Explorer TOUTES les optimisations possibles (court, moyen, long terme)

---

## 🎯 Synthèse des Problèmes Identifiés

### Problèmes Critiques (Bloquants Production)

1. **❌ Timeout avec Embeddings JSON** (>30s)
   - Envoyer 768 floats dans JSON HTTP = trop lourd
   - Sérialisation/désérialisation coûteuse
   - Impossible d'utiliser en production

2. **❌ API N'Auto-Embed PAS les Queries**
   - Client doit générer embeddings côté client
   - Pas de recherche sémantique automatique
   - UX dégradée

3. **⚠️ Startup Lent en Mode Real** (~30-40s)
   - Chargement 2.5GB de modèles ML au démarrage
   - Application indisponible pendant le chargement
   - Problème pour auto-scaling

### Problèmes Mineurs (Optimisations Souhaitables)

4. **⚠️ Dual Embedding Mismatch**
   - Chunks: CODE embeddings
   - Queries: TEXT embeddings
   - Espaces vectoriels différents

5. **⚠️ Mémoire Élevée** (2.5GB RAM)
   - 2 modèles chargés en permanence
   - Coût infrastructure élevé
   - Limite scaling horizontal

6. **⚠️ Tree-sitter Chunking Issues**
   - Regex escaping casse le parsing
   - 0 chunks créés dans certains cas
   - Tests incomplets

---

## 🚀 PARTIE 1: Solutions Immédiates (Sprint Courant)

### 1.1. Auto-Embedding dans l'API (CRITIQUE)

#### Problème
```python
# Actuellement: Client DOIT fournir embedding
payload = {
    "query": "validate email",
    "embedding_text": [0.12, ...],  # 768 floats! ❌ Timeout
}
```

#### Solution A: Auto-Generate si Absent (RECOMMANDÉ)

```python
# api/routes/code_search_routes.py

from services.dual_embedding_service import DualEmbeddingService, EmbeddingDomain

@router.post("/v1/code/search/hybrid")
async def search_hybrid(
    request: HybridSearchRequest,
    embedding_svc: DualEmbeddingService = Depends(get_embedding_service)
):
    """Hybrid search with automatic query embedding generation."""

    # Auto-generate embedding if not provided AND vector search enabled
    if not request.embedding_text and request.enable_vector:
        logger.info(f"Auto-generating embedding for query: {request.query[:50]}...")

        try:
            result = await embedding_svc.generate_embedding(
                text=request.query,
                domain=EmbeddingDomain.TEXT
            )
            request.embedding_text = result['text']
            logger.info(f"✅ Query embedding generated (768D)")
        except Exception as e:
            logger.warning(f"Failed to generate embedding: {e}, falling back to lexical-only")
            request.enable_vector = False  # Graceful degradation

    # Proceed with hybrid search (lexical + vector + RRF)
    ...
```

**Avantages**:
- ✅ Aucun changement côté client (backward compatible)
- ✅ Recherche sémantique automatique par défaut
- ✅ Graceful degradation si échec
- ✅ Résout le problème de timeout (pas d'embedding dans JSON)

**Inconvénients**:
- ⚠️ Latency +10-20ms (génération embedding)
- ⚠️ Charge CPU/GPU serveur

**Estimation**: 2-3 points de story (1 jour de dev)

---

#### Solution B: Endpoint Dédié `/v1/embeddings/generate`

```python
# api/routes/embedding_routes.py (NOUVEAU)

@router.post("/v1/embeddings/generate")
async def generate_query_embedding(
    query: str = Body(..., description="Query text to embed"),
    domain: EmbeddingDomain = Body(EmbeddingDomain.TEXT, description="TEXT or CODE domain"),
    embedding_svc: DualEmbeddingService = Depends(get_embedding_service)
) -> Dict[str, Any]:
    """
    Generate embedding for a query.

    Returns:
        {
            "query": "validate email address",
            "embedding_text": [0.12, -0.45, ...],  # 768D
            "embedding_code": [0.11, -0.44, ...],  # 768D (if HYBRID)
            "dimension": 768,
            "model": "nomic-embed-text-v1.5",
            "generation_time_ms": 15.3
        }
    """
    start_time = time.time()

    result = await embedding_svc.generate_embedding(
        text=query,
        domain=domain
    )

    elapsed_ms = (time.time() - start_time) * 1000

    return {
        "query": query,
        "embedding_text": result.get('text'),
        "embedding_code": result.get('code'),
        "dimension": 768,
        "model": "nomic-embed-text-v1.5" if 'text' in result else "jina-embeddings-v2-base-code",
        "generation_time_ms": elapsed_ms
    }
```

**Usage côté client**:
```python
# 1. Generate embedding
embedding_resp = await client.post("/v1/embeddings/generate", json={"query": "validate email"})
embedding_text = embedding_resp['embedding_text']

# 2. Search with embedding
search_resp = await client.post("/v1/code/search/hybrid", json={
    "query": "validate email",
    "embedding_text": embedding_text
})
```

**Avantages**:
- ✅ Flexibilité (client peut cacher embeddings)
- ✅ Séparation des responsabilités
- ✅ Utile pour batch processing

**Inconvénients**:
- ⚠️ 2 requêtes HTTP au lieu d'une (latency +)
- ⚠️ Toujours le problème de timeout avec embedding JSON

**Estimation**: 3 points de story (1-2 jours de dev + tests)

---

### 1.2. Compression d'Embeddings (IMPORTANT)

#### Problème
```python
# 768 floats × 4 bytes (FP32) = 3072 bytes
embedding = [0.123456789, -0.987654321, ...]  # 768 values

# En JSON: ~6 KB (overhead string representation)
json.dumps({"embedding_text": embedding})  # ~6000 bytes
```

#### Solution: Quantization INT8

```python
# api/services/embedding_compression_service.py (NOUVEAU)

import numpy as np
from typing import List
import base64

class EmbeddingCompressionService:
    """Compress embeddings from FP32 to INT8 (8x smaller)."""

    @staticmethod
    def quantize(embedding: List[float]) -> str:
        """
        Quantize FP32 embedding to INT8 and encode as base64.

        Returns:
            Base64-encoded INT8 array (768 bytes → ~1024 chars base64)
        """
        arr = np.array(embedding, dtype=np.float32)

        # Normalize to [-1, 1]
        max_abs = np.abs(arr).max()
        if max_abs > 0:
            normalized = arr / max_abs
        else:
            normalized = arr

        # Quantize to INT8 [-127, 127]
        quantized = (normalized * 127).astype(np.int8)

        # Encode as base64 for JSON transport
        return base64.b64encode(quantized.tobytes()).decode('ascii')

    @staticmethod
    def dequantize(compressed: str) -> List[float]:
        """
        Dequantize INT8 back to FP32.

        Args:
            compressed: Base64-encoded INT8 array

        Returns:
            FP32 embedding (768 floats)
        """
        # Decode base64
        data = base64.b64decode(compressed.encode('ascii'))

        # Convert to INT8 array
        quantized = np.frombuffer(data, dtype=np.int8)

        # Dequantize to FP32 [-1, 1]
        dequantized = quantized.astype(np.float32) / 127.0

        return dequantized.tolist()
```

**Usage dans l'API**:
```python
# Génération
embedding = await embedding_svc.generate_embedding(query, EmbeddingDomain.TEXT)
compressed = EmbeddingCompressionService.quantize(embedding['text'])

# Response
return {
    "embedding_compressed": compressed,  # ~1024 chars (vs 6000 bytes)
    "compression": "int8_base64",
    "dimension": 768
}

# Client decompresses
embedding_text = EmbeddingCompressionService.dequantize(compressed)
```

**Métriques**:
- **Taille**: 6 KB → 1 KB (6x reduction)
- **Précision**: ~1-2% loss (acceptable pour search)
- **Latency**: +1-2ms (compression/decompression)

**Avantages**:
- ✅ Résout timeout (6x plus petit)
- ✅ Compatible pgvector (peut stocker INT8)
- ✅ Précision acceptable (~98-99%)
- ✅ Facile à implémenter

**Inconvénients**:
- ⚠️ Légère perte de précision
- ⚠️ Complexité ajoutée

**Estimation**: 5 points de story (2-3 jours de dev + tests de précision)

---

### 1.3. Caching Query Embeddings (QUICK WIN)

#### Problème
Queries identiques re-calculent l'embedding à chaque fois.

#### Solution: Redis Cache L2

```python
# api/services/dual_embedding_service.py

import hashlib
import json

async def generate_embedding_cached(
    self,
    text: str,
    domain: EmbeddingDomain = EmbeddingDomain.TEXT
) -> Dict[str, List[float]]:
    """Generate embedding with Redis caching."""

    # Cache key: hash(text + domain)
    cache_key = f"embedding:{domain.value}:{hashlib.md5(text.encode()).hexdigest()}"

    # Try L2 cache first
    if self.redis_cache:
        try:
            cached = await self.redis_cache.get(cache_key)
            if cached:
                logger.debug(f"Embedding cache HIT: {cache_key}")
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis cache read error: {e}")

    # Generate embedding (cache MISS)
    logger.debug(f"Embedding cache MISS: {cache_key}")
    result = await self.generate_embedding(text, domain)

    # Store in L2 cache (TTL: 1 hour)
    if self.redis_cache:
        try:
            await self.redis_cache.setex(
                cache_key,
                ttl=3600,  # 1 hour
                value=json.dumps(result)
            )
        except Exception as e:
            logger.warning(f"Redis cache write error: {e}")

    return result
```

**Métriques**:
- **Cache HIT**: ~0ms (vs 10-20ms generation)
- **Cache MISS**: ~10-20ms (generation) + ~1ms (Redis write)
- **Hit rate attendu**: 30-50% (queries fréquentes)

**Avantages**:
- ✅ Latency drastiquement réduite sur cache hit
- ✅ Charge CPU/GPU réduite
- ✅ Scalable (Redis distribué)
- ✅ Facile à implémenter (déjà Redis en place)

**Inconvénients**:
- ⚠️ Mémoire Redis (+) - mais gérable avec TTL

**Estimation**: 2 points de story (1 jour de dev)

---

## 🔥 PARTIE 2: Optimisations Performance (Sprint +1)

### 2.1. Lazy Loading des Modèles

#### Problème
Modèles chargés au démarrage = 30-40s d'indisponibilité.

#### Solution: Load on First Request

```python
# api/services/dual_embedding_service.py

class DualEmbeddingService:
    def __init__(self):
        self._text_model = None
        self._code_model = None
        self._loading_lock = asyncio.Lock()
        self._load_start_time = None

    async def _ensure_text_model(self):
        """Lazy load TEXT model on first use."""
        if self._text_model is not None:
            return  # Already loaded

        async with self._loading_lock:
            # Double-check after acquiring lock
            if self._text_model is not None:
                return

            logger.info("Lazy loading TEXT model (first request)...")
            self._load_start_time = time.time()

            # Load model
            self._text_model = SentenceTransformer(self.text_model_name)

            elapsed = time.time() - self._load_start_time
            logger.info(f"✅ TEXT model loaded in {elapsed:.1f}s")
```

**Avantages**:
- ✅ Startup immédiat (0ms)
- ✅ Application disponible dès le démarrage
- ✅ Bon pour auto-scaling (pas de warm-up)

**Inconvénients**:
- ⚠️ Première requête lente (~15-20s)
- ⚠️ Complexité de thread-safety

**Solution Hybride**: Lazy + Background Pre-loading

```python
# main.py lifespan

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start app immediately
    yield

    # Pre-load models in background (non-blocking)
    asyncio.create_task(preload_models_background())

async def preload_models_background():
    """Pre-load models in background after app start."""
    await asyncio.sleep(5)  # Wait 5s for app to be healthy

    embedding_svc = DualEmbeddingService()
    await embedding_svc.preload_models()  # Non-blocking
```

**Avantages combinés**:
- ✅ App disponible immédiatement
- ✅ Modèles chargés en background (5-10s après start)
- ✅ Première requête rapide (si background load terminé)

**Estimation**: 3 points de story (1-2 jours)

---

### 2.2. Batch Processing d'Embeddings

#### Problème
Génération d'embeddings un par un = inefficace.

#### Solution: Batch API

```python
# api/routes/embedding_routes.py

@router.post("/v1/embeddings/generate/batch")
async def generate_embeddings_batch(
    queries: List[str] = Body(..., max_items=100, description="List of queries to embed"),
    domain: EmbeddingDomain = Body(EmbeddingDomain.TEXT),
    embedding_svc: DualEmbeddingService = Depends(get_embedding_service)
) -> Dict[str, Any]:
    """
    Generate embeddings for multiple queries in one shot (MUCH faster).

    Batch processing is ~10x faster than individual requests:
    - 100 queries individually: ~1000ms (10ms each)
    - 100 queries in batch: ~100ms (1ms each)
    """
    start_time = time.time()

    # Generate all embeddings in one batch
    results = await embedding_svc.generate_embeddings_batch(
        texts=queries,
        domain=domain,
        show_progress_bar=False
    )

    elapsed_ms = (time.time() - start_time) * 1000

    return {
        "count": len(results),
        "embeddings": [
            {
                "query": queries[i],
                "embedding_text": result.get('text'),
                "embedding_code": result.get('code')
            }
            for i, result in enumerate(results)
        ],
        "total_time_ms": elapsed_ms,
        "avg_time_per_query_ms": elapsed_ms / len(queries)
    }
```

**Usage côté client**:
```python
# Batch indexation
queries = ["validate email", "check format", "verify credentials", ...]  # 100 queries
response = await client.post("/v1/embeddings/generate/batch", json={"queries": queries})

# Results in one shot
embeddings = response['embeddings']  # 100 embeddings en ~100ms
```

**Métriques**:
- **Individual**: 100 queries × 10ms = 1000ms
- **Batch**: 100 queries / batch = ~100ms (10x faster)
- **Throughput**: 1000 queries/s (vs 100 queries/s)

**Avantages**:
- ✅ 10x plus rapide pour batch
- ✅ Charge serveur réduite (moins de context switches)
- ✅ Idéal pour indexation de repository complet

**Estimation**: 3 points de story (1-2 jours)

---

### 2.3. GPU Acceleration (Si Volume Élevé)

#### Problème
CPU inference lent (~10-20ms par embedding).

#### Solution: CUDA + TensorRT

```python
# api/services/dual_embedding_service.py

import torch

class DualEmbeddingService:
    def __init__(self):
        # Auto-detect GPU
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        logger.info(f"Using device: {self.device}")

        if self.device == 'cuda':
            # Load models on GPU
            self._text_model = SentenceTransformer(
                self.text_model_name,
                device='cuda'
            )
            logger.info(f"✅ TEXT model loaded on GPU (CUDA)")
        else:
            # Fallback to CPU
            self._text_model = SentenceTransformer(self.text_model_name)
            logger.warning(f"⚠️ TEXT model loaded on CPU (no GPU available)")
```

**Métriques (NVIDIA T4)**:
- **CPU**: 10-20ms per embedding
- **GPU**: 1-2ms per embedding (10x faster)
- **Batch on GPU**: 100 embeddings in ~10ms (100x faster)

**Coût Infrastructure**:
- **AWS g4dn.xlarge**: ~$0.50/hour (T4 GPU)
- **GCP n1-standard-4 + T4**: ~$0.60/hour

**Avantages**:
- ✅ 10x plus rapide (1-2ms vs 10-20ms)
- ✅ Throughput énorme (1000+ queries/s)
- ✅ Scalable horizontalement

**Inconvénients**:
- ⚠️ Coût infrastructure (+)
- ⚠️ Complexité (CUDA, drivers)

**Recommendation**: Activer si volume > 1000 queries/jour.

**Estimation**: 5 points de story (2-3 jours setup + tests)

---

### 2.4. Model Distillation (Modèles Plus Petits)

#### Problème
Modèles 137M-161M params = lourds (2.5GB RAM).

#### Solution: Distillation vers Modèles Plus Petits

**Modèles alternatifs**:
- `all-MiniLM-L6-v2`: 22M params, 384D → **6x plus petit**, 80% accuracy
- `all-MiniLM-L12-v2`: 33M params, 384D → **4x plus petit**, 85% accuracy
- Custom distilled model: 50M params, 768D → **3x plus petit**, 90% accuracy

**Configuration**:
```bash
# .env
TEXT_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
CODE_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384  # Reduced from 768
```

**Métriques**:
- **RAM**: 2.5GB → 400MB (6x reduction)
- **Startup**: 30-40s → 5-10s (3-4x faster)
- **Inference**: 10-20ms → 5-10ms (2x faster)
- **Accuracy**: 100% → ~80-85% (acceptable pour search)

**Avantages**:
- ✅ RAM drastiquement réduite (6x)
- ✅ Startup plus rapide (3-4x)
- ✅ Inference plus rapide (2x)
- ✅ Coût infrastructure réduit

**Inconvénients**:
- ⚠️ Précision réduite (~15-20% loss)
- ⚠️ Nécessite re-indexation de tous les embeddings

**Recommendation**: A/B test pour mesurer impact sur accuracy.

**Estimation**: 8 points de story (1 sprint - tests A/B compris)

---

## 🧠 PARTIE 3: Architecture Avancée (Sprint +2/+3)

### 3.1. Microservice Dédié pour Embeddings

#### Problème
Embeddings intégrés dans l'API principale = couplage fort.

#### Solution: Service Séparé

```
┌─────────────────┐
│   MnemoLite API │
│   (FastAPI)     │
└────────┬────────┘
         │ HTTP/gRPC
         ↓
┌─────────────────┐
│ Embedding Service│
│  (FastAPI/gRPC) │
│  - GPU enabled  │
│  - Auto-scaling │
└─────────────────┘
```

**Architecture**:
```yaml
# docker-compose.yml

services:
  api:
    image: mnemo-api
    depends_on:
      - embedding-service
    environment:
      EMBEDDING_SERVICE_URL: http://embedding-service:8002

  embedding-service:
    image: mnemo-embedding-service
    ports:
      - "8002:8002"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      EMBEDDING_MODE: real
      DEVICE: cuda
```

**Avantages**:
- ✅ Scaling indépendant (scale embeddings sans scale API)
- ✅ GPU uniquement sur embedding service
- ✅ Fault isolation (crash embedding ≠ crash API)
- ✅ Multi-language support (clients Python, JS, Go)

**Inconvénients**:
- ⚠️ Latency réseau (+1-2ms)
- ⚠️ Complexité architecture

**Estimation**: 13 points de story (1 sprint complet)

---

### 3.2. gRPC au lieu de REST

#### Problème
REST JSON = overhead de sérialisation.

#### Solution: gRPC + Protobuf

```protobuf
// embedding_service.proto

syntax = "proto3";

service EmbeddingService {
  rpc GenerateEmbedding(EmbeddingRequest) returns (EmbeddingResponse);
  rpc GenerateEmbeddingsBatch(BatchEmbeddingRequest) returns (BatchEmbeddingResponse);
}

message EmbeddingRequest {
  string text = 1;
  string domain = 2;  // "TEXT" or "CODE"
}

message EmbeddingResponse {
  repeated float embedding_text = 1 [packed=true];  // 768 floats
  repeated float embedding_code = 2 [packed=true];
  float generation_time_ms = 3;
}

message BatchEmbeddingRequest {
  repeated string texts = 1;
  string domain = 2;
}

message BatchEmbeddingResponse {
  repeated EmbeddingResponse embeddings = 1;
  float total_time_ms = 2;
}
```

**Métriques**:
- **REST JSON**: 6 KB (768 floats)
- **gRPC Protobuf**: 3 KB (packed floats, binary)
- **Latency**: REST 50ms → gRPC 30ms (40% faster)

**Avantages**:
- ✅ 2x plus petit (binary vs JSON)
- ✅ 40% plus rapide (pas de JSON parsing)
- ✅ Type-safe (protobuf schemas)
- ✅ Streaming support (pour batch)

**Inconvénients**:
- ⚠️ Complexité (protobuf, code generation)
- ⚠️ Debugging plus difficile

**Estimation**: 8 points de story (1 sprint)

---

### 3.3. Queue Asynchrone pour Indexation

#### Problème
Indexation bloquante = timeout pour gros repositories.

#### Solution: Celery + Redis Queue

```python
# api/workers/embedding_worker.py

from celery import Celery

celery_app = Celery('mnemolite', broker='redis://redis:6379/1')

@celery_app.task(name='generate_embeddings_async')
def generate_embeddings_async(
    repository: str,
    files: List[Dict],
    callback_url: Optional[str] = None
):
    """
    Generate embeddings asynchronously in background.

    Args:
        repository: Repository name
        files: List of files to index
        callback_url: Optional webhook URL to notify when done
    """
    logger.info(f"Starting async embedding generation for {repository}")

    embedding_svc = DualEmbeddingService()

    for file in files:
        # Generate embeddings
        result = await embedding_svc.generate_embedding(
            text=file['content'],
            domain=EmbeddingDomain.CODE
        )

        # Store in DB
        await store_code_chunk(file, result)

    logger.info(f"✅ Completed embedding generation for {repository}")

    # Notify callback
    if callback_url:
        await httpx.post(callback_url, json={
            "repository": repository,
            "status": "completed",
            "chunks_created": len(files)
        })
```

**Usage côté API**:
```python
@router.post("/v1/code/index/async")
async def index_code_async(request: IndexRequest):
    """Index code asynchronously (returns immediately)."""

    # Enqueue task
    task = generate_embeddings_async.delay(
        repository=request.repository,
        files=request.files,
        callback_url=request.callback_url
    )

    return {
        "status": "queued",
        "task_id": task.id,
        "repository": request.repository,
        "estimated_time_seconds": len(request.files) * 0.5  # 500ms per file
    }

@router.get("/v1/code/index/status/{task_id}")
async def get_index_status(task_id: str):
    """Check indexation task status."""
    task = celery_app.AsyncResult(task_id)

    return {
        "task_id": task_id,
        "status": task.status,  # PENDING, STARTED, SUCCESS, FAILURE
        "progress": task.info.get('current', 0) if task.info else 0,
        "total": task.info.get('total', 0) if task.info else 0
    }
```

**Avantages**:
- ✅ Pas de timeout (retourne immédiatement)
- ✅ Scalable (workers indépendants)
- ✅ Retry automatique sur échec
- ✅ Progress tracking

**Inconvénients**:
- ⚠️ Complexité (Celery, workers)
- ⚠️ Overhead infrastructure (Redis queue)

**Estimation**: 13 points de story (1 sprint)

---

## 💎 PARTIE 4: Qualité des Résultats (Sprint +3/+4)

### 4.1. Fine-Tuning des Modèles sur Notre Codebase

#### Problème
Modèles génériques = pas optimisés pour notre code.

#### Solution: Fine-Tuning Custom

**Processus**:
1. Collecter données de training (queries + résultats attendus)
2. Créer dataset de paires (query, code_chunk)
3. Fine-tune le modèle avec contrastive learning
4. Évaluer accuracy (recall@10, precision@10)
5. Déployer modèle custom

**Dataset**:
```python
# training_data.jsonl

{"query": "validate email address", "positive_chunk_id": "abc123", "negative_chunk_ids": ["def456", "ghi789"]}
{"query": "check user permissions", "positive_chunk_id": "xyz123", "negative_chunk_ids": ["aaa111", "bbb222"]}
...
```

**Fine-Tuning Script**:
```python
from sentence_transformers import SentenceTransformer, InputExample, losses
from torch.utils.data import DataLoader

# Load base model
model = SentenceTransformer('nomic-ai/nomic-embed-text-v1.5')

# Prepare training data
train_examples = []
for item in training_data:
    query = item['query']
    positive_code = get_chunk_content(item['positive_chunk_id'])

    train_examples.append(InputExample(
        texts=[query, positive_code],
        label=1.0  # Similar
    ))

    # Add negative examples
    for neg_id in item['negative_chunk_ids']:
        negative_code = get_chunk_content(neg_id)
        train_examples.append(InputExample(
            texts=[query, negative_code],
            label=0.0  # Not similar
        ))

# Fine-tune
train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=16)
train_loss = losses.CosineSimilarityLoss(model)

model.fit(
    train_objectives=[(train_dataloader, train_loss)],
    epochs=3,
    warmup_steps=100,
    output_path='./models/mnemolite-code-search-v1'
)
```

**Métriques Attendues**:
- **Base model**: Recall@10 = 60-70%
- **Fine-tuned**: Recall@10 = 80-90% (+20-30%)

**Avantages**:
- ✅ Précision drastiquement améliorée
- ✅ Spécialisé pour notre domaine
- ✅ Comprend nos conventions de nommage

**Inconvénients**:
- ⚠️ Nécessite dataset de training (100+ queries)
- ⚠️ GPU requis pour fine-tuning
- ⚠️ Temps de training (~1-2 heures)

**Estimation**: 21 points de story (2 sprints - collecte data + training + eval)

---

### 4.2. LLM Reranking pour Précision Maximale

#### Problème
RRF fusion = simple, mais pas optimal.

#### Solution: LLM Reranking (GPT-4, Claude)

**Pipeline**:
```
Query: "validate email address"
    ↓
1. Hybrid Search (BM25 + Vector + RRF)
   → Top 20 results (fast, ~50ms)
    ↓
2. LLM Reranking (GPT-4/Claude)
   → Top 5 results (slow, ~500ms, mais très précis)
    ↓
Final Results: Optimal ranking
```

**Implementation**:
```python
# api/services/reranking_service.py

import anthropic

class ReRankingService:
    """LLM-based reranking for search results."""

    def __init__(self):
        self.client = anthropic.Anthropic()

    async def rerank_results(
        self,
        query: str,
        results: List[Dict],
        top_k: int = 5
    ) -> List[Dict]:
        """
        Rerank search results using Claude.

        Args:
            query: User query
            results: Top 20 results from hybrid search
            top_k: Number of results to return (default: 5)

        Returns:
            Reranked top_k results
        """
        # Prepare context for LLM
        context = f"""
Query: "{query}"

Code snippets to rank (most relevant first):

{self._format_results(results)}

Rank these code snippets by relevance to the query.
Return JSON: {{"rankings": [chunk_id1, chunk_id2, ...]}}
"""

        # Call Claude
        message = await self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=[{"role": "user", "content": context}]
        )

        # Parse rankings
        rankings = json.loads(message.content[0].text)['rankings']

        # Reorder results
        reranked = []
        for chunk_id in rankings[:top_k]:
            result = next(r for r in results if r['chunk_id'] == chunk_id)
            reranked.append(result)

        return reranked
```

**Métriques**:
- **Hybrid search**: Recall@5 = 70%, Latency = 50ms
- **+ LLM reranking**: Recall@5 = 90% (+20%), Latency = 550ms (+500ms)

**Coût**:
- Claude API: $0.015 per 1K tokens
- ~1K tokens per reranking request
- ~$0.015 per search (acceptable pour production)

**Avantages**:
- ✅ Précision maximale (90%+ recall)
- ✅ Comprend nuances sémantiques
- ✅ Peut expliquer pourquoi un résultat est pertinent

**Inconvénients**:
- ⚠️ Latency élevée (+500ms)
- ⚠️ Coût par requête ($0.015)
- ⚠️ Dépendance API externe

**Recommendation**: Activer optionnellement (`enable_llm_reranking=true`).

**Estimation**: 8 points de story (1 sprint)

---

### 4.3. Query Expansion (Synonymes, Acronymes)

#### Problème
Queries avec acronymes ou synonymes rares = résultats manqués.

#### Solution: Expansion Automatique

```python
# api/services/query_expansion_service.py

class QueryExpansionService:
    """Expand queries with synonyms and acronyms."""

    ACRONYMS = {
        'JWT': 'JSON Web Token',
        'ORM': 'Object Relational Mapping',
        'API': 'Application Programming Interface',
        'SQL': 'Structured Query Language',
        'XSS': 'Cross Site Scripting',
        # ... 100+ acronyms
    }

    SYNONYMS = {
        'validate': ['check', 'verify', 'confirm', 'test'],
        'authentication': ['auth', 'login', 'credentials'],
        'authorization': ['authz', 'permissions', 'access control'],
        # ... 500+ synonyms
    }

    def expand_query(self, query: str) -> List[str]:
        """
        Expand query with synonyms and acronym expansions.

        Returns:
            List of expanded queries
        """
        expanded = [query]  # Original query

        # Expand acronyms
        for acronym, expansion in self.ACRONYMS.items():
            if acronym in query:
                expanded.append(query.replace(acronym, expansion))

        # Add synonym variations
        words = query.split()
        for i, word in enumerate(words):
            if word.lower() in self.SYNONYMS:
                for synonym in self.SYNONYMS[word.lower()]:
                    variant = words.copy()
                    variant[i] = synonym
                    expanded.append(' '.join(variant))

        return expanded
```

**Usage**:
```python
# Original query
query = "validate JWT token"

# Expanded queries
expanded = query_expansion_svc.expand_query(query)
# [
#   "validate JWT token",
#   "validate JSON Web Token token",  # Acronym expansion
#   "check JWT token",                 # Synonym: validate → check
#   "verify JWT token",                # Synonym: validate → verify
#   "confirm JWT token"                # Synonym: validate → confirm
# ]

# Search with all expanded queries (merge results)
all_results = []
for q in expanded:
    results = await search_hybrid(q)
    all_results.extend(results)

# Deduplicate and rerank
final_results = deduplicate_and_rank(all_results)
```

**Avantages**:
- ✅ Meilleur recall (trouve plus de résultats)
- ✅ Robuste aux variations de vocabulaire
- ✅ Gratuit (pas d'API externe)

**Inconvénients**:
- ⚠️ Latency +20-30% (multiple queries)
- ⚠️ Précision peut baisser (faux positifs)

**Estimation**: 5 points de story (2-3 jours)

---

## 🔬 PARTIE 5: Tests & Monitoring (Sprint +4)

### 5.1. Tests de Charge (Load Testing)

#### Objectif
Mesurer performance sous charge réelle (1000+ queries/s).

#### Tools: Locust

```python
# tests/load/locustfile.py

from locust import HttpUser, task, between

class CodeSearchUser(HttpUser):
    wait_time = between(0.1, 0.5)  # 0.1-0.5s entre requêtes

    @task(weight=10)
    def search_hybrid(self):
        """Test hybrid search (most common)."""
        self.client.post("/v1/code/search/hybrid", json={
            "query": "validate email address",
            "repository": "test-repo",
            "limit": 10
        })

    @task(weight=3)
    def search_lexical(self):
        """Test lexical-only search."""
        self.client.post("/v1/code/search/hybrid", json={
            "query": "check format",
            "repository": "test-repo",
            "enable_vector": False
        })

    @task(weight=1)
    def generate_embedding(self):
        """Test embedding generation."""
        self.client.post("/v1/embeddings/generate", json={
            "query": "SQL injection detection"
        })
```

**Exécution**:
```bash
# Test avec 100 users simultanés
locust -f tests/load/locustfile.py \
       --host http://localhost:8001 \
       --users 100 \
       --spawn-rate 10 \
       --run-time 5m \
       --html report.html
```

**Métriques à Mesurer**:
- **RPS** (Requests Per Second): Target > 100 RPS
- **P50 latency**: < 50ms
- **P95 latency**: < 200ms
- **P99 latency**: < 500ms
- **Error rate**: < 1%

**Estimation**: 5 points de story (2-3 jours)

---

### 5.2. Tests de Précision (Recall, Precision, F1)

#### Objectif
Mesurer qualité des résultats de recherche.

#### Dataset de Test

```python
# tests/precision/test_queries.json

[
  {
    "query": "validate email address",
    "expected_results": [
      "EmailValidator.validateEmail",
      "checkEmailFormat",
      "isValidEmail"
    ],
    "category": "exact_match"
  },
  {
    "query": "check user permissions",
    "expected_results": [
      "AuthService.checkPermissions",
      "hasPermission",
      "canAccess"
    ],
    "category": "synonym"
  },
  {
    "query": "SQL injection vulnerability",
    "expected_results": [
      "detectSQLInjection",
      "sanitizeInput",
      "executeRawQuery"
    ],
    "category": "concept"
  }
  // ... 100+ test queries
]
```

**Evaluation Script**:
```python
# tests/precision/evaluate.py

async def evaluate_search_quality():
    """Evaluate search precision and recall."""

    results = []

    for test_case in load_test_queries():
        # Perform search
        response = await search_hybrid(
            query=test_case['query'],
            repository='test-repo'
        )

        # Extract chunk IDs
        retrieved = [r['name'] for r in response['results'][:10]]
        expected = test_case['expected_results']

        # Calculate metrics
        tp = len(set(retrieved) & set(expected))  # True positives
        fp = len(set(retrieved) - set(expected))  # False positives
        fn = len(set(expected) - set(retrieved))  # False negatives

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

        results.append({
            'query': test_case['query'],
            'category': test_case['category'],
            'precision': precision,
            'recall': recall,
            'f1': f1
        })

    # Aggregate by category
    print_metrics_by_category(results)
```

**Targets**:
- **Exact match**: Recall@10 > 95%
- **Synonym**: Recall@10 > 80%
- **Concept**: Recall@10 > 60%
- **Overall F1**: > 0.75

**Estimation**: 8 points de story (3-5 jours - création dataset + éval)

---

### 5.3. Monitoring Temps Réel (Prometheus + Grafana)

#### Objectif
Visualiser performance et détecter anomalies.

#### Metrics à Exposer

```python
# api/metrics.py

from prometheus_client import Counter, Histogram, Gauge

# Search metrics
search_requests_total = Counter(
    'search_requests_total',
    'Total number of search requests',
    ['method', 'status']  # labels: lexical/vector/hybrid, success/error
)

search_duration_seconds = Histogram(
    'search_duration_seconds',
    'Search request duration',
    ['method'],
    buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 5.0]
)

# Embedding metrics
embedding_generation_seconds = Histogram(
    'embedding_generation_seconds',
    'Embedding generation time',
    ['domain'],  # TEXT or CODE
    buckets=[0.005, 0.01, 0.02, 0.05, 0.1, 0.5]
)

embedding_cache_hits_total = Counter(
    'embedding_cache_hits_total',
    'Embedding cache hits',
    ['result']  # hit or miss
)

# Model metrics
model_loaded = Gauge(
    'model_loaded',
    'Whether model is loaded (1) or not (0)',
    ['model_name']
)

model_memory_bytes = Gauge(
    'model_memory_bytes',
    'Model memory usage in bytes',
    ['model_name']
)
```

**Grafana Dashboard**:
```json
{
  "dashboard": {
    "title": "MnemoLite Embedding Search",
    "panels": [
      {
        "title": "Search RPS",
        "targets": ["rate(search_requests_total[1m])"]
      },
      {
        "title": "Search Latency (P95)",
        "targets": ["histogram_quantile(0.95, search_duration_seconds)"]
      },
      {
        "title": "Embedding Cache Hit Rate",
        "targets": ["rate(embedding_cache_hits_total{result='hit'}[5m]) / rate(embedding_cache_hits_total[5m])"]
      },
      {
        "title": "Model Memory Usage",
        "targets": ["model_memory_bytes"]
      }
    ]
  }
}
```

**Alerts**:
```yaml
# prometheus/alerts.yml

groups:
  - name: search_performance
    interval: 30s
    rules:
      - alert: HighSearchLatency
        expr: histogram_quantile(0.95, search_duration_seconds) > 0.5
        for: 2m
        annotations:
          summary: "Search P95 latency > 500ms"

      - alert: LowCacheHitRate
        expr: rate(embedding_cache_hits_total{result='hit'}[5m]) / rate(embedding_cache_hits_total[5m]) < 0.3
        for: 5m
        annotations:
          summary: "Embedding cache hit rate < 30%"

      - alert: HighErrorRate
        expr: rate(search_requests_total{status='error'}[5m]) > 0.05
        for: 2m
        annotations:
          summary: "Search error rate > 5%"
```

**Estimation**: 5 points de story (2-3 jours)

---

## 🌟 PARTIE 6: DX & Usability (Sprint +5)

### 6.1. CLI Tool pour Tests Locaux

#### Objectif
Permettre aux devs de tester embeddings sans lancer l'API.

#### Implementation

```python
# cli/mnemolite_cli.py

import click
from services.dual_embedding_service import DualEmbeddingService, EmbeddingDomain

@click.group()
def cli():
    """MnemoLite CLI - Test embeddings locally."""
    pass

@cli.command()
@click.argument('text')
@click.option('--domain', type=click.Choice(['text', 'code', 'hybrid']), default='text')
@click.option('--compress', is_flag=True, help='Output compressed (INT8) embedding')
def embed(text: str, domain: str, compress: bool):
    """Generate embedding for text."""
    click.echo(f"Generating {domain.upper()} embedding for: {text}")

    svc = DualEmbeddingService()
    domain_enum = EmbeddingDomain[domain.upper()]

    result = asyncio.run(svc.generate_embedding(text, domain_enum))

    if compress:
        from services.embedding_compression_service import EmbeddingCompressionService
        compressed = EmbeddingCompressionService.quantize(result['text'])
        click.echo(f"\nCompressed embedding (INT8 base64):\n{compressed}")
    else:
        click.echo(f"\nEmbedding (768D FP32):\n{result}")

@cli.command()
@click.argument('query')
@click.argument('code')
def similarity(query: str, code: str):
    """Calculate semantic similarity between query and code."""
    svc = DualEmbeddingService()

    # Generate embeddings
    query_emb = asyncio.run(svc.generate_embedding(query, EmbeddingDomain.TEXT))
    code_emb = asyncio.run(svc.generate_embedding(code, EmbeddingDomain.CODE))

    # Calculate cosine similarity
    from numpy import dot
    from numpy.linalg import norm

    q = query_emb['text']
    c = code_emb['code']

    similarity = dot(q, c) / (norm(q) * norm(c))

    click.echo(f"\nQuery: {query}")
    click.echo(f"Code: {code[:100]}...")
    click.echo(f"\nSemantic Similarity: {similarity:.4f}")

    if similarity > 0.8:
        click.secho("✅ HIGHLY RELEVANT", fg='green', bold=True)
    elif similarity > 0.6:
        click.secho("⚡ MODERATELY RELEVANT", fg='yellow', bold=True)
    else:
        click.secho("❌ NOT RELEVANT", fg='red', bold=True)

if __name__ == '__main__':
    cli()
```

**Usage**:
```bash
# Generate embedding
$ mnemolite embed "validate email address" --domain text

# Calculate similarity
$ mnemolite similarity "check email format" "function validateEmail(email) { ... }"
Semantic Similarity: 0.8723
✅ HIGHLY RELEVANT

# Compress embedding
$ mnemolite embed "SQL injection" --compress
Compressed embedding (INT8 base64):
eJxTYGBgYGBgYGBgYGBgYGBgYGBgY...
```

**Estimation**: 3 points de story (1-2 jours)

---

### 6.2. Interactive Playground Web

#### Objectif
Interface web pour tester recherche sémantique sans code.

#### UI Features

```html
<!-- templates/embedding_playground.html -->

<div class="playground">
  <h1>🧪 Embedding Search Playground</h1>

  <!-- Query Input -->
  <div class="query-section">
    <label>Query:</label>
    <input type="text" id="query" placeholder="validate email address" />
    <button onclick="search()">Search</button>
  </div>

  <!-- Options -->
  <div class="options">
    <label><input type="checkbox" id="lexical" checked /> Lexical (BM25)</label>
    <label><input type="checkbox" id="vector" checked /> Vector (Embeddings)</label>
    <label><input type="checkbox" id="llm_rerank" /> LLM Reranking</label>
  </div>

  <!-- Results -->
  <div class="results">
    <div class="result-card" data-rank="1">
      <div class="score">RRF: 0.0322</div>
      <div class="name">EmailValidator.validateEmail()</div>
      <div class="path">auth/validators/email-validator.ts</div>
      <div class="snippet">
        <code>
          public validateEmail(email: string): boolean {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            return emailRegex.test(email);
          }
        </code>
      </div>
      <div class="contributions">
        <span class="lexical">Lexical: 0.357</span>
        <span class="vector">Vector: 0.872</span>
      </div>
    </div>
  </div>

  <!-- Embedding Visualization -->
  <div class="embedding-viz">
    <h3>Query Embedding (768D)</h3>
    <canvas id="embedding-plot"></canvas>
    <small>PCA projection to 2D for visualization</small>
  </div>
</div>
```

**Estimation**: 8 points de story (3-5 jours)

---

## 📊 PARTIE 7: Roadmap & Priorisation

### Priority Matrix (Effort vs Impact)

```
HIGH IMPACT
    │
    │   P1: Auto-Embed      P2: Compression
    │   (2-3pts)            (5pts)
    │         ╭─────────╮         ╭─────────╮
    │         │ QUICK   │         │ MEDIUM  │
    │         │  WIN    │         │ EFFORT  │
    │         ╰─────────╯         ╰─────────╯
    │
    │   P3: Cache Redis   P4: Lazy Load
    │   (2pts)            (3pts)
    │         ╭─────────╮         ╭─────────╮
────┼─────────┤ QUICK   ├─────────┤ MEDIUM  ├─────── EFFORT
    │         │  WIN    │         │ EFFORT  │
    │         ╰─────────╯         ╰─────────╯
    │
    │   P5: Monitoring    P6: Fine-Tuning
    │   (5pts)            (21pts)
    │         ╭─────────╮         ╭─────────╮
    │         │ MEDIUM  │         │  HIGH   │
    │         │ EFFORT  │         │ EFFORT  │
LOW IMPACT  ╰─────────╯         ╰─────────╯
```

### Sprints Recommandés

#### Sprint N (Courant) - CRITICAL FIXES
**Objectif**: Rendre les embeddings utilisables en production

- ✅ P1: Auto-Embed dans API (2-3 pts) → **MUST HAVE**
- ✅ P3: Cache Redis queries (2 pts) → **QUICK WIN**
- ✅ P2: Compression INT8 (5 pts) → **IMPORTANT**

**Total**: 9-10 points
**Deliverables**:
- `/v1/code/search/hybrid` auto-génère embeddings
- Cache Redis pour queries fréquentes
- Embeddings compressés (6x plus petits)

---

#### Sprint N+1 - PERFORMANCE
**Objectif**: Optimiser latency et throughput

- ✅ P4: Lazy loading modèles (3 pts)
- ✅ Batch API embeddings (3 pts)
- ✅ Monitoring Prometheus (5 pts)

**Total**: 11 points
**Deliverables**:
- Startup 0ms (lazy load)
- API batch pour indexation
- Dashboard Grafana

---

#### Sprint N+2 - ARCHITECTURE
**Objectif**: Scalabilité horizontale

- ✅ Microservice embeddings (13 pts)
- ✅ Queue async Celery (13 pts)

**Total**: 26 points (2 sprints)
**Deliverables**:
- Service embeddings dédié (GPU)
- Indexation asynchrone (pas de timeout)

---

#### Sprint N+3/N+4 - QUALITÉ
**Objectif**: Maximiser précision des résultats

- ✅ Fine-tuning modèles (21 pts)
- ✅ LLM reranking (8 pts)
- ✅ Query expansion (5 pts)
- ✅ Tests de précision (8 pts)

**Total**: 42 points (2 sprints)
**Deliverables**:
- Modèle custom fine-tuned (recall +20%)
- Reranking Claude (recall 90%+)
- Dataset de test (100+ queries)

---

## 🎓 Conclusion & Next Steps

### Résumé des Optimisations

| Catégorie | Optimisation | Impact | Effort | Priority |
|-----------|-------------|--------|--------|----------|
| **API Design** | Auto-embed queries | ⭐⭐⭐⭐⭐ | 2-3 pts | P1 |
| **Performance** | Compression INT8 | ⭐⭐⭐⭐ | 5 pts | P2 |
| **Cache** | Redis query cache | ⭐⭐⭐⭐ | 2 pts | P3 |
| **Startup** | Lazy loading | ⭐⭐⭐ | 3 pts | P4 |
| **Monitoring** | Prometheus + Grafana | ⭐⭐⭐ | 5 pts | P5 |
| **Architecture** | Microservice dédié | ⭐⭐⭐⭐ | 13 pts | P6 |
| **Async** | Celery queue | ⭐⭐⭐⭐ | 13 pts | P7 |
| **Qualité** | Fine-tuning custom | ⭐⭐⭐⭐⭐ | 21 pts | P8 |
| **Qualité** | LLM reranking | ⭐⭐⭐⭐ | 8 pts | P9 |
| **Performance** | GPU acceleration | ⭐⭐⭐ | 5 pts | P10 |

### Métriques de Succès

**Baseline (Actuel)**:
- ❌ Timeout avec embeddings JSON (>30s)
- ⚠️ Startup 30-40s
- ⚠️ Recall@10: 60-70%
- ⚠️ Cache hit: 0% (pas de cache)

**Target (Sprint N+4)**:
- ✅ Pas de timeout (<200ms)
- ✅ Startup 0ms (lazy)
- ✅ Recall@10: 85-90% (fine-tuned)
- ✅ Cache hit: 40-50%
- ✅ Throughput: 100+ RPS
- ✅ P95 latency: <200ms

### Prochaine Action Immédiate

**Sprint Planning Meeting**:
1. Présenter ce document ULTRATHINK à l'équipe
2. Valider priorités (P1-P3 pour sprint courant)
3. Créer stories dans backlog
4. Estimer points de complexité
5. Commencer par P1 (Auto-Embed) → CRITICAL

---

**Document Version**: 1.0
**Révisions**: À mettre à jour après chaque sprint
**Prochaine Review**: Sprint N+1 Retrospective
