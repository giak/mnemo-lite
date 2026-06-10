# SPEC : Centralisation Configuration Embedding — Design

> **Date:** 2026-06-10
> **Feature:** Configuration d'embedding centralisée
> **Priority:** P0
> **Inspiration:** pydantic-settings, FastAPI dependency injection, 12-factor app

## 1. Overview

### 1.1 Problème

19 fichiers avec des hardcodes de dimensions (`768`, `1024`), noms de modèles, et `os.getenv` éparpillés. Aucune validation de cohérence entre `.env` et les services.

### 1.2 Solution

Module `api/core/` contenant :
- **Registre statique** (`embedding_models.py`) : mapping modèle → dimension, backend
- **Configuration validée** (`settings.py`) : Pydantic BaseSettings avec auto-déduction

### 1.3 Bénéfices

| Métrique | Current | Target |
|----------|---------|--------|
| Fichiers à modifier pour changer de modèle | 5-10 | 1 (`.env`) |
| Temps de debug mismatch dimension | ~30 min | 0 (crash explicite) |
| Hardcodes `768`/`1024` | 19 fichiers | 0 |
| Duplication de la liste des modèles | 3 endroits | 1 (`embedding_models.py`) |

## 2. Architecture

### 2.1 Module `api/core/`

```
api/core/
├── __init__.py              # Exporte get_settings, KNOWN_MODELS
├── embedding_models.py      # Registre statique
└── settings.py              # Pydantic BaseSettings + validation
```

### 2.2 Registre des modèles (`embedding_models.py`)

```python
"""Registre central des modèles d'embedding supportés.

Single Source of Truth pour les dimensions, backends, et préfixes.
Ajouter un nouveau modèle = 1 ligne ici. Tout le reste auto-déduit.
"""
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class ModelSpec:
    """Spécification immuable d'un modèle d'embedding."""
    name: str
    dimension: int
    backend: str = "pytorch"  # pytorch | onnx
    max_seq_length: int = 512
    query_prefix: str = ""
    document_prefix: str = ""
    trust_remote_code: bool = False

# Registre unique — source de vérité pour tous les modèles
KNOWN_MODELS: dict[str, ModelSpec] = {
    # BGE series (BAAI) — multilingue, dense+sparse+ColBERT
    "BAAI/bge-m3": ModelSpec(
        name="BAAI/bge-m3",
        dimension=1024,
        backend="pytorch",
        max_seq_length=8192,
        query_prefix="Represent this sentence for retrieving relevant documents: ",
        document_prefix="Represent this passage for retrieval: ",
        trust_remote_code=True,
    ),
    
    # Nomic series — 768D, English-optimized
    "nomic-ai/nomic-embed-text-v1.5": ModelSpec(
        name="nomic-ai/nomic-embed-text-v1.5",
        dimension=768,
        backend="pytorch",
        max_seq_length=2048,
        trust_remote_code=True,
    ),
    "nomic-ai/nomic-embed-text-v2-moe": ModelSpec(
        name="nomic-ai/nomic-embed-text-v2-moe",
        dimension=768,
        backend="pytorch",
        max_seq_length=2048,
        trust_remote_code=True,
    ),
    
    # E5 series (intfloat) — multilingue
    "intfloat/multilingual-e5-base": ModelSpec(
        name="intfloat/multilingual-e5-base",
        dimension=768,
        backend="pytorch",
        max_seq_length=512,
        query_prefix="query: ",
        document_prefix="passage: ",
    ),
    "intfloat/multilingual-e5-large": ModelSpec(
        name="intfloat/multilingual-e5-large",
        dimension=1024,
        backend="pytorch",
        max_seq_length=512,
        query_prefix="query: ",
        document_prefix="passage: ",
    ),
    "intfloat/multilingual-e5-small": ModelSpec(
        name="intfloat/multilingual-e5-small",
        dimension=384,
        backend="pytorch",
        max_seq_length=512,
        query_prefix="query: ",
        document_prefix="passage: ",
    ),
    
    # Jina series — code + text
    "jinaai/jina-embeddings-v2-base-code": ModelSpec(
        name="jinaai/jina-embeddings-v2-base-code",
        dimension=768,
        backend="pytorch",
        max_seq_length=8192,
        trust_remote_code=True,
    ),
    "jinaai/jina-embeddings-v5-text-small": ModelSpec(
        name="jinaai/jina-embeddings-v5-text-small",
        dimension=1024,
        backend="pytorch",
        max_seq_length=8192,
    ),
    "jinaai/jina-embeddings-v5-text-nano": ModelSpec(
        name="jinaai/jina-embeddings-v5-text-nano",
        dimension=768,
        backend="pytorch",
        max_seq_length=8192,
    ),
}

def get_model_spec(model_name: str) -> Optional[ModelSpec]:
    """Récupère la spec d'un modèle, ou None si inconnu."""
    return KNOWN_MODELS.get(model_name)
```

