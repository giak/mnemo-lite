# Guide: Recherche Sémantique avec Embeddings

**Dernière mise à jour**: 2025-10-23
**EPIC**: EPIC-18 - Embedding Mode Fix + Documentation

---

## 📚 Introduction

Ce guide explique comment utiliser la recherche sémantique avec embeddings dans MnemoLite.

### Qu'est-ce que la Recherche Sémantique?

**Recherche Lexicale (BM25)**: Trouve par mots exacts
```
Query: "check email format"
Code: validateEmail()
Match: ❌ NON (pas les mots "check" ou "format")
```

**Recherche Sémantique (Embeddings)**: Comprend le sens
```
Query: "check email format"
Code: validateEmail()
Match: ✅ OUI (comprend que "check" ≈ "validate")
```

---

## 🚀 Usage Basique

### Exemple Minimal (3 lignes)

```python
from services.dual_embedding_service import DualEmbeddingService, EmbeddingDomain
from services.hybrid_code_search_service import HybridCodeSearchService

async def search_code_semantic(query: str, repository: str):
    """
    Recherche sémantique simple.

    Args:
        query: Question en langage naturel ("validate email address")
        repository: Nom du repository à chercher

    Returns:
        Liste de résultats avec scores RRF
    """
    # 1. Generate query embedding
    embedding_svc = DualEmbeddingService()
    result = await embedding_svc.generate_embedding(query, EmbeddingDomain.TEXT)

    # 2. Search with hybrid (lexical + semantic)
    search_svc = HybridCodeSearchService()
    results = await search_svc.search_hybrid(
        query=query,
        embedding_text=result['text'],  # 768D vector
        filters={'repository': repository},
        top_k=10
    )

    return results


# Usage
results = await search_code_semantic("validate email address", "my-repo")

for result in results:
    print(f"{result['name']} - Score: {result['rrf_score']:.4f}")
    print(f"  File: {result['file_path']}")
    print(f"  Type: {result['chunk_type']}")
```

---

## 🔧 Configuration: Mock vs Real

### Mode Mock (Développement & Tests)

**Avantages**:
- ✅ Startup instantané (~0ms)
- ✅ Pas de chargement de modèles ML
- ✅ Tests 80x plus rapides
- ✅ Embeddings déterministes (hash-based)

**Inconvénients**:
- ⚠️ Recherche quasi-aléatoire (pas de vraie sémantique)

**Configuration**:
```bash
# .env
EMBEDDING_MODE=mock
```

**Utilisation**:
```python
# Les embeddings sont générés instantanément par hash
embedding_svc = DualEmbeddingService()
result = await embedding_svc.generate_embedding("test", EmbeddingDomain.TEXT)
# Temps: ~0ms
# Résultat: Déterministe (même query → même embedding)
```

---

### Mode Real (Production)

**Avantages**:
- ✅ Vraie recherche sémantique
- ✅ Comprend synonymes, concepts
- ✅ Résultats pertinents

**Inconvénients**:
- ⚠️ Startup lent (~30-40s, chargement modèles ML)
- ⚠️ Mémoire élevée (~2.5 GB)
- ⚠️ Génération embedding: ~10-20ms par query

**Configuration**:
```bash
# .env
EMBEDDING_MODE=real

# Modèles utilisés (automatique)
TEXT_EMBEDDING_MODEL=nomic-ai/nomic-embed-text-v1.5
CODE_EMBEDDING_MODEL=jinaai/jina-embeddings-v2-base-code
EMBEDDING_DIMENSION=768
```

**Utilisation**:
```python
# Les embeddings sont générés par modèles ML
embedding_svc = DualEmbeddingService()
result = await embedding_svc.generate_embedding("validate email", EmbeddingDomain.TEXT)
# Temps: ~10-20ms (première fois après startup)
# Résultat: Sémantiquement significatif (768D vector)
```

---

## 📖 Exemples Pratiques

### Exemple 1: Recherche Simple

```python
async def find_validation_functions():
    """Trouve toutes les fonctions de validation."""

    results = await search_code_semantic(
        query="validate input data",
        repository="backend-api"
    )

    # Résultats attendus:
    # - validateEmail()
    # - checkUserInput()
    # - verifyDataFormat()
    # - sanitizeInput()

    return results
```

---

### Exemple 2: Recherche par Concept

```python
async def find_security_vulnerabilities():
    """Trouve du code lié à la sécurité SQL."""

    results = await search_code_semantic(
        query="SQL injection vulnerability detection",
        repository="backend-api"
    )

    # Résultats attendus (même sans mots "SQL injection"):
    # - detectSQLInjection()
    # - sanitizeQuery()
    # - executeRawQuery()
    # - escapeUserInput()

    return results
```

