# MnemoLite

A lightweight, PostgreSQL-native memory system for AI applications, optimized for local deployment and semantic/hybrid search.

## Key Features

- **Semantic Vector Search**: Fast similarity search using HNSW indexes with pgvector
- **Hybrid Search**: Combine vector similarity with metadata filters (post-filtering approach)
- **Time-Partitioned Storage**: Automatic table partitioning by month for efficient scaling
- **Performance-Optimized**: Fast query performance (P95 <15ms for vector/hybrid searches)
- **Simple REST API**: API-first design with comprehensive documentation
- **HTMX Web Interface**: Lightweight UI for exploration and management

## Architecture

MnemoLite adopts a **CQRS cognitive and modular** architecture, relying **exclusively on PostgreSQL 17** and its extensions:

- **API (FastAPI + HTMX)**: Handles Command/Query operations via a REST API. Provides a web UI for exploration using HTMX.
- **PostgreSQL 17**: The core component storing all data:
    - Relational data & Metadata (JSONB).
    - Vector embeddings & HNSW indexing (`pgvector`).
    - Time-based partitioning (`pg_partman`).
    - Scheduled tasks like data tiering (quantization) (`pg_cron`).
    - Optional asynchronous task queueing (`pgmq`).
    - Graph relationships via standard `nodes`/`edges` tables queried with SQL CTEs.
- **Worker (Optional)**: Background processing for tasks like asynchronous ingestion (if using `pgmq`) or maintenance jobs triggered by `pg_cron`.

The system typically runs as 2 or 3 Docker containers (db, app, optional worker).

## Performance

Based on benchmarks with ~50k events across multiple partitions:

- **Vector Search**: P50: 11.30ms / P95: 12.21ms
- **Hybrid Search**: P50: 11.03ms / P95: 11.33ms 
- **Metadata + Time Filter**: P50: 2.97ms / P95: 3.43ms
- **Metadata-only Search**: P50: 305.13ms / P95: 400.13ms

These results demonstrate the efficiency of the HNSW index for vector searches and the effectiveness of partition pruning when using time filters.

## Quick Start

### Prerequisites

- Docker and Docker Compose v2
- Git

### Setup

1.  Clone the repository:
    ```bash
    git clone https://github.com/giak/MnemoLite.git # Assumed repo URL
    cd MnemoLite
    ```

2.  Create a `.env` file from the example:
    ```bash
    cp .env.example .env
    # Review and edit .env for your local settings (e.g., ports, DB credentials)
    ```

3.  Start the services:
    ```bash
    docker compose up -d
    ```

4.  Verify all services are running:
    ```bash
    docker compose ps
    ```

5.  Check the API health (adjust port if needed based on `.env` or `docker-compose.yml`):
    ```bash
    curl http://localhost:8001/v1/healthz
    ```

## API Usage Examples

### Store an Event with Vector Embedding

```bash
curl -X POST http://localhost:8001/v1/events \
  -H "Content-Type: application/json" \
  -d '{
    "content": {"text": "Meeting with the team about project roadmap"},
    "metadata": {"type": "meeting", "project": "MnemoLite", "participants": ["Alice", "Bob"]},
    "embedding": [0.1, 0.2, ..., 0.3]
  }'
```

### Semantic Vector Search

```bash
# Base64-encoded vector query
curl -X GET "http://localhost:8001/v1/search?vector_query=WzAuMSwgMC4yLCAuLi4sIDAuM10=&top_k=10&limit=5" \
  -H "Accept: application/json"
```

### Hybrid Search (Vector + Metadata)

```bash
curl -X GET "http://localhost:8001/v1/search?vector_query=WzAuMSwgMC4yLCAuLi4sIDAuM10=&top_k=10&filter_metadata=%7B%22type%22%3A%22meeting%22%7D&limit=5" \
  -H "Accept: application/json"
```

### Metadata Search with Time Range

```bash
curl -X GET "http://localhost:8001/v1/search?filter_metadata=%7B%22project%22%3A%22MnemoLite%22%7D&ts_start=2024-01-01T00:00:00Z&ts_end=2024-02-01T00:00:00Z&limit=10" \
  -H "Accept: application/json"
```

## Development

### Local Development Setup

1.  Install Python 3.12+
2.  Create and activate a virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate # Linux/macOS
    # venv\Scripts\activate # Windows
    ```

3.  Install API dependencies:
    ```bash
    pip install -r api/requirements.txt
    # Install worker dependencies if applicable: pip install -r workers/requirements.txt
    ```

4.  Start required services (like the database) in development mode (if different from production setup):
    ```bash
    docker compose -f docker-compose.dev.yml up -d # Or use the main docker-compose
    ```

5.  Run the API locally with auto-reload:
    ```bash
    # Assuming your FastAPI app instance is named 'app' in 'api/main.py'
    uvicorn api.main:app --reload --host 0.0.0.0 --port 8001
    ```

## Configuration

MnemoLite uses environment variables defined in the `.env` file.

Key configuration options:

- `POSTGRES_*`: PostgreSQL connection settings (user, password, db name, host, port).
- `WORKER_*`: Configuration for the optional worker (e.g., queue name if using pgmq).
- `API_*`: API server settings (e.g., host, port if not using default).
- `EMBEDDING_MODEL`: Specifies the model used for generating embeddings.

## API Documentation

When the API service is running, interactive documentation is available at:

- Swagger UI: http://localhost:8001/v1/docs
- ReDoc: http://localhost:8001/v1/redoc

Refer to `docs/v2/Specification_API.md` for the detailed OpenAPI specification.

## Project Documentation

- **PFD**: `docs/v2/Project Foundation Document.md`
- **PRD**: `docs/v2/Product Requirements Document.md`
- **Architecture**: `docs/v2/Document Architecture.md`
- **DB Schema**: `docs/v2/bdd_schema.md`
- **Stories**: `docs/agile/STORIES_EPIC-*.md`

## Contributing

1.  Fork the repository.
2.  Create a feature branch: `git checkout -b feature/your-feature-name`.
3.  Make your changes.
4.  Commit your changes: `git commit -am 'Add some feature'`.
5.  Push to the branch: `git push origin feature/your-feature-name`.
6.  Submit a pull request.

## License

[MIT License](LICENSE)