### 2.3 Configuration validée (`settings.py`)

```python
"""Configuration centralisée de l'application.

Single Source of Truth pour toutes les variables d'environnement.
Lit .env, valide la cohérence, auto-déduit les dimensions.
Crash au démarrage si config incohérente.
"""
from functools import lru_cache
from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from api.core.embedding_models import KNOWN_MODELS, ModelSpec


class AppSettings(BaseSettings):
    """Configuration centralisée de MnemoLite."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore les vars non déclarées
        case_sensitive=True,
    )
    
    # === Modèle d'embedding texte (principal) ===
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIMENSION: Optional[int] = None  # Auto-déduit si None
    EMBEDDING_BACKEND: Optional[str] = None     # Auto-déduit si None
    EMBEDDING_MODE: str = "real"  # real | mock
    
    # === Modèle d'embedding code (DualEmbeddingService) ===
    CODE_EMBEDDING_MODEL: str = "jinaai/jina-embeddings-v2-base-code"
    CODE_EMBEDDING_DIMENSION: Optional[int] = None
    
    # === Base de données ===
    DATABASE_URL: str = ""
    TEST_DATABASE_URL: str = ""
    REDIS_URL: str = "redis://redis:6379/0"
    
    # === Environnement ===
    ENVIRONMENT: str = "development"
    
    @model_validator(mode="after")
    def validate_embedding_config(self):
        """Valide et auto-déduit la configuration d'embedding."""
        
        # 1. Validation modèle texte principal
        text_spec = KNOWN_MODELS.get(self.EMBEDDING_MODEL)
        if text_spec:
            # Vérifie cohérence dimension
            if self.EMBEDDING_DIMENSION is not None:
                if self.EMBEDDING_DIMENSION != text_spec.dimension:
                    raise ValueError(
                        f"CONFIG CONFLICT: {self.EMBEDDING_MODEL} expects "
                        f"{text_spec.dimension}D, but EMBEDDING_DIMENSION is "
                        f"set to {self.EMBEDDING_DIMENSION} in .env/docker-compose. "
                        f"Fix: remove EMBEDDING_DIMENSION (auto-inferred) or "
                        f"change EMBEDDING_MODEL."
                    )
            else:
                # Auto-déduction
                self.EMBEDDING_DIMENSION = text_spec.dimension
            
            # Vérifie cohérence backend
            if self.EMBEDDING_BACKEND is not None:
                if self.EMBEDDING_BACKEND != text_spec.backend:
                    raise ValueError(
                        f"CONFIG CONFLICT: {self.EMBEDDING_MODEL} uses "
                        f"backend '{text_spec.backend}', but "
                        f"EMBEDDING_BACKEND is '{self.EMBEDDING_BACKEND}'"
                    )
            else:
                self.EMBEDDING_BACKEND = text_spec.backend
        else:
            # Modèle inconnu — l'utilisateur DOIT fournir la dimension
            if self.EMBEDDING_DIMENSION is None:
                raise ValueError(
                    f"UNKNOWN MODEL: '{self.EMBEDDING_MODEL}' is not in "
                    f"KNOWN_MODELS. You MUST set EMBEDDING_DIMENSION in .env. "
                    f"Known models: {', '.join(sorted(KNOWN_MODELS.keys()))}"
                )
        
        # 2. Validation modèle code
        code_spec = KNOWN_MODELS.get(self.CODE_EMBEDDING_MODEL)
        if code_spec:
            if self.CODE_EMBEDDING_DIMENSION is None:
                self.CODE_EMBEDDING_DIMENSION = code_spec.dimension
            elif self.CODE_EMBEDDING_DIMENSION != code_spec.dimension:
                raise ValueError(
                    f"CONFIG CONFLICT: {self.CODE_EMBEDDING_MODEL} expects "
                    f"{code_spec.dimension}D, but CODE_EMBEDDING_DIMENSION is "
                    f"{self.CODE_EMBEDDING_DIMENSION}"
                )
        elif self.CODE_EMBEDDING_DIMENSION is None:
            raise ValueError(
                f"UNKNOWN CODE MODEL: '{self.CODE_EMBEDDING_MODEL}'. "
                f"Set CODE_EMBEDDING_DIMENSION in .env."
            )
        
        return self
    
    @property
    def text_spec(self) -> Optional[ModelSpec]:
        """Retourne la spec complète du modèle texte."""
        return KNOWN_MODELS.get(self.EMBEDDING_MODEL)
    
    @property
    def code_spec(self) -> Optional[ModelSpec]:
        """Retourne la spec complète du modèle code."""
        return KNOWN_MODELS.get(self.CODE_EMBEDDING_MODEL)


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Singleton de configuration.
    
    Calculé une seule fois au premier appel (lru_cache).
    Crash immédiat si la config est incohérente (fail fast).
    """
    return AppSettings()
```