---

### Exemple 3: Recherche Multi-Repository

```python
async def search_across_repositories(query: str, repos: list[str]):
    """Cherche dans plusieurs repositories."""

    all_results = []

    for repo in repos:
        results = await search_code_semantic(query, repo)
        all_results.extend(results)

    # Sort by RRF score (best first)
    all_results.sort(key=lambda r: r['rrf_score'], reverse=True)

    return all_results[:10]  # Top 10


# Usage
results = await search_across_repositories(
    "authentication middleware",
    repos=["backend-api", "auth-service", "gateway"]
)
```

---

### Exemple 4: Filtrer par Type de Code

```python
async def find_only_functions(query: str):
    """Trouve uniquement des fonctions (pas de classes)."""

    embedding_svc = DualEmbeddingService()
    result = await embedding_svc.generate_embedding(query, EmbeddingDomain.TEXT)

    search_svc = HybridCodeSearchService()
    results = await search_svc.search_hybrid(
        query=query,
        embedding_text=result['text'],
        filters={
            'repository': 'my-repo',
            'chunk_type': 'function'  # Filtre par type
        },
        top_k=10
    )

    return results
```

---

### Exemple 5: Recherche avec Seuil de Pertinence

```python
async def find_highly_relevant_only(query: str, min_score: float = 0.015):
    """Retourne uniquement les résultats très pertinents."""

    results = await search_code_semantic(query, "my-repo")

    # Filtre par RRF score minimum
    filtered = [r for r in results if r['rrf_score'] >= min_score]

    return filtered


# Usage
results = await find_highly_relevant_only(
    "validate email format",
    min_score=0.020  # Seuil élevé
)
```

---

## 🧪 Testing

### Test Unitaire (Mock Mode)

```python
import pytest
from services.dual_embedding_service import DualEmbeddingService, EmbeddingDomain

@pytest.mark.asyncio
async def test_embedding_generation_mock():
    """Test génération embedding en mode mock."""

    svc = DualEmbeddingService()

    # Generate embedding
    result = await svc.generate_embedding("test query", EmbeddingDomain.TEXT)

    # Assertions
    assert 'text' in result
    assert len(result['text']) == 768  # 768 dimensions
    assert all(isinstance(x, float) for x in result['text'])

    # Test déterminisme (mock mode)
    result2 = await svc.generate_embedding("test query", EmbeddingDomain.TEXT)
    assert result['text'] == result2['text']  # Même query → même embedding
```

---

### Test d'Intégration (Real Mode)

```python
@pytest.mark.asyncio
@pytest.mark.slow  # Tag pour tests lents
async def test_semantic_search_end_to_end():
    """Test complet: indexation → search avec embeddings."""

    # 1. Index sample code
    indexing_svc = CodeIndexingService()
    await indexing_svc.index_files(
        repository="test-repo",
        files=[{
            "path": "validators.py",
            "content": "def validate_email(email): return '@' in email",
            "language": "python"
        }]
    )

    # 2. Search with semantic query
    results = await search_code_semantic("check email format", "test-repo")

    # 3. Assertions
    assert len(results) > 0, "Should find at least one result"
    assert any('email' in r['name'].lower() for r in results)
    assert results[0]['rrf_score'] > 0
```

---

## 🐛 Debugging

### Vérifier Mode d'Embedding

```python
import os

mode = os.getenv('EMBEDDING_MODE', 'mock')
print(f"Embedding mode: {mode}")

# En production
assert mode == 'real', "Production should use real embeddings"
```

---

### Logs d'Embedding

```python
# Les logs montrent automatiquement:
# - Mode (mock/real)
# - Temps de génération
# - Dimension

# Exemple de log:
# INFO: Embedding generated (mode=real, time=15.3ms, dim=768)
```

---

### Comparer Lexical vs Semantic

```python
async def compare_search_methods(query: str):
    """Compare recherche lexicale seule vs hybride."""

    # 1. Lexical only
    lexical_results = await search_svc.search_hybrid(
        query=query,
        enable_lexical=True,
        enable_vector=False  # Désactive semantic
    )

    # 2. Hybrid (lexical + semantic)
    hybrid_results = await search_code_semantic(query, "my-repo")

    print(f"Lexical only: {len(lexical_results)} results")
    print(f"Hybrid: {len(hybrid_results)} results")

    # Compare top result
    if lexical_results and hybrid_results:
        print(f"\nTop lexical: {lexical_results[0]['name']}")
        print(f"Top hybrid: {hybrid_results[0]['name']}")
```

---

## ⚠️ Limitations & Best Practices

### ❌ NE PAS Faire

