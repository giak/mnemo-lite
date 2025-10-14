<p align="center">
  <img src="static/img/logo_mnemolite.jpg" alt="MnemoLite Logo" width="200" style="border-radius: 50%;">
</p>

# MnemoLite: PostgreSQL-Native Cognitive Memory

[![Version](https://img.shields.io/badge/version-1.3.0-blue.svg?style=flat-square)](https://github.com/giak/MnemoLite)
[![Build Status](https://img.shields.io/github/actions/workflow/status/giak/MnemoLite/ci.yml?branch=main&style=flat-square)](https://github.com/giak/MnemoLite/actions) <!-- Placeholder URL -->
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg?style=flat-square)](https://www.python.org/downloads/)
[![PostgreSQL Version](https://img.shields.io/badge/postgres-17-blue.svg?style=flat-square)](https://www.postgresql.org/)
[![pgvector](https://img.shields.io/badge/pgvector-0.5.1-brightgreen.svg?style=flat-square)](https://github.com/pgvector/pgvector)
[![Tests](https://img.shields.io/badge/tests-102%20passing-success.svg?style=flat-square)](https://github.com/giak/MnemoLite)

**MnemoLite v1.3.0** provides a high-performance, locally deployable cognitive memory system built *exclusively* on PostgreSQL 17. It empowers AI agents like **Expanse** with robust, searchable, and time-aware memory capabilities, ideal for simulation, testing, analysis, and enhancing conversational AI understanding.

Forget complex external dependencies – MnemoLite leverages the power of modern PostgreSQL extensions for a streamlined, powerful, and easy-to-manage solution.

## ✨ Key Features

*   **PostgreSQL Native:** Relies solely on PostgreSQL 17, `pgvector`, `pg_partman`, and optionally `pg_cron` & `pgmq`. No external vector databases or complex graph engines needed for local deployment.
*   🤖 **100% Local Embeddings:** Uses **Sentence-Transformers** (nomic-embed-text-v1.5) for semantic embeddings. Zero external API dependencies, zero cost, complete privacy.
*   🚀 **High-Performance Search:** Leverages `pgvector` with **HNSW indexing** for fast (<15ms P95) semantic vector and hybrid search directly within the database.
*   ⏳ **Time-Aware Storage:** Automatic monthly table partitioning via `pg_partman` optimizes time-based queries and simplifies data retention/lifecycle management.
*   💾 **Efficient Local Storage:** Planned Hot/Warm data tiering with **INT8 quantization** (via optional `pg_cron` job) significantly reduces disk footprint for long-term local storage.
*   🕸️ **Integrated Relational Graph:** Optional `nodes`/`edges` tables allow modeling causal links and relationships, queryable via standard SQL CTEs.
*   🧩 **Modular & API-First:** Clean REST API defined with OpenAPI 3.1 (FastAPI), facilitating integration. CQRS-inspired logical separation.
*   🖥️ **Modern Web UI v4.0:** Full-featured interface with **SCADA industrial design** using HTMX 2.0, featuring Dashboard, Search, Graph visualization (Cytoscape.js), and real-time Monitoring (ECharts). Modular CSS architecture (16 modules), structured JavaScript (6 modules), and full ARIA accessibility.
*   🐳 **Simple Deployment:** Runs easily as 2-3 Docker containers (`db`, `api`, optional `worker`) via Docker Compose.

## 🏛️ Architecture Overview

MnemoLite uses a **clean, consolidated architecture** centered around PostgreSQL 17 as the single source of truth:

1.  **API (FastAPI):**
    *   Serves the REST API with OpenAPI 3.1 documentation
    *   Optional lightweight web UI (HTMX)
    *   Uses **EventRepository** as the unified data access layer
    *   Implements dependency injection with protocol-based interfaces

2.  **PostgreSQL 17 - Single Source of Truth:**
    *   **Event storage** (`events` table) - unified storage for all events
    *   **Metadata querying** (JSONB + GIN index with `jsonb_path_ops`)
    *   **Vector similarity** (`pgvector` VECTOR(768) + HNSW index)
    *   **Time partitioning** (`pg_partman` - monthly partitions, optional)
    *   **Graph storage** (`nodes`/`edges` tables - optional)
    *   **Task queue** (`pgmq` - optional for async operations)

3.  **Worker (Optional):**
    *   Handles async tasks from `pgmq`
    *   Batch embedding generation
    *   Background maintenance

**Architecture Principles (v1.3.0):**
- ✅ **Single Repository Pattern** - EventRepository as sole data access layer
- ✅ **Protocol-based DI** - Clean interfaces with dependency inversion
- ✅ **CQRS-inspired** - Logical separation of commands and queries
- ✅ **100% Async** - All database operations use `asyncio`
- ✅ **Modular UI v4.0** - SCADA design, 16 CSS modules, 6 JS modules, HTMX 2.0

➡️ **See detailed diagrams and explanations:** [`docs/Document Architecture.md`](docs/Document%20Architecture.md)

## ⚡ Performance Highlights

Benchmarks (local machine, ~50k events, MnemoLite v1.3.0) show excellent performance:

**Search Performance (PostgreSQL 17 + pgvector HNSW):**
*   **Vector Search (HNSW):** ~12ms P95
*   **Hybrid Search (Vector + Metadata + Time):** ~11ms P95
*   **Metadata + Time Filter (Partition Pruning):** ~3ms P95
*   **Unified search interface:** `search_vector()` handles all search types

**Embedding Generation (100% Local - Sentence-Transformers):**
*   **Model:** nomic-ai/nomic-embed-text-v1.5 (768 dimensions)
*   **Average Latency:** ~30ms (5x faster than OpenAI's 150ms)
*   **P95 Latency:** ~60ms
*   **Cache Hit:** <1ms (10x+ speedup with LRU cache)
*   **Throughput:** 50-100 embeddings/sec on CPU
*   **Cost:** $0 (no API calls, no internet required)
*   **Privacy:** 100% local, data never leaves your machine

**Test Suite (v1.3.0):**
*   **Unit Tests:** 102 passing, 11 skipped
*   **Integration Tests:** 16 passing (semantic similarity, search)
*   **Test Duration:** ~13 seconds for full unit test suite
*   **Coverage:** ~87% overall

## 🚀 Quick Start

Get MnemoLite running locally in minutes.

**Prerequisites:**
*   Docker & Docker Compose v2+
*   Git
*   **No API keys required** – 100% local deployment

**Steps:**

1.  **Clone:**
    ```bash
    git clone https://github.com/giak/MnemoLite.git
    cd MnemoLite
    ```

2.  **Configure:**
    ```bash
    cp .env.example .env
    # Review .env file and customize:
    # - Database credentials (POSTGRES_PASSWORD - change in production!)
    # - API port (API_PORT, default: 8001)
    # - Embedding model (EMBEDDING_MODEL, default: nomic-ai/nomic-embed-text-v1.5)
    # - Environment (ENVIRONMENT: development/production)
    #
    # ✅ No OPENAI_API_KEY needed! Embeddings are 100% local.
    ```

3.  **Start Services:**
    ```bash
    # Using Makefile (recommended)
    make up

    # Or using Docker Compose directly
    docker compose up -d --build
    ```

4.  **Verify:**
    ```bash
    # Check all services are running
    docker compose ps
    # Expected: mnemo-api (healthy), mnemo-postgres (healthy)

    # Test API health endpoint
    curl http://localhost:8001/health
    # Expected: {"status":"healthy","services":{"postgres":{"status":"ok"}}}

    # Check readiness
    curl http://localhost:8001/readiness
    # Expected: {"status":"ok","checks":{"database":true}}
    ```

5.  **Access Web Interface & Documentation:**
    *   **Web UI (SCADA):** http://localhost:8001/ui/ - Dashboard, Search, Graph, Monitoring
    *   **Swagger UI:** http://localhost:8001/docs
    *   **ReDoc:** http://localhost:8001/redoc
    *   **Health Status:** http://localhost:8001/health
    *   **Metrics:** http://localhost:8001/metrics

➡️ **See detailed setup:** [`docs/docker_setup.md`](docs/docker_setup.md)

## 🛠️ Usage Examples (API)

Interact with MnemoLite via its REST API (default port `8001`).

**1. Store an Event:**
```bash
curl -X POST http://localhost:8001/v1/events \
  -H "Content-Type: application/json" \
  -d '{
    "content": {"message": "User asked about project status"},
    "metadata": {"type": "interaction", "project": "Expanse", "user_id": "user123"},
    "embedding": [0.05, -0.12, ..., 0.88] # Optional: 768-dim vector (auto-generated if omitted)
  }'
```
*Note: Embeddings are automatically generated from `content.text` using the local Sentence-Transformers model (nomic-embed-text-v1.5) if not provided.*

**2. Hybrid Search (Vector Text Query + Metadata Filter):**
```bash
# Search for events similar to "project status update" AND metadata.type = "interaction"
curl -G http://localhost:8001/v1/search/ \
  --data-urlencode "vector_query=project status update" \
  --data-urlencode "filter_metadata={"type":"interaction"}" \
  --data-urlencode "limit=5" \
  --data-urlencode "distance_threshold=1.0" \
  -H "Accept: application/json"
```

**🎯 Distance Threshold Optimization:**

The `distance_threshold` parameter controls the strictness of vector similarity matching (L2 distance, range 0-2):

- **0.8** - Strict matching, high precision (fewer but very relevant results)
- **1.0** - Balanced (default, recommended for most use cases)
- **1.2** - Relaxed matching, high recall (more results, broader relevance)
- **None** or **2.0** - Top-K mode (returns K nearest neighbors without distance filtering)

**Adaptive Fallback:** If a pure vector search with a threshold returns 0 results, MnemoLite automatically falls back to top-K mode to guarantee relevant results. This fallback only applies to pure vector searches (no metadata or time filters).

Example with custom threshold:
```bash
# Strict search for very similar events
curl -G http://localhost:8001/v1/search/ \
  --data-urlencode "vector_query=critical system error" \
  --data-urlencode "distance_threshold=0.8" \
  --data-urlencode "limit=5" \
  -H "Accept: application/json"
```

**3. Metadata Search + Time Range:**
```bash
# Search for events with metadata.project = "Expanse" in January 2024
curl -G http://localhost:8001/v1/search/ \
  --data-urlencode "filter_metadata={"project":"Expanse"}" \
  --data-urlencode "ts_start=2024-01-01T00:00:00Z" \
  --data-urlencode "ts_end=2024-02-01T00:00:00Z" \
  --data-urlencode "limit=10" \
  -H "Accept: application/json"
```

## 📚 Documentation

**🚀 Getting Started:**
*   [French Quick Start Guide (`GUIDE_DEMARRAGE.md`)](GUIDE_DEMARRAGE.md) - Guide complet en français avec UI v4.0
*   [Docker Setup Guide (`docs/docker_setup.md`)](docs/docker_setup.md)
*   [Development Guide (`CLAUDE.md`)](CLAUDE.md) - For contributors

**📖 API Reference (Interactive):**
*   **Swagger UI:** http://localhost:8001/docs
*   **ReDoc:** http://localhost:8001/redoc
*   **Health Check:** http://localhost:8001/health
*   **Prometheus Metrics:** http://localhost:8001/metrics

**🏗️ Architecture & Design:**
*   [Architecture Overview (`docs/Document Architecture.md`)](docs/Document%20Architecture.md)
*   [API Specification (`docs/Specification_API.md`)](docs/Specification_API.md)
*   [Database Schema (`docs/bdd_schema.md`)](docs/bdd_schema.md)
*   [UI Design System (`docs/ui_design_system.md`)](docs/ui_design_system.md) - SCADA principles & components
*   [CSS Architecture (`static/css/README.md`)](static/css/README.md) - Modular CSS guide v4.0
*   [Phase 3.4 Validation Report (`docs/VALIDATION_FINALE_PHASE3.md`)](docs/VALIDATION_FINALE_PHASE3.md)

**📋 Project Documents:**
*   [Project Foundation (PFD) (`docs/Project Foundation Document.md`)](docs/Project%20Foundation%20Document.md)
*   [Product Requirements (PRD) (`docs/Product Requirements Document.md`)](docs/Product%20Requirements%20Document.md)
*   [Test Inventory (`docs/test_inventory.md`)](docs/test_inventory.md)

## 💻 Development Workflow

Development relies on Docker for environment consistency. **No need to install Python or PostgreSQL locally!**

**Quick Commands (using Makefile):**
```bash
make up          # Start all services
make down        # Stop all services
make restart     # Restart all services
make ps          # Show service status
make logs        # Show all logs
make api-logs    # Show API logs only
make db-logs     # Show database logs

make api-test    # Run API tests
make api-shell   # Open shell in API container
make db-shell    # Open psql shell in database

make lint        # Run linters (black, isort, flake8)
make health      # Check API health endpoint
```

**Development Workflow:**

1.  **Run Services:** `docker compose up -d` (or `make up`).
2.  **Edit Code:** Modify files in your local `api/` or `workers/` directories.
3.  **API Reload:** The `mnemo-api` container uses `uvicorn --reload` and automatically restarts when Python files in `api/` change (due to volume mounts).
4.  **Worker Reload:** The `mnemo-worker` container may need a manual restart (`docker compose restart mnemo-worker`) to pick up code changes, unless it implements its own reload mechanism.
5.  **Dependencies:** If you change `api/requirements.txt` or `workers/requirements.txt`:
    ```bash
    docker compose build api worker # Rebuild affected images
    docker compose up -d --force-recreate # Restart containers with new images
    ```
You do **not** need to install Python or dependencies directly on your host machine.

## 🤝 Contributing

Contributions are welcome!

1.  Fork the repository.
2.  Create your feature branch (`git checkout -b feature/AmazingFeature`).
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4.  Push to the branch (`git push origin feature/AmazingFeature`).
5.  Open a Pull Request.

Please open an issue first to discuss major changes. Ensure tests are updated as appropriate.

## 📊 Project Status

**Current Version:** v1.3.0
**Status:** ✅ Production Ready
**Last Updated:** 2025-10-14

**Recent Changes (v1.3.0):**
- ✅ Consolidated architecture - EventRepository as single source of truth
- ✅ Removed duplicate MemoryRepository code (-1,909 lines)
- ✅ 102/102 unit tests passing
- ✅ Zero regressions detected
- ✅ Performance maintained (<15ms P95 for searches)
- ✅ 100% local embeddings with Sentence-Transformers
- ✅ UI v4.0 - Complete refactoring with SCADA industrial design
- ✅ Modular CSS (16 modules) & structured JavaScript (6 modules)
- ✅ 4 interactive pages: Dashboard, Search, Graph, Monitoring
- ✅ HTMX 2.0 standardization with data-attribute patterns
- ✅ Full ARIA accessibility + keyboard navigation

**Roadmap:**
- 🔄 Automatic table partitioning (pg_partman) - Optional, activates at 500k+ events
- 🔄 INT8 quantization for hot/warm data tiers
- 📋 GraphQL API support
- 📋 Enhanced web UI with real-time updates

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Made with ❤️ for AI agents and cognitive memory systems**
**Star ⭐ this repo if you find it useful!**