### 2.4 Injection dans `dependencies.py`

```python
from api.core.settings import get_settings, AppSettings

# Au démarrage — crash si config invalide
settings = get_settings()

def get_embedding_dimension() -> int:
    """Retourne la dimension d'embedding validée."""
    return settings.EMBEDDING_DIMENSION

def get_text_embedding_model() -> str:
    """Retourne le nom du modèle texte."""
    return settings.EMBEDDING_MODEL

# Exemple d'utilisation dans les dépendances de service
def get_vector_search_service():
    return VectorSearchService(dimension=settings.EMBEDDING_DIMENSION)

def get_memory_search_service():
    return MemorySearchService(
        embedding_dimension=settings.EMBEDDING_DIMENSION,
        embedding_model=settings.EMBEDDING_MODEL,
    )
```

## 3. Plan de migration par fichier

### Fichiers à créer (2)

| Fichier | Contenu |
|---------|---------|
| `api/core/__init__.py` | Export `get_settings`, `KNOWN_MODELS`, `ModelSpec`, `AppSettings` |
| `api/core/embedding_models.py` | Registre `KNOWN_MODELS` (cf §2.2) |
| `api/core/settings.py` | `AppSettings` + `get_settings()` (cf §2.3) |

### Fichiers à modifier (14)

| # | Fichier | Changement | Story |
|---|---------|-----------|-------|
| 1 | `api/dependencies.py` | Importer `get_settings()`, injecter dimensions | 49.2 |
| 2 | `api/main.py` | Remplacer `os.getenv("EMBEDDING_DIMENSION")` par `get_settings().EMBEDDING_DIMENSION` | 49.2 |
| 3 | `api/services/vector_search_service.py` | `len(embedding) != self.dimension` (injecté) | 49.2 |
| 4 | `api/services/memory_search_service.py` | `EXPECTED_EMBEDDING_DIM` → `get_settings().EMBEDDING_DIMENSION` | 49.2 |
| 5 | `api/services/sentence_transformer_embedding_service.py` | `EMBEDDING_MODELS` dict → `KNOWN_MODELS` du core, `model_name` depuis settings | 49.2 |
| 6 | `api/services/dual_embedding_service.py` | `text_dimension`/`code_dimension` → `get_settings()` | 49.2 |
| 7 | `api/services/embedding_service.py` | `dimension: int = 1024` → `get_settings().EMBEDDING_DIMENSION` | 49.2 |
| 8 | `api/routes/memory_graph_routes.py` | Supprimer `dimension=1024` hardcodé | 49.2 |
| 9 | `api/services/simple_cache_service.py` | `[0.1] * 768` → `[0.1] * settings.EMBEDDING_DIMENSION` | 49.3 |
| 10 | `.env` | Supprimer `EMBEDDING_DIMENSION=1024`, garder `EMBEDDING_MODEL` | 49.3 |
| 11 | `docker-compose.yml` | Supprimer `EMBEDDING_DIMENSION` du defaults | 49.3 |
| 12 | `scripts/reindex_bge_m3.py` | `MODEL_NAME` → `get_settings().EMBEDDING_MODEL` | 49.4 |
| 13 | `scripts/reindex_memories_e5.py` | Idem | 49.4 |
| 14 | `scripts/backfill_memory_embeddings.py` | Idem | 49.4 |

### Fichiers à ne PAS toucher (stables)

