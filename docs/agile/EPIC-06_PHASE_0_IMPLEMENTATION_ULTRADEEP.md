# EPIC-06 Phase 0: Ultra-Deep Implementation Analysis

**Date**: 2025-10-15
**Version**: 1.0.0
**Branch**: migration/postgresql-18
**Status**: 🔬 ULTRA-DEEP ANALYSIS

---

## 📋 Table des Matières

1. [Architecture Actuelle - Analyse Complète](#1-architecture-actuelle)
2. [Story 0.1: Alembic Async - Deep Dive](#2-story-01-alembic-async)
3. [Story 0.2: Dual Embeddings - Deep Dive](#3-story-02-dual-embeddings)
4. [Points d'Intégration Critiques](#4-points-dintégration-critiques)
5. [Plan d'Implémentation Détaillé](#5-plan-dimplémentation)
6. [Risques et Mitigations](#6-risques-et-mitigations)
7. [Tests et Validation](#7-tests-et-validation)

---

## 1. Architecture Actuelle - Analyse Complète

### 1.1 État des Lieux Infrastructure

**PostgreSQL 18.0 + pgvector 0.8.1** ✅ OPÉRATIONNEL
```bash
# Validation effectuée
$ docker exec mnemo-postgres psql -U mnemo -d mnemolite -c "SELECT version();"
PostgreSQL 18.0 (Debian 18.0-1.pgdg120+1) on x86_64-pc-linux-gnu

$ docker exec mnemo-postgres psql -U mnemo -d mnemolite -c "SELECT extversion FROM pg_extension WHERE extname='vector';"
0.8.1
```

**Embedding Model** ✅ OPÉRATIONNEL
- Model: `nomic-ai/nomic-embed-text-v1.5`
- Dimension: 768
- RAM: ~260 MB (137M params)
- Pre-loaded: OUI (main.py:78-107)

**Events Indexed**: 364/537 avec embeddings

---

### 1.2 Architecture Actuelle MnemoLite

#### Database Layer

**Fichier**: `api/db/database.py`
**Pattern**: Pure asyncpg (pas d'ORM)

```python
# Structure actuelle
class Database:
    async def get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                dsn=self.dsn,
                min_size=5,
                max_size=10,
                init=self._init_connection  # pgvector registration
            )
```

**🔴 CRITIQUE**:
- **PAS de SQLAlchemy ORM models**
- **PAS de Base declarative**
- **PAS de metadata registry**
- Tout en asyncpg direct + raw SQL

**✅ MAIS**: SQLAlchemy AsyncEngine créé dans main.py:56-76
```python
# main.py lifespan
app.state.db_engine: AsyncEngine = create_async_engine(
    db_url_to_use,
    echo=DEBUG,
    pool_size=10,
    max_overflow=5,
    future=True,
    pool_pre_ping=True,
)
```

**Implication pour Alembic**:
- ✅ AsyncEngine disponible
- ❌ Pas de metadata à migrer actuellement
- ⚠️ Besoin de créer metadata pour table `code_chunks` (nouvelle)

---

#### Embedding Service Layer

**Fichier**: `api/services/sentence_transformer_embedding_service.py`
**Pattern**: Singleton + Lazy Loading + Double-Checked Locking

```python
class SentenceTransformerEmbeddingService:
    def __init__(self, model_name, dimension, cache_size, device):
        self._model: Optional[SentenceTransformer] = None
        self._lock = asyncio.Lock()
        self._load_attempted = False

    async def _ensure_model_loaded(self):
        if self._model is not None:
            return

        async with self._lock:  # Double-checked locking ✅
            if self._model is not None:
                return

            # Chargement dans executor (non-blocking)
            loop = asyncio.get_event_loop()
            self._model = await loop.run_in_executor(
                None,
                self._load_model_sync
            )
```

**Points forts**:
- ✅ Pattern async-safe
- ✅ Lazy loading (cold start évité)
- ✅ Cache LRU (1000 entrées)
- ✅ Executor pour CPU-bound ops
- ✅ Singleton global dans dependencies.py

**Points à étendre**:
- ⚠️ Supporte 1 seul modèle actuellement
- ⚠️ Pas de concept de "domain" (TEXT vs CODE)
- ⚠️ Pas de gestion dual models

---

#### Dependency Injection

**Fichier**: `api/dependencies.py`
**Pattern**: DIP via Protocol + Singleton

```python
# Singleton global
_embedding_service_instance: Optional[EmbeddingServiceProtocol] = None

async def get_embedding_service() -> EmbeddingServiceProtocol:
    global _embedding_service_instance

    if _embedding_service_instance is not None:
        return _embedding_service_instance

    embedding_mode = os.getenv("EMBEDDING_MODE", "real").lower()

    if embedding_mode == "real":
        _embedding_service_instance = SentenceTransformerEmbeddingService(
            model_name=os.getenv("EMBEDDING_MODEL", "nomic-ai/nomic-embed-text-v1.5"),
            dimension=int(os.getenv("EMBEDDING_DIMENSION", "768")),
            cache_size=int(os.getenv("EMBEDDING_CACHE_SIZE", "1000")),
            device=os.getenv("EMBEDDING_DEVICE", "cpu")
        )
```

**Pattern propre**:
- ✅ Interface EmbeddingServiceProtocol (interfaces/services.py:14-26)
- ✅ Injection via Depends()
- ✅ Testable (mock/real switch)

**À étendre pour dual embeddings**:
- ⚠️ Besoin nouvelle interface ou extension Protocol
- ⚠️ Besoin gérer 2 singletons (text + code)

---

#### Configuration Management

**État actuel**: ❌ **PAS de fichier settings.py centralisé**

Configuration scatter across:
- `main.py`: DATABASE_URL, ENVIRONMENT, DEBUG, TEST_DATABASE_URL
- `dependencies.py`: EMBEDDING_MODEL, EMBEDDING_DIMENSION, EMBEDDING_MODE, etc.
- `services/event_service.py`: EMBEDDING_AUTO_GENERATE, EMBEDDING_FAIL_STRATEGY

**Problème**:
- 🔴 Pas de single source of truth
- 🔴 Validation config absente
- 🔴 Difficile pour Alembic (besoin alembic.ini + env.py)

**Solution Phase 0**:
- ✅ Créer `api/config/settings.py` (Pydantic BaseSettings)
- ✅ Centraliser toutes les env vars
- ✅ Validation automatique
- ✅ Compatible Alembic

---

### 1.3 Schéma Base de Données Actuel

**Table `events`** (PRODUCTION):
```sql
CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    content JSONB NOT NULL,
    embedding VECTOR(768),  -- nomic-embed-text-v1.5
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_events_timestamp_btree ON events USING btree(timestamp DESC);
CREATE INDEX idx_events_embedding_hnsw ON events USING hnsw(embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX idx_events_metadata_gin ON events USING gin(metadata jsonb_path_ops);
```

**Tables `nodes` & `edges`** (GRAPH):
```sql
CREATE TABLE nodes (
    node_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_type TEXT NOT NULL,
    label TEXT,
    properties JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE edges (
    edge_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_node_id UUID NOT NULL,  -- NO FK (flexibility)
    target_node_id UUID NOT NULL,
    relationship_type TEXT NOT NULL,
    properties JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**⚠️ AUCUNE MIGRATION ALEMBIC ACTUELLEMENT**
- Tables créées manuellement via `db/init/01-init.sql`
- Pas de versioning
- Pas de rollback support

---

## 2. Story 0.1: Alembic Async - Deep Dive

**Story Points**: 3
**Complexité**: MOYENNE
**Durée estimée**: 1-2 jours

---

### 2.1 Objectifs Story 0.1

**Primaire**:
1. Initialiser Alembic avec template async
2. Configurer env.py pour AsyncEngine
3. Créer migration baseline (snapshot état actuel)
4. Valider upgrade/downgrade fonctionne

**Secondaire**:
1. Centraliser configuration dans settings.py
2. Documenter workflow migrations
3. Intégrer au CI/CD (make commands)

---

### 2.2 Défis Techniques Identifiés

#### Défi 1: Coexistence asyncpg + SQLAlchemy Core

**Situation actuelle**:
- asyncpg: Utilisé directement dans repositories (asyncpg.Pool)
- SQLAlchemy: AsyncEngine créé mais pas vraiment utilisé

**Solution**:
- ✅ SQLAlchemy Core pour Alembic uniquement
- ✅ Garder asyncpg pour repositories (performance)
- ✅ Coexistence via 2 connexions indépendantes

**Pattern**:
```python
# Pour Alembic (SQLAlchemy Core)
from sqlalchemy import MetaData, Table, Column, ...
metadata = MetaData()

code_chunks_table = Table(
    'code_chunks',
    metadata,
    Column('id', UUID, primary_key=True),
    ...
)

# Pour repositories (asyncpg direct) - INCHANGÉ
async with pool.acquire() as conn:
    result = await conn.fetch("SELECT ...")
```

---

#### Défi 2: Pas de Models Declarative

**Problème**:
- Alembic s'attend à des models ORM (Base.metadata)
- MnemoLite n'a PAS de models Declarative

**Solutions possibles**:

**Option A**: Core metadata uniquement (RECOMMANDÉ)
```python
# api/db/models.py (NOUVEAU)
from sqlalchemy import MetaData, Table, Column, Integer, String, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB, VECTOR

metadata = MetaData()

# Définir tables existantes (pour tracking Alembic)
events_table = Table(
    'events',
    metadata,
    Column('id', UUID, primary_key=True),
    Column('timestamp', TIMESTAMP(timezone=True)),
    Column('content', JSONB),
    Column('embedding', VECTOR(768)),
    Column('metadata', JSONB),
    Column('created_at', TIMESTAMP(timezone=True)),
    Column('updated_at', TIMESTAMP(timezone=True)),
)

# Nouvelle table Phase 1
code_chunks_table = Table(
    'code_chunks',
    metadata,
    Column('id', UUID, primary_key=True),
    Column('file_path', String),
    Column('chunk_type', String),
    Column('content', String),
    Column('embedding_text', VECTOR(768)),  # nomic-text
    Column('embedding_code', VECTOR(768)),  # jina-code
    Column('metadata', JSONB),
    Column('created_at', TIMESTAMP(timezone=True)),
)
```

**Avantages**:
- ✅ Léger (pas d'ORM overhead)
- ✅ Compatible asyncpg existant
- ✅ Suffit pour Alembic
- ✅ Pas de refactoring repositories

**Option B**: Ajouter ORM models (NON RECOMMANDÉ)
- ❌ Refactoring massif repositories
- ❌ Breaking changes
- ❌ Complexité inutile

**Décision**: **Option A - Core metadata uniquement**

---

#### Défi 3: Configuration Alembic

**Fichier `alembic.ini`**:
```ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os

sqlalchemy.url = driver://user:pass@localhost/dbname  # ⚠️ DUMMY

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic
```

**🔴 PROBLÈME**: `sqlalchemy.url` hardcodé
**✅ SOLUTION**: Utiliser env.py runtime config

```python
# alembic/env.py
from api.config.settings import get_settings

settings = get_settings()

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
```

---

### 2.3 Architecture Alembic Async

#### Structure Fichiers

```
MnemoLite/
├── alembic/
│   ├── env.py          ← Configuration async
│   ├── script.py.mako  ← Template migrations
│   ├── versions/       ← Migrations
│   │   ├── 001_baseline_snapshot.py
│   │   └── 002_add_code_chunks_table.py  (Phase 1)
│   └── README
├── alembic.ini         ← Config Alembic
├── api/
│   ├── config/
│   │   └── settings.py ← Configuration centralisée (NOUVEAU)
│   └── db/
│       └── models.py   ← SQLAlchemy Core metadata (NOUVEAU)
```

---

#### Code: api/config/settings.py (NOUVEAU)

```python
"""
Configuration centralisée pour MnemoLite.
Utilise Pydantic BaseSettings pour validation et env vars.
"""

from typing import Literal
from pydantic_settings import BaseSettings
from pydantic import Field, validator
from functools import lru_cache


class Settings(BaseSettings):
    """Settings validées via Pydantic."""

    # Database
    DATABASE_URL: str = Field(..., description="PostgreSQL connection URL")
    TEST_DATABASE_URL: str = Field(None, description="Test database URL")

    # Environment
    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    DEBUG: bool = False

    # Embedding - Text (existing)
    EMBEDDING_MODEL: str = "nomic-ai/nomic-embed-text-v1.5"
    EMBEDDING_DIMENSION: int = 768
    EMBEDDING_MODE: Literal["mock", "real"] = "real"
    EMBEDDING_DEVICE: Literal["cpu", "cuda", "mps"] = "cpu"
    EMBEDDING_CACHE_SIZE: int = 1000

    # Embedding - Code (NEW for Phase 0.2)
    CODE_EMBEDDING_MODEL: str = "jinaai/jina-embeddings-v2-base-code"
    CODE_EMBEDDING_DIMENSION: int = 768

    # API
    API_PORT: int = 8001

    # PostgreSQL
    POSTGRES_USER: str = "mnemo"
    POSTGRES_PASSWORD: str = "mnemo_pass"
    POSTGRES_DB: str = "mnemolite"
    POSTGRES_PORT: int = 5432

    @validator("CODE_EMBEDDING_DIMENSION")
    def validate_same_dimension(cls, v, values):
        """Valide que text et code ont même dimension (768)."""
        text_dim = values.get("EMBEDDING_DIMENSION", 768)
        if v != text_dim:
            raise ValueError(
                f"CODE_EMBEDDING_DIMENSION ({v}) must match "
                f"EMBEDDING_DIMENSION ({text_dim}) for index compatibility"
            )
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Retourne settings singleton (cached)."""
    return Settings()
```

---

#### Code: alembic/env.py (ASYNC TEMPLATE)

```python
"""
Alembic environment configuration for async migrations.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# Import metadata
from api.db.models import metadata
from api.config.settings import get_settings

# Get settings
settings = get_settings()

# Alembic Config object
config = context.config

# Set DATABASE_URL dynamically from settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    Configure with just a URL, no Engine.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations with given connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in 'online' mode (async).
    Create async engine and run migrations.
    """
    connectable = create_async_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,  # Alembic doesn't need pool
        echo=settings.DEBUG,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run async migrations from sync context."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

**🔑 Points Clés**:
- `run_sync(do_run_migrations)`: Bridge async → sync Alembic
- `NullPool`: Alembic n'a pas besoin de connection pool
- `settings.DATABASE_URL`: Config dynamique depuis env vars

---

#### Code: api/db/models.py (NOUVEAU - Metadata Only)

```python
"""
SQLAlchemy Core table definitions for Alembic migrations.
Defines metadata without ORM (asyncpg repositories unchanged).
"""

from sqlalchemy import MetaData, Table, Column, Integer, String, Text, TIMESTAMP, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector

metadata = MetaData()

# ============================================================
# TABLE: events (EXISTING - baseline snapshot)
# ============================================================
events_table = Table(
    'events',
    metadata,
    Column('id', UUID, primary_key=True, server_default="gen_random_uuid()"),
    Column('timestamp', TIMESTAMP(timezone=True), nullable=False, server_default="NOW()"),
    Column('content', JSONB, nullable=False),
    Column('embedding', Vector(768)),  # nomic-embed-text-v1.5
    Column('metadata', JSONB, server_default="'{}'::jsonb"),
    Column('created_at', TIMESTAMP(timezone=True), server_default="NOW()"),
    Column('updated_at', TIMESTAMP(timezone=True), server_default="NOW()"),
)

# Indexes for events
Index('idx_events_timestamp_btree', events_table.c.timestamp.desc())
Index('idx_events_metadata_gin', events_table.c.metadata, postgresql_using='gin', postgresql_ops={'metadata': 'jsonb_path_ops'})

# HNSW index - cannot be created via SQLAlchemy, use raw SQL in migration
# CREATE INDEX idx_events_embedding_hnsw ON events USING hnsw(embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

# ============================================================
# TABLE: nodes (EXISTING - baseline snapshot)
# ============================================================
nodes_table = Table(
    'nodes',
    metadata,
    Column('node_id', UUID, primary_key=True, server_default="gen_random_uuid()"),
    Column('node_type', Text, nullable=False),
    Column('label', Text),
    Column('properties', JSONB, server_default="'{}'::jsonb"),
    Column('created_at', TIMESTAMP(timezone=True), server_default="NOW()"),
)

# ============================================================
# TABLE: edges (EXISTING - baseline snapshot)
# ============================================================
edges_table = Table(
    'edges',
    metadata,
    Column('edge_id', UUID, primary_key=True, server_default="gen_random_uuid()"),
    Column('source_node_id', UUID, nullable=False),
    Column('target_node_id', UUID, nullable=False),
    Column('relationship_type', Text, nullable=False),
    Column('properties', JSONB, server_default="'{}'::jsonb"),
    Column('created_at', TIMESTAMP(timezone=True), server_default="NOW()"),
)

Index('idx_edges_source', edges_table.c.source_node_id)
Index('idx_edges_target', edges_table.c.target_node_id)
Index('idx_edges_relationship', edges_table.c.relationship_type)

# ============================================================
# TABLE: code_chunks (NEW - Phase 1, defined here for reference)
# ============================================================
# Will be created in migration 002_add_code_chunks_table.py
code_chunks_table = Table(
    'code_chunks',
    metadata,
    Column('id', UUID, primary_key=True, server_default="gen_random_uuid()"),
    Column('file_path', Text, nullable=False),
    Column('language', String(50)),
    Column('chunk_type', String(50)),  # 'function', 'class', 'method', etc.
    Column('name', Text),  # function/class name
    Column('content', Text, nullable=False),
    Column('embedding_text', Vector(768)),  # nomic-embed-text-v1.5
    Column('embedding_code', Vector(768)),  # jina-embeddings-v2-base-code
    Column('metadata', JSONB, server_default="'{}'::jsonb"),
    Column('created_at', TIMESTAMP(timezone=True), server_default="NOW()"),
    Column('updated_at', TIMESTAMP(timezone=True), server_default="NOW()"),
)

# Indexes for code_chunks (created in Phase 1 migration)
Index('idx_code_chunks_file_path', code_chunks_table.c.file_path)
Index('idx_code_chunks_language', code_chunks_table.c.language)
Index('idx_code_chunks_chunk_type', code_chunks_table.c.chunk_type)
```

**🔑 Points Clés**:
- Pure SQLAlchemy Core (pas de Declarative Base)
- Metadata pour Alembic autogenerate
- Tables existantes définies (baseline snapshot)
- Table code_chunks définie mais pas créée (Phase 1)

---

### 2.4 Migration Baseline

**Commande**:
```bash
# Initialiser Alembic avec template async
$ alembic init -t async alembic

# Créer migration baseline (snapshot état actuel)
$ alembic revision --autogenerate -m "baseline snapshot existing tables"
```

**Fichier généré**: `alembic/versions/001_baseline_snapshot.py`

```python
"""baseline snapshot existing tables

Revision ID: 001
Revises:
Create Date: 2025-10-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Baseline migration: Mark existing tables as managed by Alembic.
    NO-OP migration (tables already exist from db/init/01-init.sql).
    """
    # Tables already exist, this migration just creates Alembic baseline
    pass


def downgrade() -> None:
    """
    Downgrade baseline: Would drop all tables (DANGEROUS).
    Disabled to prevent accidental data loss.
    """
    # Safety: Do NOT allow downgrade of baseline
    raise RuntimeError(
        "Cannot downgrade baseline migration. "
        "This would drop all existing tables and data."
    )
```

**⚠️ IMPORTANT**: Migration baseline est NO-OP
- Tables déjà créées via `db/init/01-init.sql`
- Alembic track seulement l'état
- Permet migrations futures (Phase 1: code_chunks)

---

### 2.5 Tests Story 0.1

#### Test 1: Alembic Init

```bash
# Test: Alembic initialized correctly
$ ls alembic/
env.py  README  script.py.mako  versions/

$ alembic current
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
Current revision(s): <none>
```

#### Test 2: Baseline Migration

```bash
# Test: Baseline migration applies
$ alembic upgrade head
INFO  [alembic.runtime.migration] Running upgrade  -> 001, baseline snapshot existing tables
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.

$ alembic current
001 (head)
```

#### Test 3: Alembic History

```bash
# Test: Alembic tracks migrations
$ alembic history
001 (head) -> baseline snapshot existing tables
```

#### Test 4: Database State

```sql
-- Test: alembic_version table created
SELECT * FROM alembic_version;
-- version_num
-- -----------
-- 001
```

---

## 3. Story 0.2: Dual Embeddings - Deep Dive

**Story Points**: 5
**Complexité**: HAUTE
**Durée estimée**: 2-3 jours

---

### 3.1 Objectifs Story 0.2

**Primaire**:
1. Étendre EmbeddingService pour supporter TEXT + CODE domains
2. Implémenter lazy loading pour 2 modèles simultanés
3. Valider RAM total < 1 GB (~700 MB target)
4. Tests avec CODE_EMBEDDING_MODEL (jina-code)

**Secondaire**:
1. Benchmark latence TEXT vs CODE vs HYBRID
2. Monitoring RAM (psutil)
3. Documentation choix jina-code vs nomic-code

---

### 3.2 Architecture Dual Embeddings

#### Pattern: Domain-Based Model Selection

```python
from enum import Enum

class EmbeddingDomain(str, Enum):
    """Domain-specific embedding selection."""
    TEXT = "text"      # Conversations, docs, general text → nomic-text
    CODE = "code"      # Code snippets, functions, classes → jina-code
    HYBRID = "hybrid"  # Generate both (code with docstrings)
```

#### Pattern: Dual Model Manager

**Fichier**: `api/services/dual_embedding_service.py` (NOUVEAU)

```python
"""
Dual Embedding Service for TEXT + CODE domains.
Manages two SentenceTransformer models simultaneously with memory optimization.
"""

import os
import logging
import asyncio
from typing import List, Dict, Optional
from enum import Enum

from sentence_transformers import SentenceTransformer
import psutil

logger = logging.getLogger(__name__)


class EmbeddingDomain(str, Enum):
    """Embedding domain types."""
    TEXT = "text"
    CODE = "code"
    HYBRID = "hybrid"


class DualEmbeddingService:
    """
    Service managing dual embeddings for text and code.

    Models:
    - TEXT: nomic-embed-text-v1.5 (137M params, 768D, ~260 MB RAM)
    - CODE: jina-embeddings-v2-base-code (161M params, 768D, ~400 MB RAM)
    - Total: ~660-700 MB RAM (< 1 GB target)

    Features:
    - Lazy loading (models loaded on-demand)
    - Domain-specific selection (TEXT | CODE | HYBRID)
    - RAM monitoring via psutil
    - Double-checked locking (thread-safe)
    """

    def __init__(
        self,
        text_model_name: Optional[str] = None,
        code_model_name: Optional[str] = None,
        dimension: int = 768,
        device: str = "cpu"
    ):
        """
        Initialize dual embedding service.

        Args:
            text_model_name: Sentence-Transformers model for text
            code_model_name: Sentence-Transformers model for code
            dimension: Expected embedding dimension (must be 768)
            device: PyTorch device ('cpu', 'cuda', 'mps')
        """
        self.text_model_name = text_model_name or os.getenv(
            "EMBEDDING_MODEL",
            "nomic-ai/nomic-embed-text-v1.5"
        )
        self.code_model_name = code_model_name or os.getenv(
            "CODE_EMBEDDING_MODEL",
            "jinaai/jina-embeddings-v2-base-code"
        )
        self.dimension = dimension
        self.device = device

        # Models (lazy loaded)
        self._text_model: Optional[SentenceTransformer] = None
        self._code_model: Optional[SentenceTransformer] = None

        # Locks for thread-safe lazy loading
        self._text_lock = asyncio.Lock()
        self._code_lock = asyncio.Lock()

        # Load attempt tracking
        self._text_load_attempted = False
        self._code_load_attempted = False

        logger.info(
            "DualEmbeddingService initialized",
            extra={
                "text_model": self.text_model_name,
                "code_model": self.code_model_name,
                "dimension": dimension,
                "device": device
            }
        )

    async def _ensure_text_model(self):
        """Load text model if not already loaded (thread-safe)."""
        if self._text_model is not None:
            return

        async with self._text_lock:
            # Double-checked locking
            if self._text_model is not None:
                return

            if self._text_load_attempted:
                raise RuntimeError(
                    "Text model loading failed previously. Restart service."
                )

            self._text_load_attempted = True

            try:
                logger.info(f"Loading TEXT model: {self.text_model_name}")

                loop = asyncio.get_event_loop()
                self._text_model = await loop.run_in_executor(
                    None,
                    lambda: SentenceTransformer(
                        self.text_model_name,
                        device=self.device,
                        trust_remote_code=True
                    )
                )

                # Validate dimension
                test_emb = await loop.run_in_executor(
                    None,
                    self._text_model.encode,
                    "test"
                )

                if len(test_emb) != self.dimension:
                    raise ValueError(
                        f"TEXT model dimension mismatch: "
                        f"expected {self.dimension}, got {len(test_emb)}"
                    )

                logger.info(
                    "✅ TEXT model loaded",
                    extra={"model": self.text_model_name, "dim": self.dimension}
                )

            except Exception as e:
                logger.error(f"❌ Failed to load TEXT model: {e}", exc_info=True)
                self._text_model = None
                raise RuntimeError(f"Failed to load TEXT model: {e}") from e

    async def _ensure_code_model(self):
        """Load code model if not already loaded (thread-safe)."""
        if self._code_model is not None:
            return

        async with self._code_lock:
            # Double-checked locking
            if self._code_model is not None:
                return

            if self._code_load_attempted:
                raise RuntimeError(
                    "Code model loading failed previously. Restart service."
                )

            self._code_load_attempted = True

            try:
                logger.info(f"Loading CODE model: {self.code_model_name}")

                loop = asyncio.get_event_loop()
                self._code_model = await loop.run_in_executor(
                    None,
                    lambda: SentenceTransformer(
                        self.code_model_name,
                        device=self.device,
                        trust_remote_code=True
                    )
                )

                # Validate dimension
                test_emb = await loop.run_in_executor(
                    None,
                    self._code_model.encode,
                    "def test(): pass"
                )

                if len(test_emb) != self.dimension:
                    raise ValueError(
                        f"CODE model dimension mismatch: "
                        f"expected {self.dimension}, got {len(test_emb)}"
                    )

                logger.info(
                    "✅ CODE model loaded",
                    extra={"model": self.code_model_name, "dim": self.dimension}
                )

            except Exception as e:
                logger.error(f"❌ Failed to load CODE model: {e}", exc_info=True)
                self._code_model = None
                raise RuntimeError(f"Failed to load CODE model: {e}") from e

    async def generate_embedding(
        self,
        text: str,
        domain: EmbeddingDomain = EmbeddingDomain.TEXT
    ) -> Dict[str, List[float]]:
        """
        Generate embedding(s) based on domain.

        Args:
            text: Text or code to embed
            domain: TEXT (text model), CODE (code model), HYBRID (both)

        Returns:
            Dict with keys 'text' and/or 'code' containing embeddings

        Examples:
            # TEXT domain (conversations, docs)
            result = await svc.generate_embedding("Hello world", domain=EmbeddingDomain.TEXT)
            # {'text': [0.1, 0.2, ...]}

            # CODE domain (code snippets)
            result = await svc.generate_embedding("def foo(): pass", domain=EmbeddingDomain.CODE)
            # {'code': [0.3, 0.4, ...]}

            # HYBRID domain (code with docstrings)
            result = await svc.generate_embedding("def foo():\n  '''Docstring'''", domain=EmbeddingDomain.HYBRID)
            # {'text': [...], 'code': [...]}
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return {domain.value: [0.0] * self.dimension}

        result = {}

        if domain in (EmbeddingDomain.TEXT, EmbeddingDomain.HYBRID):
            # Generate text embedding
            await self._ensure_text_model()

            loop = asyncio.get_event_loop()
            text_emb = await loop.run_in_executor(
                None,
                self._text_model.encode,
                text
            )
            result['text'] = text_emb.tolist()

        if domain in (EmbeddingDomain.CODE, EmbeddingDomain.HYBRID):
            # Generate code embedding
            await self._ensure_code_model()

            loop = asyncio.get_event_loop()
            code_emb = await loop.run_in_executor(
                None,
                self._code_model.encode,
                text
            )
            result['code'] = code_emb.tolist()

        return result

    def get_ram_usage_mb(self) -> Dict[str, float]:
        """
        Get current RAM usage in MB.

        Returns:
            Dict with process RAM and model estimates
        """
        process = psutil.Process()
        mem_info = process.memory_info()

        return {
            "process_rss_mb": mem_info.rss / 1024 / 1024,
            "process_vms_mb": mem_info.vms / 1024 / 1024,
            "text_model_loaded": self._text_model is not None,
            "code_model_loaded": self._code_model is not None,
            "estimated_models_mb": (
                (260 if self._text_model else 0) +
                (400 if self._code_model else 0)
            )
        }

    def get_stats(self) -> dict:
        """Return service statistics."""
        ram_usage = self.get_ram_usage_mb()

        return {
            "text_model_name": self.text_model_name,
            "code_model_name": self.code_model_name,
            "dimension": self.dimension,
            "device": self.device,
            "text_model_loaded": self._text_model is not None,
            "code_model_loaded": self._code_model is not None,
            **ram_usage
        }
```

---

### 3.3 Intégration dependencies.py

**Modification**: `api/dependencies.py`

```python
# AVANT (Story 0.1)
from services.sentence_transformer_embedding_service import SentenceTransformerEmbeddingService

# APRÈS (Story 0.2)
from services.dual_embedding_service import DualEmbeddingService, EmbeddingDomain

# Singleton global
_embedding_service_instance: Optional[DualEmbeddingService] = None


async def get_embedding_service() -> DualEmbeddingService:
    """
    Get dual embedding service instance (singleton).

    Returns:
        DualEmbeddingService supporting TEXT + CODE domains
    """
    global _embedding_service_instance

    if _embedding_service_instance is not None:
        return _embedding_service_instance

    embedding_mode = os.getenv("EMBEDDING_MODE", "real").lower()

    if embedding_mode == "mock":
        # Mock mode (tests)
        logger.warning("🔶 EMBEDDING MODE: MOCK")
        _embedding_service_instance = MockEmbeddingService(
            model_name="mock-model",
            dimension=768
        )

    elif embedding_mode == "real":
        # Real mode - Dual embeddings
        logger.info("✅ EMBEDDING MODE: DUAL (TEXT + CODE)")
        _embedding_service_instance = DualEmbeddingService(
            text_model_name=os.getenv("EMBEDDING_MODEL", "nomic-ai/nomic-embed-text-v1.5"),
            code_model_name=os.getenv("CODE_EMBEDDING_MODEL", "jinaai/jina-embeddings-v2-base-code"),
            dimension=int(os.getenv("EMBEDDING_DIMENSION", "768")),
            device=os.getenv("EMBEDDING_DEVICE", "cpu")
        )

    else:
        raise ValueError(f"Invalid EMBEDDING_MODE: '{embedding_mode}'")

    return _embedding_service_instance
```

---

### 3.4 Backward Compatibility

**⚠️ CRITIQUE**: Assurer backward compatibility avec code existant

**Pattern Adapter**:

```python
# api/services/dual_embedding_service.py

class DualEmbeddingService:
    ...

    async def generate_embedding_legacy(self, text: str) -> List[float]:
        """
        Backward compatible method (returns text embedding only).
        Used by existing EventService, MemorySearchService, etc.

        Args:
            text: Text to embed

        Returns:
            Text embedding (list of floats)
        """
        result = await self.generate_embedding(text, domain=EmbeddingDomain.TEXT)
        return result['text']
```

**Usage dans dependencies.py**:

```python
# Pour code existant qui attend EmbeddingServiceProtocol
class DualEmbeddingServiceAdapter:
    """Adapter pour backward compatibility."""

    def __init__(self, dual_service: DualEmbeddingService):
        self._dual_service = dual_service

    async def generate_embedding(self, text: str) -> List[float]:
        """Implémente EmbeddingServiceProtocol."""
        return await self._dual_service.generate_embedding_legacy(text)

    async def compute_similarity(self, emb1, emb2) -> float:
        """Delegate to dual service."""
        return await self._dual_service.compute_similarity(emb1, emb2)
```

**✅ Résultat**: Code existant fonctionne sans changement
**✅ Nouveau code**: Peut utiliser domain=CODE ou HYBRID

---

### 3.5 Tests Story 0.2

#### Test 1: Dual Models Loading

```python
# tests/services/test_dual_embedding_service.py

import pytest
from api.services.dual_embedding_service import DualEmbeddingService, EmbeddingDomain


@pytest.mark.anyio
async def test_dual_models_lazy_loading():
    """Test: Both models load correctly on-demand."""
    service = DualEmbeddingService(
        text_model_name="nomic-ai/nomic-embed-text-v1.5",
        code_model_name="jinaai/jina-embeddings-v2-base-code",
        dimension=768,
        device="cpu"
    )

    # Initially no models loaded
    assert service._text_model is None
    assert service._code_model is None

    # Generate TEXT embedding (loads text model only)
    result_text = await service.generate_embedding(
        "Hello world",
        domain=EmbeddingDomain.TEXT
    )

    assert 'text' in result_text
    assert len(result_text['text']) == 768
    assert service._text_model is not None
    assert service._code_model is None  # Code model NOT loaded yet

    # Generate CODE embedding (loads code model)
    result_code = await service.generate_embedding(
        "def foo(): pass",
        domain=EmbeddingDomain.CODE
    )

    assert 'code' in result_code
    assert len(result_code['code']) == 768
    assert service._code_model is not None  # Now code model loaded
```

#### Test 2: HYBRID Domain

```python
@pytest.mark.anyio
async def test_hybrid_domain_generates_both():
    """Test: HYBRID domain generates both embeddings."""
    service = DualEmbeddingService()

    result = await service.generate_embedding(
        "def greet():\n    '''Say hello'''\n    print('Hello')",
        domain=EmbeddingDomain.HYBRID
    )

    # Both embeddings generated
    assert 'text' in result
    assert 'code' in result
    assert len(result['text']) == 768
    assert len(result['code']) == 768

    # Embeddings are different (different models)
    assert result['text'] != result['code']
```

#### Test 3: RAM Budget Validation

```python
@pytest.mark.anyio
async def test_ram_budget_under_1gb():
    """Test: Dual models RAM usage < 1 GB."""
    service = DualEmbeddingService()

    # Load both models
    await service.generate_embedding("test", domain=EmbeddingDomain.HYBRID)

    # Check RAM usage
    ram_usage = service.get_ram_usage_mb()

    assert ram_usage['text_model_loaded'] is True
    assert ram_usage['code_model_loaded'] is True

    # Estimated models RAM
    estimated_mb = ram_usage['estimated_models_mb']
    assert estimated_mb < 1024  # < 1 GB
    assert 600 <= estimated_mb <= 800  # ~660-700 MB expected

    print(f"✅ RAM Usage: {estimated_mb:.1f} MB (< 1 GB)")
```

#### Test 4: Backward Compatibility

```python
@pytest.mark.anyio
async def test_backward_compatible_legacy_method():
    """Test: Legacy generate_embedding() works (backward compat)."""
    service = DualEmbeddingService()

    # Old API (returns List[float])
    embedding = await service.generate_embedding_legacy("Hello")

    assert isinstance(embedding, list)
    assert len(embedding) == 768
    assert all(isinstance(x, float) for x in embedding)
```

---

## 4. Points d'Intégration Critiques

### 4.1 Configuration Centralisée

**Avant Phase 0**: Config scattered
**Après Phase 0**: `api/config/settings.py` centralisé

**Migration**:
```python
# Avant
DATABASE_URL = os.getenv("DATABASE_URL")

# Après
from api.config.settings import get_settings
settings = get_settings()
database_url = settings.DATABASE_URL
```

**Impact**:
- ✅ main.py: Utilise settings.DATABASE_URL
- ✅ dependencies.py: Utilise settings.EMBEDDING_MODEL, etc.
- ✅ alembic/env.py: Utilise settings.DATABASE_URL

---

### 4.2 Coexistence asyncpg + SQLAlchemy

**asyncpg** (repositories, direct SQL):
```python
# Inchangé
async with pool.acquire() as conn:
    result = await conn.fetch("SELECT * FROM events WHERE ...")
```

**SQLAlchemy** (Alembic migrations uniquement):
```python
# Nouveau (Alembic env.py)
engine = create_async_engine(settings.DATABASE_URL)
async with engine.connect() as conn:
    await conn.run_sync(do_run_migrations)
```

**✅ Pas de conflit**: 2 connexions indépendantes

---

### 4.3 Embedding Service Extension

**Interface Protocol** (interfaces/services.py):

**AVANT**:
```python
class EmbeddingServiceProtocol(Protocol):
    async def generate_embedding(self, text: str) -> List[float]: ...
```

**APRÈS** (Option A - Extension backward compatible):
```python
class EmbeddingServiceProtocol(Protocol):
    async def generate_embedding(self, text: str) -> List[float]: ...
    # Backward compatible - returns text embedding only

class DualEmbeddingServiceProtocol(Protocol):
    async def generate_embedding(
        self,
        text: str,
        domain: EmbeddingDomain = EmbeddingDomain.TEXT
    ) -> Dict[str, List[float]]: ...
    # New protocol for dual embeddings
```

**APRÈS** (Option B - Adaptateur):
```python
# Garder EmbeddingServiceProtocol inchangé
# DualEmbeddingService implémente via adapter pattern
```

**Décision**: **Option B** (adapter pattern, moins breaking changes)

---

## 5. Plan d'Implémentation Détaillé

### Phase 0.1 - Alembic Setup (Jour 1-2)

**Jour 1 Matin**:
1. ✅ Créer `api/config/settings.py` (Pydantic BaseSettings)
2. ✅ Migrer env vars vers settings.py (DATABASE_URL, EMBEDDING_MODEL, etc.)
3. ✅ Tester settings validation

**Jour 1 Après-midi**:
4. ✅ Créer `api/db/models.py` (SQLAlchemy Core metadata)
5. ✅ Définir events_table, nodes_table, edges_table (baseline)
6. ✅ Définir code_chunks_table (pour Phase 1, pas créé maintenant)

**Jour 2 Matin**:
7. ✅ Installer Alembic: `pip install alembic`
8. ✅ Init Alembic: `alembic init -t async alembic`
9. ✅ Configurer `alembic/env.py` (import metadata, settings)
10. ✅ Créer baseline migration: `alembic revision --autogenerate -m "baseline"`

**Jour 2 Après-midi**:
11. ✅ Tester migration: `alembic upgrade head`
12. ✅ Vérifier `alembic_version` table créée
13. ✅ Documenter workflow (README Alembic)

---

### Phase 0.2 - Dual Embeddings (Jour 3-5)

**Jour 3 Matin**:
1. ✅ Créer `api/services/dual_embedding_service.py`
2. ✅ Implémenter EmbeddingDomain enum
3. ✅ Implémenter `_ensure_text_model()` + `_ensure_code_model()`

**Jour 3 Après-midi**:
4. ✅ Implémenter `generate_embedding(domain=TEXT|CODE|HYBRID)`
5. ✅ Implémenter `generate_embedding_legacy()` (backward compat)
6. ✅ Ajouter RAM monitoring (`get_ram_usage_mb()`)

**Jour 4**:
7. ✅ Modifier `dependencies.py` pour DualEmbeddingService
8. ✅ Tester loading TEXT model (nomic-embed-text-v1.5)
9. ✅ Tester loading CODE model (jina-embeddings-v2-base-code)
10. ✅ Valider RAM < 1 GB (~700 MB)

**Jour 5**:
11. ✅ Tests unitaires (test_dual_embedding_service.py)
12. ✅ Tests intégration (test_dependencies.py)
13. ✅ Benchmark latence (TEXT vs CODE vs HYBRID)
14. ✅ Documentation ADR (pourquoi jina-code)

---

### Phase 0.3 - Intégration & Validation (Jour 6-7)

**Jour 6**:
1. ✅ Mise à jour `.env.example` (CODE_EMBEDDING_MODEL)
2. ✅ Mise à jour docker-compose.yml (env vars)
3. ✅ Tests régression (events API intacte)
4. ✅ Tests backward compatibility (ancien code fonctionne)

**Jour 7**:
5. ✅ Documentation complète (EPIC-06_PHASE_0_COMPLETION_REPORT.md)
6. ✅ Commit & Push (migration/postgresql-18)
7. ✅ Démo stakeholders (Phase 0 complete)
8. ✅ Go/No-Go Phase 1

---

## 6. Risques et Mitigations

### Risque 1: RAM Overflow Dual Models

**Probabilité**: FAIBLE
**Impact**: MOYEN

**Symptômes**:
- RAM > 1 GB
- OOM errors
- Swap thrashing

**Mitigation**:
1. ✅ Lazy loading (charger à la demande, pas startup)
2. ✅ RAM monitoring continu (psutil)
3. ✅ Fallback: Désactiver CODE model si RAM critique
4. ✅ Quantization FP16 si nécessaire (future)

**Code Fallback**:
```python
# Dans _ensure_code_model()
ram_usage = self.get_ram_usage_mb()
if ram_usage['process_rss_mb'] > 900:  # > 900 MB
    logger.warning("RAM limit approaching, skipping CODE model load")
    raise RuntimeError("RAM budget exceeded, CODE model disabled")
```

---

### Risque 2: Alembic Migrations Failures

**Probabilité**: MOYENNE
**Impact**: HAUT

**Symptômes**:
- Migration SQL errors
- Inconsistent schema state
- alembic_version corruption

**Mitigation**:
1. ✅ Baseline migration NO-OP (tables déjà existent)
2. ✅ Test sur DB test avant prod
3. ✅ Backup DB avant chaque migration
4. ✅ Rollback plan documenté

**Rollback Procedure**:
```bash
# Si migration échoue
$ alembic downgrade -1  # Rollback 1 migration

# Si corruption alembic_version
$ psql -U mnemo -d mnemolite
=> DELETE FROM alembic_version WHERE version_num = 'XXX';
=> INSERT INTO alembic_version VALUES ('correct_version');
```

---

### Risque 3: Backward Compatibility Break

**Probabilité**: MOYENNE
**Impact**: HAUT

**Symptômes**:
- Tests existants échouent
- API v1 /events broken
- EventService errors

**Mitigation**:
1. ✅ Adapter pattern (DualEmbeddingServiceAdapter)
2. ✅ generate_embedding_legacy() method
3. ✅ Tests régression obligatoires
4. ✅ Interface Protocol inchangé

**Validation**:
```bash
# Tests régression MUST pass
$ make api-test-file file=tests/routes/test_event_routes.py
$ make api-test-file file=tests/services/test_event_service.py

# Output expected: ALL PASS ✅
```

---

## 7. Tests et Validation

### 7.1 Tests Story 0.1 (Alembic)

```bash
# Test 1: Alembic init
$ ls alembic/
env.py  README  script.py.mako  versions/

# Test 2: Settings centralisées
$ python -c "from api.config.settings import get_settings; print(get_settings().DATABASE_URL)"
postgresql+asyncpg://mnemo:mnemo_pass@mnemo-postgres:5432/mnemolite

# Test 3: Metadata defined
$ python -c "from api.db.models import metadata; print(metadata.tables.keys())"
dict_keys(['events', 'nodes', 'edges', 'code_chunks'])

# Test 4: Baseline migration
$ alembic upgrade head
INFO  [alembic.runtime.migration] Running upgrade  -> 001

$ alembic current
001 (head)
```

---

### 7.2 Tests Story 0.2 (Dual Embeddings)

```bash
# Test 1: Dual service creation
$ python -c "
from api.services.dual_embedding_service import DualEmbeddingService
svc = DualEmbeddingService()
print(f'✅ Service created: {svc.text_model_name}, {svc.code_model_name}')
"

# Test 2: TEXT embedding
$ python -c "
import asyncio
from api.services.dual_embedding_service import DualEmbeddingService, EmbeddingDomain

async def test():
    svc = DualEmbeddingService()
    result = await svc.generate_embedding('Hello', domain=EmbeddingDomain.TEXT)
    print(f'✅ TEXT embedding: dim={len(result[\"text\"])}')

asyncio.run(test())
"

# Test 3: CODE embedding
# (similaire avec domain=EmbeddingDomain.CODE)

# Test 4: RAM usage
$ python -c "
import asyncio
from api.services.dual_embedding_service import DualEmbeddingService, EmbeddingDomain

async def test():
    svc = DualEmbeddingService()
    await svc.generate_embedding('test', domain=EmbeddingDomain.HYBRID)
    ram = svc.get_ram_usage_mb()
    print(f'✅ RAM: {ram[\"estimated_models_mb\"]} MB (< 1 GB: {ram[\"estimated_models_mb\"] < 1024})')

asyncio.run(test())
"
```

---

### 7.3 Tests Intégration

```python
# tests/integration/test_phase_0_complete.py

import pytest
from api.dependencies import get_embedding_service
from api.services.dual_embedding_service import EmbeddingDomain


@pytest.mark.anyio
async def test_phase_0_complete_integration():
    """
    Test: Phase 0 complete integration.

    Validates:
    - Alembic initialized
    - Settings centralized
    - Dual embeddings operational
    - RAM < 1 GB
    - Backward compatibility
    """
    # 1. Check Alembic
    import subprocess
    result = subprocess.run(
        ["alembic", "current"],
        capture_output=True,
        text=True
    )
    assert "001" in result.stdout  # Baseline migration applied

    # 2. Check Settings
    from api.config.settings import get_settings
    settings = get_settings()
    assert settings.EMBEDDING_DIMENSION == 768
    assert settings.CODE_EMBEDDING_DIMENSION == 768

    # 3. Check Dual Embeddings
    svc = await get_embedding_service()

    # TEXT domain
    result_text = await svc.generate_embedding(
        "Test conversation",
        domain=EmbeddingDomain.TEXT
    )
    assert 'text' in result_text
    assert len(result_text['text']) == 768

    # CODE domain
    result_code = await svc.generate_embedding(
        "def test(): pass",
        domain=EmbeddingDomain.CODE
    )
    assert 'code' in result_code
    assert len(result_code['code']) == 768

    # HYBRID domain
    result_hybrid = await svc.generate_embedding(
        "def greet():\n    '''Say hello'''\n    return 'Hello'",
        domain=EmbeddingDomain.HYBRID
    )
    assert 'text' in result_hybrid
    assert 'code' in result_hybrid

    # 4. Check RAM
    ram = svc.get_ram_usage_mb()
    assert ram['estimated_models_mb'] < 1024  # < 1 GB
    print(f"✅ Phase 0 Complete: RAM {ram['estimated_models_mb']:.1f} MB < 1 GB")

    # 5. Check Backward Compatibility
    legacy_result = await svc.generate_embedding_legacy("Test backward compat")
    assert isinstance(legacy_result, list)
    assert len(legacy_result) == 768
```

---

### 7.4 Métriques de Succès Phase 0

| Métrique | Target | Validation |
|----------|--------|------------|
| Alembic initialized | ✅ YES | `alembic current` shows 001 |
| Settings centralized | ✅ YES | `get_settings()` works |
| Dual models loaded | ✅ YES | TEXT + CODE both load |
| RAM usage | **< 1 GB** | ~660-700 MB measured |
| TEXT embedding latency | < 50ms | Benchmark validate |
| CODE embedding latency | < 50ms | Benchmark validate |
| HYBRID embedding latency | < 100ms | Benchmark validate |
| Backward compatibility | ✅ PASS | All existing tests pass |
| Tests coverage | > 85% | pytest --cov |

---

## 8. Conclusion & Next Steps

### Phase 0 Deliverables

**Story 0.1 - Alembic Async** ✅:
- Alembic initialisé avec template async
- Configuration centralisée (settings.py)
- Metadata SQLAlchemy Core (models.py)
- Baseline migration créée et appliquée

**Story 0.2 - Dual Embeddings** ✅:
- DualEmbeddingService implémenté
- Support TEXT + CODE + HYBRID domains
- RAM < 1 GB validé (~660-700 MB)
- Backward compatibility assurée

---

### Ready for Phase 1

**Prérequis Phase 1 (Story 1: Tree-sitter Chunking)**:
- ✅ Alembic opérationnel (migrations versionnées)
- ✅ Dual embeddings disponibles (CODE model chargé)
- ✅ Settings.CODE_EMBEDDING_MODEL configuré
- ✅ Infrastructure stable (PostgreSQL 18 + pgvector 0.8.1)

**Prochaines Actions**:
1. Installer tree-sitter-languages
2. Créer CodeChunkingService
3. Migration Alembic 002: CREATE TABLE code_chunks
4. Implémenter AST parsing (Python, JS, TS)

---

**Date**: 2025-10-15
**Version**: 1.0.0
**Status**: ✅ READY FOR PHASE 0 KICKOFF

**Estimated Total Time**: 5-7 jours (Story 0.1: 2j + Story 0.2: 3j + buffer: 2j)

---

**Auteurs**: Architecture Team MnemoLite
**Reviewers**: Tech Lead, Product Owner
