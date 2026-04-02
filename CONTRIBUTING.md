# Contributing to MnemoLite

Thank you for contributing to MnemoLite!

## Quick Start

```bash
git clone https://github.com/giak/MnemoLite.git
cd MnemoLite
docker compose --profile dev up -d --build
```

| Service | URL |
|---------|-----|
| Web UI | http://localhost:3000 |
| API | http://localhost:8001 |
| API Docs | http://localhost:8001/docs |
| MCP | http://localhost:8002 |

## Project Structure

```
MnemoLite/
├── api/                    # FastAPI backend
│   ├── routes/             # REST API endpoints
│   ├── services/           # Business logic
│   ├── db/                 # Database layer (repositories, query builders)
│   ├── mnemo_mcp/          # MCP server (tools, resources, models)
│   ├── interfaces/         # DIP protocols
│   └── tests/              # (legacy, see tests/)
├── frontend/               # Vue 3 SPA
│   ├── src/
│   │   ├── pages/          # 13 pages (Dashboard, Search, Memories, etc.)
│   │   ├── components/     # Reusable components
│   │   ├── composables/    # Vue composables (useDashboard, useCodeSearch, etc.)
│   │   ├── config/         # API configuration
│   │   └── types/          # TypeScript types
│   └── vite.config.ts      # Vite config with API proxy
├── tests/                  # All tests (consolidated)
│   ├── mnemo_mcp/          # MCP tests (356/358 passing)
│   ├── integration/        # Integration tests
│   ├── services/           # Service tests
│   ├── db/                 # Database tests
│   └── unit/               # Unit tests
├── docs/                   # Documentation
│   ├── 00_CONTROL/         # Project control docs
│   ├── 01_DECISIONS/       # Architecture decision records
│   ├── 02_GUIDES/          # User guides
│   ├── 03_FEATURES/        # Feature documentation
│   ├── 04_MCP/             # MCP documentation
│   └── 99_PLANS/           # EPIC plans
├── scripts/                # Utility scripts
├── docker/                 # Docker configs (Dockerfiles, nginx.conf)
├── db/                     # PostgreSQL Docker setup
└── workers/                # Background workers
```

## Development Workflow

### Backend (FastAPI)

```bash
# Run tests
docker compose exec api python -m pytest tests/mnemo_mcp/ -v

# Open shell
docker compose exec api bash

# Run migrations
docker compose exec api alembic upgrade head
```

### Frontend (Vue 3)

```bash
cd frontend
npm install
npm run dev          # Dev server with HMR
npx vue-tsc --noEmit # Type check
npm run build        # Production build
```

The Vite dev server proxies `/api` and `/v1` to the API automatically.

### Docker Profiles

```bash
docker compose --profile dev up -d   # Dev: Vite HMR on port 3000
docker compose --profile prod up -d  # Prod: Nginx on port 80
```

## Coding Standards

### Backend
- **Python 3.12+**, async-first (asyncio + asyncpg)
- **Repository Pattern** with protocol-based dependency inversion
- **CQRS-inspired** separation of commands and queries
- **Triple-layer cache**: L1 (in-memory) → L2 (Redis) → L3 (PostgreSQL)

### Frontend
- **Vue 3.5** + **TypeScript** + **Vite 7**
- **Composition API** with `<script setup>`
- **Tailwind CSS 4** + SCADA design system
- **Pinia** for state management, **Vue Router** for routing
- Components use `scada-*` CSS classes for consistent styling

### Tests
- **pytest** with async support (`pytest-asyncio`)
- Mock external services (DB, Redis, embedding models)
- Tests live in `tests/` (single consolidated directory)
- Run: `docker compose exec api python -m pytest tests/mnemo_mcp/ -v`

## Commit Conventions

Follow the project's commit style:

```
type(scope): short description

feat(EPIC-35): add search result highlighting for code search
fix: fix Redis health check endpoint
refactor: consolidate tests — merge api/tests/ into tests/
docs: update EPIC-37 plan with audit findings
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `style`

## Pull Request Process

1. Create a feature branch from `main` or the current development branch
2. Make your changes with tests
3. Run tests: `docker compose exec api python -m pytest tests/mnemo_mcp/ -v`
4. Type check frontend: `cd frontend && npx vue-tsc --noEmit`
5. Submit PR with clear description of changes

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | `mnemo` | Database user |
| `POSTGRES_PASSWORD` | `mnemopass` | Database password |
| `POSTGRES_DB` | `mnemolite` | Database name |
| `API_PORT` | `8001` | API port |
| `EMBEDDING_MODE` | `real` | `real` or `mock` |
| `VITE_API_URL` | (proxy) | Frontend API URL (dev uses proxy) |

## Architecture Overview

MnemoLite is built around PostgreSQL 18 as the single source of truth:

- **API (FastAPI)**: REST API + MCP server + web UI proxy
- **MCP (FastMCP)**: 28 tools for LLM integration
- **PostgreSQL 18**: pgvector (HNSW), pg_trgm, pg_partman
- **Redis 7**: L2 distributed cache
- **Frontend (Vue 3)**: SPA with SCADA industrial design

See [CLAUDE.md](CLAUDE.md) for detailed architecture documentation.