| Fichier | Raison |
|---------|--------|
| `api/config/` | Config existante (circuit_breakers, timeouts, languages) — pas d'embedding |
| `api/mnemo_mcp/` | Utilise déjà l'injection de l'API — suivra automatiquement |
| `api/db/` | Pas de logique d'embedding |
| `scripts/archive/` | Scripts obsolètes |

## 4. Stratégie de validation

### 4.1 Crash Early

```
$ EMBEDDING_MODEL=BAAI/bge-m3 EMBEDDING_DIMENSION=768 python -c "from api.core.settings import get_settings; get_settings()"
ValueError: CONFIG CONFLICT: BAAI/bge-m3 expects 1024D, but EMBEDDING_DIMENSION is set to 768 in .env/docker-compose. 
Fix: remove EMBEDDING_DIMENSION (auto-inferred) or change EMBEDDING_MODEL.
```

### 4.2 Auto-déduction

```
$ EMBEDDING_MODEL=BAAI/bge-m3 python -c "from api.core.settings import get_settings; s=get_settings(); print(s.EMBEDDING_DIMENSION)"
1024
```

### 4.3 Modèle inconnu

```
$ EMBEDDING_MODEL=my-custom-model python -c "from api.core.settings import get_settings; get_settings()"
ValueError: UNKNOWN MODEL: 'my-custom-model' is not in KNOWN_MODELS. You MUST set EMBEDDING_DIMENSION in .env.
Known models: BAAI/bge-m3, intfloat/multilingual-e5-base, ...
```

### 4.4 Test de régression

```python
def test_switch_model_updates_dimension():
    """Changer EMBEDDING_MODEL doit changer EMBEDDING_DIMENSION automatiquement."""
    s1 = AppSettings(EMBEDDING_MODEL="BAAI/bge-m3")
    assert s1.EMBEDDING_DIMENSION == 1024
    
    s2 = AppSettings(EMBEDDING_MODEL="nomic-ai/nomic-embed-text-v1.5")
    assert s2.EMBEDDING_DIMENSION == 768

def test_mismatch_crashes():
    """Dimension contradictoire doit lever ValueError."""
    with pytest.raises(ValueError, match="CONFIG CONFLICT"):
        AppSettings(
            EMBEDDING_MODEL="BAAI/bge-m3",
            EMBEDDING_DIMENSION=768
        )

def test_retrocompatibility():
    """.env existant avec dimension explicite correcte doit fonctionner."""
    s = AppSettings(
        EMBEDDING_MODEL="BAAI/bge-m3",
        EMBEDDING_DIMENSION=1024  # explicite mais correct
    )
    assert s.EMBEDDING_DIMENSION == 1024  # pas d'erreur

def test_unknown_model_with_dimension_works():
    """Modèle inconnu avec dimension explicite doit fonctionner."""
    s = AppSettings(
        EMBEDDING_MODEL="my-custom-model",
        EMBEDDING_DIMENSION=2048
    )
    assert s.EMBEDDING_DIMENSION == 2048
```

## 5. Rétrocompatibilité

- `.env` avec `EMBEDDING_DIMENSION=1024` + `EMBEDDING_MODEL=BAAI/bge-m3` → valide silencieusement
- `.env` avec seulement `EMBEDDING_MODEL=BAAI/bge-m3` → auto-déduit 1024
- `.env` avec `EMBEDDING_DIMENSION=768` + `EMBEDDING_MODEL=BAAI/bge-m3` → **crash explicite** (comportement voulu : l'ancien .env était cassé)
- Scripts standalone : continuent de fonctionner, lisent la même config

## 6. Points d'attention

1. **Import circulaire** : `api/core/` ne doit RIEN importer de `api/services/` ou `api/routes/`
2. **DualEmbeddingService** : texte et code ont des dimensions différentes → `EMBEDDING_DIMENSION` vs `CODE_EMBEDDING_DIMENSION`
3. **ONNX path** : `USE_ONNX` et `ONNX_MODEL_PATH` restent dans le script de réindexation (config déploiement, pas modèle)
4. **GLiNER** : modèle d'extraction d'entités, pas d'embedding sémantique → hors scope, reste en config séparée
5. **Tests existants** : 26 tests SUBLIMATOR + 6 tests reindex ne sont pas impactés (ils testent le parsing, pas la config)
ENDDOFFILE

echo 'Spec created' && wc -l /home/giak/Work/MnemoLite/docs/superpowers/specs/2026-06-10-embedding-config-centralization-design.md
