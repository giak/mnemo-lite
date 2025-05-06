# MnemoLite: PostgreSQL-Native Cognitive Memory

[![Build Status](https://img.shields.io/github/actions/workflow/status/giak/MnemoLite/ci.yml?branch=main&style=flat-square)](https://github.com/giak/MnemoLite/actions) <!-- Placeholder URL -->
[![Code Coverage](https://img.shields.io/codecov/c/github/giak/MnemoLite?style=flat-square)](https://codecov.io/gh/giak/MnemoLite) <!-- Placeholder URL -->
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg?style=flat-square)](https://www.python.org/downloads/)
[![PostgreSQL Version](https://img.shields.io/badge/postgres-17-blue.svg?style=flat-square)](https://www.postgresql.org/)
[![pgvector](https://img.shields.io/badge/pgvector-enabled-brightgreen.svg?style=flat-square)](https://github.com/pgvector/pgvector)

**MnemoLite** provides a high-performance, locally deployable cognitive memory system built *exclusively* on PostgreSQL 17. It empowers AI agents like **Expanse** with robust, searchable, and time-aware memory capabilities, ideal for simulation, testing, analysis, and enhancing conversational AI understanding.

Forget complex external dependencies – MnemoLite leverages the power of modern PostgreSQL extensions for a streamlined, powerful, and easy-to-manage solution.

## ✨ Key Features

*   **PostgreSQL Native:** Relies solely on PostgreSQL 17, `pgvector`, `pg_partman`, and optionally `pg_cron` & `pgmq`. No external vector databases or complex graph engines needed for local deployment.
*   🚀 **High-Performance Search:** Leverages `pgvector` with **HNSW indexing** for fast (<15ms P95) semantic vector and hybrid search directly within the database.
*   ⏳ **Time-Aware Storage:** Automatic monthly table partitioning via `pg_partman` optimizes time-based queries and simplifies data retention/lifecycle management.
*   💾 **Efficient Local Storage:** Planned Hot/Warm data tiering with **INT8 quantization** (via optional `pg_cron` job) significantly reduces disk footprint for long-term local storage.
*   🕸️ **Integrated Relational Graph:** Optional `nodes`/`edges` tables allow modeling causal links and relationships, queryable via standard SQL CTEs.
*   🧩 **Modular & API-First:** Clean REST API defined with OpenAPI 3.1 (FastAPI), facilitating integration. CQRS-inspired logical separation.
*   🖥️ **Lightweight Web UI:** Optional built-in interface using **HTMX** for easy exploration, filtering, and visualization without complex frontend builds.
*   🐳 **Simple Deployment:** Runs easily as 2-3 Docker containers (`db`, `api`, optional `worker`) via Docker Compose.

## 🏛️ Architecture Overview

MnemoLite uses a modular architecture centered around PostgreSQL:

1.  **API (FastAPI + HTMX):** Serves the REST API and the optional web UI. Handles incoming requests and orchestrates queries.
2.  **PostgreSQL 17:** The single source of truth, handling:
    *   Event data storage (`events` table).
    *   Metadata querying (JSONB + GIN index).
    *   Vector similarity search (`pgvector` + HNSW index).
    *   Time-based partitioning (`pg_partman`).
    *   Relational graph storage (`nodes`/`edges` tables).
    *   (Optional) Asynchronous task queuing (`pgmq`).
    *   (Optional) Scheduled maintenance like quantization (`pg_cron`).
3.  **Worker (Optional):** Handles asynchronous tasks dequeued from `pgmq` (e.g., complex post-processing, notifications).

➡️ **See detailed diagrams and explanations:** [`docs/Document Architecture.md`](docs/Document%20Architecture.md)

## ⚡ Performance Highlights

Benchmarks (local machine, ~50k events) show excellent performance for key operations:

*   **Vector Search (HNSW):** ~12ms P95
*   **Hybrid Search (Vector + Metadata Filter):** ~11ms P95
*   **Metadata + Time Filter (Partition Pruning):** ~3ms P95

## 🚀 Quick Start

Get MnemoLite running locally in minutes.

**Prerequisites:**
*   Docker & Docker Compose v2+
*   Git

**Steps:**

1.  **Clone:**
    ```bash
    git clone https://github.com/giak/MnemoLite.git # Replace with actual URL if different
    cd MnemoLite
    ```
2.  **Configure:**
    ```bash
    cp .env.example .env
    # --> Review and edit .env (ports, DB credentials, etc.) <--
    ```
3.  **Run:**
    ```bash
    # Recommended: Use Makefile for potential init steps
    make setup  # Or equivalent target for first-time setup
    make run    # Or equivalent target to start services
    # Fallback: Direct Docker Compose
    # docker compose up -d --build
    ```
4.  **Verify:**
    ```bash
    docker compose ps
    # Check API health (default port 8001, check .env)
    curl http://localhost:8001/v1/health
    ```

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
    "embedding": [0.05, -0.12, ..., 0.88] # Your 1536-dim vector
  }'
```

**2. Hybrid Search (Vector Text Query + Metadata Filter):**
```bash
# Search for events similar to "project status update" AND metadata.type = "interaction"
curl -G http://localhost:8001/v1/search/ \
  --data-urlencode "vector_query=project status update" \
  --data-urlencode "filter_metadata={"type":"interaction"}" \
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

*   **API Reference (Interactive):**
    *   Swagger UI: `http://localhost:8001/docs` (Default port)
    *   ReDoc: `http://localhost:8001/redoc` (Default port)
*   **Key Project Documents:**
    *   [API Specification (`docs/Specification_API.md`)](docs/Specification_API.md)
    *   [Database Schema (`docs/bdd_schema.md`)](docs/bdd_schema.md)
    *   [Architecture Detailed (`docs/Document Architecture.md`)](docs/Document%20Architecture.md)
    *   [Docker Setup (`docs/docker_setup.md`)](docs/docker_setup.md)
    *   [Project Foundation (PFD) (`docs/Project Foundation Document.md`)](docs/Project%20Foundation%20Document.md)
    *   [Product Requirements (PRD) (`docs/Product Requirements Document.md`)](docs/Product%20Requirements%20Document.md)

## 💻 Development Workflow

Development relies on Docker for environment consistency:

1.  **Run Services:** `docker compose up -d` (or `make run`).
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

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