**1. N'envoyez PAS d'embeddings dans les requêtes HTTP JSON**
```python
# ❌ MAUVAIS - Timeout garanti (>30s)
await client.post("/v1/code/search/hybrid", json={
    "query": "validate email",
    "embedding_text": [0.12, -0.45, ..., 0.23]  # 768 floats!
})
```

**Raison**: Trop lourd (6 KB JSON), sérialisation coûteuse.

**✅ À la place**: Générez l'embedding côté serveur (voir exemples ci-dessus).

---

**2. N'utilisez PAS Real Mode pour les Tests**
```python
# ❌ MAUVAIS - Tests très lents (30s+ par suite)
EMBEDDING_MODE=real pytest tests/
```

**✅ À la place**: Utilisez Mock Mode pour tests rapides
```bash
EMBEDDING_MODE=mock pytest tests/  # 80x plus rapide
```

---

**3. Ne Rechargez PAS les Modèles à Chaque Requête**
```python
# ❌ MAUVAIS - Recharge 2.5GB à chaque fois!
async def search_bad(query):
    svc = DualEmbeddingService()  # ❌ Nouveau à chaque fois
    await svc.preload_models()    # ❌ Recharge modèles
    return await svc.generate_embedding(query, ...)
```

**✅ À la place**: Réutilisez l'instance (singleton)
```python
# ✅ BON - Instance réutilisée
embedding_svc = DualEmbeddingService()  # Une fois au startup

async def search_good(query):
    return await embedding_svc.generate_embedding(query, ...)
```

---

### ✅ Best Practices

**1. Cache les Embeddings Fréquents**
```python
# Pour queries fréquentes, considérez un cache simple
embedding_cache = {}

async def get_embedding_cached(query: str):
    if query in embedding_cache:
        return embedding_cache[query]

    result = await embedding_svc.generate_embedding(query, EmbeddingDomain.TEXT)
    embedding_cache[query] = result
    return result
```

---

**2. Timeout Raisonnable**
```python
import asyncio

async def search_with_timeout(query: str, timeout_sec: float = 5.0):
    """Recherche avec timeout pour éviter blocages."""
    try:
        return await asyncio.wait_for(
            search_code_semantic(query, "my-repo"),
            timeout=timeout_sec
        )
    except asyncio.TimeoutError:
        logger.warning(f"Search timeout for query: {query}")
        return []
```

---

**3. Gestion d'Erreurs Graceful**
```python
async def search_robust(query: str):
    """Recherche avec fallback sur erreur."""
    try:
        # Try semantic search
        return await search_code_semantic(query, "my-repo")
    except Exception as e:
        logger.error(f"Semantic search failed: {e}, falling back to lexical")

        # Fallback: lexical only
        return await search_svc.search_hybrid(
            query=query,
            enable_lexical=True,
            enable_vector=False
        )
```

---

## 📊 Performance

### Temps de Génération d'Embeddings

| Mode | Startup | Par Query | Use Case |
|------|---------|-----------|----------|
| **Mock** | ~0ms | ~0ms | Tests, dev |
| **Real** | 30-40s | 10-20ms | Production |

### Latency Search Complète

| Méthode | Latency Typique | Use Case |
|---------|-----------------|----------|
| **Lexical only** | 20-50ms | Recherche rapide, mots exacts |
| **Hybrid (cached)** | 25-60ms | Meilleur des deux mondes |
| **Hybrid (no cache)** | 35-80ms | Première recherche |

---

## 🔗 Liens Utiles

- **Architecture**: `docs/arch/embedding_architecture.md`
- **Tests**: `tests/integration/test_embedding_search.py`
- **API**: `api/routes/code_search_routes.py`
- **Service**: `api/services/dual_embedding_service.py`

---

## ❓ FAQ

**Q: Pourquoi startup 30-40s en mode real?**
A: Chargement des 2 modèles ML (2.5GB). Normal pour production, fait 1x au déploiement.

**Q: Comment savoir si mes embeddings fonctionnent?**
A: Comparez résultats avec/sans embeddings (voir section Debugging).

**Q: Les embeddings sont-ils cachés?**
A: Non par défaut. Génération rapide (10-20ms), cache pas nécessaire sauf queries très fréquentes.

**Q: Puis-je utiliser uniquement semantic (sans lexical)?**
A: Oui, mais **non recommandé**. Hybrid (lexical + semantic) donne les meilleurs résultats.

**Q: Comment mesurer la qualité des résultats?**
A: Voir `tests/precision/evaluate.py` pour métriques Recall@K, Precision, F1.

---

**Version**: 1.0
**Dernière mise à jour**: 2025-10-23
**Prochaine révision**: Après 1 mois d'usage production
