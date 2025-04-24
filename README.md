# MnemoLite

A lightweight memory system for AI applications with vector search capabilities.

## Architecture

MnemoLite consists of the following components, following a **CQRS cognitive and modular** architecture:

- **API**: FastAPI-based REST API for document operations (Command/Query sides) potentially using HTMX for UI.
- **Worker**: Background processing for document ingestion, indexing, and maintenance tasks (Command Side).
- **PostgreSQL 17**: Main database handling relational data, vector storage (`pgvector`), message queueing (`pgmq`), partitioning (`pg_partman`), and graph relationships (`pgrouting`).
- **ChromaDB**: High-performance vector database for embedding storage and similarity search (Query Side).

## Quick Start

### Prerequisites

- Docker and Docker Compose v2
- Git

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/MnemoLite.git
   cd MnemoLite
   ```

2. Create a `.env` file with your configuration (or use the defaults):
   ```bash
   cp .env.example .env
   ```

3. Start the services:
   ```bash
   docker compose up -d
   ```

4. Verify all services are running:
   ```bash
   docker compose ps
   ```

5. Check the API health:
   ```bash
   curl http://localhost:8000/health
   ```

## Development

### Local Development Setup

1. Install Python 3.12
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   cd api
   pip install -r requirements.txt
   ```

4. Start services in development mode:
   ```bash
   docker compose -f docker-compose.dev.yml up -d
   ```

5. Run the API locally:
   ```bash
   cd api
   uvicorn main:app --reload
   ```

## Configuration

MnemoLite uses environment variables for configuration. You can set these in the `.env` file or directly in your environment.

Key configuration options:

- `POSTGRES_*`: PostgreSQL connection settings
- `CHROMADB_*`: ChromaDB connection settings
- `WORKER_*`: Worker configuration options
- `API_*`: API server configuration

## API Documentation

When running, API documentation is available at:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -am 'Add new feature'`
4. Push to the branch: `git push origin feature/my-feature`
5. Submit a pull request

## License

[MIT License](LICENSE)
