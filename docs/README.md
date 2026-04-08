# MnemoLite Documentation

[![Version](https://img.shields.io/badge/version-5.0.0--dev-blue.svg)](https://github.com/giak/MnemoLite)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org/downloads/)
[![PostgreSQL](https://img.shields.io/badge/postgres-18-blue.svg)](https://postgresql.org/)
[![pgvector](https://img.shields.io/badge/pgvector-0.8.1-brightgreen.svg)](https://github.com/pgvector/pgvector)

**MnemoLite** is a high-performance, locally deployable cognitive memory system built on PostgreSQL 18. Zero external vector databases. Zero API dependencies.

## Features

- **Cognitive Memory** — Semantic search, time-aware storage, hybrid RRF fusion
- **Code Intelligence** — AST-based indexing, dependency graphs, 15+ languages
- **MCP Integration** — 33 tools for LLM integration
- **Triple-Layer Cache** — L1 (memory) → L2 (Redis) → L3 (PostgreSQL)

## Quick Start

```bash
git clone https://github.com/giak/MnemoLite.git
cd MnemoLite
docker compose --profile dev up -d
```

## Services

| Service | URL |
|---------|-----|
| Web UI | http://localhost:3000 |
| API | http://localhost:8001 |
| MCP | http://localhost:8002 |
| OpenObserve | http://localhost:5080 |

## Documentation

- [QUICKSTART.md](QUICKSTART.md) — Setup en 5 minutes
- [MCP.md](MCP.md) — Intégration MCP (33 outils)
- [API.md](API.md) — Endpoints REST
- [ARCHITECTURE.md](ARCHITECTURE.md) — Vue technique

## Development

```bash
make up          # Start all services
make down        # Stop all services
make test        # Run tests
make api-shell   # Shell in API container
make db-shell    # psql shell
```

## Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Vue 3 SPA │───▶│  FastAPI    │───▶│ PostgreSQL  │
│  (port 3000)│    │  (port 8001)│    │   (port 5432)│
└─────────────┘    └──────┬──────┘    └─────────────┘
                         │
                   ┌─────┴─────┐    ┌─────────────┐
                   │    MCP    │    │   Redis 7   │
                   │(port 8002)│    │  (port 6379) │
                   └───────────┘    └─────────────┘
```

## License

MIT